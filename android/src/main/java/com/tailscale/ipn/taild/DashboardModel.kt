// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.ContentResolver
import android.net.Uri
import com.tailscale.ipn.ui.notifier.Notifier
import java.time.Instant
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

data class DashboardState(
    val hours: Int = 168,
    val window: DashboardWindow = dashboardWindow(168),
    val dns: DashboardDnsSnapshot? = null,
    val activity: DashboardActivitySnapshot? = null,
    val dnsLoading: Boolean = false,
    val activityLoading: Boolean = false,
    val dnsError: String? = null,
    val activityError: String? = null,
    val exportPending: Boolean = false,
    val exportWriting: Boolean = false,
    val exportNotice: String? = null,
    val dnsDetails: DashboardDnsSnapshot? = null,
    val dnsFilter: DashboardDnsFilter = DashboardDnsFilter(),
    val activityDetails: DashboardActivitySnapshot? = null,
    val activityKind: String? = null,
    val activitySearch: String = "",
)

private fun dashboardWindow(hours: Int, until: Instant = Instant.now()) =
    DashboardWindow(until.minusSeconds(hours.toLong() * 3600), until)

/** App-owned queries finish through navigation; new hidden-page updates only mark data dirty. */
class DashboardModel(
    private val scope: CoroutineScope,
    private val history: TailDHistory,
    private val controlD: ControlDModel,
    tailnetScopes: Flow<String?> =
        combine(Notifier.netmap, Notifier.prefs) { map, prefs -> activityScope(map, prefs) },
) {
  private val mutable = MutableStateFlow(DashboardState())
  val state = mutable.asStateFlow()
  private var visible = false
  private var opened = false
  private var tailnet: String? = null
  private var generation = 0L
  private var trafficCrossCheckGeneration = 0L
  private var dnsJob: Job? = null
  private var activityJob: Job? = null
  private var dnsDirty = true
  private var activityDirty = true
  private var pendingExport: Export? = null
  // Ephemeral debug readback of the actual SAF result; never persisted or exported/logged.
  @Volatile
  internal var exportedDocumentForTest: Uri? = null
    private set

  private sealed interface Export {
    data class Dns(val data: DashboardDnsSnapshot, val filter: DashboardDnsFilter) : Export

    data class Traffic(val data: TrafficSnapshot, val identity: String?) : Export

    data class Activity(
        val data: DashboardActivitySnapshot,
        val kind: String?,
        val search: String,
    ) : Export
  }

  init {
    scope.launch {
      history.trafficDeletion.drop(1).collect {
        synchronized(this@DashboardModel) {
          if (pendingExport is Export.Traffic) {
            pendingExport = null
            mutable.update { state ->
              state.copy(
                  exportPending = false,
                  exportNotice = "Traffic history deleted. Select a new snapshot before exporting.",
              )
            }
          }
        }
      }
    }
    scope.launch {
      controlD.state
          .map { Triple(it.binding, it.page.revision, it.page.window) }
          .distinctUntilChanged()
          .collect {
            synchronized(this@DashboardModel) {
              val shown = state.value.dns
              if (
                  (shown != null && shown.binding != it.first) ||
                      state.value.dnsDetails?.binding?.let { binding -> binding != it.first } ==
                          true
              )
                  mutable.update { state ->
                    state.copy(dns = null, dnsError = null, dnsDetails = null)
                  }
              dnsDirty = true
              if (visible) readDns()
            }
          }
    }
    scope.launch {
      tailnetScopes.distinctUntilChanged().collect { selected ->
        synchronized(this@DashboardModel) {
          if (tailnet != selected) {
            tailnet = selected
            activityJob?.cancel()
            activityJob = null
            mutable.update {
              it.copy(activity = null, activityError = null, activityDetails = null)
            }
          }
          activityDirty = true
          if (visible) readActivity()
        }
      }
    }
    scope.launch {
      history.rows.drop(1).collect {
        synchronized(this@DashboardModel) {
          activityDirty = true
          if (visible) readActivity()
        }
      }
    }
  }

  @Synchronized
  fun open() {
    visible = true
    if (!opened) {
      opened = true
      refresh()
    } else {
      if (dnsDirty) readDns()
      if (activityDirty) readActivity()
    }
    if (controlD.state.value.hasRead) controlD.open()
  }

  @Synchronized
  fun closeView() {
    visible = false
  }

  @Synchronized
  fun retryDns() {
    dnsDirty = true
    readDns()
  }

  @Synchronized
  fun retryActivity() {
    activityDirty = true
    readActivity()
  }

  fun dnsDetails(data: DashboardDnsSnapshot, filter: DashboardDnsFilter = DashboardDnsFilter()) {
    mutable.update { it.copy(dnsDetails = data, dnsFilter = filter, activityDetails = null) }
  }

  @Synchronized
  fun crossCheckTraffic(traffic: TrafficSnapshot) {
    val request = ++trafficCrossCheckGeneration
    val epoch = generation
    val binding = controlD.state.value.binding
    if (binding == null) {
      mutable.update {
        it.copy(
            exportNotice = "Select a Control D endpoint/client to cross-check provider history."
        )
      }
      return
    }
    scope.launch(Dispatchers.IO) {
      try {
        val window =
            DashboardWindow(Instant.ofEpochMilli(traffic.from), Instant.ofEpochMilli(traffic.until))
        val (revision, rows) = controlD.store.facts(binding, window.from, window.until)
        synchronized(this@DashboardModel) {
          if (
              trafficCrossCheckGeneration == request &&
                  generation == epoch &&
                  controlD.state.value.binding == binding
          )
              dnsDetails(DashboardDnsSnapshot(binding, window, revision, rows))
        }
      } catch (_: Exception) {
        mutable.update { it.copy(exportNotice = "Provider history cross-check unavailable.") }
      }
    }
  }

  fun activityDetails(data: DashboardActivitySnapshot, kind: String? = null) {
    mutable.update {
      it.copy(activityDetails = data, activityKind = kind, activitySearch = "", dnsDetails = null)
    }
  }

  fun dismissDetails() {
    mutable.update { it.copy(dnsDetails = null, activityDetails = null) }
  }

  fun searchDetails(value: String) {
    mutable.update {
      if (it.dnsDetails != null) it.copy(dnsFilter = it.dnsFilter.copy(search = value.take(256)))
      else it.copy(activitySearch = value.take(256))
    }
  }

  @Synchronized
  fun refresh(hours: Int = state.value.hours) {
    require(hours in listOf(1, 24, 168))
    generation++
    dnsJob?.cancel()
    activityJob?.cancel()
    dnsJob = null
    activityJob = null
    val window = dashboardWindow(hours)
    mutable.update {
      it.copy(
          hours = hours,
          window = window,
          dns = null,
          activity = null,
          dnsError = null,
          activityError = null,
      )
    }
    dnsDirty = true
    activityDirty = true
    readDns()
    readActivity()
  }

  @Synchronized
  private fun readDns() {
    if (dnsJob != null) {
      dnsDirty = true
      return
    }
    dnsDirty = false
    val binding = controlD.state.value.binding
    if (binding == null) {
      mutable.update {
        it.copy(
            dns = null,
            dnsLoading = false,
            dnsError = "Select a Control D endpoint/client to read its retained history.",
        )
      }
      return
    }
    val epoch = generation
    val window = state.value.window
    mutable.update { it.copy(dnsLoading = true, dnsError = null) }
    val next =
        scope.launch(Dispatchers.IO, start = CoroutineStart.LAZY) {
          val owner = currentCoroutineContext()[Job]
          try {
            val (revision, rows) = controlD.store.facts(binding, window.from, window.until)
            val data = DashboardDnsSnapshot(binding, window, revision, rows)
            synchronized(this@DashboardModel) {
              if (
                  generation == epoch && dnsJob === owner && controlD.state.value.binding == binding
              )
                  mutable.update { it.copy(dns = data) }
            }
          } catch (cancelled: CancellationException) {
            throw cancelled
          } catch (_: Exception) {
            synchronized(this@DashboardModel) {
              if (generation == epoch && dnsJob === owner)
                  mutable.update {
                    it.copy(dnsError = "DNS history unavailable. Refresh explicitly to read again.")
                  }
            }
          } finally {
            synchronized(this@DashboardModel) {
              if (dnsJob === owner) {
                dnsJob = null
                mutable.update { it.copy(dnsLoading = false) }
                if (dnsDirty && visible) readDns()
              }
            }
          }
        }
    dnsJob = next
    next.start()
  }

  @Synchronized
  private fun readActivity() {
    if (activityJob != null) {
      activityDirty = true
      return
    }
    activityDirty = false
    val selected = tailnet
    if (selected == null) {
      mutable.update {
        it.copy(
            activity = null,
            activityLoading = false,
            activityError = "Current tailnet context is unavailable; this is not zero activity.",
        )
      }
      return
    }
    val epoch = generation
    val window = state.value.window
    mutable.update { it.copy(activityLoading = true, activityError = null) }
    val next =
        scope.launch(Dispatchers.IO, start = CoroutineStart.LAZY) {
          val owner = currentCoroutineContext()[Job]
          try {
            val data = history.query(selected, window)
            synchronized(this@DashboardModel) {
              if (generation == epoch && activityJob === owner && tailnet == selected)
                  mutable.update { it.copy(activity = data) }
            }
          } catch (cancelled: CancellationException) {
            throw cancelled
          } catch (_: Exception) {
            synchronized(this@DashboardModel) {
              if (generation == epoch && activityJob === owner)
                  mutable.update {
                    it.copy(
                        activityError =
                            "Local activity history unavailable. Refresh explicitly to read again."
                    )
                  }
            }
          } finally {
            synchronized(this@DashboardModel) {
              if (activityJob === owner) {
                activityJob = null
                mutable.update { it.copy(activityLoading = false) }
                if (activityDirty && visible) readActivity()
              }
            }
          }
        }
    activityJob = next
    next.start()
  }

  @Synchronized
  fun prepareTrafficExport(data: TrafficSnapshot, identity: String?): Boolean =
      prepareExport(Export.Traffic(data, identity))

  @Synchronized
  fun prepareDnsExport(data: DashboardDnsSnapshot, filter: DashboardDnsFilter): Boolean =
      prepareExport(Export.Dns(data, filter))

  @Synchronized
  fun prepareActivityExport(
      data: DashboardActivitySnapshot,
      kind: String?,
      search: String,
  ): Boolean = prepareExport(Export.Activity(data, kind, search))

  private fun prepareExport(value: Export): Boolean {
    if (pendingExport != null || state.value.exportWriting) return false
    pendingExport = value
    exportedDocumentForTest = null
    mutable.update { it.copy(exportPending = true, exportNotice = null) }
    return true
  }

  @Synchronized
  fun writeExport(resolver: ContentResolver, uri: Uri?) {
    val captured = pendingExport
    pendingExport = null
    if (uri == null) {
      mutable.update { it.copy(exportPending = false, exportNotice = "Export cancelled.") }
      return
    }
    if (captured == null) {
      mutable.update {
        it.copy(
            exportPending = false,
            exportNotice = "Export context was lost. Select the scope/window again.",
        )
      }
      return
    }
    mutable.update { it.copy(exportPending = false, exportWriting = true, exportNotice = null) }
    scope.launch(Dispatchers.IO) {
      try {
        checkNotNull(resolver.openOutputStream(uri, "wt")).bufferedWriter(Charsets.UTF_8).use {
            writer ->
          when (captured) {
            is Export.Traffic -> writer.write(captured.data.export(captured.identity))
            is Export.Dns -> captured.data.export(captured.filter, writer)
            is Export.Activity -> captured.data.export(captured.kind, captured.search, writer)
          }
        }
        if (com.tailscale.ipn.BuildConfig.DEBUG) exportedDocumentForTest = uri
        mutable.update {
          it.copy(exportNotice = "Selected snapshot exported to your chosen document.")
        }
      } catch (_: Exception) {
        mutable.update {
          it.copy(
              exportNotice =
                  "Export failed. The selected document may be incomplete; select Export again to retry explicitly."
          )
        }
      } finally {
        mutable.update { it.copy(exportWriting = false) }
      }
    }
  }
}
