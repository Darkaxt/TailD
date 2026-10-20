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
import android.view.accessibility.AccessibilityManager
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
  private val automation
    get() = instrumentation.getUiAutomation(Configurator.getInstance().uiAutomationFlags)

  private val context = instrumentation.targetContext
  private val arguments = InstrumentationRegistry.getArguments()
  private val peerName
    get() = checkNotNull(arguments.getString("peer_name"))

  private val pkg = "io.github.darkaxt.taildns"
  private lateinit var device: UiDevice

  private fun find(selector: BySelector, packageName: String = pkg): UiObject2? {
    if (Build.VERSION.SDK_INT >= 33) automation.clearCache()
    return device.findObject(By.copy(selector).pkg(packageName))
  }

  private fun node(selector: BySelector, packageName: String = pkg): UiObject2 =
      device.wait(
          object : Condition<UiDevice, UiObject2?> {
            override fun apply(value: UiDevice): UiObject2? = find(selector, packageName)
          },
          30_000,
      ) ?: error("Required delivery control missing: $selector")

  private fun click(selector: BySelector) {
    check(
        device.wait(
            object : Condition<UiDevice, Boolean> {
              override fun apply(value: UiDevice): Boolean {
                val target = find(By.copy(selector).enabled(true)) ?: return false
                return try {
                  target.click()
                  true
                } catch (_: StaleObjectException) {
                  // UiAutomator 2.3 rejects a stale handle before dispatching its gesture.
                  // Reacquire that handle after Compose remounts; never repeat a dispatched action.
                  false
                }
              }
            },
            30_000,
        )
    ) {
      "Actionable delivery control missing: $selector"
    }
    device.waitForIdle()
  }

  private fun content(selector: BySelector): UiObject2 {
    val target = By.copy(selector).pkg(pkg)
    val ready =
        device.wait(
            object : Condition<UiDevice, UiObject2?> {
              override fun apply(value: UiDevice): UiObject2? =
                  find(selector) ?: find(By.scrollable(true))
            },
            30_000,
        ) ?: error("Content did not render")
    if (!device.hasObject(target)) ready.scrollUntil(Direction.DOWN, Until.findObject(target))
    return node(selector)
  }

  private fun open(path: String) {
    context.startActivity(
        Intent(Intent.ACTION_VIEW, Uri.parse("taildns://navigate/$path"))
            .setPackage(pkg)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    device.waitForIdle()
    if (path == "settings") node(By.text("Settings"))
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
    content(By.text("DNS settings"))
    click(By.text("DNS settings"))
    val corpDNS = By.desc("Use Tailscale DNS").checkable(true)
    node(corpDNS)
    if (expected == null) {
      if (node(corpDNS).isChecked) click(corpDNS)
      check(
          device.wait(
              object : Condition<UiDevice, Boolean> {
                override fun apply(value: UiDevice): Boolean = find(corpDNS)?.isChecked == false
              },
              30_000,
          )
      )
    } else assertEquals(expected, node(corpDNS).isChecked)
    val endpoint = "https://resolver.invalid/dns-query"
    content(By.text("HTTPS DNS endpoint"))
    val editor = node(By.clazz("android.widget.EditText"))
    if (expected == null) {
      editor.click()
      editor.text = endpoint
      val ime =
          android.provider.Settings.Secure.getString(
                  context.contentResolver,
                  android.provider.Settings.Secure.DEFAULT_INPUT_METHOD,
              )
              .substringBefore('/')
      node(By.desc(Pattern.compile("Done", Pattern.CASE_INSENSITIVE)), ime).click()
      check(device.wait(Until.gone(By.pkg(ime)), 30_000))
      node(By.clazz("android.widget.EditText").enabled(true))
      device.waitForIdle()
    } else assertEquals("Manual resolver is retained without enabling it", endpoint, editor.text)
    device.pressBack()
    device.waitForIdle()
  }

  private fun analytics(enabled: Boolean, verifyOnly: Boolean = false) {
    open("settings")
    content(By.text("Collect analytics"))
    val selector = By.desc("Collect analytics").checkable(true)
    val control = node(selector)
    if (verifyOnly) assertEquals(enabled, control.isChecked)
    else if (control.isChecked != enabled) click(selector)
    device.waitForIdle()
  }

  private fun alwaysOn(enable: Boolean) {
    context.startActivity(
        Intent(android.provider.Settings.ACTION_VPN_SETTINGS)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    )
    device.waitForIdle()
    val settings = "com.android.settings"
    check(
        device.wait(
            object : Condition<UiDevice, Boolean> {
              override fun apply(value: UiDevice): Boolean =
                  find(By.text("Always-on VPN"), settings) != null ||
                      find(By.desc("Settings"), settings) != null
            },
            30_000,
        )
    )
    // Android may restore this task directly to the VPN's existing details page.
    if (find(By.text("Always-on VPN"), settings) == null) {
      node(By.desc("Settings"), settings).click()
    }
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
    content(By.text("Permissions"))
    click(By.text("Permissions"))
    click(By.text("Taildrop directory access"))
  }

  private fun prepareFolder() {
    folder()
    if (arguments.getString("origin_folder_prepared") == "true") {
      node(By.textContains("TailDDelivery"))
      return
    }
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
    if (find(By.text("Set up Control D")) == null) {
      // A recovery continuation reuses the READ vault already verified on this signed APK.
      retainedRead()
      return
    }
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
            node(By.res("taild-api-token"))
            fun input(node: AccessibilityNodeInfo): AccessibilityNodeInfo? {
              if (
                  node.packageName?.toString() == pkg &&
                      node.viewIdResourceName == "taild-api-token"
              )
                  return node
              for (index in 0 until node.childCount) {
                node.getChild(index)?.let { child ->
                  input(child)?.let {
                    return it
                  }
                }
              }
              return null
            }
            val field = checkNotNull(input(checkNotNull(automation.rootInActiveWindow)))
            // UiObject2.setText logs its input. Invoke the same Android text action without that
            // wrapper.
            check(
                field.performAction(
                    AccessibilityNodeInfo.ACTION_SET_TEXT,
                    Bundle().apply {
                      putCharSequence(
                          AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,
                          bytes.toString(Charsets.UTF_8),
                      )
                    },
                )
            )
          } finally {
            bytes.fill(0)
          }
          socket.outputStream.write(1)
          socket.outputStream.flush()
        }
      }
    }
    click(By.text("Verify and save"))
    content(By.text("Remove saved API credentials"))
    click(By.text("Close"))
    val name = checkNotNull(arguments.getString("endpoint_name"))
    if (find(By.text("No endpoint selected")) != null) {
      click(By.text("No endpoint selected"))
      content(By.text(name))
      click(By.text(name))
    } else node(By.text(name))
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
            "Accessible action width ${node.viewIdResourceName} ${node.text} ${node.contentDescription} ${bounds.flattenToString()} density=$density",
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
    return JsonArray(visit(checkNotNull(automation.rootInActiveWindow)))
  }

  private fun savedHistoryMetadata() {
    node(By.text("TailDrop history"))
    val saved = By.textContains("taildrop.saved")
    if (find(saved) == null) {
      node(By.scrollable(true).hasDescendant(By.text("TailDrop history")))
          .scrollUntil(Direction.DOWN, Until.findObject(saved))
    }
    node(saved)
  }

  @Test
  fun inspectOwnedInputRoots() {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    Configurator.getInstance().uiAutomationFlags =
        UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES
    device = UiDevice.getInstance(instrumentation)
    assumeTrue(device.currentPackageName == pkg)
    fun ids(node: AccessibilityNodeInfo): List<String> =
        listOf(
            "${node.packageName}:${node.viewIdResourceName}:${node.isEditable}:${node.isClickable}:${Rect().also(node::getBoundsInScreen).flattenToString()}:${if (node.isEditable || node.isPassword) "redacted" else node.text}"
        ) + (0 until node.childCount).flatMap { node.getChild(it)?.let(::ids).orEmpty() }
    val active = automation.rootInActiveWindow
    instrumentation.sendStatus(
        0,
        Bundle().apply {
          putString(
              "taild_input_roots",
              buildJsonObject {
                put("uia_field_found", find(By.res("taild-api-token")) != null)
                put("active", active?.let { JsonArray(ids(it).map(::JsonPrimitive)) } ?: JsonNull)
                put(
                    "windows",
                    JsonArray(
                        automation.windows.map { window ->
                          window.root?.let { JsonArray(ids(it).map(::JsonPrimitive)) } ?: JsonNull
                        }
                    ),
                )
              }
                  .toString(),
          )
        },
    )
  }

  @Test
  fun inspectOwnedSystemWindow() {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    Configurator.getInstance().uiAutomationFlags =
        UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES
    device = UiDevice.getInstance(instrumentation)
    assumeTrue(device.currentPackageName == "com.android.settings")
    val tree = java.io.ByteArrayOutputStream()
    device.dumpWindowHierarchy(tree)
    instrumentation.sendStatus(
        0,
        Bundle().apply { putString("taild_system_tree", tree.toString("UTF-8")) },
    )
  }

  @Test
  fun productionUpgradeRecoveryAndAccessibility() = runBlocking {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(arguments.getString("taild_delivery") == "true")
    Configurator.getInstance().uiAutomationFlags =
        UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES
    device = UiDevice.getInstance(instrumentation)
    val resume = arguments.getString("resume_candidate") == "true"
    val baseline = signedPackage()
    launch()
    if (arguments.getString("finalize_only") == "true") {
      signedPackage(checkNotNull(arguments.getString("candidate_code")).toLong())
      open("main/devices")
      finishDelivery()
      return@runBlocking
    }
    if (resume) {
      signedPackage(checkNotNull(arguments.getString("candidate_code")).toLong())
      // A recovery-only continuation does not repeat or claim the original migration checks.
      phase("resumed-candidate")
    }
    if (!resume && arguments.getString("origin_intro_seen") != "true") click(By.text("Get Started"))
    open("settings")
    val accounts = By.text(Pattern.compile("Accounts|user-[0-9]+@fake-control\\.example\\.net"))
    content(accounts)
    click(accounts)
    click(By.desc("menu"))
    click(By.text("Use an alternate server"))
    node(By.clazz("android.widget.EditText")).text =
        checkNotNull(arguments.getString("control_url"))
    click(By.text("Add account"))
    open("main/devices")
    node(By.text(peerName))
    dnsPreference(null)
    dnsPreference(false)
    phase("origin-dns-prepared")
    prepareFolder()
    phase("origin-folder-prepared")
    alwaysOn(true)
    open("main/devices")
    phase(if (resume) "recovery-baseline" else "baseline-ready")
    if (!resume) {
      phase("upgrade")
      launch()
      assertTrue(signedPackage() > baseline)
      node(By.text(peerName))
      phase("assert-node-continuity")
      dnsPreference(false)
      folder()
      node(By.textContains("TailDDelivery"))
      analytics(false, verifyOnly = true)
      analytics(true)
      open("main/devices")
      click(By.text("TailDrop"))
      phase("receive-ready")
      savedHistoryMetadata()
      phase("assert-saved-file")
      phase("capture-signed-taildrop")
    } else {
      analytics(true, verifyOnly = true)
      open("main/devices")
    }
    if (arguments.getString("live_read") == "true") {
      readSetup()
      open("main/devices")
      node(By.text("TailD \u00b7 Tailscale"))
      node(By.text(peerName))
    }
    val installed = signedPackage()
    phase("rejected-downgrade")
    signedPackage(installed)
    phase("reinstall")
    launch()
    signedPackage(installed)
    node(By.text(peerName))
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
    node(By.text(peerName))
    if (arguments.getString("live_read") == "true") {
      retainedRead()
      click(By.text("Control D"))
      click(By.desc("Control D setup"))
      content(By.text("Remove saved API credentials"))
      click(By.text("Remove saved API credentials"))
      click(By.text("Close"))
      node(By.text("Set up Control D"))
    }
    finishDelivery()
  }

  private fun matchingText(root: AccessibilityNodeInfo, text: String): List<AccessibilityNodeInfo> =
      (if (root.packageName?.toString() == pkg && root.text?.toString() == text) listOf(root)
      else emptyList()) +
          (0 until root.childCount).flatMap {
            root.getChild(it)?.let { child -> matchingText(child, text) }.orEmpty()
          }

  private suspend fun finishDelivery() {
    analytics(false)
    content(By.text("Delete local history"))
    click(By.text("Delete local history"))
    node(By.text("Cancel"))
    val deleteRoot = checkNotNull(automation.rootInActiveWindow)
    val deleteActions =
        matchingText(deleteRoot, "Delete local history")
            .mapNotNull { label ->
              var candidate: AccessibilityNodeInfo? = label
              while (candidate != null && !candidate.isClickable) candidate = candidate.parent
              candidate?.takeIf { it.packageName?.toString() == pkg && it.isEnabled }
            }
            .distinct()
    check(deleteActions.size == 1) { "Exact deletion confirmation action required" }
    check(deleteActions.single().performAction(AccessibilityNodeInfo.ACTION_CLICK))
    check(device.wait(Until.gone(By.text("Cancel").pkg(pkg)), 30_000))
    open("main/devices")
    node(By.text("TailD \u00b7 Tailscale"))
    check(device.wait(Until.gone(By.text("Settings").pkg(pkg)), 30_000))
    // The outgoing title can leave the viewport while the incoming destination is still clipped.
    // Wait for its rightmost bottom-navigation target to reach the actual viewport edge.
    check(
        device.wait(
            object : Condition<UiDevice, Boolean> {
              override fun apply(value: UiDevice): Boolean {
                var target = find(By.text("Dashboard")) ?: return false
                return try {
                  while (!target.isClickable && target.parent != null) target = target.parent
                  target.visibleBounds.right == device.displayWidth &&
                      target.visibleBounds.width() >= 48 * context.resources.displayMetrics.density
                } catch (_: StaleObjectException) {
                  false
                }
              }
            },
            30_000,
        )
    )
    device.waitForIdle()
    instrumentation.sendStatus(
        0,
        Bundle().apply { putString("taild_rendered_controls", renderedControls().toString()) },
    )
    phase("enable-talkback")
    val accessibility = context.getSystemService(AccessibilityManager::class.java)
    check(
        device.wait(
            object : Condition<UiDevice, Boolean> {
              override fun apply(value: UiDevice): Boolean = accessibility.isTouchExplorationEnabled
            },
            30_000,
        )
    ) {
      "TalkBack touch exploration did not become active"
    }
    for (label in listOf("Control D", "Dashboard", "Tailscale")) {
      node(By.text(label))
      val root = checkNotNull(automation.rootInActiveWindow)
      val labelNode = matchingText(root, label).first()
      var candidate = labelNode
      while (!candidate.isClickable && candidate.parent != null) candidate = candidate.parent
      check(candidate.packageName?.toString() == pkg && candidate.isClickable)
      if (candidate.isAccessibilityFocused)
          check(candidate.performAction(AccessibilityNodeInfo.ACTION_CLEAR_ACCESSIBILITY_FOCUS))
      automation.executeAndWaitForEvent(
          {
            check(candidate.performAction(AccessibilityNodeInfo.ACTION_ACCESSIBILITY_FOCUS)) {
              "Focus rejected for $label: visible=${candidate.isVisibleToUser}, important=${candidate.isImportantForAccessibility}, actions=${candidate.actionList.map { it.id }}"
            }
          },
          { it.eventType == AccessibilityEvent.TYPE_VIEW_ACCESSIBILITY_FOCUSED },
          30_000,
      )
      check(candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK))
      node(By.text("TailD \u00b7 $label"))
    }
    phase("capture-talkback")
    phase("disable-talkback")
    alwaysOn(false)
    phase("delivery-verified")
  }
}
