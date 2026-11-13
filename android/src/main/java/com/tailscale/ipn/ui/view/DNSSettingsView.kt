// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause

package com.tailscale.ipn.ui.view

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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.tailscale.ipn.R
import com.tailscale.ipn.ui.components.Header
import com.tailscale.ipn.ui.components.ListItemSwitch
import com.tailscale.ipn.ui.dataSource.DNSSettingsDataSource
import com.tailscale.ipn.ui.model.DnsType
import com.tailscale.ipn.ui.model.LocalDNSStatus
import com.tailscale.ipn.ui.theme.AppTheme
import com.tailscale.ipn.ui.util.AndroidTVUtil
import com.tailscale.ipn.ui.util.ClipboardValueView
import com.tailscale.ipn.ui.util.Lists
import com.tailscale.ipn.ui.util.LoadingIndicator
import com.tailscale.ipn.ui.util.itemsWithDividers
import com.tailscale.ipn.ui.viewModel.DNSEnablementState
import com.tailscale.ipn.ui.viewModel.DNSSettingsViewModel
import com.tailscale.ipn.ui.viewModel.DNSSettingsViewModelFactory

data class ViewableRoute(val name: String, val resolvers: List<DnsType.Resolver>)

@Composable
fun DNSSettingsView(
    backToSettings: () -> Unit,
    dataSource: DNSSettingsDataSource,
) {
  val factory = remember(dataSource) { DNSSettingsViewModelFactory(dataSource) }
  val dnsSettingsViewModel: DNSSettingsViewModel = viewModel(factory = factory)
  val screenState by dnsSettingsViewModel.uiState.collectAsStateWithLifecycle()

  val localDNS by dnsSettingsViewModel.localDNS.collectAsStateWithLifecycle()
  val localDNSError by dnsSettingsViewModel.localDNSError.collectAsStateWithLifecycle()
  val savingLocalDNS by dnsSettingsViewModel.savingLocalDNS.collectAsStateWithLifecycle()
  val strictPrivateDNS by dnsSettingsViewModel.strictPrivateDNS.collectAsStateWithLifecycle()
  val lifecycleOwner = LocalLifecycleOwner.current
  DisposableEffect(lifecycleOwner, dnsSettingsViewModel) {
    val observer = LifecycleEventObserver { _, event ->
      if (event == Lifecycle.Event.ON_RESUME) dnsSettingsViewModel.refreshLocalDNS()
    }
    lifecycleOwner.lifecycle.addObserver(observer)
    onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
  }

  val dnsConfig = screenState.dnsConfig
  val resolvers = dnsConfig?.Resolvers.orEmpty()
  val domains = dnsConfig?.Domains.orEmpty()
  val routes =
      dnsConfig?.Routes.orEmpty().mapNotNull { (name, resolvers) ->
        resolvers?.let { ViewableRoute(name = name, resolvers = it) }
      }

  DNSSettingsScreen(
      state =
          DNSSettingsUIState(
              enablement = screenState.enablementState,
              resolvers = resolvers.map { it.Addr.orEmpty() },
              domains = domains,
              routes = routes,
              mdmHiddenFromUser = screenState.mdmHiddenFromUser,
              useCorpDNS = screenState.useCorpDNS,
              localDNS = localDNS,
              localDNSError = localDNSError,
              savingLocalDNS = savingLocalDNS,
              strictPrivateDNS = strictPrivateDNS,
          ),
      onToggle = { enabled ->
        LoadingIndicator.start()
        dnsSettingsViewModel.setCorpDNS(enabled) { LoadingIndicator.stop() }
      },
      onSaveLocalDNS = dnsSettingsViewModel::saveLocalDNS,
      backToSettings = backToSettings,
      isTv = AndroidTVUtil.isAndroidTV(),
  )
}

private data class DNSSettingsUIState(
    val enablement: DNSEnablementState,
    val resolvers: List<String>,
    val domains: List<String>,
    val routes: List<ViewableRoute>,
    val mdmHiddenFromUser: Boolean,
    val useCorpDNS: Boolean,
    val localDNS: LocalDNSStatus? = null,
    val localDNSError: Boolean = false,
    val savingLocalDNS: Boolean = false,
    val strictPrivateDNS: Boolean? = null,
)

@Composable
private fun DNSSettingsScreen(
    state: DNSSettingsUIState,
    onToggle: (Boolean) -> Unit,
    onSaveLocalDNS: (String, Boolean, String, Boolean) -> Unit,
    backToSettings: () -> Unit,
    isTv: Boolean,
) {
  val keyboard = LocalSoftwareKeyboardController.current
  Scaffold(
      topBar = {
        Header(
            R.string.dns_settings,
            onBack = backToSettings,
            isTv = isTv,
        )
      }
  ) { innerPadding ->
    LoadingIndicator.Wrap {
      LazyColumn(Modifier.padding(innerPadding)) {
        item("state") {
          ListItem(
              leadingContent = {
                Icon(
                    painter = painterResource(state.enablement.symbolDrawable),
                    contentDescription = null,
                    tint = state.enablement.tint(),
                    modifier = Modifier.size(36.dp),
                )
              },
              headlineContent = {
                Text(
                    stringResource(state.enablement.title),
                    style = MaterialTheme.typography.titleMedium,
                )
              },
              supportingContent = { Text(stringResource(state.enablement.caption)) },
          )

          if (!state.mdmHiddenFromUser) {
            Lists.ItemDivider()
            ListItemSwitch(
                R.string.use_ts_dns,
                isOn = state.useCorpDNS,
                onToggle = onToggle,
            )
          }
        }

        item("localDNS") {
          Lists.SectionDivider(stringResource(R.string.local_dns_title))
          Column(Modifier.padding(16.dp)) {
            Text(stringResource(R.string.local_dns_scope))
            if (state.strictPrivateDNS != false) {
              Text(
                  stringResource(
                      if (state.strictPrivateDNS == true) R.string.local_dns_strict_conflict
                      else R.string.local_dns_mode_unknown
                  )
              )
            }
            state.localDNS?.let { saved ->
              var endpoint by
                  remember(saved.ProfileID, saved.ManualEndpoint) {
                    mutableStateOf(saved.ManualEndpoint)
                  }
              val editable =
                  !state.mdmHiddenFromUser && saved.ProfileID.isNotEmpty() && !state.savingLocalDNS
              Row {
                Text(stringResource(R.string.local_dns_enable), Modifier.weight(1f))
                Switch(
                    checked = saved.Configured,
                    onCheckedChange = {
                      onSaveLocalDNS(
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
                      onSaveLocalDNS(
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
                                onSaveLocalDNS(
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
            if (state.localDNSError)
                Text(
                    stringResource(R.string.local_dns_error),
                    color = MaterialTheme.colorScheme.error,
                )
          }
        }

        if (state.resolvers.isNotEmpty()) {
          item("resolversHeader") {
            Lists.SectionDivider(
                stringResource(
                    if (state.localDNS?.Configured == true) R.string.local_dns_tailnet_resolvers
                    else R.string.resolvers
                )
            )
          }

          itemsWithDividers(state.resolvers) { resolver -> ClipboardValueView(resolver) }
        }

        if (state.domains.isNotEmpty()) {
          item("domainsHeader") { Lists.SectionDivider(stringResource(R.string.search_domains)) }

          itemsWithDividers(state.domains) { domain -> ClipboardValueView(domain) }
        }

        if (state.routes.isNotEmpty()) {
          state.routes.forEach { route ->
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

@Preview(showSystemUi = true)
@Composable
fun DNSSettingsPreview() {
  AppTheme {
    DNSSettingsScreen(
        state =
            DNSSettingsUIState(
                enablement = DNSEnablementState.ENABLED,
                resolvers = listOf("1.1.1.1"),
                domains = listOf("tailscale.com"),
                routes = listOf(ViewableRoute(name = "Route", resolvers = emptyList())),
                mdmHiddenFromUser = false,
                useCorpDNS = true,
            ),
        onToggle = {},
        onSaveLocalDNS = { _, _, _, _ -> },
        backToSettings = {},
        isTv = false,
    )
  }
}
