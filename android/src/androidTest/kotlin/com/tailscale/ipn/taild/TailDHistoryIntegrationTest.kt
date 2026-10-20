package com.tailscale.ipn.taild

import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.model.Netmap
import com.tailscale.ipn.ui.model.Tailcfg
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Uses separate device-protected fixture storage on an emulator, never product history. */
class TailDHistoryIntegrationTest {
  @Test
  fun optInScopeDedupRestartAndDeleteUseRealSQLite() = runBlocking {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    val context =
        InstrumentationRegistry.getInstrumentation()
            .targetContext
            .createDeviceProtectedStorageContext()
    context.deleteDatabase("taild-history.sqlite")
    context.getSharedPreferences("taild.analytics", 0).edit().clear().commit()
    val map =
        Netmap.NetworkMap(
            SelfNode =
                Tailcfg.Node(StableID = "test-self", User = 1, Name = "test-phone", Online = true),
            Peers =
                listOf(Tailcfg.Node(StableID = "test-peer", Name = "test-laptop", Online = null)),
            Domain = "isolated.test",
            UserProfiles = emptyMap(),
            TKAEnabled = false,
        )
    val scopeKey = activityScope(map, Ipn.Prefs())!!
    var job = SupervisorJob()
    var history = TailDHistory(context, CoroutineScope(job + Dispatchers.Default))
    try {
      history.refresh(scopeKey)
      history.observe(Ipn.State.Running, map, Ipn.Prefs(), null)
      history.awaitIdle()
      assertFalse(history.enabled.value)
      assertTrue(history.rows.value.isEmpty())

      history.setEnabled(true)
      history.awaitIdle()
      history.observe(Ipn.State.Running, map, Ipn.Prefs(), null)
      val outgoing =
          Ipn.OutgoingFile(
              ID = "transfer-1",
              Name = "not-retained-secret.txt",
              DeclaredSize = 42,
              PeerID = "test-peer",
              Finished = true,
              Succeeded = true,
          )
      repeat(2) {
        history.observe(
            Ipn.State.Running,
            map,
            Ipn.Prefs(),
            null,
            Ipn.Notify(OutgoingFiles = listOf(outgoing)),
        )
      }
      repeat(2) { history.documentSaved(scopeKey, "content://test/private-document") }
      history.awaitIdle()
      assertNull(history.error.value)
      assertEquals(1, history.rows.value.count { it.event.kind == "taildrop.sent" })
      assertEquals(1, history.rows.value.count { it.event.kind == "taildrop.saved" })
      assertTrue(history.rows.value.any { it.event.detail == "Unknown" })
      assertTrue(
          history.rows.value.none {
            it.toString().contains("not-retained-secret") || it.toString().contains("content://")
          }
      )
      val count = history.rows.value.size

      history.refresh("different/account")
      history.awaitIdle()
      assertTrue(history.rows.value.isEmpty())
      history.refresh(scopeKey)
      history.setEnabled(false)
      history.awaitIdle()
      history.observe(Ipn.State.Stopped, map, Ipn.Prefs(), null)
      history.awaitIdle()
      assertEquals(count, history.rows.value.size)
      job.cancelAndJoin()

      job = SupervisorJob()
      history = TailDHistory(context, CoroutineScope(job + Dispatchers.Default))
      history.refresh(scopeKey)
      history.awaitIdle()
      assertFalse(history.enabled.value)
      assertEquals(count, history.rows.value.size)
      history.setEnabled(true)
      history.awaitIdle()
      history.observe(Ipn.State.Running, map, Ipn.Prefs(), null)
      history.awaitIdle()
      assertTrue(history.rows.value.any { it.event.detail.contains("Previous observation:") })
      history.deleteHistory()
      history.awaitIdle()
      assertTrue(history.rows.value.isEmpty())
      assertNull(history.error.value)
    } finally {
      job.cancelAndJoin()
      context.deleteDatabase("taild-history.sqlite")
      context.getSharedPreferences("taild.analytics", 0).edit().clear().commit()
    }
  }
}
