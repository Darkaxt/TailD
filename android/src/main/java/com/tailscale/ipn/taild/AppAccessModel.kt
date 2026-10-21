// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.ComponentName
import android.content.Context
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.IBinder
import android.os.Process
import com.tailscale.ipn.BuildConfig
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import rikka.shizuku.Shizuku

internal data class AppAccessState(
    val status: String =
        "App blocking is optional. Connect Shizuku to inspect Android firewall state.",
    val snapshot: AppAccessSnapshot? = null,
    val owned: List<AppAccessOwned> = emptyList(),
    val busy: Boolean = false,
    val connected: Boolean = false,
    val preview: AppAccessRequest? = null,
    val error: String? = null,
    val journalAvailable: Boolean = true,
)

/** One fixed optional backend, private ownership journal and explicit reviewed operations. */
internal class AppAccessModel(context: Context, private val scope: CoroutineScope) {
  private val context = context.applicationContext
  private val preferences = context.getSharedPreferences("taild.app-access", Context.MODE_PRIVATE)
  private val json = Json
  private val mutable = MutableStateFlow(AppAccessState())
  val state = mutable.asStateFlow()
  private val lock = Mutex()
  @Volatile private var active = false
  @Volatile private var binding = false
  @Volatile private var writing = false
  @Volatile private var service: IAppAccessService? = null
  private var journalReadable = true
  private var profile = Process.myUid() / 100_000
  private val args =
      Shizuku.UserServiceArgs(ComponentName(context, AppAccessUserService::class.java))
          .tag("taild-app-access-v1")
          .version(BuildConfig.VERSION_CODE)
          .daemon(false)
          .processNameSuffix("app_access")

  init {
    try {
      val saved =
          json.decodeFromString<List<AppAccessOwned>>(preferences.getString("owned", "[]")!!)
      require(saved.map { it.identity.uid }.distinct().size == saved.size)
      mutable.update { it.copy(owned = saved) }
    } catch (_: Exception) {
      journalReadable = false
      mutable.update {
        it.copy(
            journalAvailable = false,
            error = "The app-control ownership journal cannot be read. No rules will be changed.",
        )
      }
    }
  }

  private fun save(entries: List<AppAccessOwned>) {
    check(journalReadable) { "Ownership journal is unavailable" }
    check(preferences.edit().putString("owned", json.encodeToString(entries)).commit()) {
      "Ownership journal could not be saved; no further change will be sent"
    }
    mutable.update { it.copy(owned = entries) }
  }

  private fun failed(error: Throwable) {
    val cause = error.cause ?: error
    mutable.update {
      it.copy(
          busy = false,
          snapshot = null,
          preview = null,
          status = "App control needs attention; refresh to inspect current state.",
          error =
              if (cause is android.os.DeadObjectException)
                  "App-control connection was lost. Reconnect and inspect the recorded rules."
              else cause.message ?: cause.javaClass.simpleName,
      )
    }
  }

  private val received = Shizuku.OnBinderReceivedListener { if (active) availability() }
  private val dead = Shizuku.OnBinderDeadListener {
    service = null
    binding = false
    mutable.update {
      it.copy(
          connected = false,
          busy = writing,
          preview = null,
          status =
              "Shizuku disconnected. Existing blocks may remain; reconnect to inspect or restore access.",
      )
    }
  }
  private val permission = Shizuku.OnRequestPermissionResultListener { code, grant ->
    if (code == 4733 && active) {
      if (grant == PackageManager.PERMISSION_GRANTED) bind()
      else mutable.update { it.copy(status = "Shizuku permission was not granted.") }
    }
  }
  private val connection =
      object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, binder: IBinder) {
          binding = false
          if (!active && !writing) {
            disconnect()
            return
          }
          service = IAppAccessService.Stub.asInterface(binder)
          mutable.update { it.copy(connected = true) }
          refresh()
        }

        override fun onServiceDisconnected(name: ComponentName) = dead.onBinderDead()
      }

  fun open() {
    active = true
    Shizuku.addBinderReceivedListenerSticky(received)
    Shizuku.addBinderDeadListener(dead)
    Shizuku.addRequestPermissionResultListener(permission)
    availability()
  }

  fun close() {
    active = false
    Shizuku.removeBinderReceivedListener(received)
    Shizuku.removeBinderDeadListener(dead)
    Shizuku.removeRequestPermissionResultListener(permission)
    if (!writing) disconnect()
  }

  private fun disconnect() {
    service = null
    binding = false
    runCatching { Shizuku.unbindUserService(args, connection, true) }
    // remove=true destroys the remote record but leaves the SDK callback cache
    // until asynchronous Binder death. Forget that binding synchronously too:
    // an immediate activity/theme recreation must bind through a fresh callback,
    // rather than have the old death event clear the replacement connection.
    runCatching { Shizuku.unbindUserService(args, connection, false) }
    mutable.update { it.copy(connected = false, preview = null) }
  }

  private fun availability() {
    try {
      if (!Shizuku.pingBinder()) {
        mutable.update {
          it.copy(
              connected = false,
              status = "Start Shizuku, then connect. No app rules are changed by setup.",
          )
        }
        return
      }
      if (Shizuku.getVersion() < 13) {
        mutable.update { it.copy(status = "App control requires Shizuku 13 or newer.") }
        return
      }
      if (Shizuku.checkSelfPermission() != PackageManager.PERMISSION_GRANTED) {
        mutable.update {
          it.copy(status = "Connect to authorize the optional Shizuku app-control backend.")
        }
        return
      }
      if (preferences.getBoolean("configured", false)) bind()
    } catch (error: RuntimeException) {
      // Binder liveness and a subsequent SDK call are not atomic. Report a
      // lost external backend instead of crashing or retrying a policy write.
      service = null
      binding = false
      mutable.update { it.copy(connected = false) }
      failed(error)
    }
  }

  fun connect() {
    try {
      check(Shizuku.pingBinder()) { "Start Shizuku first; use its official setup instructions." }
      check(Shizuku.getVersion() >= 13) { "App control requires Shizuku 13 or newer" }
      check(preferences.edit().putBoolean("configured", true).commit()) {
        "Setup could not be saved"
      }
      if (Shizuku.checkSelfPermission() == PackageManager.PERMISSION_GRANTED) bind()
      else Shizuku.requestPermission(4733)
    } catch (error: Exception) {
      failed(error)
    }
  }

  private fun bind() {
    if (binding || service != null || !active) return
    try {
      binding = true
      mutable.update { it.copy(status = "Connecting to app control…", error = null) }
      Shizuku.bindUserService(args, connection)
    } catch (error: Exception) {
      binding = false
      failed(error)
    }
  }

  fun selectProfile(value: Int) {
    if (state.value.busy) return
    profile = value
    mutable.update { it.copy(snapshot = null, preview = null) }
    refresh()
  }

  fun refresh() {
    val backend = service ?: return
    if (state.value.busy) return
    mutable.update {
      it.copy(busy = true, preview = null, error = null, status = "Reading Android firewall state…")
    }
    scope.launch {
      lock.withLock {
        try {
          val result =
              withContext(Dispatchers.IO) {
                json.decodeFromString<AppAccessSnapshot>(backend.inspect(profile))
              }
          // A read never reapplies a lost/rebooted block or adopts a foreign deny rule.
          if (service === backend)
              mutable.update {
                it.copy(
                    snapshot = result,
                    busy = false,
                    connected = true,
                    status =
                        "Android firewall state inspected. Other network restrictions may also apply.",
                )
              }
        } catch (error: Exception) {
          if (service === backend) failed(error)
        } finally {
          if (service !== backend) {
            mutable.update { it.copy(busy = false) }
            // Finish the obsolete read, then inspect the new connection once.
            // This is coalescing a real service transition, never replaying a write.
            if (active && service != null) refresh()
          }
        }
      }
    }
  }

  fun review(identity: AppAccessIdentity, blocked: Boolean) {
    try {
      check(journalReadable && state.value.connected && !state.value.busy && !writing) {
        "Refresh app-control state first"
      }
      val owned = state.value.owned.singleOrNull { it.identity.uid == identity.uid }
      check(state.value.owned.all { it.phase == "ACTIVE" }) {
        "Reconcile the pending outcome before another policy change"
      }
      val request =
          planAppAccess(
              state.value.snapshot ?: error("Refresh first"),
              identity,
              blocked,
              owned,
              Process.myUid(),
          )
      mutable.update { it.copy(preview = request, error = null) }
    } catch (error: Exception) {
      failed(error)
    }
  }

  fun dismiss() {
    if (!writing) mutable.update { it.copy(preview = null) }
  }

  fun applyReviewed() {
    val request = state.value.preview ?: return
    val backend = service ?: return
    if (state.value.busy || writing || !journalReadable) return
    writing = true
    mutable.update { it.copy(busy = true, preview = null, error = null) }
    scope.launch {
      lock.withLock {
        try {
          withContext(Dispatchers.IO) {
            val pending =
                AppAccessOwned(
                    request.identity,
                    if (request.blocked) "PENDING_BLOCK" else "PENDING_UNBLOCK",
                )
            save(state.value.owned.filterNot { it.identity.uid == request.identity.uid } + pending)
            val result =
                json.decodeFromString<AppAccessSnapshot>(
                    backend.apply(json.encodeToString(request))
                )
            val remaining = state.value.owned.filterNot { it.identity.uid == request.identity.uid }
            save(
                if (request.blocked) remaining + AppAccessOwned(request.identity, "ACTIVE")
                else remaining
            )
            mutable.update {
              it.copy(snapshot = result, busy = false, status = "App rule changed and read back.")
            }
          }
        } catch (error: Exception) {
          failed(error)
          mutable.update {
            it.copy(
                status = "Change outcome needs reconciliation. Refresh before any further action."
            )
          }
        } finally {
          writing = false
          if (!active) withContext(Dispatchers.Main) { disconnect() }
        }
      }
    }
  }

  /** Explicit readback reconciliation; never sends a policy write. */
  fun reconcile(identity: AppAccessIdentity) {
    if (state.value.busy || !state.value.connected) return
    val backend = service ?: return
    val owned = state.value.owned.singleOrNull { it.identity.uid == identity.uid } ?: return
    mutable.update { it.copy(busy = true, preview = null, error = null) }
    scope.launch {
      lock.withLock {
        try {
          withContext(Dispatchers.IO) {
            // Recovery entries include their own profile. They can be opened from
            // another profile's list, but must be inspected against that identity.
            val snapshot =
                json.decodeFromString<AppAccessSnapshot>(backend.inspect(identity.profile))
            val active = identity.uid in snapshot.blockedUids
            if (active)
                require(
                    snapshot.apps.singleOrNull { it.uid == identity.uid }?.fingerprint ==
                        owned.identity.fingerprint
                ) {
                  "Recorded identity changed. Its rule cannot safely be removed for a different installation. Reconnect after an Android restart to inspect recovery."
                }
            save(
                state.value.owned.filterNot { it.identity.uid == identity.uid } +
                    if (active) listOf(owned.copy(phase = "ACTIVE")) else emptyList()
            )
            profile = snapshot.profile
            mutable.update {
              it.copy(
                  snapshot = snapshot,
                  busy = false,
                  error = null,
                  status =
                      if (active)
                          "Recorded rule is present. Review Remove TailD block to restore access."
                      else "Recorded rule is inactive; no policy write was sent.",
              )
            }
          }
        } catch (error: Exception) {
          failed(error)
        }
      }
    }
  }
}
