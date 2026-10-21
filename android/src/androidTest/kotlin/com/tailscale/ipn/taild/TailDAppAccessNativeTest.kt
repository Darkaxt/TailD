package com.tailscale.ipn.taild

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import rikka.shizuku.Shizuku

private class NativeAppAccess(
    private val fixture: NativeControlDSession,
    private val compose: androidx.compose.ui.test.junit4.ComposeTestRule,
) {
  suspend fun open() {
    fixture.launch()
    val rail = compose.onNodeWithTag("taild-main-navigation-rail")
    if (
        compose.onAllNodesWithTag("taild-main-navigation-rail").fetchSemanticsNodes().isNotEmpty()
    ) {
      rail.performScrollToNode(hasText("Dashboard"))
      compose.onNodeWithText("Dashboard").assertIsDisplayed()
      rail.performScrollToNode(hasText("Firewall"))
    }
    compose.onNodeWithText("Firewall").performClick()
  }

  fun ready(afterBackendRestart: Boolean = false) {
    try {
      compose.waitUntil(30_000) {
        val state = com.tailscale.ipn.App.get().tailDAppAccess.state.value
        val inspected =
            listOf(
                    "Android firewall state inspected.",
                    "App rule changed and read back.",
                    "Recorded rule is inactive;",
                    "Recorded rule is present.",
                )
                .any { state.status.startsWith(it) }
        (!afterBackendRestart || state.connected) &&
            (state.error != null ||
                (!state.busy && state.connected && state.snapshot != null && inspected))
      }
    } catch (failure: Throwable) {
      val state = com.tailscale.ipn.App.get().tailDAppAccess.state.value
      fixture.instrumentation.sendStatus(
          0,
          android.os.Bundle().apply {
            putString(
                "taild_failure",
                "App access: connected=${state.connected}, busy=${state.busy}, profile=${state.snapshot?.profile}, status=${state.status}, error=${state.error}, owned=${state.owned.map { it.phase }}, server=${Shizuku.pingBinder()}",
            )
          },
      )
      throw failure
    }
    compose.onNodeWithTag("taild-app-access").performScrollToIndex(0)
    compose.onNodeWithTag("taild-app-access-error").assertDoesNotExist()
    compose.onNodeWithTag("taild-app-access-search").performScrollTo().performTextClearance()
    compose.onNodeWithTag("taild-app-access-search").performTextInput("TailD F0")
    compose.onNodeWithTag("taild-app-access-search").performImeAction()
  }

  fun selectProfile(profile: Int) {
    compose.onNodeWithTag("taild-app-access").performScrollToIndex(0)
    compose.onNodeWithText("Profile $profile").performScrollTo().performClick()
    compose.waitUntil(30_000) {
      val state = com.tailscale.ipn.App.get().tailDAppAccess.state.value
      state.error != null || (!state.busy && state.snapshot?.profile == profile)
    }
    ready()
  }

  fun action(description: String) {
    compose
        .onNodeWithTag("taild-app-access")
        .performScrollToNode(hasContentDescription(description))
    compose.onNodeWithContentDescription(description).performClick()
  }

  fun apply(blocked: Boolean) {
    action(if (blocked) "Block app TailD F0 One" else "Remove TailD block for TailD F0 One")
    for (name in listOf("One", "Two")) {
      compose
          .onNodeWithText("TailD F0 $name\nio.github.darkaxt.taild.fixture.${name.lowercase()}")
          .performScrollTo()
          .assertIsDisplayed()
    }
    compose
        .onNodeWithText("Every app sharing this UID is affected.")
        .performScrollTo()
        .assertIsDisplayed()
    compose.onNodeWithText("Apply").performClick()
    // Removing the recovery banner changes the lazy list's viewport. Observe
    // actual readback first, then bring the inverse control back into composition.
    compose.waitUntil(30_000) {
      val state = com.tailscale.ipn.App.get().tailDAppAccess.state.value
      !state.busy &&
          (state.error != null ||
              (state.status == "App rule changed and read back." &&
                  state.owned.any {
                    it.identity.packages.any { p ->
                      p.name == "io.github.darkaxt.taild.fixture.one"
                    }
                  } == blocked))
    }
    compose.onNodeWithTag("taild-app-access-error").assertDoesNotExist()
    val inverse = if (blocked) "Remove TailD block for TailD F0 One" else "Block app TailD F0 One"
    compose.onNodeWithTag("taild-app-access").performScrollToNode(hasContentDescription(inverse))
    compose.onNodeWithContentDescription(inverse).assertIsDisplayed()
  }

  fun refresh() {
    compose.onNodeWithTag("taild-app-access").performScrollToIndex(0)
    compose.onNodeWithContentDescription("Refresh app access").performClick()
    ready()
  }

  fun reconcile() {
    compose.onNodeWithTag("taild-app-access").performScrollToNode(hasText("Reconcile"))
    compose.onNodeWithText("Reconcile").performClick()
    compose.waitUntil(30_000) {
      val state = com.tailscale.ipn.App.get().tailDAppAccess.state.value
      !state.busy && (state.error != null || state.owned.all { it.phase == "ACTIVE" })
    }
    compose.onNodeWithTag("taild-app-access").performScrollToIndex(0)
    compose.onNodeWithTag("taild-app-access-error").assertDoesNotExist()
  }
}

class TailDAppAccessNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun realSharedUidBlockAndBackendLoss() = runBlocking {
    val fixture = NativeControlDSession(reset = true, compose = compose)
    try {
      val ui = NativeAppAccess(fixture, compose)
      ui.open()
      fixture.phase("app-access-ensure-backend")
      // Binder arrival is a real SDK event. Advancing Compose's virtual frame
      // clock while Android is laying out the permission window re-enters measure.
      val binderReady = CompletableDeferred<Unit>()
      val listener = Shizuku.OnBinderReceivedListener { binderReady.complete(Unit) }
      Shizuku.addBinderReceivedListenerSticky(listener)
      try {
        binderReady.await()
      } finally {
        Shizuku.removeBinderReceivedListener(listener)
      }
      fixture.instrumentation.waitForIdleSync()
      fixture.phase("app-access-binder-ready")
      val granted =
          Shizuku.checkSelfPermission() == android.content.pm.PackageManager.PERMISSION_GRANTED
      if (
          !granted ||
              !fixture.context
                  .getSharedPreferences("taild.app-access", 0)
                  .getBoolean("configured", false)
      )
          fixture.click(By.text("Connect Shizuku"))
      if (!granted) {
        val manager =
            fixture.device.wait(
                androidx.test.uiautomator.Until.findObject(
                    // The official release obfuscates resource names; use its actual
                    // rendered English authorization label on this fixed-locale VM.
                    By.pkg("moe.shizuku.privileged.api").text("Allow all the time")
                ),
                30_000,
            )
        assertNotNull("Real Shizuku authorization dialog", manager)
        manager.click()
      }
      ui.ready()
      compose.onNodeWithText("Shared UID · 2 apps affected").performScrollTo().assertIsDisplayed()
      compose.onNodeWithText("io.github.darkaxt.taild.fixture.one").assertDoesNotExist()
      ui.action("App details for TailD F0 One")
      compose
          .onNodeWithText("io.github.darkaxt.taild.fixture.one")
          .performScrollTo()
          .assertIsDisplayed()
      ui.action("App details for TailD F0 One")
      compose.onNodeWithText("io.github.darkaxt.taild.fixture.one").assertDoesNotExist()
      // Resume the previous owned run through the actual reviewed removal UI.
      // Never clear its journal or reset a platform chain to manufacture a baseline.
      if (com.tailscale.ipn.App.get().tailDAppAccess.state.value.owned.isNotEmpty()) {
        ui.apply(false)
        fixture.phase("app-access-unblocked")
      }
      fixture.phase("app-access-before")
      ui.apply(true)
      fixture.phase("capture-app-access-blocked")
      fixture.phase("app-access-blocked")
      fixture.phase("app-access-stop-backend")
      compose.waitUntil(30_000) {
        val state = com.tailscale.ipn.App.get().tailDAppAccess.state.value
        !state.connected && state.status.startsWith("Shizuku disconnected.")
      }
      compose.onNodeWithTag("taild-app-access").performScrollToIndex(0)
      compose.onNodeWithText("Shizuku disconnected.", substring = true).assertIsDisplayed()
      fixture.phase("capture-app-access-backend-lost")
      fixture.phase("app-access-restart-backend")
      ui.ready(afterBackendRestart = true)
      fixture.phase("assert-read-only-dashboard")
      // Leave this owned block for the next process's real persisted-state recovery.
    } finally {
      fixture.close()
    }
  }
}

class TailDAppAccessRestartNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun restartCoexistenceIdentityAndProfileBoundaries() = runBlocking {
    val fixture = NativeControlDSession(reset = false, compose = compose)
    try {
      val ui = NativeAppAccess(fixture, compose)
      ui.open()
      ui.ready()
      fixture.phase("capture-app-access-restarted")
      ui.apply(false)
      fixture.phase("app-access-unblocked")
      val profile = InstrumentationRegistry.getArguments().getString("app_access_profile")!!.toInt()
      ui.selectProfile(profile)
      fixture.phase("app-access-profile-before")
      ui.apply(true)
      fixture.phase("app-access-profile-blocked")
      ui.apply(false)
      fixture.phase("app-access-profile-unblocked")
      ui.selectProfile(0)
      fixture.phase("app-access-seed-external")
      ui.refresh()
      ui.apply(true)
      fixture.phase("app-access-coexist-blocked")
      ui.apply(false)
      fixture.phase("app-access-coexist-unblocked")
      fixture.phase("app-access-seed-disabled-external")
      ui.refresh()
      ui.action("Block app TailD F0 One")
      compose
          .onNodeWithText(
              "The disabled firewall chain has existing rules; activation would change other policy"
          )
          .assertExists()
      fixture.phase("app-access-refused-foreign-activation")
      fixture.phase("app-access-clear-external")
      ui.refresh()
      ui.action("Block app TailD F0 One")
      fixture.phase("app-access-change-identity")
      compose.onNodeWithText("Apply").performClick()
      compose.waitUntil(30_000) {
        compose
            .onAllNodesWithText("App identity changed;", substring = true)
            .fetchSemanticsNodes()
            .isNotEmpty()
      }
      fixture.phase("app-access-stale-refused")
      ui.refresh()
      ui.reconcile()
      ui.apply(true)
      fixture.phase("app-access-before-reboot")
      fixture.phase("assert-read-only-dashboard")
    } finally {
      fixture.close()
    }
  }
}

class TailDAppAccessRebootNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun rebootNeverReappliesAndExplicitReconciliationRestoresOwnership() = runBlocking {
    val fixture = NativeControlDSession(reset = false, compose = compose)
    try {
      val ui = NativeAppAccess(fixture, compose)
      ui.open()
      compose.onNodeWithText("Recorded rules").assertExists()
      assertFalse("No hidden Shizuku boot provisioning", Shizuku.pingBinder())
      fixture.phase("app-access-after-reboot")
      fixture.phase("app-access-restart-backend")
      ui.ready(afterBackendRestart = true)
      ui.reconcile()
      fixture.phase("app-access-reboot-reconciled")
      ui.apply(true)
      ui.apply(false)
      fixture.phase("app-access-final-restored")
      fixture.phase("capture-app-access-final")
      fixture.phase("assert-read-only-dashboard")
    } finally {
      fixture.close()
    }
  }
}

/** Drop an actual successful RPC response at the transport boundary, then recover explicitly. */
class TailDAppAccessFailureNativeTest {
  @get:Rule val compose = createEmptyComposeRule()

  @Test
  fun unknownWriteAndLiveAutomaticTheme() = runBlocking {
    val fixture = NativeControlDSession(reset = false, compose = compose)
    try {
      val ui = NativeAppAccess(fixture, compose)
      ui.open()
      ui.ready()
      val model = com.tailscale.ipn.App.get().tailDAppAccess
      // Resume a previous interrupted fixture through its recorded, reviewed UI.
      model.state.value.owned.singleOrNull()?.let { recorded ->
        assertEquals(
            setOf("io.github.darkaxt.taild.fixture.one", "io.github.darkaxt.taild.fixture.two"),
            recorded.identity.packages.map { it.name }.toSet(),
        )
        if (recorded.identity.profile != model.state.value.snapshot!!.profile) {
          ui.selectProfile(recorded.identity.profile)
        }
        if (
            recorded.phase != "ACTIVE" ||
                recorded.identity.uid !in model.state.value.snapshot!!.blockedUids
        ) {
          ui.reconcile()
          ui.ready()
        }
        if (model.state.value.owned.isNotEmpty()) ui.apply(false)
        if (recorded.identity.profile != 0) fixture.phase("app-access-profile-unblocked")
      }
      if (model.state.value.snapshot!!.profile != 0) ui.selectProfile(0)
      assertTrue(model.state.value.owned.isEmpty())
      fixture.phase("app-access-before")
      fixture.phase("switch-theme")
      compose.waitUntil(30_000) {
        fixture.context.resources.configuration.uiMode and
            android.content.res.Configuration.UI_MODE_NIGHT_MASK ==
            android.content.res.Configuration.UI_MODE_NIGHT_YES
      }
      ui.ready()
      compose.onNodeWithText("TailD · Firewall").assertIsDisplayed()
      assertTrue("Theme transition sends no policy write", model.state.value.owned.isEmpty())
      fixture.phase("capture-app-access-auto-dark")

      // Test-only client transport fault: the real typed service applies and reads
      // back the rule. Its response is then lost after the host kills that server.
      // No fault hook or alternate privileged command path enters the product APK.
      val serviceField =
          AppAccessModel::class.java.getDeclaredField("service").apply { isAccessible = true }
      val remote = serviceField.get(model) as IAppAccessService
      serviceField.set(
          model,
          object : IAppAccessService by remote {
            override fun apply(request: String): String {
              remote.apply(request)
              runBlocking { fixture.phase("app-access-drop-response") }
              throw android.os.DeadObjectException()
            }
          },
      )
      ui.action("Block app TailD F0 One")
      compose.onNodeWithText("Apply").performClick()
      compose.waitUntil(30_000) {
        !model.state.value.busy &&
            model.state.value.status.startsWith("Change outcome needs reconciliation.")
      }
      assertFalse(model.state.value.connected)
      assertEquals(listOf("PENDING_BLOCK"), model.state.value.owned.map { it.phase })
      compose.onNodeWithTag("taild-app-access").performScrollToIndex(0)
      compose
          .onNodeWithText("Change outcome needs reconciliation.", substring = true)
          .assertIsDisplayed()
      fixture.phase("capture-app-access-pending")
      fixture.phase("app-access-restart-backend")
      ui.ready(afterBackendRestart = true)
      ui.reconcile()
      fixture.phase("app-access-pending-reconciled")
      ui.apply(false)
      fixture.phase("app-access-final-restored")
      // A recorded work-profile rule remains recoverable from the personal list.
      // The record's full UID/profile, rather than the current view, owns readback.
      val profile = InstrumentationRegistry.getArguments().getString("app_access_profile")!!.toInt()
      ui.selectProfile(profile)
      ui.apply(true)
      fixture.phase("app-access-profile-blocked")
      ui.selectProfile(0)
      compose
          .onNodeWithTag("taild-app-access")
          .performScrollToNode(hasText("Reconcile recorded rule"))
      compose.onNodeWithText("Reconcile recorded rule").performClick()
      compose.waitUntil(30_000) { !model.state.value.busy }
      assertNull(model.state.value.error)
      assertEquals(profile, model.state.value.snapshot!!.profile)
      fixture.phase("app-access-profile-reconciled")
      ui.ready()
      ui.apply(false)
      fixture.phase("app-access-profile-unblocked")
      fixture.phase("assert-read-only-dashboard")
    } finally {
      fixture.close()
    }
  }
}
