package com.tailscale.ipn.taild

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.PowerManager
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.tailscale.ipn.App
import com.tailscale.ipn.awaitVPNStartReadiness
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.notifier.Notifier
import com.tailscale.ipn.util.TSLog
import com.tailscale.ipn.workerForegroundInfo

/**
 * Reconnect after an in-place update. Replacing the package kills the process and the VPN service,
 * and nothing restarts it: the backend comes back Running (WantRunning survives) with no tunnel.
 */
internal fun shouldReconnectAfterUpdate(
    state: Ipn.State,
    idlePaused: Boolean,
    vpnPermitted: Boolean,
): Boolean {
  if (!vpnPermitted) return false
  // Starting/Running mean the user still wants the VPN; a user-stopped VPN settles in Stopped.
  val wanted = state == Ipn.State.Starting || state == Ipn.State.Running
  // An idle pause stops the VPN (Stopped) but is ours to restore.
  return wanted || (idlePaused && state == Ipn.State.Stopped)
}

class UpdateReconnectReceiver : BroadcastReceiver() {
  override fun onReceive(context: Context, intent: Intent) {
    if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
    val request =
        OneTimeWorkRequestBuilder<UpdateReconnectWorker>()
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .build()
    WorkManager.getInstance(context)
        .enqueueUniqueWork("taild-update-reconnect", ExistingWorkPolicy.REPLACE, request)
  }
}

class UpdateReconnectWorker(appContext: Context, params: WorkerParameters) :
    CoroutineWorker(appContext, params) {
  override suspend fun getForegroundInfo(): ForegroundInfo = workerForegroundInfo()

  override suspend fun doWork(): Result {
    val app = App.get()
    awaitVPNStartReadiness(Notifier.state)
    val state = Notifier.state.value
    val reconnect =
        shouldReconnectAfterUpdate(
            state = state,
            idlePaused = IdlePause.isPaused(app),
            vpnPermitted = VpnService.prepare(app) == null,
        )
    TSLog.d("TailDUpdateReconnect", "after update: state=$state reconnect=$reconnect")
    if (reconnect) {
      app.startVPN()
      // No screen-off broadcast follows an update made while the screen is off, so arm the
      // idle pause here instead of waiting for the next screen cycle.
      val interactive = app.getSystemService(PowerManager::class.java)?.isInteractive != false
      if (!interactive && IdlePause.isEnabled(app)) {
        IdlePause.scheduleCheck(app, IDLE_PAUSE_DELAY_MILLIS)
      }
    }
    return Result.success()
  }
}
