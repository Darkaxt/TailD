// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@OptIn(
    ExperimentalLayoutApi::class,
    ExperimentalMaterial3Api::class,
    ExperimentalComposeUiApi::class,
)
@Composable
fun DashboardView(
    model: DashboardModel,
    controlD: ControlDModel,
    history: TailDHistory,
    onControlD: () -> Unit,
    onPreferences: () -> Unit,
) {
  val state by model.state.collectAsState()
  val provider by controlD.state.collectAsState()
  val recording by history.enabled.collectAsState()
  val context = LocalContext.current
  var tab by rememberSaveable { mutableIntStateOf(0) }
  var about by rememberSaveable { mutableStateOf(false) }
  val exporter =
      rememberLauncherForActivityResult(
          ActivityResultContracts.CreateDocument("application/json")
      ) {
        model.writeExport(context.contentResolver, it)
      }
  fun exportDns(data: DashboardDnsSnapshot, filter: DashboardDnsFilter) {
    if (model.prepareDnsExport(data, filter))
        exporter.launch("TailD-DNS-${Instant.now().epochSecond}.json")
  }
  fun exportActivity(data: DashboardActivitySnapshot, kind: String?, search: String) {
    if (model.prepareActivityExport(data, kind, search))
        exporter.launch("TailD-activity-${Instant.now().epochSecond}.json")
  }
  DisposableEffect(model) {
    model.open()
    onDispose { model.closeView() }
  }
  Column(Modifier.fillMaxSize()) {
    FlowRow(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      listOf(1 to "1h", 24 to "24h", 168 to "7 days").forEach { (hours, label) ->
        FilterChip(
            selected = state.hours == hours,
            onClick = { model.refresh(hours) },
            label = { Text(label) },
            modifier = Modifier.semantics { contentDescription = "Last $label" },
        )
      }
      IconButton(
          onClick = { model.refresh() },
          enabled = !state.dnsLoading && !state.activityLoading,
      ) {
        Icon(Icons.Default.Refresh, "Refresh Dashboard")
      }
      IconButton(onClick = { about = true }) {
        Icon(Icons.Default.Info, "About TailD and source health")
      }
    }
    ScrollableTabRow(tab, edgePadding = 0.dp, modifier = Modifier.testTag("taild-dashboard-tabs")) {
      listOf("Overview", "Geography", "Activity", "Sources & health").forEachIndexed { index, label
        ->
        Tab(selected = tab == index, onClick = { tab = index }, text = { Text(label) })
      }
    }
    LazyColumn(
        Modifier.fillMaxSize().navigationBarsPadding().testTag("taild-dashboard-content"),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
      item {
        Text(
            if (recording) "Analytics recording enabled"
            else "Analytics recording off · retained observations preserved",
            style = MaterialTheme.typography.labelLarge,
        )
        Text(
            "${state.window.from} → ${state.window.until} · UTC, end exclusive",
            style = MaterialTheme.typography.bodySmall,
        )
        Text(
            "Retained observations; incomplete source coverage and gaps remain unknown.",
            style = MaterialTheme.typography.bodySmall,
        )
        state.exportNotice?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        if (state.exportWriting)
            LinearProgressIndicator(
                Modifier.fillMaxWidth().semantics {
                  contentDescription = "Writing selected snapshot"
                }
            )
      }
      if (tab == 0 || tab == 1) {
        item {
          Text(
              "Control D · ${provider.endpointName}${provider.clientName?.let { " / $it" }.orEmpty()}",
              style = MaterialTheme.typography.titleMedium,
          )
          TextButton(onClick = onControlD) { Text("Change endpoint/client or open Recent DNS") }
          if (state.dnsLoading)
              LinearProgressIndicator(
                  Modifier.fillMaxWidth().semantics { contentDescription = "Reading DNS dashboard" }
              )
          state.dnsError?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
            TextButton(onClick = model::retryDns) { Text("Retry DNS query") }
          }
          provider.historyError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
          if (provider.busyHistory)
              Text(
                  provider.historyProgress
                      ?: "Provider history synchronization is running in the app.",
                  style = MaterialTheme.typography.bodySmall,
              )
          Text(provider.page.coverage, style = MaterialTheme.typography.bodySmall)
        }
        val data = state.dns?.takeIf { it.binding == provider.binding }
        if (data != null) {
          if (tab == 0) {
            item {
              TextButton(onClick = { model.dnsDetails(data) }) {
                Text(
                    "${data.total} stored DNS observations",
                    style = MaterialTheme.typography.headlineSmall,
                )
              }
              Text(
                  "Snapshot through ${data.window.until} UTC",
                  style = MaterialTheme.typography.bodySmall,
              )
              val decisions = remember(data) { data.decisions }
              FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                decisions.forEach { (label, count) ->
                  OutlinedButton(
                      onClick = { model.dnsDetails(data, DashboardDnsFilter(decision = label)) }
                  ) {
                    Text("$label · $count")
                  }
                }
              }
              if (data.total == 0L)
                  Text(
                      "No stored observations in this scope/window. This is not proof of no DNS activity."
                  )
              DnsTrend(data) { from, until ->
                model.dnsDetails(data, DashboardDnsFilter(bucketFrom = from, bucketUntil = until))
              }
            }
            item {
              Ranking("Top domains", remember(data) { data.domains }) {
                model.dnsDetails(data, DashboardDnsFilter(domain = it))
              }
              Ranking("Reported reasons", remember(data) { data.reasons }) {
                model.dnsDetails(data, DashboardDnsFilter(reason = it))
              }
              TextButton(
                  onClick = { exportDns(data, DashboardDnsFilter()) },
                  enabled = !state.exportPending && !state.exportWriting,
              ) {
                Text("Export scoped DNS snapshot")
              }
            }
          } else
              item {
                Text("Provider DNS-answer geography", style = MaterialTheme.typography.titleLarge)
                Text(
                    "Country coverage · ${data.countryCoverage} / ${data.total}\nASN coverage · ${data.asnCoverage} / ${data.total}"
                )
                Text(
                    "Each observation counts in every returned answer group; groups may overlap. Missing geography stays Unknown.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Ranking("Answer countries", remember(data) { data.countries }) {
                  model.dnsDetails(data, DashboardDnsFilter(country = it))
                }
                Ranking("Answer ASNs", remember(data) { data.asns }) {
                  model.dnsDetails(data, DashboardDnsFilter(asn = it))
                }
              }
        }
      }
      if (tab == 0 || tab == 2)
          item {
            Text("Observed Tailscale / TailDrop", style = MaterialTheme.typography.titleMedium)
            if (state.activityLoading)
                LinearProgressIndicator(
                    Modifier.fillMaxWidth().semantics {
                      contentDescription = "Reading local activity dashboard"
                    }
                )
            state.activityError?.let {
              Text(it, color = MaterialTheme.colorScheme.error)
              TextButton(onClick = model::retryActivity) { Text("Retry activity query") }
            }
            state.activity?.let { data ->
              TextButton(onClick = { model.activityDetails(data) }) {
                Text(
                    "${data.rows.size} local observations",
                    style = MaterialTheme.typography.titleLarge,
                )
              }
              Text(
                  "Snapshot through ${data.window.until} UTC. Local baselines and gaps are retained; unseen events remain unknown.",
                  style = MaterialTheme.typography.bodySmall,
              )
              if (tab == 2)
                  Ranking("Recorded event kinds", remember(data) { data.kinds }) {
                    model.activityDetails(data, it)
                  }
              FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(
                        "taildrop.sent" to "Outgoing results",
                        "taildrop.received" to "Daemon receipts",
                        "taildrop.saved" to "Document saves",
                    )
                    .forEach { (kind, label) ->
                      OutlinedButton(onClick = { model.activityDetails(data, kind) }) {
                        Text("$label · ${data.kinds[kind] ?: 0}")
                      }
                    }
              }
              TextButton(
                  onClick = { exportActivity(data, null, "") },
                  enabled = !state.exportPending && !state.exportWriting,
              ) {
                Text("Export scoped local observations")
              }
            }
          }
      if (tab == 3) item { TailDSourceHealth(controlD, history, onPreferences) }
    }
  }
  val dnsDetails = state.dnsDetails?.takeIf { it.binding == provider.binding }
  val activityDetails = state.activityDetails
  if (dnsDetails != null || activityDetails != null) {
    val matchingDns by
        produceState<List<ControlDStoredFact>?>(null, dnsDetails, state.dnsFilter) {
          value = null
          if (dnsDetails != null)
              value = withContext(Dispatchers.Default) { dnsDetails.filtered(state.dnsFilter) }
        }
    val matchingActivity by
        produceState<List<RecordedActivity>?>(
            null,
            activityDetails,
            state.activityKind,
            state.activitySearch,
        ) {
          value = null
          if (activityDetails != null)
              value =
                  withContext(Dispatchers.Default) {
                    activityDetails.filtered(state.activityKind, state.activitySearch)
                  }
        }
    ModalBottomSheet(
        onDismissRequest = model::dismissDetails,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        modifier = Modifier.semantics { testTagsAsResourceId = true },
    ) {
      LazyColumn(
          Modifier.fillMaxHeight(.9f)
              .imePadding()
              .padding(horizontal = 16.dp)
              .testTag("taild-dashboard-details")
      ) {
        item {
          Text(
              if (dnsDetails != null) "DNS observations" else "Local observations",
              style = MaterialTheme.typography.titleLarge,
          )
          val window = dnsDetails?.window ?: activityDetails!!.window
          Text(
              "${window.from} → ${window.until} UTC · end exclusive",
              style = MaterialTheme.typography.bodySmall,
          )
          OutlinedTextField(
              value = if (dnsDetails != null) state.dnsFilter.search else state.activitySearch,
              onValueChange = model::searchDetails,
              label = { Text("Search selected facts") },
              modifier = Modifier.fillMaxWidth(),
              singleLine = true,
          )
          val ready = if (dnsDetails != null) matchingDns != null else matchingActivity != null
          Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                if (!ready) "Filtering…"
                else "${matchingDns?.size ?: matchingActivity?.size ?: 0} matching observations",
                Modifier.weight(1f),
            )
            TextButton(
                onClick = {
                  if (dnsDetails != null) exportDns(dnsDetails, state.dnsFilter)
                  else exportActivity(activityDetails!!, state.activityKind, state.activitySearch)
                },
                enabled = ready && !state.exportPending && !state.exportWriting,
            ) {
              Text("Export")
            }
            TextButton(onClick = model::dismissDetails) { Text("Close") }
          }
          if (!ready) LinearProgressIndicator(Modifier.fillMaxWidth())
        }

        items(matchingDns.orEmpty(), key = { it.key }) { row ->
          Text(row.fact.question, style = MaterialTheme.typography.titleMedium)
          Text(
              "${row.fact.at} UTC · ${row.fact.type}\n${row.fact.decision} · ${row.fact.reason}",
              style = MaterialTheme.typography.bodySmall,
          )
          HorizontalDivider()
        }
        items(matchingActivity.orEmpty(), key = { it.id }) { row ->
          Text(row.event.subject, style = MaterialTheme.typography.titleMedium)
          Text(
              "${Instant.ofEpochMilli(row.at)} UTC · ${row.event.kind}\n${row.event.detail}",
              style = MaterialTheme.typography.bodySmall,
          )
          HorizontalDivider()
        }
      }
    }
  }
  if (about) TailDAboutDialog(controlD, history, onPreferences) { about = false }
}

@Composable
private fun Ranking(title: String, values: Map<String, Long>, onSelect: (String) -> Unit) {
  Text(title, style = MaterialTheme.typography.titleMedium)
  values.entries.take(10).forEach { (label, count) ->
    ListItem(
        headlineContent = { Text(label) },
        trailingContent = { Text(count.toString()) },
        modifier =
            Modifier.fillMaxWidth().clickable(onClickLabel = "Show observations for $label") {
              onSelect(label)
            },
    )
  }
  if (values.isEmpty())
      Text("No stored groups in this window.", style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun DnsTrend(data: DashboardDnsSnapshot, onSelect: (Instant, Instant) -> Unit) {
  val hourly = java.time.Duration.between(data.window.from, data.window.until).toHours() <= 24
  val buckets =
      remember(data, hourly) {
        val counts =
            if (hourly) data.hourly
            else
                data.days
                    .mapKeys {
                      java.time.LocalDate.parse(it.key).atStartOfDay(ZoneOffset.UTC).toInstant()
                    }
                    .mapValues { it.value.toInt() }
        val result = mutableListOf<Pair<Instant, Int>>()
        var at =
            if (hourly) data.window.from.truncatedTo(ChronoUnit.HOURS)
            else
                data.window.from
                    .atZone(ZoneOffset.UTC)
                    .toLocalDate()
                    .atStartOfDay(ZoneOffset.UTC)
                    .toInstant()
        while (at < data.window.until) {
          result += at to (counts[at] ?: 0)
          at = at.plus(1, if (hourly) ChronoUnit.HOURS else ChronoUnit.DAYS)
        }
        result
      }
  val maximum = buckets.maxOfOrNull { it.second }?.coerceAtLeast(1) ?: 1
  val formatter =
      remember(hourly) {
        DateTimeFormatter.ofPattern(if (hourly) "HH:mm" else "MMM d").withZone(ZoneOffset.UTC)
      }
  Text(
      if (hourly) "Hourly stored DNS observations · UTC" else "Daily stored DNS observations · UTC",
      style = MaterialTheme.typography.titleMedium,
  )
  Row(
      Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
      horizontalArrangement = Arrangement.spacedBy(8.dp),
  ) {
    buckets.forEach { (at, count) ->
      val until = at.plus(1, if (hourly) ChronoUnit.HOURS else ChronoUnit.DAYS)
      Column(
          Modifier.width(64.dp)
              .clickable { onSelect(at, until) }
              .semantics {
                contentDescription = "$at UTC: $count stored DNS observations; gaps remain unknown"
              },
          horizontalAlignment = Alignment.CenterHorizontally,
      ) {
        Text(count.toString(), style = MaterialTheme.typography.labelSmall)
        Box(Modifier.height(96.dp).fillMaxWidth(), contentAlignment = Alignment.BottomCenter) {
          Surface(
              Modifier.width(32.dp).height((96f * count / maximum).dp),
              color = MaterialTheme.colorScheme.primary,
          ) {}
        }
        Text(formatter.format(at), style = MaterialTheme.typography.labelSmall)
      }
    }
  }
  Text(
      "A zero is zero stored observations; source gaps remain unknown.",
      style = MaterialTheme.typography.bodySmall,
  )
}

@Composable
fun TailDSourceHealth(controlD: ControlDModel, history: TailDHistory, onPreferences: () -> Unit) {
  val provider by controlD.state.collectAsState()
  val recording by history.enabled.collectAsState()
  val error by history.error.collectAsState()
  Text("History & source health", style = MaterialTheme.typography.titleLarge)
  Text("Retention · 7 days\nRecording · ${if(recording) "Enabled" else "Disabled"}")
  TextButton(onClick = onPreferences) { Text("Collection preferences") }
  Text("Observed Tailscale / TailDrop", style = MaterialTheme.typography.titleMedium)
  Text(
      error
          ?: "Records only what the existing app/VPN notification bus observes. Baselines and gaps are explicit."
  )
  Text("Control D DNS", style = MaterialTheme.typography.titleMedium)
  Text(
      "READ access · ${if(provider.hasRead) "Configured" else "Not configured"}\nSeparate Write access · ${if(provider.hasWrite) "Configured" else "Not configured"}"
  )
  Text(
      "Selected endpoint · ${provider.endpointName}${provider.clientName?.let {" / $it"}.orEmpty()}"
  )
  Text("Last stored read · ${provider.page.lastRead?.toString() ?: "None in this scope"}")
  Text(provider.page.coverage)
  Text(provider.resolverNotice)
  if (provider.busyHistory)
      Text(provider.historyProgress ?: "Provider history synchronization in progress")
  provider.historyError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
  provider.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
  Text(
      "History capture and API management preserve your existing VPN and DNS ownership.",
      style = MaterialTheme.typography.bodySmall,
  )
}

@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun TailDAboutDialog(
    controlD: ControlDModel,
    history: TailDHistory,
    onPreferences: () -> Unit,
    onClose: () -> Unit,
) {
  AlertDialog(
      onDismissRequest = onClose,
      modifier = Modifier.semantics { testTagsAsResourceId = true },
      title = { Text("About TailD") },
      text = {
        LazyColumn(
            Modifier.heightIn(max = 440.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
          item {
            Text("Independent TailDNS fork · native device control and private local analytics")
          }
          item {
            TailDSourceHealth(controlD, history) {
              onClose()
              onPreferences()
            }
          }
        }
      },
      confirmButton = { TextButton(onClick = onClose) { Text("Close") } },
  )
}
