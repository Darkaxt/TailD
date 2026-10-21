package com.tailscale.ipn.taild

import android.os.Build
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Storage edge contracts supplement the real VPN fixture; they do not replace it. */
class TrafficStoreIntegrationTest {
  @Test
  fun dedupFrozenWindowsRetentionAndDeletedEpoch() {
    assumeTrue(Build.HARDWARE in listOf("ranchu", "goldfish"))
    val context =
        InstrumentationRegistry.getInstrumentation()
            .targetContext
            .createDeviceProtectedStorageContext()
    context.deleteDatabase("taild-traffic.sqlite")
    val base = (System.currentTimeMillis() / 60000 - 2) * 60000
    fun batch(sequence: Int, at: Long, bytes: Long) =
        JSONObject()
            .put("session", "storage-fixture")
            .put("sequence", sequence)
            .put("dropped", 3)
            .put("unacknowledged", 2)
            .put(
                "facts",
                JSONArray()
                    .put(
                        JSONObject()
                            .put("at", at)
                            .put("bytes", bytes)
                            .put("packets", 1)
                            .put(
                                "scope",
                                JSONObject().put("id", "fixture-scope").put("configuration", "{}"),
                            )
                            .put("upload", true)
                            .put("protocol", 6)
                            .put("local", "100.64.0.2")
                            .put("remote", "203.0.113.1")
                            .put("localPort", 1234)
                            .put("remotePort", 443)
                            .put("uid", -1)
                            .put("lookupAt", at)
                            .put("candidateCoverage", "fixture observed DNS")
                            .put(
                                "candidates",
                                JSONArray()
                                    .put(JSONObject().put("name", "alpha.test"))
                                    .put(JSONObject().put("name", "beta.test")),
                            )
                    ),
            )
    TrafficStore(context).use { store ->
      assertTrue(store.commit(batch(1, base + 100, 101), "storage-fixture"))
      assertTrue(store.commit(batch(1, base + 100, 101), "storage-fixture"))
      assertTrue(store.commit(batch(2, base + 900, 100), "storage-fixture"))
      val frozen = store.snapshot(base, base + 1000)
      assertEquals(201L, frozen.sent)
      assertEquals(2L, frozen.rows.single().packets)
      val serialized = frozen.export()
      val partial = store.snapshot(base + 500, base + 1000)
      assertTrue(partial.rows.isEmpty())
      assertEquals(201L, partial.boundaryBytes)
      assertTrue(store.commit(batch(3, base + 1100, 99), "storage-fixture"))
      assertEquals(serialized, frozen.export())
      val estimates =
          JSONObject(serialized)
              .getJSONArray("facts")
              .getJSONObject(0)
              .getJSONArray("equalWeightEstimates")
      assertEquals("201", estimates.getJSONObject(0).getString("byteNumerator"))
      assertEquals("2", estimates.getJSONObject(0).getString("byteDenominator"))
      assertEquals(300L, store.snapshot(base, base + 2000).sent)
      store.finish(
          JSONObject()
              .put("session", "storage-fixture")
              .put("dropped", 5)
              .put("unacknowledged", 4)
              .toString()
      )
      assertEquals(
          5L,
          JSONArray(store.snapshot(base, base + 2000).sessions)
              .getJSONObject(0)
              .getLong("droppedMetadataRecords"),
      )
      assertTrue(
          store.commit(batch(4, base - TailDHistory.RETENTION_MILLIS - 1, 17), "storage-fixture")
      )
      assertTrue(store.snapshot(base, base + 2000).coverage.contains("17 bytes removed"))
      store.clear()
      assertFalse(store.commit(batch(5, base + 1200, 11), "new-epoch"))
      assertTrue(store.snapshot(base, base + 2000).rows.isEmpty())
      // SQLite text length counts characters; the storage budget is UTF-8 bytes.
      val oversized = batch(1, base + 1300, 11).put("session", "capacity-fixture")
      oversized
          .getJSONArray("facts")
          .getJSONObject(0)
          .getJSONObject("scope")
          .put("configuration", "\u20ac".repeat(9 * 1024 * 1024))
      assertTrue(store.commit(oversized, "capacity-fixture"))
      val capped = store.snapshot(base, base + 2000)
      assertTrue(capped.rows.isEmpty())
      assertTrue(capped.coverage.contains("11 bytes removed"))
      store.clear()
    }
  }
}
