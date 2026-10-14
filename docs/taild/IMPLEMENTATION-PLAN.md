# TailD staged execution

Sources of truth: [initial specification](SPECIFICATION.md) for R01–R07 and
[remaining-product specification](PRODUCT-SPECIFICATION.md) for R08–R18.
Stages 1–3 were authorized by the request to create the public TailD derivative,
inherit TailDNS and start Control D work. The October 8 request authorizes the
remaining specification. The subsequent instruction to start Stage 4 authorizes
its implementation, verification and commit. Stage 4 is now COMPLETE; Stages 5–10
remain NOT STARTED at Stage 4 closure. The subsequent explicit Stage 5 request
authorizes its implementation, verification and commit; Stage 5 is now COMPLETE
and Stages 6–10 remained NOT STARTED at that checkpoint. The October 13 request
to continue TailD authorizes remaining implementation through Stage 9. Stage 6
and Stage 7 are now COMPLETE. The reopened Stage 1 R02 promotion regression is
resolved and verified; Stages 8–9 are COMPLETE. The subsequent October 13
"go ahead", answering the explicit Stage 10 release/migration/updater question,
authorizes that delivery scope. Stage 10 is the single ACTIVE stage.

## Stage 1 — Public TailDNS derivative with automatic inheritance

Status: **COMPLETE**. Requirements: R01–R05.

Acceptance: public lineage/ancestry; isolated inherited workflows; tested real-Git
merge behavior; live TailDNS boundary and CI verification; preserved exact core
pin and inherited behavior; truthful README. Implement the smallest merge/check/
promotion workflow, not a second release system.

Satisfied: clean main clone at verified TailDNS 57c220e807b0d295c5946d8293bd3f636a4f85f5;
public repository created with Actions initially disabled; focused real-Git tests
pass for no-op, DNS/core inheritance, local preservation, dirty checkouts,
conflicts and newly inherited workflows. README repository identity is TailD;
inherited app-branding assertions remain TailDNS, with only README heading
assertion adapted to TailD. No app or DNS behavior changed.
Exact checked source: b6c2563ad7aa89011a90d10301b3b6167212597d.
Evidence: GitHub run 37588073660 SUCCESS, including real-Git merge/bundle/
concurrent-main regression tests, inherited version/branding/lifecycle/installer
contracts, Linux Android/native/shared DNS tests, unsigned APK compilation and
all five Windows CLI/daemon/resolver/tray/installer command compilations.
The live TailDNS boundary was already synchronized at 57c220e807b0d295c5946d8293bd3f636a4f85f5,
so promotion was correctly skipped. Actual GitHub write-job promotion awaits the
first real upstream update; equivalent bundle/fast-forward/race behavior was
verified with real Git repositories, not a fabricated upstream commit.
Remote main contains complete TailDNS ancestry and no other heads/release tags.
Only taild-checks and taild-inherit are active; inherited workflows are explicitly
disabled and default authority is read-only. No signing secrets or release exists.
October 13 regression: the first real candidate containing an inherited workflow
passed run 38382663145 but GITHUB_TOKEN could not promote that workflow file.
The exact checked candidate was manually fast-forwarded with the existing
workflow-capable login. Stage 1 was reopened after Stage 7 closure to repair
this existing R02 requirement, not to expand scope.
Resolved advancement blocker B02 (internal): the built-in token cannot update workflow
files. Existing authorized repository-admin access is available; resolve with
scoped automation authentication, not a broad personal login copied into CI.
Do not exclude inherited workflow source or create releases as a workaround.
No device/deployment verification is claimed. Tracked deferrals: none.

Repair implementation: a new write-enabled SSH deploy key is scoped only to
`Darkaxt/TailD` (key ID 166323174, public fingerprint
`SHA256:/g8EyVu+b7zAcrKynihwBTmivO+ytsFErKi5ecZNZ/g`). Its private part is in the
repository secret `TAILD_INHERITANCE_SSH_KEY`, only consumed by the isolated
promotion job; GITHUB_TOKEN is reduced to contents/actions read there. No personal
OAuth, Control D token, signing identity or another repository's key is copied.
The exact-bundle/parent/base/fast-forward checks and disabled-inherited-workflow
gate remain. A manual, default-off identity check writes a static workflow-comment
change to one unique temporary non-production ref, verifies it, deletes it and
checks main stayed unchanged. This is credential-boundary verification, not a
fabricated TailDNS update or release. Local real-Git and workflow-authority
contracts pass. Run 38418991496 at repair commit 485e15693c41bf3458043a5ac9aa4bfc134b39f0
passed the actual SSH workflow-file write/readback/deletion check. Temporary ref
taild-auth-check-38418991496-1 was independently confirmed absent, main remained
unchanged and inherited workflows remained disabled. TailDNS was already current
at c2116d244b05bf0e85c03e70a42d03678950c442; no new upstream merge is claimed.
The local private-key copy was deleted by reviewed cleanup after verification.
Remaining: none. Blockers: none. Tracked deferrals: none.

## Stage 2 — First read-only Control D data

Status: **COMPLETE**. Requirement: R06.

Acceptance: documented device/profile read and the verified CSV route; safe
credential/error handling and HTTP contract tests; at least one real account read
and DNS decision without policy changes. The organization-only documentation
label remains a provider-contract distinction, not an artificial rejection of
the personal-account read proved below. Use one direct command, not a provider layer.

Satisfied: GET-only device/profile inventory; UTC-bounded first-decision CSV;
authenticated region discovery; redirect refusal; sanitized HTTP/envelope errors;
raw-code/source preservation; non-overwriting local export outside the repo.
Focused real loopback HTTP and synthetic CSV tests passed, together with the
unchanged inheritance tests. Actual inventory read succeeded. Actual account
metadata showed no org ID and returned a region label, not a hostname. Vendor
dashboard source proved the region-to-host mapping. The actual development
command then discovered the region and retrieved one real CSV DNS decision with
the user's READ token. API writes, browser cookies and policy changes were absent.
Public evidence intentionally omits returned identities, queries, IPs and token.
Remaining: none for R06. Full API breadth and an installed analytics UI are not
claimed by this initial increment.
The user supplied a token and explicitly confirmed READ-only permissions. It is
held only in the execution session and will be supplied to the local command
through stdin, not arguments, logs, repository files or GitHub secrets.
Observed personal-account CSV availability is not a documented entitlement for
every account; future server denial remains an error, never a scope/session upgrade.
Blockers: none. Tracked deferrals: none.

## Stage 3 — Real Windows joined record and final reconciliation

Status: **COMPLETE**. Requirement: R07 and integrated R01–R07 reconciliation.

Acceptance: validated read-only application connection + network-byte source;
one real DNS/process/device joined export with honest provenance/confidence;
final checks and verified commits. No dashboard or broad telemetry framework.

Satisfied: AppControl field availability was checked live; missing network fields
are established, not assumed. A narrow GlassWire SQLite source and IPv4/path
decode were independently validated. The implemented on-demand reader queries
an explicit one-second database/UTC interval in read-only transactions including
WAL, preserves raw nullable metadata and provenance, rejects malformed identity/
byte data, and reports limits/unsupported families without invented addresses.
Actual Control D reads and the actual join CLI produced a private local export
with nonzero-byte application/destination records and real DNS candidates, plus
the laptop's live Running TailDNS identity and active matching Control D resolver.
Both source slices were untruncated. Ambiguous candidates, unmatched buckets,
unknown families/answers and source-snapshot/TTL/PID/socket limits remain explicit.
No duplicate byte allocation across candidate domains is performed.
Remaining: none for this initial joined-record increment. Exact implementation
commit: ae9a9e7ab57e147f0b558ac8359fdd6f5cd2b1ac. GitHub focused run
37657894730 SUCCESS verified the TailD contracts and inherited lightweight
version/branding/lifecycle/toolchain/Windows-installer contracts. Native source,
core pin and app identity are unchanged, so the earlier inherited native build
evidence remains applicable; no redundant Android build/device operation occurred.
Private real inputs and joined deliverable are retained in an ACL-restricted
local validation folder. Temporary validation helpers/reports were transactionally
removed, and the session-held token was cleared after the authorized reads.
The elevated inspection is recorded in [GLASSWIRE-READS.md](GLASSWIRE-READS.md);
the implementation and verification in [LOCAL-READER.md](LOCAL-READER.md).

Resolved access blocker B01: R07's real application connection/destination/network-byte
acceptance criterion previously had no accessible validated source. Live AppControl
MCP lacks those fields. GlassWire 3.10.1138 is running, but its service stats folders,
both candidate databases opened in SQLite read-only mode, and ACL inspection deny
access to the current process. No existing CSV/database was found in its scoped
user-side Local/Roaming app folders. No supported live third-party API was found
in the checked vendor guide; its documented Usage Table CSV export is a viable
data source, but no sample has been supplied yet.

Resolution: user supplies a Usage Table CSV with suitable application/host/byte
and time-window information, or authorizes a read-only elevated inspection to
establish whether local service data is usable. Elevated access is not assumed
to guarantee a usable/compatible schema. No ACL changes, service stop/restart,
firewall modification, private protocol bypass or UI operation was attempted.
On October 7 the user authorized elevated read-only inspection. A one-shot
helper opened both databases without ACL/service changes, then established
`traffic_stats` columns for application ID, remote host/port, timestamp, inbound
and outbound network bytes. A normal `mode=ro` transaction including WAL returned
one actual row with nonzero bytes. The schema-only immutable probe is not used
as live-row evidence. Application/address fields are binary and remain to be
validated before any adapter or joined-record claim. Subsequent bounded format
inspection independently matched the observed executable-path field and
little-endian IPv4 encoding plus remote port against Windows' own process/TCP
table. IPv6 and enum meanings are not established. These source counters are
application/destination/time-bucket metrics, not proven individual PID/socket
bytes. The source is an observed internal schema, not a stable third-party API.
Initial database permission
access is therefore no longer an external blocker. The previously remaining
extraction, source integration and actual joined-record proof have now passed.
The first multi-row live read exposed nullable threat metadata; a reproducing
SQLite regression test and focused correction preserve null while retaining
strict network-byte/identity checks. The joined CLI's output and private inputs
contain no API token or private node key. The validation folder has a private
user/SYSTEM/Administrators ACL; no source permission/service/policy was changed.
Fresh focused verification of all TailD contracts passed on the current source,
including existing Control D/inheritance contracts and new reader/join behavior.
Fresh GitHub settings and captured TailDNS/main/core pin were checked unchanged.
Blockers: none.
Tracked deferrals: none.

## Initial-increment reconciliation

R01–R05: satisfied with live repository/settings and exact inherited-build proof.
R06: satisfied with focused contracts plus actual authenticated inventory and
the development command's real personal-account DNS-decision read. Candidate
97d2c677c7ce1b1b0683834c3167db4f84bdedbe passed GitHub focused run 37592262745.
R07: satisfied by real read-only extraction/integration/joined export with actual
device/endpoint context, explicit provenance/ambiguity/byte limitations and fresh
focused/local/GitHub verification of the exact implementation commit above.
R01–R07 initial increment: COMPLETE. Blockers: none. Tracked deferrals: none.
This is not completion of a full analytics product, API breadth, dashboard,
native UI integration, IPv6 decode or continuous collection; those are not
required acceptance criteria of this explicitly bounded initial increment.
No TailD release/deployment occurred. No Control D write request was made.

## Remaining-product stages — specification recorded 2026-10-08

The following stages are planned work, not a claim of implemented components.
Use the [Portmaster source map](PORTMASTER-DESIGN.md) for layout and metrics
traceability. Do not begin a later stage while another stage is ACTIVE.
At implementation start, record the actual candidate revision and focused
verification evidence; do not reuse prototype proof for changed production code.

### Stage 4 — Incremental ingestion, durable history and first local query

Status: **COMPLETE**. Requirements: R09a–c and R14a; preserve R01–R07.

Objective: close the narrow real source -> persisted history -> filtered query
workflow before building the broader analytics runtime or desktop.

Acceptance criteria:

- Verified GlassWire source discovery, one-second selection, database generations,
  read-only WAL access, schema/IPv6 compatibility and unknown-family preservation.
- Transactional facts/checkpoints; correction-aware traffic replay; Control D
  bounded slices, equal-event multiset handling and honest completeness/gaps.
- Versioned private SQLite history, exact byte integers, retention/deletion and
  local query; no source writes, ACL relaxation or service operations.
- Focused crash/replay/rotation/mutation/truncation/late-arrival/retention/migration
  tests and a real persisted-read/restart/replay workflow with conserved totals.

Satisfied, criterion by criterion:

1. Live GlassWire 3.10.1138 service/catalog discovery verified UTF-8 BLOB leaf
   filenames below `stats`, scale-1 selection, two distinct physical daily
   generations and WAL-inclusive read transactions. IPv6 field 3 network-order
   bytes matched an independently known TCP DNS peer/port and Windows executable
   evidence. Malformed known encodings fail closed; unknown families retain bytes.
2. Facts/checkpoints commit atomically; traffic corrections replace canonical
   counters. Bounded DNS multiset/subdivision/late-arrival and gap contracts pass.
   Two live reads of 2,098 completed-window rowids were stable, not proof of universal
   finalization. Conservative retained-horizon replay does not assume immutability.
   Source-retention gaps and endpoint/window-specific coverage are regression-tested.
3. Private versioned SQLite, exact counters/JSON, retention/deletion suppression
   and filtered local queries pass. Live source connections are read-only; no
   source writes/checkpoints, ACL changes, service operations or provider writes.
4. Focused subprocess crash, migration/rollback, WAL, replacement/midnight/rowid
   reuse, mutation, truncation, late-arrival, retention and privacy checks pass.
   Real source -> owned history -> filtered query -> close/reopen/replay conserved
   all 2,550 buckets and exact totals; a fresh unelevated process confirmed durable
   totals/coverage. All 113 retained authorized Control D decisions remain present;
   their earlier import/restart/replay proof is retained, not a new API-read claim.

See [LOCAL-HISTORY.md](LOCAL-HISTORY.md) and [GLASSWIRE-READS.md](GLASSWIRE-READS.md)
for evidence and the bounded internal-source compatibility guarantee.
Remaining: none for Stage 4. Continuous runtime, production query/metrics and
packaging are explicitly assigned to later stages, not claimed here.

Historical blocker B02 (external): R09a/R09b and the first/fourth Stage 4 criteria require
fresh GlassWire source access. Unelevated SQLite read is denied. Both authorized
one-shot RunAs attempts were canceled at UAC before the helper ran. Resolve with
an approved one-shot read-only elevated inspection, then finalize the observed
source contract and perform actual traffic persistence/replay verification.
Resolution: the user returned and approved one-shot elevations on October 8.
Fresh source inspection, contract corrections, independent IPv6 validation and
the actual persisted traffic/restart/replay acceptance workflow passed. B02 is
resolved. No source ACL/service/VPN changes occurred. Later stages were not started.
Blockers: none.
Tracked deferrals: none.
Dependency: completed Stages 1–3.

### Stage 5 — Context-aware correlation and metrics/query vertical slice

Status: **COMPLETE**. Requirements: R10, R11a–b, R08 metrics design.

Objective: query correct, provenance-bearing summaries from actual stored facts.

Acceptance criteria:

- Versioned candidate links, historical context boundaries and endpoint/device
  ambiguity; missing event/TTL/PID data remains explicitly unproven.
- Every required metric dictionary entry, units, denominator, unknown/coverage
  states, exact counters, UTC chart boundaries and byte-conserving drill-downs.
- Allowlisted typed filtering/grouping/ordering/batching, stable pagination and
  consistent revisions; no raw SQL exposure or joins multiplying byte counters.
- Real stored traffic + Control D -> summary/chart/query result, plus focused
  ambiguity/provider-change/gap/injection/large-counter/correction verification.

Satisfied, criterion by criterion:

1. Schema-v4 whitelisted observed snapshots and versioned virtual candidate links
   enforce capture/change/gap boundaries, same-endpoint answer/IP/preceding-time
   matching and explicit historical-binding uncertainty. Fixture verification
   covers shared endpoints/IPs, duplicate/identical/out-of-order decisions,
   provider/account/exit/portal changes, conflicting captures and missing context.
   Real unelevated local READ capture verifies current configuration/identity;
   old traffic remains unbound. TTL/PID/socket and resolver-event routes are not invented.
2. All R11a entries have tested byte/count domains, versions, scope and coverage:
   exact bytes, partial/null-rate UTC bins, observed application identities,
   conserved rankings, canonical DNS counts/questions, unknown-safe outcome
   denominator, correlation partitions/inferred domains, single-answer provider
   geography/ASN and operational health. Numeric outcome meanings remain
   unverified and therefore unknown, with a null block rate, not a fabricated one.
3. Typed field/operator/value/group/order allowlists, literal search, fixed bound
   SQL scopes, bounded batching and revision-bound pagination pass. A real
   concurrent WAL commit cannot mix a batch's read revision. Stale/malformed
   cursors fail explicitly. Compound DNS predicates require one candidate, and
   never multiply traffic bytes. Context/policy snapshot query contracts pass;
   actual policy acquisition belongs to Stage 6 and remains not-collected.
4. The real private-history six-result summary/chart/group/detail/DNS/policy
   batch conserves 2,550 buckets, 113 DNS events and 67,680,901 observed bytes.
   A fresh process independently verifies its private export and shared revision.
   Focused ambiguity/change/gap/injection/large-counter/correction/deletion and
   migration checks plus all TailD local contracts pass. No current binding was
   applied to historical traffic and no incomplete hourly bin became zero traffic.

Portmaster source-to-query/chart traceability and exact evidence are recorded in
[METRICS-QUERY.md](METRICS-QUERY.md). No Portmaster runtime or source was copied.
Remaining: none for Stage 5. No mutating live resolver-change test was authorized;
the specification explicitly makes that test conditional on live-change authority.
Blockers: none. Tracked deferrals: none. Dependency: Stage 4 COMPLETE.

### Stage 6 — Remaining Control D READ coverage and credentials

Status: **COMPLETE**. Requirements: R12 and R14b; maintain R14a safeguards.

Objective: expose policy context and capabilities for the account without writes.

Acceptance criteria:

- Endpoint/client/profile associations and policy categories (filters, services,
  rules/folders, restrictions), each with a verified read route or an evidence-
  backed unavailable capability. No guessed routes or silent category omissions.
- Timestamped policy snapshots, activity reason/answer metadata and a maintained
  documentation/account/scope/pagination/rate-limit capability matrix.
- Optional user-bound credential persistence, secure replacement/removal and
  sanitized redirect/denial/rate-limit/malformed-response handling.
- Actual account reads for every available category; fixtures and captured
  provider evidence for unavailable categories; zero provider mutations.

Satisfied, criterion by criterion:

1. Verified vendor-owned GET contracts and real selected endpoint/profile reads
   cover native/external filters, services, rules, folders, options, restriction
   catalog/enabled state and default rule. The dedicated regional client read
   succeeds despite the legacy inventory field being absent; no guessed route
   or artificial unavailable category is substituted.
2. Private point snapshots persist/reopen/query through the existing schema-v4
   typed policy surface. Every capability records source/route/scope/shape/time,
   pagination and retention uncertainty and rate-limit behavior. Live account
   CSV decisions retain reason/answer/profile/client/geography and unknown fields;
   the bounded account sample is explicitly truncated and never host-attributed.
3. Optional current-user Windows Credential Manager round-trip, replacement and
   removal pass natively with synthetic credentials. Hidden/vault input integrates
   with GET-only capture and private history. Echo fallback, secret exports,
   redirects, malformed data, scope/path injection, denial and 429 handling pass.
   The existing READ token was used only transiently for live validation, not
   installed in the product vault; no new token/re-entry was needed.
4. Live reads passed for all available categories. Real capture -> private store
   -> close/reopen -> exact typed query passed. All current TailD Python contracts
   passed (including Windows native credential and actual SQLite/HTTP boundaries).
   No provider writes, installed-client operations or background installation.

Evidence and commands: [POLICY-READS.md](POLICY-READS.md). Remaining: none for
Stage 6. Blockers: none. Tracked deferrals: none. The inherited native source and
core pin were not changed by this stage. A separate existing inheritance run's
Go checksum-service HTTP/2 error was diagnosed, not hidden by a source patch;
the normal trusted workflow was re-dispatched as run 38382663145 and is tracked
through completion before dependent integration. It does not replace any failed
candidate or change this stage's verified analytics source.
Dependency: Stage 5 COMPLETE; history/context must be integrated into snapshots.

### Stage 7 — Opt-in continuous runtime and privilege boundary

Status: **COMPLETE**. Requirements: R13 and remaining R14a–d.

Objective: safely acquire and query data without manual developer commands.

Acceptance criteria:

- Unelevated owning-user collector/UI and minimally privileged read-only
  GlassWire reader with authenticated allowlisted IPC; no source ACL changes.
- Explicit opt-in, serialized/coalesced acquisition cadence, pause/resume/stop,
  source incompatibility/staleness states and catch-up without timed cancellation.
- Private history/credential isolation, authorized local query access, resource
  bounds, backpressure, disk-full behavior and redacted diagnostics.
- Authorized real lifecycle tests for window closure and restart; live provider
  READ plus source/provider outage/recovery contracts; unauthorized-account/IPC/origin tests;
  unchanged VPN/DNS/firewall and no duplicate or visible-console helpers.

User-authorized October 13 amendment: skip forced live sleep/wake, network loss
and GlassWire stop/update tests because no isolated Windows host is available.
Native wiring and deterministic availability/generation contracts remain required;
the waived physical/live scenarios stay explicitly untested. Natural user reports
may trigger later bug fixes. This is not a required-work deferral or simulated pass.

Verified integrated evidence and final criterion reconciliation are in
[CONTINUOUS-RUNTIME.md](CONTINUOUS-RUNTIME.md). The protected real-source ->
unelevated collector -> authenticated local query/restart workflow passes; native
ownership, bounded lifecycle, HTTP authorization, deletion replay and SQLite FULL
contracts pass. The actual Portmaster-derived/Tailscale-coloured control window,
source-build launcher, actual other non-admin account and live Control D runtime
are now verified. Actual served CSP, literal source text, native lifecycle and
current runtime/history/query contracts pass. Every criterion above is satisfied
under the explicit user waiver; no simulated physical test is claimed.
Remaining: none. Blockers: none. The earlier R02 promotion regression is now
resolved and Stage 8 is ACTIVE.
Tracked deferrals: none.
Dependency: Stage 6 COMPLETE; stages 4–6 data contracts remain enforced.
Installing a service for live validation requires applicable live-test authority;
this documentation request does not install or schedule one.

### Stage 8 — Portmaster-derived desktop analytics

Status: **COMPLETE**. Requirements: R08 layout, R15, R16; preserve R11/R14.

Objective: close overview -> application -> activity -> evidence/export in a
packaged local desktop surface, not a collection of disconnected mockups.

Acceptance criteria:

- Persistent navigation and shared device/time/filter scope; overview cards,
  bandwidth charts/rankings, application list/details, typed activity explorer,
  Control D policy/capability view, source health and settings.
- Exact metric/query revision shared across cards, charts, pagination and exports;
  ambiguity/unknowns/gaps visible, with no unsupported Portmaster firewall cards.
- Saved local queries, compound filters, focused-row-preserving refresh and
  evidence details; private JSON/CSV export, formula safety and exact integers.
- Actual-source desktop drill-down/export and focused keyboard/accessibility/
  scaling/security review; pinned source-map traceability and reuse notices.
- Current Portmaster layout/widget retrieval before presentation work; maximum
  practical literal reuse with per-component adaptation/replacement reasons and
  license/source notices. Real charts, ranked consumers, filters and drill-downs
  must not be replaced with text blocks or a generic card grid. Actual served
  assets must satisfy the design map's responsive/screenshot contract.

Satisfied: every criterion above, reconciled in [DESKTOP-ANALYTICS.md](DESKTOP-ANALYTICS.md).
Actual-source drill-down and private export reconcile 1,773 facts/20,378,798 bytes.
Typed compound filters, saved scoped/grouped queries after restart, stale-revision
rejection, anchored selected-row/focus refresh, exact >2^53 bytes and private native
JSON/CSV save pass. Current Portmaster-derived charts/rankings/explorer meet the
responsive/Tailscale-theme contract. User-accepted app-local 150% zoom measures
949×574 CSS px/DPR 1.5, keyboard/overflow verified and Windows unchanged. Existing
collection lifecycle and source-build launcher pass on the same served assets.
Physical outage tests remain untested under the explicit earlier waiver.
Remaining: none. Blockers: none.
Tracked deferrals: none.
Dependency: Stage 7 COMPLETE; do not substitute mock-only UI for integration.

### Stage 9 — Production packaging and local release-readiness

Status: **COMPLETE**. Requirements: R17 and R18 pre-delivery reconciliation.

Objective: produce and verify an installable product with no developer toolchain
requirement, while preserving the inherited in-place connectivity installation.

Acceptance criteria:

- Complete local desktop/analytics/reader payload, exact inherited core pin,
  TailD-owned minimal integration, license inventory and reproducible provenance.
- Installer/upgrade/uninstall/rollback tested in isolated Windows; service/node/
  Tailnet Lock state preserved; no second VPN service or permanent versions tree.
- Isolated credential-free checks and reviewed signing/release workflow design;
  pinned-key manifest/tamper/replay/version contracts; truthful signature labels.
- Current R01–R17 and pre-delivery R18 evidence reconciliation, clean production
  build, offline launch and packaged-runtime/installer acceptance. No publication,
  updater activation or personal-device rollout merely to close this stage.

Satisfied: all four criteria, reconciled in [PACKAGING.md](PACKAGING.md). Clean
production source ca73b3094ddf03cc44c9be2afdd48da138daf202 produces the locally
production-key-signed 1.105.0+1 payload and reviewed normal Inno installer. Actual
Windows run 38450846929 passes installer/SCM upgrade, external rollback, anti-replay,
tamper, history retention/removal and synthetic account-state preservation. Actual
hook-free Release/frozen-collector offline Overview -> Settings -> normal close
passes; independent installer extraction verifies all signed payload hashes.
Collected notices/provenance and the credential-isolated signing/release design
are recorded. Existing R01–R16 evidence remains applicable to unchanged product
paths. No live authenticated migration, publication or updater is claimed.
Resolved B09 (internal): production payload/isolated recovery/offline acceptance
previously lacked evidence. The integrated checks above resolve it; no Debug
host/component test is presented as installer acceptance.
Remaining: none. Blockers: none. Tracked deferrals: none.
Dependency: Stage 8 COMPLETE. Release and live rollout belong to Stage 10 by
explicit scope separation, not an unmet Stage 9 criterion hidden as a deferral.

### Stage 10 — Authorized release, rollout and updater verification

Status: **ACTIVE**. Requirement: remaining R18, preserving R01–R17.

Objective: deliver the verified Windows product and prove its independent update
channel without redirecting existing TailDNS installations implicitly.

Acceptance criteria:

- Explicit delivery/migration authority, normal signed GitHub release and
  independent download/source/hash/signature/version/architecture/payload proof.
- Approved in-place rollout preserving authentication, addresses, Tailnet Lock
  signing and DNS/GUI behavior; actual product collection/drill-down/export proof.
- Authorized TailD updater activation and real update/rollback, with negative
  replay/tamper/downgrade/interruption tests and no source/account data loss.
- R01–R18 final reconciliation, no required blockers/deferrals, documented source
  compatibility and upstream ownership; existing maintenance tasks unchanged.

Satisfied: explicit delivery/migration/updater authority; normal signed public
release 1.105.0+1 at bde37693a2575b7bd3d5708d18a161a798cffe32; independent public
download and full extracted-payload verification; actual authorized Beacon migration
with node/addresses/signer/service/DNS continuity and public/MagicDNS resolution.
Remaining: production analytics workflow, real updater/recovery verification,
the October 14 left-click desktop/focus and preserved right-click-menu clarification,
then final reconciliation. These remain internal advancement blockers, not deferrals.
Resolved B10 (external): the October 13 explicit "go ahead" authorizes public
release, active Windows replacement and TailD updater activation. No synthetic
Stage 9 result substitutes for the required real production checks.
Resolved B11 (internal): the complete build, isolated installer matrix
and protected payload/installer signing passed run 38463490065. Current-source
0472970 passed build/contracts/payload signing in run 38465087871, but the added
fresh-host full-product migration-refusal check observed exit 0 without an
authenticated baseline. Run 38466700479 captured the cause: connectivity activation
correctly failed; Inno had already committed its framework, ignored the post-install
exception for exit reporting and retained uninstaller/registration after payload
recovery. The correction binds success to full transaction completion and uses
the normal uninstaller after confirmed first-migration core recovery. Signed
retained-member checks support interrupted uninstall without deleting history or
unmigrating twice. Reproducing recovery contracts and the actual full-product
fresh-host correction pass run 38468405916 at bde3769. The same signed candidate
passed actual hook-free Overview -> Settings -> normal shutdown and reviewed
rendering; an earlier invalidated UIA read remains a failed observation, not evidence
of a production app defect. The public normal release was independently downloaded,
its installer digest and all 414 extracted signed members verified, and Beacon
migrated through the elevation gate with fresh private continuity evidence.
Advancement blocker B12 (internal): live installed collection/restart/correction,
reconciled desktop drill-down/export, clarified tray activation and actual signed
channel update/rollback still require their complete workflows. Resolve them and
the final R01–R18 reconciliation before Stage 10 completion. Tracked deferrals: none.
The tray candidate 691e4f2 passed full production/signing run 38472355738 but was
not published: installed collection exposed a separate diagnostic-file sharing
conflict incorrectly disabling ingestion. An actual Windows deny-delete observer
reproduces it; status publication now has separate API-visible health and cannot
set the facts/checkpoint write-error state. Focused regression and source acquisition
pass; the other native runtime checks apply, with the HTTP negative check passing
individually after a host TCP abort in the combined diagnostic run. Current update
finish also stops reapplying the immutable migration's update preference to later
updates; a reproducing contract verifies current preference ownership. These
corrections require the current signed payload and live workflow verification.
Dependency: Stage 9 COMPLETE and explicit publication/deployment authorization.

October 14 B12 update: native drill-down and saved JSON now reconcile the same
203 production facts / 20,684,627 bytes at revision 137 (different display ordering
and equivalent UTC bounds are retained in the export). Installed restart retained
opt-ins/history. The empty recent view is verified against retained traffic ending
October 12, not a plotting failure. The user requests an ingestion notice and the
inherited application icon. A separate real navigation/close stall traced to the
shared source/query queue: after pausing at a committed boundary, catalog took
0.164 s and recent summary 0.009 s. Resolve read-only query/lifecycle isolation,
actual progress notice and icon in this single ACTIVE stage; revalidate their
integrated native workflow before the next signed release. Ingestion is temporarily
paused for diagnosis; VPN/source services and saved opt-in remain unchanged.

The integrated correction now passes the actual native WebView2 workflow: a held
GlassWire source read does not block Overview/Applications/Activity/Health navigation
or ordinary OS Close, enabled collection survives Close and reopening retains its
opt-in. The served themed notice displays its real read interval/committed-read
count and the empty-scope explanation. Revision-bound read-only SQLite views cannot
write and see committed facts during an uncommitted writer transaction. Native
window icon presence and extracted executable pixels match the inherited original.
Type checking, production Angular build and native Debug build pass. Current-task
Windows runtime contracts pass except one combined-run HTTP denial observation
aborted with 10053; the unchanged denial test passes individually. Do not describe
the combined run as a zero-failure result. Physical lifecycle waivers are unchanged.
These are local native/SQLite proofs, not an installed correction or Stage 10 closure.
The earlier signed +2 candidate at 02b6825 is superseded and must not be published.
Next: sign the current coherent correction, independently verify its complete
release payload, and prove installed update/tray/recovery and real collection
continuity. Refactoring assessment: no optional consolidation; the native pipe
serializes read callers, the collector remains the sole SQLite writer,
and diagnostic monitoring never acquires data or changes the displayed revision.

Latest Stage 10 checkpoint, October 14: normal release **1.105.0+2** at
456af1ee493461b7f1ed88cab955d62ed4078db0 passed signing/complete-package matrix
run 38482124246 and independent public download/extraction: installer SHA-256
98dc6ddf3d1abca0c5c42c0574030edde4bc09992fb71109356ff9943349f6dc,
114,056,037 bytes, all 415 signed payload members verified. The actual running
service dispatched the signed updater and completed installation; fresh continuity
checks preserved node/addresses/Tailnet Lock signer/DNS preferences and update
preferences, with public/MagicDNS resolution and installed-package verification.
Actual tray left activation launched the owning unelevated desktop and collector.
These supersede the earlier pending +2 publication/update notes, not the remaining
rollback/recovery, repeated focus/minimized restore/right-menu or final acceptance.
Automatic unattended collector resumption after the update is not yet proven;
the subsequent actual tray launch is not evidence of that separate requirement.

User correction: Control D is the primary integration; source acquisition must
run independently in parallel, not wait for a GlassWire backlog. R13/R18 now
explicitly preserve one SQLite writer while giving each source its own serialized
acquisition loop. GlassWire starts every pass with recent traffic and then advances
a saved, bounded newest-first backfill. No history cutoff, retention or default
chart-range change is authorized. The former shared-worker source design was an
internal advancement blocker for this correction, not a credential failure.

The integrated source correction is verified on Windows: either held source lets
the other read and commit through the sole owning writer; refresh coalesces without
duplicate reads; pause is responsive and prevents unadmitted catalog reads;
pause/resume invalidates the old pass and starts a fresh recent-data opportunity;
shutdown settles the in-flight reads/commits and joins both threads. Real SQLite
continuation survives restart, recent time advances first and replay conserves
traffic totals. Provider denial/recovery and persisted Retry-After, write failure,
read-only views, deletion/retention and the known-file uninstall check remain
verified. The same concurrency contracts run in hosted Linux CI as dispatcher
tests, separately from actual Windows owner/token/native-pipe verification.

The current source also passes the actual isolated native WebView2 workflow:
controls/autosave, ingestion notice, navigation/ordinary Close during held source
IO, reopen with opt-in intact, explicit stop, CSP/injection and icon presence.
This is source-build integration using synthetic SQLite records, not a packaged
or installed Control D correction. Source/runtime and UI validation leave the
installed 1.105.0+2, its real history, VPN, credentials and source services untouched.
The user has expressly asked to stop before the next deployment. Further package
verification may proceed, but installed validation waits for that boundary to be
lifted. B12 remains open for the installed correction and the other enumerated
real workflows/final R01–R18 reconciliation; Stage 10 remains ACTIVE and is not
declared complete. Tracked deferrals: none. Assessment: the separate acquisition
threads serve this demonstrated requirement; no new service, task, framework,
consolidation stage or optional refactoring is introduced.

Pre-deployment candidate checkpoint: source
0a76e1dd917995aa9a4ce0bf2d47315c144544a2 passed hosted check run 38488989232 and
the complete signed candidate workflow 38489010515. Publication was disabled;
the publish job is SKIPPED. The workflow includes actual isolated
install/upgrade/rollback/uninstall and fresh-host complete-product refusal/recovery
without an authenticated baseline. Independent downloaded/extracted installer
verification matches all 415 signed payload members and the pinned core.
Candidate **1.105.0+3** installer SHA-256:
38ea300ac60284dac8dbec346f3cc33ea33584b43ef76f9a8cb33cffd3094d52,
114,063,057 bytes; package-manifest SHA-256:
cf694e3856c715f5ba425ffae8bf5196e09734f70bf17869cc8afa6e31444248.
This is the pinned Ed25519 project identity, not Authenticode signing.

A separately launched, unelevated frozen candidate proves the real READ boundary
without deployment: hold synthetic GlassWire catalog discovery on its actual
protected named pipe first, then enable Control D with the existing owning-user
vault credential passed only in memory. The successful provider run commits while
the gate remains held, 0.464 seconds from provider configure to observed commit.
The response window is empty; this proves a successful source read, not observed
DNS activity or a new host-to-endpoint binding. Cooperative pause/shutdown exits
cleanly. Initial diagnostic observer predicates were corrected and retained as
invalid observations: an expiry gap is not a successful provider commit, and an
older disabled diagnostic-file snapshot is not a failed configure receipt.
The final gate-first proof requires a complete/truncated provider run and the
authenticated enabled receipt; no inferred ordering from simultaneous enablement.

The verified candidate assets/payload and sanitized reports are retained locally
for the next approved delivery. Expendable downloads/extraction, test histories
and WebView caches are removed through exact reviewed cleanup; credentials,
installed history and existing recovery payloads are preserved. Installed Beacon
is freshly confirmed running **1.105.0-taild.2**, and the public normal release
remains **1.105.0+2**. Candidate +3 is neither published nor deployed. The latest
user instruction at that checkpoint held the next deployment. The subsequent
October 14 "You can deploy now" lifts that hold. The +3 payload, inherited core
manifest, release envelope and installer digest were freshly reverified against
the pinned production key; the installed +2 baseline was captured privately in
`D:/Tools/taild-stage10-validation-20261013/live-update-3/before.json`. The existing
rollback-protected in-place installer is submitted once through the elevation
gate (request `44f7aba427944128a5308e94aace3a62`). Submission is not deployment
success. That request subsequently completed with administrator token, installer
exit 0 and complete package/continuity verification. Installed version is
**1.105.0-taild.3**. Node, addresses, Tailnet Lock signer, service path, current
update preference and DNS settings are preserved; public and own MagicDNS resolve.
Both services run. The unelevated `TailD.Background.exe` resumed automatically in
the owning user's session without dashboard activation, retained both opt-ins,
and its authenticated pipe reports committed reads from both independent sources
with no data-write error. Private `after-3.json`, `collector-after.json` and
`collector-acquisition.json` retain the actual evidence alongside the baseline.
The observed current GlassWire interval preceded its older-history read. This
closes installed correction/automatic collector-resumption proof for this manual
update, not all updater/session lifecycle paths. Stage 10 remains ACTIVE.

Normal release `windows-v1.105.0+3` is now published at the exact signed source
`0a76e1dd917995aa9a4ce0bf2d47315c144544a2`, not the later documentation/test commit.
Independent public download verifies both pinned signatures, the package manifest
digest and the complete 114,063,057-byte installer SHA-256
`38ea300ac60284dac8dbec346f3cc33ea33584b43ef76f9a8cb33cffd3094d52`.
Private `public-release-verification.json` records this evidence. No Android
release/device change occurred.

Installer cleanup transaction `cede28bad94ea885b1991a2f6d4a1b32` reviewed only
the exact Inno residual `C:/Users/darka/AppData/Local/Temp/is-BTSGEG2S2C.tmp` and
its empty `{app}` child. Apply reports both directories locked, with zero files
or payload bytes remaining. Current process inspection identifies the working
directory of the running tray child as that `{app}` path. Preserve the valid
partial ticket `6f5c233c785beeaf52ca048ecc6eedbf2ce213d0bbff386a891d5becc2300da4`
until those actual consumers exit; do not force-stop the working tray for cleanup
or claim the directories were removed. This is a concrete installer-lifecycle
finding for B12 reconciliation, not a connectivity or acquisition failure.

B12 still owns integrated collection/drill-down/export continuity, actual rollback
and restoration, unattended service-update collector resume, open-window update handoff, repeated
tray focus/minimized restore/right-click controls and final R01–R18 reconciliation.
The service's signed update path is verified; the standalone `tailscale update`
entrypoint still inherits the upstream updater and needs reconciliation with R18
before any claim that all update entrypoints use the project channel. Do not run
that command on Beacon as a diagnostic. These remain identified current-stage
advancement blockers, not unnamed deferrals or passed acceptance. This checkpoint
finishes the independently verified collector correction up to the requested
pre-deployment stop, not the overall Stage 10 outcome.

## Stage 5 execution — 2026-10-08

Authorization: already_authorized by the explicit request to start Stage 5.
Stage 5 was the single ACTIVE stage and is now COMPLETE. Execution sequence:
observed context and revision-bound candidate links -> real stored-data summary,
chart and filtered detail -> complete typed query/metrics contracts and focused
edge-case checks -> real private-history reconciliation -> final verification/commit.
Use [METRICS-QUERY.md](METRICS-QUERY.md) for the concrete contract and R08/R10/R11
traceability. No later stage, elevated GlassWire read, provider write, installed
client change or delivery is authorized or needed for this stored-data workflow.
Final verification: all TailD Python contracts passed, including the actual
SQLite concurrent-commit and migrated-history boundaries. Current local READ
capture and private stored-data batch/export verification passed. No Gradle/native
build was required: inherited app/core source, pin and workflows are unchanged.

## Remaining-product reconciliation at specification creation

Stages 1–3: COMPLETE for their initial scope. Stages 4–10: NOT STARTED.
No ACTIVE implementation stage, no currently established implementation blocker
and no tracked deferral. The remaining-product specification is documented;
the remaining product is not implemented, integrated, packaged or delivered.

## Stage 4 execution reconciliation — 2026-10-08

Stages 1–4 are COMPLETE for their assigned scope. B02 is resolved and every
Stage 4 acceptance criterion above is verified. Stages 5–10 remain NOT STARTED.
There is no ACTIVE stage, unresolved Stage 4 blocker or tracked deferral. This work has not been
released, deployed or represented as a completed analytics product.

## Stage 5 final reconciliation — 2026-10-08

Stages 1–5 are COMPLETE for their assigned scope. Stage 5 has no remaining
acceptance criterion, blocker or tracked deferral. Stages 6–10 remain NOT STARTED;
there is no ACTIVE stage. R10/R11 and the R08 metrics boundary are reconciled
above; the complete R01–R18 product is not declared complete. No provider policy
acquisition, credential recovery, installed runtime/UI, release or deployment
is claimed. Verified changes are committed locally, not pushed or published.

## Stage 6 execution — 2026-10-13

Authorization: already_authorized by the request to continue TailD. Stage 6 was
the single ACTIVE stage and is now COMPLETE. Reuse the GET-only HTTP boundary, private schema-v4
snapshots and existing typed policy queries. First prove secure credential entry
-> explicit endpoint/profile selection -> verified policy reads -> timestamped
private snapshot -> existing query. Then close remaining capability/error/unknown
contracts and real-account verification. Never recover a transcript credential
for installation in the product vault. The user reminded us that the existing
READ token is already supplied: bounded on-demand validation can reuse it solely
in process memory, without persistence, argument/log exposure or scope changes.
Provider policies, source services, installed clients and background tasks stay
unchanged. Stage 7 does not start before Stage 6 closes or is genuinely parked.

## Stage 7 execution — 2026-10-13

Stage 7 is the single ACTIVE stage. First prove an unelevated owning-user
collector -> authenticated, fixed-schema read-only GlassWire pipe -> private
history -> existing query, with deterministic start/pause/resume/stop and no
overlapping source reads. Then verify opt-in acquisition cadence, scoped source
errors/catch-up, credentials and IPC ownership, interruption/disk-full behavior
and the required live lifecycle matrix. No permanent service/startup task, client
replacement, provider write, updater change or release is implied. A privileged
reader exists only to satisfy the verified source ACL boundary; it receives no
provider credential or arbitrary SQL/path/shell operation.

The actual R13 control window belongs to Stage 7 because window closure is an
existing acceptance criterion. It may reuse the retrieved Portmaster themed panel
and control primitives, with license/source notices before import. This is not
Stage 8 analytics implementation: overview metrics, explorer, charts and exports
remain NOT STARTED until Stage 7 closes. No criterion is moved merely to close it.

The October 13 user instruction separately authorizes current Portmaster layout
research now. The full Angular/shared-asset tree at bb6c444 is retrieved and its
immutable inventory/design map recorded before Stage 8 presentation work. This
research does not activate Stage 8 implementation or satisfy its UI criteria.
Replacement standing instructions were reread along with the installed
spec-gated-implementation, frontend-design and transactional-cleanup skills;
advancement blockers are distinct from justified BLOCKED execution status, and
component diagnostics are not feature acceptance validation.
