// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Binder
import android.os.Build
import android.os.IBinder
import androidx.annotation.Keep
import kotlin.system.exitProcess
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/** Optional Shizuku boundary. All operations are fixed, UID-scoped and caller-checked. */
@Keep
class AppAccessUserService @Keep constructor(private val context: Context) :
    IAppAccessService.Stub() {
  private val ownerUid = context.applicationInfo.uid
  private val json = Json
  private val chain = 8 // OEM_DENY_2; never reset or disable a shared system chain.

  private fun service(name: String, stub: String): Any {
    val binder =
        Class.forName("android.os.ServiceManager")
            .getMethod("getService", String::class.java)
            .invoke(null, name) as? IBinder ?: error("$name service is unavailable")
    return Class.forName(stub).getMethod("asInterface", IBinder::class.java).invoke(null, binder)
        ?: error("$name interface is unavailable")
  }

  private fun <T> authorized(action: () -> T): T {
    check(Binder.getCallingUid() == ownerUid) { "Caller is not this TailD installation" }
    check(Build.VERSION.SDK_INT >= 33) {
      "This Android version has no supported app-control readback"
    }
    val identity = Binder.clearCallingIdentity()
    return try {
      action()
    } finally {
      Binder.restoreCallingIdentity(identity)
    }
  }

  private fun command(vararg args: String): List<String> {
    val process = ProcessBuilder(*args).redirectErrorStream(true).start()
    val lines = mutableListOf<String>()
    var size = 0
    // Drain before waiting even on over-budget output; no pipe deadlock or partial snapshot.
    process.inputStream.bufferedReader().useLines { input ->
      input.forEach { line ->
        size += line.length
        if (size <= 4_000_000) lines.add(line)
      }
    }
    check(process.waitFor() == 0 && size <= 4_000_000) {
      "Platform readback failed or exceeded its budget"
    }
    return lines
  }

  private fun profiles(): List<Int> {
    val lines = command("/system/bin/cmd", "user", "list")
    check(lines.firstOrNull()?.trim() == "Users:") { "Android profile inventory is unavailable" }
    return lines
        .drop(1)
        .filter { it.isNotBlank() }
        .map {
          Regex("UserInfo\\{(\\d+):").find(it)?.groupValues?.get(1)?.toInt()
              ?: error("Unrecognized Android profile inventory")
        }
        .distinct()
        .sorted()
        .also { check(it.isNotEmpty()) }
  }

  private fun packages(profile: Int): List<AppAccessIdentity> {
    val pm = service("package", "android.content.pm.IPackageManager\$Stub")
    val flags = (PackageManager.GET_SIGNING_CERTIFICATES or PackageManager.GET_PERMISSIONS).toLong()
    val slice =
        pm.javaClass
            .getMethod(
                "getInstalledPackages",
                Long::class.javaPrimitiveType,
                Int::class.javaPrimitiveType,
            )
            .invoke(pm, flags, profile) ?: error("Package inventory is unavailable")
    @Suppress("UNCHECKED_CAST")
    val packages = slice.javaClass.getMethod("getList").invoke(slice) as List<PackageInfo>
    check(packages.size <= 5000) { "Package inventory exceeds supported snapshot size" }
    return packages
        .filter { it.applicationInfo != null }
        .groupBy { it.applicationInfo!!.uid }
        .filter { (uid, _) -> uid / 100_000 == profile && uid % 100_000 >= 10_000 }
        .map { (uid, group) ->
          AppAccessIdentity(
              uid,
              group
                  .map { info ->
                    val signers =
                        info.signingInfo
                            ?.apkContentsSigners
                            ?.map { signer ->
                              java.security.MessageDigest.getInstance("SHA-256")
                                  .digest(signer.toByteArray())
                                  .joinToString("") { "%02x".format(it) }
                            }
                            .orEmpty()
                            .sorted()
                    AppAccessPackage(
                        info.packageName,
                        info.applicationInfo!!.loadLabel(context.packageManager).toString(),
                        signers,
                        info.firstInstallTime,
                        info.lastUpdateTime,
                        info.longVersionCode,
                    )
                  }
                  .sortedBy { it.name },
          )
        }
        .sortedBy { it.uid }
  }

  private fun snapshot(profile: Int): AppAccessSnapshot {
    val users = profiles()
    require(profile in users) { "Android profile is no longer available" }
    val connectivity = service("connectivity", "android.net.IConnectivityManager\$Stub")
    val enabled =
        connectivity.javaClass
            .getMethod("getFirewallChainEnabled", Int::class.javaPrimitiveType)
            .invoke(connectivity, chain) as Boolean
    val blocked =
        appAccessBlockedUids(
            command("/system/bin/dumpsys", "connectivity", "trafficcontroller", "verbose")
        )
    val apps = packages(profile)
    // Check the typed API against the complete map for this scope, including permitted UIDs.
    val getRule =
        connectivity.javaClass.getMethod(
            "getUidFirewallRule",
            Int::class.javaPrimitiveType,
            Int::class.javaPrimitiveType,
        )
    apps.forEach {
      val rule = getRule.invoke(connectivity, chain, it.uid) as Int
      check(rule == if (it.uid in blocked) 2 else 1) {
        "Firewall readback changed or is inconsistent"
      }
    }
    check(
        enabled ==
            connectivity.javaClass
                .getMethod("getFirewallChainEnabled", Int::class.javaPrimitiveType)
                .invoke(connectivity, chain)
    ) {
      "Firewall state changed during readback"
    }
    return AppAccessSnapshot(profile, users, apps, enabled, blocked)
  }

  @Synchronized
  override fun inspect(profile: Int): String = authorized {
    json.encodeToString(snapshot(profile)).also {
      check(it.toByteArray(Charsets.UTF_8).size <= 700_000) {
        "Profile snapshot exceeds the Binder budget"
      }
    }
  }

  @Synchronized
  override fun apply(request: String): String = authorized {
    require(request.length < 64_000) { "App control request exceeds its budget" }
    val wanted = json.decodeFromString<AppAccessRequest>(request)
    val before = snapshot(wanted.identity.profile)
    require(before.revision == wanted.revision) {
      "Firewall state changed; refresh and review again"
    }
    planAppAccess(before, wanted.identity, wanted.blocked, wanted.owned, ownerUid)
    val connectivity = service("connectivity", "android.net.IConnectivityManager\$Stub")
    connectivity.javaClass
        .getMethod(
            "setUidFirewallRule",
            Int::class.javaPrimitiveType,
            Int::class.javaPrimitiveType,
            Int::class.javaPrimitiveType,
        )
        .invoke(connectivity, chain, wanted.identity.uid, if (wanted.blocked) 2 else 1)
    if (wanted.blocked && !before.chainEnabled) {
      connectivity.javaClass
          .getMethod(
              "setFirewallChainEnabled",
              Int::class.javaPrimitiveType,
              Boolean::class.javaPrimitiveType,
          )
          .invoke(connectivity, chain, true)
    }
    val after = snapshot(wanted.identity.profile)
    val expected =
        if (wanted.blocked) before.blockedUids + wanted.identity.uid
        else before.blockedUids - wanted.identity.uid
    check(
        after.blockedUids == expected &&
            after.chainEnabled == (before.chainEnabled || wanted.blocked)
    ) {
      "Firewall changed during apply; outcome needs reconciliation"
    }
    check(
        after.apps.singleOrNull { it.uid == wanted.identity.uid }?.fingerprint ==
            wanted.identity.fingerprint
    ) {
      "App identity changed during apply; outcome needs reconciliation"
    }
    json.encodeToString(after)
  }

  override fun destroy() {
    check(Binder.getCallingUid() in setOf(ownerUid, 0, 2000)) { "Unauthorized service destruction" }
    // User-selected rules are durable OS state; closing the view must not silently unblock apps.
    exitProcess(0)
  }
}
