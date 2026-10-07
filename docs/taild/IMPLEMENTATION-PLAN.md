# TailD staged execution

Source of truth: [SPECIFICATION.md](SPECIFICATION.md). Already authorized by the
request to create the public TailD fork, inherit TailDNS and start Control D work.
Only one stage may be ACTIVE. No release or deployment is authorized here.

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
Remaining: none for this stage. No device/deployment verification is claimed.
Blockers: none. Tracked deferrals: none.

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

Status: **ACTIVE**. Requirement: R07 and integrated R01–R07 reconciliation.

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
Remaining: final publication/check evidence and closure reconciliation.
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
R07: real extraction/integration/join proof and focused contracts satisfied;
final publication/check evidence and closure remain ACTIVE.
Overall first joined-record increment is not yet declared complete.
No TailD release/deployment occurred. No Control D write request was made.
