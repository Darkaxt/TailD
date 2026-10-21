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

  private fun enterText(selector: BySelector, text: String, packageName: String = pkg) {
    check(
        device.wait(
            object : Condition<UiDevice, Boolean> {
              override fun apply(value: UiDevice): Boolean {
                val target = find(selector, packageName) ?: return false
                return try {
                  target.text = text
                  true
                } catch (_: StaleObjectException) {
                  // UiObject2 checks its node before dispatching ACTION_SET_TEXT. A stale
                  // node here means no action was dispatched; reacquire the current node.
                  false
                }
              }
            },
            30_000,
        )
    ) {
      "Editable delivery control missing: $selector"
    }
    device.waitForIdle()
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
    var observed: Boolean? = null
    check(
        device.wait(
            object : Condition<UiDevice, Boolean> {
              override fun apply(value: UiDevice): Boolean {
                val current = find(selector) ?: return false
                return try {
                  observed = current.isChecked
                  true
                } catch (_: StaleObjectException) {
                  // Read-only acquisition; no setting action has been dispatched.
                  false
                }
              }
            },
            30_000,
        )
    )
    if (verifyOnly) assertEquals(enabled, observed)
    else if (observed != enabled) {
      // This setting can still be moving during a navigation transition. Invoke
      // its actual accessibility click, then require the persisted UI state.
      fun controls(root: AccessibilityNodeInfo): List<AccessibilityNodeInfo> =
          (if (
              root.packageName?.toString() == pkg &&
                  root.contentDescription?.toString() == "Collect analytics" &&
                  root.isCheckable
          )
              listOf(root)
          else emptyList()) +
              (0 until root.childCount).flatMap { index ->
                root.getChild(index)?.let(::controls).orEmpty()
              }
      val target = controls(checkNotNull(automation.rootInActiveWindow)).single()
      check(target.isEnabled && target.performAction(AccessibilityNodeInfo.ACTION_CLICK))
      check(
          device.wait(
              object : Condition<UiDevice, Boolean> {
                override fun apply(value: UiDevice): Boolean =
                    value.hasObject(By.copy(selector).checked(enabled).pkg(pkg))
              },
              30_000,
          )
      ) {
        "Analytics setting did not reach the requested state"
      }
    }
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

  private fun savedHistoryMetadata(expected: String? = null): String {
    node(By.text("TailDrop history"))
    val saved = if (expected == null) By.textContains("taildrop.saved") else By.text(expected)
    if (find(saved) == null) {
      node(By.scrollable(true).hasDescendant(By.text("TailDrop history")))
          .scrollUntil(Direction.DOWN, Until.findObject(saved))
    }
    return node(saved).text
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
    if (arguments.getString("audit_only") == "true") {
      check(resume)
      phase("recovery-baseline")
      verifyAuditRelease()
      phase("rejected-downgrade")
      phase("reinstall")
      launch()
      signedPackage(checkNotNull(arguments.getString("candidate_code")).toLong())
      open("main/devices")
      node(By.text(peerName))
      phase("assert-node-continuity")
      click(By.text("Dashboard"))
      click(By.text("Applications"))
      node(By.res("taild-traffic-app-${arguments.getString("traffic_uid")}"))
      phase("delivery-verified")
      return@runBlocking
    }
    if (arguments.getString("ui_correction") == "true") {
      prepareFolder()
      alwaysOn(true)
      analytics(true)
      open("main/devices")
      node(By.text(peerName))
      click(By.text("TailDrop"))
      phase("receive-ready")
      content(By.text("Refresh history"))
      click(By.text("Refresh history"))
      val baselineFact = savedHistoryMetadata()
      assertTrue(baselineFact.contains("Saved to the selected Android document folder"))
      phase("assert-saved-file")
      phase("baseline-history-recorded")
      open("main/devices")
      phase("baseline-ready")
      phase("upgrade")
      launch()
      signedPackage(checkNotNull(arguments.getString("candidate_code")).toLong())
      node(By.text(peerName))
      phase("assert-node-continuity")
      folder()
      node(By.textContains("TailDDelivery"))
      analytics(true, verifyOnly = true)
      open("main/devices")
      click(By.text("TailDrop"))
      content(By.text("Refresh history"))
      click(By.text("Refresh history"))
      savedHistoryMetadata(baselineFact)
      phase("upgrade-history-preserved")
      verifyUiCorrection()
      if (arguments.getString("audit_release") == "true") verifyAuditRelease()
      phase("rejected-downgrade")
      phase("reinstall")
      launch()
      signedPackage(checkNotNull(arguments.getString("candidate_code")).toLong())
      folder()
      node(By.textContains("TailDDelivery"))
      analytics(arguments.getString("audit_release") != "true", verifyOnly = true)
      open("main/devices")
      node(By.text(peerName))
      click(By.text("TailDrop"))
      content(By.text("Refresh history"))
      click(By.text("Refresh history"))
      savedHistoryMetadata(baselineFact)
      phase("assert-saved-file")
      phase("reinstall-history-preserved")
      phase("delivery-verified")
      return@runBlocking
    }

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

  private suspend fun verifyUiCorrection() {
    fun shell(command: String) {
      android.os.ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(command))
          .use { it.readBytes() }
      device.waitForIdle()
    }
    fun connection() {
      open("main/devices")
      val peer = node(By.text(peerName))
      val android = node(By.descContains("android"))
      assertTrue(
          "Local Android icon precedes the remote peer",
          android.visibleBounds.top < peer.visibleBounds.top,
      )
      val owner = checkNotNull(arguments.getString("owner_name"))
      // A short LazyColumn has no scroll action in the accessibility tree.
      // The connection page identifies the account by login, never its owner heading.
      assertNull("No redundant owner heading on Connection", find(By.text(owner)))
      node(By.text("Tailscale"))
      node(By.text("Control D"))
    }
    fun search(value: String) {
      click(By.text("Control D"))
      val editor = node(By.clazz("android.widget.EditText"))
      editor.click()
      editor.text = value
      node(By.desc("Search domains or decisions"))
      assertEquals(value, node(By.clazz("android.widget.EditText")).text)
      // Setting text does not prove the keyboard has finished appearing. Back
      // before that transition closes MainActivity instead of dismissing the IME.
      check(
          device.wait(
              object : Condition<UiDevice, Boolean> {
                override fun apply(value: UiDevice): Boolean =
                    automation.windows.any {
                      it.type ==
                          android.view.accessibility.AccessibilityWindowInfo.TYPE_INPUT_METHOD
                    }
              },
              30_000,
          )
      ) {
        "Search keyboard must be visible before dismissing it"
      }
      device.pressBack()
      device.waitForIdle()
    }
    connection()
    phase("capture-ui-phone-light")
    search("Blocked")
    shell("cmd uimode night yes")
    node(By.desc("Scope & coverage"))
    assertEquals("Blocked", node(By.clazz("android.widget.EditText")).text)
    phase("capture-ui-phone-dark")
    node(By.clazz("android.widget.EditText")).click()
    click(By.desc("Clear domain or decision search"))
    assertTrue(node(By.clazz("android.widget.EditText")).text.isNullOrEmpty())
    shell("wm size 1680x1800")
    shell("wm density 320")
    connection()
    phase("capture-ui-rail-dark")
    search("example.invalid")
    shell("cmd uimode night no")
    node(By.desc("Scope & coverage"))
    assertEquals("example.invalid", node(By.clazz("android.widget.EditText")).text)
    node(By.clazz("android.widget.EditText")).click()
    click(By.desc("Clear domain or decision search"))
    assertTrue(node(By.clazz("android.widget.EditText")).text.isNullOrEmpty())
    phase("capture-ui-rail-light")
    shell("wm size 1080x2400")
    shell("wm density 480")
    shell("settings put system font_scale 1.5")
    node(By.res("taild-main-navigation-large"))
    click(By.text("Control D"))
    node(By.desc("Scope & coverage"))
    node(By.desc("Search domains or decisions"))
    click(By.desc("Scope & coverage"))
    content(By.text("Close scope details"))
    click(By.text("Close scope details"))
    phase("capture-ui-phone-large")
    shell("cmd uimode night yes")
    node(By.res("taild-main-navigation-large"))
    node(By.desc("Scope & coverage"))
    phase("capture-ui-phone-large-dark")
    click(By.text("Dashboard"))
    click(By.text("Applications"))
    node(By.desc("Export selected snapshot"))
    node(By.desc("OS app totals"))
    shell("settings put system font_scale 1.0")
    shell("cmd uimode night no")
  }

  private fun openFirewallList() {
    open("main/devices")
    click(By.text("Firewall"))
    val screen =
        device.wait(
            object : Condition<UiDevice, String?> {
              override fun apply(value: UiDevice): String? =
                  when {
                    value.hasObject(By.res("taild-app-diagnosis").pkg(pkg)) -> "diagnosis"
                    value.hasObject(By.res("taild-firewall-ready").pkg(pkg)) -> "list"
                    else -> null
                  }
            },
            30_000,
        ) ?: error("Retained Firewall screen did not finish loading")
    if (screen == "diagnosis") click(By.desc("Back to Firewall"))
    node(By.res("taild-firewall-ready"))
  }

  /** Verify the new diagnosis export against the retained real-traffic delivery fixture. */
  @Test
  fun appDiagnosisExportRetainsScope() {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(arguments.getString("taild_delivery") == "true")
    device = UiDevice.getInstance(instrumentation)
    signedPackage()
    val uid = checkNotNull(arguments.getString("traffic_uid")).toInt()
    openFirewallList()
    click(By.desc("Refresh app traffic"))
    node(By.res("taild-firewall-ready"))
    check(device.wait(Until.gone(By.res("taild-app-access-busy").pkg(pkg)), 30_000))
    click(By.clazz("android.widget.EditText"))
    enterText(By.clazz("android.widget.EditText"), "TailD F0")
    check(
        device.wait(
            object : Condition<UiDevice, Boolean> {
              override fun apply(value: UiDevice) =
                  automation.windows.any {
                    it.type == android.view.accessibility.AccessibilityWindowInfo.TYPE_INPUT_METHOD
                  }
            },
            30_000,
        )
    )
    device.pressBack()
    device.waitForIdle()
    val currentRow = By.res("taild-firewall-app").hasDescendant(By.desc("Block app TailD F0 One"))
    val list = node(By.res("taild-app-access"))
    if (!device.hasObject(By.copy(currentRow).pkg(pkg)))
        list.scrollUntil(Direction.DOWN, Until.findObject(By.copy(currentRow).pkg(pkg)))
    // Resumed fixture installs create new generations. Select the current installation,
    // not an older recorded row with the same display label and larger byte totals.
    val diagnosis = node(currentRow).findObject(By.desc("Diagnose TailD F0 One / TailD F0 Two"))
    diagnosis.click()
    device.waitForIdle()
    node(By.desc(Pattern.compile("Hourly observed traffic; peak .*")))
    click(By.desc("Export app diagnosis snapshot"))
    val picker =
        checkNotNull(
                context.packageManager.resolveActivity(
                    Intent(Intent.ACTION_CREATE_DOCUMENT)
                        .setType("application/json")
                        .addCategory(Intent.CATEGORY_OPENABLE),
                    0,
                )
            )
            .activityInfo
            .packageName
    node(By.desc("Show roots"), picker).click()
    val downloads = device.findObject(UiSelector().packageName(picker).text("Downloads"))
    assertTrue(downloads.waitForExists(30_000))
    assertTrue(downloads.click())
    val fileName = "taild-app-diagnosis-${System.currentTimeMillis()}.json"
    enterText(By.clazz("android.widget.EditText"), fileName, picker)
    node(By.text(Pattern.compile("save", Pattern.CASE_INSENSITIVE)), picker).click()
    node(By.text("Selected snapshot exported to your chosen document."))
    val text =
        android.os.ParcelFileDescriptor.AutoCloseInputStream(
                automation.executeShellCommand("cat /sdcard/Download/$fileName")
            )
            .use { it.bufferedReader().readText() }
    val data = Json.parseToJsonElement(text).jsonObject
    assertEquals(
        86400000L,
        data.getValue("untilExclusive").jsonPrimitive.long -
            data.getValue("fromInclusive").jsonPrimitive.long,
    )
    val facts = data.getValue("facts").jsonArray
    assertTrue(facts.isNotEmpty())
    assertTrue(
        facts.all { row ->
          val source = row.jsonObject.getValue("source").jsonObject
          source.getValue("uid").jsonPrimitive.int == uid ||
              source["dns"]
                  ?.jsonObject
                  ?.get("queryIdentity")
                  ?.jsonObject
                  ?.get("uid")
                  ?.jsonPrimitive
                  ?.int == uid
        }
    )
    assertTrue(
        facts
            .filter {
              it.jsonObject.getValue("source").jsonObject.getValue("uid").jsonPrimitive.int == uid
            }
            .sumOf { it.jsonObject.getValue("measuredBytes").jsonPrimitive.long } > 32768L
    )
  }

  /** Caller updates only the owned traffic fixtures after the current-installation export check. */
  @Test
  fun historicalDiagnosisRetainsPackageMetadata() {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    assumeTrue(arguments.getString("taild_delivery") == "true")
    device = UiDevice.getInstance(instrumentation)
    signedPackage()
    openFirewallList()
    click(By.desc("Refresh app traffic"))
    node(By.res("taild-firewall-ready"))
    check(device.wait(Until.gone(By.res("taild-app-access-busy").pkg(pkg)), 30_000))
    enterText(By.clazz("android.widget.EditText"), "TailD F0")
    val currentRow = By.res("taild-firewall-app").hasDescendant(By.desc("Block app TailD F0 One"))
    if (!device.hasObject(By.copy(currentRow).pkg(pkg)))
        node(By.res("taild-app-access"))
            .scrollUntil(Direction.DOWN, Until.findObject(By.copy(currentRow).pkg(pkg)))
    node(currentRow).findObject(By.desc("Diagnose TailD F0 One / TailD F0 Two")).click()
    node(By.text("No recorded traffic"))
    node(By.text("No retained destinations in this day."))
    click(By.desc("Back to Firewall"))
    node(By.res("taild-app-access")).scroll(Direction.UP, 1f)
    val recordedRow =
        By.res("taild-firewall-app")
            .hasDescendant(By.text("Recorded identity"))
            .hasDescendant(By.desc("Diagnose TailD F0 One / TailD F0 Two"))
    if (!device.hasObject(By.copy(recordedRow).pkg(pkg)))
        node(By.res("taild-app-access"))
            .scrollUntil(Direction.DOWN, Until.findObject(By.copy(recordedRow).pkg(pkg)))
    node(recordedRow).findObject(By.desc("Diagnose TailD F0 One / TailD F0 Two")).click()
    node(By.desc(Pattern.compile("Hourly observed traffic; peak .*")))
    click(By.desc("App & coverage details"))
    node(By.res("taild-firewall-details"))
    node(By.text("Previous installation"))
    content(By.text("io.github.darkaxt.taild.fixture.one"))
    click(By.text("Close"))
  }

  /** Exercise the normally signed/R8 package through its public UI only. */
  private suspend fun verifyAuditRelease() {
    fun shell(command: String) {
      android.os.ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(command))
          .use { it.readBytes() }
      device.waitForIdle()
    }
    fun dismissKeyboard() {
      check(
          device.wait(
              object : Condition<UiDevice, Boolean> {
                override fun apply(value: UiDevice) =
                    automation.windows.any {
                      it.type ==
                          android.view.accessibility.AccessibilityWindowInfo.TYPE_INPUT_METHOD
                    }
              },
              30_000,
          )
      )
      device.pressBack()
      device.waitForIdle()
    }
    shell("wm size 1080x2400")
    shell("wm density 480")
    phase("production-firewall-backend")
    openFirewallList()
    node(By.res("taild-app-access"))
    if (!device.hasObject(By.desc("Hide firewall setup").pkg(pkg)))
        click(By.desc("Firewall setup & coverage"))
    val entry =
        device.wait(
            object : Condition<UiDevice, UiObject2?> {
              override fun apply(value: UiDevice) =
                  find(By.textContains("Android firewall state inspected."))
                      ?: find(By.text("Connect Shizuku"))
            },
            30_000,
        ) ?: error("App-control setup did not render")
    if (entry.text == "Connect Shizuku") {
      val permission =
          context.packageManager.checkPermission("moe.shizuku.manager.permission.API_V23", pkg) ==
              PackageManager.PERMISSION_GRANTED
      click(By.text("Connect Shizuku"))
      if (!permission)
          node(By.text(Pattern.compile("Allow all the time|Allow")), "moe.shizuku.privileged.api")
              .click()
    }
    node(By.textContains("Android firewall state inspected."))
    click(By.clazz("android.widget.EditText"))
    enterText(By.clazz("android.widget.EditText"), "TailD F0")
    dismissKeyboard()
    phase("capture-signed-firewall")
    click(By.desc("Block app TailD F0 One"))
    node(By.text("Every app sharing this UID is affected."))
    click(By.text("Apply"))
    node(By.text("TailD block active"))
    phase("production-firewall-blocked")
    click(By.desc("Remove TailD block for TailD F0 One"))
    click(By.text("Apply"))
    node(By.desc("Block app TailD F0 One"))
    phase("production-firewall-restored")
    analytics(true)
    phase("production-traffic")
    analytics(false)
    openFirewallList()
    click(By.desc("Refresh app traffic"))
    node(By.res("taild-firewall-ready"))
    check(device.wait(Until.gone(By.res("taild-app-access-busy").pkg(pkg)), 30_000))
    click(By.clazz("android.widget.EditText"))
    enterText(By.clazz("android.widget.EditText"), "TailD F0")
    dismissKeyboard()
    node(By.text("Last 24 hours"))
    val currentRow = By.res("taild-firewall-app").hasDescendant(By.desc("Block app TailD F0 One"))
    val list = node(By.res("taild-app-access"))
    if (!device.hasObject(By.copy(currentRow).pkg(pkg)))
        list.scrollUntil(Direction.DOWN, Until.findObject(By.copy(currentRow).pkg(pkg)))
    // Resumed fixture installs create new generations. Select the current installation,
    // not an older recorded row with the same display label and larger byte totals.
    val diagnosis = node(currentRow).findObject(By.desc("Diagnose TailD F0 One / TailD F0 Two"))
    phase("capture-signed-firewall-hourly")
    diagnosis.click()
    device.waitForIdle()
    node(By.res("taild-app-diagnosis"))
    node(By.desc(Pattern.compile("Hourly observed traffic; peak .*")))
    node(By.res("taild-diagnosis-table-heading"))
    node(By.res("taild-diagnosis-destination-row"))
    click(By.desc("App & coverage details"))
    content(By.text("io.github.darkaxt.taild.fixture.one"))
    click(By.text("Close"))
    phase("capture-signed-diagnosis-light")
    shell("cmd uimode night yes")
    node(By.res("taild-app-diagnosis"))
    node(By.desc(Pattern.compile("Hourly observed traffic; peak .*")))
    phase("capture-signed-diagnosis-dark")
    click(By.desc("Back to Firewall"))
    node(By.res("taild-app-access"))
    shell("cmd uimode night no")
    open("main/devices")
    click(By.text("Dashboard"))
    click(By.text("Applications"))
    click(By.desc("Refresh Dashboard"))
    val uid = checkNotNull(arguments.getString("traffic_uid"))
    val app = By.res("taild-traffic-app-$uid")
    node(By.res("taild-traffic-content"))
        .scrollUntil(Direction.DOWN, Until.findObject(By.copy(app).pkg(pkg)))
    node(app)
    phase("capture-signed-traffic-light")
    node(By.res("taild-traffic-content")).scroll(Direction.UP, 1f)
    click(By.desc("Export selected snapshot"))
    val picker =
        checkNotNull(
                context.packageManager.resolveActivity(
                    Intent(Intent.ACTION_CREATE_DOCUMENT)
                        .setType("application/json")
                        .addCategory(Intent.CATEGORY_OPENABLE),
                    0,
                )
            )
            .activityInfo
            .packageName
    node(By.desc("Show roots"), picker).click()
    device.waitForIdle()
    val downloads = device.findObject(UiSelector().packageName(picker).text("Downloads"))
    assertTrue(downloads.waitForExists(30_000))
    assertTrue(downloads.click())
    device.waitForIdle()
    node(By.clazz("android.widget.EditText"), picker).text =
        checkNotNull(arguments.getString("traffic_export"))
    device.waitForIdle()
    node(By.text(Pattern.compile("save", Pattern.CASE_INSENSITIVE)), picker).click()
    node(By.text("Selected snapshot exported to your chosen document."))
    phase("production-traffic-export")
    shell("cmd uimode night yes")
    node(By.text("Applications"))
    phase("capture-signed-traffic-dark")
    shell("wm size 1920x1200")
    shell("wm density 240")
    node(By.res("taild-main-navigation-rail"))
    node(By.text("Applications"))
    phase("capture-signed-traffic-rail")
    shell("cmd uimode night no")
    node(By.text("Applications"))
    click(By.text("Geography"))
    phase("capture-signed-geography-empty")
    shell("wm size 1080x2400")
    shell("wm density 480")
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
