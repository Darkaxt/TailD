package com.tailscale.ipn.taild

import java.io.StringWriter
import java.time.Instant
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class DashboardFactsTest {
  private val until = Instant.parse("2026-10-20T12:00:00Z")
  private val window = DashboardWindow(until.minusSeconds(7 * 86400), until)
  private val binding = ControlDBinding("account", null, "endpoint", "client")

  private fun fact(
      index: Int,
      action: String = "0",
      country: String = "US",
      asn: String = "AS64500",
  ) =
      ControlDStoredFact(
          index.toString(),
          ControlDDnsFact(
              mapOf(
                  "timestamp" to until.minusSeconds(index.toLong() + 1).toString(),
                  "endpointId" to "endpoint",
                  "clientId" to "client",
                  "question" to "example.invalid",
                  "rrType" to "A",
                  "action" to action,
                  "answerCountryCode" to country,
                  "answerASN" to asn,
                  "providerFutureField" to "preserved",
              )
          ),
      )

  @Test
  fun allRetainedCountsAndExactDrilldownExportShareOneSnapshot() {
    val snapshot =
        DashboardDnsSnapshot(
            binding,
            window,
            42,
            (0..236).map { fact(it, if (it % 3 == 0) "1" else "0") },
        )
    assertEquals(237L, snapshot.total)
    assertEquals(snapshot.total, snapshot.decisions.values.sum())
    assertEquals(snapshot.total, snapshot.domains.values.sum())
    assertEquals(snapshot.total, snapshot.days.values.sum())
    val filter = DashboardDnsFilter(decision = "Blocked", country = "US", search = "blocked")
    val selected = snapshot.filtered(filter)
    assertTrue(selected.size > 100)
    val output = StringWriter().also { snapshot.export(filter, it) }.toString()
    val parsed = Json.parseToJsonElement(output).jsonObject
    assertEquals(
        selected.size,
        parsed.getValue("metadata").jsonObject.getValue("record_count").jsonPrimitive.int,
    )
    assertEquals(
        42L,
        parsed.getValue("metadata").jsonObject.getValue("history_revision").jsonPrimitive.long,
    )
    assertEquals(
        selected.map { it.key },
        parsed.getValue("records").jsonArray.map {
          it.jsonObject.getValue("occurrence").jsonPrimitive.content
        },
    )
    assertTrue(output.contains("providerFutureField"))
  }

  @Test
  fun geographyCoverageUnknownDecisionsAndOverlappingCountriesAreExplicit() {
    val snapshot =
        DashboardDnsSnapshot(
            binding,
            window,
            1,
            listOf(fact(0, "999", "", ""), fact(1, "0", "US;DE;US", "64500;AS64501")),
        )
    assertEquals(1L, snapshot.countryCoverage)
    assertEquals(1L, snapshot.asnCoverage)
    assertEquals(1L, snapshot.decisions["Unknown"])
    assertEquals(1L, snapshot.countries[DNS_GEOGRAPHY_UNKNOWN])
    assertEquals(1, snapshot.filtered(DashboardDnsFilter(country = "DE")).size)
    assertEquals(1, snapshot.filtered(DashboardDnsFilter(asn = "64501")).size)
    assertEquals(3L, snapshot.countries.values.sum())
  }

  @Test
  fun crossScopeAndOutOfWindowFactsCannotBeExportedAsSelectedScope() {
    assertThrows(IllegalArgumentException::class.java) {
      DashboardDnsSnapshot(binding.copy(client = "other"), window, 1, listOf(fact(0)))
    }
    assertThrows(IllegalArgumentException::class.java) {
      DashboardDnsSnapshot(binding, window, 1, listOf(fact(9 * 86400)))
    }
  }

  @Test
  fun localReceiptAndDocumentSaveRemainDistinctAndRevisionTracksDeletion() {
    val rows =
        listOf("taildrop.received", "taildrop.saved", "coverage").mapIndexed { index, kind ->
          RecordedActivity(
              index.toLong(),
              until.minusSeconds(1).toEpochMilli(),
              "scope",
              ActivityEvent(kind, "Transfer", "Observed"),
          )
        }
    val snapshot = DashboardActivitySnapshot("scope", window, rows)
    assertEquals(2, snapshot.taildrop.size)
    assertEquals(1, snapshot.filtered("taildrop.saved").size)
    val output = StringWriter().also { snapshot.export("taildrop.received", "", it) }.toString()
    assertEquals(1, Json.parseToJsonElement(output).jsonObject.getValue("records").jsonArray.size)
    assertNotEquals(snapshot.revision, snapshot.copy(rows = emptyList()).revision)
  }
}
