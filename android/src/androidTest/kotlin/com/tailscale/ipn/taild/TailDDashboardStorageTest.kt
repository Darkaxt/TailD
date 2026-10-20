package com.tailscale.ipn.taild

import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry
import java.time.Instant
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

class TailDDashboardStorageTest {
  @Test
  fun realSqliteSnapshotsRetentionCancellationAndRecordingBoundary() = runBlocking {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    val context =
        InstrumentationRegistry.getInstrumentation()
            .targetContext
            .createDeviceProtectedStorageContext()
    context.deleteDatabase("taild-dns.sqlite")
    context.deleteDatabase("taild-history.sqlite")
    context.getSharedPreferences("taild.analytics", 0).edit().clear().commit()
    var lifetime = SupervisorJob()
    var history = TailDHistory(context, CoroutineScope(lifetime + Dispatchers.Default))
    val store = ControlDDnsStore(context)
    val binding = ControlDBinding("storage-account", null, "endpoint", "client")
    val until = Instant.now()
    val window = DashboardWindow(until.minusSeconds(7 * 86400), until)
    val facts =
        (0..250).map { index ->
          ControlDDnsFact(
              mapOf(
                  "timestamp" to until.minusSeconds(index + 1L).toString(),
                  "endpointId" to "endpoint",
                  "clientId" to "client",
                  "question" to "stored.invalid",
                  "rrType" to "A",
                  "action" to "0",
              )
          )
        }
    val slice = ControlDDnsSlice(binding, window.from, window.until, facts, false)
    try {
      assertFalse(history.importDns(store, slice))
      history.setEnabled(true)
      history.awaitIdle()
      assertTrue(history.importDns(store, slice))
      history.importDns(store, slice)
      val (revision, all) = store.facts(binding, window.from, window.until)
      assertEquals(251, all.size)
      assertEquals(100, store.recent(binding, now = until).rows.size)
      assertEquals(
          251L,
          store.recent(binding, "blocked", until).summaries["stored.invalid" to "A"]!!.total,
      )
      assertTrue(
          store.facts(binding.copy(client = "other"), window.from, window.until).second.isEmpty()
      )
      history.importDns(store, slice.copy(facts = facts.take(3), truncated = true))
      assertEquals(all, store.facts(binding, window.from, window.until).second)
      assertTrue(store.recent(binding).coverage.contains("incomplete"))
      assertTrue(store.returnedWindows(binding, window).isNotEmpty())
      var checked = 0
      val cancelled = runCatching {
        store.import(slice.copy(facts = facts.take(100))) { ++checked < 50 }
      }
          .exceptionOrNull()
      assertTrue(cancelled is CancellationException)
      assertEquals(all, store.facts(binding, window.from, window.until).second)
      assertTrue(store.facts(binding, window.from, window.until).first > revision)
      // The queue orders a current commit, recording-off acknowledgment, then rejected persistence.
      val beforeOff = async(start = CoroutineStart.UNDISPATCHED) { history.importDns(store, slice) }
      history.setEnabled(false)
      history.awaitIdle()
      assertTrue(beforeOff.await())
      assertFalse(history.enabled.value)
      assertFalse(history.importDns(store, slice.copy(facts = emptyList())))
      assertEquals(251, store.facts(binding, window.from, window.until).second.size)
      // Retention is enforced even if a provider sends an older observation.
      val expired =
          ControlDDnsFact(
              facts.first().raw + mapOf("timestamp" to until.minusSeconds(8 * 86400).toString())
          )
      store.import(
          slice.copy(from = until.minusSeconds(9 * 86400), facts = listOf(expired) + facts)
      )
      assertEquals(251, store.facts(binding, until.minusSeconds(9 * 86400), until).second.size)
      history.setEnabled(true)
      history.awaitIdle()
      repeat(240) { history.documentSaved("scope", "content://synthetic/$it") }
      history.awaitIdle()
      val localWindow = DashboardWindow(until.minusSeconds(86400), Instant.now().plusSeconds(1))
      assertEquals(240, history.query("scope", localWindow).rows.size)
      assertTrue(history.query("other", localWindow).rows.isEmpty())
      lifetime.cancelAndJoin()
      lifetime = SupervisorJob()
      history = TailDHistory(context, CoroutineScope(lifetime + Dispatchers.Default))
      assertTrue(history.enabled.value)
      assertEquals(240, history.query("scope", localWindow).rows.size)
      history.deleteHistory()
      history.awaitIdle()
      assertTrue(history.query("scope", localWindow).rows.isEmpty())
      store.deleteHistory()
      store.import(slice)
      assertTrue(store.facts(binding, window.from, window.until).second.isEmpty())
    } finally {
      lifetime.cancelAndJoin()
      store.close()
      context.deleteDatabase("taild-dns.sqlite")
      context.deleteDatabase("taild-history.sqlite")
      context.getSharedPreferences("taild.analytics", 0).edit().clear().commit()
    }
  }
}
