// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.Clear
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.tailscale.ipn.R
import com.tailscale.ipn.ui.theme.searchBarColors
import java.time.Instant
import kotlinx.serialization.json.*

private data class RuleEditor(
    val host: String,
    val action: Int,
    val enabled: Boolean,
    val comment: String,
    val eventProfile: String?,
    val unsupported: Boolean,
)

private val ruleEditorSaver =
    Saver<RuleEditor?, List<String>>(
        save = {
          it?.let { value ->
            listOf(
                value.host,
                value.action.toString(),
                value.enabled.toString(),
                value.comment,
                value.eventProfile.orEmpty(),
                value.unsupported.toString(),
            )
          }
        },
        restore = {
          RuleEditor(
              it[0],
              it[1].toInt(),
              it[2].toBoolean(),
              it[3],
              it[4].takeIf(String::isNotBlank),
              it[5].toBoolean(),
          )
        },
    )

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun ControlDView(model: ControlDModel, onDNSSettings: () -> Unit) {
  val focusManager = LocalFocusManager.current
  var searchFocused by remember { mutableStateOf(false) }
  val state by model.state.collectAsState()
  var tab by rememberSaveable { mutableIntStateOf(0) }
  var setup by remember { mutableStateOf<ControlDCredentials.Access?>(null) }
  var endpointsOpen by remember { mutableStateOf(false) }
  var clientsOpen by remember { mutableStateOf(false) }
  var impactOpen by rememberSaveable { mutableStateOf(false) }
  var editor by rememberSaveable(stateSaver = ruleEditorSaver) { mutableStateOf<RuleEditor?>(null) }
  var acknowledge by remember { mutableStateOf(false) }
  LaunchedEffect(model) { model.open() }
  val now = Instant.now()
  val displayedRows =
      state.transient
          ?.filter {
            it.fact.at >= now.minusSeconds(900) && it.fact.at < now && it.fact.matches(state.search)
          }
          ?.sortedByDescending { it.fact.at }
          ?.take(100) ?: state.page.rows
  val writable =
      state.hasWrite &&
          !state.busyWrite &&
          !state.busySetup &&
          state.error == null &&
          !state.unresolved &&
          state.policy?.resources?.values?.all { it.state == "available" } == true
  fun edit(
      hostname: String,
      eventProfile: String? = null,
      unsupportedEvent: Boolean = false,
      decision: Int? = null,
  ) {
    val row =
        state.policy
            ?.resources
            ?.get("rules")
            ?.takeIf { it.state == "available" }
            ?.objects()
            ?.find { it.text("PK") == hostname }
    val action = row?.objectAt("action")?.number("do") ?: decision ?: 0
    model.dismissPreview()
    editor =
        RuleEditor(
            hostname,
            action,
            row?.objectAt("action")?.number("status") != 0,
            row?.text("comment").orEmpty(),
            eventProfile,
            unsupportedEvent ||
                action !in 0..1 ||
                (eventProfile != null && eventProfile != state.policy?.profile),
        )
  }
  Column(Modifier.fillMaxSize()) {
    FlowRow(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
      Text(
          if (state.busyHistory) "Reading history"
          else if (state.transient != null) "Transient DNS view" else "Retained DNS view",
          Modifier.align(Alignment.CenterVertically),
          style = MaterialTheme.typography.labelMedium,
      )
      Box {
        TextButton(
            onClick = { endpointsOpen = true },
            enabled = !state.busyWrite && !state.busySetup && state.inventory != null,
        ) {
          Text(state.endpointName)
          Icon(Icons.Default.ArrowDropDown, null)
        }
        DropdownMenu(expanded = endpointsOpen, onDismissRequest = { endpointsOpen = false }) {
          state.inventory?.endpoints?.forEach { endpoint ->
            DropdownMenuItem(
                text = { Text(endpoint.name) },
                onClick = {
                  endpointsOpen = false
                  model.select(endpoint)
                },
            )
          }
        }
      }
      if (state.binding != null && (state.clients.isNotEmpty() || state.clientName != null))
          Box {
            TextButton(onClick = { clientsOpen = true }, enabled = !state.busyWrite) {
              Text(state.clientName ?: "All clients")
              Icon(Icons.Default.ArrowDropDown, null)
            }
            DropdownMenu(expanded = clientsOpen, onDismissRequest = { clientsOpen = false }) {
              val endpoint = state.inventory?.endpoints?.find { it.id == state.binding?.endpoint }
              DropdownMenuItem(
                  text = { Text("All clients · endpoint scope") },
                  onClick = {
                    clientsOpen = false
                    endpoint?.let { model.select(it) }
                  },
              )
              state.clients.forEach { client ->
                DropdownMenuItem(
                    text = { Text(client.name) },
                    onClick = {
                      clientsOpen = false
                      endpoint?.let { model.select(it, client) }
                    },
                )
              }
            }
          }
      state.policy?.let {
        Text(
            it.profileName,
            Modifier.align(Alignment.CenterVertically),
            style = MaterialTheme.typography.labelMedium,
        )
      }
      IconButton(
          onClick = model::refreshPolicy,
          enabled = !state.busyPolicy && !state.busyWrite && state.binding != null && state.hasRead,
      ) {
        Icon(Icons.Default.Refresh, "Reload policy")
      }
      IconButton(
          onClick = { setup = ControlDCredentials.Access.READ },
          enabled = !state.busyWrite,
      ) {
        Icon(Icons.Default.Settings, "Control D setup")
      }
    }
    TabRow(selectedTabIndex = tab) {
      Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Recent DNS") })
      Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Profile policy") })
    }
    LazyColumn(
        Modifier.fillMaxSize().navigationBarsPadding().testTag("taild-control-d-content"),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      item {
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.notice?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        if (state.busyWrite)
            LinearProgressIndicator(
                Modifier.fillMaxWidth().semantics {
                  contentDescription = "Checking explicit change"
                }
            )
        if (!state.hasRead) {
          Text(
              "Connect a READ credential, then select the endpoint/client used by your resolver. DNS settings are independent."
          )
          Button(onClick = { setup = ControlDCredentials.Access.READ }) { Text("Set up Control D") }
        }
        state.policy?.let { policy ->
          TextButton(onClick = { impactOpen = !impactOpen }) {
            Text("Shared profile · ${policy.affectedNames.size} affected endpoints")
          }
          if (impactOpen) {
            Text(
                "Changes affect every endpoint below. Allow creates an explicit Bypass rule and may override filter blocks.",
                style = MaterialTheme.typography.bodySmall,
            )
            policy.affectedNames.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
          }
        }
        if (!state.hasWrite && state.hasRead)
            TextButton(onClick = { setup = ControlDCredentials.Access.WRITE }) {
              Text("Add separate Write access")
            }
        if (state.unresolved) {
          Text(
              "An earlier change has an unresolved outcome. No policy write will be retried.",
              color = MaterialTheme.colorScheme.error,
          )
          FlowRow {
            TextButton(onClick = model::reconcile, enabled = !state.busyWrite && state.hasRead) {
              Text("Reconcile current policy")
            }
            TextButton(
                onClick = { acknowledge = true },
                enabled = !state.busyWrite && state.policy != null,
            ) {
              Text("Accept current policy…")
            }
          }
        }
      }
      if (tab == 0) {
        item {
          Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = state.search,
                onValueChange = model::search,
                placeholder = {
                  Text(
                      "Domain / decision",
                      style = MaterialTheme.typography.bodyLarge,
                      maxLines = 1,
                  )
                },
                modifier = Modifier.weight(1f).onFocusChanged { searchFocused = it.isFocused },
                singleLine = true,
                shape = MaterialTheme.shapes.extraLarge,
                colors = MaterialTheme.colorScheme.searchBarColors,
                leadingIcon = { Icon(Icons.Outlined.Search, "Search domains or decisions") },
                trailingIcon = {
                  if (searchFocused) {
                    IconButton(
                        onClick = {
                          focusManager.clearFocus()
                          model.search("")
                        }
                    ) {
                      Icon(
                          if (state.search.isEmpty()) Icons.Outlined.Close
                          else Icons.Outlined.Clear,
                          "Clear domain or decision search",
                          tint = MaterialTheme.colorScheme.onSurfaceVariant,
                      )
                    }
                  }
                },
            )
            IconButton(
                onClick = { model.refreshHistory(full = true) },
                enabled = !state.busyHistory && state.binding != null && state.hasRead,
            ) {
              Icon(Icons.Default.Refresh, "Refresh DNS")
            }
          }
          if (state.busyHistory) {
            LinearProgressIndicator(Modifier.fillMaxWidth())
            TextButton(onClick = model::cancelHistoryRead) { Text("Cancel history read") }
          }
          Text(
              "Latest 100 observations in 15 minutes. First seen and Total use all retained observations in the last 7 days, independently of search. Gaps do not mean zero activity.",
              style = MaterialTheme.typography.bodySmall,
          )
          if (state.transient != null)
              Text(
                  "Current provider rows are transient; First seen and Total still describe retained history.",
                  style = MaterialTheme.typography.bodySmall,
              )
          state.historyError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
          if (displayedRows.isEmpty() && !state.busyHistory)
              Text(
                  if (state.search.isBlank())
                      "No observations in this scope's recent window. This is not proof of no DNS activity."
                  else "No matching domain or decision in this recent window."
              )
        }
        items(displayedRows, key = { it.key }) { entry ->
          val fact = entry.fact
          val summary = state.page.summaries[fact.question to fact.type]
          Column(Modifier.fillMaxWidth()) {
            Text(fact.question, style = MaterialTheme.typography.titleMedium)
            Text("${fact.type} · ${fact.at} UTC", style = MaterialTheme.typography.bodySmall)
            FlowRow(
                verticalArrangement = Arrangement.Center,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
              Text(
                  fact.decision,
                  Modifier.align(Alignment.CenterVertically),
                  color =
                      if (fact.action == 0) MaterialTheme.colorScheme.error
                      else MaterialTheme.colorScheme.onSurface,
                  style = MaterialTheme.typography.labelLarge,
              )
              val existing =
                  state.policy
                      ?.resources
                      ?.get("rules")
                      ?.takeIf { it.state == "available" }
                      ?.objects()
                      ?.find { it.text("PK") == fact.question }
              val quick =
                  writable &&
                      fact.profile != null &&
                      fact.profile == state.policy?.profile &&
                      fact.action in 0..3 &&
                      (existing == null || existing.objectAt("action")?.number("do") in 0..1)
              if (fact.action != 0)
                  IconButton(onClick = { model.incident(fact, 0) }, enabled = quick) {
                    Icon(painterResource(R.drawable.taild_block), "Block ${fact.question}")
                  }
              if (fact.action != 1)
                  IconButton(onClick = { model.incident(fact, 1) }, enabled = quick) {
                    Icon(Icons.Default.Check, "Allow ${fact.question} with Bypass")
                  }
              IconButton(
                  onClick = {
                    edit(fact.question, fact.profile, fact.action !in 0..3, fact.action)
                  },
                  enabled = !state.busyWrite,
              ) {
                Icon(Icons.Default.Settings, "Edit rule for ${fact.question}")
              }
            }
            Text(fact.reason, style = MaterialTheme.typography.bodySmall)
            Text(
                "First seen · ${summary?.firstSeen ?: "Not retained"}\nTotal · ${summary?.total ?: "Not retained"} · retained 7 days",
                style = MaterialTheme.typography.bodySmall,
            )
            HorizontalDivider(Modifier.padding(top = 8.dp))
          }
        }
      } else {
        item {
          Text("Profile policy", style = MaterialTheme.typography.titleLarge)
          Text(
              "Browsing uses READ access. Management changes are reviewed against fresh policy and affect the shared profile.",
              style = MaterialTheme.typography.bodySmall,
          )
          TextButton(onClick = { edit("") }, enabled = !state.busyWrite && state.policy != null) {
            Text("Create custom rule")
          }
          if (state.busyPolicy) LinearProgressIndicator(Modifier.fillMaxWidth())
        }
        listOf(
                "rules" to "Custom rules",
                "filters" to "Filters",
                "services" to "Services",
                "options" to "Profile options",
            )
            .forEach { (kind, title) ->
              val resource = state.policy?.resources?.get(kind)
              item(key = "heading-$kind") {
                Text(title, style = MaterialTheme.typography.titleMedium)
                if (resource != null && resource.state != "available")
                    Text(
                        resource.message ?: "This category is unavailable",
                        color = MaterialTheme.colorScheme.error,
                    )
              }
              val rows = resource?.takeIf { it.state == "available" }?.objects().orEmpty()
              items(rows, key = { "$kind-${it.text("PK")}" }) { row ->
                val id = row.text("PK").orEmpty()
                val action = row.objectAt("action")
                val enabled =
                    when (kind) {
                      "rules",
                      "services" -> action?.number("status") == 1
                      "options" -> row.text("value") == "1"
                      else -> row.number("status") == 1
                    }
                val supported =
                    when (kind) {
                      "rules",
                      "services" -> action?.number("do") in 0..1
                      "options" -> row.text("type") == "toggle"
                      else -> true
                    }
                ListItem(
                    headlineContent = {
                      Text(
                          if (kind == "rules") id
                          else
                              row.text("name")
                                  ?: row.text("title")
                                  ?: "Unnamed ${title.lowercase()}"
                      )
                    },
                    supportingContent = {
                      Text(
                          if (!supported) "Unsupported action/type · read only"
                          else if (enabled) "Enabled" else "Disabled"
                      )
                    },
                    trailingContent = {
                      if (kind == "rules")
                          IconButton(onClick = { edit(id) }, enabled = !state.busyWrite) {
                            Icon(Icons.Default.Settings, "Edit $id")
                          }
                      else
                          Switch(
                              checked = enabled,
                              enabled = writable && supported,
                              modifier =
                                  Modifier.semantics {
                                    contentDescription =
                                        row.text("name") ?: row.text("title") ?: title
                                  },
                              onCheckedChange = { desired ->
                                val change =
                                    when (kind) {
                                      "filters" ->
                                          ControlDChange.Filter(action?.text("lvl") ?: id, desired)
                                      "services" ->
                                          ControlDChange.Service(
                                              id,
                                              action?.number("do") ?: -1,
                                              desired,
                                          )
                                      else -> ControlDChange.Option(id, desired)
                                    }
                                model.prepare(change)
                              },
                          )
                    },
                )
              }
            }
      }
    }
  }
  setup?.let { access ->
    ControlDSetupDialog(state, access, model, onDNSSettings, onClose = { setup = null })
  }
  editor?.let { value ->
    RuleEditorDialog(
        value,
        state,
        model,
        onClose = {
          editor = null
          model.dismissPreview()
        },
    )
  }
  val preview = state.preview
  if (preview != null && editor == null)
      AlertDialog(
          onDismissRequest = model::dismissPreview,
          title = { Text("Review policy change") },
          text = {
            Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
              Text(changeLabel(preview.change))
              Text("Profile: ${preview.policy.profileName}")
              Text("Affected endpoints:")
              preview.policy.affectedNames.forEach { Text(it) }
            }
          },
          confirmButton = {
            TextButton(
                onClick = { model.applyPreview(preview.ticket) },
                enabled = !state.busyWrite,
            ) {
              Text("Apply")
            }
          },
          dismissButton = { TextButton(onClick = model::dismissPreview) { Text("Cancel") } },
      )
  if (acknowledge)
      AlertDialog(
          onDismissRequest = { acknowledge = false },
          title = { Text("Accept current policy?") },
          text = {
            Text(
                "This clears the local unresolved receipt after a fresh policy check. It does not undo or retry the earlier write, or prove that the earlier request never ran."
            )
          },
          confirmButton = {
            TextButton(
                onClick = {
                  acknowledge = false
                  model.acknowledgeCurrentPolicy()
                }
            ) {
              Text("Accept current policy")
            }
          },
          dismissButton = { TextButton(onClick = { acknowledge = false }) { Text("Cancel") } },
      )
}

@Composable
@OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class)
private fun ControlDSetupDialog(
    state: ControlDState,
    access: ControlDCredentials.Access,
    model: ControlDModel,
    onDNSSettings: () -> Unit,
    onClose: () -> Unit,
) {
  // Credentials deliberately use remember, never rememberSaveable/Android saved-state.
  var credential by remember(access) { mutableStateOf("") }
  var organization by remember {
    mutableStateOf(state.inventory?.organization ?: state.binding?.organization.orEmpty())
  }
  AlertDialog(
      onDismissRequest = onClose,
      modifier = Modifier.semantics { testTagsAsResourceId = true },
      title = {
        Text(
            if (access == ControlDCredentials.Access.READ) "Control D READ setup"
            else "Separate Write access"
        )
      },
      text = {
        Column(
            Modifier.heightIn(max = 440.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
          Text(
              "Enter a ${if(access == ControlDCredentials.Access.READ) "Read-only" else "Write"} API token from Control D. Resolver IDs are not API credentials. Saved tokens are protected by Android Keystore and excluded from backups."
          )
          OutlinedTextField(
              value = credential,
              onValueChange = { credential = it },
              label = { Text("${access.name} API token") },
              modifier = Modifier.testTag("taild-api-token"),
              visualTransformation = PasswordVisualTransformation(),
              singleLine = true,
          )
          if (access == ControlDCredentials.Access.READ)
              OutlinedTextField(
                  value = organization,
                  onValueChange = { organization = it },
                  label = { Text("Organization scope · optional") },
                  singleLine = true,
              )
          Text(
              "Adding API access never changes DNS. Choose the matching endpoint/client after connecting.",
              style = MaterialTheme.typography.bodySmall,
          )
          Text(state.resolverNotice, style = MaterialTheme.typography.bodySmall)
          state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
          state.notice?.let { Text(it) }
          if (state.busySetup) LinearProgressIndicator(Modifier.fillMaxWidth())
          TextButton(
              onClick = {
                onClose()
                onDNSSettings()
              }
          ) {
            Text("Open DNS settings")
          }
          if (state.hasRead || state.hasWrite)
              TextButton(
                  onClick = model::removeCredentials,
                  enabled = !state.busySetup && !state.busyWrite,
              ) {
                Text("Remove saved API credentials")
              }
        }
      },
      confirmButton = {
        TextButton(
            onClick = {
              if (access == ControlDCredentials.Access.READ)
                  model.configureRead(credential, organization)
              else model.configureWrite(credential)
              credential = ""
            },
            enabled = credential.isNotBlank() && !state.busySetup && !state.busyWrite,
        ) {
          Text("Verify and save")
        }
      },
      dismissButton = { TextButton(onClick = onClose) { Text("Close") } },
  )
}

@Composable
@OptIn(androidx.compose.ui.ExperimentalComposeUiApi::class, ExperimentalMaterial3Api::class)
private fun RuleEditorDialog(
    initial: RuleEditor,
    state: ControlDState,
    model: ControlDModel,
    onClose: () -> Unit,
) {
  var host by rememberSaveable(initial.host) { mutableStateOf(initial.host) }
  var action by rememberSaveable(initial.host) { mutableIntStateOf(initial.action) }
  var enabled by rememberSaveable(initial.host) { mutableStateOf(initial.enabled) }
  var comment by rememberSaveable(initial.host) { mutableStateOf(initial.comment) }
  val preview = state.preview
  val editable =
      !initial.unsupported &&
          state.hasWrite &&
          !state.busyWrite &&
          !state.unresolved &&
          state.policy != null
  fun changed() = model.dismissPreview()
  AlertDialog(
      onDismissRequest = onClose,
      modifier = Modifier.semantics { testTagsAsResourceId = true },
      title = { Text("Edit custom rule") },
      text = {
        Column(
            Modifier.heightIn(max = 440.dp)
                .verticalScroll(rememberScrollState())
                .testTag("taild-rule-editor-content"),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
          OutlinedTextField(
              value = host,
              onValueChange = {
                changed()
                host = it
              },
              label = { Text("Hostname") },
              modifier = Modifier.testTag("taild-rule-hostname"),
              enabled = editable && initial.host.isBlank(),
              singleLine = true,
          )
          if (initial.unsupported)
              Text(
                  "This event or rule cannot be edited safely here. Existing Spoof/Redirect and historical-profile actions remain unchanged."
              )
          if (!state.hasWrite)
              Text("READ view. Add a separate Write credential to manage current policy.")
          Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                when (action) {
                  0 -> "Rule action · Block"
                  1 -> "Rule action · Allow / Bypass"
                  else -> "Unsupported rule action · read only"
                },
                Modifier.weight(1f),
            )
            if (action in 0..1) {
              val opposite = if (action == 0) 1 else 0
              val label =
                  if (opposite == 0) "Block rule action" else "Allow with Bypass rule action"
              TooltipBox(
                  positionProvider = TooltipDefaults.rememberPlainTooltipPositionProvider(),
                  tooltip = {
                    PlainTooltip { Text(if (opposite == 0) "Block" else "Allow · explicit Bypass") }
                  },
                  state = rememberTooltipState(),
              ) {
                FilledTonalIconButton(
                    onClick = {
                      changed()
                      action = opposite
                    },
                    enabled = editable,
                    modifier = Modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp),
                ) {
                  Icon(if (opposite == 0) Icons.Default.Close else Icons.Default.Check, label)
                }
              }
            }
          }
          Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Enabled", Modifier.weight(1f))
            Switch(
                checked = enabled,
                onCheckedChange = {
                  changed()
                  enabled = it
                },
                enabled = editable,
                modifier = Modifier.semantics { contentDescription = "Rule enabled" },
            )
          }
          OutlinedTextField(
              value = comment,
              onValueChange = {
                changed()
                comment = it.take(64)
              },
              label = { Text("Comment") },
              modifier = Modifier.testTag("taild-rule-comment"),
              enabled = editable,
          )
          state.policy?.let { policy ->
            Text("Shared profile: ${policy.profileName}")
            Text("Affects ${policy.affectedNames.size} endpoints:")
            policy.affectedNames.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
          }
          if (preview != null)
              Text(
                  "Fresh policy reviewed: ${changeLabel(preview.change)}",
                  style = MaterialTheme.typography.labelLarge,
              )
          state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
          state.notice?.let { Text(it) }
          if (initial.host.isNotBlank())
              TextButton(
                  onClick = {
                    model.prepare(
                        ControlDChange.Rule(
                            initial.host,
                            initial.action,
                            initial.enabled,
                            initial.comment,
                            delete = true,
                        ),
                        initial.eventProfile,
                    )
                  },
                  enabled = editable,
              ) {
                Text("Review deletion")
              }
        }
      },
      confirmButton = {
        TextButton(
            onClick = {
              if (preview != null) model.applyPreview(preview.ticket)
              else
                  model.prepare(
                      ControlDChange.Rule(host, action, enabled, comment),
                      initial.eventProfile,
                  )
            },
            enabled = editable && host.isNotBlank(),
        ) {
          Text(if (preview == null) "Review change" else "Apply reviewed change")
        }
      },
      dismissButton = { TextButton(onClick = onClose) { Text("Close") } },
  )
}

private fun changeLabel(change: ControlDChange): String =
    when (change) {
      is ControlDChange.Rule ->
          if (change.delete) "Delete custom rule for ${change.hostname}"
          else
              "${if(change.action == 0) "Block" else "Allow with Bypass"} ${change.hostname} · ${if(change.enabled) "Enabled" else "Disabled"}"
      is ControlDChange.Filter -> "${if(change.enabled) "Enable" else "Disable"} selected filter"
      is ControlDChange.Service ->
          "${if(change.enabled) "Enable" else "Disable"} selected service action"
      is ControlDChange.Option ->
          "${if(change.enabled) "Enable" else "Disable"} selected profile option"
    }
