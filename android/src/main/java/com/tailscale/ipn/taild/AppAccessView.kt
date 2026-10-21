// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.os.Process
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.tailscale.ipn.App
import com.tailscale.ipn.R
import com.tailscale.ipn.ui.theme.searchBarColors

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun AppAccessView(
    installed: List<AppAccessIdentity> = emptyList(),
    traffic: TrafficSnapshot? = null,
    onDiagnosis: ((FirewallTrafficApp) -> Unit)? = null,
) {
  val context = LocalContext.current
  val model = remember { App.get().tailDAppAccess }
  val state by model.state.collectAsState()
  val uri = LocalUriHandler.current
  val focus = LocalFocusManager.current
  var search by rememberSaveable { mutableStateOf("") }
  var expanded by rememberSaveable { mutableStateOf<Int?>(null) }
  var setupDetails by rememberSaveable { mutableStateOf(false) }
  val snapshot = state.snapshot
  val apps =
      remember(snapshot?.apps, installed, traffic, search) {
        firewallTrafficApps(snapshot?.apps ?: installed, traffic).filter { app ->
          app.label.contains(search, true) ||
              app.current?.packages?.any {
                it.label.contains(search, true) || it.name.contains(search, true)
              } == true
        }
      }
  DisposableEffect(model) {
    model.open()
    onDispose { model.close() }
  }
  LazyColumn(
      Modifier.fillMaxSize().imePadding().testTag("taild-app-access"),
      contentPadding =
          PaddingValues(horizontal = 16.dp, vertical = if (onDiagnosis == null) 16.dp else 8.dp),
      verticalArrangement = Arrangement.spacedBy(if (onDiagnosis == null) 12.dp else 8.dp),
  ) {
    if (
        onDiagnosis == null ||
            setupDetails ||
            !state.journalAvailable ||
            state.error != null ||
            state.busy
    )
        item {
          if (onDiagnosis == null)
              Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "App access",
                    Modifier.weight(1f),
                    style = MaterialTheme.typography.titleMedium,
                )
                IconButton(onClick = model::refresh, enabled = state.connected && !state.busy) {
                  Icon(Icons.Default.Refresh, "Refresh app access")
                }
              }
          if (onDiagnosis == null || setupDetails)
              Text(state.status, style = MaterialTheme.typography.bodySmall)
          if (!state.journalAvailable)
              Text(
                  "The ownership journal is unavailable. Policy changes are disabled.",
                  color = MaterialTheme.colorScheme.error,
              )
          if (!state.connected && (onDiagnosis == null || setupDetails)) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
              TextButton(onClick = model::connect, enabled = !state.busy) {
                Text("Connect Shizuku")
              }
              TextButton(onClick = { uri.openUri("https://shizuku.rikka.app/guide/setup/") }) {
                Text("Shizuku setup")
              }
            }
          }
          state.error?.let {
            Text(
                it,
                Modifier.testTag("taild-app-access-error"),
                color = MaterialTheme.colorScheme.error,
            )
          }
          if (state.busy)
              LinearProgressIndicator(Modifier.fillMaxWidth().testTag("taild-app-access-busy"))
        }
    if (snapshot != null || onDiagnosis != null) {
      item {
        if (snapshot != null && snapshot.profiles.size > 1)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
              snapshot.profiles.forEach { profile ->
                FilterChip(
                    selected = profile == snapshot.profile,
                    onClick = { model.selectProfile(profile) },
                    enabled = !state.busy,
                    label = { Text("Profile $profile") },
                )
              }
            }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
          OutlinedTextField(
              search,
              { search = it },
              Modifier.weight(1f).testTag("taild-app-access-search"),
              singleLine = true,
              keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
              keyboardActions = KeyboardActions(onDone = { focus.clearFocus() }),
              placeholder = { Text("App / package") },
              shape = MaterialTheme.shapes.extraLarge,
              colors = MaterialTheme.colorScheme.searchBarColors,
              leadingIcon = { Icon(Icons.Outlined.Search, "Search apps") },
          )
          if (onDiagnosis != null)
              IconButton(onClick = { setupDetails = !setupDetails }) {
                Icon(
                    Icons.Default.Info,
                    if (setupDetails) "Hide firewall setup" else "Firewall setup & coverage",
                )
              }
        }
      }
      items(apps, key = { it.key }) { row ->
        val app = row.current
        if (app == null) {
          Row(
              Modifier.fillMaxWidth().testTag("taild-firewall-app"),
              verticalAlignment = Alignment.CenterVertically,
          ) {
            Column(Modifier.weight(1f)) {
              Text(row.label, maxLines = 2, overflow = TextOverflow.Ellipsis)
              Text(
                  "↓ ${trafficBytes(row.received)} · ↑ ${trafficBytes(row.sent)}",
                  style = MaterialTheme.typography.bodySmall,
              )
              HourlyTrafficGraph(row.hourly, Modifier.fillMaxWidth().height(24.dp))
              Text("Recorded identity", style = MaterialTheme.typography.labelSmall)
            }
            IconButton(onClick = { onDiagnosis?.invoke(row) }) {
              Icon(Icons.Default.Info, "Diagnose ${row.label}")
            }
          }
          HorizontalDivider()
          return@items
        }
        val owned = state.owned.singleOrNull { it.identity.uid == app.uid }
        val present = app.uid in snapshot?.blockedUids.orEmpty()
        val same = owned?.identity?.fingerprint == app.fingerprint
        val pending = owned != null && (owned.phase != "ACTIVE" || !present || !same)
        Row(
            Modifier.fillMaxWidth().testTag("taild-firewall-app"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
          Column(Modifier.weight(1f)) {
            Text(
                app.packages.joinToString(" / ") { it.label },
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (app.packages.size > 1)
                Text(
                    "Shared UID · ${app.packages.size} apps affected",
                    style = MaterialTheme.typography.labelMedium,
                )
            if (onDiagnosis != null)
                Column {
                  Text(
                      if (traffic == null) "Traffic unavailable"
                      else "↓ ${trafficBytes(row.received)} · ↑ ${trafficBytes(row.sent)}",
                      style = MaterialTheme.typography.bodySmall,
                  )
                  HourlyTrafficGraph(row.hourly, Modifier.fillMaxWidth().height(24.dp))
                }
            Text(
                when {
                  !state.connected || snapshot == null -> "Rule unknown"
                  pending -> "Recorded change needs reconciliation"
                  present && same && snapshot?.chainEnabled == true -> "TailD block active"
                  present && same -> "TailD rule present · Android filter inactive"
                  present -> "Existing rule · not owned by TailD"
                  else -> "No TailD block"
                },
                style = MaterialTheme.typography.bodySmall,
            )
          }
          IconButton(
              onClick = {
                if (onDiagnosis != null) onDiagnosis(row)
                else expanded = if (expanded == app.uid) null else app.uid
              }
          ) {
            Icon(
                Icons.Default.Info,
                if (onDiagnosis != null) "Diagnose ${row.label}"
                else "App details for ${app.packages.first().label}",
            )
          }
          if (pending)
              TextButton(
                  onClick = { model.reconcile(owned!!.identity) },
                  enabled = !state.busy && state.connected,
              ) {
                Text("Reconcile")
              }
          else if (
              state.connected &&
                  snapshot != null &&
                  app.uid != Process.myUid() &&
                  app.packages.none { it.name == context.packageName } &&
                  (!present || same)
          ) {
            IconButton(
                onClick = {
                  focus.clearFocus()
                  model.review(app, !present)
                },
                enabled =
                    state.journalAvailable &&
                        state.connected &&
                        snapshot != null &&
                        !state.busy &&
                        state.owned.all { it.phase == "ACTIVE" },
            ) {
              if (present)
                  Icon(Icons.Default.Check, "Remove TailD block for ${app.packages.first().label}")
              else
                  Icon(
                      painterResource(R.drawable.taild_block),
                      "Block app ${app.packages.first().label}",
                  )
            }
          }
        }
        if (expanded == app.uid) {
          Text("UID ${app.uid}", style = MaterialTheme.typography.bodySmall)
          app.packages.forEach { Text(it.name, style = MaterialTheme.typography.bodySmall) }
        }
        HorizontalDivider()
      }
    }
    val missing =
        state.owned.filter { entry ->
          state.snapshot?.apps?.none { it.uid == entry.identity.uid } != false
        }
    if (missing.isNotEmpty())
        item {
          Text("Recorded rules", style = MaterialTheme.typography.titleSmall)
          Text(
              "Blocks may remain when backend access is lost. Reconnect and reconcile to inspect them. An Android restart clears transient platform rules on supported devices; TailD never silently reapplies them.",
              style = MaterialTheme.typography.bodySmall,
          )
        }
    items(missing, key = { "owned-${it.identity.uid}" }) { owned ->
      Text(owned.identity.packages.joinToString(" / ") { it.label })
      Text(
          "Profile ${owned.identity.profile} · UID ${owned.identity.uid} · effective state not established",
          style = MaterialTheme.typography.bodySmall,
      )
      TextButton(
          onClick = { model.reconcile(owned.identity) },
          enabled = state.connected && !state.busy,
      ) {
        Text("Reconcile recorded rule")
      }
    }
  }
  state.preview?.let { request ->
    AlertDialog(
        onDismissRequest = model::dismiss,
        title = { Text(if (request.blocked) "Block app traffic?" else "Remove TailD block?") },
        text = {
          Column(
              Modifier.verticalScroll(rememberScrollState()),
              verticalArrangement = Arrangement.spacedBy(8.dp),
          ) {
            request.identity.packages.forEach { Text("${it.label}\n${it.name}") }
            Text("Profile ${request.identity.profile} · UID ${request.identity.uid}")
            if (request.identity.packages.size > 1) Text("Every app sharing this UID is affected.")
            if (request.blocked && state.snapshot?.chainEnabled == false)
                Text(
                    "This first block activates an empty Android app filter. TailD never resets other app rules."
                )
            Text(
                "Other firewall and DNS policies remain independent.",
                style = MaterialTheme.typography.bodySmall,
            )
          }
        },
        confirmButton = { TextButton(onClick = model::applyReviewed) { Text("Apply") } },
        dismissButton = { TextButton(onClick = model::dismiss) { Text("Cancel") } },
    )
  }
}
