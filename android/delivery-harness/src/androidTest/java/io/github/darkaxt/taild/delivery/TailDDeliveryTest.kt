package io.github.darkaxt.taild.delivery

import android.app.UiAutomation
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.graphics.Rect
import android.net.LocalServerSocket
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.*
import java.io.DataInputStream
import java.security.MessageDigest
import java.util.regex.Pattern
import kotlinx.coroutines.*
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** A separate, self-targeted test UID: no private app API, production key or run-as access. */
class TailDDeliveryTest {
  private val instrumentation = InstrumentationRegistry.getInstrumentation()
  private val context = instrumentation.targetContext
  private val arguments = InstrumentationRegistry.getArguments()
  private val pkg = "io.github.darkaxt.taildns"
  private lateinit var device: UiDevice

  private fun node(selector: BySelector, packageName: String = pkg): UiObject2 =
      device.wait(Until.findObject(By.copy(selector).pkg(packageName)), 30_000)
          ?: error("Required delivery control missing: $selector")

  private fun click(selector: BySelector) {
    node(selector).click()
    device.waitForIdle()
  }

  private fun content(selector: BySelector): UiObject2 {
    if (!device.hasObject(By.copy(selector).pkg(pkg)))
        node(By.scrollable(true))
            .scrollUntil(Direction.DOWN, Until.findObject(By.copy(selector).pkg(pkg)))
    return node(selector)
  }

  private fun open(path: String) {
    context.startActivity(
        Intent(Intent.ACTION_VIEW, Uri.parse("taildns://navigate/$path"))
            .setPackage(pkg)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    device.waitForIdle()
  }

  private suspend fun phase(name: String) {
    LocalServerSocket("taild-r37-delivery").use { server ->
      instrumentation.sendStatus(0, Bundle().apply { putString("taild_phase", name) })
      val ack =
          withContext(Dispatchers.IO) {
            server.accept().use {
              val value = it.inputStream.read()
              it.outputStream.write(value)
              it.outputStream.flush()
              value
            }
          }
      assertEquals("Host completed $name", 1, ack)
    }
  }

  private fun signedPackage(expectedCode: Long? = null): Long {
    val info = context.packageManager.getPackageInfo(pkg, PackageManager.GET_SIGNING_CERTIFICATES)
    assertEquals(0, info.applicationInfo!!.flags and ApplicationInfo.FLAG_DEBUGGABLE)
    val signers = info.signingInfo!!.apkContentsSigners
    assertEquals(1, signers.size)
    val actual =
        MessageDigest.getInstance("SHA-256").digest(signers.single().toByteArray()).joinToString(
            ""
        ) {
          "%02x".format(it)
        }
    assertEquals("dcd0ede91eb7e0ed88a72b5289f84f8d4a61ccc22707f36378e15540b99d32e1", actual)
    expectedCode?.let { assertEquals(it, info.longVersionCode) }
    if (expectedCode != null) {
      val metadata =
          context
              .createPackageContext(pkg, 0)
              .assets
              .open("taild-build.json")
              .bufferedReader()
              .use { Json.parseToJsonElement(it.readText()).jsonObject }
      assertEquals(
          arguments.getString("source_revision"),
          metadata.getValue("source_revision").jsonPrimitive.content,
      )
      assertEquals(info.longVersionCode, metadata.getValue("version_code").jsonPrimitive.long)
      assertEquals(info.versionName, metadata.getValue("version_name").jsonPrimitive.content)
    }
    return info.longVersionCode
  }

  private fun launch() {
    context.startActivity(
        context.packageManager
            .getLaunchIntentForPackage(pkg)!!
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    device.waitForIdle()
  }

  private fun dnsPreference(expected: Boolean?) {
    open("settings")
    content(By.text("DNS settings")).click()
    val first = node(By.checkable(true))
    if (expected == null) {
      if (first.isChecked) first.click()
    } else assertEquals(expected, first.isChecked)
    val endpoint = "https://resolver.invalid/dns-query"
    content(By.text("HTTPS DNS endpoint"))
    val editor = node(By.clazz("android.widget.EditText"))
    if (expected == null) {
      editor.click()
      editor.text = endpoint
      val focused =
          checkNotNull(
              instrumentation.uiAutomation.rootInActiveWindow.findFocus(
                  AccessibilityNodeInfo.FOCUS_INPUT
              )
          )
      check(focused.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.id))
      device.waitForIdle()
    } else assertEquals("Manual resolver is retained without enabling it", endpoint, editor.text)
    device.pressBack()
    device.waitForIdle()
  }

  private fun analytics(enabled: Boolean, verifyOnly: Boolean = false) {
    open("settings")
    val label = content(By.text("Collect analytics"))
    val row = label.parent
    val control =
        row.findObject(By.checkable(true))
            ?: row.parent.findObject(By.checkable(true))
            ?: error("Analytics preference has no switch")
    if (verifyOnly) assertEquals(enabled, control.isChecked)
    else if (control.isChecked != enabled) control.click()
    device.waitForIdle()
  }

  private fun alwaysOn(enable: Boolean) {
    context.startActivity(
        Intent(android.provider.Settings.ACTION_VPN_SETTINGS)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    device.waitForIdle()
    val settings = "com.android.settings"
    node(By.desc(Pattern.compile(".*[Ss]ettings.*TailD.*|.*TailD.*[Ss]ettings.*")), settings)
        .click()
    val label = node(By.text("Always-on VPN"), settings)
    val row = label.parent.parent
    val toggle = row.findObject(By.checkable(true)) ?: error("Always-on VPN switch missing")
    if (toggle.isChecked != enable) toggle.click()
    device.waitForIdle()
    assertEquals(
        enable,
        node(By.text("Always-on VPN"), settings)
            .parent
            .parent
            .findObject(By.checkable(true))!!
            .isChecked,
    )
    launch()
  }

  private fun folder() {
    open("settings")
    content(By.text("Permissions")).click()
    click(By.text("Taildrop directory access"))
  }

  private fun prepareFolder() {
    folder()
    click(By.text("Pick a different directory"))
    val picker =
        context.packageManager
            .resolveActivity(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), 0)!!
            .activityInfo
            .packageName
    node(By.text(Pattern.compile("create new folder", Pattern.CASE_INSENSITIVE)), picker).click()
    node(By.clazz("android.widget.EditText"), picker).text = "TailDDelivery"
    node(By.text("OK"), picker).click()
    node(By.text(Pattern.compile("use this folder", Pattern.CASE_INSENSITIVE)), picker).click()
    node(By.text(Pattern.compile("allow", Pattern.CASE_INSENSITIVE)), picker).click()
    node(By.textContains("TailDDelivery"))
  }

  private suspend fun readSetup() {
    click(By.text("Control D"))
    click(By.text("Set up Control D"))
    LocalServerSocket("taild-r37-release-read").use { server ->
      instrumentation.sendStatus(
          0,
          Bundle().apply { putString("taild_phase", "read-credential-ready") },
      )
      withContext(Dispatchers.IO) {
        server.accept().use { socket ->
          val input = DataInputStream(socket.inputStream)
          val size = input.readInt()
          check(size in 8..8192)
          val bytes = ByteArray(size)
          input.readFully(bytes)
          try {
            node(By.res("taild-api-token")).text = bytes.toString(Charsets.UTF_8)
          } finally {
            bytes.fill(0)
          }
          socket.outputStream.write(1)
          socket.outputStream.flush()
        }
      }
    }
    click(By.text("Verify and save"))
    node(By.text("Remove saved API credentials"))
    click(By.text("Close"))
    click(By.text("No endpoint selected"))
    val name = checkNotNull(arguments.getString("endpoint_name"))
    content(By.text(name)).click()
    node(By.text(checkNotNull(arguments.getString("profile_name"))))
    click(By.text("Dashboard"))
    node(By.text(Pattern.compile("[1-9][0-9]* stored DNS observations")))
  }

  private fun retainedRead() {
    click(By.text("Control D"))
    node(By.text(checkNotNull(arguments.getString("endpoint_name"))))
    node(By.text(checkNotNull(arguments.getString("profile_name"))))
    click(By.text("Dashboard"))
    node(By.text(Pattern.compile("[1-9][0-9]* stored DNS observations")))
  }

  private fun renderedControls(): JsonArray {
    val density = context.resources.displayMetrics.density
    val screen = Rect(0, 0, device.displayWidth, device.displayHeight)
    fun visit(node: AccessibilityNodeInfo): List<JsonElement> {
      val children = (0 until node.childCount).flatMap { node.getChild(it)?.let(::visit).orEmpty() }
      if (node.packageName?.toString() != pkg || !node.isVisibleToUser) return children
      val bounds = Rect().also(node::getBoundsInScreen)
      if (node.isClickable && node.isEnabled && screen.contains(bounds)) {
        assertTrue(
            "Accessible action height ${node.viewIdResourceName}",
            bounds.height() / density >= 47.5f,
        )
        assertTrue(
            "Accessible action width ${node.viewIdResourceName}",
            bounds.width() / density >= 47.5f,
        )
      }
      return listOf(
          buildJsonObject {
            put("class", node.className?.toString().orEmpty())
            put("id", node.viewIdResourceName.orEmpty())
            put("text", node.text?.toString().orEmpty())
            put("description", node.contentDescription?.toString().orEmpty())
            put("bounds_px", bounds.flattenToString())
            put("clickable", node.isClickable)
            put("enabled", node.isEnabled)
          }
      ) + children
    }
    return JsonArray(visit(checkNotNull(instrumentation.uiAutomation.rootInActiveWindow)))
  }

  @Test
  fun productionUpgradeRecoveryAndAccessibility() = runBlocking {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(arguments.getString("taild_delivery") == "true")
    Configurator.getInstance().uiAutomationFlags =
        UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES
    device = UiDevice.getInstance(instrumentation)
    val baseline = signedPackage()
    launch()
    click(By.text("Get Started"))
    open("settings")
    content(By.text("Accounts")).click()
    click(By.desc("menu"))
    click(By.text("Use an alternate server"))
    node(By.clazz("android.widget.EditText")).text =
        checkNotNull(arguments.getString("control_url"))
    click(By.text("Add account"))
    node(By.text("taild-delivery-peer"))
    dnsPreference(null)
    dnsPreference(false)
    prepareFolder()
    alwaysOn(true)
    open("main/devices")
    phase("baseline-ready")
    phase("upgrade")
    launch()
    assertTrue(signedPackage() > baseline)
    node(By.text("taild-delivery-peer"))
    phase("assert-node-continuity")
    dnsPreference(false)
    folder()
    node(By.textContains("TailDDelivery"))
    analytics(false, verifyOnly = true)
    analytics(true)
    open("main/devices")
    click(By.text("TailDrop"))
    phase("receive-ready")
    node(By.textContains("taildrop.saved"))
    phase("assert-saved-file")
    phase("capture-signed-taildrop")
    if (arguments.getString("live_read") == "true") {
      readSetup()
      open("main/devices")
      node(By.text("TailD · Tailscale"))
      node(By.text("taild-delivery-peer"))
    }
    val installed = signedPackage()
    phase("rejected-downgrade")
    signedPackage(installed)
    phase("reinstall")
    launch()
    signedPackage(installed)
    node(By.text("taild-delivery-peer"))
    phase("assert-node-continuity")
    dnsPreference(false)
    folder()
    node(By.textContains("TailDDelivery"))
    analytics(true, verifyOnly = true)
    open("main/devices")
    context.sendBroadcast(
        Intent("$pkg.DISCONNECT_VPN").setClassName(pkg, "com.tailscale.ipn.IPNReceiver")
    )
    node(By.desc("Connect"))
    context.sendBroadcast(
        Intent("$pkg.CONNECT_VPN").setClassName(pkg, "com.tailscale.ipn.IPNReceiver")
    )
    node(By.desc("Disconnect"))
    node(By.text("taild-delivery-peer"))
    if (arguments.getString("live_read") == "true") {
      retainedRead()
      click(By.text("Control D"))
      click(By.desc("Control D setup"))
      click(By.text("Remove saved API credentials"))
      click(By.text("Close"))
      node(By.text("Set up Control D"))
    }
    analytics(false)
    content(By.text("Delete local history")).click()
    click(By.text("Delete local history"))
    open("main/devices")
    instrumentation.sendStatus(
        0,
        Bundle().apply { putString("taild_rendered_controls", renderedControls().toString()) },
    )
    phase("enable-talkback")
    for (label in listOf("Control D", "Dashboard", "Tailscale")) {
      val root = checkNotNull(instrumentation.uiAutomation.rootInActiveWindow)
      val labelNode =
          root.findAccessibilityNodeInfosByText(label).first { it.packageName?.toString() == pkg }
      var candidate = labelNode
      while (!candidate.isClickable && candidate.parent != null) candidate = candidate.parent
      check(candidate.packageName?.toString() == pkg && candidate.isClickable)
      instrumentation.uiAutomation.executeAndWaitForEvent(
          { check(candidate.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS)) },
          { it.eventType == AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED },
          30_000,
      )
      check(candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK))
      node(By.text("TailD · $label"))
    }
    phase("capture-talkback")
    phase("disable-talkback")
    alwaysOn(false)
    phase("delivery-verified")
  }
}
