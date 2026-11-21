// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.VpnService
import android.os.Build
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.notifier.Notifier
import com.tailscale.ipn.util.TSLog
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Bounds the wait for the backend's first settled state. Startup normally settles within seconds;
 * without a bound a backend stuck in NoState/Stopping would hold the worker until WorkManager stops
 * it, and the user would never receive the "connect failed" notification below.
 */
internal const val VPN_START_READINESS_TIMEOUT_MILLIS = 60_000L

internal suspend fun awaitVPNStartReadiness(
    states: StateFlow<Ipn.State>,
    timeoutMillis: Long = VPN_START_READINESS_TIMEOUT_MILLIS,
): Boolean {
  val state =
      withTimeoutOrNull(timeoutMillis) {
        states.first { it != Ipn.State.NoState && it != Ipn.State.Stopping }
      } ?: return false
  return state > Ipn.State.NeedsMachineAuth
}

/** A worker that exists to support [IPNReceiver]. */
class StartVPNWorker(appContext: Context, workerParams: WorkerParameters) :
    CoroutineWorker(appContext, workerParams) {
  override suspend fun getForegroundInfo(): ForegroundInfo = workerForegroundInfo()

  override suspend fun doWork(): Result {
    // A receiver can recreate a cold process before the cached readiness preference has ever been
    // populated. Initialize the backend and wait for its initial state instead of rejecting the
    // first connect request or relying on a second request after startup happens incidentally.
    val app = App.get()
    if (awaitVPNStartReadiness(Notifier.state) && VpnService.prepare(app) == null) {
      app.startVPN()
      return Result.success()
    }

    TSLog.e("StartVPNWorker", "Tailscale isn't ready to start the VPN, notify the user.")

    val notificationManager =
        app.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    val channelId = "start_vpn_channel"
    app.createNotificationChannel(
        channelId,
        applicationContext.getString(R.string.vpn_start),
        applicationContext.getString(
            R.string
                .notifications_delivered_when_user_interaction_is_required_to_establish_the_vpn_tunnel
        ),
        NotificationManager.IMPORTANCE_HIGH,
    )

    val intent =
        requireNotNull(app.packageManager.getLaunchIntentForPackage(app.packageName)).apply {
          flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
    val pendingIntentFlags =
        PendingIntent.FLAG_ONE_SHOT or
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_IMMUTABLE else 0
    val pendingIntent = PendingIntent.getActivity(app, 0, intent, pendingIntentFlags)
    val notification =
        Notification.Builder(app, channelId)
            .setContentTitle(app.getString(R.string.title_connection_failed))
            .setContentText(app.getString(R.string.body_open_tailscale))
            .setSmallIcon(R.drawable.ic_notification)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()
    notificationManager.notify(1, notification)

    return Result.failure()
  }
}
