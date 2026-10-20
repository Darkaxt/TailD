package com.tailscale.ipn.taild

import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.Assert.*
import org.junit.Test

class ControlDNetworkTest {
  private fun api(server: MockWebServer) =
      ControlDApi(
          OkHttpClient.Builder()
              .addInterceptor { chain ->
                val original = chain.request()
                chain.proceed(
                    original
                        .newBuilder()
                        .url(
                            server.url(
                                original.url.encodedPath +
                                    (original.url.encodedQuery?.let { "?$it" } ?: "")
                            )
                        )
                        .build()
                )
              }
              .build()
      )

  private val token = "synthetic-read-token"

  @Test
  fun redirectCannotForwardTheBearer() = runBlocking {
    MockWebServer().use { server ->
      server.enqueue(
          MockResponse().setResponseCode(302).addHeader("Location", "https://other.invalid/private")
      )
      val failure =
          runCatching { api(server).account(token, null) }.exceptionOrNull() as ControlDFailure
      assertEquals("redirect-refused", failure.state)
      assertEquals(1, server.requestCount)
      val request = server.takeRequest()
      assertEquals("GET", request.method)
      assertEquals("Bearer $token", request.getHeader("Authorization"))
      assertFalse(failure.message.orEmpty().contains(token))
    }
  }

  @Test
  fun committedWriteWithLostResponseIsNotReplayed() = runBlocking {
    MockWebServer().use { server ->
      server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST))
      val failure =
          runCatching {
            api(server)
                .mutate(
                    "synthetic-write-token",
                    null,
                    ControlDMutation(
                        "POST",
                        "/profiles/profile/rules",
                        mapOf(
                            "hostnames[]" to listOf("example.invalid"),
                            "do" to listOf("1"),
                            "status" to listOf("1"),
                        ),
                    ),
                )
          }
              .exceptionOrNull() as ControlDFailure
      assertEquals("outcome-unknown", failure.state)
      assertEquals(1, server.requestCount)
      assertEquals("POST", server.takeRequest().method)
    }
  }

  @Test
  fun retryAfterZeroDoesNotCreateASecondExchange() = runBlocking {
    MockWebServer().use { server ->
      server.enqueue(MockResponse().setResponseCode(503).addHeader("Retry-After", "0"))
      val failure = runCatching { api(server).account(token, null) }.exceptionOrNull()
      assertTrue(failure is ControlDFailure)
      assertEquals(1, server.requestCount)
    }
  }

  @Test
  fun writeRetryAfterZeroAlsoRemainsSingleUse() = runBlocking {
    MockWebServer().use { server ->
      server.enqueue(MockResponse().setResponseCode(503).addHeader("Retry-After", "0"))
      val failure =
          runCatching {
            api(server)
                .mutate(
                    "synthetic-write",
                    null,
                    ControlDMutation(
                        "PUT",
                        "/profiles/profile/options/test",
                        mapOf("status" to listOf("1")),
                    ),
                )
          }
              .exceptionOrNull() as ControlDFailure
      assertEquals("outcome-unknown", failure.state)
      assertEquals(1, server.requestCount)
    }
  }

  @Test
  fun deniedEnvelopeAndRateLimitAreTerminalAndSanitized() = runBlocking {
    MockWebServer().use { server ->
      server.enqueue(
          MockResponse()
              .setBody(
                  "{\"success\":false,\"error\":{\"code\":403123,\"message\":\"private account\"}}"
              )
      )
      val denied =
          runCatching { api(server).account(token, null) }.exceptionOrNull() as ControlDFailure
      assertEquals("denied", denied.state)
      assertFalse(denied.message.orEmpty().contains("private account"))
      server.enqueue(MockResponse().setResponseCode(429).addHeader("Retry-After", "120"))
      val limited =
          runCatching { api(server).account(token, null) }.exceptionOrNull() as ControlDFailure
      assertEquals("rate-limited", limited.state)
      assertEquals("120", limited.retryAfter)
      assertEquals(2, server.requestCount)
    }
  }
}
