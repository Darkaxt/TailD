package com.tailscale.ipn.taild

import android.content.ComponentCallbacks
import android.content.Intent
import android.content.res.Configuration
import android.net.LocalServerSocket
import android.os.Build
import android.os.Bundle
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.*
import com.tailscale.ipn.App
import com.tailscale.ipn.MainActivity
import java.net.URI
import java.security.KeyStore
import java.security.MessageDigest
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Synthetic credentials and pinned HTTPS only, on the host-owned emulator. */
internal class NativeControlDSession(reset: Boolean) {
  val instrumentation = InstrumentationRegistry.getInstrumentation()
  val context = instrumentation.targetContext
  val app = App.get()
  val fixtureContext = context.createDeviceProtectedStorageContext()
  val job = SupervisorJob()
  val scope = CoroutineScope(job + Dispatchers.Default)
  val device = UiDevice.getInstance(instrumentation)
  val model: ControlDModel

  init {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    val arguments = InstrumentationRegistry.getArguments()
    assumeTrue(arguments.getString("taild_fixture") == "true")
    val uri = URI(arguments.getString("fixture_url")!!)
    check(uri.scheme == "https" && uri.host == "127.0.0.1" && uri.port > 0)
    val pin = arguments.getString("fixture_cert")!!
    check(pin.matches(Regex("[0-9a-f]{64}")))
    val trust =
        object : X509TrustManager {
          override fun getAcceptedIssuers() = emptyArray<X509Certificate>()

          override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) =
              error("No client TLS")

          override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
            check(chain.size == 1)
            val actual =
                MessageDigest.getInstance("SHA-256").digest(chain[0].encoded).joinToString("") {
                  "%02x".format(it)
                }
            check(actual == pin) { "Fixture TLS identity changed" }
          }
        }
    val tls = SSLContext.getInstance("TLS").apply { init(null, arrayOf(trust), null) }
    val client =
        okhttp3.OkHttpClient.Builder()
            .sslSocketFactory(tls.socketFactory, trust)
            .hostnameVerifier { host, _ -> host == "127.0.0.1" }
            .addInterceptor { chain ->
              val request = chain.request()
              val url = request.url.newBuilder().host("127.0.0.1").port(uri.port).build()
              chain.proceed(request.newBuilder().url(url).build())
            }
            .build()
    if (reset) {
      fixtureContext.deleteDatabase("taild-dns.sqlite")
      fixtureContext.getSharedPreferences("taild.controld.settings", 0).edit().clear().commit()
      ControlDCredentials(fixtureContext).apply {
        remove(ControlDCredentials.Access.READ)
        remove(ControlDCredentials.Access.WRITE)
      }
    }
    model = ControlDModel(fixtureContext, scope, app.tailDHistory, ControlDApi(client))
    app.setControlDForEmulatorTest(model)
  }

  private fun freshFind(selector: BySelector): UiObject2? {
    if (Build.VERSION.SDK_INT >= 33) instrumentation.uiAutomation.clearCache()
    return device.findObject(By.copy(selector).pkg(context.packageName))
  }

  fun node(selector: BySelector): UiObject2 =
      device.wait(
          object : Condition<UiDevice, UiObject2?> {
            override fun apply(device: UiDevice): UiObject2? = freshFind(selector)
          },
          30_000,
      ) ?: throw AssertionError("Native Control D node missing: $selector")

  fun click(selector: BySelector) {
    node(selector).click()
    instrumentation.waitForIdleSync()
  }

  suspend fun scrollTo(tag: String, selector: BySelector, horizontal: Boolean = false): UiObject2 {
    val selected = By.copy(selector).pkg(context.packageName)
    instrumentation.waitForIdleSync()
    device.waitForIdle()
    fun tagged(
        node: android.view.accessibility.AccessibilityNodeInfo
    ): android.view.accessibility.AccessibilityNodeInfo? {
      if (node.viewIdResourceName == tag) return node
      for (i in 0 until node.childCount) node.getChild(i)?.let {
        tagged(it)?.let {
          return it
        }
      }
      return null
    }
    fun viewport(): String {
      if (Build.VERSION.SDK_INT >= 33) instrumentation.uiAutomation.clearCache()
      val root =
          tagged(checkNotNull(instrumentation.uiAutomation.rootInActiveWindow))
              ?: error("Rendered scroll region missing: $tag")
      val out = StringBuilder()
      fun visit(node: android.view.accessibility.AccessibilityNodeInfo) {
        if (!node.isVisibleToUser) return
        val bounds = android.graphics.Rect().also(node::getBoundsInScreen)
        out.append(node.text)
            .append('|')
            .append(node.contentDescription)
            .append('|')
            .append(bounds.flattenToString())
            .append('\n')
        for (i in 0 until node.childCount) node.getChild(i)?.let(::visit)
      }
      visit(root)
      return out.toString()
    }
    val directions =
        if (horizontal) listOf(Direction.LEFT, Direction.RIGHT)
        else listOf(Direction.UP, Direction.DOWN)
    for (direction in directions) {
      while (freshFind(selector) == null) {
        val before = viewport()
        val root = node(By.res(tag))
        val scroll =
            if (root.isScrollable) root
            else root.findObject(By.scrollable(true)) ?: error("No scrollable child in $tag")
        // A physical swipe plus fresh measured viewport determines progress.
        // UiAutomator's scroll boolean/events falsely reported a middle item as the end.
        val gesture =
            when (direction) {
              Direction.UP -> Direction.DOWN
              Direction.DOWN -> Direction.UP
              Direction.LEFT -> Direction.RIGHT
              Direction.RIGHT -> Direction.LEFT
            }
        scroll.swipe(gesture, 0.75f)
        device.waitForIdle()
        if (viewport() == before) break
      }
    }
    try {
      return node(selector)
    } catch (missing: AssertionError) {
      val tree = java.io.ByteArrayOutputStream()
      device.dumpWindowHierarchy(tree)
      instrumentation.sendStatus(
          0,
          Bundle().apply {
            putString("taild_missing_content", selector.toString())
            putString("taild_missing_tree", tree.toString("UTF-8"))
          },
      )
      phase("capture-missing-content")
      throw missing
    }
  }

  suspend fun content(text: String, description: Boolean = false): UiObject2 {
    val selector = if (description) By.desc(text) else By.text(text)
    return scrollTo("taild-control-d-content", selector)
  }

  suspend fun ready(predicate: (ControlDState) -> Boolean): ControlDState =
      model.state
          .first {
            predicate(it) ||
                ((!it.busySetup && !it.busyPolicy && !it.busyHistory && !it.busyWrite) &&
                    (it.error != null || it.historyError != null))
          }
          .also {
            check(predicate(it)) {
              "Native Control D readiness failed: ${it.error ?: it.historyError}"
            }
          }

  suspend fun phase(name: String) {
    LocalServerSocket("taild-r37-native").use { server ->
      instrumentation.sendStatus(0, Bundle().apply { putString("taild_phase", name) })
      val ack =
          withContext(Dispatchers.IO) {
            server.accept().use { socket ->
              val value = socket.inputStream.read()
              socket.outputStream.write(value)
              socket.outputStream.flush()
              value
            }
          }
      assertEquals("Host accepted $name", 1, ack)
    }
  }

  suspend fun launch() {
    app.stopVPN()
    app.getAppScopedViewModel().vpnActive.first { !it }
    app.tailDHistory.setEnabled(true)
    app.tailDHistory.awaitIdle()
    context.getSharedPreferences("introScreen", 0).edit().putBoolean("seen", true).commit()
    if (InstrumentationRegistry.getArguments().getString("landscape") == "true")
        device.setOrientationLeft()
    else device.setOrientationNatural()
    context.startActivity(
        Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    click(By.text("Control D"))
  }

  suspend fun reviewedToggle(label: String) {
    content(label, description = true).click()
    ready { !it.busyWrite && (it.preview != null || it.error != null) }
    assertNull(model.state.value.error)
    click(By.text("Apply"))
    ready { !it.busyWrite }
    assertNull(model.state.value.error)
    assertFalse(model.state.value.unresolved)
  }

  suspend fun applyEditor() {
    click(By.text("Review change"))
    ready { !it.busyWrite && (it.preview != null || it.error != null) }
    assertNull(model.state.value.error)
    click(By.text("Apply reviewed change"))
    ready { !it.busyWrite }
    assertNull(model.state.value.error)
    assertFalse(model.state.value.unresolved)
    assertTrue(
        device.wait(Until.gone(By.text("Apply reviewed change").pkg(context.packageName)), 30_000)
    )
    click(By.text("Close"))
    assertTrue(
        "The full editor has closed",
        device.wait(Until.gone(By.text("Edit custom rule").pkg(context.packageName)), 30_000),
    )
  }

  fun rule(host: String) = model.state.value.policy!!.rows("rules").find { it.text("PK") == host }

  suspend fun close() {
    job.cancelAndJoin()
    app.setControlDForEmulatorTest(null)
  }
}

class TailDControlDInitialTest {
  @Test
  fun nativeSetupHistoryPolicyAndUnknownOutcome() = runBlocking {
    val fixture = NativeControlDSession(reset = true)
    with(fixture) {
      try {
        launch()
        click(By.text("Set up Control D"))
        node(By.res("taild-api-token")).text = "read-fixture"
        click(By.text("Verify and save"))
        ready { it.hasRead && !it.busySetup }
        click(By.text("Close"))
        click(By.text("No endpoint selected"))
        click(By.text("Emulator endpoint"))
        ready { it.policy != null && !it.busyPolicy && !it.busyHistory }
        click(By.text("All clients"))
        click(By.text("This emulator"))
        ready {
          it.binding?.client == "phone" &&
              it.policy != null &&
              it.page.lastRead != null &&
              !it.busyHistory &&
              !it.busyPolicy
        }
        assertEquals(124L, model.state.value.page.summaries["blocked.invalid" to "A"]?.total)
        assertEquals(100, model.state.value.page.rows.size)
        assertFalse(
            model.state.value.page.summaries.keys.any { it.first == "other-client.invalid" }
        )
        val firstSeen =
            model.state.value.page.summaries.getValue("blocked.invalid" to "A").firstSeen
        assertTrue(firstSeen < java.time.Instant.now().minusSeconds(2 * 86400))
        model.refreshHistory()
        ready { !it.busyHistory }
        assertEquals(
            124L,
            model.store
                .recent(model.state.value.binding!!)
                .summaries
                .getValue("blocked.invalid" to "A")
                .total,
        )
        model.search("Blocked")
        ready { it.page.query == "Blocked" }
        assertEquals(100, model.state.value.page.rows.size)
        assertTrue(model.state.value.page.rows.all { it.fact.action == 0 })
        phase("capture-recent")
        content("Add separate Write access").click()
        node(By.res("taild-api-token")).text = "write-fixture"
        click(By.text("Verify and save"))
        ready { it.hasWrite && !it.busySetup }
        click(By.text("Close"))
        model.search("")
        ready { it.page.query == "" }
        content("Edit rule for allowed.invalid", description = true).click()
        node(By.desc("Block rule action"))
        assertFalse(
            "An allowed observation without a custom rule only offers Block",
            device.hasObject(By.desc("Allow with Bypass rule action").pkg(context.packageName)),
        )
        click(By.text("Close"))
        assertTrue(
            device.wait(Until.gone(By.text("Edit custom rule").pkg(context.packageName)), 30_000)
        )
        model.search("Blocked")
        ready { it.page.query == "Blocked" }
        // Freeze an older reload after its rules were read. The direct action
        // must own the policy shown after its fresh post-write readback.
        phase("hold-old-policy")
        click(By.desc("Reload policy"))
        phase("policy-waiting")
        content("Allow blocked.invalid with Bypass", description = true).click()
        ready { !it.busyWrite && rule("blocked.invalid")?.objectAt("action")?.number("do") == 1 }
        phase("release-policy")
        ready { !it.busyPolicy }
        assertEquals(1, rule("blocked.invalid")?.objectAt("action")?.number("do"))
        assertNull(model.state.value.error)
        assertNull(model.state.value.preview)
        assertEquals(7, rule("blocked.invalid")?.number("group"))
        content("Edit rule for blocked.invalid", description = true).click()
        phase("hold-policy")
        click(By.text("Review change"))
        phase("policy-waiting")
        assertTrue(model.state.value.busyWrite)
        click(By.text("Close"))
        phase("release-policy")
        ready { !it.busyWrite }
        assertNull(
            "Closing an in-flight review must invalidate its eventual preview",
            model.state.value.preview,
        )
        content("Edit rule for blocked.invalid", description = true).click()
        scrollTo("taild-rule-editor-content", By.res("taild-rule-comment")).click()
        val ime =
            android.provider.Settings.Secure.getString(
                    context.contentResolver,
                    android.provider.Settings.Secure.DEFAULT_INPUT_METHOD,
                )
                .substringBefore('/')
        assertTrue(
            "The real software keyboard is visible",
            device.wait(Until.hasObject(By.pkg(ime)), 30_000),
        )
        node(By.res("taild-rule-comment")).text = "Reviewed in Android"
        phase("capture-editor-keyboard")
        device.pressBack()
        assertTrue(device.wait(Until.gone(By.pkg(ime)), 30_000))
        scrollTo("taild-rule-editor-content", By.desc("Block rule action")).click()
        node(By.desc("Allow with Bypass rule action"))
        assertFalse(
            "Only the inverse rule action is offered",
            device.hasObject(By.desc("Block rule action").pkg(context.packageName)),
        )
        val night =
            if (
                context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK ==
                    Configuration.UI_MODE_NIGHT_YES
            )
                Configuration.UI_MODE_NIGHT_NO
            else Configuration.UI_MODE_NIGHT_YES
        val changed = CompletableDeferred<Unit>()
        val callback =
            object : ComponentCallbacks {
              override fun onConfigurationChanged(configuration: Configuration) {
                if (configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == night)
                    changed.complete(Unit)
              }

              override fun onLowMemory() {}
            }
        context.registerComponentCallbacks(callback)
        try {
          phase("switch-theme")
          changed.await()
          assertEquals("Reviewed in Android", node(By.res("taild-rule-comment")).text)
          phase("capture-editor")
        } finally {
          context.unregisterComponentCallbacks(callback)
        }
        click(By.text("Review change"))
        ready { !it.busyWrite && it.preview != null }
        click(By.text("Apply reviewed change"))
        ready { !it.busyWrite && rule("blocked.invalid")?.objectAt("action")?.number("do") == 0 }
        assertNull(model.state.value.error)
        assertEquals(7, rule("blocked.invalid")?.number("group"))
        click(By.text("Close"))
        click(By.text("Profile policy"))
        content("Create custom rule").click()
        node(By.res("taild-rule-hostname")).text = "new.invalid"
        node(By.res("taild-rule-comment")).text = "New rule"
        applyEditor()
        assertNotNull(rule("new.invalid"))
        content("Edit new.invalid", description = true).click()
        click(By.desc("Rule enabled"))
        applyEditor()
        assertEquals(0, rule("new.invalid")?.objectAt("action")?.number("status"))
        content("Edit new.invalid", description = true).click()
        scrollTo("taild-rule-editor-content", By.text("Review deletion")).click()
        ready { !it.busyWrite && it.preview != null }
        click(By.text("Apply reviewed change"))
        ready { !it.busyWrite }
        assertNull(model.state.value.error)
        click(By.text("Close"))
        assertNull(rule("new.invalid"))
        reviewedToggle("Fixture filter")
        reviewedToggle("Fixture service")
        reviewedToggle("Block private answers")
        assertEquals(2, rule("unsupported.invalid")?.objectAt("action")?.number("do"))
        model.configureWrite("other-write")
        ready { !it.busySetup && it.error != null }
        assertEquals("write-fixture", model.vault.read(ControlDCredentials.Access.WRITE))
        model.refreshPolicy()
        ready { !it.busyPolicy && it.error == null }
        model.prepare(ControlDChange.Rule("blocked.invalid", 1, true, "stale"))
        ready { !it.busyWrite && it.preview != null }
        val stale = model.state.value.preview!!.ticket
        phase("stale-policy")
        click(By.text("Apply"))
        ready { !it.busyWrite && it.error != null }
        assertFalse(model.state.value.unresolved)
        model.applyPreview(stale)
        ready { !it.busyWrite && it.error != null }
        model.refreshPolicy()
        ready { !it.busyPolicy && it.error == null }
        click(By.text("Recent DNS"))
        phase("drop-next-write")
        content("Allow blocked.invalid with Bypass", description = true).click()
        ready { !it.busyWrite && it.unresolved && it.error != null }
        val journal =
            fixtureContext
                .getSharedPreferences("taild.controld.settings", 0)
                .getString("pending-change", null)!!
        assertFalse(journal.contains("write-fixture") || journal.contains("read-fixture"))
        phase("assert-after-unknown")
        phase("capture-unknown")
        assertFalse(app.getAppScopedViewModel().vpnActive.value)
      } finally {
        close()
      }
    }
  }
}

class TailDControlDRestartTest {
  @Test
  fun processRestartReconcilesWithoutRepeatingWrite() = runBlocking {
    val fixture = NativeControlDSession(reset = false)
    with(fixture) {
      try {
        assertTrue(model.state.value.unresolved)
        assertEquals("phone", model.state.value.binding?.client)
        assertEquals("read-fixture", model.vault.read(ControlDCredentials.Access.READ))
        assertEquals("write-fixture", model.vault.read(ControlDCredentials.Access.WRITE))
        launch()
        ready { it.policy != null && !it.busyHistory && !it.busyPolicy && !it.busySetup }
        assertTrue(model.state.value.unresolved)
        phase("assert-after-restart")
        phase("capture-recent")
        content("Reconcile current policy").click()
        ready { !it.busyWrite && !it.unresolved }
        assertNull(model.state.value.error)
        assertEquals(1, rule("blocked.invalid")?.objectAt("action")?.number("do"))
        phase("assert-after-reconcile")
        phase("capture-reconciled")
        // Off stops retention; a deliberate read remains transient, and changing
        // scope never mixes the prior client's counts with another client.
        val retained = model.store.recent(model.state.value.binding!!)
        app.tailDHistory.setEnabled(false)
        app.tailDHistory.awaitIdle()
        model.state.first { !it.busyHistory && it.historyError != null }
        model.refreshHistory()
        ready { !it.busyHistory && it.transient != null }
        assertEquals(retained.summaries, model.store.recent(model.state.value.binding!!).summaries)
        model.select(
            model.state.value.inventory!!.endpoints.first(),
            ControlDClient("other", "Other client"),
        )
        ready { !it.busyHistory && it.transient != null }
        assertEquals(1, model.state.value.transient!!.size)
        assertTrue(model.store.recent(model.state.value.binding!!).summaries.isEmpty())
        // Actual Android Keystore key loss is explicit and does not delete history.
        KeyStore.getInstance("AndroidKeyStore").apply {
          load(null)
          deleteEntry("taild.controld.read")
        }
        val failure = runCatching {
          model.vault.read(ControlDCredentials.Access.READ)
        }
            .exceptionOrNull()
        assertTrue(failure is ControlDFailure)
        assertTrue(failure!!.message!!.contains("Re-enter"))
        assertEquals("write-fixture", model.vault.read(ControlDCredentials.Access.WRITE))
        model.vault.save(ControlDCredentials.Access.READ, "read-fixture")
        model.store.deleteHistory()
        assertTrue(model.store.recent(retainedBinding()).summaries.isEmpty())
        // Changing READ accounts also clears Write access before any endpoint
        // was selected; account identity is not inferred from a binding alone.
        close()
        fixtureContext
            .getSharedPreferences("taild.controld.settings", 0)
            .edit()
            .remove("binding")
            .commit()
        val accountJob = SupervisorJob()
        val accountModel =
            ControlDModel(
                fixtureContext,
                CoroutineScope(accountJob + Dispatchers.Default),
                app.tailDHistory,
                model.api,
            )
        try {
          assertNull(accountModel.state.value.binding)
          assertTrue(accountModel.state.value.hasWrite)
          accountModel.configureRead("other-read", null)
          val switched =
              accountModel.state.first {
                !it.busySetup && (it.inventory?.account == "different-account" || it.error != null)
              }
          assertNull(switched.error)
          assertFalse(switched.hasWrite)
          assertFalse(accountModel.vault.contains(ControlDCredentials.Access.WRITE))
          accountModel.configureRead("read-fixture", null)
          val restored =
              accountModel.state.first {
                !it.busySetup && (it.inventory?.account == "account" || it.error != null)
              }
          assertNull(restored.error)
          assertFalse(restored.hasWrite)
          assertNull(restored.binding)
        } finally {
          accountJob.cancelAndJoin()
        }
      } finally {
        close()
        model.vault.remove(ControlDCredentials.Access.READ)
        model.vault.remove(ControlDCredentials.Access.WRITE)
      }
    }
  }

  private fun retainedBinding() = ControlDBinding("account", null, "endpoint", "phone")
}
