// Copyright (c) TailD contributors. SPDX-License-Identifier: BSD-3-Clause
package com.tailscale.ipn.taild

import android.content.Context
import com.tailscale.ipn.ui.localapi.Client
import com.tailscale.ipn.ui.model.LocalDNSStatus
import java.net.URI
import java.time.Instant
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.serialization.json.*

data class ControlDPreview(
    val ticket: String,
    val policy: ControlDPolicy,
    val change: ControlDChange,
    val eventProfile: String?,
)

data class ControlDState(
    val binding: ControlDBinding? = null,
    val endpointName: String = "No endpoint selected",
    val clientName: String? = null,
    val inventory: ControlDInventory? = null,
    val clients: List<ControlDClient> = emptyList(),
    val policy: ControlDPolicy? = null,
    val page: ControlDDnsPage = ControlDDnsPage(),
    val transient: List<ControlDStoredFact>? = null,
    val hasRead: Boolean = false,
    val hasWrite: Boolean = false,
    val busySetup: Boolean = false,
    val busyPolicy: Boolean = false,
    val busyHistory: Boolean = false,
    val historyProgress: String? = null,
    val busyWrite: Boolean = false,
    val search: String = "",
    val error: String? = null,
    val historyError: String? = null,
    val notice: String? = null,
    val resolverNotice: String = "Resolver association has not been checked",
    val preview: ControlDPreview? = null,
    val unresolved: Boolean = false,
)

/**
 * Application-owned provider work; navigation never becomes a second collector or a write intent.
 */
class ControlDModel(
    context: Context,
    private val scope: CoroutineScope,
    private val activity: TailDHistory,
    internal val api: ControlDApi = ControlDApi(),
    internal val vault: ControlDCredentials = ControlDCredentials(context),
    internal val store: ControlDDnsStore = ControlDDnsStore(context),
) {
  private val settings =
      context.getSharedPreferences("taild.controld.settings", Context.MODE_PRIVATE)
  private val generation = AtomicLong()
  private val reviewGeneration = AtomicLong()
  private val setupJob = AtomicReference<Job?>()
  private val policyJob = AtomicReference<Job?>()
  private val historyJob = AtomicReference<Job?>()
  private var queryJob: Job? = null
  private val writeLock = Mutex()
  private var pending: ControlDPreview? = null
  private val _state =
      MutableStateFlow(
          ControlDState(
              binding =
                  settings.getString("binding", null)?.let {
                    runCatching { bindingFromJson(Json.parseToJsonElement(it).jsonObject) }
                        .getOrNull()
                  },
              endpointName = settings.getString("endpoint-name", null) ?: "No endpoint selected",
              clientName = settings.getString("client-name", null),
              hasRead = vault.contains(ControlDCredentials.Access.READ),
              hasWrite = vault.contains(ControlDCredentials.Access.WRITE),
              unresolved = settings.contains("pending-change"),
          )
      )
  val state = _state.asStateFlow()

  init {
    scope.launch { activity.enabled.drop(1).collect { if (!it) cancelHistoryRead() } }
    loadLocal()
    scope.coroutineContext[Job]?.invokeOnCompletion { store.close() }
  }

  private fun token(access: ControlDCredentials.Access): String =
      vault.read(access)
          ?: throw ControlDFailure(
              "credentials",
              "Configure the ${if(access == ControlDCredentials.Access.READ) "READ" else "separate Write"} credential in setup",
          )

  private fun message(problem: Exception): String =
      (problem as? ControlDFailure)?.let {
        it.message.orEmpty() +
            (it.retryAfter?.let { retry ->
              " Retry-After: $retry. No automatic retry is scheduled."
            } ?: "")
      }
          ?: "Control D is unavailable. Previously displayed observations may be stale; refresh explicitly."

  @Synchronized
  private fun invalidate(preserveSetup: Boolean = false) {
    generation.incrementAndGet()
    reviewGeneration.incrementAndGet()
    if (!preserveSetup) setupJob.getAndSet(null)?.cancel()
    policyJob.getAndSet(null)?.cancel()
    historyJob.getAndSet(null)?.cancel()
    queryJob?.cancel()
    pending = null
    _state.update {
      it.copy(
          preview = null,
          busySetup = if (preserveSetup) it.busySetup else false,
          busyPolicy = false,
          busyHistory = false,
          transient = null,
      )
    }
  }

  @Synchronized
  private fun read(
      job: AtomicReference<Job?>,
      history: Boolean = false,
      setup: Boolean = false,
      action: suspend (Long) -> Unit,
  ) {
    val previous = job.get()
    if (previous != null && !previous.isCompleted) return
    val epoch = generation.get()
    val next =
        scope.launch(Dispatchers.IO, start = CoroutineStart.LAZY) {
          val owner = currentCoroutineContext()[Job]
          try {
            action(epoch)
          } catch (cancelled: CancellationException) {
            if (history && generation.get() == epoch && job.get() === owner)
                _state.update {
                  it.copy(
                      historyError = "History read cancelled. Stored observations are preserved."
                  )
                }
            throw cancelled
          } catch (problem: Exception) {
            if (generation.get() == epoch && job.get() === owner)
                _state.update {
                  if (history) it.copy(historyError = message(problem))
                  else it.copy(error = message(problem), preview = null)
                }
          } finally {
            synchronized(this@ControlDModel) {
              if (job.compareAndSet(owner, null))
                  _state.update {
                    when {
                      history -> it.copy(busyHistory = false, historyProgress = null)
                      setup -> it.copy(busySetup = false)
                      else -> it.copy(busyPolicy = false)
                    }
                  }
            }
          }
        }
    if (!job.compareAndSet(previous, next)) {
      next.cancel()
      return
    }
    _state.update {
      when {
        history -> it.copy(busyHistory = true, historyError = null)
        setup -> it.copy(busySetup = true, error = null)
        else -> it.copy(busyPolicy = true, error = null)
      }
    }
    next.start()
  }

  fun open() {
    if (state.value.hasRead) {
      if (state.value.inventory == null) refreshInventory()
      else {
        if (state.value.policy == null) refreshPolicy()
        refreshHistory()
      }
    }
    loadLocal()
    refreshResolver()
  }

  fun configureRead(raw: String, organization: String?) {
    if (state.value.busyWrite) return
    read(setupJob, setup = true) { epoch ->
      val token = raw.trim()
      ControlDCredentials.validate(token)
      val org = organization?.trim()?.takeIf(String::isNotBlank)?.let(::cdIdentifier)
      val inventory = api.inventory(token, org)
      if (generation.get() != epoch) return@read
      val previous = state.value.binding
      val previousAccount = settings.getString("account", null)
      val previousOrganization = settings.getString("organization", null)
      val binding = previous?.takeIf {
        it.account == inventory.account &&
            it.organization == org &&
            inventory.endpoints.any { endpoint -> endpoint.id == it.endpoint }
      }
      configurationCommit {
        if (generation.get() != epoch) return@read
        vault.save(ControlDCredentials.Access.READ, token)
        if (previousAccount != inventory.account || previousOrganization != org)
            vault.remove(ControlDCredentials.Access.WRITE)
        invalidate(preserveSetup = true)
        check(
            settings
                .edit()
                .putString("organization", org)
                .putString("account", inventory.account)
                .apply { if (binding == null) remove("binding") }
                .commit()
        )
        _state.update {
          it.copy(
              binding = binding,
              endpointName = if (binding == null) "No endpoint selected" else it.endpointName,
              clientName = if (binding == null) null else it.clientName,
              inventory = inventory,
              policy = null,
              page = ControlDDnsPage(),
              hasRead = true,
              hasWrite = vault.contains(ControlDCredentials.Access.WRITE),
              error = null,
              notice =
                  "READ access connected. Select the endpoint and optional client used by your resolver.",
          )
        }
      }
      if (binding != null) {
        refreshPolicy()
        refreshHistory()
      }
    }
  }

  fun configureWrite(raw: String) {
    if (state.value.busyWrite) return
    read(setupJob, setup = true) { epoch ->
      val readToken = token(ControlDCredentials.Access.READ)
      val org =
          state.value.inventory?.organization
              ?: state.value.binding?.organization
              ?: settings.getString("organization", null)
      val expected = api.account(readToken, org).first
      val writeToken = raw.trim()
      ControlDCredentials.validate(writeToken)
      cdRequire(
          api.account(writeToken, org).first == expected,
          "Write credential belongs to a different account",
      )
      if (generation.get() != epoch) return@read
      configurationCommit {
        if (generation.get() != epoch) return@read
        vault.save(ControlDCredentials.Access.WRITE, writeToken)
        pending = null
        _state.update {
          it.copy(
              hasWrite = true,
              preview = null,
              notice = "Separate Write credential saved. Browsing continues to use READ access.",
          )
        }
      }
    }
  }

  fun removeCredentials() = writeWork {
    invalidate()
    vault.remove(ControlDCredentials.Access.READ)
    vault.remove(ControlDCredentials.Access.WRITE)
    _state.update {
      it.copy(
          hasRead = false,
          hasWrite = false,
          inventory = null,
          policy = null,
          error = null,
          notice = "Saved credentials removed. Scoped history is preserved.",
      )
    }
  }

  private inline fun configurationCommit(block: () -> Unit) =
      synchronized(this) {
        if (!writeLock.tryLock())
            throw ControlDFailure(
                "busy",
                "An explicit policy change is still running. Wait for its result before changing API setup.",
            )
        try {
          block()
        } finally {
          writeLock.unlock()
        }
      }

  fun refreshInventory() =
      read(setupJob, setup = true) { epoch ->
        val inventory =
            api.inventory(
                token(ControlDCredentials.Access.READ),
                state.value.binding?.organization ?: settings.getString("organization", null),
            )
        val binding = state.value.binding
        if (binding != null)
            cdRequire(
                inventory.account == binding.account,
                "Credential account no longer matches the saved binding",
            )
        if (generation.get() == epoch) {
          val endpoint = binding?.let { current ->
            inventory.endpoints.find { it.id == current.endpoint }
          }
          val clients =
              endpoint?.clients
                  ?: if (endpoint != null)
                      try {
                        api.clients(token(ControlDCredentials.Access.READ), inventory, endpoint)
                      } catch (_: ControlDFailure) {
                        emptyList()
                      }
                  else emptyList()
          if (generation.get() != epoch) return@read
          _state.update {
            it.copy(
                inventory = inventory,
                clients = clients,
                endpointName = endpoint?.name ?: it.endpointName,
                clientName =
                    clients.find { client -> client.id == binding?.client }?.name ?: it.clientName,
            )
          }
          if (binding != null) {
            refreshPolicy()
            refreshHistory()
          }
        }
      }

  @Synchronized
  fun select(endpoint: ControlDEndpoint, client: ControlDClient? = null) {
    if (state.value.busyWrite) return
    val inventory = state.value.inventory ?: return
    if (
        inventory.endpoints.none { it.id == endpoint.id } ||
            (client != null &&
                endpoint.clients.orEmpty().none { it.id == client.id } &&
                (state.value.binding?.endpoint != endpoint.id ||
                    state.value.clients.none { it.id == client.id }))
    ) {
      _state.update { it.copy(error = "Endpoint/client selection is stale. Reload inventory.") }
      return
    }
    if (!writeLock.tryLock()) return
    try {
      invalidate()
      val binding =
          ControlDBinding(inventory.account, inventory.organization, endpoint.id, client?.id)
      check(
          settings
              .edit()
              .putString("binding", bindingToJson(binding).toString())
              .putString("endpoint-name", endpoint.name)
              .putString("client-name", client?.name)
              .commit()
      )
      _state.update {
        it.copy(
            binding = binding,
            endpointName = endpoint.name,
            clientName = client?.name,
            clients = endpoint.clients.orEmpty(),
            policy = null,
            page = ControlDDnsPage(),
            error = null,
            historyError = null,
            notice = null,
        )
      }
    } catch (problem: Exception) {
      _state.update { it.copy(error = message(problem)) }
      return
    } finally {
      writeLock.unlock()
    }
    loadLocal()
    refreshPolicy()
    refreshHistory()
    refreshResolver()
    if (endpoint.clients == null)
        read(setupJob, setup = true) { epoch ->
          val clients = api.clients(token(ControlDCredentials.Access.READ), inventory, endpoint)
          if (generation.get() == epoch) _state.update { it.copy(clients = clients) }
        }
  }

  fun refreshPolicy() {
    if (state.value.busyWrite) return
    val binding = state.value.binding ?: return
    dismissPreview()
    read(policyJob) { epoch ->
      val owner = currentCoroutineContext()[Job]
      val policy = api.policy(token(ControlDCredentials.Access.READ), binding)
      synchronized(this@ControlDModel) {
        if (generation.get() == epoch && policyJob.get() === owner)
            _state.update { it.copy(policy = policy) }
      }
    }
  }

  fun refreshHistory(full: Boolean = false) {
    val binding = state.value.binding ?: return
    if (!state.value.hasRead) return
    read(historyJob, history = true) { epoch ->
      val readToken = token(ControlDCredentials.Access.READ)
      val (account, region) = api.account(readToken, binding.organization)
      cdRequire(account == binding.account, "Credential account does not match this DNS scope")
      val selectedRegion =
          region ?: throw ControlDFailure("unavailable", "Provider analytics region is unavailable")
      val capturedUntil = Instant.now()
      val window =
          DashboardWindow(capturedUntil.minusMillis(TailDHistory.RETENTION_MILLIS), capturedUntil)
      val recording = activity.enabled.value
      val returned = if (full || !recording) emptyList() else store.returnedWindows(binding, window)
      val windows =
          if (recording) historyCatchup(window, returned)
          else listOf(DashboardWindow(window.until.minusSeconds(900), window.until))
      val queue = java.util.ArrayDeque(windows)
      val transientFacts = mutableListOf<ControlDDnsFact>()
      var incomplete = false
      while (queue.isNotEmpty()) {
        currentCoroutineContext().ensureActive()
        if (generation.get() != epoch) return@read
        val part = queue.removeFirst()
        _state.update {
          it.copy(
              historyProgress =
                  "Reading ${part.from} → ${part.until} UTC · ${queue.size} queued windows"
          )
        }
        val slice =
            try {
              api.history(readToken, binding, selectedRegion, part.from, part.until)
            } catch (problem: ControlDFailure) {
              if (
                  problem.state != "incomplete" ||
                      java.time.Duration.between(part.from, part.until).toMillis() <= 1000
              )
                  throw problem
              val midpoint =
                  part.from.plusNanos(
                      java.time.Duration.between(part.from, part.until).toNanos() / 2
                  )
              queue.addFirst(DashboardWindow(part.from, midpoint))
              queue.addFirst(DashboardWindow(midpoint, part.until))
              continue
            }
        if (
            slice.truncated && java.time.Duration.between(part.from, part.until).toMillis() > 1000
        ) {
          val midpoint =
              part.from.plusNanos(java.time.Duration.between(part.from, part.until).toNanos() / 2)
          queue.addFirst(DashboardWindow(part.from, midpoint))
          queue.addFirst(DashboardWindow(midpoint, part.until))
          continue
        }
        if (generation.get() != epoch) return@read
        currentCoroutineContext().ensureActive()
        val persisted = activity.importDns(store, slice)
        if (generation.get() != epoch) return@read
        incomplete = incomplete || slice.truncated
        if (!persisted || slice.truncated)
            transientFacts += slice.facts.filter { it.at >= window.until.minusSeconds(900) }
        val counts = mutableMapOf<String, Int>()
        _state.update {
          it.copy(
              transient =
                  if (transientFacts.isEmpty() && persisted) null
                  else
                      transientFacts.map { fact ->
                        val ordinal = (counts[fact.identity] ?: 0) + 1
                        counts[fact.identity] = ordinal
                        ControlDStoredFact(fact.identity + ":" + ordinal, fact)
                      },
              historyError =
                  if (incomplete)
                      "Provider result is incomplete. Previous stored totals were preserved."
                  else null,
          )
        }
        loadLocal()
      }
      refreshResolver()
    }
  }

  @Synchronized
  fun cancelHistoryRead() {
    val job = historyJob.get()
    if (job != null && !job.isCompleted) {
      _state.update {
        it.copy(
            historyProgress = "Cancelling history read; waiting for its current operation to finish"
        )
      }
      job.cancel()
    } else
        _state.update {
          it.copy(historyError = "History recording is off. Stored observations are preserved.")
        }
  }

  fun search(value: String) {
    _state.update { it.copy(search = value.take(256)) }
    loadLocal()
  }

  @Synchronized
  private fun loadLocal() {
    val binding = state.value.binding ?: return
    val search = state.value.search
    val epoch = generation.get()
    queryJob?.cancel()
    queryJob =
        scope.launch(Dispatchers.IO) {
          try {
            val page = store.recent(binding, search)
            if (generation.get() == epoch && state.value.search == search)
                _state.update { it.copy(page = page) }
          } catch (cancelled: CancellationException) {
            throw cancelled
          } catch (problem: Exception) {
            if (generation.get() == epoch)
                _state.update { it.copy(historyError = message(problem)) }
          }
        }
  }

  private fun refreshResolver() {
    val binding = state.value.binding ?: return
    val epoch = generation.get()
    Client(scope).localDNS { result ->
      if (generation.get() == epoch)
          _state.update {
            it.copy(
                resolverNotice =
                    result.getOrNull()?.let { resolverNotice(it, binding) }
                        ?: "Configured resolver could not be checked. This is the selected provider scope, not proof of device attribution."
            )
          }
    }
  }

  private fun resolverNotice(dns: LocalDNSStatus, binding: ControlDBinding): String {
    if (!dns.Configured)
        return "No local resolver override is configured. This selected scope is not proof that this device uses it."
    val endpoint = state.value.inventory?.endpoints?.find { it.id == binding.endpoint }
    val ids = listOfNotNull(binding.endpoint, endpoint?.deviceId).distinct()
    val value = dns.Endpoint
    val uri = runCatching { URI(value) }.getOrNull()
    val matches = ids.any { id ->
      val path = "/$id" + (binding.client?.let { "/$it" } ?: "")
      (uri?.scheme == "https" &&
          uri.host == "dns.controld.com" &&
          uri.rawQuery == null &&
          uri.rawFragment == null &&
          uri.path.trimEnd('/') == path) ||
          value == id + (binding.client?.let { "-$it" } ?: "") + ".dns.controld.com"
    }
    return if (matches)
        "Configured resolver matches this endpoint/client. Imported DNS records verify the returned provider scope; gaps remain unknown."
    else
        "Configured resolver does not match this exact endpoint/client. Results describe the selected provider scope, not this device."
  }

  fun clearHistory() =
      scope.launch(Dispatchers.IO) {
        try {
          historyJob.getAndSet(null)?.cancelAndJoin()
          store.deleteHistory()
          _state.update { it.copy(transient = null, page = ControlDDnsPage(), historyError = null) }
          loadLocal()
        } catch (problem: Exception) {
          _state.update { it.copy(historyError = message(problem)) }
        }
      }

  @Synchronized
  fun dismissPreview() {
    reviewGeneration.incrementAndGet()
    pending = null
    _state.update { it.copy(preview = null, notice = null) }
  }

  @Synchronized
  private fun writeWork(action: suspend () -> Unit) {
    if (!writeLock.tryLock()) return
    // A pre-change reader must never replace this operation's verified readback.
    policyJob.getAndSet(null)?.cancel()
    _state.update { it.copy(busyWrite = true, busyPolicy = false, error = null, notice = null) }
    scope.launch(Dispatchers.IO) {
      try {
        action()
      } catch (cancelled: CancellationException) {
        throw cancelled
      } catch (problem: Exception) {
        _state.update {
          it.copy(error = message(problem), unresolved = settings.contains("pending-change"))
        }
      } finally {
        synchronized(this@ControlDModel) {
          writeLock.unlock()
          _state.update { it.copy(busyWrite = false) }
        }
      }
    }
  }

  private suspend fun validatedWrite(binding: ControlDBinding): Pair<String, String> {
    val read = token(ControlDCredentials.Access.READ)
    val write = token(ControlDCredentials.Access.WRITE)
    cdRequire(
        api.account(read, binding.organization).first == binding.account &&
            api.account(write, binding.organization).first == binding.account,
        "READ and Write credentials must belong to the selected account",
    )
    return read to write
  }

  fun prepare(change: ControlDChange, eventProfile: String? = null) {
    val review = reviewGeneration.get()
    writeWork {
      cdRequire(
          !settings.contains("pending-change"),
          "An earlier change has an unresolved outcome. Reconcile it first.",
      )
      val shown =
          state.value.policy ?: throw ControlDFailure("unavailable", "Reload policy before editing")
      val (read, _) = validatedWrite(shown.binding)
      val fresh = api.policy(read, shown.binding)
      cdRequire(
          state.value.binding == fresh.binding &&
              fresh.profile == shown.profile &&
              (eventProfile == null || fresh.profile == eventProfile),
          "The selected policy changed. Reload before editing.",
      )
      checkControlDIntent(fresh, fresh, eventProfile)
      controlDMutation(fresh, change)
      val preview = ControlDPreview(UUID.randomUUID().toString(), fresh, change, eventProfile)
      synchronized(this@ControlDModel) {
        if (reviewGeneration.get() == review) {
          pending = preview
          _state.update { it.copy(policy = fresh, preview = preview) }
        }
      }
    }
  }

  fun applyPreview(ticket: String) = writeWork {
    val preview = pending
    pending = null
    _state.update { it.copy(preview = null) }
    cdRequire(
        preview != null && preview.ticket == ticket,
        "This review has already been consumed or invalidated",
    )
    apply(checkNotNull(preview).policy, preview.change, preview.eventProfile)
  }

  fun incident(fact: ControlDDnsFact, action: Int) = writeWork {
    pending = null
    _state.update { it.copy(preview = null) }
    val shown =
        state.value.policy ?: throw ControlDFailure("unavailable", "Reload current policy first")
    cdRequire(
        fact.action in 0..3 &&
            fact.profile != null &&
            fact.raw["endpointId"] == shown.binding.endpoint &&
            (shown.binding.client == null || fact.raw["clientId"] == shown.binding.client),
        "This DNS event does not match the selected binding",
    )
    apply(shown, ControlDChange.Rule(fact.question, action, true, "TailD incident"), fact.profile)
  }

  private suspend fun apply(shown: ControlDPolicy, change: ControlDChange, eventProfile: String?) {
    cdRequire(!settings.contains("pending-change"), "Reconcile the earlier unresolved change first")
    cdRequire(state.value.binding == shown.binding, "Endpoint binding changed")
    val (read, write) = validatedWrite(shown.binding)
    val fresh = api.policy(read, shown.binding)
    checkControlDIntent(shown, fresh, eventProfile)
    val mutation = controlDMutation(fresh, change)
    val receipt = buildJsonObject {
      put("binding", bindingToJson(fresh.binding))
      put("profile", fresh.profile)
      put("profile-name", fresh.profileName)
      put("affected", JsonArray(fresh.affectedIds.map(::JsonPrimitive)))
      put("change", changeToJson(change))
      put("group", mutation.expectedGroup ?: JsonNull)
      put("requested-at", Instant.now().toString())
    }
    check(settings.edit().putString("pending-change", receipt.toString()).commit())
    _state.update { it.copy(unresolved = true) }
    try {
      api.mutate(write, fresh.binding.organization, mutation)
    } catch (failure: ControlDFailure) {
      if (
          failure.status in listOf(401, 403, 404, 405, 429) || failure.state == "redirect-refused"
      ) {
        check(settings.edit().remove("pending-change").commit())
        _state.update { it.copy(unresolved = false) }
      }
      throw failure
    }
    try {
      val after = api.policy(read, fresh.binding)
      if (
          after.profile != fresh.profile ||
              after.affectedIds != fresh.affectedIds ||
              !controlDChangeVerified(after, change, mutation)
      )
          throw ControlDFailure(
              "outcome-unknown",
              "Provider readback differs from the requested change",
          )
      check(settings.edit().remove("pending-change").commit())
      _state.update {
        it.copy(
            policy = after,
            unresolved = false,
            notice = "Change applied and current provider policy verified.",
        )
      }
    } catch (_: Exception) {
      throw ControlDFailure(
          "outcome-unknown",
          "Change outcome is unknown. Reconcile policy; this intent will not be retried.",
      )
    }
  }

  fun reconcile() = writeWork {
    val receipt = settings.getString("pending-change", null) ?: return@writeWork
    val journal = runCatching {
      Json.parseToJsonElement(receipt).jsonObject
    }
        .getOrElse {
          throw ControlDFailure(
              "outcome-unknown",
              "The pending change receipt is unreadable; no write is allowed",
          )
        }
    val binding = bindingFromJson(journal.getValue("binding").jsonObject)
    cdRequire(
        state.value.binding == binding,
        "Select the original endpoint/client and account to reconcile the earlier change",
    )
    val fresh = api.policy(token(ControlDCredentials.Access.READ), binding)
    val change = changeFromJson(journal.getValue("change").jsonObject)
    val affected = journal.getValue("affected").jsonArray.map { it.jsonPrimitive.content }
    val verified =
        fresh.profile == journal.text("profile") &&
            fresh.affectedIds == affected &&
            controlDChangeVerified(
                fresh,
                change,
                ControlDMutation(
                    "",
                    "",
                    emptyMap(),
                    journal["group"]?.takeUnless { it == JsonNull },
                ),
            )
    if (verified) check(settings.edit().remove("pending-change").commit())
    _state.update {
      it.copy(
          policy = fresh,
          unresolved = !verified,
          notice =
              if (verified)
                  "The requested change is present in current provider policy. Nothing was retried."
              else
                  "Current policy does not verify the earlier change. Its outcome remains unresolved; nothing was retried.",
      )
    }
  }

  fun acknowledgeCurrentPolicy() = writeWork {
    val shown =
        state.value.policy
            ?: throw ControlDFailure("unavailable", "Read current policy before accepting it")
    val journal =
        settings.getString("pending-change", null)?.let { Json.parseToJsonElement(it).jsonObject }
            ?: return@writeWork
    cdRequire(
        bindingFromJson(journal.getValue("binding").jsonObject) == shown.binding,
        "Select the original account and endpoint before accepting current policy",
    )
    val fresh = api.policy(token(ControlDCredentials.Access.READ), shown.binding)
    checkControlDIntent(shown, fresh)
    check(settings.edit().remove("pending-change").commit())
    _state.update {
      it.copy(
          policy = fresh,
          unresolved = false,
          notice = "Current policy accepted. The earlier write was neither retried nor undone.",
      )
    }
  }
}

internal fun bindingToJson(value: ControlDBinding) = buildJsonObject {
  put("account", value.account)
  put("organization", value.organization?.let(::JsonPrimitive) ?: JsonNull)
  put("endpoint", value.endpoint)
  put("client", value.client?.let(::JsonPrimitive) ?: JsonNull)
}

internal fun bindingFromJson(value: JsonObject) =
    ControlDBinding(
        cdIdentifier(value.text("account") ?: ""),
        value.text("organization")?.let(::cdIdentifier),
        cdIdentifier(value.text("endpoint") ?: ""),
        value.text("client")?.let(::cdClientIdentifier),
    )

internal fun changeToJson(value: ControlDChange): JsonObject = buildJsonObject {
  when (value) {
    is ControlDChange.Rule -> {
      put("kind", "rule")
      put("hostname", value.hostname)
      put("do", value.action)
      put("enabled", value.enabled)
      put("comment", value.comment)
      put("delete", value.delete)
    }
    is ControlDChange.Filter -> {
      put("kind", "filter")
      put("id", value.id)
      put("enabled", value.enabled)
    }
    is ControlDChange.Service -> {
      put("kind", "service")
      put("id", value.id)
      put("do", value.action)
      put("enabled", value.enabled)
    }
    is ControlDChange.Option -> {
      put("kind", "option")
      put("id", value.id)
      put("enabled", value.enabled)
    }
  }
}

internal fun changeFromJson(value: JsonObject): ControlDChange {
  val enabled =
      (value["enabled"] as? JsonPrimitive)?.booleanOrNull
          ?: throw ControlDFailure("incompatible", "Invalid management receipt")
  return when (value.text("kind")) {
    "rule" ->
        ControlDChange.Rule(
            value.text("hostname") ?: "",
            value.number("do") ?: -1,
            enabled,
            value.text("comment").orEmpty(),
            (value["delete"] as? JsonPrimitive)?.booleanOrNull == true,
        )
    "filter" -> ControlDChange.Filter(value.text("id") ?: "", enabled)
    "service" -> ControlDChange.Service(value.text("id") ?: "", value.number("do") ?: -1, enabled)
    "option" -> ControlDChange.Option(value.text("id") ?: "", enabled)
    else -> throw ControlDFailure("incompatible", "Unsupported management receipt")
  }
}
