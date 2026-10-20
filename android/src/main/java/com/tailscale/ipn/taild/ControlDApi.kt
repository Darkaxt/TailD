// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.URL
import java.net.URLEncoder
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.time.Instant
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.*
import kotlinx.serialization.json.*
import okhttp3.*

/**
 * Fixed provider origins, bounded authenticated reads, no redirects/retries or invented deadlines.
 */
class ControlDApi(client: OkHttpClient = OkHttpClient()) {
  private class Exchange {
    val sent = AtomicBoolean()
  }

  private val client =
      client
          .newBuilder()
          .cache(null)
          .followRedirects(false)
          .followSslRedirects(false)
          .retryOnConnectionFailure(false)
          .connectTimeout(0, TimeUnit.MILLISECONDS)
          .readTimeout(0, TimeUnit.MILLISECONDS)
          .writeTimeout(0, TimeUnit.MILLISECONDS)
          .callTimeout(0, TimeUnit.MILLISECONDS)
          .addNetworkInterceptor { chain ->
            // OkHttp 4 also follows a 503/Retry-After:0 independently of its
            // connection-retry flag. Reject a second exchange before it sends bytes.
            val exchange =
                chain.request().tag(Exchange::class.java)
                    ?: throw IOException("Missing request identity")
            if (!exchange.sent.compareAndSet(false, true))
                throw IOException("Repeat provider exchange refused")
            chain.proceed(chain.request())
          }
          .build()
  private val json = Json { ignoreUnknownKeys = true }

  private suspend fun request(
      url: URL,
      token: String,
      organization: String?,
      method: String = "GET",
      form: Map<String, List<String>> = emptyMap(),
      csv: Boolean = false,
  ): String = suspendCancellableCoroutine { continuation ->
    try {
      ControlDCredentials.validate(token)
      organization?.let(::cdIdentifier)
      cdRequire(
          url.protocol == "https" &&
              (url.host == "api.controld.com" ||
                  Regex("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.analytics\\.controld\\.com")
                      .matches(url.host)),
          "Invalid provider destination",
      )
      val builder =
          Request.Builder()
              .url(url.toString())
              .tag(Exchange::class.java, Exchange())
              .header("Authorization", "Bearer " + token.trim())
              .header("User-Agent", "TailD-Android")
              .header("Cache-Control", "no-cache, no-store")
      organization?.let { builder.header("X-Force-Org-Id", it) }
      if (method != "GET") {
        val body =
            FormBody.Builder()
                .apply { form.forEach { (key, values) -> values.forEach { add(key, it) } } }
                .build()
        builder.method(
            method,
            object : RequestBody() {
              override fun contentType() = body.contentType()

              override fun contentLength() = body.contentLength()

              override fun isOneShot() = true

              override fun writeTo(sink: okio.BufferedSink) = body.writeTo(sink)
            },
        )
      }
      val call = client.newCall(builder.build())
      continuation.invokeOnCancellation { call.cancel() }
      call.enqueue(
          object : Callback {
            override fun onFailure(call: Call, error: IOException) {
              if (continuation.isActive)
                  continuation.resumeWithException(
                      ControlDFailure(
                          if (method == "GET") "unavailable" else "outcome-unknown",
                          if (method == "GET") "Control D read failed. Refresh to try a new read."
                          else
                              "Change outcome is unknown. Reconcile policy; the write will not be retried.",
                      )
                  )
            }

            override fun onResponse(call: Call, response: Response) {
              try {
                response.use {
                  val code = response.code
                  if (code !in 200..299) {
                    val state =
                        when (code) {
                          401,
                          403 -> "denied"
                          429 -> "rate-limited"
                          in 300..399 -> "redirect-refused"
                          404,
                          405 -> "unavailable"
                          else -> "unavailable"
                        }
                    val retry =
                        response.header("Retry-After")?.let { value ->
                          if (Regex("[0-9]{1,10}").matches(value)) value
                          else
                              runCatching {
                                java.time.ZonedDateTime.parse(
                                        value,
                                        java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME,
                                    )
                                    .toInstant()
                                    .toString()
                              }
                                  .getOrNull()
                        }
                    throw ControlDFailure(
                        state,
                        "Control D request was rejected (HTTP $code)",
                        code,
                        retry,
                    )
                  }
                  val budget = if (csv) 16 * 1024 * 1024 else 4 * 1024 * 1024
                  val bytes =
                      (response.body
                              ?: throw ControlDFailure("incompatible", "Empty provider response"))
                          .byteStream()
                          .use { input ->
                            val output = ByteArrayOutputStream()
                            val buffer = ByteArray(8192)
                            while (output.size() <= budget) {
                              val read =
                                  input.read(
                                      buffer,
                                      0,
                                      minOf(buffer.size, budget + 1 - output.size()),
                                  )
                              if (read < 0) break
                              output.write(buffer, 0, read)
                            }
                            output.toByteArray()
                          }
                  if (bytes.size > budget)
                      throw ControlDFailure(
                          "incomplete",
                          "Provider response exceeds the local resource budget. Existing history is preserved.",
                      )
                  val text =
                      Charsets.UTF_8.newDecoder()
                          .onMalformedInput(CodingErrorAction.REPORT)
                          .onUnmappableCharacter(CodingErrorAction.REPORT)
                          .decode(ByteBuffer.wrap(bytes))
                          .toString()
                  cdRequire(
                      !text.contains(token.trim()),
                      "Credential-bearing provider response refused",
                  )
                  if (continuation.isActive) continuation.resume(text)
                }
              } catch (problem: Exception) {
                if (continuation.isActive)
                    continuation.resumeWithException(
                        if (problem is ControlDFailure) problem
                        else
                            ControlDFailure(
                                if (method == "GET") "unavailable" else "outcome-unknown",
                                "Provider response could not be read safely",
                            )
                    )
              }
            }
          }
      )
    } catch (problem: Exception) {
      if (continuation.isActive)
          continuation.resumeWithException(
              if (problem is ControlDFailure) problem
              else ControlDFailure("unavailable", "Control D request could not be started")
          )
    }
  }

  private suspend fun body(path: String, token: String, organization: String?): JsonObject {
    val text = request(URL("https://api.controld.com$path"), token, organization)
    return envelope(text)
  }

  private fun envelope(text: String): JsonObject {
    val root = runCatching { json.parseToJsonElement(text) as? JsonObject }.getOrNull()
    if (root?.get("success") != JsonPrimitive(true)) {
      val code =
          root
              ?.objectAt("error")
              ?.text("code")
              ?.takeIf { Regex("[0-9]{3,12}").matches(it) }
              ?.take(3)
              ?.toIntOrNull()
      throw ControlDFailure(
          when (code) {
            401,
            403 -> "denied"
            429 -> "rate-limited"
            else -> "incompatible"
          },
          "Control D returned an unsuccessful response",
          code,
      )
    }
    return (root.objectAt("body")?.let(::safeControlDJson) as? JsonObject)
        ?: throw ControlDFailure("incompatible", "Unsupported provider response envelope")
  }

  private fun records(body: JsonObject, key: String): List<JsonObject> {
    cdRequire(
        listOf("next", "next_cursor", "nextCursor", "has_more", "hasMore", "truncated").none {
          body[it]?.let { v ->
            v !in
                listOf(
                    JsonNull,
                    JsonPrimitive(false),
                    JsonPrimitive(0),
                    JsonPrimitive(""),
                    JsonArray(emptyList()),
                )
          } == true
        },
        "Provider returned an incomplete policy inventory",
    )
    val rows =
        body[key] as? JsonArray
            ?: throw ControlDFailure("incompatible", "Unsupported provider inventory schema")
    cdRequire(rows.size <= 10000 && rows.all { it is JsonObject })
    return rows.map { it.jsonObject }
  }

  suspend fun account(token: String, organization: String?): Pair<String, String?> {
    val data = body("/users", token, organization)
    val account =
        cdIdentifier(
            data.text("PK")
                ?: throw ControlDFailure("incompatible", "Provider account identity is unavailable")
        )
    val region =
        (data.objectAt("org")?.text("stats_endpoint") ?: data.text("stats_endpoint"))?.takeIf {
          Regex("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?").matches(it)
        }
    return account to region
  }

  suspend fun inventory(token: String, organization: String?): ControlDInventory {
    val (account, region) = account(token, organization)
    val profiles =
        records(body("/profiles", token, organization), "profiles").associate {
          cdIdentifier(it.text("PK") ?: "") to
              (it.text("name")?.takeIf(String::isNotBlank) ?: "Unnamed profile")
        }
    val endpoints =
        records(body("/devices?last_activity=1", token, organization), "devices").map { row ->
          val id = cdIdentifier(row.text("PK") ?: "")
          val profile = cdIdentifier(row.objectAt("profile")?.text("PK") ?: "")
          cdRequire(profile in profiles, "Endpoint profile is outside the selected account")
          val clients =
              (row["clients"] as? JsonArray)?.map { element ->
                val client =
                    element as? JsonObject
                        ?: throw ControlDFailure("incompatible", "Unsupported client inventory")
                ControlDClient(
                    cdClientIdentifier(client.text("PK") ?: client.text("client_id") ?: ""),
                    client.text("name") ?: client.text("hostname") ?: "Unnamed client",
                )
              }
          ControlDEndpoint(
              id,
              row.text("name")?.takeIf(String::isNotBlank) ?: "Unnamed endpoint",
              profile,
              row.objectAt("profile2")?.text("PK")?.let(::cdIdentifier),
              clients,
              row.text("device_id") ?: id,
          )
        }
    cdRequire(endpoints.map { it.id }.distinct().size == endpoints.size)
    return ControlDInventory(account, organization, region, endpoints, profiles)
  }

  suspend fun clients(
      token: String,
      inventory: ControlDInventory,
      endpoint: ControlDEndpoint,
  ): List<ControlDClient> {
    endpoint.clients?.let {
      return it
    }
    val region =
        inventory.region
            ?: throw ControlDFailure("unavailable", "Provider client inventory is unavailable")
    val raw =
        envelope(
            request(
                URL(
                    "https://$region.analytics.controld.com/v2/client?endpointId=${cdIdentifier(endpoint.id)}"
                ),
                token,
                inventory.organization,
            )
        )
    val items =
        raw.objectAt("items")
            ?: throw ControlDFailure("incompatible", "Unsupported client inventory")
    val selected = items[endpoint.deviceId] ?: return emptyList()
    val clients =
        (selected as? JsonObject)?.objectAt("clients")
            ?: throw ControlDFailure("incompatible", "Unsupported client inventory")
    return clients.map { (key, value) ->
      val client =
          value as? JsonObject
              ?: throw ControlDFailure("incompatible", "Unsupported client inventory")
      ControlDClient(
          cdClientIdentifier(key),
          client.text("alias")
              ?: client.text("hostname")
              ?: client.text("name")
              ?: "Unnamed client",
      )
    }
  }

  suspend fun policy(token: String, binding: ControlDBinding): ControlDPolicy {
    val inventory = inventory(token, binding.organization)
    cdRequire(
        inventory.account == binding.account,
        "The READ credential belongs to a different account",
    )
    val endpoint =
        inventory.endpoints.singleOrNull { it.id == binding.endpoint }
            ?: throw ControlDFailure("conflict", "Selected endpoint is no longer in this account")
    if (binding.client != null)
        cdRequire(
            clients(token, inventory, endpoint).any { it.id == binding.client },
            "Selected client is no longer in this endpoint",
        )
    val profile = endpoint.profile
    val resources = mutableMapOf<String, ControlDResource>()
    for ((kind, suffix) in
        listOf(
            "rules" to "rules/all",
            "filters" to "filters",
            "services" to "services",
            "options" to "options",
        )) {
      resources[kind] =
          try {
            val rows =
                records(body("/profiles/$profile/$suffix", token, binding.organization), kind)
            cdRequire(
                rows.all { !it.text("PK").isNullOrBlank() } &&
                    rows.map { it.text("PK") }.distinct().size == rows.size,
                "Policy category has ambiguous object identities",
            )
            cdRequire(
                rows.all { row ->
                  when (kind) {
                    "rules",
                    "services" ->
                        row.objectAt("action")?.number("do") != null &&
                            row.objectAt("action")?.number("status") in 0..1
                    "filters" -> row.number("status") in 0..1
                    else -> true
                  }
                },
                "Unsupported policy category schema",
            )
            ControlDResource("available", JsonArray(rows))
          } catch (failure: ControlDFailure) {
            ControlDResource(failure.state, message = failure.message)
          }
    }
    val options = resources["options"]
    if (options?.state == "available") {
      resources["options"] =
          try {
            val configured = options.objects().associateBy { it.text("PK") }
            val catalog = records(body("/profiles/options", token, binding.organization), "options")
            ControlDResource(
                "available",
                JsonArray(
                    catalog.map { option ->
                      JsonObject(
                          option +
                              mapOf(
                                  "configured" to JsonPrimitive(option.text("PK") in configured),
                                  "value" to JsonNull,
                              ) +
                              configured[option.text("PK")].orEmpty()
                      )
                    }
                ),
            )
          } catch (failure: ControlDFailure) {
            ControlDResource(failure.state, message = failure.message)
          }
    }
    val affected =
        inventory.endpoints
            .filter { it.profile == profile || it.secondaryProfile == profile }
            .sortedBy { it.id }
    return ControlDPolicy(
        binding,
        profile,
        inventory.profiles.getValue(profile),
        affected.map { it.name },
        resources,
        affected.map { it.id },
    )
  }

  suspend fun history(
      token: String,
      binding: ControlDBinding,
      region: String,
      from: Instant,
      until: Instant,
  ): ControlDDnsSlice {
    cdRequire(Regex("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?").matches(region))
    val query =
        mapOf(
                "startTime" to from.toString(),
                "endTime" to until.toString(),
                "endpointId" to binding.endpoint,
            )
            .entries
            .joinToString("&") {
              URLEncoder.encode(it.key, "UTF-8") + "=" + URLEncoder.encode(it.value, "UTF-8")
            }
    return parseControlDCsv(
        request(
            URL("https://$region.analytics.controld.com/v2/activity-log/csv?$query"),
            token,
            binding.organization,
            csv = true,
        ),
        binding,
        from,
        until,
    )
  }

  suspend fun mutate(token: String, organization: String?, mutation: ControlDMutation) {
    try {
      val response =
          request(
              URL("https://api.controld.com${mutation.route}"),
              token,
              organization,
              mutation.method,
              mutation.form,
          )
      val root = runCatching { json.parseToJsonElement(response) as? JsonObject }.getOrNull()
      if (root?.get("success") != JsonPrimitive(true))
          throw ControlDFailure(
              "outcome-unknown",
              "Provider write response could not be verified. Reconcile current policy.",
          )
    } catch (failure: ControlDFailure) {
      if (failure.status in listOf(401, 403, 404, 405, 429) || failure.state == "redirect-refused")
          throw failure
      throw ControlDFailure(
          "outcome-unknown",
          "Change outcome is unknown. Reconcile current policy; the write will not be retried.",
      )
    }
  }
}
