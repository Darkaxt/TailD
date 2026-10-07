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

Status: **ACTIVE**. Requirement: R06.

Acceptance: documented device/profile read and organization CSV command; safe
credential/error handling and HTTP contract tests; at least one real account read
and DNS decision without policy changes. Account type determines whether the
documented organization endpoint applies; do not pretend a personal dashboard
export is a live API. Use one direct command, not a generic provider layer.

Satisfied: official API boundary investigation only.
Remaining: implementation, focused tests and actual authenticated validation.
The user supplied a token and explicitly confirmed READ-only permissions. It is
held only in the execution session and will be supplied to the local command
through stdin, not arguments, logs, repository files or GitHub secrets.
Account type and analytics instance remain unknown. Ordinary implementation is
not blocked by those prerequisites; actual DNS-decision verification can be.
Tracked deferrals: none.

## Stage 3 — Real Windows joined record and final reconciliation

Status: **NOT STARTED**. Requirement: R07 and integrated R01–R07 reconciliation.

Acceptance: validated read-only application connection + network-byte source;
one real DNS/process/device joined export with honest provenance/confidence;
final checks and verified commits. No dashboard or broad telemetry framework.

Satisfied: AppControl field availability was checked live; missing network fields
are established, not assumed. Remaining: viable GlassWire/other authorized source,
actual data integration and joined-record proof. Blockers not yet activated.
Tracked deferrals: none.
