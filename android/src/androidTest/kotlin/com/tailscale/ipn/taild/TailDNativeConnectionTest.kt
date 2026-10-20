package com.tailscale.ipn.taild

import android.content.ComponentCallbacks
import android.content.Intent
import android.content.res.Configuration
import android.net.LocalServerSocket
import android.os.Build
import android.os.Bundle
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.*
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.tailscale.ipn.App
import com.tailscale.ipn.IPNReceiver
import com.tailscale.ipn.IntegrationLoginWorker
import com.tailscale.ipn.MainActivity
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.notifier.Notifier
import com.tailscale.ipn.util.ShareFileHelper
import java.util.regex.Pattern
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Requires TestTailDNativeUI's isolated real control plane and native VPN. */
class TailDNativeConnectionTest {
  @Test
  fun liveDeviceControlPreferencesAndHistory() = runBlocking {
    val instrumentation = InstrumentationRegistry.getInstrumentation()
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(InstrumentationRegistry.getArguments().getString("taild_fixture") == "true")
    val context = instrumentation.targetContext
    val app = App.get()
    suspend fun phase(name: String) {
      // Test-only event handshake. The host captures or sends a real file, then
      // acknowledges; no sleep/poll/deadline keeps a screen artificially stable.
      LocalServerSocket("taild-r37-native").use { server ->
        instrumentation.sendStatus(0, Bundle().apply { putString("taild_phase", name) })
        val accepted =
            withContext(Dispatchers.IO) {
              server.accept().use {
                val value = it.inputStream.read()
                it.outputStream.write(value)
                it.outputStream.flush()
                value
              }
            }
        assertEquals("Host accepted $name", 1, accepted)
      }
    }
    val workManager = WorkManager.getInstance(context)
    val previousLoginWork =
        withContext(Dispatchers.IO) {
          workManager
              .getWorkInfosForUniqueWork(IntegrationLoginWorker.WORK_NAME)
              .get()
              .map { it.id }
              .toSet()
        }
    phase("login-ready")
    val completedLogin =
        workManager
            .getWorkInfosForUniqueWorkFlow(IntegrationLoginWorker.WORK_NAME)
            .first { work -> work.any { it.id !in previousLoginWork && it.state.isFinished } }
            .first { it.id !in previousLoginWork && it.state.isFinished }
    assertEquals("Fixture login completed", WorkInfo.State.SUCCEEDED, completedLogin.state)
    val fixturePeerKey = InstrumentationRegistry.getArguments().getString("fixture_peer_key")!!
    val map =
        Notifier.netmap.filterNotNull().first {
          it.Peers.orEmpty().any { peer ->
            peer.displayName == "taild-test-peer" && peer.Key == fixturePeerKey
          }
        }
    Notifier.state.first { it == Ipn.State.Running }
    app.getAppScopedViewModel().vpnActive.first { it }
    context.getSharedPreferences("introScreen", 0).edit().putBoolean("seen", true).commit()
    context.startActivity(
        Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    val device = UiDevice.getInstance(instrumentation)
    if (InstrumentationRegistry.getArguments().getString("landscape") == "true") {
      device.setOrientationLeft()
    } else {
      device.setOrientationNatural()
    }
    fun node(selector: BySelector): UiObject2 =
        device.wait(Until.findObject(selector.pkg(context.packageName)), 30_000)
            ?: throw AssertionError("Native UI missing $selector")
    val documentPackage =
        context.packageManager
            .resolveActivity(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), 0)!!
            .activityInfo
            .packageName
    fun documentNode(selector: BySelector): UiObject2 =
        device.wait(Until.findObject(selector.pkg(documentPackage)), 30_000)
            ?: throw AssertionError("Document UI missing $selector")
    fun tab(label: String) {
      val strip = node(By.res("taild-tailscale-tabs"))
      val scroller = strip.findObject(By.scrollable(true))
      if (device.findObject(By.text(label).pkg(context.packageName)) == null) {
        val order = listOf("Connection", "Activity", "TailDrop", "Admin console", "Preferences")
        val selected = strip.findObject(By.selected(true))
        val selectedLabel = order.firstOrNull {
          selected?.text == it || selected?.hasObject(By.text(it)) == true
        }
        checkNotNull(selectedLabel) { "Selected tab has no accessible label" }
        val direction =
            if (order.indexOf(label) < order.indexOf(selectedLabel)) Direction.LEFT
            else Direction.RIGHT
        checkNotNull(scroller) { "Tab strip has no scrollable child" }
            .scrollUntil(direction, Until.findObject(By.text(label).pkg(context.packageName)))
      }
      node(By.text(label)).click()
      instrumentation.waitForIdleSync()
    }
    fun preference(label: String, direction: Direction = Direction.DOWN) {
      if (device.findObject(By.text(label).pkg(context.packageName)) == null) {
        node(By.res("taild-preferences"))
            .scrollUntil(direction, Until.findObject(By.text(label).pkg(context.packageName)))
      }
      node(By.text(label))
    }
    try {
      if (InstrumentationRegistry.getArguments().getString("layout_only") == "true") {
        node(By.desc("Disconnect"))
        phase("capture-connection")
        tab("Preferences")
        preference("Collect analytics")
        node(By.desc("Collect analytics"))
        phase("capture-preferences")
        tab("Activity")
        node(By.text("Observed activity"))
        phase("capture-activity")
        tab("TailDrop")
        node(By.text("Send files"))
        phase("capture-taildrop")
        val expectedNight =
            if (
                context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK ==
                    Configuration.UI_MODE_NIGHT_YES
            )
                Configuration.UI_MODE_NIGHT_NO
            else Configuration.UI_MODE_NIGHT_YES
        val themeChanged = CompletableDeferred<Unit>()
        val configurationObserver =
            object : ComponentCallbacks {
              override fun onConfigurationChanged(configuration: Configuration) {
                if (configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == expectedNight)
                    themeChanged.complete(Unit)
              }

              override fun onLowMemory() {}
            }
        context.registerComponentCallbacks(configurationObserver)
        try {
          phase("switch-theme")
          themeChanged.await()
          instrumentation.waitForIdleSync()
          node(By.text("Send files"))
          assertTrue("Theme change preserves the VPN", app.getAppScopedViewModel().vpnActive.value)
          assertEquals(Ipn.State.Running, Notifier.state.value)
          phase("capture-theme-changed")
        } finally {
          context.unregisterComponentCallbacks(configurationObserver)
        }
        return@runBlocking
      }
      val self = node(By.text(map.SelfNode.displayName))
      val peer = node(By.text("taild-test-peer"))
      assertTrue("This device precedes the peer", self.visibleBounds.top < peer.visibleBounds.top)
      phase("capture-connection")
      node(By.desc("Search")).click()
      node(By.clazz("android.widget.EditText")).text = "taild-test-peer"
      node(By.text("taild-test-peer"))
      node(By.desc("Back")).click()
      node(By.text(map.SelfNode.displayName))
      node(By.text("taild-test-peer")).click()
      node(By.text("Allowed routes"))
      device.pressBack()
      node(By.text("taild-test-peer"))
      tab("Preferences")
      val switch = node(By.desc("Collect analytics"))
      if (!switch.isChecked) switch.click()
      app.tailDHistory.enabled.first { it }
      val scopeKey = activityScope(map, Notifier.prefs.value)!!
      app.tailDHistory.refresh(scopeKey)
      app.tailDHistory.rows.first { it.any { row -> row.event.kind == "baseline" } }
      if (InstrumentationRegistry.getArguments().getString("require_restart_gap") == "true") {
        app.tailDHistory.awaitIdle()
        assertTrue(
            "Process restart retains history and records the prior observation boundary",
            app.tailDHistory.rows.value.any {
              it.event.kind == "coverage" && it.event.detail.contains("Previous observation:")
            },
        )
      }
      assertNull(app.tailDHistory.error.value)
      phase("capture-preferences")
      preference("DNS settings")
      node(By.text("DNS settings")).click()
      node(By.desc("Go back to the previous screen")).click()
      preference("Collect analytics", Direction.UP)
      node(By.desc("Collect analytics"))
      tab("Activity")
      node(By.text("Observed activity"))
      phase("capture-activity")
      tab("Connection")
      node(By.desc("Disconnect")).click()
      app.getAppScopedViewModel().vpnActive.first { !it }
      node(By.desc("Connect")).click()
      Notifier.state.first { it == Ipn.State.Running }
      app.getAppScopedViewModel().vpnActive.first { it }
      node(By.text("taild-test-peer"))
      app.tailDHistory.refresh(scopeKey)
      app.tailDHistory.rows.first { it.any { row -> row.event.kind == "connection" } }
      assertNull(app.tailDHistory.error.value)
      val dnsBeforeBroadcast = Notifier.prefs.value?.CorpDNS
      context.sendBroadcast(
          Intent(IPNReceiver.INTENT_DISCONNECT_VPN).setClass(context, IPNReceiver::class.java)
      )
      app.getAppScopedViewModel().vpnActive.first { !it }
      context.sendBroadcast(
          Intent(IPNReceiver.INTENT_CONNECT_VPN).setClass(context, IPNReceiver::class.java)
      )
      Notifier.state.first { it == Ipn.State.Running }
      app.getAppScopedViewModel().vpnActive.first { it }
      assertEquals(
          "External VPN actions preserve DNS ownership",
          dnsBeforeBroadcast,
          Notifier.prefs.value?.CorpDNS,
      )
      if (!ShareFileHelper.hasValidTaildropDir()) {
        instrumentation.runOnMainSync {
          app.getAppScopedViewModel().directoryPickerLauncher!!.launch(null)
        }
        documentNode(By.text(Pattern.compile("create new folder", Pattern.CASE_INSENSITIVE)))
            .click()
        documentNode(By.clazz("android.widget.EditText")).text = "TailDTest"
        documentNode(By.text("OK")).click()
        documentNode(By.text(Pattern.compile("use this folder", Pattern.CASE_INSENSITIVE))).click()
        documentNode(By.text(Pattern.compile("allow", Pattern.CASE_INSENSITIVE))).click()
      }
      tab("TailDrop")
      val previousSaves = app.tailDHistory.rows.value.count { it.event.kind == "taildrop.saved" }
      phase("receive-ready")
      app.tailDHistory.rows.first { rows ->
        rows.count { it.event.kind == "taildrop.saved" } > previousSaves
      }
      assertTrue(
          app.tailDHistory.rows.value.none { it.toString().contains("taild-a1-private-payload") }
      )
      phase("capture-taildrop")
      instrumentation.waitForIdleSync()
    } catch (problem: Throwable) {
      instrumentation.sendStatus(
          0,
          Bundle().apply {
            putString(
                "taild_diagnostic",
                "state=${Notifier.state.value}, self=${Notifier.netmap.value?.SelfNode?.displayName}",
            )
          },
      )
      phase("capture-failure")
      throw problem
    }
  }
}
