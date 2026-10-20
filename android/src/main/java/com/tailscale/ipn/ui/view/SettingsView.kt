// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause

package com.tailscale.ipn.ui.view

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.tailscale.ipn.App
import com.tailscale.ipn.BuildConfig
import com.tailscale.ipn.R
import com.tailscale.ipn.mdm.AlwaysNeverUserDecides
import com.tailscale.ipn.mdm.MDMSettings
import com.tailscale.ipn.mdm.ShowHide
import com.tailscale.ipn.ui.Links
import com.tailscale.ipn.ui.theme.link
import com.tailscale.ipn.ui.theme.listItem
import com.tailscale.ipn.ui.util.AndroidTVUtil
import com.tailscale.ipn.ui.util.AndroidTVUtil.isAndroidTV
import com.tailscale.ipn.ui.util.AppVersion
import com.tailscale.ipn.ui.util.Lists
import com.tailscale.ipn.ui.util.set
import com.tailscale.ipn.ui.viewModel.AppViewModel
import com.tailscale.ipn.ui.viewModel.SettingsNav
import com.tailscale.ipn.ui.viewModel.SettingsViewModel

@Composable
fun SettingsView(
    settingsNav: SettingsNav,
    viewModel: SettingsViewModel = viewModel(),
    appViewModel: AppViewModel = viewModel(),
    embedded: Boolean = false,
) {
  val handler = LocalUriHandler.current

  val user by viewModel.loggedInUser.collectAsState()
  val isAdmin by viewModel.isAdmin.collectAsState()
  val managedByOrganization by viewModel.managedByOrganization.collectAsState()
  val tailnetLockEnabled by viewModel.tailNetLockEnabled.collectAsState()
  val corpDNSEnabled by viewModel.corpDNSEnabled.collectAsState()
  val isVPNPrepared by appViewModel.vpnPrepared.collectAsState()
  val showTailnetLock by MDMSettings.manageTailnetLock.flow.collectAsState()
  val useTailscaleSubnets by MDMSettings.useTailscaleSubnets.flow.collectAsState()
  val isClientRemoteLoggingEnabled by viewModel.isClientRemoteLoggingEnabled.collectAsState()
  var showDisableLoggingDialog by remember { mutableStateOf(false) }
  var showDeleteHistoryDialog by remember { mutableStateOf(false) }
  var showSourceHealth by remember { mutableStateOf(false) }
  val history = App.get().tailDHistory
  val recording by history.enabled.collectAsState()
  val exitPrefs by viewModel.prefs.collectAsState()
  val map by viewModel.netmap.collectAsState()
  val exitPicker by MDMSettings.exitNodesPicker.flow.collectAsState()
  val managedExit by MDMSettings.exitNodeID.flow.collectAsState()
  val exitEnabled = !exitPrefs?.activeExitNodeID.isNullOrEmpty()
  val runningAsExit by viewModel.isRunningExitNode.collectAsState()
  var exitChangePending by remember { mutableStateOf(false) }
  var exitError by remember { mutableStateOf(false) }

  Scaffold(
      topBar = {
        if (!embedded)
            Header(titleRes = R.string.settings_title, onBack = settingsNav.onNavigateBackHome)
      }
  ) { innerPadding ->
    Column(
        modifier =
            Modifier.padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .testTag("taild-preferences")
    ) {
      if (isVPNPrepared) {
        UserView(
            profile = user,
            actionState = UserActionState.NAV,
            onClick = settingsNav.onNavigateToUserSwitcher,
        )
      }

      if (isAdmin && !isAndroidTV()) {
        Lists.ItemDivider()
        AdminTextView { handler.openUri(Links.ADMIN_URL) }
      }

      Lists.SectionDivider()
      Setting.Switch(
          R.string.taild_collect_analytics,
          subtitle = stringResource(R.string.taild_collect_analytics_detail),
          isOn = recording,
          onToggle = history::setEnabled,
      )
      Setting.Text(R.string.taild_delete_history, onClick = { showDeleteHistoryDialog = true })
      if (exitPicker.value == ShowHide.Show) {
        Lists.ItemDivider()
        Setting.Switch(
            R.string.taild_use_exit_node,
            isOn = exitEnabled,
            enabled = exitPrefs != null && managedExit.value.isNullOrEmpty() && !exitChangePending,
            onToggle = {
              if (exitPrefs?.activeExitNodeID != null || exitPrefs?.selectedExitNodeID != null) {
                exitError = false
                exitChangePending = true
                viewModel.toggleExitNode { result ->
                  exitChangePending = false
                  exitError = result.isFailure
                }
              } else settingsNav.onNavigateToExitNodes()
            },
        )
        if (exitEnabled) {
          Setting.Text(
              R.string.exit_node,
              subtitle =
                  map?.Peers?.find { it.StableID == exitPrefs?.activeExitNodeID }?.displayName
                      ?: stringResource(R.string.taild_exit_node_unavailable),
              onClick = settingsNav.onNavigateToExitNodes,
          )
        }
        if (exitError)
            Text(
                stringResource(R.string.taild_exit_node_failed),
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        Setting.Text(
            R.string.taild_run_exit_node,
            subtitle = stringResource(if (runningAsExit) R.string.enabled else R.string.disabled),
            onClick = settingsNav.onNavigateToRunAsExitNode,
        )
      }
      Lists.ItemDivider()
      Setting.Text(
          R.string.dns_settings,
          subtitle =
              corpDNSEnabled?.let {
                stringResource(
                    if (it) R.string.using_tailscale_dns else R.string.not_using_tailscale_dns
                )
              },
          onClick = settingsNav.onNavigateToDNSSettings,
      )

      Lists.ItemDivider()
      Setting.Text(
          R.string.split_tunneling,
          subtitle = stringResource(R.string.filter_apps_allowed_to_access_tailscale),
          onClick = settingsNav.onNavigateToSplitTunneling,
      )

      if (showTailnetLock.value == ShowHide.Show) {
        Lists.ItemDivider()
        Setting.Text(
            R.string.tailnet_lock,
            subtitle =
                tailnetLockEnabled?.let {
                  stringResource(if (it) R.string.enabled else R.string.disabled)
                },
            onClick = settingsNav.onNavigateToTailnetLock,
        )
      }
      if (useTailscaleSubnets.value == AlwaysNeverUserDecides.UserDecides) {
        Lists.ItemDivider()
        Setting.Text(R.string.subnet_routing, onClick = settingsNav.onNavigateToSubnetRouting)
      }

      Lists.ItemDivider()
      Setting.Switch(
          R.string.client_remote_logging_enabled,
          subtitle =
              stringResource(
                  if (MDMSettings.isMDMConfigured)
                      R.string.client_remote_logging_enabled_subtitle_mdm
                  else R.string.client_remote_logging_enabled_subtitle
              ),
          isOn = isClientRemoteLoggingEnabled,
          enabled = !MDMSettings.isMDMConfigured,
          onToggle = {
            if (isClientRemoteLoggingEnabled) {
              showDisableLoggingDialog = true
            } else {
              viewModel.toggleIsClientRemoteLoggingEnabled()
            }
          },
      )

      if (!AndroidTVUtil.isAndroidTV()) {
        Lists.ItemDivider()
        Setting.Text(R.string.permissions, onClick = settingsNav.onNavigateToPermissions)
      }

      managedByOrganization.value?.let {
        Lists.ItemDivider()
        Setting.Text(
            title = stringResource(R.string.managed_by_orgName, it),
            onClick = settingsNav.onNavigateToManagedBy,
        )
      }

      Lists.SectionDivider()
      Setting.Text(R.string.bug_report, onClick = settingsNav.onNavigateToBugReport)

      Lists.ItemDivider()
      Setting.Text(
          title = "About TailD · history & source health",
          onClick = { showSourceHealth = true },
      )
      Lists.ItemDivider()
      Setting.Text(
          R.string.about_tailscale,
          subtitle = "${stringResource(id = R.string.version)} ${AppVersion.Short()}",
          onClick = settingsNav.onNavigateToAbout,
      )

      // TODO: put a heading for the debug section
      if (BuildConfig.DEBUG) {
        Lists.SectionDivider()
        Lists.MutedHeader(text = stringResource(R.string.internal_debug_options))
        Setting.Text(R.string.mdm_settings, onClick = settingsNav.onNavigateToMDMSettings)
      }
    }
  }

  if (showSourceHealth)
      com.tailscale.ipn.taild.TailDAboutDialog(
          App.get().tailDControlD,
          history,
          onPreferences = { showSourceHealth = false },
          onClose = { showSourceHealth = false },
      )
  if (showDeleteHistoryDialog) {
    AlertDialog(
        onDismissRequest = { showDeleteHistoryDialog = false },
        title = { Text(stringResource(R.string.taild_delete_history)) },
        text = { Text(stringResource(R.string.taild_delete_history_detail)) },
        confirmButton = {
          TextButton(
              onClick = {
                history.deleteHistory()
                App.get().tailDControlD.clearHistory()
                showDeleteHistoryDialog = false
              }
          ) {
            Text(stringResource(R.string.taild_delete_history))
          }
        },
        dismissButton = {
          TextButton(onClick = { showDeleteHistoryDialog = false }) {
            Text(stringResource(R.string.cancel))
          }
        },
    )
  }

  if (showDisableLoggingDialog) {
    AlertDialog(
        onDismissRequest = { showDisableLoggingDialog = false },
        title = { Text(stringResource(R.string.client_remote_logging_disable_confirm_title)) },
        text = { Text(stringResource(R.string.client_remote_logging_disable_confirm_message)) },
        confirmButton = {
          TextButton(
              onClick = {
                showDisableLoggingDialog = false
                viewModel.toggleIsClientRemoteLoggingEnabled()
              }
          ) {
            Text(
                stringResource(R.string.client_remote_logging_disable_confirm_button),
                color = MaterialTheme.colorScheme.error,
            )
          }
        },
        dismissButton = {
          TextButton(onClick = { showDisableLoggingDialog = false }) {
            Text(stringResource(R.string.cancel))
          }
        },
    )
  }
}

object Setting {
  @Composable
  fun Text(
      titleRes: Int = 0,
      title: String? = null,
      subtitle: String? = null,
      destructive: Boolean = false,
      enabled: Boolean = true,
      onClick: (() -> Unit)? = null,
  ) {
    var modifier: Modifier = Modifier
    if (enabled) {
      onClick?.let { modifier = modifier.clickable(onClick = it) }
    }
    ListItem(
        modifier = modifier,
        colors = MaterialTheme.colorScheme.listItem,
        headlineContent = {
          Text(
              title ?: stringResource(titleRes),
              style = MaterialTheme.typography.bodyMedium,
              color = if (destructive) MaterialTheme.colorScheme.error else Color.Unspecified,
          )
        },
        supportingContent =
            subtitle?.let {
              {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
              }
            },
    )
  }

  @Composable
  fun Switch(
      titleRes: Int = 0,
      title: String? = null,
      subtitle: String? = null,
      isOn: Boolean,
      enabled: Boolean = true,
      onToggle: (Boolean) -> Unit = {},
  ) {
    val label = title ?: stringResource(titleRes)
    ListItem(
        colors = MaterialTheme.colorScheme.listItem,
        headlineContent = {
          Text(
              title ?: stringResource(titleRes),
              style = MaterialTheme.typography.bodyMedium,
          )
        },
        supportingContent =
            subtitle?.let {
              {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
              }
            },
        trailingContent = {
          TintedSwitch(
              checked = isOn,
              onCheckedChange = onToggle,
              enabled = enabled,
              modifier = Modifier.semantics { contentDescription = label },
          )
        },
    )
  }
}

@Composable
fun AdminTextView(onNavigateToAdminConsole: () -> Unit) {
  val adminStr = buildAnnotatedString {
    append(stringResource(id = R.string.settings_admin_prefix))

    pushStringAnnotation(tag = "link", annotation = Links.ADMIN_URL)
    withStyle(
        style =
            SpanStyle(
                color = MaterialTheme.colorScheme.link,
                textDecoration = TextDecoration.Underline,
            )
    ) {
      append(stringResource(id = R.string.settings_admin_link))
    }
  }

  Lists.InfoItem(adminStr, onClick = onNavigateToAdminConsole)
}

@Preview
@Composable
fun SettingsPreview() {
  val vm = SettingsViewModel()
  vm.corpDNSEnabled.set(true)
  vm.tailNetLockEnabled.set(true)
  vm.isAdmin.set(true)
  vm.managedByOrganization.set("Tails and Scales Inc.")
  SettingsView(SettingsNav({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}), vm)
}
