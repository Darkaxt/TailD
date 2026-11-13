// Copyright (c) Tailscale Inc & AUTHORS
// SPDX-License-Identifier: BSD-3-Clause

package com.tailscale.ipn.ui.viewModel

import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import com.tailscale.ipn.mdm.AlwaysNeverUserDecides
import com.tailscale.ipn.mdm.SettingState
import com.tailscale.ipn.ui.dataSource.DNSSettingsDataSource
import com.tailscale.ipn.ui.model.Ipn
import com.tailscale.ipn.ui.model.IpnLocal
import com.tailscale.ipn.ui.model.LocalDNSStatus
import com.tailscale.ipn.ui.model.LocalDNSUpdate
import com.tailscale.ipn.ui.model.Netmap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DNSSettingsViewModelTest {
  private val store = ViewModelStore()
  private val source = FakeDNSSettingsDataSource()

  @Before
  fun setUp() {
    Dispatchers.setMain(StandardTestDispatcher())
  }

  @After
  fun tearDown() {
    store.clear()
    Dispatchers.resetMain()
  }

  private fun model() =
      ViewModelProvider(store, DNSSettingsViewModelFactory(source))[
          DNSSettingsViewModel::class.java]

  private fun status(profile: String) =
      LocalDNSStatus(ProfileID = profile, ManualEndpoint = "https://dns.example/dns-query")

  @Test
  fun staleReadCannotOverwriteNewestProfile() = runTest {
    val model = model()
    runCurrent()
    val old = source.reads.last()
    model.refreshLocalDNS()
    source.reads.last()(Result.success(status("new-profile")))
    old(Result.success(status("old-profile")))
    assertEquals("new-profile", model.localDNS.value?.ProfileID)
    assertFalse(model.localDNSError.value)
  }

  @Test
  fun successfulSaveLocksThroughNewestStatusReadAndPreservesProfileAndSource() = runTest {
    val model = model()
    runCurrent()
    val stale = source.reads.last()
    model.saveLocalDNS("profile-A", true, "https://dns.example/dns-query", true)
    assertEquals(
        LocalDNSUpdate("profile-A", true, "https://dns.example/dns-query", true),
        source.writes.single().first,
    )
    model.saveLocalDNS("profile-A", false, "", false)
    assertEquals(1, source.writes.size)
    source.writes.single().second(Result.success(status("profile-A")))
    assertTrue(model.savingLocalDNS.value)
    val savedRead = source.reads.last()
    model.refreshLocalDNS()
    savedRead(Result.success(status("profile-A")))
    stale(Result.failure(Exception("stale failure")))
    assertTrue(model.savingLocalDNS.value)
    assertNull(model.localDNS.value)
    source.reads.last()(Result.success(status("profile-B")))
    assertFalse(model.savingLocalDNS.value)
    assertFalse(model.localDNSError.value)
    assertEquals("profile-B", model.localDNS.value?.ProfileID)
  }

  @Test
  fun failedWriteAndFailedPostWriteReadReleaseControlsAndReportError() = runTest {
    val model = model()
    runCurrent()
    model.saveLocalDNS("profile-A", false, "", false)
    source.writes.last().second(Result.failure(Exception("write failed")))
    assertFalse(model.savingLocalDNS.value)
    assertTrue(model.localDNSError.value)
    model.saveLocalDNS("profile-A", false, "", false)
    source.writes.last().second(Result.success(status("profile-A")))
    assertTrue(model.savingLocalDNS.value)
    source.reads.last()(Result.failure(Exception("read failed")))
    assertFalse(model.savingLocalDNS.value)
    assertTrue(model.localDNSError.value)
    assertNull(model.localDNS.value)
  }

  @Test
  fun privateDNSAndCompletedProfileChangesRefreshCurrentStatus() = runTest {
    val model = model()
    runCurrent()
    var reads = source.reads.size
    source.strict = true
    source.privateDNSChanges.value++
    runCurrent()
    assertTrue(source.reads.size > reads)
    assertEquals(true, model.strictPrivateDNS.value)
    source.state.value = Ipn.State.Running
    runCurrent()
    assertEquals(2, source.profiles.size)
    reads = source.reads.size
    source.profiles.last()(Result.failure(Exception("no profile")))
    assertEquals(reads + 1, source.reads.size)
  }

  @Test
  fun canonicalStateAndExplicitCorpDNSWriteRemainDataSourceOwned() = runTest {
    val model = model()
    backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) { model.uiState.collect {} }
    runCurrent()
    var failed = false
    model.setCorpDNS(true) { failed = it.isFailure }
    assertTrue(failed)
    assertTrue(source.prefWrites.isEmpty())
    source.prefs.value = Ipn.Prefs(CorpDNS = false)
    source.dnsSettingsPolicy.value = SettingState(AlwaysNeverUserDecides.Always, true)
    runCurrent()
    assertTrue(model.uiState.value.mdmHiddenFromUser)
    assertEquals(DNSEnablementState.DISABLED, model.uiState.value.enablementState)
    model.setCorpDNS(false) {}
    assertEquals(false, source.prefWrites.single().CorpDNS)
    source.prefs.value = Ipn.Prefs(CorpDNS = true)
    runCurrent()
    assertTrue(model.uiState.value.useCorpDNS)
    assertEquals(DNSEnablementState.ENABLED, model.uiState.value.enablementState)
  }

  private class FakeDNSSettingsDataSource : DNSSettingsDataSource {
    override val state = MutableStateFlow(Ipn.State.NoState)
    override val privateDNSChanges = MutableStateFlow(0L)
    override val prefs = MutableStateFlow<Ipn.Prefs?>(null)
    override val netmap = MutableStateFlow<Netmap.NetworkMap?>(null)
    override val dnsSettingsPolicy =
        MutableStateFlow(SettingState(AlwaysNeverUserDecides.UserDecides, false))
    var strict: Boolean? = false
    val profiles = mutableListOf<(Result<IpnLocal.LoginProfile>) -> Unit>()
    val reads = mutableListOf<(Result<LocalDNSStatus>) -> Unit>()
    val writes = mutableListOf<Pair<LocalDNSUpdate, (Result<LocalDNSStatus>) -> Unit>>()
    val prefWrites = mutableListOf<Ipn.MaskedPrefs>()

    override fun strictPrivateDNS() = strict

    override fun currentProfile(
        scope: CoroutineScope,
        callback: (Result<IpnLocal.LoginProfile>) -> Unit,
    ) {
      profiles.add(callback)
    }

    override fun localDNS(scope: CoroutineScope, callback: (Result<LocalDNSStatus>) -> Unit) {
      reads.add(callback)
    }

    override fun editLocalDNS(
        scope: CoroutineScope,
        update: LocalDNSUpdate,
        callback: (Result<LocalDNSStatus>) -> Unit,
    ) {
      writes.add(update to callback)
    }

    override fun editPrefs(
        scope: CoroutineScope,
        prefs: Ipn.MaskedPrefs,
        callback: (Result<Ipn.Prefs>) -> Unit,
    ) {
      prefWrites.add(prefs)
      callback(Result.success(Ipn.Prefs(CorpDNS = prefs.CorpDNS ?: false)))
    }
  }
}
