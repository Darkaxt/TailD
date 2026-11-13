// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause

package com.tailscale.ipn.ui.viewModel

import androidx.annotation.StringRes
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.tailscale.ipn.R
import com.tailscale.ipn.ui.dataSource.DNSSettingsDataSource
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.model.LocalDNSStatus
import com.tailscale.ipn.ui.model.LocalDNSUpdate
import com.tailscale.ipn.ui.model.Tailcfg
import com.tailscale.ipn.ui.theme.off
import com.tailscale.ipn.ui.theme.success
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class DNSSettingsViewModelFactory(private val dataSource: DNSSettingsDataSource) :
    ViewModelProvider.Factory {
  @Suppress("UNCHECKED_CAST")
  override fun <T : ViewModel> create(modelClass: Class<T>): T {
    if (modelClass.isAssignableFrom(DNSSettingsViewModel::class.java)) {
      return DNSSettingsViewModel(dataSource) as T
    }
    throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
  }
}

data class DNSSettingsUiState(
    val enablementState: DNSEnablementState = DNSEnablementState.NOT_RUNNING,
    val dnsConfig: Tailcfg.DNSConfig? = null,
    val useCorpDNS: Boolean = false,
    val mdmHiddenFromUser: Boolean = false,
)

class DNSSettingsViewModel(private val dataSource: DNSSettingsDataSource) : ViewModel() {
  val localDNS = MutableStateFlow<LocalDNSStatus?>(null)
  val localDNSError = MutableStateFlow(false)
  val savingLocalDNS = MutableStateFlow(false)
  val strictPrivateDNS = MutableStateFlow<Boolean?>(null)
  private var localDNSGeneration = 0L
  private var awaitingSavedLocalDNSStatus = false

  init {
    viewModelScope.launch {
      combine(
              dataSource.prefs,
              dataSource.netmap,
              dataSource.dnsSettingsPolicy,
              dataSource.privateDNSChanges,
          ) { _, _, _, _ ->
            Unit
          }
          .collect { refreshLocalDNS() }
    }
    viewModelScope.launch {
      // Preserve the profile-completion refresh previously provided by IpnViewModel,
      // without inheriting its unrelated global exit-node and account observers.
      combine(
              dataSource.state,
              dataSource.netmap.map { it?.SelfNode?.User }.distinctUntilChanged(),
          ) { _, _ ->
            Unit
          }
          .collect { dataSource.currentProfile(viewModelScope) { refreshLocalDNS() } }
    }
  }

  private val dnsConfig: StateFlow<Tailcfg.DNSConfig?> =
      dataSource.netmap
          .filterNotNull()
          .map { it.DNS }
          .stateIn(
              viewModelScope,
              SharingStarted.WhileSubscribed(5_000),
              null,
          )

  val uiState: StateFlow<DNSSettingsUiState> =
      combine(
              dataSource.prefs,
              dnsConfig,
              dataSource.dnsSettingsPolicy,
          ) { prefs, dnsConfig, policy ->
            val corpDNS = prefs?.CorpDNS == true

            DNSSettingsUiState(
                enablementState =
                    when (prefs?.CorpDNS) {
                      null -> DNSEnablementState.NOT_RUNNING
                      true -> DNSEnablementState.ENABLED
                      false -> DNSEnablementState.DISABLED
                    },
                dnsConfig = dnsConfig,
                useCorpDNS = corpDNS,
                mdmHiddenFromUser = policy.value.hiddenFromUser,
            )
          }
          .stateIn(
              viewModelScope,
              SharingStarted.WhileSubscribed(5_000),
              DNSSettingsUiState(),
          )

  fun refreshLocalDNS() {
    strictPrivateDNS.value = dataSource.strictPrivateDNS()
    val generation = ++localDNSGeneration
    dataSource.localDNS(viewModelScope) { result ->
      if (generation != localDNSGeneration) return@localDNS
      localDNS.value = result.getOrNull()
      localDNSError.value = result.isFailure
      if (awaitingSavedLocalDNSStatus) {
        awaitingSavedLocalDNSStatus = false
        savingLocalDNS.value = false
      }
    }
  }

  fun saveLocalDNS(
      profileID: String,
      enabled: Boolean,
      endpoint: String,
      followAndroid: Boolean = false,
  ) {
    if (savingLocalDNS.value) return
    savingLocalDNS.value = true
    ++localDNSGeneration
    dataSource.editLocalDNS(
        viewModelScope,
        LocalDNSUpdate(profileID, enabled, endpoint, followAndroid),
    ) { result ->
      localDNSError.value = result.isFailure
      // Re-read current state: a successful edit may have preceded a profile switch.
      // Keep switches disabled until the newest status read is delivered, not
      // merely until the write returns, so another toggle cannot use old state.
      if (result.isSuccess) {
        awaitingSavedLocalDNSStatus = true
        refreshLocalDNS()
      } else {
        savingLocalDNS.value = false
      }
    }
  }

  fun setCorpDNS(
      enabled: Boolean,
      callback: (Result<Ipn.Prefs>) -> Unit,
  ) {
    if (dataSource.prefs.value == null) {
      callback(Result.failure(Exception("no prefs")))
      return
    }

    val prefsOut = Ipn.MaskedPrefs().apply { CorpDNS = enabled }
    dataSource.editPrefs(viewModelScope, prefsOut, callback)
  }
}

enum class DNSEnablementState(
    @param:StringRes val title: Int,
    @param:StringRes val caption: Int,
    val symbolDrawable: Int,
    val tint: @Composable () -> Color,
) {
  NOT_RUNNING(
      R.string.not_running,
      R.string.tailscale_is_not_running_this_device_is_using_the_system_dns_resolver,
      R.drawable.xmark_circle,
      { MaterialTheme.colorScheme.off },
  ),
  ENABLED(
      R.string.using_tailscale_dns,
      R.string.this_device_is_using_tailscale_to_resolve_dns_names,
      R.drawable.check_circle,
      { MaterialTheme.colorScheme.success },
  ),
  DISABLED(
      R.string.not_using_tailscale_dns,
      R.string.this_device_is_using_the_system_dns_resolver,
      R.drawable.xmark_circle,
      { MaterialTheme.colorScheme.error },
  ),
}
