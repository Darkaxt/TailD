package com.tailscale.ipn.taild

import com.tailscale.ipn.ui.model.Tailcfg
import com.tailscale.ipn.ui.util.PeerSet
import com.tailscale.ipn.ui.util.withSelfFirst
import org.junit.Assert.*
import org.junit.Test

class DevicePresentationTest {
  @Test
  fun selfIsFirstWithoutDuplicateAndHiddenSelfStaysHidden() {
    val self = Tailcfg.Node(StableID = "self")
    val other = Tailcfg.Node(StableID = "other")
    val sets = listOf(PeerSet(-1, "Pinned", listOf(other)), PeerSet(1, "Owner", listOf(self)))
    assertEquals(
        listOf("self", "other"),
        sets.withSelfFirst("self").flatMap { it.nodes }.map { it.StableID },
    )
    assertEquals(sets.take(1), sets.take(1).withSelfFirst("self"))
  }

  @Test
  fun taildropUsesAuthoritativeEligibilityAndHidesUnknownOrOffline() {
    val node = Tailcfg.Node(StableID = "other", Online = true, TaildropTarget = 1)
    assertEquals(true, taildropCapability(node, "self"))
    assertEquals(false, taildropCapability(node.copy(TaildropTarget = 4), "self"))
    assertNull(taildropCapability(node.copy(TaildropTarget = 0), "self"))
    assertNull(taildropCapability(node.copy(Online = false), "self"))
    assertNull(taildropCapability(node.copy(Online = null), "self"))
    assertNull(taildropCapability(node, "other"))
    assertNull(
        taildropCapability(node.copy(TaildropTarget = null, Capabilities = emptyList()), "self")
    )
  }
}
