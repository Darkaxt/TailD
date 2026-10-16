# TailD Android expansion proposal

Date: 2026-10-16. Status: planning and brainstorming only.

This proposal does not activate implementation, close desktop Stage 10/B12,
change a schedule, configure signing,
publish a release, or authorize installation or provider-policy changes.
Its proposed stages are all NOT STARTED.

## Confirmed direction

- Android belongs to **Darkaxt/TailD**, which is an expanded TailDNS derivative.
  Implement TailD-specific Android features in this repository's inherited
  Android client; do not add them to Darkaxt/TailDNS first or create another app.
- Expand Tailscale representation, basic Control D management and compatible
  dashboards first. App/IP traffic auditing, equal-weight domain estimates and
  app blocking are required later on both Windows and Android under
  [R33's named F1–F3 stages](TRAFFIC-AUDIT-AND-BLOCKING-SPECIFICATION.md).
- Prefer battery-conscious collection. Do not require an uninterrupted Android
  DNS stream to build historical DNS dashboards.
- Correctly configured Control D resolvers already identify endpoints/clients.
  Control D records DNS facts server-side; Android reads those facts later.
  DNS ingestion is synchronization, not packet capture or app attribution.
- Existing README screenshots may remain slightly outdated.

## Source-verified starting point

Inspected TailD main at 8e81c27fccdae0a5e75a7e1e421db25e2669814d.

| Existing boundary | Reuse and remaining work |
| --- | --- |
| `android/src/main/java/com/tailscale/ipn/ui/notifier/Notifier.kt` | Application-scoped IPN notifications, peer changes, preferences, health and TailDrop flows already exist. Add durable observation handling without another daemon watcher. |
| `ui/localapi/Client.kt` | Existing status, preference, DNS, profiles, ping and file APIs. Extend only where the required metadata is missing. |
| `ui/model/IpnState.kt`, `Tailcfg.kt` | Presence, last seen, identities, addresses, routes and capability metadata exist. Preserve unknown values; missing booleans must not silently become Disabled/Offline in new UI. |
| `MainActivity.kt`, `ui/viewModel/*`, `ui/view/*` | Native Compose/navigation and peer/control screens exist. Expand these patterns. |
| `util/ShareFileHelper.kt`, TailDrop view models | Transfer notifications and Android document-save callbacks exist; recent-recipient preferences are not a durable transfer ledger. |
| `IPNService.kt`, `App.kt` | Existing VPN/background lifecycle and application coroutine scope. Analytics must never delay VPN connect/disconnect or change explicit disconnect behavior. |
| `android/build.gradle.kts` | Current package is `io.github.darkaxt.taildns`; Compose, coroutines, Room KTX and Vico chart dependencies already exist. Room dependency alone does not establish an implemented database or compiler setup. |
| `scripts/taild/{controld,management,live_dns,history,tailscale_activity}.py` | Desktop behavior, provider normalization, safe-write and evidence contracts are reusable references; Windows Python/vault/pipe code is not an Android runtime. |
| `.github/workflows/taild-inherit.yml` | Existing TailDNS inheritance and inherited Android/core checks must preserve Android-specific TailD changes. |

Live GitHub workflow inventory confirms inherited Android CI, TailDNS validation
and TailDNS release workflows are disabled in TailD. `fork-release.yml` also
restricts execution to Darkaxt/TailDNS. Current TailD delivery is Windows-only;
an Android release needs a deliberately scoped TailD workflow.

## Approach choices

1. **Recommended: native Compose expansion inside TailD Android.** Reuse the
   installed VPN/client model; implement the required Control D behavior in
   Kotlin, with local persistence and native mobile charts. Share data meanings,
   action mappings and synthetic contract fixtures with desktop. This duplicates
   some implementation across Kotlin/Python but preserves a small Android runtime
   and avoids inventing a cross-platform backend before it is needed.
2. **Embed the desktop Angular UI.** Some charts/styles could be reused, but the
   Windows collector, Python runtime and IPC would still need replacement. A new
   native bridge plus WebView lifecycle, accessibility and mobile layout work
   make this less attractive for the requested scope.
3. **Android as a remote Windows dashboard.** Reuses desktop data and queries but
   requires an available Windows service, remote API and authentication. It does
   not provide independent on-device history or the desired integrated client.

Keep shared Tailscale core responsible for VPN/DNS behavior. Do not add provider
management to shared core simply to eliminate a small Kotlin API implementation.

## Proposed user experience and feature scope

Use three top-level destinations: **Tailscale**, **Control D**, **Dashboard**.
Open on Tailscale Connection. Settings/About remain consistently reachable.
Use a bottom bar on phones and a rail with list/detail layouts on wider screens.
Keep the current Android visual language while matching desktop meanings and
labels; do not shrink a desktop table/sidebar into a phone screen.

| Area | Android scope |
| --- | --- |
| Connection | Searchable visible peers, owner, OS, IP/MagicDNS, actual reported last online, supported routes/tags and details. Keep local connection, exit-node and DNS controls. |
| TailDrop capability | Only `TailDrop · Enabled` / `TailDrop · Disabled` when known and applicable; hide unknown/offline capability labels. Presence remains separate. |
| Tailscale activity | Recorded presence/connection/exit-node/resolver-health changes, baselines and observation gaps. No invented historical uptime or proof of ping reachability. |
| TailDrop history | Observed outgoing results and incoming receipts; distinguish an actual successful Android document-save callback from daemon receipt. Store metadata, never file/text/clipboard contents. |
| Control D setup | READ credential, explicit endpoint/client selection, resolved profile and effective resolver association. Optional separate Write credential for management. |
| Control D Recent DNS | Provider timestamps, domain/type, actual action/reason, selected device/client and available answer metadata; search/filter and open related policy. |
| Basic management | Create Block/explicit Bypass rules; inspect/edit supported custom rules; enable/disable existing rules, filters and services; supported simple profile options. Unsupported Spoof/Redirect editing must never coerce an action into Block. |
| Dashboard overview | DNS request/outcome totals, trends, top domains and supported reasons, observed tailnet activity and TailDrop totals. Panels link to matching scoped facts. |
| Geography | Provider-supplied DNS-answer country/ASN counts with explicit missing coverage. Reuse offline map assets only when licensing and mobile layout fit; ranked country/ASN drill-down is required even without a map. |
| History controls | One opt-in Collect analytics preference, retention, source freshness/coverage, explicit history deletion and scoped private export. Recording off preserves live controls and retained history. |

For A1–A4, omit application bandwidth, process attribution, socket history,
system-wide traffic totals and GlassWire correlation pages. DNS requests alone
do not measure bytes, connections or which Android app issued a query. These
exclusions are delivery ordering, not permanent rejection: the user requested
app/IP auditing, traffic measurement through the existing Tailscale VPN, DNS
association with equal-weight ambiguity handling and app blocking afterward.
R33 records scope, source review, coverage limits and final acceptance for both
platforms. Do not activate that extension during A1–A4.

## Device-aware DNS data flow

Use either a dedicated Control D endpoint for the Android device or a named
client under a shared endpoint, through the existing compatible resolver path.
Control D documents client-specific DoH URLs and DoT hostnames. A client name
is not a Tailscale stable node ID, and hostname/IP similarity is not a binding.

Setup must show and persist the exact account, endpoint and optional client scope.
Offer suggestions from the configured resolver where unambiguous, then verify
the provider inventory and observed matching records. If a scope change creates
a new provider time series, preserve the old history's original binding.
Do not label account-wide/shared-endpoint results as this device's results.
Do not silently change DNS configuration when adding API credentials.

Data flow:

`configured DNS -> Control D endpoint/client logs -> authorized history reads ->
private Android database -> DNS views/dashboard/export`

Android may be asleep while Control D records queries. The initial policy is
bounded historical catch-up on opening and explicit refresh, without a new
periodic polling job. Fetch only provider-retained intervals; an absence longer
than provider retention cannot be reconstructed and must remain a coverage gap.
Use provider query windows,
explicit completeness/truncation and overlap reconciliation. Duplicate payloads
must not produce duplicate events, but genuinely identical repeated DNS queries
must remain distinct. Never mark incomplete/denied windows as complete coverage.

The current CSV request filters by endpoint; when the API does not support the
required client filter, filter the verified returned client field locally and
budget the endpoint fetch appropriately. Missing client identity remains unknown.

An optional foreground Recent DNS stream improves freshness while that view is
visible. Historical synchronization still works without it, and stream events
must reconcile with later historical facts without double counting. Do not keep
a permanent stream alive solely to make historical DNS dashboards work.

Control D's public CSV guide currently labels automated access organization-only;
TailD has recorded personal-account access evidence. Verify the actual capability
again during Android integration, and expose server denial truthfully. No browser
cookies, scraping, forced permission upgrades or live secret reuse from history.

## Local observations, storage and Android lifecycle

Record Tailscale events using the existing process/VPN notifier when available.
Do not add a second perpetual service or keep the VPN alive merely for recording.
If Android stops the process or SleepManager disconnects it, record an observation
gap at the next start; do not backfill unseen presence or transfers.

Local observation coverage and provider DNS history coverage are separate:
process downtime can lose local Tailscale events while provider DNS history may
remain fetchable. Conversely, no queries routed to Control D means it has no
facts to supply. Browser/application DNS overrides can also bypass that resolver.

Collect analytics off stops durable recording/backfill persistence. An explicit
Recent DNS read may still display provider data transiently without silently
opting the user into local history. Saved history remains readable.

Use app-private SQLite/Room tables for scoped DNS facts, Tailscale observations,
TailDrop metadata, coverage and binding history. Follow the current Android
patterns; add only the persistence/DAO/compiler wiring this scope needs. Serialize
writes, keep queries off the main thread and read consistent query/export
snapshots. DNS acquisition and chart queries must not hold up VPN operations.
Reuse meaningful desktop semantic fixtures rather than forcing the Android
database to imitate Windows history schema/migrations.

Store separate READ/Write token ciphertext protected by an Android Keystore key.
Do not log tokens, include them in exports/URLs, back them up, or silently copy
Windows vault contents. A resolver ID is not an API credential. Test key loss,
credential removal, account changes and process restart without mixing scopes.

Control D management follows desktop's safe workflow: fresh binding/policy read,
preview including every affected endpoint sharing a profile, explicit confirmation,
single consumed write intent, then verified readback. Switching account/profile
invalidates previews. A lost response after mutation is outcome unknown until
reconciled; never retry the write automatically. Starting the app, collecting or
refreshing data never changes policy. API management need not require VPN on
when ordinary Internet connectivity is available.

## Package, compatibility and delivery

Recommended migration contract: TailD branding/repository/release artifacts with
the existing `io.github.darkaxt.taildns` application ID and signing certificate,
so an authorized upgrade can preserve login, preferences, VPN authorization,
always-on association, TailDrop URI grants and SleepManager targeting. Verify all
of these on a real upgrade; source identity alone does not establish continuity.
Retain connect/disconnect action names and SleepManager's exact package contract.
Do not rename Kotlin namespaces simply for branding.

The signer must be verifiably available to a protected TailD Android signing job;
do not regenerate or silently substitute it. This is a delivery prerequisite,
not permission in this planning task to provision credentials or change settings.
Preserve independent Windows and Android release identities. Android versionCode
must exceed installed/public compatible builds, with the true upstream version
base and explicit TailD sequence. Keep existing TailDNS release selection from
offering an older or incompatible build after migration. Verify the actual
installed update-discovery mechanism before selecting its transition behavior.

Keep inherited TailDNS workflows disabled in TailD. Add a narrowly owned Android
check/release path when implementation is authorized, preserving inheritance
contracts and Windows behavior. Independent APK verification must cover package,
certificate, version/code, ABI/core pin, checksums, notices and release source.
This proposal authorizes no build, key changes, release, schedule expansion or
device installation.

## Proposed delivery sequence

These are future integrated slices, not component-only validation milestones.
Only one could become ACTIVE at a time after implementation authorization and
reconciliation with the existing desktop Stage 10 workload.

| Stage | Status | Complete workflow and acceptance |
| --- | --- | --- |
| A1: Tailscale representation and history | NOT STARTED | Live peer -> detail/control -> opt-in observed event -> durable history -> process restart with truthful gap; observed TailDrop outcome/save -> history. Verify phone/tablet rendering and preservation of VPN/DNS/SleepManager behavior. |
| A2: Control D setup, history and basic management | NOT STARTED | Explicit device/client resolver binding -> READ inventory/history -> matching Recent DNS facts -> selected domain policy preview -> separately authorized write -> verified provider readback. Cover shared profiles, wrong account, stale preview, unknown outcome, unknown schemas and server denial. |
| A3: Compatible dashboard and battery lifecycle | NOT STARTED | Committed scoped history -> count/trend/domain/geography or local-activity panel -> exact drill-down -> matching private export. Verify backfill/overlap/retention, recording off, visible-only optional stream, process death and delayed work without blocking connection/navigation. |
| A4: TailD Android distribution and migration readiness | NOT STARTED | Clean current-source build -> protected existing signer -> independent APK verification -> authorized in-place test -> retained identity/data/VPN/TailDrop/SleepManager -> compatible recovery/update transition. Publication and device deployment require their applicable explicit authority. |

Required tracked deferrals: F1 (Windows app/IP audit and weighted domains), F2
(Android equivalent) and F3 (explicit app blocking on both), owned by
[R33](TRAFFIC-AUDIT-AND-BLOCKING-SPECIFICATION.md#named-stages-and-tracked-deferrals).
They begin only after the preceding desktop/Android acceptance prerequisites;
they do not excuse any incomplete A1–A4 criterion or authorize implementation now.

Develop each slice as a complete feature before its acceptance validation. Focused
contract tests should cover normalization, exact counts, state changes and safe
writes. Real provider reads and any real test mutation need the applicable scoped
authority; never substitute fixture results for them. Use an isolated test policy
or exact recoverable confirmed action for writes, not a silent production probe.

Use the installed Gradle build gate and required memory profile for Windows
Gradle verification. Validate the actual served native Compose UI at compact
phone and wide/tablet sizes, large text, keyboard/TalkBack and state changes.
Preserve existing Android TV connectivity; do not accidentally ship a broken
inherited TV variant or broaden this proposal into a TV analytics redesign.

## Feasibility and effort assessment

Tailscale representation is the smallest increment because the notifier, status
models, controls and native UI are present. Durable event history and TailDrop
receipt semantics add real work beyond changing labels.

Control D management/history is the largest new product area: Android credentials,
API normalization, exact endpoint/client binding, provider capabilities and write
reconciliation need implementation and real integration proof. Dashboard queries
and charts follow those verified facts; no packet interceptor is required.

Android lifecycle and signing/migration are the largest acceptance risks. Treat
this as several integrated development slices, not a quick WebView/reskin task.
The plan is technically credible without a new server, firewall, root permission
or desktop dependency. No calendar-duration promise is inferred from inspection.

## Evidence and external references

- Local `android/build.gradle.kts`, `MainActivity.kt`, `App.kt`, `IPNService.kt`,
  `ui/notifier/Notifier.kt`, `ui/localapi/Client.kt`, `ui/model/IpnState.kt`,
  `ui/model/Tailcfg.kt`, TailDrop view models and `util/ShareFileHelper.kt`.
- Desktop `SPECIFICATION.md`, `PRODUCT-SPECIFICATION.md`, `IMPLEMENTATION-PLAN.md`,
  `CONTROL-D-READS.md`, `POLICY-READS.md` and `TAILSCALE-ACTIVITY.md`.
- `SleepManager/docs/taildns-support/SPECIFICATION.md` and its actual package policy.
- [Control D device/client resolver identity](https://docs.controld.com/docs/device-clients).
- [Control D CSV history API and limits](https://docs.controld.com/docs/how-to-export-logs-to-csv).
- [Control D rule actions](https://docs.controld.com/reference/post_profiles-profile-id-rules).
- [Android VPN lifecycle and one active VPN per profile](https://developer.android.com/develop/connectivity/vpn).
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore).
- [Android foreground service requirements](https://developer.android.com/develop/background-work/services/fgs/service-types).

All inspection was read-only apart from this planning document. No Android build,
runtime implementation, credential provisioning, authenticated provider call, device mutation,
workflow activation, release or automation modification was performed.
