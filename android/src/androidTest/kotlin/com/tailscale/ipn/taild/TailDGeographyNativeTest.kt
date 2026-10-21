package com.tailscale.ipn.taild

import android.content.ComponentCallbacks
import android.content.res.Configuration
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.uiautomator.By
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** Real offline paths + native touch -> the existing HTTPS/SQLite dashboard/filter boundary. */
class TailDGeographyNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun mapCountryScopeUnknownEmptyAndAutomaticTheme() = runBlocking {
    val fixture = NativeControlDSession(reset = true, compose = compose)
    with(fixture) {
      val dashboard =
          DashboardModel(scope, TailDHistory(fixtureContext, scope), model, flowOf("map-scope"))
      try {
        launch()
        model.configureRead("read-fixture", null)
        ready { !it.busySetup && it.inventory != null }
        model.select(
            model.state.value.inventory!!.endpoints.first(),
            ControlDClient("phone", "This emulator"),
        )
        ready { !it.busyHistory && it.page.summaries["blocked.invalid" to "A"]?.total == 124L }
        app.setDashboardForEmulatorTest(dashboard)
        click(By.text("Dashboard"))
        val snapshot = dashboard.state.first { !it.dnsLoading && it.dns?.total == 125L }.dns!!
        assertEquals(124L, snapshot.countries["US"])
        assertEquals(1L, snapshot.countries["DE"])
        assertEquals(1L, snapshot.countries[DNS_GEOGRAPHY_UNKNOWN])
        click(By.text("Geography"))
        fun mapNode(): SemanticsNodeInteraction {
          // A configuration callback precedes the new composition/off-thread asset
          // load. Await the actual rendered map, including after a theme change.
          compose.waitUntil(30_000) {
            compose.onAllNodesWithTag("taild-dns-country-map").fetchSemanticsNodes().isNotEmpty()
          }
          return compose
              .onNodeWithTag("taild-dns-country-map", useUnmergedTree = true)
              .performScrollTo()
        }
        mapNode().assertIsDisplayed()
        phase("capture-map-light")
        val mapSnapshot = dashboard.state.value.dns!!
        val us = readDnsCountryShapes(context.assets).first { it.code == "US" }
        val point =
            (100..300)
                .flatMap { y -> (160..400).map { x -> x to y } }
                .filter { (x, y) ->
                  us.hit.contains(x, y) &&
                      us.hit.contains(x - 3, y - 3) &&
                      us.hit.contains(x + 3, y + 3)
                }
                .minBy { (x, y) -> (x - 270) * (x - 270) + (y - 180) * (y - 180) }
        mapNode().performTouchInput {
          val factor = minOf(width / 1000f, height / 500f)
          click(
              Offset(
                  (width - 1000 * factor) / 2 + point.first * factor,
                  (height - 500 * factor) / 2 + point.second * factor,
              )
          )
        }
        dashboard.state.first { it.dnsFilter.country == "US" && it.dnsDetails != null }
        scrollTo("taild-dashboard-details", "124 matching observations")
        val selected = dashboard.state.value.dnsDetails!!
        assertTrue(
            "Map drill-down preserves the displayed snapshot",
            mapSnapshot.binding == selected.binding &&
                mapSnapshot.window == selected.window &&
                mapSnapshot.revision == selected.revision &&
                mapSnapshot.rows == selected.rows,
        )
        assertEquals(
            "US",
            dashboard.state.value.dnsFilter.json()["answer_country"]!!.toString().trim('"'),
        )
        phase("capture-map-drilldown")
        scrollTo("taild-dashboard-details", "Close").click()
        val dark = CompletableDeferred<Unit>()
        val callback =
            object : ComponentCallbacks {
              override fun onConfigurationChanged(configuration: Configuration) {
                if (
                    configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK ==
                        Configuration.UI_MODE_NIGHT_YES
                )
                    dark.complete(Unit)
              }

              override fun onLowMemory() {}
            }
        context.registerComponentCallbacks(callback)
        try {
          phase("switch-theme")
          dark.await()
        } finally {
          context.unregisterComponentCallbacks(callback)
        }
        mapNode().assertIsDisplayed()
        assertEquals(mapSnapshot.total, dashboard.state.value.dns!!.total)
        assertEquals(mapSnapshot.countries, dashboard.state.value.dns!!.countries)
        phase("capture-map-dark")
        scrollTo("taild-dashboard-content", "Unknown / unmapped · 1", contains = true)
        scrollTo("taild-dashboard-content", DNS_GEOGRAPHY_UNKNOWN).click()
        dashboard.state.first { it.dnsFilter.country == DNS_GEOGRAPHY_UNKNOWN }
        scrollTo("taild-dashboard-details", "1 matching observations")
        scrollTo("taild-dashboard-details", "Close").click()
        // This database belongs only to the isolated fixture, never production history.
        model.state.first { !it.busyHistory }
        fixtureContext.openOrCreateDatabase("taild-dns.sqlite", 0, null).use {
          it.execSQL("DELETE FROM dns")
        }
        dashboard.refresh()
        dashboard.state.first { !it.dnsLoading && it.dns?.total == 0L }
        mapNode().assertIsDisplayed()
        scrollTo("taild-dashboard-content", "No answer countries observed", contains = true)
        mapNode()
        phase("capture-map-empty")
        model.select(
            model.state.value.inventory!!.endpoints.first(),
            ControlDClient("other", "Other fixture client"),
        )
        ready { !it.busyHistory && it.page.summaries["other-client.invalid" to "A"]?.total == 1L }
        val changed =
            dashboard.state
                .first {
                  !it.dnsLoading && it.dns?.binding?.client == "other" && it.dns?.total == 1L
                }
                .dns!!
        assertEquals(mapOf("US" to 1L), changed.countries)
        mapNode().assertIsDisplayed()
        phase("capture-map-scope")
        phase("assert-read-only-dashboard")
      } finally {
        app.setDashboardForEmulatorTest(null)
        close()
        model.vault.remove(ControlDCredentials.Access.READ)
        model.vault.remove(ControlDCredentials.Access.WRITE)
      }
    }
  }
}
