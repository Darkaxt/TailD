# Portmaster source design reference for TailD

Inspected 2026-10-08. This is an engineering reference, not copied product code.
It supports the authoritative [remaining-product specification](PRODUCT-SPECIFICATION.md).

## Pinned evidence

Repository: [safing/portmaster](https://github.com/safing/portmaster).
Inspected development commit: `882d900dadb6df91150cf87f0a12706d29172586`.
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
Direct reuse is not required to satisfy this design; an original implementation
of the specified layout and query/metrics contracts is the default.

No Portmaster packet interception, WFP driver, DNS interception, firewall,
SPN, subscription backend or updater is part of TailD's analytics design.
