// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.tailscale.ipn.ui.model.Health
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.model.Netmap
import com.tailscale.ipn.ui.notifier.Notifier
import java.security.MessageDigest
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** App-private, single-writer history. It never starts a service or keeps the VPN alive. */
class TailDHistory(context: Context, scope: CoroutineScope) {
  private val preferences = context.getSharedPreferences("taild.analytics", Context.MODE_PRIVATE)
  private val database = ActivityDatabase(context)
  private val commands = Channel<Command>(Channel.UNLIMITED)
  private val reducer = ActivityHistoryReducer()
  private var currentScope = ""
  private var started = false
  private var viewScope: String? = null
  private val _enabled = MutableStateFlow(preferences.getBoolean("enabled", false))
  val enabled = _enabled.asStateFlow()
  private val _rows = MutableStateFlow<List<RecordedActivity>>(emptyList())
  val rows = _rows.asStateFlow()
  private val _error = MutableStateFlow<String?>(null)
  val error = _error.asStateFlow()

  private sealed interface Command {
    data class Enable(val value: Boolean) : Command

    data class Observe(val at: Long, val snapshot: ActivitySnapshot) : Command

    data class Event(val at: Long, val scope: String, val event: ActivityEvent, val key: String?) :
        Command

    data class Refresh(val scope: String?) : Command

    data class Barrier(val done: CompletableDeferred<Unit>) : Command

    data class Query(
        val scope: String?,
        val window: DashboardWindow,
        val done: CompletableDeferred<DashboardActivitySnapshot>,
    ) : Command

    data class Dns(
        val store: ControlDDnsStore,
        val slice: ControlDDnsSlice,
        val done: CompletableDeferred<Boolean>,
        val finished: CompletableDeferred<Unit>,
    ) : Command

    data object Delete : Command
  }

  init {
    val writer =
        scope.launch(Dispatchers.IO) {
          for (command in commands) {
            try {
              when (command) {
                is Command.Query -> {
                  try {
                    val removed =
                        database.writableDatabase.delete(
                            "activity",
                            "at < ?",
                            arrayOf((System.currentTimeMillis() - RETENTION_MILLIS).toString()),
                        )
                    if (removed > 0) _rows.value = readRecent()
                    if (command.done.isActive)
                        command.done.complete(
                            readWindow(command.scope, command.window) { command.done.isActive }
                        )
                  } catch (_: CancellationException) {
                    command.done.cancel()
                  } catch (_: Exception) {
                    command.done.completeExceptionally(
                        IllegalStateException("Activity history unavailable")
                    )
                  }
                  continue
                }
                is Command.Dns -> {
                  try {
                    if (command.done.isActive && _enabled.value) {
                      command.store.import(command.slice) { command.done.isActive }
                      command.done.complete(true)
                    } else command.done.complete(false)
                  } catch (_: CancellationException) {
                    command.done.cancel()
                  } catch (problem: Exception) {
                    command.done.completeExceptionally(problem)
                  } finally {
                    command.finished.complete(Unit)
                  }
                  continue
                }
                is Command.Enable -> {
                  check(preferences.edit().putBoolean("enabled", command.value).commit())
                  _enabled.value = command.value
                  reducer.reset()
                  started = false
                  if (command.value) {
                    observe(
                        Notifier.state.value,
                        Notifier.netmap.value,
                        Notifier.prefs.value,
                        Notifier.health.value,
                    )
                  }
                }
                is Command.Observe ->
                    if (_enabled.value) {
                      val snapshot = command.snapshot
                      database.writableDatabase.inTransaction {
                        if (!started || currentScope != snapshot.scope) {
                          val previousAt =
                              rawQuery(
                                      "SELECT at FROM checkpoint WHERE scope = ?",
                                      arrayOf(snapshot.scope),
                                  )
                                  .use { if (it.moveToFirst()) it.getLong(0) else null }
                          insert(
                              command.at,
                              snapshot.scope,
                              ActivityEvent(
                                  "coverage",
                                  "Local observation",
                                  "New observation baseline. Unobserved events, including process, recording or storage gaps, remain unknown." +
                                      (previousAt?.let {
                                        " Previous observation: ${java.time.Instant.ofEpochMilli(it)}."
                                      } ?: ""),
                              ),
                          )
                          reducer.reset()
                        }
                        reducer.observe(snapshot).forEach { insert(command.at, snapshot.scope, it) }
                        // Coverage is an observation checkpoint, not a claim of complete event
                        // delivery.
                        execSQL(
                            "INSERT OR REPLACE INTO checkpoint(scope, at) VALUES(?, ?)",
                            arrayOf<Any?>(snapshot.scope, command.at),
                        )
                      }
                      currentScope = snapshot.scope
                      started = true
                    }
                is Command.Event ->
                    if (_enabled.value && command.scope.isNotEmpty()) {
                      database.writableDatabase.insert(
                          command.at,
                          command.scope,
                          command.event,
                          command.key,
                      )
                    }
                Command.Delete -> {
                  database.writableDatabase.inTransaction {
                    delete("activity", null, null)
                    delete("checkpoint", null, null)
                  }
                  reducer.reset()
                  started = false
                }
                is Command.Refresh -> viewScope = command.scope
                is Command.Barrier -> {
                  command.done.complete(Unit)
                  continue
                }
              }
              database.writableDatabase.delete(
                  "activity",
                  "at < ?",
                  arrayOf((System.currentTimeMillis() - RETENTION_MILLIS).toString()),
              )
              _rows.value = readRecent()
              _error.value = null
            } catch (_: Exception) {
              // Do not leak paths, provider data or credentials; explicit refresh can re-read.
              reducer.reset()
              started = false
              _error.value =
                  "Activity history unavailable. Previously displayed observations may be stale. Refresh to read again."
            }
          }
        }
    writer.invokeOnCompletion {
      commands.close()
      while (true) {
        val pending = commands.tryReceive().getOrNull() ?: break
        when (pending) {
          is Command.Query ->
              pending.done.completeExceptionally(
                  IllegalStateException("Activity history unavailable")
              )
          is Command.Dns -> {
            pending.done.cancel()
            pending.finished.complete(Unit)
          }
          is Command.Barrier ->
              pending.done.completeExceptionally(
                  IllegalStateException("Activity history unavailable")
              )
          else -> Unit
        }
      }
      database.close()
    }
    commands.trySend(Command.Refresh(null))
  }

  fun setEnabled(value: Boolean) {
    commands.trySend(Command.Enable(value))
  }

  fun refresh(scope: String?) {
    commands.trySend(Command.Refresh(scope))
  }

  fun deleteHistory() {
    commands.trySend(Command.Delete)
  }

  internal suspend fun awaitIdle() {
    val done = CompletableDeferred<Unit>()
    commands.send(Command.Barrier(done))
    done.await()
  }

  suspend fun query(scope: String?, window: DashboardWindow): DashboardActivitySnapshot {
    val done = CompletableDeferred<DashboardActivitySnapshot>()
    try {
      commands.send(Command.Query(scope, window, done))
      return done.await()
    } finally {
      if (!done.isCompleted) done.cancel()
    }
  }

  /** DNS commits and recording changes share this actor's deterministic boundary. */
  suspend fun importDns(store: ControlDDnsStore, slice: ControlDDnsSlice): Boolean {
    val done = CompletableDeferred<Boolean>()
    val finished = CompletableDeferred<Unit>()
    var enqueued = false
    try {
      commands.send(Command.Dns(store, slice, done, finished))
      enqueued = true
      return done.await()
    } finally {
      if (!done.isCompleted) done.cancel()
      if (enqueued) withContext(NonCancellable) { finished.await() }
    }
  }

  fun observe(
      state: Ipn.State,
      netmap: Netmap.NetworkMap?,
      prefs: Ipn.Prefs?,
      health: Health.State?,
      notify: Ipn.Notify? = null,
  ) {
    if (!_enabled.value) return
    val map = netmap ?: return
    val at = System.currentTimeMillis()
    val scope = activityScope(map, prefs) ?: return
    val settings = buildMap {
      put("connection", state.name)
      prefs?.let {
        put(
            "exit-node",
            it.activeExitNodeID?.let { id ->
              map.Peers?.find { peer -> peer.StableID == id }?.displayName
                  ?: "Selected node unavailable"
            } ?: "Disabled",
        )
        put("tailscale-dns", if (it.CorpDNS) "Enabled" else "Disabled")
      }
      health?.let {
        put(
            "health",
            it.Warnings.orEmpty()
                .toSortedMap()
                .values
                .joinToString("; ") {
                  it?.Title?.takeIf(String::isNotBlank) ?: "Warning details unavailable"
                }
                .ifEmpty { "No reported warnings" },
        )
      }
    }
    val devices =
        (listOf(map.SelfNode) + map.Peers.orEmpty()).map {
          DeviceObservation(
              it.StableID,
              it.displayName,
              if (it.StableID == map.SelfNode.StableID && state == Ipn.State.Running) true
              else it.Online,
          )
        }
    commands.trySend(
        Command.Observe(
            at,
            ActivitySnapshot(
                scope,
                settings,
                devices,
                mapOf(
                    "exit-node" to prefs?.activeExitNodeID.orEmpty(),
                    "health" to health?.Warnings.orEmpty().keys.sorted().joinToString(","),
                ),
            ),
        )
    )
    notify
        ?.OutgoingFiles
        ?.filter { it.Finished }
        ?.forEach {
          commands.trySend(
              Command.Event(
                  at,
                  scope,
                  ActivityEvent(
                      "taildrop.sent",
                      "Outgoing transfer",
                      if (it.Succeeded) "Succeeded" else "Failed",
                      it.PeerID,
                  ),
                  it.ID.takeIf(String::isNotEmpty)?.let { id -> "sent:$id:${it.Succeeded}" },
              )
          )
        }
    notify
        ?.IncomingFiles
        ?.filter { it.Done == true }
        ?.forEach {
          commands.trySend(
              Command.Event(
                  at,
                  scope,
                  ActivityEvent(
                      "taildrop.received",
                      "Incoming transfer",
                      "Daemon receipt observed; document save is separate",
                  ),
                  sourceKey("received:${it.Started}:${it.Name}"),
              )
          )
        }
  }

  fun documentSaved(scope: String?, transferIdentity: String) {
    if (!_enabled.value) return
    commands.trySend(
        Command.Event(
            System.currentTimeMillis(),
            scope ?: "unknown",
            ActivityEvent(
                "taildrop.saved",
                "Incoming transfer",
                "Saved to the selected Android document folder",
            ),
            sourceKey("saved:$transferIdentity"),
        )
    )
  }

  private fun readRecent(): List<RecordedActivity> {
    val scope = viewScope ?: return emptyList()
    val records = mutableListOf<RecordedActivity>()
    database.readableDatabase
        .rawQuery(
            "SELECT id, at, scope, kind, subject, detail, identity FROM activity WHERE scope = ? ORDER BY at DESC, id DESC LIMIT 200",
            arrayOf(scope),
        )
        .use {
          while (it.moveToNext()) {
            records +=
                RecordedActivity(
                    it.getLong(0),
                    it.getLong(1),
                    it.getString(2),
                    ActivityEvent(
                        it.getString(3),
                        it.getString(4),
                        it.getString(5),
                        it.getString(6),
                    ),
                )
          }
        }
    return records
  }

  private fun readWindow(
      scope: String?,
      window: DashboardWindow,
      active: () -> Boolean,
  ): DashboardActivitySnapshot {
    val rows = mutableListOf<RecordedActivity>()
    if (scope != null)
        database.readableDatabase
            .rawQuery(
                "SELECT id,at,scope,kind,subject,detail,identity FROM activity WHERE scope = ? AND at >= ? AND at < ? ORDER BY at,id",
                arrayOf(
                    scope,
                    maxOf(
                            activityMillisCeiling(window.from),
                            System.currentTimeMillis() - RETENTION_MILLIS,
                        )
                        .toString(),
                    activityMillisCeiling(window.until).toString(),
                ),
            )
            .use { cursor ->
              while (cursor.moveToNext()) {
                if (!active()) throw CancellationException("Activity query cancelled")
                rows +=
                    RecordedActivity(
                        cursor.getLong(0),
                        cursor.getLong(1),
                        cursor.getString(2),
                        ActivityEvent(
                            cursor.getString(3),
                            cursor.getString(4),
                            cursor.getString(5),
                            cursor.getString(6),
                        ),
                    )
              }
            }
    return DashboardActivitySnapshot(scope, window, rows)
  }

  companion object {
    const val RETENTION_MILLIS = 7L * 24 * 60 * 60 * 1000
  }
}

private class ActivityDatabase(context: Context) :
    SQLiteOpenHelper(context, "taild-history.sqlite", null, 1) {
  init {
    setWriteAheadLoggingEnabled(true)
  }

  override fun onCreate(db: SQLiteDatabase) {
    db.execSQL(
        "CREATE TABLE activity(id INTEGER PRIMARY KEY, at INTEGER NOT NULL, scope TEXT NOT NULL, kind TEXT NOT NULL, subject TEXT NOT NULL, detail TEXT NOT NULL, identity TEXT NOT NULL, source_key TEXT, UNIQUE(scope, source_key))"
    )
    db.execSQL("CREATE INDEX activity_scope_time ON activity(scope, at)")
    db.execSQL("CREATE TABLE checkpoint(scope TEXT PRIMARY KEY, at INTEGER NOT NULL)")
  }

  override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
    error("Unsupported history migration; preserve the existing database")
  }
}

private inline fun SQLiteDatabase.inTransaction(block: SQLiteDatabase.() -> Unit) {
  beginTransaction()
  try {
    block()
    setTransactionSuccessful()
  } finally {
    endTransaction()
  }
}

private fun SQLiteDatabase.insert(
    at: Long,
    scope: String,
    event: ActivityEvent,
    key: String? = null,
) {
  execSQL(
      "INSERT OR IGNORE INTO activity(at, scope, kind, subject, detail, identity, source_key) VALUES(?, ?, ?, ?, ?, ?, ?)",
      arrayOf<Any?>(at, scope, event.kind, event.subject, event.detail, event.identity, key),
  )
}

private fun sourceKey(value: String) =
    MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8)).joinToString(
        ""
    ) {
      "%02x".format(it)
    }

fun activityScope(map: Netmap.NetworkMap?, prefs: Ipn.Prefs?): String? {
  if (map == null || prefs == null) return null
  return activityScope(map.Domain, map.SelfNode.StableID, map.SelfNode.User, prefs.ControlURL)
}
