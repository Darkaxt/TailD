package com.tailscale.ipn.taild

import java.time.Instant
import org.junit.Assert.*
import org.junit.Test

class HistoryCatchupTest {
  private val end = Instant.parse("2026-10-20T12:00:00Z")
  private val window = DashboardWindow(end.minusSeconds(7 * 86400), end)

  @Test
  fun initialReadIsBoundedDailyNewestFirstWithoutOverlap() {
    val parts = historyCatchup(window, emptyList())
    assertEquals(7, parts.size)
    assertEquals(window.until, parts.first().until)
    assertEquals(window.from, parts.last().from)
    parts.zipWithNext().forEach { (new, old) -> assertEquals(new.from, old.until) }
  }

  @Test
  fun returnedWindowsOnlyNeedRecentOverlapAndUnfetchedGaps() {
    val gap = DashboardWindow(window.from.plusSeconds(86400), window.from.plusSeconds(86400 + 3600))
    val parts =
        historyCatchup(
            window,
            listOf(DashboardWindow(window.from, gap.from), DashboardWindow(gap.until, end)),
        )
    assertEquals(listOf(DashboardWindow(end.minusSeconds(900), end), gap), parts)
    assertEquals(
        listOf(DashboardWindow(end.minusSeconds(900), end)),
        historyCatchup(window, listOf(window, window)),
    )
  }
}
