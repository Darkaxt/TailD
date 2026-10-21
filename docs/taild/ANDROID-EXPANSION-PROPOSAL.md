# TailD Android specification

Version 1.5, 2026-10-21. Authoritative Android extension to
[PRODUCT-SPECIFICATION.md](PRODUCT-SPECIFICATION.md), requirement R37.
The historical filename is retained to preserve existing links.

The October 20 instruction authorizes implementation in TailD, specification
alignment with the shipped Windows R36 behavior, verification and the normal
Android release. It does not authorize unrelated device deployment, changing
production provider policy or closing desktop B12. Current stage status lives in
[IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md); historical planning language
below is superseded by this authority and the parity contract below.

## October 21 Firewall traffic and diagnosis

The user authorizes the following integrated update and normal final Android
release. Existing blocking, history, privacy, theme and package contracts remain.

- U8: Firewall is the primary app traffic entry. Show received and sent totals
  per app/shared UID for the last 24 hours. The user's subsequent one-day
  simplification replaces selectable periods in this view; Dashboard retains its
  own periods. Show a compact clock-hour traffic graph per row and a larger graph
  with accessible hourly values on the diagnosis page. Partial edge hours remain
  within the exact rolling day, local labels include timezone, and graph bytes
  reconcile to the row total without duplicating resolver context bytes.
  Sort by combined measured bytes descending, then app name alphabetically with
  deterministic ties. Traffic inspection works without Shizuku; optional blocking
  still requires its existing authorized backend. Preserve unassigned/system and
  historical installation identities separately; never relabel reused UIDs.
  Refresh cancellation cannot publish an error over a newer successful snapshot;
  search focus and text survive status rows appearing/disappearing and refresh.
- U9: An accessible diagnosis icon opens a separate full content page with Back,
  app/package/UID/profile/version/install/update/signer metadata, totals, observed
  IP/protocol/time/packet and DNS resolution/block evidence, equal-weight domain
  candidates and unknown/coverage disclosures. Keep the list compact. Retain exact
  snapshot scope and export; system resolver context must not inflate app bytes.
  Existing Dashboard Applications remains available. No provider policy writes.
- U10: Handle the verified Control D whole-second CSV boundary behavior using an
  explicit transport envelope and exact local half-open interval filtering.
  Continue rejecting mismatched endpoints, malformed timestamps and records outside
  that envelope. Preserve duplicate DNS events and truncation/resource accounting.
  Verify fractional-boundary live READ behavior and focused regressions.

Use existing Material colors/type, 48 dp diagnosis targets, wrapping narrow/large
text rows and centered 840 dp wide content. Results must retain at least half the
phone viewport. Verify native navigation, sorting, shared/reused identity, metadata,
no-backend viewing, live automatic theme, retained upgrade and independent release.

## October 21 review-driven UI refinement

The user's follow-up authorizes acting on the seven recorded layout findings,
using Huashu critique guidance within the existing native Material design and
publishing one verified Android update. No direction-selection/manual integration
checkpoint is added. This is a bounded refinement, not a replacement UI.

- U1: Geography without a binding offers a prominent Select endpoint action
  adjacent to the empty-state explanation. Retry is for an actual query failure.
- U2: Dashboard period controls and secondary actions have an intentional
  large-text arrangement. At 360 dp/font scale 1.5, destination names remain
  readable and primary content remains reachable without clipped controls.
- U3: Applications places Coverage, Export and optional OS totals in one compact,
  wrapping action row. Keep the observed-VPN/device scope visible and preserve
  immutable export/detail selection and coverage disclosure.
- U4: Control D is results-first. A compact endpoint/action bar replaces the
  repeated destination title and retention heading. Tabs and search are the only
  other permanent rows above results. Scope details contains client selection,
  profile/affected endpoints, separate Write setup, policy reload and coverage;
  actionable errors and unresolved writes remain visible. Shared impact remains
  explicit at mutation review. DNS rows show domain, decision/inverse action,
  relative time, First seen and seven-day Total; expand a row for exact UTC and
  reason metadata. At 360 dp/font 1.0 the first result starts within the top 35%
  of the app viewport and at least 60% remains for results. At font 1.5 controls
  remain accessible and results retain at least half the viewport. Verify actual
  populated native bounds and captures, not only control presence.
- U5: Firewall emphasizes app name, policy state and shared-UID affected-app
  count. Package identifiers are available through accessible row details.
  Explicit shared-UID change review, ownership and inverse actions stay intact.
- U6: Dashboard/traffic content has a centered working column capped at 840 dp
  on wide screens; phone search fills the available width. No horizontal overflow.
- U7: Export feedback uses an accessible dismissible overlay/status surface and
  does not occupy another tab's scrolling content or displace its map/results.

Use the existing theme, official marks, rounded search and 4/8/16 dp spacing;
retain 48 dp interactive targets. Verify the real native UI at phone/tablet,
portrait/landscape, automatic light/dark and font scale 1.5, including scope
selection, shared-UID disclosure, detail/coverage expansion and actual SAF export.
Record before/after captures and reconcile all seven findings. Final delivery
requires the established exact-source signed candidate, isolated upgrade/recovery
and independent public APK/package/signer/source/assets verification. Preserve
physical-device/provider boundaries and unresolved Windows B12/F1/F3.

## Confirmed direction

The October 21 versioning correction replaces Android's `+N` release suffix with
`.N`: APK versionName is `<upstream Android base>.<TailD Android sequence>` and
the tag is `v<upstream Android base>.<TailD Android sequence>`. The upstream base
remains the exact three-component inherited Android version. Continue the
monotonic positive sequence across historical `+N` and new `.N` tags/releases;
do not rename or replace old releases. Android versionCode must increase beyond
both prior TailD APKs and the current TailDNS upgrade origin. Keep the package,
certificate, signed source/core provenance and Windows version/channel unchanged.
Acceptance requires the actual signed APK and public tag to agree, successful
in-place upgrade/recovery in the isolated delivery harness, and ObtainX to offer
the release while retaining Android-only title/APK filters. Once installed,
equivalent dotted package/tag names must compare equal, and a later dotted
sequence must compare newer. No ObtainX fork or pseudo installed-version tracking.

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

## October 21 Geography correction

The user identified the missing map in the shipped Geography destination. The
subsequent screenshot feedback requires map-first presentation: only a compact
endpoint/client row precedes it. Put source/retention text, exact UTC window,
recording status, country/ASN coverage and explanatory metadata in a collapsed
Coverage & details section below the map. Keep actionable errors visible. This
instruction makes an offline native world map required, replacing the earlier
optional-map wording. Reuse the pinned Windows country dataset and retain its
source/license notices. No tile service, location permission, WebView or VPN/DNS
change is needed. The map uses the same immutable endpoint/client/window/revision
snapshot as country rankings, details and exports. Observed countries are shaded;
unobserved countries stay neutral. Unknown/unmapped observations remain visible
and selectable in the country list, and overlapping answer-country groups remain
explicit. A map country tap opens the matching existing country-filtered details.
The list provides equivalent accessible actions with at least 48 dp targets.

Use a 2:1 projection fitted uniformly inside the available content width, capped
at 40 percent of screen height for landscape/short displays. Include 360 dp phones
and 840 dp tablet layouts, with no distorted/clipped shape or horizontal scroll.
Respect automatic system light/dark changes, font scale 1.5, empty data and scope
changes. Package the map offline and independently verify its asset and notices
in the signed final APK. Acceptance includes native map rendering, country tap ->
exact matching observations/export scope, unknown/empty states and live theme
transition retaining the current tab/data. No physical-device acceptance is implied.

The traffic assessment is followed by explicit October 21 authority to proceed
directly into implementation when ready. After Geography closes, implement the
ShizuWall-style Android app/UID control stage (R33 F0), then Android Tailscale
measurement (F2), then one integrated verified Android release. Preserve the
separate unresolved Windows scope/B12 and real-device privilege boundaries.
R33 owns the detailed identity, counter, DNS, estimation and recovery contracts.

## Source-verified starting point

Implementation baseline: TailD main
61f96f5836edfb99814260a5e19e59adf0c3c19b, containing verified TailDNS
84e54804c0fc4b39f5d9a1ce7acaf3593fae316e and shared core
28b0deb7805710f50689f4aa133ed911f74e504d. Windows reference is the
verified R36 interface delivered in windows-v1.105.0+27.

## Windows parity and native design contract

Reuse the native Compose application and existing VPN/control operations. Phone
navigation has Tailscale, Control D, Firewall and Dashboard destinations; wide layouts use
a rail. The Tailscale destination opens Connection, with TailDrop, Admin console
and Preferences alongside it. Admin console respects current management policy
and opens the authenticated provider website; it must not collect browser cookies.
Do not expose unfinished destinations as working features in a released APK.

Connection is a searchable device list with this device first. Put a presence
square/dot before the name and an accessible OS icon immediately after it. Unknown
presence stays Unknown. The local device uses its known Android platform even
when its self-node OS metadata is omitted; remote unknown OS stays unknown. Do
not repeat owner/account headings in the list: account identity is already
beside the connection switch. Preserve the pinned-devices heading. Use the same
official Tailscale and Control D marks as Windows for rail and bottom navigation,
with theme-aware tint, unchanged accessible destination labels and bundled notices.
Show relative Last online and make the exact provider UTC
timestamp available by tap/long press and accessibility, equivalent to Windows
hover. Phone rows may wrap; do not require a five-column desktop table on a phone.
Keep addresses, owner, routes, tags, health and capability facts reachable in device
details. Put the existing VPN switch beside its truthful state; no duplicate This
device or exit-node card. Put exit-node controls in ordinary Preferences rows,
hide dependent rows when disabled, preserve MDM constraints and visible failures.
Collect analytics is one preference row, disabled by default, independent of VPN
state. Production debug controls stay out of normal navigation.

Recent DNS uses Time, Question, Decision/reason, First seen and Total semantics.
Its domain/decision search uses the Tailscale search field's rounded shape,
theme colors, search glyph, placeholder and focused clear/close control. Preserve
the current domain/decision filtering and independent history-refresh action.
The recent list is the latest 100 observations in 15 minutes; First seen and Total
query every retained observation in the last seven days for the exact selected
account/endpoint/client/question/type, independently of list/search limits. Label
the analytical window and incomplete provider/local coverage. No internal IDs in
normal rows. Place endpoint display name, enforced profile name and labelled icon
reload beside collection status; shared-profile impact remains discoverable.
Search includes visible decision labels and canonical outcomes, case-insensitively;
distinguish no matches, no observations and read failure.

Blocked observations show a tick Allow action (explicit bypass); allowed observations
show a forbid Block action. Other supported decisions may show both. Put these
accessible icons and a tool Edit icon beside Decision, with no actions column.
Quick actions consume an explicit user tap and perform fresh binding/event-profile/
shared-profile checks and verified readback without another transaction popup.
Only Edit opens the full floating rule editor; it must not shrink the list and
dismissal preserves query, scroll and focus. The October 20 UI refinement also
applies the single-inverse-action rule inside Edit: show the draft's current rule
action and only one icon to change it (check for Allow/explicit Bypass, cross for
Block), with a tooltip, accessible name and 48 dp touch target. Do not display both
choices for a known action. A supported observation supplies the initial action
when no custom rule exists; unsupported actions remain read-only. Close and Review
change retain their text labels and existing explicit review behavior. Other
management writes keep their explicit review and confirmation. Unsupported actions cannot be coerced to Block.

Dashboard defaults to seven days. DNS counts/outcomes/trends/domains/reasons and
available answer country/ASN data share exact scopes with drill-down/export.
Local Tailscale/TailDrop observations are distinct from provider DNS coverage.
Do not show Windows-only GlassWire/application-byte panels. Source acquisition,
history freshness and diagnostics belong to About and the dashboard's source
health view. Background queries survive navigation under the app's existing scope;
complete panels remain usable and failed panels become Unavailable with explicit
refresh, never endless Loading. VPN control must not await history or charts.

Verify actual native rendering at 360x800 and 412x915 dp phones and 840x900 dp
tablet, portrait/landscape, font scale 1.0/1.5, dark/light, keyboard and accessible
48 dp actions. Lists and floating editors must remain scroll reachable. Evidence
must identify build/source, viewport, visible state and synthetic versus live data.
Preserve inherited Android TV connectivity without requiring a TV dashboard redesign.
Android TailD continues to follow the system's automatic light/dark theme. A live
system theme change must repaint the current native destination while retaining
its selected tab, local data and active VPN; do not hard-code a light or dark theme.

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
restricts execution to Darkaxt/TailDNS. At the baseline, TailD delivery was Windows-only. R37 adds the deliberately
scoped taild-android-release.yml candidate/signing/publication workflow and the
verified normal Android release v1.103.312+34; inherited workflows remain disabled.

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

Use four top-level destinations: **Tailscale**, **Control D**, **Firewall**,
**Dashboard**. The October 21 user correction gives optional app/UID controls
their own Firewall tab, with the official ShizuWall mark and source/license
attribution; Dashboard Applications contains traffic metrics and domain details.
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
| Geography | Provider-supplied DNS-answer country/ASN counts with explicit missing coverage. Offline native country map and ranked country/ASN drill-down are required; preserve licensing, mobile layout and unknowns. |
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

The initial A1–A4 implementation uses bounded CSV catch-up on opening and explicit
refresh; it does not open the optional foreground stream. Returned-window
checkpoints avoid repeatedly fetching old intervals, while a 15-minute overlap
reconciles recent observations. Daily request windows split on an explicit local
response budget/cap, preserving incomplete facts and truthful unknown coverage.
Recording off permits only a deliberate transient recent read. No polling timer,
periodic worker or additional foreground service is introduced.

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

Control D management follows the parity contract above: direct incident Allow/
Block actions use a fresh, single consumed intent and verified readback; other
management writes include a preview of all affected endpoints and explicit
confirmation. Switching account/profile invalidates previews. A lost response
after mutation is outcome unknown until reconciled; never retry the write
automatically. Starting the app, collecting or refreshing never changes policy.
API management need not require VPN on when Internet connectivity is available.

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
not permission to regenerate keys or substitute a different identity.
Preserve independent Windows and Android release identities. Android versionCode
must exceed installed/public compatible builds, with the true upstream version
base and explicit TailD sequence. Keep existing TailDNS release selection from
offering an older or incompatible build after migration. Verify the actual
installed update-discovery mechanism before selecting its transition behavior.

Keep inherited TailDNS workflows disabled in TailD. Add a narrowly owned Android
check/release path when implementation is authorized, preserving inheritance
contracts and Windows behavior. Independent APK verification must cover package,
certificate, version/code, ABI/core pin, checksums, notices and release source.
The authorized implementation includes builds and a verified normal release;
no schedule expansion or unrelated device installation is implied.

## Required delivery sequence

These are integrated slices, not component-only validation milestones. Only one
may be ACTIVE. Status is maintained in IMPLEMENTATION-PLAN.md.

| Stage | Status | Complete workflow and acceptance |
| --- | --- | --- |
| A1: Tailscale representation and history | COMPLETE | Live peer -> detail/control -> opt-in observed event -> durable history -> process restart with truthful gap; observed TailDrop outcome/save -> history. Verify phone/tablet rendering, live automatic system theme and preservation of VPN/DNS/SleepManager behavior. |
| A2: Control D setup, history and basic management | COMPLETE | Explicit device/client resolver binding -> READ inventory/history -> matching Recent DNS facts -> direct incident action or reviewed Edit/management action -> verified provider readback. Cover shared profiles, wrong account, stale intent, unknown outcome, unknown schemas and server denial. |
| A3: Compatible dashboard and battery lifecycle | COMPLETE | Committed scoped history -> count/trend/domain/geography or local-activity panel -> exact drill-down -> matching private export. Verify backfill/overlap/retention, recording off, visible-only optional stream, process death and delayed work without blocking connection/navigation. |
| A4: TailD Android distribution and migration readiness | COMPLETE | Clean current-source build -> protected existing signer -> independent APK verification -> isolated in-place upgrade -> retained identity/data/VPN/TailDrop/SleepManager contracts -> compatible recovery/update transition -> normal published Android release and independent public asset verification. Real-device continuity requires its actual evidence and is never inferred from CI or an emulator. |

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

October 20 live-verification scope: the user selected an existing device/profile and
directed read-only verification with the saved Windows READ credential. Verify
Android's actual inventory, binding, policy and history reads against that target.
Keep management mutation/reconciliation acceptance in the isolated HTTPS fixture;
do not create provider resources or change that production profile to prove the write path.
Report fixture management evidence separately from real provider read evidence.

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

## October 21 smart exit-node trigger evaluation

The user requests evaluation for a subsequent Windows and Android update, not
activation during the current Geography/F0/F2 implementation. The intended
behavior is an opt-in extension of exit-node selection: use the prioritized
eligible exit node when away from its Internet egress, and suspend only the exit
route when already sharing that egress. Tailscale remains connected. This is
distinct from upstream `auto:any`, which chooses a recommended exit node.

Reuse native VPN-bypassing sockets before considering an excluded helper app.
The current Android `libtailscale/backend.go` already connects
`VpnService.protect` and `App.bindSocketToNetwork` to core `netns`. The latter
currently binds to `NetworkChangeCallback.cachedDefaultNetwork`; it is not yet a
probe API for every prioritized underlying network. A dedicated probe can
protect its own socket, bind to the selected eligible non-VPN `Network`, and use
that network's DNS resolution. It must verify protection/binding success and must
not accept an ordinary VPN-routed request as direct-egress evidence. Do not
exclude TailD's whole package, enable global bypass, rebind the process, or turn
off the VPN to measure an address. The existing per-app split-tunnel exclusion
could support a separately excluded helper, but no helper is needed merely to
obtain this native socket capability. Preserve administrator restrictions.

The pinned Windows core already uses `net/netns/netns_windows.go` to bind sockets
to a default interface outside Tailscale WinTun. Evaluate a narrow probe through
the existing owning daemon/native boundary, with explicit physical-interface and
IPv4/IPv6 binding when testing additional eligible interfaces. Do not assume the
existing default-interface dialer exposes arbitrary interface priority or add a
privileged service solely for this feature.

The proposed decision records pair a stable exit-node identity with fresh direct
egress observations and the actual active underlying network generation. Probe
only available networks allowed by system policy and user metering preferences;
an inactive mobile connection need not be awakened to test it. Resolve/probe via
the same bound network; reject stale results after network, profile or candidate
changes. Compare like address families. IPv6 host addresses may differ on one
LAN, so equality of individual IPv6 addresses is not a same-network test.
Matching public IPv4 is evidence of shared egress, not proof of the same LAN
(CGNAT/shared NAT); report that distinction and assess local reachability as
corroboration before offering a same-LAN claim.

Each candidate also needs trustworthy direct-egress evidence. Tailscale/STUN
endpoint metadata can be a hint, but may include stale, local or multiple
addresses. An arbitrary exit-capable peer does not automatically expose a fresh
public-IP observation API. Evaluate existing authenticated peer capabilities
first; if a TailD peer/helper is necessary, document that compatibility boundary
rather than silently installing software or assuming every exit node supports it.
The public-IP discovery service and its privacy/availability contract must be
selected explicitly in the eventual implementation design; no new external
probe service has been enabled by this evaluation.

The eventual implementation must preserve manual overrides, administrator-forced
exit nodes, profile/DNS ownership and configured candidate order. Reevaluate on
actual network/candidate events, cancel or disregard obsolete generations, and
avoid route-write loops caused by the trigger's own changes. Unknown/offline or
failed-probe results must remain visible and cannot be treated as an IP mismatch
or authority to silently disable a previously selected exit route. Explicitly
specify unavailable-candidate behavior before implementation.

Required evaluation/acceptance cases are: an active exit node while a protected
probe still reports direct egress; home/away transitions; two simultaneous
underlying networks with different priorities; Wi-Fi/mobile handover; IPv4-only,
IPv6-only and dual stack; shared NAT/CGNAT; stale/offline peers; captive portal and
probe failure; manual override, managed policy and restart recovery. Verify both
Windows and Android with actual route/readback evidence before claiming delivery.
This evaluation adds no ACTIVE implementation stage and does not authorize live
routing changes on the user's devices.

References: [Android socket protection](https://developer.android.com/reference/android/net/VpnService#protect(int)),
[network-specific sockets](https://developer.android.com/reference/android/net/Network#bindSocket(java.net.Socket)),
[Windows interface socket options](https://learn.microsoft.com/en-us/windows/win32/winsock/ipproto-ip-socket-options),
and [upstream automatic exit nodes](https://tailscale.com/docs/features/exit-nodes/auto-exit-nodes).

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

The original October 16 investigation was read-only apart from this document.
Subsequent implementation and verification evidence belongs in the execution
ledger; the planning inspection is not acceptance evidence.
