// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause

package com.tailscale.ipn.ui.view

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import com.tailscale.ipn.R
import com.tailscale.ipn.mdm.MDMSettings
import com.tailscale.ipn.ui.components.Header
import com.tailscale.ipn.ui.components.ListItemSwitch
import com.tailscale.ipn.ui.model.DnsType
import com.tailscale.ipn.ui.notifier.Notifier
import com.tailscale.ipn.ui.util.AndroidTVUtil
import com.tailscale.ipn.ui.util.ClipboardValueView
import com.tailscale.ipn.ui.util.Lists
import com.tailscale.ipn.ui.util.LoadingIndicator
import com.tailscale.ipn.ui.util.itemsWithDividers
import com.tailscale.ipn.ui.util.set
import com.tailscale.ipn.ui.viewModel.DNSEnablementState
import com.tailscale.ipn.ui.viewModel.DNSSettingsViewModel
import com.tailscale.ipn.ui.viewModel.DNSSettingsViewModelFactory

data class ViewableRoute(val name: String, val resolvers: List<DnsType.Resolver>)

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun DNSSettingsView(
    backToSettings: () -> Unit,
    model: DNSSettingsViewModel = viewModel(factory = DNSSettingsViewModelFactory()),
) {
  val state: DNSEnablementState by model.enablementState.collectAsState()
  val resolvers = model.dnsConfig.collectAsState().value?.Resolvers ?: emptyList()
  val domains = model.dnsConfig.collectAsState().value?.Domains ?: emptyList()
  val routes: List<ViewableRoute> =
      model.dnsConfig.collectAsState().value?.Routes?.mapNotNull { entry ->
        entry.value?.let { resolvers -> ViewableRoute(name = entry.key, resolvers) } ?: run { null }
      } ?: emptyList()
  val useCorpDNS = Notifier.prefs.collectAsState().value?.CorpDNS == true
  val dnsSettingsMDMDisposition by MDMSettings.useTailscaleDNSSettings.flow.collectAsState()
  val localDNS by model.localDNS.collectAsState()
  val localDNSError by model.localDNSError.collectAsState()
  val savingLocalDNS by model.savingLocalDNS.collectAsState()
  val strictPrivateDNS by model.strictPrivateDNS.collectAsState()
  val lifecycleOwner = LocalLifecycleOwner.current
  val keyboard = LocalSoftwareKeyboardController.current
  DisposableEffect(lifecycleOwner, model) {
    val observer = LifecycleEventObserver { _, event ->
      if (event == Lifecycle.Event.ON_RESUME) model.refreshLocalDNS()
    }
    lifecycleOwner.lifecycle.addObserver(observer)
    onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
  }

  Scaffold(
      topBar = {
        Header(
            R.string.dns_settings,
            onBack = backToSettings,
            isTv = AndroidTVUtil.isAndroidTV(),
        )
      }
  ) { innerPadding ->
    LoadingIndicator.Wrap {
      LazyColumn(Modifier.padding(innerPadding)) {
        item("state") {
          ListItem(
              leadingContent = {
                Icon(
                    painter = painterResource(state.symbolDrawable),
                    contentDescription = null,
                    tint = state.tint(),
                    modifier = Modifier.size(36.dp),
                )
              },
              headlineContent = {
                Text(stringResource(state.title), style = MaterialTheme.typography.titleMedium)
              },
              supportingContent = { Text(stringResource(state.caption)) },
          )

          if (!dnsSettingsMDMDisposition.value.hiddenFromUser) {
            Lists.ItemDivider()
            ListItemSwitch(
                R.string.use_ts_dns,
                isOn = useCorpDNS,
                onToggle = {
                  LoadingIndicator.start()
                  model.toggleCorpDNS { LoadingIndicator.stop() }
                },
            )
          }
        }

        item("localDNS") {
          Lists.SectionDivider(stringResource(R.string.local_dns_title))
          Column(Modifier.padding(16.dp)) {
            Text(stringResource(R.string.local_dns_scope))
            if (strictPrivateDNS != false) {
              Text(
                  stringResource(
                      if (strictPrivateDNS == true) R.string.local_dns_strict_conflict
                      else R.string.local_dns_mode_unknown
                  )
              )
            }
            localDNS?.let { saved ->
              var endpoint by
                  remember(saved.ProfileID, saved.ManualEndpoint) {
                    mutableStateOf(saved.ManualEndpoint)
                  }
              val editable =
                  !dnsSettingsMDMDisposition.value.hiddenFromUser &&
                      saved.ProfileID.isNotEmpty() &&
                      !savingLocalDNS
              Row {
                Text(stringResource(R.string.local_dns_enable), Modifier.weight(1f))
                Switch(
                    checked = saved.Configured,
                    onCheckedChange = {
                      model.saveLocalDNS(
                          saved.ProfileID,
                          it,
                          saved.ManualEndpoint,
                          saved.FollowAndroid,
                      )
                    },
                    enabled =
                        isLocalDNSToggleEnabled(
                            editable,
                            saved.Configured,
                            saved.FollowAndroid,
                            saved.ManualEndpoint,
                        ),
                )
              }
              Row {
                Text(stringResource(R.string.local_dns_follow), Modifier.weight(1f))
                Switch(
                    checked = saved.FollowAndroid,
                    onCheckedChange = {
                      // Explicitly leaving follow is an escape hatch. An empty manual
                      // source cannot be enabled until a valid endpoint is entered.
                      model.saveLocalDNS(
                          saved.ProfileID,
                          saved.Configured && (it || saved.ManualEndpoint.isNotEmpty()),
                          saved.ManualEndpoint,
                          it,
                      )
                    },
                    enabled = editable,
                )
              }
              if (saved.FollowAndroid) {
                Text(stringResource(R.string.local_dns_follow_description))
                if (saved.FollowAndroid && saved.Endpoint.isNotEmpty()) Text(saved.Endpoint)
                if (saved.Endpoint.isEmpty() && saved.LastValidEndpoint.isNotEmpty()) {
                  Text(
                      stringResource(R.string.local_dns_previous_endpoint, saved.LastValidEndpoint)
                  )
                }
              } else
                  OutlinedTextField(
                      value = endpoint,
                      onValueChange = { endpoint = it },
                      label = { Text(stringResource(R.string.local_dns_endpoint)) },
                      singleLine = true,
                      keyboardOptions =
                          KeyboardOptions(
                              keyboardType = KeyboardType.Uri,
                              imeAction = ImeAction.Done,
                          ),
                      keyboardActions =
                          KeyboardActions(
                              onDone = {
                                model.saveLocalDNS(
                                    saved.ProfileID,
                                    saved.Configured,
                                    endpoint,
                                    false,
                                )
                                keyboard?.hide()
                              }
                          ),
                      supportingText = { Text(stringResource(R.string.local_dns_manual_done)) },
                      enabled = editable,
                      modifier = Modifier.fillMaxWidth(),
                  )
              Text(saved.Reason)
            }
            if (localDNSError)
                Text(
                    stringResource(R.string.local_dns_error),
                    color = MaterialTheme.colorScheme.error,
                )
          }
        }

        if (resolvers.isNotEmpty()) {
          item("resolversHeader") {
            Lists.SectionDivider(
                stringResource(
                    if (localDNS?.Configured == true) R.string.local_dns_tailnet_resolvers
                    else R.string.resolvers
                )
            )
          }

          itemsWithDividers(resolvers) { resolver -> ClipboardValueView(resolver.Addr.orEmpty()) }
        }

        if (domains.isNotEmpty()) {
          item("domainsHeader") { Lists.SectionDivider(stringResource(R.string.search_domains)) }

          itemsWithDividers(domains) { domain -> ClipboardValueView(domain) }
        }

        if (routes.isNotEmpty()) {
          routes.forEach { route ->
            item { Lists.SectionDivider("Route: ${route.name}") }

            itemsWithDividers(route.resolvers) { resolver ->
              ClipboardValueView(resolver.Addr.orEmpty())
            }
          }
        }
      }
    }
  }
}

@Preview
@Composable
fun DNSSettingsViewPreview() {
  val vm = DNSSettingsViewModel()
  vm.enablementState.set(DNSEnablementState.ENABLED)
  DNSSettingsView(backToSettings = {}, vm)
}
