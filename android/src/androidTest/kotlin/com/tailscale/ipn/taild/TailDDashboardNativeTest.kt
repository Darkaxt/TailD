package com.tailscale.ipn.taild

import android.content.ComponentCallbacks
import android.content.res.Configuration
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.uiautomator.*
import java.time.Instant
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/**
 * Complete native Dashboard workflow against the same isolated HTTPS/SQLite boundary as Control D.
 */
class TailDDashboardNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun scopedPanelsDrilldownExportNavigationAndRecordingLifecycle() = runBlocking {
    val fixture = NativeControlDSession(reset = true, compose = compose)
    with(fixture) {
      suspend fun dashboardContent(text: String, contains: Boolean = false): UiObject2 =
          scrollTo("taild-dashboard-content", text, contains = contains)
      suspend fun dashboardTab(label: String) {
        scrollTo("taild-dashboard-tabs", label, horizontal = true).click()
        compose.waitForIdle()
      }
      var localJob: Job? = null
      try {
        phase("dashboard-before-launch")
        launch()
        phase("dashboard-after-launch")
        model.configureRead("read-fixture", null)
        ready { !it.busySetup && it.inventory != null }
        phase("dashboard-inventory-ready")
        model.select(
            model.state.value.inventory!!.endpoints.first(),
            ControlDClient("phone", "This emulator"),
        )
        ready { !it.busyHistory && it.page.summaries["blocked.invalid" to "A"]?.total == 124L }
        assertEquals(
            125,
            model.store
                .facts(
                    model.state.value.binding!!,
                    Instant.now().minusSeconds(7 * 86400),
                    Instant.now(),
                )
                .second
                .size,
        )
        // Repeated reads and daily-window boundaries do not multiply identical occurrences.
        model.refreshHistory()
        ready { !it.busyHistory }
        assertEquals(124L, model.state.value.page.summaries["blocked.invalid" to "A"]!!.total)
        fixtureContext.deleteDatabase("taild-history.sqlite")
        fixtureContext.getSharedPreferences("taild.analytics", 0).edit().clear().commit()
        val lifetime = SupervisorJob().also { localJob = it }
        val localScope = CoroutineScope(lifetime + Dispatchers.Default)
        val local = TailDHistory(fixtureContext, localScope)
        local.setEnabled(true)
        local.awaitIdle()
        repeat(230) { local.documentSaved("dashboard-scope", "content://synthetic/document-$it") }
        local.awaitIdle()
        val tailnet = MutableStateFlow<String?>("dashboard-scope")
        val dashboard = DashboardModel(localScope, local, model, tailnet)
        app.setDashboardForEmulatorTest(dashboard)
        click(By.text("Dashboard"))
        val shown =
            dashboard.state.first {
              !it.dnsLoading && !it.activityLoading && it.dns != null && it.activity != null
            }
        assertEquals(168, shown.hours)
        assertEquals(125L, shown.dns!!.total)
        assertEquals(230, shown.activity!!.rows.size)
        dashboardContent("125 stored DNS observations")
        phase("capture-dashboard")
        dashboardContent("Blocked · 124").click()
        phase("capture-details-before-count")
        scrollTo("taild-dashboard-details", "124 matching observations")
        val selected = checkNotNull(dashboard.state.value.dnsDetails)
        phase("capture-drilldown")
        // The actual native CreateDocument launcher preserves the selected snapshot and
        // cancellation.
        scrollTo("taild-dashboard-details", "Export").click()
        val picker =
            context.packageManager
                .resolveActivity(
                    android.content
                        .Intent(android.content.Intent.ACTION_CREATE_DOCUMENT)
                        .setType("application/json")
                        .addCategory(android.content.Intent.CATEGORY_OPENABLE),
                    0,
                )!!
                .activityInfo
                .packageName
        assertTrue(device.wait(Until.hasObject(By.pkg(picker)), 30_000))
        fun documentNode(selector: BySelector): UiObject2 =
            device.wait(Until.findObject(By.copy(selector).pkg(picker)), 30_000)
                ?: error("Document picker node missing: $selector")
        documentNode(By.desc("Show roots")).click()
        device.waitForIdle()
        val downloads = device.findObject(UiSelector().packageName(picker).text("Downloads"))
        assertTrue(downloads.waitForExists(30_000))
        assertTrue(downloads.click())
        device.waitForIdle()
        val filename = "TailD-dashboard-native-${System.currentTimeMillis()}.json"
        documentNode(By.clazz("android.widget.EditText")).text = filename
        device.waitForIdle()
        documentNode(
                By.text(
                    java.util.regex.Pattern.compile(
                        "save",
                        java.util.regex.Pattern.CASE_INSENSITIVE,
                    )
                )
            )
            .click()
        dashboard.state.first { !it.exportPending && !it.exportWriting && it.exportNotice != null }
        val uri = checkNotNull(dashboard.exportedDocumentForTest)
        val delivered =
            context.contentResolver.openInputStream(uri)!!.bufferedReader().use { it.readText() }
        val output = Json.parseToJsonElement(delivered).jsonObject
        assertEquals(
            124,
            output.getValue("metadata").jsonObject.getValue("record_count").jsonPrimitive.int,
        )
        scrollTo("taild-dashboard-details", "Export").click()
        assertTrue(device.wait(Until.hasObject(By.pkg(picker)), 30_000))
        device.pressBack()
        assertTrue(
            "Document cancellation returns to TailD",
            device.wait(Until.hasObject(By.pkg(context.packageName)), 30_000),
        )
        dashboard.state.first { !it.exportPending && it.exportNotice == "Export cancelled." }
        assertEquals(124, output.getValue("records").jsonArray.size)
        phase("document-exported")
        assertEquals(
            selected.revision,
            output.getValue("metadata").jsonObject.getValue("history_revision").jsonPrimitive.long,
        )
        scrollTo("taild-dashboard-details", "Close").click()
        dashboardTab("Geography")
        dashboardContent("Coverage & details").click()
        dashboardContent("Provider DNS-answer geography")
        dashboardContent("Country coverage · 125 / 125", contains = true)
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
        } catch (error: Throwable) {
          instrumentation.sendStatus(
              0,
              android.os.Bundle().apply { putString("taild_failure", error.stackTraceToString()) },
          )
          throw error
        } finally {
          context.unregisterComponentCallbacks(callback)
        }
        dashboardContent("Provider DNS-answer geography")
        assertEquals(125L, dashboard.state.value.dns!!.total)
        phase("capture-dashboard-dark")
        dashboardTab("Activity")
        dashboardContent("230 local observations")
        // Queries remain app-owned while hidden. A source scope switch never relabels old facts.
        click(By.text("Tailscale"))
        tailnet.value = "different-scope"
        dashboard.state.first { it.activity == null }
        dashboard.refresh()
        dashboard.state.first { !it.activityLoading && it.activity?.scope == "different-scope" }
        assertTrue(dashboard.state.value.activity!!.rows.isEmpty())
        click(By.text("Dashboard"))
        dashboardContent("0 local observations")
        tailnet.value = "dashboard-scope"
        val restored =
            dashboard.state.first { !it.activityLoading && it.activity?.scope == "dashboard-scope" }
        assertEquals(230, restored.activity!!.rows.size)
        dashboardContent("230 local observations")
        // Pause the actual HTTP boundary; switching destinations cannot cancel its owner.
        model.state.first { !it.busyHistory }
        phase("hold-history")
        model.refreshHistory(full = true)
        phase("history-waiting")
        assertTrue(model.state.value.busyHistory)
        click(By.text("Control D"))
        click(By.text("Tailscale"))
        phase("release-history")
        ready { !it.busyHistory }
        click(By.text("Dashboard"))
        dashboardTab("Overview")
        dashboard.state.first { !it.dnsLoading && it.dns?.total == 125L }
        // An intentionally held SQLite writer proves the chart query finishes after navigation.
        model.state.first { !it.busyHistory }
        fixtureContext.openOrCreateDatabase("taild-dns.sqlite", 0, null).use { blocker ->
          blocker.beginTransactionNonExclusive()
          try {
            dashboard.refresh()
            assertTrue(dashboard.state.value.dnsLoading)
            click(By.text("Tailscale"))
          } finally {
            blocker.endTransaction()
          }
        }
        dashboard.state.first { !it.dnsLoading && it.dns?.total == 125L }
        click(By.text("Dashboard"))
        dashboardContent("125 stored DNS observations")
        // A real SQLite read failure ends in a usable error panel; explicit retry recovers.
        fixtureContext.openOrCreateDatabase("taild-dns.sqlite", 0, null).use {
          it.execSQL("ALTER TABLE dns RENAME TO dns_unavailable_fixture")
        }
        dashboard.refresh()
        dashboard.state.first { !it.dnsLoading && it.dnsError != null }
        dashboardContent("Retry DNS query")
        fixtureContext.openOrCreateDatabase("taild-dns.sqlite", 0, null).use {
          it.execSQL("ALTER TABLE dns_unavailable_fixture RENAME TO dns")
        }
        dashboardContent("Retry DNS query").click()
        dashboard.state.first { !it.dnsLoading && it.dns?.total == 125L }
        // Off cancels an actual pending read and fences later persistence.
        model.state.first { !it.busyHistory }
        phase("hold-history")
        model.refreshHistory(full = true)
        phase("history-waiting")
        app.tailDHistory.setEnabled(false)
        app.tailDHistory.awaitIdle()
        model.state.first { !it.busyHistory }
        phase("release-history")
        val before = model.store.recent(model.state.value.binding!!).summaries
        model.refreshHistory()
        model.state.first { !it.busyHistory && it.transient != null }
        assertEquals(before, model.store.recent(model.state.value.binding!!).summaries)
        phase("assert-read-only-dashboard")
      } catch (error: Throwable) {
        instrumentation.sendStatus(
            0,
            android.os.Bundle().apply { putString("taild_failure", error.stackTraceToString()) },
        )
        throw error
      } finally {
        app.setDashboardForEmulatorTest(null)
        localJob?.cancelAndJoin()
        close()
        model.vault.remove(ControlDCredentials.Access.READ)
        model.vault.remove(ControlDCredentials.Access.WRITE)
      }
    }
  }
}
