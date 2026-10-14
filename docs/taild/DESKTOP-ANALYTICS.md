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
