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
are established, not assumed. Remaining: viable validated GlassWire source,
actual data integration and joined-record proof. Next: read-only interface
inventory, without opening its UI or modifying its policy/service/data.
Tracked deferrals: none.
