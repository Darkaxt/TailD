# TailD remaining-product specification

Version 1.8, 2026-10-14. Authoritative extension to [SPECIFICATION.md](SPECIFICATION.md).

## 1. Authority, authorization and completion boundary

The user requested a specification for the remaining product areas and explicitly
required Portmaster source as the layout and metrics-module design reference.
The specification request authorized documents and their commit. The subsequent
instruction to start Stage 4 authorizes that stage's implementation, verification
and commit, including required bounded read-only live validation. It does not
authorize releases, background installation or provider policy changes. The
subsequent explicit request to start Stage 5 authorizes its implementation,
verification and local commit over retained facts and read-only local context.

R01–R07 and Stages 1–3 were accepted at the initial increment checkpoint. The
October 13 real workflow-file promotion regression reopens Stage 1/R02 for repair;
its historical verification is not proof the later boundary succeeded. This
document adds R08–R18 and Stages 4–10. The initial increment's no-background/no-UI/no-release constraints applied
to that increment. The corresponding future capabilities are now specified,
not implemented by the specification task. The October 13 instruction to continue
TailD authorizes remaining implementation, verification and commits through local
release-readiness, preserving the explicit Stage 10 delivery boundary. Stage 6 is
COMPLETE with the evidence in POLICY-READS.md; Stage 7 is COMPLETE under its
recorded live-test waiver. The reopened Stage 1 R02 repair is verified and COMPLETE;
Stages 8–9 are COMPLETE. The subsequent October 13 "go ahead", replying to the
explicit Stage 10 release/in-place Windows migration/updater question, authorizes
those live actions. Stage 10 is ACTIVE. Normal release 1.105.0+2 is published and
independently verified; authenticated Beacon migration and the actual
service-dispatched signed-channel update preserve node, addresses,
Tailnet Lock signer, service path and DNS preferences, with public/MagicDNS reads
passing. Remaining live analytics, tray/recovery and rollback acceptance remain
in the stage ledger. The October 14 instruction to continue development but stop
before the next deployment held further installed-client changes. The subsequent
October 14 instruction, "You can deploy now", lifts that hold and authorizes the
retained verified Windows candidate's in-place deployment and continuity checks.
It does not substitute isolated tests for the remaining installed proof. The
retained 1.105.0+3 candidate is now published and deployed with verified in-place
identity/DNS continuity and automatic opted-in owner collection resumption;
Stage 10 remains ACTIVE for its remaining acceptance criteria.

The subsequent deployment request authorizes the report-driven dashboard release
and correction of an observed owner-launch failure. Normal **1.105.0+5** is now
published and installed from the verified source recorded in the ledger, with
node/signer/DNS continuity, automatic opted-in collector resumption and actual
native dashboard launch verified. The transient-file ACL race is corrected
without relaxing permissions. This does not close the ledger's remaining B12
lifecycle/updater/recovery acceptance or claim overall product completion.

The subsequent "deploy when ready" authorizes the verified R15c optimization's
signed public release and in-place Windows installation. Normal **1.105.0+7** is
published and installed with exact public payload verification, identity/signer/
DNS continuity, automatic collection resumption and actual native dashboard
readiness. The upstream version stays 1.105.0. This does not close existing B12
or convert snapshot benchmarks into live startup guarantees. The ledger records
the discovered Codex MSIX AppData redirection and its evidence limits.

The [stage ledger](IMPLEMENTATION-PLAN.md) maps every requirement to acceptance
criteria. A plan cannot weaken this document. Only one implementation stage may
be ACTIVE. Unmet current-stage requirements are advancement blockers; implementable
gaps keep the stage ACTIVE. Only a presently unresolvable impediment justifies parking
it as BLOCKED. A tracked deferral must satisfy the named-later-stage contract.
Stage 9 is local release-readiness; actual delivery requires Stage 10 and explicit
delivery authorization. Neither a prototype nor Stage 9 means the product shipped.

## 2. Product purpose and platform boundary

Deliver a Windows-first local analytics application combining:

- inherited TailDNS DNS behavior, Windows tray/UI and authenticated device context;
- Control D endpoint/profile/policy state and DNS activity using READ credentials;
- GlassWire application/destination traffic and transferred-byte measurements;
- Portmaster-derived information architecture and query/metrics separation.

Control D remains responsible for DNS policy and blocking. GlassWire and existing
host security products retain firewall enforcement. TailD explains observed
activity; it does not install another network interception/filtering engine.

The required first product is one Windows host with selectable Control D
endpoints. Other endpoints may have DNS-only views, clearly labeled. An endpoint
is not a proven physical host: shared resolvers and client IDs must be represented.
Do not attribute another device's activity to this laptop from an endpoint ID alone.

Keep inherited Android DNS improvements and builds compatible. Android-wide app
traffic collection, remote host agents, cloud synchronization, AppControl network
telemetry and Control D policy writes are separately scoped extensions, not hidden
completion requirements. The currently observed AppControl interface lacks network
bytes; integration does not become mandatory merely because it exposes MCP.

## 3. Verified baseline and outstanding evidence

Initial implementation: `ae9a9e7ab57e147f0b558ac8359fdd6f5cd2b1ac`;
documentation closure: `22597e3c22f2396af14d34be801b6521fd56fcfc`.
See [LOCAL-READER.md](LOCAL-READER.md), [CONTROL-D-READS.md](CONTROL-D-READS.md)
and [GLASSWIRE-READS.md](GLASSWIRE-READS.md) for historical verification.

Observed facts: read-only Control D inventory and real CSV activity succeeded;
GlassWire SQLite reads including WAL yielded application paths, IPv4 peers and
byte buckets; the real joined export retained ambiguity and nonzero bytes.
These prove the initial slice, not a production ingestion or GUI capability.

Stage 4 subsequently verified the GlassWire 3.10.1138 catalog, two daily physical
identities, independently matched observed IPv6 layout and the real durable
traffic/filter/restart/replay path. Completed-window rows were stable across two
bounded reads; correction-aware replay still assumes no finalization guarantee.
See [LOCAL-HISTORY.md](LOCAL-HISTORY.md) for precise verification and limits.

Still unverified: universal GlassWire bucket immutability/finalization, complete
binary schema beyond the observed IPv4/IPv6 fields, provider event IDs/late-arrival guarantees,
supported filter/rule/service read coverage, action-code semantics, stable
third-party GlassWire compatibility, continuous runtime and packaged delivery.
The owning stages must establish these facts or expose the specified unavailable
capability. No field decoder, metric meaning or source guarantee may be guessed.

## 4. Portmaster design requirement — R08

The pinned [Portmaster design map](PORTMASTER-DESIGN.md) is part of this specification.
The October 13 user instruction requires comprehensive retrieval of current
Portmaster layouts before further metrics/presentation implementation and maximum
practical reuse of its actual widgets. The refreshed layout reference is development
commit `bb6c44468a5d66bddb13bf3c43fcb2625c326ca9`; the earlier metrics-source review
remains separately identified. The complete retrieved Angular/shared-asset tree is
recorded in [the source inventory](portmaster-source-inventory.json). Marketing
screenshots alone do not satisfy the source-design requirement.

Implement the same functional hierarchy: overview -> application or filtered
activity -> evidence detail. Separate ingestion/storage, typed query/aggregation,
charts and presentation. Use a shared filter contract rather than independent
card/table calculations. Distinguish network analytics from runtime-health metrics.
Do not carry over Portmaster's firewall, driver, SPN, subscription restrictions,
raw SQL/debug interface, timing constants or unsupported connection semantics.

**Acceptance:** implementation review traces layout and metrics components to the
source map; a card, chart, filtered table and export reconcile on the same facts;
there are no required Portmaster runtime processes. Reuse upstream widget code,
templates and styles wherever compatible, rather than defaulting to a generic
reimplementation. Record each reused component, adaptations and concrete reasons
for any replacement. Literal reuse must pass file-specific license/notice/source
review before integration or distribution, without rewriting inherited copyright
notices. Do not replace charts, ranked consumers, filters or drill-downs with text
blocks, placeholder counters or generic metric-card grids. Unknown/partial data
must remain honest, visible states within functional widgets.
The user additionally permits targeted improvements while retaining the same
themed widgets and overall visual language. Pixel-identical reproduction is not
required; readability, accessibility, interaction and truthful data-state changes
are allowed without replacing the design system or weakening required workflows.

Authorized visual amendment (2026-10-13): retain Portmaster's actual widget
structure, layout and interactions, but shift colour tokens toward Tailscale's
official palette. This supersedes a literal Portmaster colour match, not widget
reuse. Use restrained warm-neutral surfaces and Tailscale blue (#4b70cc), with
accessible semantic status colours rather than neon-green selection chrome.
Keep native window chrome visually coherent with the content. TailD remains
identified as the fork; visual familiarity does not assert official endorsement.

Authorized scaling-test amendment (2026-10-13): the user accepts app-local 150%
WebView2 zoom instead of changing Windows display scaling. Verify the actual
native window at that zoom, its measured CSS viewport/device-pixel ratio,
keyboard access, layout and screenshots. Windows itself stays at 100%; do not
claim a physical Windows 150% test. This replaces only that Stage 8 design-map
acceptance check, not its other viewport, accessibility or workflow criteria.

## 5. Incremental ingestion and history — R09

### R09a. Source selection and immutable provenance

Discover the installed GlassWire service data location through verified local
installation metadata and its observed database catalog; support an explicit
validated override. Query only observed one-second sources. Track each physical
database generation independently; a filename, rowid or timestamp alone is not
a globally stable ID. Validate catalog paths stay within the approved source
directory. Never sum overlapping one-/thirty-/six-hundred-second sources.

Reuse the existing read-only decoder and Control D HTTP boundary. Do not write,
checkpoint, copy active databases unsafely, alter ACLs or stop GlassWire. Include
WAL in read transactions and retain separate-snapshot limitations. Unknown schemas
stop that source's ingestion with a visible error, leaving existing history intact.

Store source/version/schema identity, query bounds, collection time, completeness,
original row identity and binary fingerprints. Keep unsupported well-formed
families as unknown records with bytes intact. Required production IPv6 decoding
must be independently matched to known addresses and Windows process/peer evidence
before use; if a source truly cannot expose it, the capability must say unavailable,
not silently discard those bytes or infer an address.

### R09b. Exact replay and completeness

Persist imported facts and their source checkpoint in one TailD transaction.
After interruption, replay must not double count, skip or mix device/source epochs.
Validate whether traffic rows update in place. If mutable, replace canonical
bucket values transactionally and invalidate/recompute affected aggregates;
never treat repeated cumulative values as new delta bytes. Identity reuse and
database replacement must start a distinct generation rather than overwrite history.

Control D ingestion needs an explicit bounded UTC window and endpoint/account
scope, with pagination or deterministic subwindows if supported. Normalize to
half-open intervals locally without assuming the provider's inclusive bounds.
Do not advance a complete checkpoint through truncated or failed slices.
An irreducibly capped interval must be marked incomplete, not called successful.

If no provider event ID exists, use repeatable window ownership and multiset
reconciliation that preserves identical real events. A hash of CSV fields alone
must not collapse two genuine equal rows. Overlap, late arrivals and provider
retention limits remain recorded. Record a complete-through time and reconciliation
revision, not a promise that the provider can never return a later correction.
Catch up retained source history after restart/resume; report expired-source gaps.

### R09c. Owned local store

Use one local SQLite analytics database with versioned transactional migrations.
Logical records: source runs/coverage/checkpoints, applications, traffic buckets,
DNS decisions, context snapshots, candidate links and timestamped policy snapshots.
Separate facts from correlations and cached aggregates. Each derived result records
the fact revision and correlation/metric version. Keep integer byte precision
end-to-end, including values above JavaScript's exact-number range.

Default detailed retention is seven days. An explicit setting can change it;
no indefinite raw retention by default. Compact summaries use the same seven-day
default unless the user explicitly chooses longer summary retention. Display
storage use, expiry and gaps. Deleting an interval/application/source must remove
dependent correlations and summaries, not leave private derived data behind.
Persist the minimum deletion-scope/checkpoint metadata needed to prevent catch-up
from reimporting deliberately removed history. Retention also constrains replay;
an automatic catch-up is not permission to restore an expired interval.
Never delete GlassWire data or provider records. Retention checks occur on ingest,
startup and explicit cleanup, with transactional consistency and no source locks
held while rendering or calling the provider.

**Acceptance:** real source read -> durable history -> filtered local result;
unchanged replay, crash-before/after-commit, mutable rows, WAL, midnight rotation,
rowid reuse, identical DNS events, truncation, late corrections, source expiry,
retention and migration fixtures pass. At least one real restart/replay preserves
totals and coverage; external sources remain unchanged by TailD writes.

## 6. Correlation and TailDNS context — R10

Preserve the existing same-endpoint, parsed-answer-IP, preceding-time candidate
method. Record the chosen analytical age, algorithm version, all candidates and
unknown TTL/cache validity. A unique candidate is still an inference, not a proven
process-to-domain association. Unsupported answers remain visible; never extract
IP-like substrings from arbitrary provider text.

Capture TailDNS authenticated identity, resolver/endpoint binding, DNS acceptance,
local override state, VPN state, selected exit-node context and relevant split-DNS/
MagicDNS configuration through supported read-only local interfaces. Whitelist
fields; do not export complete preferences, peer maps or private node keys.
Context is effective from its observed capture/change event, not retrospectively
invented. Imported older traffic without corresponding context is historical-
binding-unknown. Resolver changes, logout, device/account changes and portal
mode create boundaries; never extend old bindings through a missing interval.

Label MagicDNS/split-DNS/local-resolver activity as such only if an actual observed
resolver event proves that route. Configuration alone does not prove a particular
query traversed it. Where no event interface exists, show routing configuration
and an event-coverage gap; do not introduce a DNS interception component to fill it.
The analytics collector must work offline against retained facts and must not
control DNS, the VPN or captive-portal recovery.

**Acceptance:** shared-IP ambiguity, duplicate answers, cache reuse, out-of-order
decisions, missing context, shared endpoints and provider/exit-node changes cannot
produce false certainty. A real local resolver change partitions subsequent
correlations correctly when live testing is authorized. Existing DNS/MagicDNS/
split-route/portal behavior is unchanged by analytics.

## 7. Metrics and query module — R11

### R11a. Required metrics dictionary

Every result carries device/endpoint scope, UTC interval, source revision,
coverage and aggregation version. Missing is not zero; stale is not current.
Rates below describe sampled/bucketed data, not instantaneous link utilization.

| Metric | Definition and unit | Required restriction |
|---|---|---|
| Received / sent / total data | Sum each canonical traffic bucket's inbound / outbound / both counters once, in bytes | All observed traffic, including unmatched/unknown-family records; no claim of WAN-only or adapter-wire totals. |
| Time-series throughput | Sum bucket bytes / represented bucket duration, in B/s; optional bit display multiplies by eight | Floor-aligned UTC bins; gaps remain gaps and partial bins expose coverage. Never zero-fill an unobserved interval. |
| Application activity | Distinct observed application identities and bucket counts in the selected interval | Not OS process count, socket count or active-connection count. Preserve missing identities. |
| Top applications / destinations | Rank canonical byte totals with received/sent split | No duplicate bytes when DNS candidate links fan out; totals reconcile to overall traffic including an unknown group. |
| DNS activity | Count canonical provider decision events; group by endpoint/profile/question/type/raw action/trigger | Not traffic connections; preserve repeated genuine equal events and provider gaps. |
| DNS decisions by outcome | Counts for provider-verified allow/block/redirect/other mappings plus unknown | Unknown raw codes retain an unknown category. A block rate uses only classified decisions and separately reports excluded unknowns. |
| DNS question rankings | Canonical decision counts and distinct names under selected filters | Domain question spelling/normalization version retained; not registrable-domain/organization totals without a verified mapping. |
| Correlation coverage | Traffic bucket counts and bytes in unmatched, unique-candidate, ambiguous and unusable classes | Classes partition all selected traffic exactly; coverage is not attribution accuracy. |
| Candidate-domain traffic | Bytes from unique-candidate buckets, explicitly labeled inferred, plus separate ambiguous/unmatched byte totals | Never distribute a bucket's bytes to every candidate or call the result exact domain usage. |
| Geography / ASN | Provider-reported answer metadata or independently validated destination metadata, with source label | Source location is not destination location; mixed answers or mismatched candidate IPs cannot assign a destination country. Unknown remains a group. |
| Source health | Last successful read, requested/complete-through time, lag, gaps, truncation, errors and unsupported counts | Operational counters, not network activity or a privacy/security score. |

Unavailable metrics: per-socket/PID bytes, live connection count/lifetime, DNS
latency, blocked/saved bytes, payload inspection, encryption/security verdicts and
historical firewall decisions, unless a separately validated source is added by
an authorized scope change. Do not synthesize these to match Portmaster cards.

### R11b. Query and chart contract

Provide a typed query for traffic facts, DNS facts, correlations and policy/context
snapshots. Support UTC bounds, device/endpoint, application, destination IP/port,
raw/verified protocol, question/type, outcome/reason, source and correlation state;
text search; allowed group/order fields; stable cursor pagination; bounded batch
queries and export. Unsupported field/source combinations are explicit errors,
not silently ignored filters. Use parameter binding and field/operator/alias
allowlists, never user-provided SQL or unrestricted expressions.

Use server-side aggregation; charts and cards do not fetch every fact into the UI.
Fact queries and all summaries in one view share a consistent TailD read revision.
Stable pagination must not skip/duplicate facts while ingestion proceeds. The
aggregate/count domain is explicit: joined DNS filters may select traffic by
existence, not multiply counters. Byte sums are conserved across drill-downs.
Query limits are resource bounds, not arbitrary execution/cancellation deadlines.

**Acceptance:** known fixtures reproduce every dictionary metric and partition;
cards, charts, pages and exports reconcile; large counters remain exact; adversarial
queries cannot inject SQL; gaps, mixed-source scopes and changing revisions remain
visible. Replay/correction changes totals only by the actual source correction.

## 8. Control D read coverage — R12

Extend the first inventory/activity slice into a maintained READ integration for:

1. account/analytics-instance capability and endpoint/client inventory;
2. profiles and endpoint-to-profile associations;
3. filter, service, custom-rule/folder and restriction state exposed to the account;
4. activity questions/answers, action/trigger/reason, profile/client and available
   answer-geography metadata;
5. historical policy snapshots and source/capability/retention information.

Maintain a per-resource capability matrix with documented source, verified request
method/route, permission/account scope, response shape, pagination, rate-limit
behavior, last validation and availability. This is domain-specific integration,
not a speculative generic provider framework. Snapshot state is current as of
capture; it must not be retroactively asserted as the rule that caused an older
decision. Prefer provider-returned event reason over reconstructed explanations.

Only documented or independently verified provider-owned READ routes are allowed.
The currently documented [endpoint](https://docs.controld.com/reference/get_devices)
and [profile](https://docs.controld.com/reference/get_profiles) APIs are anchors;
the [reference index](https://docs.controld.com/llms.txt) is the discovery source.
Filter/rule/service routes and action enums are not established by this document.
The [CSV guide](https://docs.controld.com/docs/how-to-export-logs-to-csv) labels
automated access organization-only; the October 7 personal-account success is
observed capability, not a universal entitlement or service guarantee.

READ credentials are mandatory; no mutation method, cookie-based scraping,
credential-bearing redirect, permission upgrade or silent account impersonation.
If a provider does not expose a requested category, display the exact unavailable
capability and its evidence. A universal/full-API claim is prohibited. The stage
may close with an evidence-backed provider limitation and a working unavailable
state, but must not invent substitute policy data or quietly omit the category.

Manual refresh and explicit endpoint selection remain available. Surface 401/403
as credentials/capability errors, 429 with provider retry-after metadata, and network
failure as stale-source state. Scheduled future samples are distinct reads; do not
loop on a failed request or bypass provider limits. Cancellation is explicit;
protocol-mandated transport timeouts remain isolated at that transport boundary.

**Acceptance:** real account inventory/activity and each available policy category
are read and represented without writes; unavailable categories have reproducible
provider/document evidence and UI states; fixtures cover scope, pagination,
unknown fields/enums, denied access, malformed envelopes, redirect and rate limits.
No account values or query history enter public fixtures/CI/logs.

## 9. Continuous runtime and lifecycle — R13

Continuous ingestion is opt-in. It reads GlassWire's existing collector, not
packets. The desktop UI runs unelevated. A narrowly scoped Windows reader process
may run under an installer-provisioned identity with the minimum verified access
needed for service-owned GlassWire data; never relax source ACLs. A service is
justified here by unattended read access, not as a generic application framework.
The READ token and provider requests remain in the owning user's unprivileged
collector; the privileged reader does not need them or browser data.

The default product sampling requirement is one traffic refresh opportunity per
10 seconds and one provider activity opportunity per 60 seconds, configurable
upward to respect provider capacity. These are data-acquisition cadences, not
timeouts, completion tests, sleeps or forced cancellation. Serialize each source;
coalesce missed ticks and never overlap or abort an active read to meet cadence.
October 14 correction: source acquisition is independent and concurrent across
Control D and GlassWire; only local database operations are serialized. Control D
is the primary integration and starts promptly when enabled, regardless of a held
GlassWire read/backfill. GlassWire reads the recent overlap first on every pass,
then advances a bounded durable backfill, so current traffic continues forward
while older history is reconciled. Neither source may hold the other's network
or source-read opportunity. Preserve per-source quota, exact replay and lifecycle
contracts; no parallel reads of the same source.
Filesystem notifications may trigger discovery but are not proof a bucket is final.
Use provider-supported rate limits and declared analytical overlap windows.

Record explicit disabled, starting, collecting, paused, stale/error, incompatible
and stopping states. Pause stops new reads; shutdown awaits the current transaction
or explicit cancellation. Resume/start/network-restored events drive catch-up.
No arbitrary watchdog kills, retry loops, lock stealing or timeout-based recovery.
Dashboard read snapshots must not prevent the owning writer from committing
acquired facts. Normal history initialization establishes SQLite WAL mode before
opening concurrent views, keeping one consistent revision per dashboard batch.
Genuine storage failures still roll back and freeze writes until explicit resume;
contention must not be concealed by extending busy timeouts or restarting queries.
Closing the window does not implicitly disable enabled collection; an explicit
Exit/pause control explains whether the collector remains active.

**Acceptance:** authorized live start/pause/resume, window close, process restart,
sleep/wake, network loss, provider denial and GlassWire stop/update produce correct
states and conserved history. No duplicate collectors; no visible helper consoles;
no changes to the VPN, firewall, GlassWire service or other installed clients.

**Authorized acceptance amendment, 2026-10-13:** the user has no isolated Windows
test host and explicitly waived forced live sleep/wake, network-loss and GlassWire
stop/update tests on the active laptop. Do not disrupt that laptop to manufacture
evidence. Their handling requirements remain in scope; verify native event wiring,
bounded source unavailability/generation recovery and conserved history through
the available isolated contracts. Physical/live disruptive scenarios are expressly
untested, not passed, and are no longer Stage 7 advancement blockers. The user
will report problems if these events naturally expose defects. This is a user
waiver of those acceptance tests, not a claim that simulated events prove them
or an unnamed required-work deferral. Live provider READ, denied/throttled-provider
contracts, actual window lifecycle, ownership and other R14 checks remain required.

## 10. Security, privacy and resource boundaries — R14

October 14 deployment correction (R14a/R18, ACTIVE Stage 10): opening the
dashboard and resuming opted-in collection must tolerate normal SQLite journal
removal and atomic diagnostic-file replacement. Validate Windows ownership,
allow-list ACLs and link identity against the opened object, not a pathname
enumerated before a separate PowerShell process. A transient file absent when
opened is absent, not a launch failure; access denial, public ACLs and links still
fail closed. Verify deterministic disappearance before/after open, existing
security rejection contracts and the installed owner dashboard/collector workflow.

R14a (first persistence): user-owned analytics storage and exports have restrictive
ACLs for the owner and required Windows administration/system identities; data is
not globally readable. No secrets or private records in Git/CI/arguments/logs.
Plaintext database contents require Windows account/disk protection; do not claim
application-level encryption that has not been implemented. No cloud upload.

R14b (provider): persistent credentials are optional and stored through Windows
Credential Manager or user-bound DPAPI, never plaintext settings. Interactive
input does not echo. Show account scope without revealing the token. Revocation/
replacement removes the prior local credential reference. Do not recover a token
from chat/transcript to install it; obtain it through the secure product entry flow.

One-time authorized credential-setup amendment (2026-10-13): when asked to enter
the already-supplied READ token, the owner explicitly instructed the assistant to
use that token and run setup itself. This authorizes saving only that owner-supplied
Control D READ token through the hidden local credential-entry flow for Stage 10.
Do not repeat it in command-line arguments, diagnostics, source, CI or public output;
no other credential recovery, permission upgrade or provider write is authorized.

R14c (runtime/UI): use an ACL-restricted authenticated named pipe for privileged
reads with an allowlisted command/schema/path surface. No shell command, arbitrary
file access or general SQL execution. Authenticate user ownership, not just PID
or membership in an interactive session. Local dashboard API has per-user/session
authorization and origin/CSRF protections, even on loopback; no LAN listener or
credentials in URL parameters. Serve packaged local assets with restrictive CSP;
render provider text as text, not HTML. External links open separately and never
receive credentials or browsing access to the local API.

R14d (retention/resources): enforce explicit retention/delete/export controls,
source-window/page/queue bounds and backpressure. On disk exhaustion, preserve
committed data, stop new writes visibly and retain replay checkpoints correctly.
Do not silently evict private evidence to hide an error. Diagnostics default to
counts/status/version, with preview/redaction before explicit private export.

**Acceptance:** access tests from a different non-admin account and unauthorized
IPC/web origins fail; tokens cannot appear in traces/exports; provider strings
cannot execute markup; pause/deletion/restart cannot resurrect deliberately deleted
history; bounded queries and disk-full interruption cannot corrupt checkpoints.

## 11. Portmaster-derived desktop layout — R15

The UI is a packaged local desktop surface opened from a TailD shortcut. It reuses
the inherited TailDNS connectivity tray behavior, not the proprietary official
GUI. The exact application shell/framework is an implementation choice; selecting
one must preserve the following layout, local security and packaged-runtime tests.
Do not require installing Portmaster or copying its entire Angular application.

Use the current retrieved dashboard, application insights, Netquery explorer,
details, navigation, theme and `@safing/ui` controls as the concrete component
reference. Prefer a compatible Angular subset to discarding reusable widgets for
another framework without a demonstrated need. Adapt only the product bindings,
unsupported semantics, security and exact-counter/gap behavior necessary for TailD.
The design map defines representative viewport/layout and screenshot acceptance;
verify the actual served assets, not only source or mock previews.

Persistent sidebar: Overview, Applications, Activity, Control D, Sources & health,
Settings. Shared header: device/endpoint, time range, source freshness/coverage and
active filter chips. Default to the rolling Last 7 days (exactly 168 hours), and
offer Recent (15 minutes), Last hour, Today and explicit UTC range. Display
timezone conversion and preserve UTC query semantics. Refresh rolls a preset
forward; navigation and explicit/saved scopes retain their selected bounds.
Multi-day charts show UTC dates. Seven-day traffic aggregates must include
all retained traffic facts without truncation or materializing the entire traffic history
in memory; existing explicit fact/export and response resource bounds remain.

October 14 user amendment (R15a; owned by ACTIVE Stage 10):
refresh must show a centered Portmaster-themed loading indicator over a translucent
content scrim while retaining the old revision. Loading lasts for the actual
operation, never an artificial delay; error clears it and keeps prior data. Native
Close remains available. Repeated refresh cannot enqueue duplicates or mutate the
displayed scope. Avoid redundant correlation preparation within one revision-bound
dashboard batch; no cross-revision cache or weakened coverage/query semantics.

Application-facing labels use the executable basename, with full path available
in title/details. Full paths and canonical application identities still drive
filters, navigation and exports; equal basenames must not merge distinct paths.

October 14 dashboard-performance amendment (R15c; owned by ACTIVE Stage 10):
the user explicitly authorizes optimizing the dashboard query and loading paths.
Keep the seven-day default, exact integer counters, correlation uncertainty,
source coverage, existing resource/privacy limits and consistent read revisions.
Remove measured repeated scans/object expansion rather than hide delay behind a
spinner. Display completed independent dashboard domains without waiting for
unrelated expensive work, while clearly marking pending panels; never mix their
revisions or enable a drill-down against an unfinished/stale generation. Keep
navigation and native closure responsive, coalesce duplicate refresh and discard
superseded presentation results without arbitrary cancellation deadlines.
Use the existing Portmaster widgets and Tailscale palette, not a visual redesign.
Acceptance: compare complete baseline/optimized results on one fixed retained
seven-day snapshot; exact outputs must reconcile and measured complete-query
latency must improve materially. Verify actual native packaged assets with held
work, independent panel readiness, error recovery, refresh/navigation and
revision-bound drill-down/export. Record actual timings and unsupported timing
boundaries, not a synthetic instant-load claim. No collection/DNS/retention change
or installed deployment/public release is implied by this optimization request.

Restore the pinned Portmaster dashboard's compact country/map grouping and paired
consumer/bandwidth panels, preserving Tailscale colors. Include its offline D3
world-map widget with reviewed topology/source notices, country selection linked
to the same scoped explorer, keyboard/list equivalence and explicit unknowns.
Only unique temporal candidate answer-country bytes may highlight countries;
unobserved geography remains neutral, never fabricated routes/location. Keep
country/ASN tables and unsupported firewall/SPN widgets excluded. Verify actual
served assets at the existing representative viewports and app-local 150% zoom,
held refresh/error recovery, duplicate names, country drill-down and exact export.

October 14 report-driven dashboard amendment (R15b; owned by ACTIVE Stage 10):
use [the complete layout mapping](PORTMASTER-LAYOUT-MAP.md) to improve the
dashboard, without expanding this request into other pages, collectors or delivery.
Keep the existing Tailscale palette and Portmaster panel/chart primitives. Place
six meaningful scope-bound summaries above a primary DNS decision-count chart,
with collection status alongside them. Show Control D first in that status panel;
keep GlassWire acquisition independent. Country tiles and the map coordinate
hover/focus without changing filters until activated. Preserve unknown country/ASN
tables, ranked consumers, destinations, DNS questions and correlation partition.
Dashboard links preserve interval and applicable scope into activity/application
details; DNS always exposes its independent endpoint scope. Do not introduce
firewall/SPN/privacy scores, subscription cards or news.

Acceptance: decision-count bins reconcile with the canonical DNS summary and
filtered facts at one revision, use DNS coverage (not traffic coverage), and keep
unobserved bins as gaps. A bin drill-down uses the intersection with the selected
half-open interval. Six summaries and collection-context actions work end to end;
country hover/focus coordinates the map without a query, and selection opens the
same country-filtered facts. The complete dashboard fits actual served/native
1440×900, 1280×800 and 1024×768 viewports and app-local 150% zoom; keyboard actions,
empty/partial states, loading/error recovery, exact counters, same-name application
identities and exports remain valid. No installed update or public release is
implied by this amendment.

Overview follows the pinned dashboard's card/chart/ranked-consumer structure:
received/sent data, observed applications, DNS decisions by verified outcome,
correlation coverage; sent/received time series; top applications, destinations
and DNS questions; geographic breakdown with unknowns; source status. A country
table is required; R15a now also requires the truthful interactive map. Omit subscription/news/SPN widgets.
Each card drills into exactly the scope that produced it, preserving time/device.

Applications lists executable identity, received/sent bytes, last observed bucket
and correlation coverage. Detail includes identity/provenance, traffic charts,
destination rankings, candidate DNS questions and scoped activity. Do not rename
an application from a domain or merge different paths merely by display name.

Activity uses Portmaster's search -> filter/group/order -> chart -> paginated
expandable-row relationship. Separate Traffic, DNS and Correlations fact modes.
Show correlated candidates as candidates, with an explicit unique/ambiguous/
unmatched badge and no color that implies a proven allow/block verdict.

Control D shows endpoint/profile associations, current policy snapshots and the
resource capability matrix. Sources & health shows lag, completeness, gaps,
unsupported fields, privileges and compatibility. Settings provides secure
credentials, endpoint binding, sampling, retention, privacy/export and collection
controls. Provider policies and firewall controls remain read-only with optional
links to their owning application/site, not inert copied Portmaster buttons.

**Acceptance:** a real-data overview -> application -> filtered activity -> evidence
workflow works in the desktop shell, with consistent numbers and no privileged
UI. Source unavailable/stale/empty/loading states are visually distinct from zero.
Keyboard navigation, focus order, text labels, screen-reader names, contrast,
scaling and narrow-window behavior pass focused accessibility/UX review.

## 12. Explorer, details and export — R16

Support combined filters and grouping from R11, removable chips, stable pagination,
sorting, saved local queries and explicit refresh. Live refresh preserves the
selected/focused row and does not mix revisions. Details show original source,
UTC/collection timestamps, bytes, raw protocol/metadata, endpoint/profile,
available policy reason, context capture and correlation evidence/uncertainty.
Unavailable PID/socket/encryption fields show unavailable, not plausible defaults.

Provide local JSON evidence export and CSV analytical export with schema/metric
versions, query scope, units and completeness. CSV prevents spreadsheet formula
execution; export uses non-overwriting/private-file rules and an explicit user
destination. Preserve integer bytes, unknown categories and inferred labels.
Exports never include credentials, private keys or unnecessary account/peer data.

**Acceptance:** card-to-explorer, compound filters, saved-query reopening, paging
through concurrent ingestion, details and export round-trip are verified. Export
totals match the selected revision. Synthetic hostile text and large integers
cannot change query semantics, execute formulas or lose precision.

## 13. Packaging and local release-readiness — R17

Keep TailD as the analytics-development derivative of TailDNS. Do not alter
TailDNS/core maintained repositories or redirect their installed updater as part
of implementing analytics. New Windows work belongs to TailD-owned source or a
reviewed minimal build overlay against the exact inherited shared-core revision;
do not copy the whole tray/DNS codebase or silently replace its pin.

The Windows package must include desktop UI/assets, analytics runtime, required
reader/credential setup and matching inherited connectivity components where an
in-place client upgrade is selected. End users must not need a developer Python,
Node or Go installation. Reuse validated contracts; a production port of the
Python slice must pass the same source/correlation privacy tests.

Preserve the user's in-place installation preference: installed connectivity
components remain under `C:/Program Files/Tailscale`, preserving the existing
service identity, authenticated node, Tailnet Lock signer and configuration.
No permanent `TailDNS/versions` store, parallel vanilla/TailD VPN services or
re-login to introduce analytics. Analytics state belongs in an owner-private
Windows data folder, never Program Files. Analytics failure must not stop DNS/VPN.

Installer changes require a defined rollback that restores verified binaries,
startup/service state and compatible analytics schema without touching node keys
or provider policy. Preserve official/inherited state-icon transparency and
connectivity feature parity. Uninstall offers explicit analytics-history removal,
but never silently deletes GlassWire history, provider configuration or tailnet nodes.

Prepare a TailD-owned GitHub build/sign/package workflow; credentials are absent
from candidate checks and untrusted source jobs. Use a dedicated reviewed TailD
signing arrangement, not copied TailDNS production secrets. Pin the verification
key outside downloaded manifests. Preserve the official upstream version and
append only the monotonic fork subversion. Do not manufacture upstream versions.
Packages/manifests identify all component revisions and hashes, architecture,
license notices and migration compatibility; distinguish manifest signatures
from Authenticode. No updater activation or release publication in Stage 9.

**Acceptance:** clean production build and local installer exercise in an isolated
Windows test environment, upgrade/rollback/uninstall and account-state preservation
pass; assets and all bundled runtimes are present; offline launch is functional;
signature/manifest/tamper/version rules are testable; end-user launch uses one
documented shortcut with no competing legacy GUI or visible helper console.

## 14. Final validation, delivery and maintenance — R18

Reconcile all R01–R18 before product completion. Run focused regressions plus
cross-layer verification appropriate to ingestion, security, DNS compatibility and
packaging. Required real workflow: enabled collection -> restart/resume and
correction -> reconciled metrics -> desktop drill-down -> private export.
Historical October 7 samples do not substitute for the new production workflow.

October 14 tray-interaction clarification: left-click opens or focuses the TailD
analytics interface; right-click retains the inherited connectivity menu and its
features. Repeated activation must not create a second desktop or collector.
Implement this narrow Windows launch/focus integration in Stage 10 and verify
actual tray event -> owning-user desktop, minimized restore and repeated focus,
plus preserved right-click controls. Existing Start menu launch remains available.

October 14 ingestion/window clarification: show a persistent themed in-app notice
while history is being read, with the actual source interval and committed read
count when available, plus latest stored traffic/DNS observations. Explain when
the selected period has no imported observations; do not infer complete coverage
from the latest event, fabricate a percentage/ETA or emit repeated OS popups.
Refresh this diagnostic notice only while the dashboard is visible, without
starting source reads, changing the selected range or invalidating its revision.
Read-only dashboard queries and ordinary window closure must not wait behind an
unrelated source acquisition. Serialize reads within each source and SQLite writes,
not acquisition across independent sources, and
retain revision-consistent queries/exports and explicit lifecycle acknowledgments.
Use the inherited unmodified Tailscale icon for the dashboard executable and
window/taskbar, with source provenance. These are Stage 10 acceptance requirements;
the user chose ingestion visibility, not a change to retention or the 15-minute
default. The subsequent October 14 instruction additionally requires independent
source acquisition and recent-first GlassWire collection as specified in R13.

Stage 10 requires separate explicit publication/deployment authority. Publish one
normal signed release only after Stage 9 closure; independently download and
verify exact source/asset hashes, version/architecture, signatures against the
pinned trusted key, license notices and complete payload. Then perform an approved
in-place Windows rollout with rollback available and retained signing ability.
No Android deployment is required for this Windows analytics product.

Updater activation must be explicitly selected and tested against TailD's own
signed release channel, with replay/tamper/downgrade/partial-download rejection
and recoverable interruption. Never redirect installed TailDNS users without
their explicit migration. Preserve checked TailDNS inheritance and validate the
analytics/runtime/package contracts on each future merge. Record tested GlassWire
schema/version compatibility; fail visibly on incompatible source updates.

Keep the existing TailDNS/SleepManager maintenance scope unchanged. This task
creates no new heartbeat or host task. Product-specific recurring maintenance
can be configured only as an explicitly requested delivery action, with defined
merge/check/release behavior and no automatic device deployment.

**Acceptance:** complete requirement/evidence reconciliation, authorized live
production workflow, independent normal-release verification, successful approved
installation/update/rollback and a documented ownership/compatibility procedure.
No unresolved required blocker or tracked deferral remains. A missing delivery
authorization parks Stage 10; it does not make it COMPLETE.

## 15. Stage mapping and verification boundaries

| Stage | Required scope | Status at specification creation |
|---|---|---|
| 1–3 | Initial inheritance, Control D reads, real joined slice (R01–R07) | COMPLETE; existing recorded evidence only |
| 4 | Incremental source -> durable history -> local query; R09, R14a | COMPLETE |
| 5 | Versioned correlation/context and metrics/query contracts; R10, R11, R08 metrics boundary | COMPLETE |
| 6 | Remaining Control D READ/capability coverage; R12, R14b credential boundary | COMPLETE |
| 7 | Opt-in continuous lifecycle and secure runtime; R13, remaining R14 | COMPLETE |
| 8 | Portmaster-derived desktop layout/explorer/export; R08 layout, R15, R16 | COMPLETE |
| 9 | Production packaging and local release-readiness; R17, R18 pre-delivery reconciliation | COMPLETE |
| 10 | Authorized release, rollout, updater proof and final reconciliation; remaining R18 | ACTIVE; delivery/migration/updater authority granted |

Each stage's detailed acceptance obligations are in the ledger. Verification
of an earlier implementation remains valid only for unchanged relevant code and
conditions. A missing future capability is ordinary remaining work, not evidence
that the specification task failed or that product implementation has started.

## 16. Explicit non-goals and limits

No new firewall/packet driver, TLS decryption, Portmaster subscription service,
Control D writes, replacement GlassWire collector, unvalidated AppControl network
adapter, cross-device process attribution, remote management server or cloud
telemetry. No fabricated socket/latency/security/blocked-byte statistics.

Provider-denied/private unsupported interfaces are not bypassed. Internal GlassWire
compatibility is a maintained empirical contract, not a promised public SDK.
Required unknown/unavailable handling is part of product correctness, not a way
to mark missing required UI, ingestion or metric calculations complete.
