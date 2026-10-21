// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import java.io.IOException
import java.net.IDN
import java.security.MessageDigest
import java.time.Instant
import java.time.OffsetDateTime
import kotlinx.serialization.json.*

class ControlDFailure(
    val state: String,
    message: String,
    val status: Int? = null,
    val retryAfter: String? = null,
) : IOException(message)

internal fun cdRequire(
    value: Boolean,
    message: String = "Control D returned an unsupported response",
) {
  if (!value) throw ControlDFailure("incompatible", message)
}

internal fun JsonObject.text(key: String): String? = (get(key) as? JsonPrimitive)?.contentOrNull

internal fun JsonObject.number(key: String): Int? = (get(key) as? JsonPrimitive)?.intOrNull

internal fun JsonObject.objectAt(key: String): JsonObject? = get(key) as? JsonObject

internal fun cdIdentifier(value: String): String {
  cdRequire(Regex("[A-Za-z0-9_-]{1,128}").matches(value), "Invalid provider object identity")
  return value
}

internal fun cdClientIdentifier(value: String): String {
  cdRequire(
      value.length in 1..256 && value.none { it.code < 32 || it.code == 127 },
      "Invalid provider client identity",
  )
  return value
}

internal fun cdDigest(value: String): String =
    MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8)).joinToString(
        ""
    ) {
      "%02x".format(it)
    }

internal fun canonicalCd(value: JsonElement): String =
    when (value) {
      is JsonObject ->
          value.toSortedMap().entries.joinToString(",", "{", "}") {
            JsonPrimitive(it.key).toString() + ":" + canonicalCd(it.value)
          }
      is JsonArray -> value.joinToString(",", "[", "]") { canonicalCd(it) }
      else -> value.toString()
    }

internal fun safeControlDJson(value: JsonElement, depth: Int = 0): JsonElement {
  cdRequire(depth <= 24, "Provider data exceeds the nesting budget")
  return when (value) {
    is JsonObject ->
        JsonObject(
            value
                .filterKeys {
                  it.lowercase().replace("_", "").replace("-", "") !in
                      setOf(
                          "token",
                          "apitoken",
                          "apikey",
                          "authorization",
                          "password",
                          "secret",
                          "credentials",
                          "credential",
                      )
                }
                .mapValues { safeControlDJson(it.value, depth + 1) }
        )
    is JsonArray -> {
      cdRequire(value.size <= 10000, "Provider collection exceeds the resource budget")
      JsonArray(value.map { safeControlDJson(it, depth + 1) })
    }
    else -> value
  }
}

data class ControlDBinding(
    val account: String,
    val organization: String?,
    val endpoint: String,
    val client: String?,
) {
  val scope: String
    get() =
        cdDigest(
            JsonArray(
                    listOf(account, organization.orEmpty(), endpoint, client.orEmpty())
                        .map(::JsonPrimitive)
                )
                .toString()
        )
}

data class ControlDClient(val id: String, val name: String)

data class ControlDEndpoint(
    val id: String,
    val name: String,
    val profile: String,
    val secondaryProfile: String?,
    val clients: List<ControlDClient>?,
    val deviceId: String = id,
)

data class ControlDInventory(
    val account: String,
    val organization: String?,
    val region: String?,
    val endpoints: List<ControlDEndpoint>,
    val profiles: Map<String, String>,
)

data class ControlDResource(
    val state: String,
    val records: JsonElement = JsonNull,
    val message: String? = null,
) {
  fun objects(): List<JsonObject> {
    if (state != "available")
        throw ControlDFailure(state, message ?: "This policy category is unavailable")
    val rows =
        records as? JsonArray
            ?: throw ControlDFailure("incompatible", "Unsupported policy category schema")
    cdRequire(rows.all { it is JsonObject })
    return rows.map { it.jsonObject }
  }
}

data class ControlDPolicy(
    val binding: ControlDBinding,
    val profile: String,
    val profileName: String,
    val affectedNames: List<String>,
    val resources: Map<String, ControlDResource>,
    val affectedIds: List<String> = affectedNames,
) {
  val fingerprint: String
    get() =
        cdDigest(
            buildJsonObject {
                  put("scope", binding.scope)
                  put("profile", profile)
                  put("affected", JsonArray(affectedIds.sorted().map(::JsonPrimitive)))
                  put(
                      "policy",
                      buildJsonObject {
                        resources.toSortedMap().forEach { (name, resource) ->
                          put(
                              name,
                              buildJsonObject {
                                put("state", resource.state)
                                put("records", resource.records)
                              },
                          )
                        }
                      },
                  )
                }
                .let(::canonicalCd)
        )

  fun rows(kind: String) =
      resources[kind]?.objects()
          ?: throw ControlDFailure("unavailable", "Policy category unavailable")
}

fun checkControlDIntent(
    displayed: ControlDPolicy,
    fresh: ControlDPolicy,
    eventProfile: String? = null,
) {
  if (fresh.resources.values.any { it.state != "available" })
      throw ControlDFailure(
          "unavailable",
          "Current policy could not be fully verified. Reload policy before changing it.",
      )
  if (
      displayed.binding != fresh.binding ||
          displayed.profile != fresh.profile ||
          displayed.fingerprint != fresh.fingerprint ||
          (eventProfile != null && eventProfile != fresh.profile)
  ) {
    throw ControlDFailure(
        "conflict",
        "Policy or endpoint binding changed. Reload policy before making a new change.",
    )
  }
}

sealed interface ControlDChange {
  data class Rule(
      val hostname: String,
      val action: Int,
      val enabled: Boolean,
      val comment: String,
      val delete: Boolean = false,
  ) : ControlDChange

  data class Filter(val id: String, val enabled: Boolean) : ControlDChange

  data class Service(val id: String, val action: Int, val enabled: Boolean) : ControlDChange

  data class Option(val id: String, val enabled: Boolean, val value: String? = null) :
      ControlDChange
}

data class ControlDMutation(
    val method: String,
    val route: String,
    val form: Map<String, List<String>>,
    val expectedGroup: JsonElement? = null,
)

internal fun cdHostname(value: String): String {
  val name = value.trim().trimEnd('.').lowercase()
  cdRequire(
      name.length in 1..253 && !name.any { it.isWhitespace() || it in "/:%?@\\#" },
      "Enter a DNS hostname, not a URL",
  )
  val prefix = if (name.startsWith("*.")) "*." else ""
  val ascii = runCatching {
    IDN.toASCII(name.removePrefix(prefix))
  }
      .getOrElse { throw ControlDFailure("incompatible", "Invalid DNS hostname") }
  cdRequire(
      Regex(
              "[a-zA-Z0-9](?:[a-zA-Z0-9_-]*[a-zA-Z0-9])?(?:\\.[a-zA-Z0-9](?:[a-zA-Z0-9_-]*[a-zA-Z0-9])?)*"
          )
          .matches(ascii),
      "Invalid DNS hostname",
  )
  return prefix + ascii.lowercase()
}

fun controlDMutation(policy: ControlDPolicy, change: ControlDChange): ControlDMutation {
  val root = "/profiles/" + cdIdentifier(policy.profile)
  fun enabled(value: Boolean) = listOf(if (value) "1" else "0")
  return when (change) {
    is ControlDChange.Rule -> {
      val host = cdHostname(change.hostname)
      val existing = policy.rows("rules").singleOrNull { it.text("PK") == host }
      if (change.delete) {
        cdRequire(existing != null, "The rule no longer exists")
        cdRequire(
            existing?.objectAt("action")?.number("do") in 0..1,
            "The existing rule uses an unsupported action and is read only here",
        )
        ControlDMutation("DELETE", "$root/rules/$host", emptyMap())
      } else {
        cdRequire(
            change.action in 0..1,
            "Spoof/Redirect editing is unsupported; the existing rule is unchanged",
        )
        cdRequire(
            existing == null || existing.objectAt("action")?.number("do") in 0..1,
            "The existing rule uses an unsupported action and cannot be replaced here",
        )
        cdRequire(
            change.comment.length <= 64 && change.comment.none { it.code < 32 },
            "Comments must be at most 64 characters",
        )
        val group = existing?.get("group")?.takeUnless { it == JsonNull }
        val form =
            mutableMapOf(
                "hostnames[]" to listOf(host),
                "do" to listOf(change.action.toString()),
                "status" to enabled(change.enabled),
                "comment" to listOf(change.comment),
            )
        group?.let {
          cdRequire(it is JsonPrimitive)
          form["group"] = listOf(it.jsonPrimitive.content)
        }
        ControlDMutation(if (existing == null) "POST" else "PUT", "$root/rules", form, group)
      }
    }
    is ControlDChange.Filter -> {
      val id = cdIdentifier(change.id)
      cdRequire(
          policy.rows("filters").any {
            it.text("PK") == id ||
                (it["levels"] as? JsonArray).orEmpty().any { level ->
                  (level as? JsonObject)?.text("name") == id
                }
          },
          "Filter is not in the current policy",
      )
      ControlDMutation(
          "PUT",
          "$root/filters/filter/$id",
          mapOf("status" to enabled(change.enabled)),
      )
    }
    is ControlDChange.Service -> {
      val id = cdIdentifier(change.id)
      val existing = policy.rows("services").singleOrNull { it.text("PK") == id }
      cdRequire(
          change.action in 0..1 && existing?.objectAt("action")?.number("do") in 0..1,
          "Unsupported service action",
      )
      ControlDMutation(
          "PUT",
          "$root/services/$id",
          mapOf("status" to enabled(change.enabled), "do" to listOf(change.action.toString())),
      )
    }
    is ControlDChange.Option -> {
      val id = cdIdentifier(change.id)
      val option = policy.rows("options").singleOrNull { it.text("PK") == id }
      cdRequire(
          option?.text("type") == "toggle",
          "Only supported simple toggle options can be edited",
      )
      cdRequire(
          change.value == null || change.value in listOf("0", "1"),
          "Unsupported option value",
      )
      ControlDMutation("PUT", "$root/options/$id", mapOf("status" to enabled(change.enabled)))
    }
  }
}

fun controlDChangeVerified(
    policy: ControlDPolicy,
    change: ControlDChange,
    mutation: ControlDMutation,
): Boolean =
    when (change) {
      is ControlDChange.Rule ->
          policy
              .rows("rules")
              .singleOrNull { it.text("PK") == cdHostname(change.hostname) }
              .let { row ->
                if (change.delete) row == null
                else
                    row != null &&
                        row.objectAt("action")?.number("do") == change.action &&
                        row.objectAt("action")?.number("status") ==
                            (if (change.enabled) 1 else 0) &&
                        row.text("comment").orEmpty() == change.comment &&
                        (mutation.expectedGroup == null || row["group"] == mutation.expectedGroup)
              }
      is ControlDChange.Filter ->
          policy
              .rows("filters")
              .singleOrNull {
                it.text("PK") == change.id ||
                    (it["levels"] as? JsonArray).orEmpty().any { level ->
                      (level as? JsonObject)?.text("name") == change.id
                    }
              }
              .let { row ->
                row != null &&
                    row.number("status") == (if (change.enabled) 1 else 0) &&
                    (!change.enabled ||
                        (row.objectAt("action")?.text("lvl") ?: row.text("PK")) == change.id)
              }
      is ControlDChange.Service ->
          policy
              .rows("services")
              .singleOrNull { it.text("PK") == change.id }
              ?.objectAt("action")
              .let {
                it?.number("do") == change.action &&
                    it?.number("status") == (if (change.enabled) 1 else 0)
              }
      is ControlDChange.Option ->
          policy
              .rows("options")
              .singleOrNull { it.text("PK") == change.id }
              .let { row ->
                row != null &&
                    (row.text("value") == (if (change.enabled) "1" else "0") ||
                        (!change.enabled && row["configured"] == JsonPrimitive(false)))
              }
    }

data class ControlDDnsFact(val raw: Map<String, String>) {
  val at: Instant
    get() = cdInstant(raw.getValue("timestamp"))

  val question: String
    get() = raw.getValue("question").trimEnd('.').lowercase()

  val type: String
    get() = raw["rrType"]?.takeIf(String::isNotBlank) ?: "Unknown"

  val profile: String?
    get() = raw["profileId"]?.takeIf(String::isNotBlank)

  val action: Int?
    get() = raw["action"]?.toIntOrNull()

  val decision: String
    get() =
        when (action) {
          0 -> "Blocked"
          1 -> "Allowed"
          2 -> "Spoofed"
          3 -> "Redirected"
          else -> "Unknown"
        }

  val reason: String
    get() =
        listOfNotNull(
                raw["trigger"]?.takeIf(String::isNotBlank),
                raw["triggerValue"]?.takeIf(String::isNotBlank),
            )
            .joinToString(" · ")
            .ifBlank { "Reason unavailable" }

  val identity: String
    get() = cdDigest(canonicalCd(JsonObject(raw.mapValues { JsonPrimitive(it.value) })))

  fun matches(search: String) =
      listOf(
              question,
              type,
              decision,
              reason,
              when (action) {
                0 -> "block blocked"
                1 -> "allow allowed bypass"
                2 -> "spoof"
                3 -> "redirect"
                else -> "unknown"
              },
          )
          .any { it.contains(search, ignoreCase = true) }
}

data class ControlDDnsSlice(
    val binding: ControlDBinding,
    val from: Instant,
    val until: Instant,
    val facts: List<ControlDDnsFact>,
    val truncated: Boolean,
)

internal fun cdInstant(value: String): Instant =
    try {
      val parsed = OffsetDateTime.parse(value)
      cdRequire(parsed.offset.totalSeconds == 0, "Provider timestamp is not UTC")
      parsed.toInstant()
    } catch (_: java.time.DateTimeException) {
      throw ControlDFailure("incompatible", "Invalid provider UTC timestamp")
    }

/** Strict RFC4180 parsing, with bounded input supplied by the network reader. */
fun parseControlDCsv(
    text: String,
    binding: ControlDBinding,
    from: Instant,
    until: Instant,
    limit: Int = 50_000,
): ControlDDnsSlice {
  cdRequire(from < until && limit > 0)
  val rows =
      sequence<List<String>> {
            val fields = mutableListOf<String>()
            val cell = StringBuilder()
            var quoted = false
            var closed = false
            var offset = 0
            val input = text.removePrefix("\uFEFF")
            while (offset < input.length) {
              val c = input[offset++]
              if (quoted) {
                if (c == '"') {
                  if (offset < input.length && input[offset] == '"') {
                    cell.append('"')
                    offset++
                  } else {
                    quoted = false
                    closed = true
                  }
                } else cell.append(c)
              } else
                  when (c) {
                    '"' -> {
                      cdRequire(cell.isEmpty() && !closed, "Invalid CSV quoting")
                      quoted = true
                    }
                    ',' -> {
                      fields += cell.toString()
                      cell.setLength(0)
                      closed = false
                    }
                    '\r',
                    '\n' -> {
                      if (c == '\r' && offset < input.length && input[offset] == '\n') offset++
                      fields += cell.toString()
                      yield(fields.toList())
                      fields.clear()
                      cell.setLength(0)
                      closed = false
                    }
                    else -> {
                      cdRequire(!closed, "Invalid CSV trailing data")
                      cell.append(c)
                    }
                  }
              cdRequire(
                  cell.length <= 8192 && fields.size <= 128,
                  "DNS record exceeds the resource budget",
              )
            }
            cdRequire(!quoted, "Incomplete CSV record")
            if (cell.isNotEmpty() || fields.isNotEmpty() || closed) {
              fields += cell.toString()
              yield(fields.toList())
            }
          }
          .iterator()
  cdRequire(rows.hasNext(), "Empty provider CSV response")
  val header = rows.next()
  cdRequire(
      header.size == header.toSet().size &&
          header.containsAll(listOf("timestamp", "endpointId", "question", "action")),
      "Unsupported provider CSV columns",
  )
  if (binding.client != null)
      cdRequire("clientId" in header, "Provider did not return client identity")
  val facts = mutableListOf<ControlDDnsFact>()
  var count = 0
  var truncated = false
  while (rows.hasNext()) {
    val values = rows.next()
    cdRequire(values.size == header.size, "Invalid provider CSV row")
    val raw =
        header.zip(values).toMap().filterKeys {
          it.lowercase().replace("_", "").replace("-", "") !in
              setOf(
                  "token",
                  "apitoken",
                  "apikey",
                  "authorization",
                  "password",
                  "secret",
                  "credentials",
                  "credential",
              )
        }
    cdRequire(raw["endpointId"] == binding.endpoint, "Provider returned a different endpoint")
    val fact = ControlDDnsFact(raw)
    // CSV transport uses whole-second bounds. Keep that envelope separate from
    // exact local ownership; fractional catch-up windows must not fail or overlap.
    val envelopeFrom = from.truncatedTo(java.time.temporal.ChronoUnit.SECONDS)
    val envelopeUntil =
        until.truncatedTo(java.time.temporal.ChronoUnit.SECONDS).let {
          if (it == until) it else it.plusSeconds(1)
        }
    cdRequire(
        fact.at >= envelopeFrom && fact.at <= envelopeUntil && fact.question.length in 1..4096,
        "Provider record is outside the requested scope",
    )
    count++
    if (count > limit) {
      truncated = true
      break
    }
    if (
        fact.at >= from &&
            fact.at < until &&
            (binding.client == null || raw["clientId"] == binding.client)
    )
        facts += fact
  }
  return ControlDDnsSlice(binding, from, until, facts, truncated)
}
