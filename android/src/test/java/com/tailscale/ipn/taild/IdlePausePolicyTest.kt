package com.tailscale.ipn.taild

import android.media.AudioManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class IdlePausePolicyTest {
  private fun decide(
      enabled: Boolean = true,
      interactive: Boolean = false,
      vpnRunning: Boolean = true,
      alreadyPaused: Boolean = false,
      audioBusy: Boolean = false,
  ) = decideIdlePause(enabled, interactive, vpnRunning, alreadyPaused, audioBusy)

  @Test
  fun pausesARunningVpnOnceTheScreenStaysOffWithoutAudio() {
    assertEquals(IdlePauseDecision.PAUSE, decide())
  }

  @Test
  fun neverPausesWhenDisabledInteractiveStoppedOrAlreadyPaused() {
    assertEquals(IdlePauseDecision.NONE, decide(enabled = false))
    assertEquals(IdlePauseDecision.NONE, decide(interactive = true))
    // A VPN the user disconnected is not ours to restore later.
    assertEquals(IdlePauseDecision.NONE, decide(vpnRunning = false))
    assertEquals(IdlePauseDecision.NONE, decide(alreadyPaused = true))
  }

  @Test
  fun playingAudioDefersThePauseInsteadOfCuttingTheStream() {
    assertEquals(IdlePauseDecision.RECHECK_LATER, decide(audioBusy = true))
  }

  @Test
  fun mediaAndEveryCallModeCountAsBusy() {
    assertTrue(isAudioBusy(musicActive = true, audioMode = AudioManager.MODE_NORMAL))
    assertTrue(isAudioBusy(false, AudioManager.MODE_IN_CALL))
    assertTrue(isAudioBusy(false, AudioManager.MODE_IN_COMMUNICATION))
    assertTrue(isAudioBusy(false, AudioManager.MODE_RINGTONE))
    assertFalse(isAudioBusy(false, AudioManager.MODE_NORMAL))
  }
}
