// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import java.security.MessageDigest
import java.time.Duration
import java.time.Instant

fun activityScope(domain: String, node: String, user: Long, controlURL: String): String {
  val origin = controlURL.ifBlank { "https://controlplane.tailscale.com" }.trimEnd('/')
  val digest =
      MessageDigest.getInstance("SHA-256").digest(origin.toByteArray(Charsets.UTF_8)).joinToString(
          ""
      ) {
        "%02x".format(it)
      }
  return "$digest/$domain/$node/$user"
}

data class DeviceObservation(val id: String, val name: String, val online: Boolean?)

data class ActivitySnapshot(
    val scope: String,
    val settings: Map<String, String>,
    val devices: List<DeviceObservation>,
    val settingIdentities: Map<String, String> = emptyMap(),
)

data class ActivityEvent(
    val kind: String,
    val subject: String,
    val detail: String,
    val identity: String = "",
)

data class RecordedActivity(val id: Long, val at: Long, val scope: String, val event: ActivityEvent)

/** Only compares observations in one uninterrupted scope, never infers missed events. */
class ActivityHistoryReducer {
  private var previous: ActivitySnapshot? = null

  fun reset() {
    previous = null
  }

  fun observe(next: ActivitySnapshot): List<ActivityEvent> {
    val old = previous?.takeIf { it.scope == next.scope }
    val events = mutableListOf<ActivityEvent>()
    next.settings.forEach { (key, value) ->
      if (
          old?.settings?.get(key) != value ||
              old?.settingIdentities?.get(key) != next.settingIdentities[key]
      ) {
        events +=
            ActivityEvent(
                if (old?.settings?.containsKey(key) != true) "baseline" else key,
                when (key) {
                  "connection" -> "Connection"
                  "exit-node" -> "Exit node"
                  "tailscale-dns" -> "Tailscale DNS"
                  "health" -> "Health"
                  else -> key
                },
                value,
                next.settingIdentities[key].orEmpty(),
            )
      }
    }
    val oldDevices = old?.devices?.associateBy { it.id }.orEmpty()
    next.devices.forEach { device ->
      val before = oldDevices[device.id]
      if (before == null || before.online != device.online) {
        events +=
            ActivityEvent(
                if (before == null) "baseline" else "presence",
                device.name,
                when (device.online) {
                  true -> "Online"
                  false -> "Offline"
                  null -> "Unknown"
                },
                device.id,
            )
      }
    }
    val nextIds = next.devices.map { it.id }.toSet()
    oldDevices.values
        .filter { it.id !in nextIds }
        .forEach {
          events +=
              ActivityEvent("peer-list", it.name, "No longer in the observed peer list", it.id)
        }
    previous = next
    return events
  }
}

fun relativeLastSeen(value: String?, now: Instant = Instant.now()): String {
  val instant = value?.let { runCatching { Instant.parse(it) }.getOrNull() } ?: return "Unknown"
  if (instant.isBefore(Instant.EPOCH)) return "Unknown"
  val seconds = Duration.between(instant, now).seconds
  if (seconds < 0) return "In the future"
  return when {
    seconds < 60 -> "Just now"
    seconds < 3600 -> "${seconds / 60}m ago"
    seconds < 172800 -> "${seconds / 3600}h ago"
    seconds < 2592000 -> "${seconds / 86400} days ago"
    seconds < 31536000 -> {
      val months = seconds / 2592000
      "$months ${if (months == 1L) "month" else "months"} ago"
    }
    else -> {
      val years = seconds / 31536000
      "$years ${if (years == 1L) "year" else "years"} ago"
    }
  }
}
