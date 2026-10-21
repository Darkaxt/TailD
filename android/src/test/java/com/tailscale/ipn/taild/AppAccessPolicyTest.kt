package com.tailscale.ipn.taild

import org.junit.Assert.*
import org.junit.Test

class AppAccessPolicyTest {
  private val app =
      AppAccessIdentity(10123, listOf(AppAccessPackage("test.one", "One", listOf("cert"), 1, 2, 3)))

  private fun snapshot(enabled: Boolean = false, blocked: Set<Int> = emptySet()) =
      AppAccessSnapshot(0, listOf(0, 10), listOf(app), enabled, blocked)

  private fun rejected(action: () -> Unit) {
    assertThrows(IllegalArgumentException::class.java, action)
  }

  @Test
  fun ownedSharedUidRuleHasExactIdentityAndDoesNotAdoptAnotherBlock() {
    val shared = app.copy(packages = app.packages + app.packages.first().copy(name = "test.two"))
    val base = snapshot().copy(apps = listOf(shared))
    val request = planAppAccess(base, shared, true, null, 10500)
    assertEquals(2, request.identity.packages.size)
    val applied = base.copy(chainEnabled = true, blockedUids = setOf(app.uid, 10888))
    rejected { planAppAccess(applied, shared, true, null, 10500) }
    rejected { planAppAccess(applied, shared, false, null, 10500) }
    val owned = AppAccessOwned(shared, "ACTIVE")
    assertFalse(planAppAccess(applied, shared, false, owned, 10500).blocked)
    rejected { planAppAccess(applied, shared, false, AppAccessOwned(app, "ACTIVE"), 10500) }
  }

  @Test
  fun rejectsUidReuseProfileSwitchSelfAndDisabledForeignRules() {
    rejected { planAppAccess(snapshot(), app, true, null, app.uid) }
    rejected { planAppAccess(snapshot().copy(profile = 10), app, true, null, 10500) }
    rejected {
      planAppAccess(
          snapshot(),
          app.copy(packages = listOf(app.packages.first().copy(installed = 9))),
          true,
          null,
          10500,
      )
    }
    rejected { planAppAccess(snapshot(blocked = setOf(10999)), app, true, null, 10500) }
    assertTrue(planAppAccess(snapshot(true, setOf(10999)), app, true, null, 10500).blocked)
  }

  @Test
  fun completeMapKeepsOtherChainsAndRejectsPartialReadback() {
    assertEquals(
        setOf(10123),
        appAccessBlockedUids(
            listOf(
                "sUidOwnerMap:",
                "10123 OEM_DENY_2_MATCH",
                "10001 OEM_DENY_3_MATCH BACKGROUND_MATCH",
                "sUidPermissionMap:",
            )
        ),
    )
    rejected { appAccessBlockedUids(listOf("sUidOwnerMap:", "10123 OEM_DENY_2_MATCH")) }
    rejected {
      appAccessBlockedUids(
          listOf("sUidOwnerMap:", "Failed to read: permission denied", "sUidPermissionMap:")
      )
    }
  }
}
