package com.tailscale.ipn.taild

import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.uiautomator.By
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** Host force-stops the previous instrumentation process before this test starts. */
class TailDDashboardRestartTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun newProcessReadsRetainedDashboardScopesWithoutReplayingProviderWrites() = runBlocking {
    val fixture = NativeControlDSession(reset = false, compose = compose)
    with(fixture) {
      try {
        val local = TailDHistory(fixtureContext, scope)
        val dashboard = DashboardModel(scope, local, model, flowOf("dashboard-scope"))
        app.setDashboardForEmulatorTest(dashboard)
        launch()
        assertFalse(model.state.value.hasWrite)
        click(By.text("Dashboard"))
        val restored =
            dashboard.state.first {
              !it.dnsLoading && !it.activityLoading && it.dns != null && it.activity != null
            }
        assertEquals(125L, restored.dns!!.total)
        assertEquals(230, restored.activity!!.rows.size)
        assertEquals(168, restored.hours)
        node(By.text("125 stored DNS observations"))
        click(By.text("Activity"))
        node(By.text("230 local observations"))
        phase("capture-dashboard-restart")
        phase("assert-read-only-dashboard")
      } finally {
        app.setDashboardForEmulatorTest(null)
        close()
      }
    }
  }
}
