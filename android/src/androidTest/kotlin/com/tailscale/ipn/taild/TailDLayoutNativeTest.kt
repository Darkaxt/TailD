package com.tailscale.ipn.taild

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.test.uiautomator.By
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** Native scope/disclosure/export feedback and measured responsive UI, never a physical device. */
@OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class)
class TailDLayoutNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun reviewFindingsUseRealScopeAndDisclosure() = runBlocking {
    val fixture = NativeControlDSession(reset = true, compose = compose)
    with(fixture) {
      val dashboard = DashboardModel(scope, app.tailDHistory, model, flowOf("layout-scope"))
      app.setDashboardForEmulatorTest(dashboard)
      try {
        launch()
        for (label in listOf("Tailscale", "Control D", "Firewall", "Dashboard")) {
          if (
              compose
                  .onAllNodesWithTag("taild-main-navigation-rail")
                  .fetchSemanticsNodes()
                  .isNotEmpty()
          )
              compose
                  .onNodeWithTag("taild-main-navigation-rail")
                  .performScrollToNode(hasText(label))
          val target =
              compose
                  .onNode(hasText(label) and hasClickAction())
                  .assertIsDisplayed()
                  .fetchSemanticsNode()
                  .boundsInRoot
          compose
              .onNodeWithText(label, useUnmergedTree = true)
              .assertIsDisplayed()
              .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { read ->
                val result = mutableListOf<TextLayoutResult>()
                assertTrue(read(result))
                assertTrue("$label has measured text", result.isNotEmpty())
                // Material's centered paragraph can exceed its intrinsic Text size
                // while every glyph fits the actual navigation item. Check painted
                // line spans and ellipsis against that item's measured bounds.
                for (layout in result) {
                  assertTrue(
                      "$label fits its target height",
                      layout.multiParagraph.height <= target.height + 1,
                  )
                  for (line in 0 until layout.lineCount) {
                    assertFalse("$label is not ellipsized", layout.isLineEllipsized(line))
                    assertTrue(
                        "$label line fits its target width",
                        layout.getLineRight(line) - layout.getLineLeft(line) <= target.width + 1,
                    )
                  }
                }
              }
        }
        click(By.text("Dashboard"))
        click(By.text("Geography"))
        compose.onNodeWithTag("taild-select-endpoint").assertIsDisplayed()
        compose.onNodeWithText("Retry DNS query").assertDoesNotExist()
        phase("capture-layout-empty")
        compose.onNodeWithTag("taild-select-endpoint").performClick()
        content("Set up Control D")
        model.configureRead("read-fixture", null)
        ready { !it.busySetup && it.inventory != null }
        click(By.text("No endpoint selected"))
        click(By.text("Emulator endpoint"))
        ready { it.binding != null && !it.busyHistory && it.policy != null }
        compose.onNodeWithText("Latest 100 observations", substring = true).assertDoesNotExist()
        compose.onNodeWithContentDescription("Scope & coverage").performClick()
        compose.onNodeWithText("Shared profile · 2 affected endpoints").assertIsDisplayed()
        scrollTo(
            "",
            "Latest 100 observations in 15 minutes. First seen and Total use all retained observations in the last 7 days, independently of search. Gaps do not mean zero activity.",
        )
        scrollTo("", "Close scope details").click()
        compose.onNodeWithText("Latest 100 observations", substring = true).assertDoesNotExist()
        val list =
            compose.onNodeWithTag("taild-control-d-content").fetchSemanticsNode().boundsInRoot
        val first =
            compose
                .onAllNodesWithTag("taild-dns-entry")
                .fetchSemanticsNodes()
                .minBy { it.boundsInRoot.top }
                .boundsInRoot
        val root = compose.onNodeWithTag("taild-app-viewport").fetchSemanticsNode().boundsInRoot
        instrumentation.sendStatus(
            0,
            android.os.Bundle().apply {
              putString("taild_layout_density", "first=$first list=$list viewport=$root")
            },
        )
        val large = compose.density.fontScale >= 1.3f
        assertTrue(
            "Results occupy the viewport: first=$first list=$list root=$root",
            (list.bottom - first.top) / root.height >= if (large) 0.50f else 0.60f,
        )
        if (!large)
            assertTrue(
                "First result starts near the top: $first in $root",
                (first.top - root.top) / root.height <= 0.35f,
            )
        compose
            .onAllNodesWithContentDescription("DNS details for allowed.invalid")
            .onFirst()
            .performClick()
        compose.onNodeWithText("filter · fixture, category", substring = true).assertExists()
        compose
            .onAllNodesWithContentDescription("DNS details for allowed.invalid")
            .onFirst()
            .performClick()
        phase("capture-layout-control-d")
        click(By.text("Dashboard"))
        dashboard.state.first { !it.dnsLoading && it.dns != null }
        scrollTo("taild-dashboard-tabs", "Geography", horizontal = true).click()
        compose.waitUntil(30_000) {
          compose.onAllNodesWithTag("taild-dns-country-map").fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithTag("taild-dns-country-map").performScrollTo().assertIsDisplayed()
        val density = compose.density.density
        val column =
            compose.onNodeWithTag("taild-dashboard-column").fetchSemanticsNode().boundsInRoot
        assertTrue("Bounded working column", column.width <= 840 * density + 1)
        val rootWidth = context.resources.displayMetrics.widthPixels.toFloat()
        assertTrue("Column fits the screen", column.left >= 0 && column.right <= rootWidth + 1)
        phase("capture-layout-map")
        scrollTo("taild-dashboard-tabs", "Applications", horizontal = true).click()
        compose.onNodeWithTag("taild-traffic-search").assertIsDisplayed()
        compose.waitUntil(30_000) {
          compose
              .onAllNodesWithContentDescription("Export selected snapshot")
              .fetchSemanticsNodes()
              .isNotEmpty()
        }
        for (tag in listOf("taild-traffic-export", "taild-traffic-os-totals")) {
          val bounds =
              compose
                  .onNodeWithTag(tag)
                  .performScrollTo()
                  .assertIsDisplayed()
                  .fetchSemanticsNode()
                  .touchBoundsInRoot
          assertTrue(
              "$tag minimum target: $bounds at density $density",
              bounds.width >= 48 * density - 1 && bounds.height >= 48 * density - 1,
          )
        }
        compose.onNodeWithContentDescription("OS app totals").performClick()
        compose
            .onNodeWithTag("taild-traffic-content")
            .performScrollToNode(hasText("Manage Usage Access"))
        compose.onNodeWithText("Manage Usage Access").assertIsDisplayed()
        compose
            .onNodeWithTag("taild-traffic-content")
            .performScrollToNode(hasTestTag("taild-traffic-search"))
        phase("capture-layout-applications")
        // Real export feedback and frozen content are exercised in the existing Dashboard/traffic
        // tests.
        phase("assert-read-only-dashboard")
      } catch (failure: Throwable) {
        phase("capture-layout-failed")
        throw failure
      } finally {
        app.setDashboardForEmulatorTest(null)
        close()
        model.vault.remove(ControlDCredentials.Access.READ)
      }
    }
  }
}
