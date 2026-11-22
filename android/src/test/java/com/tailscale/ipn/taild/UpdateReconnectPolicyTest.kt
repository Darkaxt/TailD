package com.tailscale.ipn.taild

import com.tailscale.ipn.ui.model.Ipn
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UpdateReconnectPolicyTest {
  @Test
  fun reconnectsAVpnTheUserStillWantsAfterAnUpdate() {
    assertTrue(shouldReconnectAfterUpdate(Ipn.State.Running, idlePaused = false, true))
    assertTrue(shouldReconnectAfterUpdate(Ipn.State.Starting, idlePaused = false, true))
  }

  @Test
  fun keepsAUserStoppedVpnOff() {
    assertFalse(shouldReconnectAfterUpdate(Ipn.State.Stopped, idlePaused = false, true))
    assertFalse(shouldReconnectAfterUpdate(Ipn.State.Stopping, idlePaused = false, true))
  }

  @Test
  fun restoresAnIdlePausedVpn() {
    assertTrue(shouldReconnectAfterUpdate(Ipn.State.Stopped, idlePaused = true, true))
  }

  @Test
  fun neverReconnectsWithoutVpnPermissionOrLogin() {
    assertFalse(shouldReconnectAfterUpdate(Ipn.State.Running, idlePaused = true, false))
    assertFalse(shouldReconnectAfterUpdate(Ipn.State.NeedsLogin, idlePaused = true, true))
    assertFalse(shouldReconnectAfterUpdate(Ipn.State.NoState, idlePaused = false, true))
  }
}
