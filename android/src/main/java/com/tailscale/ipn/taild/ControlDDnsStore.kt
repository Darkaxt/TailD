// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.time.Instant
import java.time.format.DateTimeFormatterBuilder
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.*

data class ControlDDnsSummary(val firstSeen: Instant, val total: Long)

data class ControlDStoredFact(val key: String, val fact: ControlDDnsFact)

data class ControlDDnsPage(
    val rows: List<ControlDStoredFact> = emptyList(),
    val summaries: Map<Pair<String, String>, ControlDDnsSummary> = emptyMap(),
    val revision: Long = 0,
    val lastRead: Instant? = null,
    val coverage: String = "No stored provider read in this scope",
    val query: String = "",
    val window: DashboardWindow? = null,
)

private val dnsTimeFormat = DateTimeFormatterBuilder().appendInstant(9).toFormatter()

internal fun cdTimeKey(time: Instant): String = dnsTimeFormat.format(time)

/** Exact per-binding multisets. Complete CSV windows replace live/older facts transactionally. */
class ControlDDnsStore(context: Context) {
  private val database = DnsDatabase(context)
  private val lock = Mutex()
  private val json = Json

  suspend fun import(slice: ControlDDnsSlice, active: () -> Boolean = { true }) =
      withContext(Dispatchers.IO) {
        lock.withLock {
          val owner = currentCoroutineContext()
          database.writableDatabase.dnsTransaction {
            owner.ensureActive()
            if (!active()) throw CancellationException("DNS import cancelled")
            expire()
            val scope = slice.binding.scope
            val start = cdTimeKey(slice.from)
            val end = cdTimeKey(slice.until)
            val revision = nextRevision()
            insertOrThrow(
                "dns_reads",
                null,
                ContentValues().apply {
                  put("scope", scope)
                  put("start", start)
                  put("end", end)
                  put("read_at", cdTimeKey(Instant.now()))
                  put("state", if (slice.truncated) "incomplete" else "returned-window")
                  put("revision", revision)
                },
            )
            // A truncated multiset cannot retract a previous complete window or
            // establish how many identical occurrences it omitted. Keep prior facts.
            if (!slice.truncated) {
              delete("dns", "scope = ? AND time >= ? AND time < ?", arrayOf(scope, start, end))
              val floor = cdTimeKey(Instant.now().minusMillis(TailDHistory.RETENTION_MILLIS))
              val deletedBefore =
                  rawQuery("SELECT value FROM dns_meta WHERE key = 'deleted-before'", null).use {
                    if (it.moveToFirst()) it.getString(0) else ""
                  }
              val occurrences = mutableMapOf<String, Int>()
              slice.facts.forEach { fact ->
                owner.ensureActive()
                if (!active()) throw CancellationException("DNS import cancelled")
                val identity = fact.identity
                val ordinal = (occurrences[identity] ?: 0) + 1
                occurrences[identity] = ordinal
                val time = cdTimeKey(fact.at)
                if (time >= floor && time > deletedBefore)
                    insertOrThrow(
                        "dns",
                        null,
                        ContentValues().apply {
                          put("scope", scope)
                          put("identity", identity)
                          put("ordinal", ordinal)
                          put("time", time)
                          put("question", fact.question)
                          put("type", fact.type)
                          put(
                              "search",
                              listOf(
                                      fact.question,
                                      fact.type,
                                      fact.decision,
                                      fact.reason,
                                      when (fact.action) {
                                        0 -> "block blocked"
                                        1 -> "allow allowed bypass"
                                        2 -> "spoof"
                                        3 -> "redirect"
                                        else -> "unknown"
                                      },
                                  )
                                  .joinToString(" ")
                                  .lowercase(),
                          )
                          put("source", "csv")
                          put(
                              "raw",
                              JsonObject(fact.raw.mapValues { JsonPrimitive(it.value) }).toString(),
                          )
                          put("revision", revision)
                        },
                    )
              }
            }
            owner.ensureActive()
            if (!active()) throw CancellationException("DNS import cancelled")
          }
        }
      }

  suspend fun recent(
      binding: ControlDBinding,
      search: String = "",
      now: Instant = Instant.now(),
  ): ControlDDnsPage =
      withContext(Dispatchers.IO) {
        lock.withLock {
          database.writableDatabase.dnsTransaction {
            expire()
            val scope = binding.scope
            val until = cdTimeKey(now)
            val floor = cdTimeKey(now.minusMillis(TailDHistory.RETENTION_MILLIS))
            val recent = cdTimeKey(now.minusSeconds(15 * 60))
            val summaries = mutableMapOf<Pair<String, String>, ControlDDnsSummary>()
            rawQuery(
                    "SELECT question, type, MIN(time), COUNT(*) FROM dns WHERE scope = ? AND time >= ? AND time < ? GROUP BY question, type",
                    arrayOf(scope, floor, until),
                )
                .use { cursor ->
                  while (cursor.moveToNext()) summaries[
                      cursor.getString(0) to cursor.getString(1)] =
                      ControlDDnsSummary(Instant.parse(cursor.getString(2)), cursor.getLong(3))
                }
            val rows = mutableListOf<ControlDStoredFact>()
            rawQuery(
                    "SELECT identity, ordinal, raw FROM dns WHERE scope = ? AND time >= ? AND time < ? AND instr(search, ?) > 0 ORDER BY time DESC, identity, ordinal LIMIT 100",
                    arrayOf(scope, recent, until, search.lowercase()),
                )
                .use { cursor ->
                  while (cursor.moveToNext()) rows +=
                      ControlDStoredFact(
                          cursor.getString(0) + ":" + cursor.getInt(1),
                          fact(cursor.getString(2)),
                      )
                }
            var readAt: Instant? = null
            var coverage = "No stored provider read in this scope"
            rawQuery(
                    "SELECT read_at, state FROM dns_reads WHERE scope = ? ORDER BY revision DESC LIMIT 1",
                    arrayOf(scope),
                )
                .use {
                  if (it.moveToFirst()) {
                    readAt = Instant.parse(it.getString(0))
                    coverage =
                        if (it.getString(1) == "returned-window")
                            "Provider response imported; upstream retention and coverage are not guaranteed"
                        else "Provider response incomplete; previous stored facts preserved"
                  }
                }
            ControlDDnsPage(
                rows,
                summaries,
                currentRevision(),
                readAt,
                coverage,
                search,
                DashboardWindow(now.minusMillis(TailDHistory.RETENTION_MILLIS), now),
            )
          }
        }
      }

  suspend fun facts(
      binding: ControlDBinding,
      from: Instant,
      until: Instant,
  ): Pair<Long, List<ControlDStoredFact>> =
      withContext(Dispatchers.IO) {
        lock.withLock {
          val owner = currentCoroutineContext()
          database.writableDatabase.dnsTransaction {
            expire()
            val rows = mutableListOf<ControlDStoredFact>()
            rawQuery(
                    "SELECT identity, ordinal, raw FROM dns WHERE scope = ? AND time >= ? AND time < ? ORDER BY time, identity, ordinal",
                    arrayOf(binding.scope, cdTimeKey(from), cdTimeKey(until)),
                )
                .use {
                  while (it.moveToNext()) {
                    owner.ensureActive()
                    rows +=
                        ControlDStoredFact(
                            it.getString(0) + ":" + it.getInt(1),
                            fact(it.getString(2)),
                        )
                  }
                }
            owner.ensureActive()
            currentRevision() to rows
          }
        }
      }

  internal suspend fun returnedWindows(
      binding: ControlDBinding,
      window: DashboardWindow,
  ): List<DashboardWindow> =
      withContext(Dispatchers.IO) {
        lock.withLock {
          database.writableDatabase.dnsTransaction {
            expire()
            rawQuery(
                    "SELECT start,end FROM dns_reads WHERE scope = ? AND state = 'returned-window' AND end > ? AND start < ?",
                    arrayOf(binding.scope, cdTimeKey(window.from), cdTimeKey(window.until)),
                )
                .use { cursor ->
                  buildList {
                    while (cursor.moveToNext()) add(
                        DashboardWindow(
                            Instant.parse(cursor.getString(0)),
                            Instant.parse(cursor.getString(1)),
                        )
                    )
                  }
                }
          }
        }
      }

  suspend fun deleteHistory() =
      withContext(Dispatchers.IO) {
        lock.withLock {
          database.writableDatabase.dnsTransaction {
            delete("dns", null, null)
            delete("dns_reads", null, null)
            execSQL(
                "INSERT OR REPLACE INTO dns_meta(key,value) VALUES('deleted-before', ?)",
                arrayOf(cdTimeKey(Instant.now())),
            )
            nextRevision()
          }
        }
      }

  internal fun close() = database.close()

  private fun fact(raw: String) =
      ControlDDnsFact(
          json.parseToJsonElement(raw).jsonObject.mapValues { it.value.jsonPrimitive.content }
      )

  private fun SQLiteDatabase.currentRevision(): Long =
      rawQuery("SELECT value FROM dns_meta WHERE key = 'revision'", null).use {
        if (it.moveToFirst()) it.getString(0).toLong() else 0L
      }

  private fun SQLiteDatabase.nextRevision(): Long =
      (currentRevision() + 1).also {
        execSQL(
            "INSERT OR REPLACE INTO dns_meta(key,value) VALUES('revision',?)",
            arrayOf(it.toString()),
        )
      }

  private fun SQLiteDatabase.expire() {
    val floor = cdTimeKey(Instant.now().minusMillis(TailDHistory.RETENTION_MILLIS))
    val removed =
        delete("dns", "time < ?", arrayOf(floor)) + delete("dns_reads", "end < ?", arrayOf(floor))
    if (removed > 0) nextRevision()
  }
}

private class DnsDatabase(context: Context) :
    SQLiteOpenHelper(context, "taild-dns.sqlite", null, 1) {
  init {
    setWriteAheadLoggingEnabled(true)
  }

  override fun onCreate(db: SQLiteDatabase) {
    db.execSQL(
        "CREATE TABLE dns(scope TEXT NOT NULL,identity TEXT NOT NULL,ordinal INTEGER NOT NULL,time TEXT NOT NULL,question TEXT NOT NULL,type TEXT NOT NULL,search TEXT NOT NULL,source TEXT NOT NULL,raw TEXT NOT NULL,revision INTEGER NOT NULL,PRIMARY KEY(scope,identity,ordinal))"
    )
    db.execSQL("CREATE INDEX dns_scope_time ON dns(scope,time)")
    db.execSQL("CREATE INDEX dns_question_time ON dns(scope,question,type,time)")
    db.execSQL(
        "CREATE TABLE dns_reads(scope TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,read_at TEXT NOT NULL,state TEXT NOT NULL,revision INTEGER PRIMARY KEY)"
    )
    db.execSQL("CREATE TABLE dns_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
  }

  override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
    error("Unsupported DNS history migration; preserve the existing database")
  }
}

private inline fun <T> SQLiteDatabase.dnsTransaction(block: SQLiteDatabase.() -> T): T {
  beginTransaction()
  return try {
    block().also { setTransactionSuccessful() }
  } finally {
    endTransaction()
  }
}
