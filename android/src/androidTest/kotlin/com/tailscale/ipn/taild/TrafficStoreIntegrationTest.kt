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
  fun diagnosisTablesKeepMeasuredBytesAndDnsCountsDistinct() {
    val owner = JSONObject().put("uid", 10123).put("label", "Fixture").put("packages", JSONArray())
    val resolver =
        JSONObject().put("uid", 1000).put("label", "Resolver").put("packages", JSONArray())
    fun observation(
        bytes: Long,
        upload: Boolean,
        address: String,
        dns: JSONObject? = null,
        context: Boolean = false,
    ): TrafficRow {
      val fact =
          JSONObject()
              .put("identity", if (context) resolver else owner)
              .put("uid", if (context) 1000 else 10123)
              .put("upload", upload)
              .put("remote", address)
              .put("remotePort", if (dns == null) 443 else 53)
              .put("protocol", if (dns == null) 6 else 17)
      if (dns != null) fact.put("dns", dns.put("queryIdentity", owner))
      else
          fact.put(
              "candidates",
              JSONArray()
                  .put(JSONObject().put("name", "alpha.test"))
                  .put(JSONObject().put("name", "beta.test")),
          )
      return TrafficRow(3600001, 3600001, bytes, 1, fact.toString(), 3600001, 3600001)
    }
    fun dns(name: String, response: Boolean, blocked: Boolean = false) =
        JSONObject().put("name", name).put("response", response).put("blocked", blocked)
    val rows =
        listOf(
            observation(100, true, "203.0.113.1"),
            observation(400, false, "203.0.113.1"),
            observation(60, true, "100.100.100.100", dns("alpha.test", false)),
            observation(70, true, "100.100.100.100", dns("beta.test", false)),
            observation(
                90,
                false,
                "100.100.100.100",
                dns("alpha.test", true, true),
                context = true,
            ),
            observation(80, false, "100.100.100.100", dns("beta.test", true)),
        )
    val entry = FirewallTrafficApp("fixture", "Fixture", null, setOf(owner.toString()), 230, 480)
    val destinations = firewallDestinations(entry, rows)
    assertEquals(listOf(500L, 210L), destinations.map { it.total })
    assertEquals(230L, destinations.sumOf { it.sent })
    assertEquals(480L, destinations.sumOf { it.received })
    assertEquals(listOf("alpha.test", "beta.test"), destinations.first().candidates)
    val names = firewallDnsNames(rows)
    assertEquals(listOf("alpha.test", "beta.test"), names.map { it.name })
    assertEquals(listOf(1L, 1L), names.map { it.questions })
    assertEquals(listOf(1L, 1L), names.map { it.replies })
    assertEquals(listOf(1L, 0L), names.map { it.blocked })
    val owned = rows.filter { it.uid == 10123 }
    val data = TrafficSnapshot(1, 86400001, 1, rows, 0, "fixture", "[]")
    assertEquals(480L, hourlyTraffic(owned.filter { !it.upload }, data).sumOf { it.second })
    assertEquals(230L, hourlyTraffic(owned.filter { it.upload }, data).sumOf { it.second })
  }

  @Test
  fun firewallTotalsSortHourlyAndInstallationOwnership() {
    val one = AppAccessPackage("test.one", "Zeta", listOf("cert"), 1, 2, 3)
    val app = AppAccessIdentity(10123, listOf(one))
    fun identity(value: AppAccessIdentity) =
        JSONObject()
            .put("uid", value.uid)
            .put("label", value.packages.joinToString(" / ") { it.label })
            .put(
                "packages",
                JSONArray(
                    value.packages.map { pkg ->
                      JSONObject()
                          .put("package", pkg.name)
                          .put("versionCode", pkg.version)
                          .put("firstInstallTime", pkg.installed)
                          .put("lastUpdateTime", pkg.updated)
                          .put("signerSha256", JSONArray(pkg.signers))
                    }
                ),
            )
    fun row(
        owner: JSONObject,
        bytes: Long,
        sent: Boolean,
        at: Long,
        query: JSONObject? = null,
    ): TrafficRow {
      val fact =
          JSONObject().put("identity", owner).put("uid", owner.getInt("uid")).put("upload", sent)
      if (query != null)
          fact.put("dns", JSONObject().put("queryIdentity", query).put("blocked", true))
      return TrafficRow(at, at, bytes, 1, fact.toString(), at, at)
    }
    val other = AppAccessIdentity(10124, listOf(one.copy(name = "test.two", label = "Alpha")))
    val stale = identity(app.copy(packages = listOf(one.copy(version = 2))))
    val rows =
        listOf(
            row(identity(app), 300, true, 3600000),
            row(identity(app), 200, false, 7200000),
            row(identity(other), 500, false, 3600000),
            row(stale, 900, true, 3600000),
            row(
                JSONObject()
                    .put("uid", 1000)
                    .put("label", "System UID 1000")
                    .put("packages", JSONArray()),
                1000,
                false,
                7200000,
                identity(app),
            ),
        )
    val data = TrafficSnapshot(1, 86400001, 1, rows, 0, "fixture", "[]")
    val result = firewallTrafficApps(listOf(app, other), data)
    assertEquals(listOf("System UID 1000", "Zeta", "Alpha", "Zeta"), result.map { it.label })
    val current = result.single { it.current == app }
    assertEquals(300L, current.sent)
    assertEquals(200L, current.received)
    assertEquals(500L, current.hourly.sumOf { it.second })
    assertEquals(300L, current.hourly.single { it.first == 3600000L }.second)
    assertFalse(trafficIdentityMatches(stale, app))
    assertEquals(rows.sumOf { it.bytes }, result.sumOf { it.total })
  }

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
