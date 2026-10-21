package com.tailscale.ipn.taild

import android.content.ComponentCallbacks
import android.content.Intent
import android.content.res.Configuration
import android.net.LocalServerSocket
import android.os.Build
import android.os.Bundle
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.*
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.tailscale.ipn.App
import com.tailscale.ipn.IntegrationLoginWorker
import com.tailscale.ipn.MainActivity
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.notifier.Notifier
import java.time.Instant
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test

/** Real fixture app -> Android TUN -> owner lookup -> private history -> native view. */
class TailDTrafficNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun realUidDnsBytesAndNativeSnapshot() = runBlocking {
    val instrumentation = InstrumentationRegistry.getInstrumentation()
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(InstrumentationRegistry.getArguments().getString("taild_fixture") == "true")
    val context = instrumentation.targetContext
    val app = App.get()
    suspend fun phase(name: String) {
      LocalServerSocket("taild-r37-native").use { server ->
        instrumentation.sendStatus(0, Bundle().apply { putString("taild_phase", name) })
        val result =
            withContext(Dispatchers.IO) {
              server.accept().use {
                val value = it.inputStream.read()
                it.outputStream.write(value)
                it.outputStream.flush()
                value
              }
            }
        assertEquals("Host accepted $name", 1, result)
      }
    }
    val work = WorkManager.getInstance(context)
    val prior =
        withContext(Dispatchers.IO) {
          work
              .getWorkInfosForUniqueWork(IntegrationLoginWorker.WORK_NAME)
              .get()
              .map { it.id }
              .toSet()
        }
    phase("login-ready")
    val login =
        work
            .getWorkInfosForUniqueWorkFlow(IntegrationLoginWorker.WORK_NAME)
            .first { it.any { item -> item.id !in prior && item.state.isFinished } }
            .first { it.id !in prior && it.state.isFinished }
    assertEquals(WorkInfo.State.SUCCEEDED, login.state)
    Notifier.state.first { it == Ipn.State.Running }
    app.getAppScopedViewModel().vpnActive.first { it }
    val history = app.tailDHistory
    history.setEnabled(true)
    history.awaitIdle()
    history.deleteHistory()
    history.awaitIdle()
    val from = System.currentTimeMillis()
    val uid =
        context.packageManager.getApplicationInfo("io.github.darkaxt.taild.fixture.one", 0).uid
    var observed: TrafficSnapshot? = null
    suspend fun awaitRows(predicate: (TrafficSnapshot) -> Boolean): TrafficSnapshot {
      combine(history.trafficRevision, history.trafficError) { revision, error ->
            revision to error
          }
          .first { (_, error) ->
            check(error == null) { error.orEmpty() }
            val data = history.queryTraffic(from, System.currentTimeMillis() + 1)
            if (predicate(data)) {
              observed = data
              true
            } else false
          }
      return checkNotNull(observed)
    }
    try {
      phase("traffic-start")
      val upload = awaitRows { data ->
        data.rows
            .filter { it.upload && it.fact.optInt("remotePort") == 18080 }
            .sumOf { it.bytes } >= 8192
      }
      assertTrue(
          upload.rows
              .filter { it.uid == uid && it.upload && it.fact.optInt("remotePort") == 18080 }
              .sumOf { it.bytes } >= 8192
      )
      assertTrue(
          upload.rows.any {
            it.fact.optJSONObject("dns")?.let { dns ->
              dns.optBoolean("blocked") &&
                  dns.optInt("queryUid") == uid &&
                  dns.getJSONObject("queryIdentity").getJSONArray("packages").length() == 2
            } == true
          }
      )
      assertTrue(upload.rows.any { it.fact.optJSONObject("dns")?.optBoolean("matched") == true })
      assertTrue(
          upload.rows
              .filter { it.uid == uid }
              .any { it.identity.contains("One") && it.identity.contains("Two") }
      )
      phase("traffic-release")
      val snapshot = awaitRows { data ->
        data.rows
            .filter { it.uid == uid && !it.upload && it.fact.optInt("remotePort") != 53 }
            .sumOf { it.bytes } >= 32768
      }
      assertTrue(snapshot.sent >= 8192)
      assertTrue(snapshot.received >= 32768)
      val exported = org.json.JSONObject(snapshot.export())
      assertEquals(snapshot.revision, exported.getLong("revision"))
      val facts = exported.getJSONArray("facts")
      assertEquals(
          snapshot.sent + snapshot.received,
          (0 until facts.length()).sumOf { facts.getJSONObject(it).getLong("measuredBytes") },
      )
      assertTrue(
          (0 until facts.length()).any {
            facts.getJSONObject(it).getJSONArray("equalWeightEstimates").length() == 2
          }
      )
      val weighted = snapshot.rows.filter { it.uid == uid && it.fact.optInt("remotePort") != 53 }
      assertTrue(weighted.isNotEmpty())
      assertTrue(weighted.all { (it.fact.optJSONArray("candidates")?.length() ?: 0) == 2 })
      phase("traffic-finish")
      phase("usage-accounting")
      val os =
          withContext(Dispatchers.IO) {
            readAppUsage(
                context,
                System.currentTimeMillis() - TailDHistory.RETENTION_MILLIS,
                System.currentTimeMillis() + 1,
            )
          }
      assertTrue(
          "Public OS UID accounting available: ${os.coverage}",
          os.rows.any { it.uid == uid && it.received + it.sent > 0 },
      )
      instrumentation.sendStatus(
          0,
          Bundle().apply {
            putString(
                "taild_accounting",
                os.rows.joinToString { "${it.uid}:${it.sent}:${it.received}" },
            )
          },
      )
      phase("usage-revoke")
      assertTrue(
          withContext(Dispatchers.IO) {
                readAppUsage(
                    context,
                    System.currentTimeMillis() - TailDHistory.RETENTION_MILLIS,
                    System.currentTimeMillis() + 1,
                )
              }
              .coverage
              .contains("not granted")
      )
      context.getSharedPreferences("introScreen", 0).edit().putBoolean("seen", true).commit()
      context.startActivity(
          Intent(context, MainActivity::class.java)
              .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
      )
      val device = UiDevice.getInstance(instrumentation)
      fun node(selector: BySelector): UiObject2 {
        // The Compose test clock must settle each action before native lookup.
        compose.waitForIdle()
        if (Build.VERSION.SDK_INT >= 33) instrumentation.uiAutomation.clearCache()
        return device.wait(Until.findObject(By.copy(selector).pkg(context.packageName)), 30000)
            ?: run {
              val tree = java.io.ByteArrayOutputStream()
              device.dumpWindowHierarchy(tree)
              instrumentation.sendStatus(
                  0,
                  Bundle().apply { putString("taild_missing_tree", tree.toString("UTF-8")) },
              )
              throw AssertionError("Missing traffic UI $selector")
            }
      }
      node(By.text("Dashboard")).click()
      node(By.text("Applications")).click()
      node(By.res("taild-traffic-app-$uid"))
      compose.onNodeWithTag("taild-traffic-search").performTextInput("absent-domain.invalid")
      compose.onNodeWithTag("taild-traffic-app-$uid").assertDoesNotExist()
      compose.onNodeWithTag("taild-traffic-search").performTextClearance()
      compose.onNodeWithTag("taild-traffic-search").performTextInput("alpha.taild.test")
      compose.onNodeWithTag("taild-traffic-app-$uid").assertIsDisplayed()
      compose.onNodeWithTag("taild-traffic-search").performTextClearance()
      compose.onNodeWithTag("taild-traffic-search").performImeAction()
      phase("capture-traffic-apps")
      node(By.res("taild-traffic-app-$uid")).click()
      node(By.text("Cross-check Control D history for this period"))
      phase("capture-traffic-details")
      // The same native SAF launcher must deliver the frozen selected snapshot.
      node(By.desc("Export selected snapshot")).click()
      val picker =
          context.packageManager
              .resolveActivity(
                  Intent(Intent.ACTION_CREATE_DOCUMENT)
                      .setType("application/json")
                      .addCategory(Intent.CATEGORY_OPENABLE),
                  0,
              )!!
              .activityInfo
              .packageName
      fun documentNode(selector: BySelector): UiObject2 =
          device.wait(
              object : Condition<UiDevice, UiObject2?> {
                override fun apply(device: UiDevice): UiObject2? {
                  if (android.os.Build.VERSION.SDK_INT >= 33)
                      instrumentation.uiAutomation.clearCache()
                  return device.findObject(By.copy(selector).pkg(picker))
                }
              },
              30000,
          ) ?: error("Document picker missing $selector")
      documentNode(By.desc("Show roots")).click()
      device.waitForIdle()
      val downloads = device.findObject(UiSelector().packageName(picker).text("Downloads"))
      assertTrue(downloads.waitForExists(30000))
      assertTrue(downloads.click())
      device.waitForIdle()
      documentNode(By.clazz("android.widget.EditText")).text =
          "TailD-traffic-native-${System.currentTimeMillis()}.json"
      device.waitForIdle()
      documentNode(
              By.text(
                  java.util.regex.Pattern.compile("save", java.util.regex.Pattern.CASE_INSENSITIVE)
              )
          )
          .click()
      assertTrue(
          "Save closes the actual document picker",
          device.wait(Until.gone(By.pkg(picker)), 30000),
      )
      app.tailDDashboard.state.first {
        !it.exportPending && !it.exportWriting && it.exportNotice != null
      }
      val uri = checkNotNull(app.tailDDashboard.exportedDocumentForTest)
      val delivered =
          org.json.JSONObject(
              context.contentResolver.openInputStream(uri)!!.bufferedReader().use { it.readText() }
          )
      assertEquals("TailD-Android-traffic-v1", delivered.getString("format"))
      assertTrue(delivered.getJSONArray("facts").length() > 0)
      instrumentation.sendStatus(
          0,
          Bundle().apply { putString("taild_document_uri", uri.toString()) },
      )
      phase("document-exported")
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
        node(By.text("Applications"))
        phase("capture-traffic-dark")
      } finally {
        context.unregisterComponentCallbacks(callback)
      }
      val beforeNetwork =
          history.queryTraffic(from, System.currentTimeMillis() + 1).rows.maxOfOrNull {
            it.fact.optLong("networkGeneration")
          } ?: 0
      phase("network-mobile")
      val mobile = awaitRows { data ->
        data.rows.any {
          it.fact.optString("observation") == "network-change" &&
              it.fact.optString("networkName") == "eth0" &&
              it.fact.optLong("networkGeneration") > beforeNetwork
        }
      }
      val mobileGeneration =
          mobile.rows
              .filter { it.fact.optString("networkName") == "eth0" }
              .maxOf { it.fact.optLong("networkGeneration") }
      phase("network-probe")
      awaitRows { data ->
        data.rows.any {
          it.fact.optLong("networkGeneration") >= mobileGeneration &&
              it.upload &&
              it.fact.optInt("remotePort") == 18080 &&
              it.bytes > 1000
        }
      }
      phase("network-restore")
      awaitRows { data ->
        data.rows.any {
          it.fact.optString("observation") == "network-change" &&
              it.fact.optString("networkName") == "wlan0" &&
              it.fact.optLong("networkGeneration") > mobileGeneration
        }
      }
      val cm = context.getSystemService(android.net.ConnectivityManager::class.java)
      val vpn =
          cm.allNetworks.single {
            cm.getNetworkCapabilities(it)
                ?.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN) == true
          }
      assertFalse(
          cm.getLinkProperties(vpn)!!.routes.any {
            it.matches(java.net.InetAddress.getByName("10.0.2.2"))
          }
      )
      phase("direct-route")
      history.awaitIdle()
      assertFalse(
          history.queryTraffic(from, System.currentTimeMillis() + 1).rows.any {
            it.fact.optString("remote") == "10.0.2.2"
          }
      )
      phase("layout-phone-large")
      compose.waitUntil(30_000) { context.resources.configuration.fontScale == 1.5f }
      compose
          .onNodeWithTag("taild-traffic-content")
          .performScrollToNode(hasTestTag("taild-traffic-app-$uid"))
      compose.onNodeWithTag("taild-traffic-app-$uid").assertIsDisplayed()
      compose.onNodeWithTag("taild-traffic-content").performScrollToIndex(0)
      phase("capture-traffic-large")
      phase("layout-tablet")
      compose.waitUntil(30_000) {
        context.resources.configuration.screenWidthDp >= 600 &&
            context.resources.configuration.orientation == Configuration.ORIENTATION_PORTRAIT
      }
      compose.onNodeWithTag("taild-main-navigation-rail").assertIsDisplayed()
      compose
          .onNodeWithTag("taild-traffic-content")
          .performScrollToNode(hasTestTag("taild-traffic-app-$uid"))
      compose.onNodeWithTag("taild-traffic-app-$uid").assertIsDisplayed()
      compose.onNodeWithTag("taild-traffic-content").performScrollToIndex(0)
      phase("capture-traffic-tablet")
      phase("layout-landscape")
      compose.waitUntil(30_000) {
        context.resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
      }
      compose.onNodeWithTag("taild-main-navigation-rail").assertIsDisplayed()
      compose
          .onNodeWithTag("taild-traffic-content")
          .performScrollToNode(hasTestTag("taild-traffic-app-$uid"))
      compose.onNodeWithTag("taild-traffic-app-$uid").assertIsDisplayed()
      compose.onNodeWithTag("taild-traffic-content").performScrollToIndex(0)
      phase("capture-traffic-landscape")
      phase("layout-phone")
      compose.waitUntil(30_000) {
        context.resources.configuration.screenWidthDp < 600 &&
            context.resources.configuration.fontScale == 1f
      }
      val oldRows = snapshot.rows.map { it.metadata }
      phase("traffic-reinstall")
      assertTrue(
          history
              .queryTraffic(from, System.currentTimeMillis() + 1)
              .rows
              .map { it.metadata }
              .toSet()
              .containsAll(oldRows)
      )

      // Turning collection off preserves the exact frozen result, independently of Firewall.
      history.setEnabled(false)
      history.awaitIdle()
      assertFalse(history.enabled.value)
      val retained = history.queryTraffic(from, Instant.now().toEpochMilli() + 1)
      assertTrue(retained.sent >= snapshot.sent)
      context
          .getSharedPreferences("taild.traffic.native-fixture", 0)
          .edit()
          .putLong("from", retained.from)
          .putLong("until", retained.until)
          .putInt("uid", uid)
          .putLong("processStart", android.os.Process.getStartElapsedRealtime())
          .putString("hash", trafficFixtureHash(retained.export()))
          .commit()
      phase("retained-for-restart")
      assertEquals(Ipn.State.Running, Notifier.state.value)
    } finally {
      phase("traffic-close")
    }
  }
}

private fun trafficFixtureHash(value: String) =
    java.security.MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { "%02x".format(it) }

class TailDTrafficRestartNativeTest {
  @Test
  fun reopenRetainedTrafficWithoutOptingInAndDeleteFromPreferences() = runBlocking {
    val instrumentation = InstrumentationRegistry.getInstrumentation()
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(InstrumentationRegistry.getArguments().getString("taild_fixture") == "true")
    val context = instrumentation.targetContext
    val app = App.get()
    val history = app.tailDHistory
    val receipt = context.getSharedPreferences("taild.traffic.native-fixture", 0)
    assertTrue(receipt.contains("hash"))
    assertNotEquals(
        receipt.getLong("processStart", -1),
        android.os.Process.getStartElapsedRealtime(),
    )
    assertFalse(history.enabled.value)
    val reopened = history.queryTraffic(receipt.getLong("from", -1), receipt.getLong("until", -1))
    assertEquals(receipt.getString("hash", null), trafficFixtureHash(reopened.export()))
    context.startActivity(
        Intent(context, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
    )
    val device = UiDevice.getInstance(instrumentation)
    fun node(selector: BySelector): UiObject2 =
        device.wait(Until.findObject(selector.pkg(context.packageName)), 30000)
            ?: error("Restart UI missing $selector")
    node(By.text("Dashboard")).click()
    node(By.text("Applications")).click()
    node(By.res("taild-traffic-app-${receipt.getInt("uid",-1)}"))
    node(By.text("Tailscale")).click()
    val strip = node(By.res("taild-tailscale-tabs"))
    val scroller = strip.findObject(By.scrollable(true))
    if (device.findObject(By.text("Preferences").pkg(context.packageName)) == null)
        checkNotNull(scroller)
            .scrollUntil(
                Direction.RIGHT,
                Until.findObject(By.text("Preferences").pkg(context.packageName)),
            )
    node(By.text("Preferences")).click()
    node(By.res("taild-preferences"))
        .scrollUntil(
            Direction.DOWN,
            Until.findObject(By.text("Delete local history").pkg(context.packageName)),
        )
    node(By.text("Delete local history")).click()
    node(
        By.text(
            "Remove local activity, DNS and traffic history from this app. Recording and VPN settings stay as configured. Control D cloud history is unchanged."
        )
    )
    node(By.res("taild-delete-history-confirm")).click()
    history.trafficDeletion.first { it > 0 }
    assertTrue(history.queryTraffic(reopened.from, System.currentTimeMillis() + 1).rows.isEmpty())
    assertFalse(history.enabled.value)
    node(By.text("Dashboard")).click()
    node(By.text("Applications")).click()
    node(By.text("No retained VPN packets in this period. This does not prove no traffic."))
    receipt.edit().clear().commit()
    LocalServerSocket("taild-r37-native").use { server ->
      instrumentation.sendStatus(
          0,
          Bundle().apply { putString("taild_phase", "capture-traffic-restarted-cleared") },
      )
      assertEquals(
          1,
          withContext(Dispatchers.IO) {
            server.accept().use {
              val value = it.inputStream.read()
              it.outputStream.write(value)
              it.outputStream.flush()
              value
            }
          },
      )
    }
  }
}
