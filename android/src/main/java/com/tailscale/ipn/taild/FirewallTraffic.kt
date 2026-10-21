// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.tailscale.ipn.App
import com.tailscale.ipn.R
import java.time.Instant
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

internal data class FirewallTrafficApp(
    val key: String,
    val label: String,
    val current: AppAccessIdentity?,
    val recorded: Set<String>,
    val sent: Long,
    val received: Long,
    val hourly: List<Pair<Long, Long>> = emptyList(),
) {
  val total
    get() = sent + received
}

/** Storage facts are minute-bounded; clock-hour grouping never splits measured bytes. */
internal fun hourlyTraffic(rows: List<TrafficRow>, data: TrafficSnapshot?): List<Pair<Long, Long>> {
  if (data == null) return emptyList()
  val firstHour = Math.floorDiv(data.from, 3600000L)
  val lastHour = Math.floorDiv(data.until - 1, 3600000L)
  return (firstHour..lastHour).map { hour ->
    hour * 3600000L to rows.filter { Math.floorDiv(it.first, 3600000L) == hour }.sumOf { it.bytes }
  }
}

internal fun trafficIdentityMatches(recorded: JSONObject, app: AppAccessIdentity): Boolean {
  if (recorded.optInt("uid", -1) != app.uid) return false
  val packages = recorded.optJSONArray("packages") ?: return false
  if (packages.length() != app.packages.size || app.packages.isEmpty()) return false
  return app.packages.all { current ->
    (0 until packages.length()).any { i ->
      val old = packages.getJSONObject(i)
      val signers = old.optJSONArray("signerSha256")
      old.optString("package") == current.name &&
          old.optLong("versionCode", -1) == current.version &&
          old.optLong("firstInstallTime", -1) == current.installed &&
          old.optLong("lastUpdateTime", -1) == current.updated &&
          signers != null &&
          current.signers.isNotEmpty() &&
          (0 until signers.length()).map { signers.getString(it) }.sorted() ==
              current.signers.sorted()
    }
  }
}

/** Joins only exact installation generations; UID reuse never relabels old bytes. */
internal fun firewallTrafficApps(
    apps: List<AppAccessIdentity>,
    data: TrafficSnapshot?,
): List<FirewallTrafficApp> {
  val identities = linkedMapOf<String, JSONObject>()
  data?.rows.orEmpty().forEach { row ->
    val fact = row.fact
    listOfNotNull(
            fact.optJSONObject("identity"),
            fact.optJSONObject("dns")?.optJSONObject("queryIdentity"),
        )
        .forEach { identities[it.toString()] = it }
  }
  val unmatched = identities.keys.toMutableSet()
  val identitiesByUid = identities.entries.groupBy { it.value.optInt("uid", -1) }
  val rowsByIdentity = data?.rows.orEmpty().groupBy { it.fact.getJSONObject("identity").toString() }
  val result =
      apps
          .map { app ->
            val keys =
                identitiesByUid[app.uid]
                    .orEmpty()
                    .filter { trafficIdentityMatches(it.value, app) }
                    .map { it.key }
                    .toSet()
            unmatched.removeAll(keys)
            val rows = keys.flatMap { rowsByIdentity[it].orEmpty() }
            FirewallTrafficApp(
                "current:${app.fingerprint}",
                app.packages.joinToString(" / ") { it.label },
                app,
                keys,
                rows.filter { it.upload }.sumOf { it.bytes },
                rows.filter { !it.upload }.sumOf { it.bytes },
                hourlyTraffic(rows, data),
            )
          }
          .toMutableList()
  unmatched.forEach { key ->
    val identity = identities.getValue(key)
    val rows = rowsByIdentity[key].orEmpty()
    result +=
        FirewallTrafficApp(
            "recorded:$key",
            identity.optString("label", "Unassigned app"),
            null,
            setOf(key),
            rows.filter { it.upload }.sumOf { it.bytes },
            rows.filter { !it.upload }.sumOf { it.bytes },
            hourlyTraffic(rows, data),
        )
  }
  return result.sortedWith(
      compareByDescending<FirewallTrafficApp> { it.total }
          .thenBy { it.label.lowercase(Locale.ROOT) }
          .thenBy { it.key }
  )
}

@Suppress("DEPRECATION")
internal fun localFirewallApps(context: Context): List<AppAccessIdentity> {
  val pm = context.packageManager
  return pm.getInstalledPackages(
          if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES
          else PackageManager.GET_SIGNATURES
      )
      .filter { it.applicationInfo?.uid?.rem(100000)?.let { uid -> uid >= 10000 } == true }
      .groupBy { it.applicationInfo!!.uid }
      .map { (uid, packages) ->
        AppAccessIdentity(
            uid,
            packages
                .sortedBy { it.packageName }
                .map { info ->
                  AppAccessPackage(
                      info.packageName,
                      info.applicationInfo!!.loadLabel(pm).toString(),
                      (if (Build.VERSION.SDK_INT >= 28)
                              info.signingInfo?.apkContentsSigners.orEmpty()
                          else info.signatures.orEmpty())
                          .map { signer ->
                            java.security.MessageDigest.getInstance("SHA-256")
                                .digest(signer.toByteArray())
                                .joinToString("") { "%02x".format(it) }
                          }
                          .sorted(),
                      info.firstInstallTime,
                      info.lastUpdateTime,
                      if (Build.VERSION.SDK_INT >= 28) info.longVersionCode
                      else info.versionCode.toLong(),
                  )
                },
        )
      }
}

internal data class FirewallDiagnosis(val app: FirewallTrafficApp, val snapshot: TrafficSnapshot?)

@Composable
internal fun FirewallView(onPreferences: () -> Unit) {
  val context = LocalContext.current
  val app = App.get()
  val history = app.tailDHistory
  var untilMillis by rememberSaveable { mutableLongStateOf(System.currentTimeMillis()) }
  val until = Instant.ofEpochMilli(untilMillis)
  var snapshot by remember { mutableStateOf<TrafficSnapshot?>(null) }
  var installed by remember { mutableStateOf<List<AppAccessIdentity>>(emptyList()) }
  var error by remember { mutableStateOf<String?>(null) }
  var diagnosis by remember { mutableStateOf<FirewallDiagnosis?>(null) }
  var diagnosisKey by rememberSaveable { mutableStateOf<String?>(null) }
  val listState = rememberSaveableStateHolder()
  val deleted by history.trafficDeletion.collectAsState()
  val recording by history.enabled.collectAsState()
  LaunchedEffect(until, deleted) {
    snapshot = null
    diagnosis = null
    error = null
    try {
      installed = withContext(Dispatchers.IO) { localFirewallApps(context) }
      snapshot =
          history.queryTraffic(until.minusSeconds(86400).toEpochMilli(), until.toEpochMilli())
      if (diagnosisKey != null) {
        val apps = app.tailDAppAccess.state.value.snapshot?.apps ?: installed
        diagnosis =
            firewallTrafficApps(apps, snapshot)
                .find { it.key == diagnosisKey }
                ?.let { FirewallDiagnosis(it, snapshot) }
      }
    } catch (_: Exception) {
      error = "App traffic unavailable. Refresh to read again."
    }
  }
  val selection = diagnosis
  if (selection != null) {
    BackHandler {
      diagnosis = null
      diagnosisKey = null
    }
    FirewallDiagnosisView(
        selection,
        onBack = {
          diagnosis = null
          diagnosisKey = null
        },
    )
  } else
      Box(Modifier.fillMaxSize()) {
        Column(Modifier.align(Alignment.TopCenter).widthIn(max = 840.dp).fillMaxSize()) {
          Row(
              Modifier.fillMaxWidth().padding(horizontal = 16.dp),
              verticalAlignment = Alignment.CenterVertically,
          ) {
            Column(Modifier.weight(1f)) {
              Text("Last 24 hours", style = MaterialTheme.typography.titleSmall)
              Text(
                  "Observed VPN traffic · this device",
                  style = MaterialTheme.typography.labelSmall,
              )
            }
            IconButton(
                onClick = {
                  untilMillis = System.currentTimeMillis()
                  if (app.tailDAppAccess.state.value.connected) app.tailDAppAccess.refresh()
                }
            ) {
              Icon(Icons.Default.Refresh, "Refresh app traffic")
            }
          }
          if (!recording)
              TextButton(onClick = onPreferences) { Text("Recording off · open Preferences") }
          error?.let {
            Text(it, Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.error)
          }
          if (snapshot == null && error == null) LinearProgressIndicator(Modifier.fillMaxWidth())
          listState.SaveableStateProvider("firewall-list") {
            AppAccessView(
                installed,
                snapshot,
                onDiagnosis = {
                  diagnosisKey = it.key
                  diagnosis = FirewallDiagnosis(it, snapshot)
                },
            )
          }
        }
      }
}

@Composable
internal fun FirewallDiagnosisView(selection: FirewallDiagnosis, onBack: () -> Unit) {
  val entry = selection.app
  val data = selection.snapshot
  val model = App.get().tailDDashboard
  val context = LocalContext.current
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
  Box(Modifier.fillMaxSize()) {
    LazyColumn(
        Modifier.align(Alignment.TopCenter)
            .widthIn(max = 840.dp)
            .fillMaxSize()
            .testTag("taild-app-diagnosis"),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
      item {
        Row(verticalAlignment = Alignment.CenterVertically) {
          IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back to Firewall")
          }
          Text(entry.label, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
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
        Text(
            if (data == null) "Traffic snapshot unavailable"
            else "${trafficBytes(entry.received)} received · ${trafficBytes(entry.sent)} sent",
            style = MaterialTheme.typography.titleMedium,
        )
        Text("Observed VPN traffic · this device", style = MaterialTheme.typography.labelLarge)
        HourlyTrafficGraph(entry.hourly, Modifier.fillMaxWidth().height(80.dp))
        if (entry.hourly.isNotEmpty()) {
          val format =
              java.time.format.DateTimeFormatter.ofPattern("HH:mm z")
                  .withZone(java.time.ZoneId.systemDefault())
          Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(
                format.format(Instant.ofEpochMilli(entry.hourly.first().first)),
                style = MaterialTheme.typography.labelSmall,
            )
            Text(
                format.format(Instant.ofEpochMilli(entry.hourly.last().first)),
                style = MaterialTheme.typography.labelSmall,
            )
          }
          var hourlyDetails by remember { mutableStateOf(false) }
          TextButton(onClick = { hourlyDetails = !hourlyDetails }) { Text("Hourly traffic") }
          if (hourlyDetails)
              entry.hourly.forEach { (hour, bytes) ->
                Text(
                    "${format.format(Instant.ofEpochMilli(hour))} · ${trafficBytes(bytes)}",
                    style = MaterialTheme.typography.bodySmall,
                )
              }
        }
        data?.let {
          Text(
              "${Instant.ofEpochMilli(it.from)} → ${Instant.ofEpochMilli(it.until)} UTC",
              style = MaterialTheme.typography.bodySmall,
          )
        }
        if (entry.current == null)
            Text(
                "Recorded identity · not assigned to a current installation",
                style = MaterialTheme.typography.bodySmall,
            )
        entry.current?.let { current ->
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
        }
        var coverage by remember { mutableStateOf(false) }
        TextButton(onClick = { coverage = !coverage }) { Text("Coverage & identity details") }
        if (coverage) {
          Text(
              data?.coverage ?: "Traffic snapshot unavailable",
              style = MaterialTheme.typography.bodySmall,
          )
          Text(
              "Resolver context can be owned by another UID; its bytes are excluded from this app's totals. Control D history is endpoint/client scoped and does not establish app ownership.",
              style = MaterialTheme.typography.bodySmall,
          )
          data?.let {
            Text(
                "${it.boundaryBytes} unallocated boundary bytes · revision ${it.revision}\n${it.sessions}",
                style = MaterialTheme.typography.bodySmall,
            )
          }
          entry.recorded.forEach {
            Text(JSONObject(it).toString(2), style = MaterialTheme.typography.bodySmall)
          }
        }
        if (relevant.isEmpty())
            Text(
                "No retained traffic or attributed DNS observations in this period. This does not prove no activity."
            )
      }
      items(relevant, key = { it.metadata }) { TrafficFactContent(it) }
    }
    SnackbarHost(feedback, Modifier.align(Alignment.BottomCenter))
  }
}

@Composable
internal fun HourlyTrafficGraph(hours: List<Pair<Long, Long>>, modifier: Modifier = Modifier) {
  val color = MaterialTheme.colorScheme.primary
  val baseline = MaterialTheme.colorScheme.outlineVariant
  val peak = hours.maxByOrNull { it.second }
  val format =
      java.time.format.DateTimeFormatter.ofPattern("HH:mm z")
          .withZone(java.time.ZoneId.systemDefault())
  val description =
      if (peak == null || peak.second == 0L) "Hourly observed traffic: no recorded bytes"
      else
          "Hourly observed traffic; peak ${format.format(Instant.ofEpochMilli(peak.first))}, ${trafficBytes(peak.second)}"
  Canvas(modifier.semantics { contentDescription = description }) {
    if (hours.isEmpty()) return@Canvas
    val maximum = hours.maxOf { it.second }.coerceAtLeast(1).toFloat()
    val step = size.width / hours.size
    hours.forEachIndexed { index, (_, bytes) ->
      val height =
          if (bytes == 0L) 1.dp.toPx()
          else (size.height * bytes / maximum).coerceAtLeast(1.dp.toPx())
      drawRect(
          if (bytes == 0L) baseline else color,
          androidx.compose.ui.geometry.Offset(index * step, size.height - height),
          androidx.compose.ui.geometry.Size((step - 1.dp.toPx()).coerceAtLeast(1f), height),
      )
    }
  }
}
