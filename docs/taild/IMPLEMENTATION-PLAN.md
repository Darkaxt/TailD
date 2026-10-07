# TailD staged execution

Source of truth: [SPECIFICATION.md](SPECIFICATION.md). Already authorized by the
request to create the public TailD fork, inherit TailDNS and start Control D work.
Only one stage may be ACTIVE. No release or deployment is authorized here.

## Stage 1 — Public TailDNS derivative with automatic inheritance

Status: **ACTIVE**. Requirements: R01–R05.

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
Remaining: final promotion-protocol tests, source push, inherited workflow
disabling and actual GitHub no-signing inherited-build proof.
Blockers: none. Tracked deferrals: none.

## Stage 2 — First read-only Control D data

Status: **NOT STARTED**. Requirement: R06.

Acceptance: documented device/profile read and organization CSV command; safe
credential/error handling and HTTP contract tests; at least one real account read
and DNS decision without policy changes. Account type determines whether the
documented organization endpoint applies; do not pretend a personal dashboard
export is a live API. Use one direct command, not a generic provider layer.

Satisfied: official API boundary investigation only.
Remaining: implementation, focused tests and actual authenticated validation.
Potential external prerequisites: locally stored Read token, account type and
analytics instance. Ordinary implementation is not blocked by these prerequisites.
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
