// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import java.security.MessageDigest
import kotlinx.serialization.Serializable

internal fun appAccessDigest(value: String): String =
    MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8)).joinToString(
        ""
    ) {
      "%02x".format(it)
    }

@Serializable
internal data class AppAccessPackage(
    val name: String,
    val label: String,
    val signers: List<String>,
    val installed: Long,
    val updated: Long,
    val version: Long,
)

@Serializable
internal data class AppAccessIdentity(val uid: Int, val packages: List<AppAccessPackage>) {
  val profile: Int
    get() = uid / 100_000

  val fingerprint: String
    get() =
        appAccessDigest(
            "$uid\n" +
                packages
                    .sortedBy { it.name }
                    .joinToString("\n") {
                      "${it.name}:${it.signers.sorted().joinToString(",")}:${it.installed}:${it.updated}:${it.version}"
                    }
        )
}

@Serializable
internal data class AppAccessSnapshot(
    val profile: Int,
    val profiles: List<Int>,
    val apps: List<AppAccessIdentity>,
    val chainEnabled: Boolean,
    val blockedUids: Set<Int>,
) {
  val revision: String
    get() = appAccessDigest("$chainEnabled:${blockedUids.sorted().joinToString(",")}")
}

@Serializable internal data class AppAccessOwned(val identity: AppAccessIdentity, val phase: String)

@Serializable
internal data class AppAccessRequest(
    val identity: AppAccessIdentity,
    val blocked: Boolean,
    val revision: String,
    val owned: AppAccessOwned? = null,
)

/** Shared preflight in the normal app and privileged boundary. No platform writes here. */
internal fun planAppAccess(
    snapshot: AppAccessSnapshot,
    identity: AppAccessIdentity,
    blocked: Boolean,
    owned: AppAccessOwned?,
    callerUid: Int,
): AppAccessRequest {
  require(identity.uid % 100_000 >= 10_000 && identity.uid != callerUid) {
    "This UID cannot be controlled"
  }
  require(identity.packages.none { it.name == "io.github.darkaxt.taildns" }) {
    "TailD's VPN identity cannot be blocked in any profile"
  }
  require(snapshot.profile == identity.profile) { "Android profile changed" }
  val current = snapshot.apps.singleOrNull { it.uid == identity.uid }
  require(current?.fingerprint == identity.fingerprint) {
    "App identity changed; refresh before changing access"
  }
  require(identity.packages.isNotEmpty() && identity.packages.all { it.signers.isNotEmpty() }) {
    "Signing identity is unavailable"
  }
  if (blocked) {
    require(identity.uid !in snapshot.blockedUids) {
      "An existing block is not owned by this change"
    }
    require(snapshot.chainEnabled || snapshot.blockedUids.isEmpty()) {
      "The disabled firewall chain has existing rules; activation would change other policy"
    }
  } else {
    require(owned?.identity?.fingerprint == identity.fingerprint) {
      "No matching TailD-owned block"
    }
    require(identity.uid in snapshot.blockedUids) {
      "The recorded block is already inactive; reconcile first"
    }
  }
  return AppAccessRequest(identity, blocked, snapshot.revision, owned)
}

/** Strict complete platform map parsing; unsupported/partial dumps never mean an empty chain. */
internal fun appAccessBlockedUids(lines: List<String>): Set<Int> {
  val start = lines.indexOfFirst { it.trim() == "sUidOwnerMap:" }
  val end = lines.indexOfFirst { it.trim() == "sUidPermissionMap:" }
  require(start >= 0 && end > start) { "Complete firewall readback is unavailable" }
  return buildSet {
    for (line in lines.subList(start + 1, end).filter { it.isNotBlank() }) {
      val parts = line.trim().split(Regex("\\s+"))
      val uid = parts.first().toIntOrNull()
      require(
          uid != null &&
              uid >= 0 &&
              parts.size > 1 &&
              parts.drop(1).all { it.matches(Regex("[A-Z][A-Z0-9_]*|[0-9]+")) } &&
              parts.none { it.contains("ERROR", true) }
      ) {
        "Unrecognized firewall readback"
      }
      if ("OEM_DENY_2_MATCH" in parts) add(uid)
    }
  }
}
