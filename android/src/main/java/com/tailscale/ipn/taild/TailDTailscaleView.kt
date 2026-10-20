// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.ClipData
import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import com.tailscale.ipn.App
import com.tailscale.ipn.ShareActivity
import com.tailscale.ipn.ui.Links
import com.tailscale.ipn.ui.util.AndroidTVUtil.isAndroidTV
import com.tailscale.ipn.ui.view.*
import com.tailscale.ipn.ui.viewModel.AppViewModel
import com.tailscale.ipn.ui.viewModel.MainViewModel
import com.tailscale.ipn.ui.viewModel.SettingsNav
import java.time.Instant

/** Native expansion of the inherited app. Connection/login still use its original controls. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalComposeUiApi::class)
@Composable
fun TailDTailscaleView(
    loginAtUrl: (String) -> Unit,
    navigation: MainViewNavigation,
    settingsNav: SettingsNav,
    viewModel: MainViewModel,
    appViewModel: AppViewModel,
    destinationState: MutableIntState,
    tabState: MutableIntState,
) {
  // Keep the established TV focus/login flow while phone/tablet navigation expands.
  if (isAndroidTV()) {
    MainView(loginAtUrl, navigation, viewModel)
    return
  }
  var selected by tabState
  var destination by destinationState
  val savedDestinations = rememberSaveableStateHolder()
  val tabs = listOf("Connection", "Activity", "TailDrop", "Admin console", "Preferences")
  BoxWithConstraints(
      Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.statusBars).semantics {
        testTagsAsResourceId = true
      }
  ) {
    val useRail = maxWidth >= 600.dp || maxHeight < 480.dp
    Row(Modifier.fillMaxSize()) {
      if (useRail)
          NavigationRail(Modifier.navigationBarsPadding()) {
            NavigationRailItem(
                selected = destination == 0,
                onClick = { destination = 0 },
                icon = { Icon(Icons.Default.List, null) },
                label = { Text("Tailscale") },
            )
            NavigationRailItem(
                selected = destination == 1,
                onClick = { destination = 1 },
                icon = { Icon(Icons.Default.Settings, null) },
                label = { Text("Control D") },
            )
            NavigationRailItem(
                selected = destination == 2,
                onClick = { destination = 2 },
                icon = { Icon(Icons.Default.Info, null) },
                label = { Text("Dashboard") },
            )
          }
      Column(Modifier.weight(1f)) {
        Text(
            listOf("TailD · Tailscale", "TailD · Control D", "TailD · Dashboard")[destination],
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
        )
        if (destination == 0) {
          ScrollableTabRow(
              selectedTabIndex = selected,
              edgePadding = 0.dp,
              modifier = Modifier.testTag("taild-tailscale-tabs"),
          ) {
            tabs.forEachIndexed { index, name ->
              Tab(
                  selected = selected == index,
                  onClick = { selected = index },
                  text = { Text(name) },
              )
            }
          }
          Box(Modifier.weight(1f)) {
            when (selected) {
              0 ->
                  MainView(
                      loginAtUrl,
                      navigation.copy(onNavigateToSettings = { selected = 4 }),
                      viewModel,
                  )
              1 -> ActivityHistoryView(App.get().tailDHistory)
              2 -> TailDTransfersView(viewModel)
              3 -> {
                val map by viewModel.netmap.collectAsState()
                val handler = LocalUriHandler.current
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                  Text("Admin console", style = MaterialTheme.typography.titleLarge)
                  Text("Manage your tailnet using your existing Tailscale sign-in.")
                  Button(
                      enabled = map?.SelfNode?.isAdmin == true,
                      onClick = { handler.openUri(Links.ADMIN_URL) },
                  ) {
                    Text("Open admin console")
                  }
                  if (map?.SelfNode?.isAdmin != true) Text("An administrator account is required.")
                }
              }
              4 -> SettingsView(settingsNav, appViewModel = appViewModel, embedded = true)
            }
          }
        } else
            Box(Modifier.weight(1f)) {
              savedDestinations.SaveableStateProvider(destination) {
                if (destination == 1)
                    ControlDView(App.get().tailDControlD, settingsNav.onNavigateToDNSSettings)
                else
                    DashboardView(
                        App.get().tailDDashboard,
                        App.get().tailDControlD,
                        App.get().tailDHistory,
                        onControlD = { destination = 1 },
                        onPreferences = {
                          selected = 4
                          destination = 0
                        },
                    )
              }
            }
        if (!useRail)
            NavigationBar {
              NavigationBarItem(
                  selected = destination == 0,
                  onClick = { destination = 0 },
                  icon = { Icon(Icons.Default.List, null) },
                  label = { Text("Tailscale") },
              )
              NavigationBarItem(
                  selected = destination == 1,
                  onClick = { destination = 1 },
                  icon = { Icon(Icons.Default.Settings, null) },
                  label = { Text("Control D") },
              )
              NavigationBarItem(
                  selected = destination == 2,
                  onClick = { destination = 2 },
                  icon = { Icon(Icons.Default.Info, null) },
                  label = { Text("Dashboard") },
              )
            }
      }
    }
  }
}

@Composable
private fun TailDTransfersView(viewModel: MainViewModel) {
  val context = LocalContext.current
  val files =
      rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        if (uris.isNotEmpty()) {
          val clip = ClipData.newRawUri("TailDrop", uris.first())
          uris.drop(1).forEach { clip.addItem(ClipData.Item(it)) }
          context.startActivity(
              Intent(context, ShareActivity::class.java).apply {
                action = Intent.ACTION_SEND_MULTIPLE
                type = "*/*"
                putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
                clipData = clip
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
              }
          )
        }
      }
  val pending by viewModel.pendingTaildrop.pendingItems.collectAsState()
  Column(Modifier.fillMaxSize()) {
    Row(
        Modifier.fillMaxWidth().padding(16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
      Button(onClick = { files.launch(arrayOf("*/*")) }) { Text("Send files") }
      OutlinedButton(onClick = { viewModel.pendingTaildrop.openTaildropFolder(context) }) {
        Text("Open folder")
      }
    }
    if (pending.isNotEmpty()) {
      Box(Modifier.weight(1f)) { InlineShareListSheet(viewModel.pendingTaildrop) }
    }
    Box(Modifier.weight(1f)) { ActivityHistoryView(App.get().tailDHistory, taildropOnly = true) }
  }
}

@Composable
fun ActivityHistoryView(history: TailDHistory, taildropOnly: Boolean = false) {
  val enabled by history.enabled.collectAsState()
  val error by history.error.collectAsState()
  val allRows by history.rows.collectAsState()
  val map by com.tailscale.ipn.ui.notifier.Notifier.netmap.collectAsState()
  val prefs by com.tailscale.ipn.ui.notifier.Notifier.prefs.collectAsState()
  val scope = activityScope(map, prefs)
  val rows = allRows.filter {
    it.scope == scope && (!taildropOnly || it.event.kind.startsWith("taildrop."))
  }
  LaunchedEffect(history, scope) { history.refresh(scope) }
  LazyColumn(
      Modifier.fillMaxSize().navigationBarsPadding(),
      contentPadding = PaddingValues(16.dp),
  ) {
    item {
      Text(
          if (taildropOnly) "TailDrop history" else "Observed activity",
          style = MaterialTheme.typography.titleLarge,
      )
      Text(
          if (enabled) "Recording while this app process is active · 7-day retention"
          else "Recording is off. Retained observations are preserved.",
          style = MaterialTheme.typography.bodyMedium,
      )
      Text(
          "This device's current tailnet scope. Gaps do not mean no activity; restarts begin a new baseline.",
          style = MaterialTheme.typography.bodySmall,
      )
      TextButton(onClick = { history.refresh(scope) }) { Text("Refresh history") }
      Text(
          "Latest 200 retained observations in this scope.",
          style = MaterialTheme.typography.bodySmall,
      )
      error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
      if (scope == null) Text("Connect or select your tailnet to view its recorded activity.")
      else if (rows.isEmpty())
          Text(
              "No retained observations in this scope. Enable Collect analytics in Preferences to record new activity."
          )
    }
    items(rows, key = { it.id }) { row ->
      ListItem(
          headlineContent = { Text(row.event.subject) },
          supportingContent = {
            Text("${row.event.detail}\n${Instant.ofEpochMilli(row.at)} · ${row.event.kind}")
          },
      )
      HorizontalDivider()
    }
  }
}
