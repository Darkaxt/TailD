// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.app.AppOpsManager
import android.app.usage.NetworkStats
import android.app.usage.NetworkStatsManager
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.tailscale.ipn.ui.theme.searchBarColors
import java.time.Instant
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

internal data class AppUsageRow(
    val uid: Int,
    val sent: Long,
    val received: Long,
    val labels: List<String> = emptyList(),
)

internal data class AppUsageSnapshot(
    val at: Long,
    val rows: List<AppUsageRow>,
    val coverage: String,
    val buckets: String = "[]",
) {
  fun export(): String =
      org.json
          .JSONObject()
          .put("source", "Android NetworkStatsManager summary")
          .put("readAt", at)
          .put("coverage", coverage)
          .put("buckets", org.json.JSONArray(buckets))
          .put(
              "rows",
              org.json.JSONArray(
                  rows.map {
                    org.json
                        .JSONObject()
                        .put("uid", it.uid)
                        .put("sent", it.sent)
                        .put("received", it.received)
                        .put("currentPackageLabels", org.json.JSONArray(it.labels))
                  }
              ),
          )
          .toString()
}

/** Public OS accounting is read on explicit view refresh, separately from observed VPN packets. */
@Suppress("DEPRECATION")
internal fun readAppUsage(context: Context, from: Long, until: Long): AppUsageSnapshot {
  val at = System.currentTimeMillis()
  val op = context.getSystemService(AppOpsManager::class.java)
  val mode =
      if (Build.VERSION.SDK_INT >= 29)
          op.unsafeCheckOpNoThrow(
              AppOpsManager.OPSTR_GET_USAGE_STATS,
              android.os.Process.myUid(),
              context.packageName,
          )
      else
          op.checkOpNoThrow(
              AppOpsManager.OPSTR_GET_USAGE_STATS,
              android.os.Process.myUid(),
              context.packageName,
          )
  if (mode != AppOpsManager.MODE_ALLOWED)
      return AppUsageSnapshot(
          at,
          emptyList(),
          "Usage Access not granted. Broader OS app totals are unavailable.",
      )
  val manager = context.getSystemService(NetworkStatsManager::class.java)
  val rows = mutableMapOf<Int, AppUsageRow>()
  val buckets = org.json.JSONArray()
  val unavailable = mutableListOf<String>()
  for ((type, label) in
      listOf(
          ConnectivityManager.TYPE_WIFI to "Wi-Fi",
          ConnectivityManager.TYPE_MOBILE to "Mobile",
      )) {
    if (type == ConnectivityManager.TYPE_MOBILE && Build.VERSION.SDK_INT < 29) {
      unavailable += "$label unsupported without subscriber access"
      continue
    }
    try {
      manager.querySummary(type, null, from, until).use { stats ->
        val bucket = NetworkStats.Bucket()
        while (stats.hasNextBucket()) {
          stats.getNextBucket(bucket)
          buckets.put(
              org.json
                  .JSONObject()
                  .put("networkType", label)
                  .put("uid", bucket.uid)
                  .put("start", bucket.startTimeStamp)
                  .put("end", bucket.endTimeStamp)
                  .put("state", bucket.state)
                  .put("metered", bucket.metered)
                  .put("roaming", bucket.roaming)
                  .put("tag", bucket.tag)
                  .put("sent", bucket.txBytes)
                  .put("received", bucket.rxBytes)
          )
          val prior = rows[bucket.uid] ?: AppUsageRow(bucket.uid, 0, 0)
          rows[bucket.uid] =
              prior.copy(
                  sent = prior.sent + bucket.txBytes,
                  received = prior.received + bucket.rxBytes,
              )
        }
      }
    } catch (_: Exception) {
      unavailable += "$label accounting unavailable"
    }
  }
  return AppUsageSnapshot(
      at,
      rows.values
          .map { row ->
            row.copy(
                labels =
                    context.packageManager.getPackagesForUid(row.uid).orEmpty().sorted().map { name
                      ->
                      try {
                        context.packageManager
                            .getApplicationInfo(name, 0)
                            .loadLabel(context.packageManager)
                            .toString()
                      } catch (_: android.content.pm.PackageManager.NameNotFoundException) {
                        "Package changed"
                      }
                    }
            )
          }
          .sortedByDescending { it.sent + it.received },
      "OS Wi-Fi/mobile estimates for the requested interval; coarse counters may be prorated and may lag. Returned summary bounds do not expose the underlying bucket resolution. Current UID/package labels do not prove historical ownership. VPN-owner and app accounting may overlap; never add these totals to VPN observations. " +
          unavailable.joinToString("; "),
      buckets.toString(),
  )
}

@Composable
internal fun TrafficView(
    history: TailDHistory,
    window: DashboardWindow,
    exportNotice: String?,
    onRefresh: () -> Unit,
    onProvider: (TrafficSnapshot) -> Unit,
    onExport: (TrafficSnapshot, String?) -> Unit,
) {
  val context = LocalContext.current
  val focus = LocalFocusManager.current
  var snapshot by remember { mutableStateOf<TrafficSnapshot?>(null) }
  var usage by remember { mutableStateOf<AppUsageSnapshot?>(null) }
  var error by remember { mutableStateOf<String?>(null) }
  var search by remember { mutableStateOf("") }
  var details by remember { mutableStateOf<String?>(null) }
  var coverage by remember { mutableStateOf(false) }
  var osDetails by remember { mutableStateOf(false) }
  val recordingError by history.trafficError.collectAsState()
  val deleted by history.trafficDeletion.collectAsState()
  LaunchedEffect(window, deleted) {
    snapshot = null
    details = null
    error = null
    usage = null
    try {
      val captured =
          history.queryTraffic(
              activityMillisCeiling(window.from),
              activityMillisCeiling(window.until),
          )
      usage =
          if (history.enabled.value)
              withContext(Dispatchers.IO) {
                readAppUsage(
                    context,
                    activityMillisCeiling(window.from),
                    activityMillisCeiling(window.until),
                )
              }
          else
              AppUsageSnapshot(
                  System.currentTimeMillis(),
                  emptyList(),
                  "Collection is off; OS usage was not read.",
              )
      snapshot = captured.copy(osUsage = usage?.export())
    } catch (_: Exception) {
      error = "Traffic history unavailable. Refresh to read again."
    }
  }
  val data = snapshot
  val groups =
      remember(data) {
        val groups =
            data
                ?.rows
                ?.filter { it.bytes > 0 }
                ?.groupBy { it.fact.getJSONObject("identity").toString() }
                ?.toMutableMap() ?: mutableMapOf()
        data?.rows?.forEach { row ->
          row.fact.optJSONObject("dns")?.optJSONObject("queryIdentity")?.toString()?.let {
            groups.putIfAbsent(it, emptyList())
          }
        }
        groups.toMap()
      }
  val detailRows =
      remember(data, details) {
        if (details == null) emptyList()
        else
            data?.rows.orEmpty().filter {
              it.bytes > 0 &&
                  (it.fact.getJSONObject("identity").toString() == details ||
                      it.fact.optJSONObject("dns")?.optJSONObject("queryIdentity")?.toString() ==
                          details)
            }
      }
  LazyColumn(
      Modifier.fillMaxSize().navigationBarsPadding().testTag("taild-traffic-content"),
      contentPadding = PaddingValues(16.dp),
      verticalArrangement = Arrangement.spacedBy(12.dp),
  ) {
    item {
      OutlinedTextField(
          search,
          { search = it },
          Modifier.fillMaxWidth().testTag("taild-traffic-search"),
          singleLine = true,
          keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
          keyboardActions = KeyboardActions(onDone = { focus.clearFocus() }),
          placeholder = { Text("App / domain / IP") },
          shape = MaterialTheme.shapes.extraLarge,
          colors = MaterialTheme.colorScheme.searchBarColors,
          leadingIcon = { Icon(Icons.Outlined.Search, "Search traffic") },
      )
      if (data == null && error == null) LinearProgressIndicator(Modifier.fillMaxWidth())
      error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
      recordingError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
      if (data != null) {
        Text(
            "${trafficBytes(data.received)} received · ${trafficBytes(data.sent)} sent",
            style = MaterialTheme.typography.titleLarge,
        )
        Text("Observed VPN traffic · this device", style = MaterialTheme.typography.labelLarge)
        TextButton(onClick = { coverage = !coverage }) { Text("Coverage & details") }
        if (coverage) {
          Text(data.coverage, style = MaterialTheme.typography.bodySmall)
          Text(
              "${Instant.ofEpochMilli(data.from)} → ${Instant.ofEpochMilli(data.until)} · UTC, end exclusive\n${data.boundaryBytes} bytes in overlapping boundary buckets",
              style = MaterialTheme.typography.bodySmall,
          )
          val sessions = org.json.JSONArray(data.sessions)
          for (i in 0 until sessions.length()) {
            val session = sessions.getJSONObject(i)
            Text(
                "Last recorded metadata loss · dropped: ${session.getLong("droppedMetadataRecords")} · unacknowledged: ${session.getLong("unacknowledgedMetadataRecords")}",
                style = MaterialTheme.typography.bodySmall,
            )
          }
        }
        if (data.rows.isEmpty())
            Text("No retained VPN packets in this period. This does not prove no traffic.")
        TextButton(onClick = { onExport(data, details) }) { Text("Export selected snapshot") }
        exportNotice?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
      }
    }
    items(
        groups.entries
            .filter { entry ->
              (details == null || entry.key == details) &&
                  (entry.key.contains(search, true) ||
                      entry.value.any { it.metadata.contains(search, true) })
            }
            .sortedByDescending { it.value.sumOf { row -> row.bytes } },
        key = { it.key },
    ) { entry ->
      val rows = entry.value
      val identity = org.json.JSONObject(entry.key)
      val uid = identity.getInt("uid")
      Column(
          Modifier.fillMaxWidth()
              .clickable { details = if (details == entry.key) null else entry.key }
              .testTag("taild-traffic-app-$uid")
      ) {
        Text(identity.getString("label"), style = MaterialTheme.typography.titleMedium)
        Text(
            "UID $uid · ${trafficBytes(rows.filter {!it.upload}.sumOf {it.bytes})} received · ${trafficBytes(rows.filter {it.upload}.sumOf {it.bytes})} sent"
        )
        val blocked =
            data
                ?.rows
                .orEmpty()
                .filter {
                  it.fact.optJSONObject("dns")?.let { dns ->
                    dns.optBoolean("blocked") &&
                        dns.optJSONObject("queryIdentity")?.toString() == entry.key
                  } == true
                }
                .sumOf { it.packets }
        if (blocked > 0)
            Text(
                "$blocked observed resolver-block responses",
                style = MaterialTheme.typography.labelLarge,
            )
        if (details == entry.key) {
          TextButton(onClick = { onProvider(checkNotNull(data)) }) {
            Text("Cross-check Control D history for this period")
          }
          Text(
              "Provider history remains endpoint/client scoped; it is not an app block log.",
              style = MaterialTheme.typography.bodySmall,
          )
        }
      }
      HorizontalDivider()
    }
    items(detailRows, key = { it.metadata }) { row ->
      val fact = row.fact
      Column {
        Text(
            "${fact.optString("remote","Unknown IP")}:${fact.optInt("remotePort")} · ${if(fact.optInt("protocol")==6) "TCP" else if(fact.optInt("protocol")==17) "UDP" else "IP ${fact.optInt("protocol")}"} · ${trafficBytes(row.bytes)}",
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(
            "Bytes owner UID ${row.uid} · ${Instant.ofEpochMilli(row.first)}",
            style = MaterialTheme.typography.bodySmall,
        )
        val dns = fact.optJSONObject("dns")
        if (dns != null) {
          val status =
              if (dns.optBoolean("blocked")) "Resolver reports Blocked (EDE)"
              else if (dns.optBoolean("response")) "DNS response ${dns.optInt("code")}"
              else "Observed DNS question"
          Text("${dns.optString("name")} · $status", style = MaterialTheme.typography.bodySmall)
          if (dns.optBoolean("blocked"))
              Text(
                  "Query owner UID ${dns.optInt("queryUid",-1)}; missing/system owners do not identify an app.",
                  style = MaterialTheme.typography.bodySmall,
              )
        }
        val candidates = fact.optJSONArray("candidates") ?: org.json.JSONArray()
        if (candidates.length() == 0)
            Text("Domain unassigned", style = MaterialTheme.typography.bodySmall)
        for (i in 0 until candidates.length()) Text(
            "${candidates.getJSONObject(i).getString("name")} · 1/${candidates.length()} estimate (${row.bytes}/${candidates.length()} bytes)",
            style = MaterialTheme.typography.bodySmall,
        )
        fact
            .optString("unknown")
            .takeIf { it.isNotEmpty() }
            ?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        HorizontalDivider()
      }
    }
    item {
      TextButton(onClick = { osDetails = !osDetails }) { Text("OS app totals") }
      if (osDetails) {
        usage?.let { os ->
          Text(os.coverage, style = MaterialTheme.typography.bodySmall)
          Text("Read ${Instant.ofEpochMilli(os.at)}", style = MaterialTheme.typography.bodySmall)
          for (row in os.rows) Text(
              "${row.labels.joinToString(" / ").ifEmpty { "UID ${row.uid}" }} · ${trafficBytes(row.received)} received · ${trafficBytes(row.sent)} sent",
              style = MaterialTheme.typography.bodySmall,
          )
        }
        TextButton(
            onClick = {
              context.startActivity(
                  Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)
                      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
              )
            }
        ) {
          Text("Manage Usage Access")
        }
        TextButton(onClick = onRefresh) { Text("Refresh snapshot") }
      }
    }
  }
}

internal fun trafficBytes(bytes: Long): String =
    when {
      bytes >= 1024L * 1024 -> "%.1f MiB".format(bytes / (1024.0 * 1024))
      bytes >= 1024 -> "%.1f KiB".format(bytes / 1024.0)
      else -> "$bytes B"
    }
