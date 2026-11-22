package com.tailscale.ipn.taild

import android.app.AlarmManager
import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioManager
import android.media.AudioPlaybackConfiguration
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.tailscale.ipn.App
import com.tailscale.ipn.MainActivity
import com.tailscale.ipn.R
import com.tailscale.ipn.UninitializedApp
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.notifier.Notifier
import com.tailscale.ipn.ui.view.Setting
import com.tailscale.ipn.util.TSLog

/**
 * Pause while idle: the phone is a tailnet client, so while it rests nothing needs to reach it.
 * After the screen has been off for [IDLE_PAUSE_DELAY_MILLIS] with no audio or call active, TailD
 * disconnects the VPN (stopping magicsock keepalives, DERP and control traffic) and reconnects on
 * screen-on or when audio playback starts. Only a connection this feature paused is restored.
 */
internal const val IDLE_PAUSE_DELAY_MILLIS = 10 * 60 * 1000L

internal enum class IdlePauseDecision {
  PAUSE,
  RECHECK_LATER,
  NONE,
}

/** Pure decision taken when the screen-off delay expires. */
internal fun decideIdlePause(
    enabled: Boolean,
    interactive: Boolean,
    vpnRunning: Boolean,
    alreadyPaused: Boolean,
    audioBusy: Boolean,
): IdlePauseDecision =
    when {
      !enabled || interactive || !vpnRunning || alreadyPaused -> IdlePauseDecision.NONE
      audioBusy -> IdlePauseDecision.RECHECK_LATER
      else -> IdlePauseDecision.PAUSE
    }

/** True while media plays or a call (cellular or VoIP) holds the audio mode. */
internal fun isAudioBusy(musicActive: Boolean, audioMode: Int): Boolean =
    musicActive ||
        audioMode == AudioManager.MODE_IN_CALL ||
        audioMode == AudioManager.MODE_IN_COMMUNICATION ||
        audioMode == AudioManager.MODE_RINGTONE ||
        audioMode == AudioManager.MODE_CALL_SCREENING

object IdlePause {
  private const val TAG = "TailDIdlePause"
  private const val PREFS = "taild.idle-pause"
  private const val KEY_ENABLED = "enabled"
  private const val KEY_PAUSED = "paused"
  private const val ALARM_REQUEST = 0x7A1D
  internal const val NOTIFICATION_ID = 0x7A1D
  internal const val ACTION_CHECK = "com.tailscale.ipn.taild.IDLE_PAUSE_CHECK"
  internal const val ACTION_PAUSE = "com.tailscale.ipn.taild.IDLE_PAUSE"
  internal const val ACTION_RESUME = "com.tailscale.ipn.taild.IDLE_RESUME"

  @Volatile private var installed = false

  private fun prefs(context: Context) =
      context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

  fun isEnabled(context: Context): Boolean = prefs(context).getBoolean(KEY_ENABLED, true)

  fun setEnabled(context: Context, enabled: Boolean) {
    prefs(context).edit().putBoolean(KEY_ENABLED, enabled).apply()
    if (!enabled) {
      cancelCheck(context)
      if (isPaused(context)) resume(context, "disabled")
    }
  }

  fun isPaused(context: Context): Boolean = prefs(context).getBoolean(KEY_PAUSED, false)

  internal fun setPaused(context: Context, paused: Boolean) {
    prefs(context).edit().putBoolean(KEY_PAUSED, paused).commit()
  }

  /** Registers screen-state tracking; runs for the life of the app process. */
  fun install(context: Context) {
    if (installed) return
    installed = true
    val app = context.applicationContext
    val filter =
        IntentFilter().apply {
          addAction(Intent.ACTION_SCREEN_OFF)
          addAction(Intent.ACTION_SCREEN_ON)
        }
    ContextCompat.registerReceiver(
        app,
        object : BroadcastReceiver() {
          override fun onReceive(ctx: Context, intent: Intent) {
            when (intent.action) {
              Intent.ACTION_SCREEN_OFF ->
                  if (isEnabled(ctx) && Notifier.state.value == Ipn.State.Running) {
                    scheduleCheck(ctx, IDLE_PAUSE_DELAY_MILLIS)
                  }
              Intent.ACTION_SCREEN_ON -> {
                cancelCheck(ctx)
                if (isPaused(ctx)) resume(ctx, "screen on")
              }
            }
          }
        },
        filter,
        ContextCompat.RECEIVER_NOT_EXPORTED,
    )
  }

  private fun checkIntent(context: Context): PendingIntent =
      PendingIntent.getBroadcast(
          context,
          ALARM_REQUEST,
          Intent(context, IdlePauseAlarmReceiver::class.java).setAction(ACTION_CHECK),
          PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
      )

  internal fun scheduleCheck(context: Context, delayMillis: Long) {
    val alarms = context.getSystemService(AlarmManager::class.java) ?: return
    // Inexact and allowed while idle: in Doze the pause lands in the next maintenance window,
    // and the alarm grants the temporary allowance needed to start the pause service.
    alarms.setAndAllowWhileIdle(
        AlarmManager.ELAPSED_REALTIME_WAKEUP,
        SystemClock.elapsedRealtime() + delayMillis,
        checkIntent(context),
    )
  }

  internal fun cancelCheck(context: Context) {
    context.getSystemService(AlarmManager::class.java)?.cancel(checkIntent(context))
  }

  internal fun audioBusy(context: Context): Boolean {
    val audio = context.getSystemService(AudioManager::class.java) ?: return false
    return isAudioBusy(audio.isMusicActive, audio.mode)
  }

  internal fun onCheck(context: Context) {
    val power = context.getSystemService(PowerManager::class.java)
    val decision =
        decideIdlePause(
            enabled = isEnabled(context),
            interactive = power?.isInteractive != false,
            vpnRunning = Notifier.state.value == Ipn.State.Running,
            alreadyPaused = isPaused(context),
            audioBusy = audioBusy(context),
        )
    TSLog.d(TAG, "idle check: $decision")
    when (decision) {
      IdlePauseDecision.PAUSE ->
          try {
            ContextCompat.startForegroundService(
                context,
                Intent(context, IdlePauseService::class.java).setAction(ACTION_PAUSE),
            )
          } catch (e: Exception) {
            TSLog.e(TAG, "could not start idle pause: $e")
          }
      IdlePauseDecision.RECHECK_LATER -> scheduleCheck(context, IDLE_PAUSE_DELAY_MILLIS)
      IdlePauseDecision.NONE -> Unit
    }
  }

  /** Reconnects a VPN this feature paused. The pause service stops once IPNService starts. */
  internal fun resume(context: Context, reason: String) {
    if (!isPaused(context)) return
    TSLog.d(TAG, "resuming after idle pause: $reason")
    setPaused(context, false)
    App.get().startVPN()
  }

  /** Called by IPNService for every VPN start, including manual ones, to end an idle pause. */
  fun onVpnStartRequested(context: Context) {
    setPaused(context, false)
    context.stopService(Intent(context, IdlePauseService::class.java))
  }

  internal fun pausedNotification(context: Context): Notification {
    val reconnect =
        PendingIntent.getForegroundService(
            context,
            NOTIFICATION_ID,
            Intent(context, IdlePauseService::class.java).setAction(ACTION_RESUME),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    val open =
        PendingIntent.getActivity(
            context,
            NOTIFICATION_ID,
            Intent(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    return NotificationCompat.Builder(context, UninitializedApp.STATUS_CHANNEL_ID)
        .setSmallIcon(R.drawable.ic_notification_disabled)
        .setContentTitle(context.getString(R.string.taild_idle_paused))
        .setContentText(context.getString(R.string.taild_idle_paused_detail))
        .setSilent(true)
        .setOngoing(true)
        .setPriority(NotificationCompat.PRIORITY_MIN)
        .setContentIntent(open)
        .addAction(
            NotificationCompat.Action.Builder(0, context.getString(R.string.connect), reconnect)
                .build()
        )
        .build()
  }
}

class IdlePauseAlarmReceiver : BroadcastReceiver() {
  override fun onReceive(context: Context, intent: Intent) {
    if (intent.action == IdlePause.ACTION_CHECK) IdlePause.onCheck(context)
  }
}

/**
 * Keeps the process alive and listening while the VPN is paused, so screen-on and audio playback
 * can reconnect it. It holds no tunnel and does no network work.
 */
class IdlePauseService : Service() {
  private var audioCallback: AudioManager.AudioPlaybackCallback? = null

  override fun onBind(intent: Intent?): IBinder? = null

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    startForeground(IdlePause.NOTIFICATION_ID, IdlePause.pausedNotification(this))
    when (intent?.action) {
      IdlePause.ACTION_PAUSE -> {
        if (IdlePause.isPaused(this) || Notifier.state.value != Ipn.State.Running) {
          if (!IdlePause.isPaused(this)) stopSelf()
          return START_STICKY
        }
        IdlePause.setPaused(this, true)
        listenForAudio()
        App.get().stopVPN()
      }
      IdlePause.ACTION_RESUME -> resumeOrStop("notification")
      // Restarted after the process was killed: listeners are gone, so reconnect now.
      else -> resumeOrStop("service restart")
    }
    return START_STICKY
  }

  private fun resumeOrStop(reason: String) {
    if (IdlePause.isPaused(this)) IdlePause.resume(this, reason) else stopSelf()
  }

  private fun listenForAudio() {
    if (audioCallback != null) return
    val audio = getSystemService(AudioManager::class.java) ?: return
    val callback =
        object : AudioManager.AudioPlaybackCallback() {
          override fun onPlaybackConfigChanged(configs: MutableList<AudioPlaybackConfiguration>) {
            if (IdlePause.audioBusy(this@IdlePauseService)) {
              IdlePause.resume(this@IdlePauseService, "audio playback")
            }
          }
        }
    audio.registerAudioPlaybackCallback(callback, Handler(Looper.getMainLooper()))
    audioCallback = callback
  }

  override fun onDestroy() {
    audioCallback?.let {
      getSystemService(AudioManager::class.java)?.unregisterAudioPlaybackCallback(it)
    }
    audioCallback = null
    super.onDestroy()
  }
}

@Composable
fun IdlePauseSetting() {
  val context = LocalContext.current
  var enabled by remember { mutableStateOf(IdlePause.isEnabled(context)) }
  Setting.Switch(
      R.string.taild_idle_pause,
      subtitle = stringResource(R.string.taild_idle_pause_detail),
      isOn = enabled,
      onToggle = {
        enabled = it
        IdlePause.setEnabled(context, it)
      },
  )
}
