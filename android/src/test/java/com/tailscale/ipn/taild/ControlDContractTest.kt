package com.tailscale.ipn.taild

import java.time.Instant
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class ControlDContractTest {
  private val binding = ControlDBinding("account", null, "endpoint", "phone")
  private val from = Instant.parse("2026-10-20T09:00:00Z")
  private val until = Instant.parse("2026-10-20T10:00:00Z")

  @Test
  fun csvPreservesIdenticalOccurrencesAndExactClientScope() {
    val header =
        "timestamp,endpointId,clientId,profileId,question,action,rrType,trigger,answers\r\n"
    val row =
        "2026-10-20T09:30:00Z,endpoint,phone,profile,Example.COM,0,A,filter,\"1.2.3.4;5.6.7.8\"\r\n"
    val slice =
        parseControlDCsv(
            header + row + row + row.replace(",phone,", ",other,"),
            binding,
            from,
            until,
        )
    assertEquals(2, slice.facts.size)
    assertFalse(slice.truncated)
    assertEquals("Blocked", slice.facts.first().decision)
    assertEquals(slice.facts[0].identity, slice.facts[1].identity)
    assertEquals("example.com", slice.facts[0].question)
  }

  @Test
  fun csvRejectsNaiveTimeWrongEndpointAndAmbiguousHeaders() {
    val header = "timestamp,endpointId,clientId,question,action\n"
    for (csv in
        listOf(
            header + "2026-10-20T09:30:00,endpoint,phone,test.invalid,0\n",
            header + "2026-10-20T09:30:00Z,other,phone,test.invalid,0\n",
            "timestamp,timestamp,endpointId,question,action\n",
        )) {
      assertThrows(ControlDFailure::class.java) { parseControlDCsv(csv, binding, from, until) }
    }
  }

  @Test
  fun unsupportedActionsStayUnknownAndCappedResultsAreIncomplete() {
    val csv =
        "timestamp,endpointId,clientId,question,action\n" +
            "2026-10-20T09:30:00Z,endpoint,phone,test.invalid,999\n".repeat(2)
    val slice = parseControlDCsv(csv, binding, from, until, limit = 1)
    assertTrue(slice.truncated)
    assertEquals("Unknown", slice.facts.single().decision)
    assertEquals("999", slice.facts.single().raw["action"])
  }

  @Test
  fun bindingAndPolicyChangesInvalidateIntent() {
    fun policy(rule: String = "0", account: String = "account") =
        ControlDPolicy(
            binding.copy(account = account),
            "profile",
            "Shared",
            listOf("Other device"),
            mapOf(
                "rules" to
                    ControlDResource(
                        "available",
                        Json.parseToJsonElement(
                                "[{\"PK\":\"test.invalid\",\"action\":{\"do\":$rule,\"status\":1},\"group\":4}]"
                            )
                            .jsonArray,
                    )
            ),
        )
    val before = policy()
    checkControlDIntent(before, policy(), "profile")
    assertThrows(ControlDFailure::class.java) {
      checkControlDIntent(before, policy("1"), "profile")
    }
    assertThrows(ControlDFailure::class.java) {
      checkControlDIntent(before, policy(account = "other"), "profile")
    }
    assertThrows(ControlDFailure::class.java) {
      checkControlDIntent(before, policy(), "old-profile")
    }
    val route = controlDMutation(before, ControlDChange.Rule("test.invalid", 1, true, "Incident"))
    assertEquals("PUT", route.method)
    assertEquals(listOf("4"), route.form["group"])
    assertThrows(ControlDFailure::class.java) {
      controlDMutation(before, ControlDChange.Rule("https://test.invalid", 0, true, ""))
    }
    assertThrows(ControlDFailure::class.java) {
      controlDMutation(before, ControlDChange.Rule("test.invalid", 2, true, ""))
    }
    assertThrows(ControlDFailure::class.java) {
      controlDMutation(policy("2"), ControlDChange.Rule("test.invalid", 0, true, "", delete = true))
    }
    val unknownService =
        before.copy(resources = mapOf("services" to policy("2").resources.getValue("rules")))
    assertThrows(ControlDFailure::class.java) {
      controlDMutation(unknownService, ControlDChange.Service("test.invalid", 0, true))
    }
  }
}
