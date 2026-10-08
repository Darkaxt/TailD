# Stage 5 context, correlation and metrics/query contract

Status: **COMPLETE**, 2026-10-08, for the assigned on-demand Stage 5 boundary.

Authoritative requirements: PRODUCT-SPECIFICATION R10, R11a–b and R08's metrics
boundary. This document records implementation choices and verification, not
weaker acceptance criteria. No desktop or continuous collector is implied.

## Narrow architecture and source traceability

Reuse history.py's private facts, exact integers, coverage and revision, and
join.py's strict answer decoder. Store observed context snapshots in that same
private database; never apply a new capture to older traffic. A capture includes
an explicit observation validity boundary and endpoint scope, not an inferred
physical-device association for a shared endpoint. Missing intervals stay unknown.
Correlation links are computed from retained facts at the read revision, not
cached with stale byte counters. Deletion/expiry cannot leave derived private rows.

The pinned Portmaster query request and bandwidth handler in PORTMASTER-DESIGN.md
guide the separation of validated requests, aggregation and chart results. TailD
uses original code; no Portmaster code/license/runtime dependency is imported.
One analytics module serves summaries, charts, grouped results and fact pages,
with one SQLite read transaction per bounded batch. UI clients receive aggregates
and bounded pages, not every fact. This is server-side computation even when the
current entry point is an on-demand developer command.

## Context and uncertainty

Read only whitelisted fields from supported local TailDNS CLI responses: observed
identity/account, VPN state, accepted DNS/local override, resolver binding and
exit-node/configuration. Store capture time and explicit end of observed coverage.
Never invent continuity across acquisition gaps or use current binding to label
old data. Configured MagicDNS/split routes are configuration, not event evidence;
missing resolver-event coverage is explicit. A unique preceding answer/IP/time
candidate remains inferred; all candidates and analytical age/version are retained.

## Typed data and metrics

Requests specify half-open UTC bounds, host/device and endpoint/account scope,
fact kind, allowlisted typed predicates/search, grouping/ordering, bounded page
size and optional revision-bound cursor. Unsupported field/source combinations
are errors. A stale cursor fails explicitly rather than mixing revisions or
silently skipping/duplicating rows. Batches share one revision and source coverage.
Policy snapshot querying is part of the contract; actual policy acquisition and
the wider provider capability matrix belong to Stage 6. No policy snapshot has
been acquired by Stage 5. CSV numeric action meanings remain unverified: raw
codes count as unknown, classified denominator is zero and block rate is null.
This is an explicit limitation, not a guess from the current account's values.
Control D's [CSV guide](https://docs.controld.com/docs/how-to-export-logs-to-csv)
documents separate source and answer ASN/country fields. Only well-formed
single-answer metadata is used; mixed answers cannot assign a destination country.

All R11a dictionary entries must be present, with units, denominator, scope,
coverage and version. Counts and bytes are canonical once-only facts, not joined
rows. DNS filters on traffic use existence of a candidate, not a multiplying join.
Question spelling is preserved. Geography requires validated destination metadata;
provider source-country fields cannot become destination-country statistics.
Unknown application/address/codes remain groups. Throughput bins floor-align in
UTC and expose exact byte/duration fractions; unobserved bins have null rates.
Rates describe bucketed bytes, not instantaneous utilization. Exact integer byte
values are decimal strings in JSON, including counters above 2^53 and totals
above SQLite's signed integer SUM range.

## Implemented API and persistence

`scripts/taild/analytics.py` provides `Analytics(store).batch(requests)` and the
on-demand command below. `history.py` schema v4 adds only the context/policy
snapshot area required by R10/R11; policy acquisition is not implemented early.
Snapshot expiry follows owned retention. Snapshot deletion records suppression,
including overlap deletion, so replay cannot restore the removed binding.
Correlation links are a versioned virtual view over current facts and context;
there are no persisted links/aggregates to survive deletion or go stale.

Each request has `kind` (`traffic`, `dns`, `correlations`, `context`, `policy`),
`view` (`facts`, `groups`, `summary`, `series`, `health`) and UTC `start`/`end`.
Unsupported combinations are rejected: snapshots are not traffic summaries and
DNS decisions are not a throughput series. Optional `scope` has independent
`host` (local traffic/context), `account` and `endpoint` (provider data) selectors.
An optional physical `device` requires observed historical context for traffic;
it is rejected for DNS/policy because an endpoint does not prove a physical host.
A traffic summary includes independently scoped DNS statistics, explicitly
labeled as not application-attributed; use a DNS request with its own applicable
predicates for DNS cards. It must not be displayed as process-owned DNS activity.

`where` is an allowlisted typed predicate `{field,op,value}`, or nested `all`/`any`
arrays. Operators: `eq`, `ne`, `in`, `contains`, `gt`, `gte`, `lt`, `lte`, restricted
by field type. Common identity/time/source/scope fields are supplemented by
traffic application/path, IP/port, raw protocol, byte and correlation-state fields;
DNS endpoint/client/profile/question/type/raw action/reason/protocol fields; and
whitelisted context fields. DNS predicates on traffic require one candidate to
satisfy the whole expression, not unrelated answers satisfying separate clauses.
They select traffic by existence without multiplying byte counters. Verified
protocol filtering is explicitly unsupported while the source codes are unverified.

`search` is case-insensitive literal text; `group_by` and `order_by` use allowed
fields, with `count` and byte ordering on the corresponding aggregate domain.
Traffic cannot group by a multi-valued DNS candidate; inferred-domain metrics
are the deliberately separate domain. Facts have stable time/identity tie-breaks.
A cursor binds query/limit/order and revision; a changed revision gives a stale
cursor error requiring a fresh view, never an implicit page on changed data.
Retention maintenance may also advance the revision. Same-store pagination and
batches are verified; no historical snapshot-server/session infrastructure is implied.

Budgets are explicit resource limits: 16 queries/batch, 100,000 retained source
facts or snapshots per read, 10,000 rows/page or chart bins, four group/order
fields, 256 predicate nodes/depth eight, 100 `in` values, 1,024 text characters.
The CLI bounds request input to 1,048,576 characters. The recorded analytical age
defaults to 300 seconds and supports 1–86,400 seconds; it is not a timeout or TTL.
Budget excess is an error, not a successful truncated aggregation. Data reads use
fixed SQL with bound bounds/scopes; typed predicates are evaluated in the backend,
not interpolated as SQL. No caller-supplied SQL, expressions or aliases exist.

## Metric results and denominators

All results include scope, UTC bounds, read revision, source coverage and
aggregation/correlation versions. `value_state` distinguishes observed, partial
and unobserved. Observed byte sums are retained even for partial data, but
`complete_total_bytes` is null when coverage is incomplete. An empty unobserved
scope must not be rendered as known zero. Raw source fields/provenance remain in
fact detail. No socket/PID/lifetime/encryption/blocked-byte metrics are fabricated.

| R11a entry | Result and counting domain |
|---|---|
| Received/sent/total | `data`, exact bytes from each selected canonical traffic bucket once; no WAN-only claim. |
| Throughput | `series.bins`, floor-aligned UTC, bytes / represented microseconds × 1,000,000 B/s. The exact fraction is returned; partial/unobserved source bins have null rates, not zero fill. |
| Application activity | `application_activity`, distinct observed application-record identities, bucket count and separate missing-identity count; not process/socket count. |
| Top applications/destinations | `top_applications`, `top_destinations`, received/sent/total bytes and bucket counts; null unknown groups participate in the total. |
| DNS activity | `dns_activity`, canonical provider events, preserving identical events; groups by endpoint/client/profile/question/type/raw action/trigger/protocol. |
| Outcomes | `dns_outcomes`, classified/unknown counts, classified denominator and excluded unknown count. Current unverified numeric codes all remain unknown; no invented block rate. |
| Questions | `dns_questions`, canonical event rankings/distinct spellings, normalization `raw-spelling-v1`. |
| Correlation coverage | `correlation_coverage`, counts/bytes partition into unmatched, unique-candidate, ambiguous and unusable; coverage is not attribution accuracy. |
| Candidate domains | `candidate_domains`, only unique-candidate bytes grouped as inferred; ambiguous/unmatched/unusable bytes stay separate, never repeated per candidate. |
| Geography/ASN | `geography_asn`, provider answer-metadata event counts and unique-candidate inferred traffic groups; only one parsed matching answer IP, with separate country/ASN unknown groups. Client/source country is never destination country. |
| Health | `source_health`, operational read/request/checkpoint/reconciliation times, lag, gap/attempt/error/truncation states and canonical unsupported counts; replay does not multiply unsupported fact counts. |

JSON byte fields are decimal strings, including fact/provenance counters and
rate numerators. Python integer aggregation avoids SQLite SUM overflow. Health
has an explicit as-of time and last-success age; lag is as-of minus complete-through,
with requested lag separate. Historical query bounds do not make stale data current.

## Developer commands

No UAC or new API token is needed to query the owned history. Capture uses only
`status --json`, `debug prefs`, `dns status --json` and explicit **GET** on the
inherited `/localapi/v0/local-dns` read interface. Critical whitelisted fields are
re-read; a change discards the observation without retries or settings changes.
Separate local reads are not an atomic snapshot. A point capture is stored as
one microsecond of observed context, never extended between polls or backward.
Observed continuous intervals are supported for the future event-fed runtime and
fixture verification, not synthesized by this command. MagicDNS/split configuration
is recorded but resolver-event coverage remains unavailable.

```powershell
python -B scripts/taild/analytics.py --history D:/Maintenance/TailD-history capture-context --scope local-host
@'
[{"kind":"traffic","view":"summary","start":"2026-10-08T10:00:00Z","end":"2026-10-08T10:05:00Z","scope":{"host":"local-host"}},
 {"kind":"traffic","view":"series","start":"2026-10-08T10:00:00Z","end":"2026-10-08T10:05:00Z","scope":{"host":"local-host"},"bin_seconds":60}]
'@ | python -B scripts/taild/analytics.py --history D:/Maintenance/TailD-history query --request-stdin --output D:/Maintenance/TailD-history/metrics.json
python -B scripts/taild/analytics.py --history D:/Maintenance/TailD-history delete-snapshots --kind context --scope local-host --start 2026-10-08T10:00:00Z --end 2026-10-08T10:05:00Z
```

Replace example bounds/scopes. Export is private, new and non-overwriting, inside
the validated history directory; stdout contains only status/count metadata.
The command owns no background worker and does not install/change any client.

## Acceptance evidence

- R10: context/identity/provider/exit-node boundaries; ambiguity and unsupported
  answers; no retrospective binding or false certainty, no connectivity changes.
- R11a: every dictionary metric, precise denominators and byte-conserving partitions;
  missing vs observed zero and health vs network activity; exact rate fractions.
- R11b: typed validation/injection, stable pagination/revisions, bounded batching,
  grouped drill-down/card/chart/export reconciliation, correction/deletion/expiry.
- Real retained GlassWire and Control D facts -> summary/chart/query output;
  context captured now must leave older facts historical-binding-unknown.
- Stages 1–4 preserved; no source access elevation, deployment or release.

Actual private history migrated from v3 to v4 without losing its 2,550 GlassWire
buckets or 113 retained Control D decisions. Current local TailDNS context was
captured through the above READ interfaces unelevated. The real interval
`[2026-10-07T00:00:00Z, 2026-10-08T18:00:00Z)` produced a six-result private
summary/chart/group/detail/DNS/policy batch at one revision. Total **67,680,901**
bytes (48,184,294 received, 19,496,607 sent) reconciled across summary, hourly
chart, application groups/rankings and correlation partitions. Fact count is
2,550; DNS count is 113. A fresh process independently read the export and checked
those equalities. Hourly bins retain null rates because only a small part of the
wider window was actually observed. Current capture did not retroactively bind
older traffic: every inspected historical detail remained binding-unknown.

The private export is `D:/Maintenance/TailD-stage4-validation-20261008/stage5-metrics-validation.json`;
its returned private identities/questions are not copied into Git or this document.
Policy acquisition remains not-collected, not claimed provider-denied. No fresh
Control D token was recovered or API request made. Fixture checks exercise
same-IP/shared-endpoint ambiguity, identical and duplicate answers, out-of-order
decisions, context gaps/account/provider/exit/portal boundaries, concurrent WAL
commit with one batch snapshot, cursor rejection, injection, scoped coverage,
large exact counters, corrections, deletion/suppression and v3/v4 migration/expiry.
No real resolver change was performed: the authorized live workflow was read-only;
the specification makes a mutating live-change test conditional on that authority.
No later-stage GUI/runtime, service, source write, source ACL, release or deployment.

Fresh final verification passed:

```powershell
python -B -m unittest discover -s scripts/taild -p 'test_*.py' -v
```

All local TailD contracts passed, including earlier inheritance/Control D/reader/
history/join contracts and new real-SQLite metrics/query/context contracts. No
native source, module pin, workflow or installed client changed. Private validation
history and the non-overwriting final export remain intentional local evidence;
test fixtures were removed by their owning temporary-directory cleanup. No
expendable manual helper, copied source database or persistent job was created.
