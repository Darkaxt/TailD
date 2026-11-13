// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause

package com.tailscale.ipn.ui.dataSource

import android.provider.Settings
import com.tailscale.ipn.App
import com.tailscale.ipn.mdm.AlwaysNeverUserDecides
import com.tailscale.ipn.mdm.MDMSettings
import com.tailscale.ipn.mdm.SettingState
import com.tailscale.ipn.ui.localapi.Client
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.model.IpnLocal
import com.tailscale.ipn.ui.model.LocalDNSStatus
import com.tailscale.ipn.ui.model.LocalDNSUpdate
import com.tailscale.ipn.ui.model.Netmap
import com.tailscale.ipn.ui.notifier.Notifier
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.StateFlow

interface DNSSettingsDataSource {
  val state: StateFlow<Ipn.State>
  val privateDNSChanges: StateFlow<Long>

  fun strictPrivateDNS(): Boolean?

  fun currentProfile(scope: CoroutineScope, callback: (Result<IpnLocal.LoginProfile>) -> Unit)

  fun localDNS(scope: CoroutineScope, callback: (Result<LocalDNSStatus>) -> Unit)

  fun editLocalDNS(
      scope: CoroutineScope,
      update: LocalDNSUpdate,
      callback: (Result<LocalDNSStatus>) -> Unit,
  )

  val prefs: StateFlow<Ipn.Prefs?>
  val netmap: StateFlow<Netmap.NetworkMap?>
  val dnsSettingsPolicy: StateFlow<SettingState<AlwaysNeverUserDecides>>

  fun editPrefs(
      scope: CoroutineScope,
      prefs: Ipn.MaskedPrefs,
      callback: (Result<Ipn.Prefs>) -> Unit,
  )
}

class DNSSettingsDataSourceImpl : DNSSettingsDataSource {
  override val state = Notifier.state
  override val privateDNSChanges
    get() = App.get().privateDNSChanges

  override fun strictPrivateDNS(): Boolean? = runCatching {
    val resolver = App.get().contentResolver
    when (
        Settings.Global.getString(resolver, "private_dns_mode")
            ?: Settings.Global.getString(resolver, "private_dns_default_mode")
    ) {
      "hostname" -> true
      "opportunistic",
      "off" -> false
      else -> null
    }
  }
      .getOrNull()

  override fun currentProfile(
      scope: CoroutineScope,
      callback: (Result<IpnLocal.LoginProfile>) -> Unit,
  ) {
    Client(scope).currentProfile(callback)
  }

  override fun localDNS(scope: CoroutineScope, callback: (Result<LocalDNSStatus>) -> Unit) {
    Client(scope).localDNS(callback)
  }

  override fun editLocalDNS(
      scope: CoroutineScope,
      update: LocalDNSUpdate,
      callback: (Result<LocalDNSStatus>) -> Unit,
  ) {
    Client(scope).editLocalDNS(update, callback)
  }

  override val prefs = Notifier.prefs
  override val netmap = Notifier.netmap
  override val dnsSettingsPolicy = MDMSettings.useTailscaleDNSSettings.flow

  override fun editPrefs(
      scope: CoroutineScope,
      prefs: Ipn.MaskedPrefs,
      callback: (Result<Ipn.Prefs>) -> Unit,
  ) {
    Client(scope).editPrefs(prefs, callback)
  }
}
