// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

/** Returned windows are fetch checkpoints, never a promise of provider coverage. */
internal fun historyCatchup(
    window: DashboardWindow,
    returned: List<DashboardWindow>,
): List<DashboardWindow> {
  val missing = mutableListOf<DashboardWindow>()
  var cursor = window.from
  returned
      .sortedBy { it.from }
      .forEach { known ->
        val from = maxOf(known.from, window.from)
        val until = minOf(known.until, window.until)
        if (from < until) {
          if (cursor < from) missing += DashboardWindow(cursor, from)
          cursor = maxOf(cursor, until)
        }
      }
  if (cursor < window.until) missing += DashboardWindow(cursor, window.until)
  // Always reconcile the recent interval. Merge it with missing intervals before slicing.
  val merged = mutableListOf<DashboardWindow>()
  (missing + DashboardWindow(maxOf(window.from, window.until.minusSeconds(900)), window.until))
      .sortedBy { it.from }
      .forEach {
        val last = merged.lastOrNull()
        if (last != null && it.from <= last.until)
            merged[merged.lastIndex] = DashboardWindow(last.from, maxOf(last.until, it.until))
        else merged += it
      }
  return buildList {
    merged.asReversed().forEach { interval ->
      var end = interval.until
      while (end > interval.from) {
        val start = maxOf(interval.from, end.minusSeconds(86400))
        add(DashboardWindow(start, end))
        end = start
      }
    }
  }
}
