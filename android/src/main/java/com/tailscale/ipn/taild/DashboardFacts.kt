// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import java.io.Writer
import java.time.Instant
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
import kotlinx.serialization.json.*

data class DashboardWindow(val from: Instant, val until: Instant) {
  init {
    require(from < until)
  }

  fun contains(at: Instant) = at >= from && at < until
}

internal fun activityMillisCeiling(at: Instant) =
    at.toEpochMilli() + if (at.nano % 1_000_000 == 0) 0 else 1

data class DashboardDnsFilter(
    val domain: String? = null,
    val decision: String? = null,
    val reason: String? = null,
    val day: String? = null,
    val country: String? = null,
    val asn: String? = null,
    val search: String = "",
    val bucketFrom: Instant? = null,
    val bucketUntil: Instant? = null,
) {
  fun matches(fact: ControlDDnsFact) =
      (domain == null || fact.question == domain) &&
          (decision == null || fact.decision == decision) &&
          (reason == null || fact.reason == reason) &&
          (day == null || dnsDay(fact) == day) &&
          (country == null || country in dnsCountries(fact)) &&
          (asn == null || asn in dnsAsns(fact)) &&
          fact.matches(search) &&
          (bucketFrom == null || fact.at >= bucketFrom) &&
          (bucketUntil == null || fact.at < bucketUntil)

  fun json() = buildJsonObject {
    domain?.let { put("domain", it) }
    decision?.let { put("decision", it) }
    reason?.let { put("reason", it) }
    day?.let { put("day_utc", it) }
    country?.let { put("answer_country", it) }
    asn?.let { put("answer_asn", it) }
    put("search", search)
    bucketFrom?.let { put("bucket_from_utc_inclusive", it.toString()) }
    bucketUntil?.let { put("bucket_until_utc_exclusive", it.toString()) }
  }
}

const val DNS_GEOGRAPHY_UNKNOWN = "Unknown / not provided"

private fun dnsDay(fact: ControlDDnsFact) = fact.at.atZone(ZoneOffset.UTC).toLocalDate().toString()

private fun geography(raw: String?, country: Boolean): Set<String> {
  val values =
      raw.orEmpty()
          .split(Regex("[;,\\s]+"))
          .map { it.trim().uppercase() }
          .filter(String::isNotEmpty)
          .map { if (!country) it.removePrefix("AS") else it }
          .filter {
            if (country) it.matches(Regex("[A-Z]{2}")) else it.matches(Regex("[0-9]{1,10}"))
          }
          .toSet()
  return values.ifEmpty { setOf(DNS_GEOGRAPHY_UNKNOWN) }
}

internal fun dnsCountries(fact: ControlDDnsFact) = geography(fact.raw["answerCountryCode"], true)

internal fun dnsAsns(fact: ControlDDnsFact) = geography(fact.raw["answerASN"], false)

private fun ranked(values: Sequence<String>): Map<String, Long> =
    values
        .groupingBy { it }
        .eachCount()
        .entries
        .sortedWith(compareByDescending<Map.Entry<String, Int>> { it.value }.thenBy { it.key })
        .associate { it.key to it.value.toLong() }

/** Immutable source revision/window: panels, drill-down and export share these exact facts. */
data class DashboardDnsSnapshot(
    val binding: ControlDBinding,
    val window: DashboardWindow,
    val revision: Long,
    val rows: List<ControlDStoredFact>,
) {
  init {
    require(
        rows.all { row ->
          window.contains(row.fact.at) &&
              row.fact.raw["endpointId"] == binding.endpoint &&
              (binding.client == null || row.fact.raw["clientId"] == binding.client)
        }
    )
  }

  val total = rows.size.toLong()

  val decisions = ranked(rows.asSequence().map { it.fact.decision })

  val domains = ranked(rows.asSequence().map { it.fact.question })

  val reasons = ranked(rows.asSequence().map { it.fact.reason })

  val countries = ranked(rows.asSequence().flatMap { dnsCountries(it.fact).asSequence() })

  val asns = ranked(rows.asSequence().flatMap { dnsAsns(it.fact).asSequence() })

  val countryCoverage = rows.count { DNS_GEOGRAPHY_UNKNOWN !in dnsCountries(it.fact) }.toLong()

  val asnCoverage = rows.count { DNS_GEOGRAPHY_UNKNOWN !in dnsAsns(it.fact) }.toLong()

  val days =
      rows.groupingBy { dnsDay(it.fact) }.eachCount().toSortedMap().mapValues { it.value.toLong() }

  val hourly = rows.groupingBy { it.fact.at.truncatedTo(ChronoUnit.HOURS) }.eachCount()

  fun filtered(filter: DashboardDnsFilter) = rows.filter { filter.matches(it.fact) }

  fun export(filter: DashboardDnsFilter, writer: Writer) {
    val matching = filtered(filter)
    val metadata = buildJsonObject {
      put("format", "TailD scoped DNS observations")
      put("schema", 1)
      put("source", "Control D DNS")
      put("history_revision", revision)
      put("binding", bindingToJson(binding))
      put("from_utc_inclusive", window.from.toString())
      put("until_utc_exclusive", window.until.toString())
      put("filter", filter.json())
      put("record_count", matching.size)
      put("coverage", "Returned/stored observations only; gaps remain unknown")
      put(
          "geography",
          "Provider answer geography; not client/app location. Country/ASN groups may overlap.",
      )
    }
    writer.append("{\"metadata\":").append(metadata.toString()).append(",\"records\":[")
    matching.forEachIndexed { index, row ->
      if (index > 0) writer.append(',')
      writer.append(
          buildJsonObject {
            put("occurrence", row.key)
            put(
                "provider",
                safeControlDJson(JsonObject(row.fact.raw.mapValues { JsonPrimitive(it.value) })),
            )
          }
              .toString()
      )
    }
    writer.append("]}")
  }
}

data class DashboardActivitySnapshot(
    val scope: String?,
    val window: DashboardWindow,
    val rows: List<RecordedActivity>,
) {
  init {
    require(rows.all { it.scope == scope && window.contains(Instant.ofEpochMilli(it.at)) })
  }

  // Content identity also remains truthful across process death and explicit deletion.
  val revision: String
    get() =
        cdDigest(
            buildString {
              append(scope)
              append(window.from)
              append(window.until)
              rows.forEach { append(activityJson(it)) }
            }
        )

  val kinds = ranked(rows.asSequence().map { it.event.kind })

  val taildrop = rows.filter { it.event.kind.startsWith("taildrop.") }

  fun filtered(kind: String?, search: String = "") = rows.filter {
    (kind == null || it.event.kind == kind) &&
        listOf(it.event.subject, it.event.detail, it.event.kind).any { value ->
          value.contains(search, true)
        }
  }

  fun export(kind: String?, search: String, writer: Writer) {
    val matching = filtered(kind, search)
    val metadata = buildJsonObject {
      put("format", "TailD scoped local observations")
      put("schema", 1)
      put("source", "Observed Tailscale / TailDrop")
      put("history_revision", revision)
      put("scope", scope?.let(::JsonPrimitive) ?: JsonNull)
      put("from_utc_inclusive", window.from.toString())
      put("until_utc_exclusive", window.until.toString())
      put("kind", kind?.let(::JsonPrimitive) ?: JsonNull)
      put("search", search)
      put("record_count", matching.size)
      put("coverage", "Local observations only; unseen events remain unknown")
    }
    writer.append("{\"metadata\":").append(metadata.toString()).append(",\"records\":[")
    matching.forEachIndexed { index, row ->
      if (index > 0) writer.append(',')
      writer.append(activityJson(row).toString())
    }
    writer.append("]}")
  }
}

private fun activityJson(row: RecordedActivity) = buildJsonObject {
  put("id", row.id)
  put("at_utc", Instant.ofEpochMilli(row.at).toString())
  put("kind", row.event.kind)
  put("subject", row.event.subject)
  put("detail", row.event.detail)
  put("identity", row.event.identity)
}
