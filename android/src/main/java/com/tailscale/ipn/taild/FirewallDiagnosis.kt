// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.patrykandpatrick.vico.compose.axis.axisGuidelineComponent
import com.patrykandpatrick.vico.compose.axis.horizontal.rememberBottomAxis
import com.patrykandpatrick.vico.compose.axis.vertical.rememberStartAxis
import com.patrykandpatrick.vico.compose.chart.Chart
import com.patrykandpatrick.vico.compose.chart.column.columnChart
import com.patrykandpatrick.vico.compose.chart.layout.fullWidth
import com.patrykandpatrick.vico.compose.component.lineComponent
import com.patrykandpatrick.vico.compose.component.textComponent
import com.patrykandpatrick.vico.compose.m3.style.m3ChartStyle
import com.patrykandpatrick.vico.compose.style.ProvideChartStyle
import com.patrykandpatrick.vico.core.axis.AxisItemPlacer
import com.patrykandpatrick.vico.core.chart.column.ColumnChart
import com.patrykandpatrick.vico.core.chart.layout.HorizontalLayout
import com.patrykandpatrick.vico.core.entry.FloatEntry
import com.patrykandpatrick.vico.core.entry.entryModelOf
import com.tailscale.ipn.App
import com.tailscale.ipn.R
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import org.json.JSONObject

internal data class FirewallDestination(
    val key: String,
    val address: String,
    val protocol: String,
    val received: Long,
    val sent: Long,
    val candidates: List<String>,
    val rows: List<TrafficRow>,
) {
  val total
    get() = received + sent
}

internal data class FirewallDnsName(
    val name: String,
    val questions: Long,
    val replies: Long,
    val blocked: Long,
    val rows: List<TrafficRow>,
)

/** Candidate names annotate destinations; measured bytes are never duplicated across names. */
internal fun firewallDestinations(
    entry: FirewallTrafficApp,
    rows: List<TrafficRow>,
): List<FirewallDestination> =
    rows
        .groupBy {
          val fact = it.fact
          "${fact.optString("remote", "Unknown IP")}|${fact.optInt("remotePort")}|${fact.optInt("protocol")}"
        }
        .map { (key, grouped) ->
          val fact = grouped.first().fact
          val owned = grouped.filter {
            it.fact.getJSONObject("identity").toString() in entry.recorded
          }
          val names =
              grouped
                  .flatMap { row ->
                    val list = row.fact.optJSONArray("candidates")
                    (0 until (list?.length() ?: 0)).map {
                      list!!.getJSONObject(it).getString("name")
                    }
                  }
                  .distinct()
                  .sorted()
          val ip = fact.optString("remote", "Unknown IP")
          val port = fact.optInt("remotePort")
          FirewallDestination(
              key,
              if (ip.contains(':')) "[$ip]:$port" else "$ip:$port",
              when (val protocol = fact.optInt("protocol")) {
                6 -> "TCP"
                17 -> "UDP"
                else -> "IP $protocol"
              },
              owned.filter { !it.upload }.sumOf { it.bytes },
              owned.filter { it.upload }.sumOf { it.bytes },
              names,
              grouped,
          )
        }
        .sortedWith(compareByDescending<FirewallDestination> { it.total }.thenBy { it.key })

/** Counts observations, not inferred application requests or endpoint-only Control D history. */
internal fun firewallDnsNames(rows: List<TrafficRow>): List<FirewallDnsName> =
    rows
        .filter { it.fact.optJSONObject("dns")?.optString("name").orEmpty().isNotBlank() }
        .groupBy { it.fact.getJSONObject("dns").getString("name") }
        .map { (name, grouped) ->
          FirewallDnsName(
              name,
              grouped
                  .filter { !it.fact.getJSONObject("dns").optBoolean("response") }
                  .sumOf { it.packets },
              grouped
                  .filter { it.fact.getJSONObject("dns").optBoolean("response") }
                  .sumOf { it.packets },
              grouped
                  .filter {
                    val dns = it.fact.getJSONObject("dns")
                    dns.optBoolean("response") && dns.optBoolean("blocked")
                  }
                  .sumOf { it.packets },
              grouped,
          )
        }
        .sortedWith(
            compareByDescending<FirewallDnsName> { it.questions + it.replies }.thenBy { it.name }
        )

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun FirewallDiagnosisView(selection: FirewallDiagnosis, onBack: () -> Unit) {
  val entry = selection.app
  val data = selection.snapshot
  val model = App.get().tailDDashboard
  val context = LocalContext.current
  val compact = LocalConfiguration.current.screenHeightDp < 480
  val exportState by model.state.collectAsState()
  val feedback = remember { SnackbarHostState() }
  val exporter =
      rememberLauncherForActivityResult(
          ActivityResultContracts.CreateDocument("application/json")
      ) {
        model.writeExport(context.contentResolver, it)
      }
  LaunchedEffect(exportState.exportNotice) {
    exportState.exportNotice?.let { notice ->
      feedback.showSnackbar(notice, withDismissAction = true)
      model.dismissExportNotice(notice)
    }
  }
  val relevant =
      remember(selection) {
        data?.rows.orEmpty().filter {
          it.fact.getJSONObject("identity").toString() in entry.recorded ||
              it.fact.optJSONObject("dns")?.optJSONObject("queryIdentity")?.toString() in
                  entry.recorded
        }
      }
  val destinations = remember(selection) { firewallDestinations(entry, relevant) }
  val dns = remember(selection) { firewallDnsNames(relevant) }
  var showDetails by remember(selection) { mutableStateOf(false) }
  var packetRows by remember(selection) { mutableStateOf<List<TrafficRow>?>(null) }
  var dnsTab by remember(selection) { mutableStateOf(false) }
  var alphabetical by remember(selection, dnsTab) { mutableStateOf(false) }
  var expanded by remember(selection, dnsTab) { mutableStateOf<String?>(null) }
  val zone = ZoneId.systemDefault()
  val localTime = remember(zone) { DateTimeFormatter.ofPattern("d MMM, HH:mm z").withZone(zone) }
  Box(Modifier.fillMaxSize()) {
    LazyColumn(
        Modifier.align(Alignment.TopCenter)
            .widthIn(max = 840.dp)
            .fillMaxSize()
            .testTag("taild-app-diagnosis"),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = if (compact) 4.dp else 8.dp),
    ) {
      item(key = "summary") {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
          IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to Firewall")
          }
          Column(Modifier.weight(1f)) {
            Text(
                entry.label,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.titleMedium,
            )
            if (entry.current == null && !compact)
                Text("Previous installation", style = MaterialTheme.typography.labelSmall)
          }
          IconButton(onClick = { showDetails = true }) {
            Icon(Icons.Default.Info, "App & coverage details")
          }
          if (data != null)
              IconButton(
                  onClick = {
                    if (model.prepareTrafficExport(data.copy(rows = relevant), null))
                        exporter.launch("TailD-app-traffic-${data.revision}.json")
                  }
              ) {
                Icon(
                    painterResource(R.drawable.baseline_drive_folder_upload_24),
                    "Export app diagnosis snapshot",
                )
              }
        }
        Row(Modifier.fillMaxWidth().padding(vertical = if (compact) 2.dp else 4.dp)) {
          TrafficTotal("IN", entry.received, Modifier.weight(1f), false, compact)
          TrafficTotal("OUT", entry.sent, Modifier.weight(1f), true, compact)
        }
        Text(
            if (compact && entry.current == null) "Last 24 hours · previous installation · VPN"
            else "Last 24 hours · hourly VPN traffic",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        DiagnosisHourlyChart(entry, data, relevant, compact)
        SecondaryTabRow(selectedTabIndex = if (dnsTab) 1 else 0) {
          Tab(
              selected = !dnsTab,
              onClick = { dnsTab = false },
              text = { Text("Destinations (${destinations.size})") },
          )
          Tab(selected = dnsTab, onClick = { dnsTab = true }, text = { Text("DNS (${dns.size})") })
        }
        val sortLabel =
            if (alphabetical) "Name A–Z ↑" else if (dnsTab) "Most seen ↓" else "Traffic ↓"
        if (dnsTab)
            TableHeading(
                listOf(sortLabel, "Asked", "Replies", "Blocked"),
                listOf(.43f, .19f, .19f, .19f),
                onSort = { alphabetical = !alphabetical },
            )
        else
            TableHeading(
                listOf(sortLabel, "IN", "OUT"),
                listOf(.50f, .25f, .25f),
                onSort = { alphabetical = !alphabetical },
            )
      }
      if (dnsTab) {
        val sorted = if (alphabetical) dns.sortedBy { it.name.lowercase(Locale.ROOT) } else dns
        if (sorted.isEmpty())
            item { EmptyDiagnosis("No app-attributed DNS observations in this day.") }
        items(sorted, key = { "dns:${it.name}" }) { row ->
          Column(
              Modifier.fillMaxWidth()
                  .testTag("taild-diagnosis-dns-row")
                  .clickable { expanded = if (expanded == row.name) null else row.name }
                  .padding(vertical = if (compact) 4.dp else 8.dp)
                  .heightIn(min = 48.dp)
          ) {
            TableValues(
                listOf(row.name, "${row.questions}", "${row.replies}", "${row.blocked}"),
                listOf(.43f, .19f, .19f, .19f),
            )
            LinearProgressIndicator(
                progress = {
                  ((row.questions + row.replies).toFloat() /
                          (dns.maxOfOrNull { it.questions + it.replies } ?: 1).coerceAtLeast(1))
                      .coerceIn(0f, 1f)
                },
                modifier = Modifier.fillMaxWidth(.43f).height(3.dp).padding(top = 1.dp),
                color =
                    if (row.blocked > 0) MaterialTheme.colorScheme.error
                    else MaterialTheme.colorScheme.primary,
            )
          }
          if (expanded == row.name)
              DiagnosisObservations(
                  row.rows,
                  "DNS packets; blocked counts are observed EDE replies.",
                  onPackets = { packetRows = it },
              )
          HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
      } else {
        val sorted =
            if (alphabetical) destinations.sortedBy { it.address.lowercase(Locale.ROOT) }
            else destinations
        if (sorted.isEmpty()) item { EmptyDiagnosis("No retained destinations in this day.") }
        items(sorted, key = { "ip:${it.key}" }) { row ->
          Column(
              Modifier.fillMaxWidth()
                  .testTag("taild-diagnosis-destination-row")
                  .clickable { expanded = if (expanded == row.key) null else row.key }
                  .padding(vertical = if (compact) 4.dp else 8.dp)
                  .heightIn(min = 48.dp)
          ) {
            TableValues(
                listOf(row.address, trafficBytes(row.received), trafficBytes(row.sent)),
                listOf(.50f, .25f, .25f),
            )
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
              Text(
                  if (row.candidates.isEmpty()) row.protocol
                  else "${row.protocol} · ≈ ${row.candidates.joinToString()}",
                  Modifier.weight(1f),
                  maxLines = 1,
                  overflow = TextOverflow.Ellipsis,
                  style = MaterialTheme.typography.labelSmall,
                  color = MaterialTheme.colorScheme.onSurfaceVariant,
              )
              if (row.total == 0L) Text("DNS context", style = MaterialTheme.typography.labelSmall)
            }
            LinearProgressIndicator(
                progress = {
                  (row.total.toFloat() /
                          (destinations.maxOfOrNull { it.total } ?: 1).coerceAtLeast(1))
                      .coerceIn(0f, 1f)
                },
                modifier = Modifier.fillMaxWidth().height(3.dp),
            )
          }
          if (expanded == row.key)
              DiagnosisObservations(
                  row.rows,
                  if (row.candidates.isEmpty()) "No observed domain candidate for this destination."
                  else
                      "Domain candidates: ${row.candidates.joinToString()}. Equal-weight estimates; these are measured IP bytes, not exact domain totals.",
                  onPackets = { packetRows = it },
              )
          HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
      }
    }
    SnackbarHost(feedback, Modifier.align(Alignment.BottomCenter))
  }
  packetRows?.let { records ->
    AlertDialog(
        onDismissRequest = { packetRows = null },
        title = { Text("Packet records (${records.size})") },
        text = {
          LazyColumn(Modifier.heightIn(max = 480.dp)) {
            items(records, key = { it.metadata }) { TrafficFactContent(it) }
          }
        },
        confirmButton = { TextButton(onClick = { packetRows = null }) { Text("Close") } },
    )
  }
  if (showDetails)
      AlertDialog(
          modifier = Modifier.testTag("taild-firewall-details"),
          onDismissRequest = { showDetails = false },
          title = { Text("App details") },
          text = {
            Column(
                Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
              Text(
                  if (entry.current == null) "Previous installation" else "Current installation",
                  style = MaterialTheme.typography.titleSmall,
              )
              val identities = entry.recorded.map(::JSONObject)
              val current = entry.current
              if (current != null) {
                Text("UID ${current.uid} · Profile ${current.profile}")
                current.packages.forEach { pkg ->
                  Text(pkg.name, style = MaterialTheme.typography.titleSmall)
                  Text(
                      "Version code ${pkg.version}\nInstalled ${Instant.ofEpochMilli(pkg.installed)}\nUpdated ${Instant.ofEpochMilli(pkg.updated)}",
                      style = MaterialTheme.typography.bodySmall,
                  )
                  pkg.signers.forEach {
                    Text("Signer SHA-256 $it", style = MaterialTheme.typography.bodySmall)
                  }
                }
              } else
                  identities.forEach { identity ->
                    Text("UID ${identity.optInt("uid", -1)}")
                    val packages = identity.optJSONArray("packages")
                    (0 until (packages?.length() ?: 0)).forEach { i ->
                      val pkg = packages!!.getJSONObject(i)
                      Text(pkg.optString("package"), style = MaterialTheme.typography.titleSmall)
                      Text(
                          "Version code ${pkg.optLong("versionCode")}\nInstalled ${Instant.ofEpochMilli(pkg.optLong("firstInstallTime"))}\nUpdated ${Instant.ofEpochMilli(pkg.optLong("lastUpdateTime"))}",
                          style = MaterialTheme.typography.bodySmall,
                      )
                      Text(
                          "Signer SHA-256 ${pkg.optJSONArray("signerSha256")}",
                          style = MaterialTheme.typography.bodySmall,
                      )
                    }
                  }
              HorizontalDivider()
              var hours by remember { mutableStateOf(false) }
              TextButton(onClick = { hours = !hours }) { Text("Hourly totals") }
              if (hours) {
                val owned = relevant.filter {
                  it.fact.getJSONObject("identity").toString() in entry.recorded
                }
                val received = hourlyTraffic(owned.filter { !it.upload }, data)
                val sent = hourlyTraffic(owned.filter { it.upload }, data)
                TableHeading(listOf("Hour", "IN", "OUT"), listOf(.46f, .27f, .27f))
                received.forEachIndexed { i, (hour, bytes) ->
                  TableValues(
                      listOf(
                          localTime.format(Instant.ofEpochMilli(hour)),
                          trafficBytes(bytes),
                          trafficBytes(sent[i].second),
                      ),
                      listOf(.46f, .27f, .27f),
                  )
                }
              }
              Text("Local timezone: $zone", style = MaterialTheme.typography.bodySmall)
              Text("Coverage", style = MaterialTheme.typography.titleSmall)
              Text(
                  data?.coverage ?: "Snapshot unavailable",
                  style = MaterialTheme.typography.bodySmall,
              )
              Text(
                  "Resolver context owned by another UID is excluded from this app's byte totals. Control D endpoint history alone does not identify an APK.",
                  style = MaterialTheme.typography.bodySmall,
              )
              data?.let {
                Text(
                    "${Instant.ofEpochMilli(it.from)} → ${Instant.ofEpochMilli(it.until)} UTC\n${it.boundaryBytes} unallocated boundary bytes · revision ${it.revision}\n${it.sessions}",
                    style = MaterialTheme.typography.bodySmall,
                )
              }
            }
          },
          confirmButton = { TextButton(onClick = { showDetails = false }) { Text("Close") } },
      )
}

@Composable
private fun TrafficTotal(
    label: String,
    bytes: Long,
    modifier: Modifier,
    sent: Boolean,
    compact: Boolean,
) {
  val color = if (sent) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.primary
  if (compact)
      Row(
          modifier,
          horizontalArrangement = Arrangement.spacedBy(8.dp),
          verticalAlignment = Alignment.CenterVertically,
      ) {
        Text(label, color = color, style = MaterialTheme.typography.bodySmall)
        Text(
            trafficBytes(bytes),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
        )
      }
  else
      Column(modifier) {
        Text(label, color = color, style = MaterialTheme.typography.labelMedium)
        Text(
            trafficBytes(bytes),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
        )
      }
}

@Composable
private fun DiagnosisHourlyChart(
    entry: FirewallTrafficApp,
    data: TrafficSnapshot?,
    rows: List<TrafficRow>,
    compact: Boolean,
) {
  val owned =
      remember(entry, rows) {
        rows.filter { it.fact.getJSONObject("identity").toString() in entry.recorded }
      }
  val received = remember(owned, data) { hourlyTraffic(owned.filter { !it.upload }, data) }
  val sent = remember(owned, data) { hourlyTraffic(owned.filter { it.upload }, data) }
  if (received.isEmpty()) {
    EmptyDiagnosis("Hourly traffic unavailable")
    return
  }
  val peak = entry.hourly.maxByOrNull { it.second }
  val format = DateTimeFormatter.ofPattern("HH:mm").withZone(ZoneId.systemDefault())
  val description =
      if (peak == null || peak.second == 0L) "Hourly observed traffic: no recorded bytes"
      else
          "Hourly observed traffic; peak ${format.format(Instant.ofEpochMilli(peak.first))}, ${trafficBytes(peak.second)}"
  if (entry.total == 0L) {
    Box(
        Modifier.fillMaxWidth().height(64.dp).testTag("taild-diagnosis-hourly-chart").semantics {
          contentDescription = description
        },
        contentAlignment = Alignment.CenterStart,
    ) {
      Text(
          "No recorded traffic",
          style = MaterialTheme.typography.bodySmall,
          color = MaterialTheme.colorScheme.onSurfaceVariant,
      )
    }
    return
  }
  val chartModel =
      remember(received, sent) {
        entryModelOf(
            received.mapIndexed { i, (_, bytes) -> FloatEntry(i.toFloat(), bytes.toFloat()) },
            sent.mapIndexed { i, (_, bytes) -> FloatEntry(i.toFloat(), bytes.toFloat()) },
        )
      }
  ProvideChartStyle(m3ChartStyle()) {
    Chart(
        chart =
            columnChart(
                columns =
                    listOf(
                        lineComponent(MaterialTheme.colorScheme.primary, 7.dp),
                        lineComponent(MaterialTheme.colorScheme.tertiary, 7.dp),
                    ),
                mergeMode = ColumnChart.MergeMode.Stack,
                spacing = 2.dp,
            ),
        model = chartModel,
        modifier =
            Modifier.fillMaxWidth()
                .height(if (compact) 88.dp else 132.dp)
                .padding(top = 4.dp)
                .testTag("taild-diagnosis-hourly-chart")
                .semantics { contentDescription = description },
        isZoomEnabled = false,
        horizontalLayout = HorizontalLayout.fullWidth(),
        startAxis =
            rememberStartAxis(
                valueFormatter = { value, _ -> trafficBytes(value.toLong()) },
                itemPlacer =
                    remember(compact) {
                      AxisItemPlacer.Vertical.default(maxItemCount = if (compact) 2 else 3)
                    },
                label =
                    textComponent(
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textSize = 11.sp,
                    ),
                guideline =
                    axisGuidelineComponent(color = MaterialTheme.colorScheme.outlineVariant),
            ),
        bottomAxis =
            rememberBottomAxis(
                itemPlacer =
                    remember {
                      AxisItemPlacer.Horizontal.default(spacing = 6, addExtremeLabelPadding = true)
                    },
                valueFormatter = { value, _ ->
                  DateTimeFormatter.ofPattern("HH")
                      .withZone(ZoneId.systemDefault())
                      .format(
                          Instant.ofEpochMilli(
                              received[value.toInt().coerceIn(received.indices)].first
                          )
                      )
                },
                label =
                    textComponent(
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textSize = 11.sp,
                    ),
                guideline = null,
            ),
    )
  }
}

@Composable
private fun TableHeading(labels: List<String>, widths: List<Float>, onSort: (() -> Unit)? = null) {
  Row(
      Modifier.fillMaxWidth()
          .background(MaterialTheme.colorScheme.surfaceContainerHighest)
          .padding(vertical = if (onSort == null) 8.dp else 0.dp)
          .testTag("taild-diagnosis-table-heading")
  ) {
    labels.forEachIndexed { i, text ->
      if (i == 0 && onSort != null)
          TextButton(onClick = onSort, modifier = Modifier.weight(widths[i])) {
            Text(text, style = MaterialTheme.typography.labelSmall)
          }
      else
          Box(
              Modifier.weight(widths[i])
                  .align(Alignment.CenterVertically)
                  .padding(horizontal = 4.dp)
          ) {
            Text(
                text,
                Modifier.fillMaxWidth(),
                textAlign = if (i == 0) TextAlign.Start else TextAlign.End,
                style = MaterialTheme.typography.labelSmall,
            )
          }
    }
  }
}

@Composable
private fun TableValues(values: List<String>, widths: List<Float>) {
  Row(Modifier.fillMaxWidth()) {
    values.forEachIndexed { i, text ->
      Text(
          text,
          Modifier.weight(widths[i]).padding(horizontal = 4.dp),
          textAlign = if (i == 0) TextAlign.Start else TextAlign.End,
          style = MaterialTheme.typography.bodySmall,
      )
    }
  }
}

@Composable
private fun EmptyDiagnosis(text: String) {
  Text(
      text,
      Modifier.padding(vertical = 16.dp),
      style = MaterialTheme.typography.bodySmall,
      color = MaterialTheme.colorScheme.onSurfaceVariant,
  )
}

@Composable
private fun DiagnosisObservations(
    rows: List<TrafficRow>,
    explanation: String,
    onPackets: (List<TrafficRow>) -> Unit,
) {
  Column(
      Modifier.fillMaxWidth()
          .background(MaterialTheme.colorScheme.surfaceContainerLow)
          .padding(8.dp),
      verticalArrangement = Arrangement.spacedBy(8.dp),
  ) {
    Text(explanation, style = MaterialTheme.typography.bodySmall)
    val time = DateTimeFormatter.ofPattern("d MMM HH:mm:ss z").withZone(ZoneId.systemDefault())
    Text(
        "${rows.sumOf { it.packets }} observed packets\nFirst ${time.format(Instant.ofEpochMilli(rows.minOf { it.first }))}\nLast ${time.format(Instant.ofEpochMilli(rows.maxOf { it.last }))}",
        style = MaterialTheme.typography.bodySmall,
    )
    TextButton(onClick = { onPackets(rows) }) { Text("Packet records (${rows.size})") }
  }
}
