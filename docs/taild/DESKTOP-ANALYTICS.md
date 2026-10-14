# Desktop analytics — Stage 8 evidence

Stage 8 is COMPLETE for the source-built desktop, not an installed TailD release.
Stage 9 owns toolchain-free packaging and isolated installer acceptance; Stage 10
owns separately authorized publication, replacement and updater activation.

## Connected workflow and acceptance

The packaged Angular application runs in the owning user's WebView2 window at
`https://taild.local/index.html`. Its fixed native bridge uses the authenticated
owner pipe and serialized private SQLite worker: no HTTP dashboard listener,
renderer SQL, arbitrary path access or provider credential.

| Stage 8 criterion | Current verified result |
|---|---|
| Navigation and scope | Overview, Applications, Activity, Control D, Sources & health and Settings share host/observed-node/account/endpoint and UTC range. Actual native transitions and loading/partial/empty/unavailable states pass. |
| Functional widgets | Real sent/received D3 series, stacked ranked consumers with keyboard list equivalents, exact counters, correlation partition, DNS outcomes/questions, destinations and country/ASN tables use typed queries. No unsupported firewall, SPN, TLS, PID or socket claims. |
| Revision/exactness | One revision per visible batch; distinct cursor pages; a real concurrent WAL commit rejects stale paging. Refresh anchors the selected fact and restores focus. `9007199254771401` synthetic bytes remain exact in UI/exports. Gaps are not zero-filled; partial values are lower bounds and unsupported outcomes remain unknown. |
| Explorer/evidence | Traffic/DNS/correlations, literal search, compound predicates, grouping, sorting, removable chips, saved queries and structured details are integrated. Scoped/grouped saved queries reopen after actual restart. Candidate evidence is paginated and instantiated only for the open fact, never duplicated into byte totals. Original evidence retains every candidate. |
| Private export | Actual Windows Save dialog selects a new JSON/CSV destination. Export is the complete filtered scope, not just a page, bound to the displayed revision and limited to 10,000 facts. Exact totals, unknowns, units, versions and UTC scope survive. Hostile executable names remain literal in the UI and formula-safe in CSV. Native ACL inspection confirms owner/SYSTEM/Administrators only; existing paths are not overwritten. |
| Actual-source boundary | A read-only snapshot of retained GlassWire data feeds application -> activity -> evidence -> native export: **1,773 facts and 20,378,798 bytes**, exactly matching the query. Retained actual Control D policy snapshots render in their original time scope. These are previously captured real records, not newly captured traffic or synthetic DNS presented as live proof. |
| Collection regression | Actual autosave, pause/resume, enabled-window close/reopen, explicit stop and source-build launcher start/stop pass on this host. Installed VPN/DNS/firewall/source services and credentials remain unchanged. |
| Design/accessibility/security | Current fixed-origin assets/CSP, hostile text, pending-query exclusion, keyboard actions, focus rings, labels, headings, dark contrast and chart/list equivalents reviewed. Actual 1440×900, 1280×800 and 1024×768 CSS viewports fit without horizontal page overflow. Accepted native **150% app-local zoom** measures **949×574 CSS px, DPR 1.5**; keyboard/overflow checks pass. Windows remains 100%; physical Windows 150% is not claimed. |

## Source-observed versus adapted layout

The full pinned Portmaster inventory was retrieved before analytics presentation.
These are source-observed comparisons, not fabricated running-upstream screenshots.
Exact paths/blob identities and GPL attribution are in [the design map](PORTMASTER-DESIGN.md),
[inventory](portmaster-source-inventory.json) and [notices](../../desktop/NOTICE.md).

| Portmaster family | TailD reuse/adaptation and reason |
|---|---|
| 64px rail/dashboard/panels | Preserve rail geometry, dense 16px rhythm, panel headers and summary/chart/ranking composition. Six analytics routes replace SPN/news/subscription actions. Warm charcoal/blue tokens follow the user's Tailscale reference. |
| D3 line chart | Reuse series/area/axis/point rendering. Owned resize lifecycle replaces upstream app coupling. Remove `fillEmptyTicks`; exact strings stay in tooltips/table, floats only in plotted coordinates. |
| Circular stacked consumers | Reuse radial stacks, ticks and received/sent legend; canonical bytes and accessible ranked scope links replace upstream connection semantics. |
| Application insights | Retain executable list -> identity -> charts/rankings -> scoped activity. Remove firewall editors/unproven process state; keep provenance/uncertainty. |
| Netquery filters/rows | Adapt dense toolbar, pills and expandable rows. Native inputs preserve keyboard semantics; allowlisted predicates replace raw TextQL/SQL. |
| Details/accordion/pagination | Reuse structured expansion and lazy evidence. Revision cursors replace arbitrary page jumps; paged candidate subrows replace enormous repeated attributes. JSON remains secondary. |
| Theme/settings/toggles | Reuse integrated themed panel/toggle subset. Native semantic controls replace unnecessary overlay/CDK dependencies; do not install the Angular12-peer UI package wholesale into Angular20. |
| Geographic map | Not imported at Stage 8. The October 14 R15a amendment adds the reviewed offline country map; current evidence is below. No measured routes or precise geography are implied. |

## Reproducibility and evidence

The current-task full Python contracts passed on the unchanged backend. Fresh
Angular production/native builds and both actual-native validators pass on the
same final assets. Build from `desktop` with pinned `npm ci --ignore-scripts`,
`npm run build`, and `dotnet build native/TailD.Desktop.csproj -p:RestoreLockedMode=true`.
Native workflow commands live at `scripts/taild/validate_analytics_windows.py` and
`validate_desktop_windows.py`; each requires an exact new private output root.
The native validation host is Debug solely for inspector/readiness/zoom hooks,
with production Angular assets. Hook-free Release packaging belongs to Stage 9.

Final served SHA-256:

- `main-PIJ752X5.js`: `3a4e528d0971818cd629568cc189d8b18899c8e19a083a367cacaee61e1d835e`
- `styles-FP6D5UJK.css`: `bb4ec3404080f0fa353b7f9ba71ca573b56809fc29dbd75bbbea7e8a42344157`
- `TailD.Desktop.dll`: `52399373042022e7266c3a92dcf6992493204e7851a4a0ca4359cd9240d48ab8`

Private evidence at `D:/Tools/taild-stage8-validation-20261013` retains both native
reports, measured hierarchy/asset identities, screenshots and JSON/CSV exports.
Copies were hash-checked; private records/screenshots are not published to GitHub.
The native zoom OS-window capture is the visual authority: CDP full-page images
clip at native WebView2 zoom and are not treated as complete visual evidence.

The explicit user waiver for forced sleep/wake, network loss and GlassWire stop/
update remains: physical scenarios are **untested**, not simulated passes. No
installer, public release, updater activation or installed replacement is claimed.
Dependency notices and toolchain-free runtimes must be included before distribution.

## R15a integrated refinement — 2026-10-14

Source feature is implemented and verified within ACTIVE Stage 10. B13 is resolved
for this refinement's source/native acceptance, not the remaining B12 delivery,
rollback or updater acceptance. Installed/public 1.105.0+3 is unchanged.

- Actual native `https://taild.local/index.html` serves the production Angular
  build in the isolated Debug inspector host. Held real query shows the centered
  three-dot translucent loading layer; scope/navigation/results cannot mutate
  while pending. Stale-revision error clears the layer and retains old data;
  explicit refresh recovers with selected-row/focus preservation. No synthetic
  timing is presented as a production latency measurement.
- Regression reproduced three correlation preparations in one dashboard batch;
  the integrated query engine now prepares once per matching UTC/scope/age domain
  in the same read transaction. Separate query predicates/aggregates, revision
  consistency, exact counters and coverage remain intact; nothing is reused across
  batches. Focused analytics and existing held-source/read-only/close checks pass.
- Portmaster-style country/map grouping and paired consumer/bandwidth panels are
  verified at 1440×900, 1280×800 and 1024×768 CSS px without page overflow. Actual
  150% native app-local zoom measures 949×574 CSS px / DPR 1.5 with keyboard access;
  OS capture is retained. Windows display scaling is unchanged.
- Reviewed pinned topology renders more than 150 country paths offline. Synthetic
  unique answer metadata highlights Germany; Enter opens the exact country-filtered
  explorer. Unknown/ambiguous geography remains neutral or explicitly unknown.
  No route, client location, unsupported firewall verdict or external lookup.
- Native duplicate-name check: `C:\Synthetic\normal.exe` and
  `D:\Other\normal.exe` both display `normal.exe` but open distinct 42-/41-fact
  scopes, with every rendered fact retaining the selected full path. Path titles,
  canonical identities and private exports are unchanged.
- Retained real GlassWire records reconstructed losslessly from the existing
  private export feed the actual window: **203 facts / 20,684,627 bytes** reconcile
  through activity drill-down and native private JSON/CSV export, including ACLs.
  This is retained real data, not fresh provider/traffic acquisition. Synthetic
  >2^53 exactness, hostile text, pagination and saved-query restart also pass.

Durable private evidence:
`D:/Tools/taild-stage10-validation-20261013/ui-refinement-20261014`.
Primary reports: `analytics-validation.json`,
`duplicate-executable-validation.json`; representative screenshots include
`refresh-loading.png`, `overview-1440x900.png` and
`overview-native-150-percent-window.png`. No private source data is published.

Verified served assets: `main-5FHARNDJ.js` SHA-256
`8e282fc32c5ce4b95bfb7f583ddcc7d6d61ae710054311878b43cfc89a7152e3`;
`styles-GDRHY5LL.css` SHA-256
`92503bcefd6b7e944318322cd3541cb100e974e063e5650f32f46cb8ded3b90f`;
lazy map `chunk-CA5NCUVR.js` SHA-256
`48d96f44b597af53d106d494da2f01cea43781415dcc1f8cc6bcc76330691b47`.
Native shell source is unchanged. Design-debt assessment found no required new
abstraction/refactor: transaction-local preparation and the existing component/
bridge boundaries directly serve R15a. No follow-up infrastructure is introduced.

## R15b report-driven dashboard refinement 2026-10-14

The [full Portmaster mapping](PORTMASTER-LAYOUT-MAP.md) now drives a more faithful
composition while retaining Tailscale colors and the reviewed Portmaster panel,
line chart, radial consumer chart and offline map. Six scope-bound summaries
precede a primary DNS decision chart; collection context occupies the adjacent
sidebar at wide sizes. Smaller layouts move it below the trend. Country tiles
coordinate map focus/hover; consumer/bandwidth panels are paired, followed by DNS
question/destination rankings and the correlation partition. Exact country/ASN
tables remain available. No unsupported SPN, firewall score, news or subscription
widget was introduced.

The DNS series uses canonical provider event counts and its own source coverage,
not traffic totals or traffic coverage. Metric version is `taild-metrics-v2`;
Tailscale/product/release versions are unchanged. Partial-bin scope bounds are
clipped to the selected half-open UTC interval. Missing zero-count bins remain
gaps; complete zero-count bins represent observed zero. Existing byte/rate
semantics and exact counters are unchanged. Source status can display Control D
first without changing acquisition scheduling or opt-ins.

| Criterion | Current evidence |
|---|---|
| R08 layout relationships | Actual served native assets show summary/trend beside source context at 1440 px; coordinated country/map and paired consumer/bandwidth composition. Template/style reuse and deliberate adaptations are recorded in `desktop/NOTICE.md`. |
| Six summaries and source navigation | All six buttons and provider/health/settings links execute normal UI events and reach the intended scoped view. Question groups open grouped DNS facts, not traffic grouping. |
| DNS trend correctness | Real SQLite fixtures preserve duplicate events, endpoint filtering, zero versus missing coverage and a shared batch revision. Native summary/series reconcile 125 synthetic events. A clipped first bin drills into exactly one event and exports that selected scope through the actual Windows Save dialog. |
| Geographic interaction | Native keyboard focus highlights Germany without a revision change or query; activation opens its exact country-filtered explorer. Unknown geography remains neutral and listed. |
| Retained source workflow | Previously captured GlassWire facts reconstructed losslessly from the private export: 203 facts / 20,684,627 bytes reconcile through actual native application/activity/evidence and private export. This is retained traffic, not a fresh acquisition. |
| Existing safety and interaction | Held refresh/error recovery, duplicate executable basenames, selected-row/focus preservation, pagination, hostile text, exact large counters, saved-scope restart, JSON/CSV export and private ACLs pass. No installed client, source service, credential or provider policy changed. |
| Viewports and accessibility | Actual native 1440×900, 1280×800 and 1024×768 CSS layouts have no horizontal document overflow. Native 150% app zoom measures 949×574 CSS px / DPR 1.5, with working keyboard navigation. OS-window screenshot reviewed; Windows scaling unchanged. New actions use native buttons with focus treatment; unknown outcomes are neutral; status remains announced, with no new animation. |

Focused analytics, desktop query/export, source-publication/scheduling and frontend
label/status regressions passed. Production Angular type-check/build and the
isolated native build succeeded. Validation uses the actual
`https://taild.local/index.html` assets, not a recreated browser UI. All six changed
implementation files were hash-matched between checkout and tested source copy.
The native validator's initial hidden-table read failed because its disclosure
was closed; the final normal open/select workflow passes. An initial diagnostic
test invocation named nonexistent modules/omitted required test output metadata;
the affected valid contracts were rerun successfully, not counted as passes.

Private durable evidence:
`D:/Tools/taild-stage10-validation-20261013/dashboard-layout-20261014`.
`analytics-validation.json` contains build identity and measured hierarchy;
representative screenshots cover all three widths, native 150% zoom, country
focus, loading, empty and retained-real evidence states. Copies were hash-checked.

Verified served assets: `main-XTFXJ7SB.js` SHA-256
`4de49c67ff2da00c818e7e2a5e1b3f52531416e3eca3195a311901ed25af5ff2`;
`styles-AUMQ4UYW.css` SHA-256
`9ab83b74fb42d5ae39f0684d19da5fe047c7886669cff0c017ab9cce2a6f57af`.
Native assembly SHA-256
`2ba5ea58c0b2c249377c8ff81e59752574c0fb028cd8db668e0e213651a571a9`.
No live Control D read or current policy revalidation was required or performed.
R15b source acceptance is satisfied; B14 is resolved. B12 and Stage 10's remaining
installed delivery/recovery acceptance remain open; this is not overall product
completion. No release/deployment is inferred from this request.

Expendable source copies, dependency/build output, WebView caches and test histories
were removed after evidence preservation through cleanup transaction
`3d1b0d2964a4385ab6302cd02be419ff`: applied, 296,066,023 bytes, no exclusions/errors
or residual task directory. Source and durable private evidence remain available.
