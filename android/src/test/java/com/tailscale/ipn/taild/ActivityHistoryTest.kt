package com.tailscale.ipn.taild

import org.junit.Assert.*
import org.junit.Test

class ActivityHistoryTest {
  @Test
  fun controlOriginsWithIdenticalNodeIDsCannotShareHistory() {
    assertNotEquals(
        activityScope("same", "node", 1, "https://one.invalid"),
        activityScope("same", "node", 1, "https://two.invalid"),
    )
    assertEquals(
        activityScope("same", "node", 1, ""),
        activityScope("same", "node", 1, "https://controlplane.tailscale.com/"),
    )
  }

  @Test
  fun baselineDoesNotInventPresenceTransitions() {
    val reducer = ActivityHistoryReducer()
    val snapshot =
        ActivitySnapshot(
            "tailnet/self",
            mapOf("connection" to "Running"),
            listOf(DeviceObservation("peer", "Laptop", null)),
        )
    val first = reducer.observe(snapshot)
    assertTrue(first.all { it.kind == "baseline" })
    assertTrue(first.any { it.detail == "Unknown" })
    assertTrue(reducer.observe(snapshot).isEmpty())
    val changed =
        reducer.observe(snapshot.copy(devices = listOf(DeviceObservation("peer", "Laptop", true))))
    assertEquals(listOf(ActivityEvent("presence", "Laptop", "Online", "peer")), changed)
  }

  @Test
  fun scopeSwitchStartsBaselineAndMissingPeerIsNotOffline() {
    val reducer = ActivityHistoryReducer()
    val snapshot =
        ActivitySnapshot("one", emptyMap(), listOf(DeviceObservation("id", "Phone", true)))
    reducer.observe(snapshot)
    assertTrue(
        reducer.observe(snapshot.copy(devices = emptyList())).none { it.detail == "Offline" }
    )
    assertTrue(reducer.observe(snapshot.copy(scope = "two")).all { it.kind == "baseline" })
    reducer.reset()
    assertTrue(reducer.observe(snapshot).all { it.kind == "baseline" })
  }

  @Test
  fun relativeTimesKeepUnknownAndFutureDistinct() {
    val now = java.time.Instant.parse("2026-10-20T10:00:00Z")
    assertEquals("Unknown", relativeLastSeen(null, now))
    assertEquals("Unknown", relativeLastSeen("0001-01-01T00:00:00Z", now))
    assertEquals("In the future", relativeLastSeen("2026-10-21T10:00:00Z", now))
    assertEquals("24h ago", relativeLastSeen("2026-10-19T10:00:00Z", now))
    assertEquals("3 days ago", relativeLastSeen("2026-10-17T10:00:00Z", now))
    assertEquals("1 month ago", relativeLastSeen("2026-09-20T10:00:00Z", now))
  }
}
