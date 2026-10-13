# Portmaster source design reference for TailD

Metrics reference inspected 2026-10-08; layout/widget retrieval refreshed 2026-10-13.
This is an engineering and planned-reuse reference, not yet integrated product code.
It supports the authoritative [remaining-product specification](PRODUCT-SPECIFICATION.md).

## Pinned evidence

Repository: [safing/portmaster](https://github.com/safing/portmaster).
Earlier metrics-design commit: `882d900dadb6df91150cf87f0a12706d29172586`.
The recursive GitHub source tree was complete, not truncated. Links below are
immutable source references; a later upstream design must be reviewed explicitly.

| Source inspected | Observed responsibility | TailD design obligation |
|---|---|---|
| [Application routes](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/src/app/app-routing.module.ts) | Dashboard, monitor, application and settings navigation | Keep overview, activity, application details and settings distinct; add Control D and source-health pages. |
| [Dashboard template](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/src/app/pages/dashboard/dashboard.component.html) and [controller](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/src/app/pages/dashboard/dashboard.component.ts) | Summary cards, charts, geographic breakdown and ranked traffic consumers; aggregate requests separated from rendering | Use summary-to-filtered-detail navigation, sent/received series and ranked applications. Replace unsupported connection/firewall metrics with accurately named TailD metrics. |
| [Application overview](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/src/app/pages/app-view/overview.html) and [insights controller](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/src/app/pages/app-view/app-insights/app-insights.component.ts) | Application-level overview and charts using the query service | All TailD application queries, including geography, must carry the selected application identity. Do not copy source expressions without checking scope. |
| [Activity explorer template](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/src/app/shared/netquery/netquery.component.html) | Search, multi-value filters, date range, grouping, ordering, charts, pagination and expandable rows | One reusable typed explorer for traffic and DNS facts, with explicit fact types, stable pagination and provenance drill-down. |
| [Detail template](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/src/app/shared/netquery/connection-details/conn-details.html) | Identity, peer, policy reason, process details and data-use inspection | Show verified fields, raw provider codes and candidate evidence. Do not include Portmaster rule-editing actions, encryption verdicts or process details that TailD cannot substantiate. |
| [Frontend query service](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/desktop/angular/projects/safing/portmaster-api/src/lib/netquery.service.ts) | Typed query, batch, chart and application-stat interfaces; live/history selection | Separate facts, aggregate results, chart buckets and source coverage in the TailD client contract. |
| [Query request](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/service/netquery/query_request.go) | Field selection, predicates, grouping, ordering, pagination and parameter binding | Whitelist every field/operator/alias and bind values. Use one validated query contract for cards, charts, explorer and exports. |
| [Database](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/service/netquery/database.go) | SQLite-backed connection facts, history, traffic counters and bandwidth samples | Use SQLite locally, but retain independent traffic, DNS and context facts; do not manufacture Portmaster connection IDs or socket lifetimes. |
| [Bandwidth chart handler](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/service/netquery/bandwidth_chart_handler.go) | Time grouping and incoming/outgoing sums joined to connection facts | Reuse the conceptual aggregation boundary, with floor-aligned UTC buckets and exact TailD counting semantics. |
| [Active-connection chart handler](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/service/netquery/active_chart_handler.go) | Connection lifetime and verdict-based charts | TailD cannot derive this from GlassWire time buckets. Show observed traffic activity instead, with no invented active-connection count. |
| [Netquery module](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/service/netquery/module_api.go) | Source feed, query/chart endpoints, history maintenance and lifecycle | Keep ingestion, query serving and retention distinct; use explicit ownership and cancellation. Do not copy its timing or shutdown policies automatically. |
| [General metrics module](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/base/metrics/module.go) | Registered operational counters and runtime/host/log measurements | Distinguish collector health from user network analytics. Prometheus/Grafana infrastructure is not necessary for this product. |

## Layout to carry forward

The required relationship is:

```text
TailD desktop
  Overview              summary cards -> same filtered explorer query
  Applications          ranked applications -> application detail + charts
  Activity              traffic / DNS / correlations -> evidence detail
  Control D             endpoints / profiles / policy state / capabilities
  Sources & health      completeness, gaps, unsupported data, collection state
  Settings              credentials, binding, retention, sampling, privacy
```

Use a persistent sidebar and a shared device/time/filter header. Overview cards
lead to the records that produced their value. Application details retain that
application's scope across charts and tables. Activity places search/filter
controls above charts and paginated rows, with an expandable evidence view.
This is a functional layout requirement, not a request for pixel-identical
branding, a subscription carousel, SPN pages or Portmaster firewall controls.

## Metrics design to carry forward

Portmaster's user-facing analytics principally flow through `service/netquery`
and the Angular Netquery client, not just `base/metrics`. TailD must use this
separation: durable source facts -> validated typed queries -> aggregates and
chart buckets -> presentation. Operational health has a separate small model.

Portmaster can represent identified connections and enforcement verdicts from
its own network engine. TailD's verified sources instead provide DNS decisions
and application/destination/time-bucket bytes. Similar presentation must not
imply equal observational power. The product specification defines the exact
metric denominator, source and uncertainty for each card and chart.

The reference code is not a correctness oracle. TailD must independently test
application-filter propagation, unknown values, query validation, chart boundary
alignment, large counters and counting across joins. Its defaults, polling,
subscription checks and history architecture are not imported wholesale.

## Reuse and attribution boundary

The inspected [Portmaster LICENSE](https://github.com/safing/portmaster/blob/882d900dadb6df91150cf87f0a12706d29172586/LICENSE)
is GPL version 3; the inherited TailDNS root license has different terms.
This specification uses source architecture and functional organization as design
input. It does not import Portmaster code, styles, icons, assets or dependencies,
and it does not change the repository's license.

Before any literal reuse, record each file's license/header, modifications,
attribution and distribution/source obligations, and establish a compatible
component boundary and notices. Do not represent copied code as independently
implemented or assume a separate process automatically settles licensing.
The October 13 user instruction supersedes the original-implementation default:
maximize practical reuse of the actual widgets, templates and styles. Complete the
file-specific notice/source review before copying them; framework convenience is
not sufficient reason to replace reusable components with generic cards or prose.

No Portmaster packet interception, WFP driver, DNS interception, firewall,
SPN, subscription backend or updater is part of TailD's analytics design.

## Current layout and widget retrieval — 2026-10-13

Current development head at retrieval: **`bb6c44468a5d66bddb13bf3c43fcb2625c326ca9`**,
committed October 12. The entire `desktop/angular` tree and `assets/data` were
retrieved in a clean read-only sparse clone, not just selected dashboard snippets.
[The complete inventory](portmaster-source-inventory.json) records all 972 tree
entries, modes and Git blob identities. The source clone is retained at
`D:\Temp\taild-portmaster-layouts-20261013` while required for Stage 8 reuse;
cleanup transaction `561026f6127b25194528437346bb22bb` owns that exact disposable
clone. No npm installation, Portmaster service/driver or network configuration
change occurred. Windows checks out upstream asset symlink modes as text pointers;
the actual shared assets were therefore retrieved explicitly. Inventory completeness
does not mean every file has been manually reviewed or approved for copying.

All paths below are relative to `desktop/angular/`; abbreviated application
paths such as `pages/`, `layout/` and `shared/` are under `src/app/`, at the immutable
[source root](https://github.com/safing/portmaster/tree/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular).
The table distinguishes reuse candidates from already integrated components.

| Layout/widget family retrieved | Source files/directories | Required reuse/adaptation |
|---|---|---|
| Shell and rail/side panel | `src/app/app.component.{html,scss,ts}`, `layout/navigation/`, `layout/side-dash/`, `app-routing.module.ts` | Reuse shell/rail geometry and navigation treatment; TailD route labels and authenticated lifecycle. Remove SPN/subscription/pause-interception actions and Safing branding. |
| Dashboard grid and panel chrome | `pages/dashboard/dashboard.component.{html,scss,ts}`, `dashboard-widget/` | Reuse panel chrome, responsive grid and dense summary/chart/ranking composition. Bind the existing typed TailD query revision, not upstream connection counters. No subscription/news filler. |
| Time-series chart | `shared/netquery/line-chart/line-chart.ts` | Reuse D3 rendering/series/interaction where compatible. Replace AppComponent coupling with owned resize lifecycle; use exact-value tooltips and explicit partial/null bins. Upstream `fillEmptyTicks` fabricates zeros: do not enable it for missing TailD coverage. |
| Ranked stacked consumers | `shared/netquery/circular-bar-chart/circular-bar-chart.component.ts` | Reuse circular stacked-bar rendering for sent/received application/destination rankings; accessible sorted table and consistent filter navigation. Plot scaled numeric coordinates, retain exact byte strings separately. |
| Application catalogue and insights | `pages/app-view/overview.{html,scss,ts}`, `app-view.{html,scss,ts}`, `app-insights/`, `shared/app-icon/` | Reuse searchable application list, detail header/tabs and chart panels. Retain selected application scope on every query. Remove profile editing/firewall/SPN controls and unproven running/process claims. |
| Activity explorer | `shared/netquery/netquery.component.{html,ts}`, `netquery.module.ts`, `searchbar/`, `search-overlay/`, `tag-bar/`, `add-to-filter/`, `textql/` | Reuse search/filter-chip/group/row interaction and layout. Translate only allowlisted TailD predicates, not raw SQL or upstream field semantics. Preserve compound predicates and revision-bound pagination. |
| Rows and evidence | `shared/netquery/connection-row/`, `connection-details/`, `scope-label/`, `pipes/` | Reuse expandable rows and structured attribute sections. Distinct traffic/DNS/candidate facts; hide unsupported socket lifespan, TLS verdict, PID and enforcement actions rather than inventing them. |
| UI primitives | `projects/safing/ui/src/lib/{accordion,dialog,dropdown,pagination,select,tabs,toggle-switch,tooltip,tipup,overlay-stepper}/` | Reuse required controls, focus/keyboard behavior and styles. Adapt paginator to revision-bound cursors; no unsupported arbitrary page jump. Do not include unrelated controls simply because retrieved. |
| Settings and status | `pages/settings/`, `shared/config/`, `notification-list/`, `action-indicator/`, `loading/`, `count-indicator/` | Reuse searchable grouped settings and compact status treatment for collection, credentials, retention and capabilities. No provider-write controls. Missing/stale/error are interactive states, not walls of prose. |
| Geographic display | `pages/spn/map-renderer/{map-renderer.ts,map-style.scss}`, `shared/country-flag/`, shared country/topology assets | Reuse the independent D3/topojson renderer only after dataset/license review; it accepts optional map handlers, so SPN network services are not needed. Label provider answer-country scope and retain unknowns; never imply traffic geolocation or route tracing. |
| Theme and typography | `tailwind.config.js`, `src/styles.scss`, `src/theme/`, `projects/safing/ui/theming.scss`, `assets/data/fonts/` | Reuse restrained dark surfaces, spacing, table/input/pill tokens and licensed font assets; preserve original notices. Accessibility may require contrast/focus improvements, not a different generic visual language. |

### Dependencies and reuse constraints observed

The application manifest declares Angular/CDK 16, RxJS 7, D3 7, Tailwind 3,
ng-zorro 16, Font Awesome and topojson. The local `@safing/ui` manifest still
declares Angular 12 peers; do not assume that package metadata is ready for direct
consumption. Stage 8 must use a compatible pinned build of the selected source
subset and verify it, not install all upstream dependencies or network backends.
The upstream lockfile is retrieved for exact dependency review. No framework
selection has yet been implemented.

Root GPL-3.0 applies to upstream source without a more specific notice. Initial
checks found separate Apache-2.0 Roboto font notices and a Go Squared permissive
flag notice. These checks do not license every geographic dataset or third-party
icon. Before import, record exact copied paths/blob IDs, original notices,
modifications, dependency licenses, corresponding source/build instructions and
the combined frontend's applicable GPL obligations. Preserve inherited TailDNS
copyrights; do not relabel copied GPL source as original BSD code. The frontend
reuse boundary and complete notices must be established before integration, not
postponed to release. No Portmaster source/assets are integrated by this research.

### Concrete Stage 8 design and acceptance contract

This is TailD's adaptation contract, not a claim that upstream was rendered or
measured in a running Portmaster installation. Source-observed anchors: the
dashboard uses a four-track grid with `gap-4`, a layout change at 1024px host
width, 150px minimum small summary/ranking cells and 400px major chart panels;
the shell uses a 64px navigation offset and a 419px optional side panel.

- Verify the actual TailD served URL and current asset build at 1440×900,
  1280×800 and 1024×768 CSS pixels, plus Windows 150% scaling and keyboard-only use.
  Retain screenshot evidence for overview, application insights, activity with
  expanded evidence, policy view and stale/empty/partial states.
- Preserve a 64px rail; expanded labeled navigation may replace the upstream
  notification side panel. Keep the shared device/time/filter header visible.
  Use the source's 16px grid rhythm and dense aligned panel headers; at narrower
  sizes stack major charts without horizontal page overflow. Tables may have
  their own deliberate horizontal scrolling without clipping controls.
- Overview must contain real sent/received time series, interactive ranked
  consumers, DNS outcome distribution and explicit coverage/source state, not
  only numerical cards. Major chart surfaces target 320–400px height at desktop
  sizes and maintain readable axes/legends at 1024px. Map/geographic display is
  optional only where the specified source supports it; a labeled unknown state
  must not imply measured geography.
- Every summary, series, ranked row and geographic selection opens the same
  scoped explorer; app details retain app identity. Evidence uses structured
  rows, source badges and explicit candidate/unknown labels, with raw JSON only
  as a secondary inspection/export affordance.
- Match source component structure and appearance with a before/adapted comparison
  for each major reused family. Document replacements with concrete license,
  security, semantic or dependency reasons. Review focus order, accessible names,
  contrast, non-color-only status and chart/table equivalence on the real assets.
- Formal acceptance is the complete connected UI/query/export feature, not a
  screenshot of disconnected widgets or a series of component-only validations.

Stage 7 remains ACTIVE. Stage 8 implementation and its acceptance are NOT STARTED;
retrieval and this binding reuse contract are the explicitly requested research.
