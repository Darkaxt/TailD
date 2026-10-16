# TailD remaining-product specification

Version 1.9, 2026-10-15. Authoritative extension to [SPECIFICATION.md](SPECIFICATION.md).

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

October 15 authorized credential-setup amendment (R14b): the owner requested
acquisition and registration of a separate Control D Write token, then explicitly
confirmed `TailD Management`, account-wide Read/Write, with no allowed-IP
restriction. Store it in a distinct owning-user Windows Credential Manager entry;
preserve the existing READ entry and all collector defaults. The Write entry
requires an explicit permission selector; replacement additionally requires
confirmation of Write access. Hidden
interactive input, explicit non-echoed stdin and a single-use loopback entry form
are allowed. Loopback entry binds only 127.0.0.1 on an OS-selected port, requires
an unguessable entry capability plus exact Origin/Host and CSRF checks, authenticates
the token to the existing READ account before persistence, never logs requests,
and closes after the registration result. Do not use clipboard history or files
to transfer the secret. No token
in argv, files, logs, source or output. Verify vault read-back, unchanged READ
credential and provider authentication without changing any profile policy. This
authorizes credential setup only; it does not silently turn existing READ flows
into mutation clients or claim incident-management/live-stream UI implementation.

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

October 15 correction (R15d; ACTIVE Stage 10, explicitly authorized): repair
the indefinitely loading Overview panels and slow Applications page on grown
real history. Reconcile run coverage from one revision-local preparation, rather
than repeating per-attempt SQL scans for every bin. Application-only rankings
must not evaluate unrelated DNS correlations. Preserve exact counters, ordering,
correlation semantics, coverage gaps/deletions/late resolution and read revisions.

Provide independent Control D answer-geography observations even when no local
traffic/resolver binding exists. Default the coordinated country/map widgets to
DNS decision counts; retain an explicit inferred-traffic-bytes mode. Label each
metric, scope and missing metadata. DNS country selection opens matching DNS
facts; traffic-country selection retains the existing inferred traffic explorer.
Never present DNS counts as transferred bytes or infer a host/location from them.
Classify only provider-verified action codes; retain raw actions and unknown codes,
version the mapping and report the classified denominator/excluded unknowns.

Acceptance: deterministic regressions reproduce the prior scan amplification,
application correlation dependency and unknown-only outcomes; unchanged coverage
and exact results reconcile against the previous evaluator on bounded fixtures.
Benchmark the actual physical seven-day history through read-only snapshots,
including Applications and progressive Overview, with no settings/retention change.
Verify current native served widgets, country/outcome drill-down, loading/error/
navigation/close and representative layout/scaling. Perform sequential bounded QA
reviews of TailD-added lifecycle/IPC, ingestion/data and presentation code; triage
concrete acceptance defects and verify repairs. No new release or installation is
authorized by this correction request alone.

The subsequent October 15 request additionally authorizes a capability-focused
repository README and actual native dashboard screenshots. Capture an explicitly
synthetic, reproducible demonstration fixture; publish no private account, domain,
application or host data. Identify screenshots as development-main UI, distinguish
shipped functionality from unreleased corrections and retain upstream licensing,
attribution and the independent-fork identity.

The subsequent explicit October 15 "Go ahead" authorizes publishing and deploying
this verified correction on Beacon. Use the complete existing signed Windows
pipeline, keep the pinned upstream base version and append the next monotonic
TailD sequence. Independently verify public artifacts before the ordinary in-place
installer. Preserve node/signing identity, DNS, opt-ins, credentials and history;
verify installed dashboard/collector recovery. Retain the verified previous
release for recovery. This does not close unrelated Stage 10 acceptance gaps.

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
controls. Firewall controls and analytic policy reads remain read-only; R19
separately authorizes explicit confirmed Control D incident actions. Optional
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

## 14a. October 15 incident-management amendment (R19–R21)

The owner authorizes implementation, bounded sequential QA reviews, a normal
public release and in-place Windows deployment. Stage 10 owns this amendment.

R19: Add a Control D incident workspace using existing Portmaster widgets and
Tailscale charcoal/blue. Select an explicit endpoint; show its enforced profile
and all endpoints sharing that profile before changing policy. Provide Rules,
Filters, Services and Profile Options tabs, searchable recent DNS and Block /
Allow / Edit actions. Allow means explicit Bypass, not rule removal. Support rule
creation/modification/deletion and filter/service/option edits on provider-returned
resources. Account/billing administration, endpoint reassignment and a full
website clone are not required.

October 15 owner refinement: blocked resolutions show the provider's blocking
trigger and supplied rule/filter/list/service identifier or label, plus supplied
category labels in decision details. Descriptive classification is not proof of
the blocking cause. Missing trigger/name/category metadata stays explicitly
unavailable; never infer a specific blocking list from the outcome alone.

Reads use the READ vault target; writes only the separate Write target after
account-continuity verification, explicit preview/confirmation and fresh profile /
resource conflict checks. Credentials never enter the renderer. No automatic
mutation retries. Ambiguous transport outcomes require a fresh read before another
explicit action. Read back successful writes; show locked/unsupported resources.

R20: Independently collect the bound endpoint's live DNS SSE using READ access
when DNS collection is enabled. Persist through the single SQLite writer even
with the dashboard closed. Complete historical CSV intervals remain authoritative
and fill gaps. Stream observations never assert complete coverage. Reconcile
overlap without inflating counts, preserving repeated identical requests. Pause,
binding changes and shutdown cancel actual I/O and drain the original worker.
Expose connection/error/last-event state. Explicit refresh/resume or real network
lifecycle events restart disconnected streams, not an arbitrary reconnect loop.
Never expose stream auth URLs or tokens.

R21: Size the answer-country map card to its content instead of stretching to
the two neighbouring grid rows. Verify actual served desktop/narrow layouts,
empty/populated states, and preserve unknown rather than zero-filled data.

Acceptance: real READ inventory/recent DNS and live stream -> persisted facts ->
dashboard; real Write operations/readback on an unassigned task-created test
profile, exact test-profile cleanup and unchanged production policy; native UI
confirmation/conflict/error flows and responsive map geometry; independent QA;
fresh focused integration/build checks; independently verified public release and
installed owner workflow preserving node identity, DNS, credentials and history.

### October 15 provider/product branding refinement — R22

The owner requests Control D artwork for its navigation tab, banners and titles,
and Tailscale artwork in place of textual TD brand marks. Stage 10 owns this
already-authorized visual change. Use the recognizable Control D symbol and
Tailscale nine-dot mark consistently in navigation, page headers, provider panels
and source labels. Preserve TailD's name, independent-fork notice, accessible
control names, existing widgets, Tailscale charcoal/blue theme and all behavior.
Brand artwork identifies products, not connection state or official endorsement.

Bundle reviewed static vector geometry in the frontend; no remote logo requests,
new runtime dependency, HTML injection or relaxed native origin/CSP is required.
Record source provenance and trademark ownership separately from code licensing.
At the existing 64px rail, marks fit the 40px navigation target; heading marks
align with text and provider wordmarks keep their aspect ratio. Verify the actual
native-served UI at desktop and 560px width, and app-local 150% zoom, with no logo
clipping, horizontal page overflow, changed navigation or unreadable active state.
Retain focused screenshot/DOM evidence. This request does not authorize another
public release or installed-client replacement.

### October 15 incident-first navigation refinement — R23

The owner identifies recent allowed/blocked DNS activity, rather than the Rules
editor, as the Control D page's main purpose. Stage 10 owns this authorized
refinement. Keep a compact endpoint/enforced-profile context at the top, followed
immediately by searchable recent resolutions with Follow, stream status, decisions,
provider blocking reasons and Block / Allow / Edit actions. Rules, Filters,
Services and Profile Options remain available below that primary incident panel.
Retain shared-profile impact and explicit preview/confirmation before writes.
Do not change collection binding, provider permissions, query scope or retention.

Acceptance: actual native-served DOM and screenshots demonstrate recent DNS above
policy tabs/editor at desktop and narrow width; a stored blocked resolution with
its supplied filter/category is visible, and its incident action reaches the
same guarded preview/apply path. Policy tabs, direct rule editing and conflict
guards continue to work. Integrate R22 branding without reverting its geometry,
accessibility or offline asset contract. No new release/deployment is requested.

### October 15 category navigation and Tailscale controls — R24

The owner requests collapsible product categories: persistent Tailscale and
Control D icons, with only the selected category's pages shown. Keep Analytics
as its own category for the existing cross-source dashboard, Applications,
Activity, Sources & health and collection settings. Tailscale exposes Connection,
Preferences and DNS resolver pages. Control D exposes Recent DNS and Profile
policy (its existing Rules/Filters/Services/Profile Options). Cross-page incident
actions must reach the correct category and preserve edit/confirmation state.
About replaces READ at the bottom-left, accessible from every category. This
refines R23's combined-page ordering into separate Recent DNS / Profile policy
tabs; recent resolutions remain Control D's default landing page.

Bring the tray's five preferences, reset-to-defaults and custom resolver controls
into the custom Tailscale pages, alongside device/peer status, connect/disconnect,
exit-node choice, LAN access and Run as exit node (preserving advertised subnets).
Preserve the tray, account/authentication,
Taildrop, updater, signer and node identity; this is not removal of tray features
or migration to a new VPN service. Changes use the existing owning-user daemon
LocalAPI through the installed fixed CLI, not a generic renderer shell/RPC or
another privileged service. Keep exact masked preference semantics and system
policy restrictions. Only explicit user controls mutate network settings;
opening/navigating pages never does. Autosave ordinary preferences, confirm
reset/disconnect, validate resolver input and pin its update to the loaded profile.
Reject stale profile/setting snapshots; read back successful changes, report
uncertain/rejected outcomes without automatic mutation retries or elevation.
Never return private preference keys, LocalAPI credentials or unrestricted daemon
responses to the renderer. The inherited generic prefs API has no atomic profile
compare-and-swap: use fresh snapshot preflight and profile/readback checks, and
report concurrent/uncertain outcomes honestly rather than claiming atomicity.
Resolver writes retain the daemon's explicit ProfileID guard.
About shows product/version/provenance, independent
fork attribution and fixed project/releases/license destinations.

Stage 10 owns R24. Acceptance: category exclusivity and persistent roots/About;
actual native control -> authenticated pipe -> typed backend -> isolated daemon
boundary -> readback, including denied/stale/reset/resolver/exit-node cases;
real installed-daemon read-only compatibility check without network mutations;
desktop/narrow/150% rendered navigation, keyboard focus and screenshots; existing
analytics/incident behavior preserved; focused security/packaging regressions and
build verification; commit/sync. The refinement originally authorized no delivery.
The owner's subsequent October 15 instruction authorizes publishing and deploying
the complete verified R22–R24 update through the existing signed release and
in-place installer path, preserving login, signing identity, credentials, history,
source opt-ins and network preferences. Verify the public download and installed
payload plus actual owning-user category/About workflows before claiming delivery.

### October 15 local-control responsiveness and state clarity — R25

The owner rejects analytics-style refresh blocking on local Tailscale pages.
Local Connection/Preferences/DNS/About requests must remain serviceable while
analytics work is pending; analytics loading, timestamps, errors and admission
limits must not block or describe those pages. Preserve the original analytics
operation through its real completion. No timeout/cancellation workaround,
stale-success fallback, relaxed origin/CSP, new service or generic RPC.
Reuse the owning-user authenticated pipe contract with a narrowly allowlisted
independent local-control lane in the same collector; preserve mutation ordering,
policy/profile/conflict guards and readback. Avoid five sequential CLI startups
for independent GETs; changing local tabs must reuse the mounted state without
another fetch. Initial local reads remain honest asynchronous service reads,
not metric aggregation or an assertion of zero physical latency.

Explicitly distinguish tailnet DNS acceptance from the optional per-device
custom override. Show whether each is enabled and whether an endpoint is saved;
never imply all DNS is disabled when only the override is absent. Do not invent
or automatically restore a provider endpoint without explicit owner authority.
The owner's subsequent correction explicitly requires the Windows device override
enabled with the previously supplied `https://dns.controld.com/1ck0taaf0tt`.
Verify the current account/endpoint association and direct DoH response first;
apply through the profile-pinned local-DNS edit and verify public DNS, MagicDNS,
and applied state. Preserve the previous state for rollback if resolution fails.
Do not change tailnet-wide DNS or Control D policy. Missing/mixed-profile resolver
responses are unavailable/conflicting, not Disabled. Operational applied/reason/
portal changes must not invalidate an unrelated preference edit. About has one
page heading and product identity, without a nested repeated About panel title.

Stage 10 acceptance: two sequential bounded QA reviews; deterministic held-query
native workflow proves local reads and controls usable before analytics releases;
invalid analytics dates do not affect local pages; separate admission limits,
same-user authentication and graceful lane/request shutdown pass; malformed,
profile-conflict and operational-state regressions pass; actual native desktop,
narrow and 150% screenshots plus measured initial-read/tab-navigation timings;
read-only installed-daemon compatibility and focused build/security/packaging
checks; commit/sync. The owner's subsequent "go ahead deploy when ready" authorizes
the signed normal Windows release and in-place local installation of this verified
correction. Independently verify public signatures, checksums, exact source/core,
version and payload before installation; verify device identity/signing ability,
custom resolver, public/MagicDNS, live collector and installed UI after it. Preserve
the previous verified release for rollback. No provider-policy or tailnet mutation.

### October 15 incident loading and navigation icon correction — R26

Recent DNS must read the current endpoint's retained resolutions independently of
both pending dashboard aggregation and remote policy retrieval. Source diagnosis:
the local 15-minute read returned 81 rows in 33.47ms; the live READ policy snapshot
took 4150.22ms. The current UI gates its entire resolutions panel on that remote
snapshot, and the native command pipe queues it behind analytics. Remove both
dependencies, retaining original operations through completion. Reuse the same
owner-authenticated pipe transport with fixed policy and recent-DNS lanes in the
same collector; no new service, general RPC, credential exposure or timeout retry.
Recent DNS requests are fixed read-only, current-account/endpoint scoped, latest
100 observations over the last 15 minutes with bounded search. Policy reads/actions
remain serialized separately; confirmation, fresh shared-profile checks and exact
mutation/readback guards remain unchanged. Recent data and its search/refresh stay
usable during policy reads/failures; actions remain disabled until current policy
validates the event profile. A genuine empty response differs from loading/error.
Use the existing themed loading dots in a centered translucent recent-panel layer
while its first read is pending, and clear independent policy progress feedback.
Respect reduced motion; navigation and already loaded recent data are not inert.
Remove the special 28px navigation Tailscale mark override: all category icon boxes
are centered 22px within the unchanged 40px hit targets. Preserve artwork/branding.

Stage 10 acceptance: reproduce held-policy/held-analytics blockage before fixing;
actual native transport proves recent rows, search and local controls complete while
both operations remain held; errors/profile/account isolation and graceful shutdown
pass; actual served loading state and equal icon bounds verified at desktop, narrow
and app-local 150% zoom; focused regressions/builds and READ-only live measurements;
commit/sync. Corrective release/deployment continues the owner's unfinished approved
delivery, with independent artifact verification and installed acceptance. No policy
write, Android deployment or unrelated refactoring. B12 stays open.

October 15 recovery authorization: the owner explicitly accepts reloading the
corrupted testing database and loss of its test observations. Replace only the
history SQLite database after graceful collector shutdown and confirmed process
exit; retain the consistent original recovery copy. Preserve runtime/provider
configuration, vault credentials, node/signer, resolver, updater preference and
retention choice. Verify new database integrity, actual ingestion and recent DNS
reads before resuming corrective release/deployment. This revises preservation
of old test observations only, not the remaining data/identity contracts.

### R27 — Safe bundled SQLite and recurring history integrity

The October 16 installed check reproduces corruption after an initially clean,
authorized test-history reload. Both shipped and development runtimes contain
SQLite 3.50.4. SQLite's upstream WAL-reset advisory confirms this is an affected
version; specific attribution of these files to that race remains unproven.
Ship a pinned official Windows amd64 SQLite runtime containing the fix, verified
against its published archive digest and recorded in the signed payload inventory.
Do not replace global Python/SQLite installations or weaken WAL/read-only views,
single-writer ownership, confirmation/identity guards or integrity checks. A frozen
product must reject an unexpected unsafe SQLite runtime before touching history.
Verify ABI/query/source compatibility, source/frozen lifecycle and complete real
cold acquisition followed by reopen/integrity checks using the fixed runtime.
Include a private representative replay above the observed failure size with
concurrent read-only snapshots; do not upload private captured facts as CI fixtures.
Test observations may be reloaded under the owner's explicit testing authorization;
runtime configuration, credentials, node/signer and resolver remain preserved.
An authorized empty-history reset also resets only the derived DNS/traffic import
cursors and runtime-status snapshot, so discarded intervals are not incorrectly
treated as imported. Preserve provider backoff state and other persistent settings;
do not use a database reset to bypass a provider rate limit.
Do not claim the corruption's cause fixed merely from a dependency version change.
R26's independently verified UI corrections remain intact; any subsequent corrective
release/deployment requires the same signed-artifact and installed acceptance gates.
This belongs to the existing ACTIVE Stage 10, not a new parallel stage.

Primary evidence: https://www.sqlite.org/wal.html#walreset and
https://www.sqlite.org/download.html. Use an immutable digest, not a latest URL.

### R28 — Session policy browsing and current public documentation

Opening or revisiting Control D must reuse the existing collector's in-memory
policy snapshot for the same exact account/provider/endpoint and READ credential.
Read once when no matching snapshot exists; Reload policy explicitly fetches again.
No TTL, timer-driven policy refresh, persistent cache, new service or write-token
read for browsing. A credential/binding change or failed fresh read must prevent
reuse of the previous snapshot. Returned snapshots must not share mutable state.
Label reused browsing policy as cached; it does not establish historical causality
or authorize a write. Prepare and Apply retain unconditional fresh policy/binding,
shared-impact, confirmation, one-use and post-write readback checks. Recent DNS
continues independently and its refresh button becomes an icon-only refresh control
with a visible tooltip, accessible name, keyboard activation, existing disabled
state and themed 36px-or-larger hit target. Assess other icon candidates, preserving
explicit labels on unfamiliar, ambiguous or destructive actions.

Refresh README screenshots from the actual current native-served assets, using
only clearly disclosed synthetic facts and no private accounts/paths/credentials.
Include current navigation, Recent DNS, connection/resolver, geography and activity
views with reproducible capture provenance. Correct the verified public release
reference (+14) and distinguish new source-only R28 behavior. Existing Stage 10
owns this bounded correction; B12 stays open. Verify cache reuse/explicit reload,
credential/provider isolation and fresh-write guards, native category revisits,
icon accessibility/layout at 100%, 150% app zoom and narrow width, screenshot
content and README links; commit/sync. No new release or deployment is implied.

The subsequent October 16 "install it" explicitly authorizes publishing the next
monotonic signed Windows release and installing R28 in place. Verify public
signatures, exact source and payload inventory before execution; preserve login,
Tailnet Lock signing ability, resolver, credentials and existing history. Verify
the installed identity, services, DNS and R28 browsing/refresh behavior. Do not
reset history or change provider policy. Existing Stage 10 owns this delivery;
broader B12 obligations remain unchanged.

### R32 — Responsive startup, background analytics and incident readability

October 16 user amendment within the existing ACTIVE Stage 10. Start on
Tailscale / Connection, matching the first category. Load Overview asynchronously
in the background, retain its completed/partial results when visiting device or
Control D pages, and reuse the matching scope on return. Navigation and usable
panels must not wait for an unrelated metric. Preserve exact snapshot revisions,
scope/generation isolation, visible progress and real terminal errors; do not
mask stalled/corrupt history with a timeout, empty result or perpetual overlay.
Investigate and correct the reported dashboard failure before acceptance.

Offline peers must not advertise TailDrop availability: show Offline without
an availability claim; unknown presence remains explicitly unconfirmed. Control
D Recent DNS and Profile policy should use the remaining viewport height, with
one appropriate content scroller rather than a fixed 480px table leaving unused
space. Keep headers/actions usable at 100%, app-local 150% and 560px minimum.
Display allow/bypass in accessible green and block in accessible red, alongside
explicit labels; redirect, failure and unknown remain distinct and neutral or
warning, never inferred to be allowed. Apply equivalent policy action styling.

Additional screenshot amendment: align the geography/map row to both content
edges. The user's clarification supersedes a fixed 3:1 split: keep the compact
map anchored top-right at a bounded width, while the country panel stretches
from the left content edge to the map. Remove the unused trailing column space;
stack at narrow sizes without enlarging the map vertically or adding filler.

Acceptance: reproduce and fix the actual loading failure; offline/unknown peer
fixtures; background read + navigation + return + scope change/error regression
workflow; native-served populated/empty DNS and policy layout at representative
sizes; label/contrast/readability review; focused backend/frontend checks and
production packaging build. Preserve VPN/DNS identity/settings, policy mutation
review and signing/update/rollback contracts. Implementation and commit/sync are
authorized; this amendment alone does not authorize another live installation.

October 16 subsequent user instruction "deploy" authorizes R32's normal signed
public release and in-place Windows installation, preserving identity, provider
settings, credentials, analytics history and automatic-update preferences. Verify
the exact public payload independently before installation and verify the actual
installed services, DNS continuity and dashboard afterward. No Android changes.

### R31 — Unified analytics preference and live connection inventory

October 16 user amendment, owned by the existing ACTIVE Stage 10: replace
per-source recording switches with one **Collect analytics** preference under
Tailscale / Preferences. Sources are selected by available integrations, not by
three independent user toggles. The existing compatible settings representation
may retain internal source flags, but the product must present one recording
decision. Preserve opted-out installations and existing credentials/bindings;
an enabled legacy configuration migrates to the unified source-selection model.
Disabling analytics stops new recording, not the VPN, resolver, Control D policy
management, current peer reads or access to retained history. Credentials must
never be inferred from the presence of a provider binding alone.

Remove the separate Devices navigation tab and enrich Connection's existing live
device table. Read from the local daemon independently of history collection:
device/owner, addresses, OS, reported presence, offline LastSeen, TailDrop
eligibility and reason, exit-node eligibility/selection, reported subnet routes,
tags, creation/key expiry where supplied and advertised SSH evidence. Preserve
tri-state/missing values and distinguish capabilities, eligibility and observed
reachability. Do not invent client versions, detailed OS versions, signing-node
roles, SSH enablement or expiry-disabled policy when local APIs omit them. The
admin API offers additional fields but no new tailnet credential or account
permission is assumed for this amendment.

Adapt navigation, queries and widgets to source availability: no GlassWire means
no irrelevant empty application/bandwidth widgets; no Control D credential/binding
means no irrelevant empty DNS widgets. Retained data keeps its views accessible
when a source is missing, paused or temporarily unavailable, with explicit stale/
recording-off/source-health state. Keep setup and management discoverable. Refresh
source availability on navigation/reload; do not cancel operations or discard
history when availability changes. Preserve independent query/management lanes,
the existing Tailscale/Portmaster theme, accessible icon/text controls and responsive
100%/150%/narrow layouts.

Acceptance: unified on/off and legacy migration, late provider/credential binding,
missing/stopped/recovered source and retained-history states; live peers while
recording is off; offline contact/capability/route/expiry privacy fixtures and real
read-only daemon boundary; native-served layout/navigation and responsiveness;
existing launcher restoration and installer/rollback contracts. User authorizes
publishing the complete next normal signed release after verification and explicitly
requires stopping before real local deployment. Build and independently verify the
public installer/assets before stopping; do not launch an installation approval.

October 16 subsequent user instruction “deploy” lifts that delivery hold for the
verified +19 installer. Perform the normal in-place local upgrade, verify live
identity/credentials/DNS/history/collector preservation and native restoration,
then restore the pre-hold automatic-installation preference. This authorizes
delivery of the completed R31 release, not unrelated product changes.

### R29 — Existing-window activation and dashboard geometry

Tray activation must restore the same minimized native window without a second
launcher, collector or error dialog. Preserve same-owner/path checks, ordinary
close/reopen, rapid-click serialization and the right-click menu. Read every local
Go overlay explicitly as UTF-8 so Windows ANSI code pages cannot change window
identity. Verify generated source Unicode, the real minimized-window activation
path, and no collector/settings/credential changes. The observed +15 overlay hash
matches CP1252 transcoding with Windows CRLF output, confirming this build defect.

October 16 normal-launch correction: the Start-menu/owning-user launcher must
also restore the matching minimized native window before collector discovery.
The existing window holds the analytics pipe; Windows pipe-busy error 231 is
not a startup failure in this case. Bind activation to current owner SID, exact
native executable and instance identity. Do not open another collector, send a
window-closed notification for a restored window, retry an occupied pipe or use
a timeout. Preserve the existing tray activation and first-launch paths.

Correct Bandwidth history geometry and remove unallocated grid holes after the
map's independent-height correction. Preserve the Portmaster-derived widgets,
Tailscale theme, source/unknown semantics, 560px minimum and 100%/150% app zoom.
Anchor the fix in measured native-served layouts with populated and empty states.
Document the actual Tailscale context contribution separately from GlassWire
traffic bytes and Control D DNS/answer geography. Do not invent packet metrics.
Existing Stage 10 owns this correction, verification and commit/sync. This bug
report does not independently authorize another public release or deployment.

### R30 — Tailscale-native activity and TailDrop history

The owner explicitly requests these features after the popup fix and authorizes
continued implementation/verification/commit/sync while away, stopping before
final deployment. The subsequent October 16 instruction, "lets deploy", explicitly
authorizes the normal signed public Windows release and local laptop upgrade of
the verified R29/R30 result, preserving identity, settings, history and rollback.
It does not authorize Android deployment or unrelated provider/device changes.

October 16 presence-semantics correction: an offline peer appearing in a status
snapshot is not device activity at that timestamp. Preserve starting snapshots
as provenance, but exclude them from the default Activity timeline with an
explicit "Include starting snapshots" option. Default activity shows actual
observed changes and observation gaps, never invented transitions before tracking.
Devices must distinguish daemon-reported presence from LastSeen (the core's
last control-plane contact, supplied only for offline peers). Show "Online now"
for online peers, the supplied last-seen timestamp for offline peers, or unknown
when absent/invalid. Never substitute the current snapshot timestamp for last
online contact. Re-reading unchanged offline state must not create an activity
entry. Verify offline baseline, repeated snapshot, true online/offline changes,
legacy records without LastSeen and native rendered labels/empty state.

Add opt-in Tailscale activity tracking to the existing owning-user collector,
independent of GlassWire and Control D. Use supported READ-only LocalAPI status,
IPN notification and custom resolver status interfaces. A cancellable Windows
named-pipe connection must settle its pending IO before handles/thread exit;
no visible subprocess, new service, scheduler or privileged API is needed.
Recover a lost subscription through a documented ten-second monitoring opportunity
or an explicit resume/wake; do not cancel healthy operations by elapsed time.

Persist only whitelisted metadata in the existing private history store and its
retention policy. No raw notifications, keys, login URLs, file contents or full
file paths. Track baseline and observed connection/reconnect, exit-node and
resolver/fallback/captive-portal state changes. Peer history records stable device
ID, display name, OS, reported online/offline/unknown state and observation time.
Online means control-plane presence, not ping/reachability or recent activity.
Only peers visible to this authenticated client are covered. Missing peers,
disconnected observation and first observation must not become fabricated offline
transitions or retrospective uptime. Profile changes isolate histories.

TailDrop records direction, filename basename, available peer ID, declared and
observed byte counts, source start time, observation times and reported result.
Outgoing Finished/Succeeded and incoming Done are explicit daemon evidence;
incoming Done means received by the daemon, not proof of local save. Disappearance
alone is unknown, not success. Empty/null updates retain their distinct meanings.
Retain completed events durably, de-duplicate replayed initial notifications and
keep gaps/unknown outcomes visible. Historical transfers before observation cannot
be reconstructed unless present in the daemon's current retained state.

Expose native-themed Tailscale tabs for Devices, Activity and TailDrop with live
source state, start/pause controls, bounded local history, time range and search.
No analytics-wide wait or Control D credential is needed. Retention and explicit
activity-history deletion apply to these facts, including replay suppression.
Keep existing tray/device settings and Tailscale/Control D group navigation.

Acceptance: real READ-only daemon subscription -> sanitized events -> durable
history -> native-served rendered peer/activity/transfer views; controlled real
protocol fixtures cover transfer completion/failure, duplicate/restart, source
gaps, profile switches and malformed/private inputs. Real local-daemon validation
must verify supported fields and current visible peers without manipulating VPN,
peer devices, files or provider policy. Clearly distinguish fixture transfers from
real transfers. Verify opt-in independence, graceful cancellation, retention/
deletion and restart; keyboard access, 560px minimum and 100%/150% app zoom.
Stage 10 remains the sole ACTIVE stage; R29 layout obligations remain required.

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
| 10 | Authorized release, rollout, updater proof and final reconciliation; remaining R18 | ACTIVE; R26/R27 corrective +14 delivery verified; existing B12 remains |

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
