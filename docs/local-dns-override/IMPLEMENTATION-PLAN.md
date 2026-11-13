# Staged implementation plan

Authority: [SPECIFICATION.md](SPECIFICATION.md), version 2.9.
Assessment: [EVALUATION.md](EVALUATION.md).

## November 7 updater repair

Scheduled capture42347715976 fails before creating a candidate because canonical
Android24fbeb48 changes its core requirement while TailDNS deliberately replaces
that requirement with its reviewed core. Exact merge-tree diagnosis shows only
go.mod/go.sum conflicts, confined to the vanilla tailscale.com requirement and
checksums; all other dependency and source changes merge normally. Preserve dirty
local Android work; the repair uses an isolated clean D: checkout.

Bounded correction: on a failed canonical merge, require the complete regular-file
go.mod/go.sum conflict set and matching existing fork require/replace. Resolve only
core-owned conflict lines while preserving every other merged dependency/source
change; reject unrelated conflicts before writing either file. Keep the existing
reviewed-core pin/tidy, no-secret checks and signing boundaries. Acceptance requires
focused rejection/preservation regressions, an exact real merge reproduction,
successful GitHub capture and exact-head candidate checks, then the ordinary normal
release and independent package/source/signer verification. No device or provider
actions; existing stages and real-device validation gaps remain unchanged.

Authorization: `already_authorized`. Implementation, GitHub signing, release, fork-aware auto-update and current-task monitoring are explicitly authorized. Stage 1 is BLOCKED on B3's unavailable controlled-network variants; Stage 2 is BLOCKED on B4's prohibited device-input action; Stages 3–8 and 10–12 are COMPLETE; Stage 9 is BLOCKED only on the target Fold's current ADB disconnection. Under specification 2.9, B3 and B4 remain honest validation gaps but do not block completion of the accessible workflow.

There may be only one **ACTIVE** stage. Other allowed statuses are **NOT STARTED**, **BLOCKED**, and **COMPLETE**. Park an actual blocked stage with the exact requirement, cause, ownership, resolving condition and dependent work before activating another. Close a stage only with fresh evidence for every assigned criterion.

## Stage 1 — Real Android manual-resolver vertical slice

Status: **BLOCKED**.

Scope: create the necessary shared-core fork when implementation is authorized; introduce the minimal local preference and composition path, pin that revision, and connect the Android custom editor/status to the actual engine. Start with a manually entered Control D URL. Do not build Windows infrastructure before this real slice works.

Acceptance criteria:

- R01 and R05: actual editor → persisted profile preference → shared-core configuration → real DoH query; disabling restores the upstream path.
- R04 manual-input subset: validator contract and a real Control D and non-Control D endpoint work; invalid edits leave committed state intact.
- R06 and R07: required routing precedence, lifecycle, management and restoration behavior passes focused tests and the relevant Android real-boundary checks.
- R08 Android transport subset: bootstrap, no-fallback failures, exit-node egress and the stated network matrix have evidence; assigning a resolver URL alone is insufficient.
- R09 backend/manual-UI subset: configured/applied/verified state and redaction are accurate.
- R03 manual-setup subset: Default/Automatic instructions and conflict/uncertainty reporting exist without privileged access or system writes.
- R15 test-install subset: independent package identity and stable signing provisioned before real-device fork installation; no public feature release at this stage.

Satisfied: R15 test-install identity, candidate verification and installation alongside the official app; the narrow R01/R05 manual editor-to-real-query flow, disable/restoration, a generic endpoint and local MagicDNS checks. Remaining: accessible routing/lifecycle/policy/failure checks and reconciliation. B1 permission and B2 authentication are resolved. Validation gap B3 affects R08: the available Thor Wi-Fi has no IPv6 route and no controlled IPv6-only/dual-stack/captive-portal environment is available. Under specification 1.5 those variants remain explicitly untested but do not block deployment or release. Other unfinished Stage 1 checks remain ordinary work, not passing results or deferrals. Tracked deferrals: none. Follow behavior belongs to Stage 2; Guard-obsolescence work to Stage 3; Windows checks to Stage 4.

Stage 1 evidence in progress (2026-09-18): shared core `4d32ac4faace6977e9f15f5f759a7281e8908485` includes profile-pinned edits, default-only composition, TLS-verified route-aware DoH, explicit base-DNS bootstrap and managed-policy transitions. Affected host package suites passed after repository consistency fixes; live `example.com` queries passed for public Control D, Cloudflare and generic OpenDNS. Bootstrap fixtures assert provider-only lookup, protected TCP dialing and rejection of recursive service addresses. These are host evidence, not Android/exit-node/network-matrix acceptance. Android editor/status integration and independent identity are present; Kotlin formatting passed. The persistent signer and GitHub secrets/public pin are provisioned as described in [SIGNING.md](SIGNING.md). Android build and installed workflow verification are still outstanding. No stage is complete.

Additional evidence: core `811a1030f5e4a5e007b9354572e463fe9dcef037` adds failure/no-fallback/redaction verification. Validation run [35349002734](https://github.com/Darkaxt/TailDNS/actions/runs/35349002734) passed native integration and affected Linux core suites and compiled Android Kotlin, but failed release lint; it produced no signed candidate. Dependency inspection isolated Fragment 1.1.0 on the compile classpath versus 1.5.4 at runtime. Android commit `fffdf00c3f9e6c52117a9a4eca16749c20ed1534` aligns the compile constraint; local dependency inspection and formatting passed. Full candidate validation is run [35350671598](https://github.com/Darkaxt/TailDNS/actions/runs/35350671598), not presumed successful. Real-device entry, recovery and evidence requirements are recorded in [ANDROID-VALIDATION.md](ANDROID-VALIDATION.md). Temporary Thor VPN/Guard changes await explicit test authority; no device state has been changed.

Final candidate result: run 35350671598 completed successfully, including release lint, tests, APK build and isolated signing. Independent downloaded-artifact verification passed; exact package/version/hash/signer evidence is in [SIGNING.md](SIGNING.md). Earlier pending-build/permission notes above describe historical checkpoints, superseded by the manual-slice evidence below and [ANDROID-VALIDATION.md](ANDROID-VALIDATION.md). This does not close full Stage 1 acceptance.

## Stage 2 — Automatic Android provider propagation

2026-09-18 reconciliation: B2 is resolved by successful Thor authentication. The manual editor applied the supplied Control D endpoint, explicit queries through quad-100 returned answers, and packet capture established HTTPS traffic to the maintained Control D address. A tailnet MagicDNS name resolved locally; disabling custom DNS restored upstream selection. A generic OpenDNS endpoint also applied and answered queries; packet capture showed only its hostname in the observed base-DNS TCP A/AAAA bootstrap. Logs redacted the custom endpoint. These establish the narrow real slice, not the full R01/R06–R09 matrix.

Stage 1 validation gap B3: R08 IPv6-only/dual-stack and captive-portal variants require a controlled network environment not currently available. The Thor has no IPv6 route; only the existing user Wi-Fi is in scope. Specification 1.5 requires these variants to remain disclosed as untested but forbids stopping deployment on them. Ordinary remaining profile, lifecycle, policy and exit-node checks are not reclassified as passed or deferred. No tracked deferrals. The original official VPN, Always-on assignment and Guard execution were restored; an explicit quad-100 lookup passed afterward. The saved Android provider requested by the user remains in Automatic mode. At this checkpoint Stage 3 became the sole ACTIVE stage.

Status: **BLOCKED**. The real Stage 1 manual slice is demonstrated; Stage 1 remains parked on B3 and is not COMPLETE. Stage 2's B4 is below. At this checkpoint Stage 3 became the sole ACTIVE implementation stage.

Acceptance criteria:

- R02: verify initial read and real change notifications on Thor, and prove that saves propagate with the fork UI closed and without reconnect/import actions. Per revision 1.3, the user tests the full release on the Samsung phone; it is not a pre-release device gate.
- R04 follow subset: provider conversion, exact client mapping, unsupported-value behavior and invalid-to-valid recovery pass. No silent fallback or stale-provider use.
- R01, R03 and R09: observer ownership, teardown, latest-value ordering, restart/profile isolation, mode conflicts and truthful effective-state reporting pass.
- Re-run the Android flow with an automatically selected endpoint and verify independent manual configuration remains functional. Observation is provider-independent; documented mappings define supported follow inputs unless a separately specified native DoT path is added.

Satisfied: Thor initial ordinary-app read, UI-closed change notification and end-to-end propagation, unsupported-input fail-closed behavior with retained MagicDNS, invalid-to-valid recovery without reconnecting, successive-save convergence, live strict-mode conflict reporting, immediate source-switch persistence without a save button, manual-after-follow queries, observer removal on switching to manual, no observer registration while disconnected, and direct follow-enabled disconnect/recreation with a verified 3 -> 0 -> 3 observer lifecycle. See [ANDROID-VALIDATION.md](ANDROID-VALIDATION.md) for exact candidates and evidence. Remaining: final reconciliation. Profile isolation, read/registration failure and stale callback contracts have focused host-test evidence, not a second real account on Thor. Validation gap B4: the ADB keyboard-Done/manual-invalid-input action was rejected by tool policy before execution and must not be retried through another shell/tool. Specification 1.5 retains the host regression/source contract and assigns final full-release phone interaction to the user; B4 does not block deployment or release. Tracked deferrals: none.

Implementation candidate: core `bd5613e68734acf2761f605d1a3d222f09797019` owns the follow choice, current-source reads and fail-closed resolver selection. Android uses a lifecycle-owned ContentObserver, registers before the initial read and refreshes visible status after backend processing. The manual endpoint remains independent. Focused tests cover parsing, read denial, invalid-to-valid recovery, latest-value application, late callbacks after manual selection, registration ordering and policy teardown; affected core package suites passed on Windows. Kotlin formatting passed. Native binding, Android compilation and real observation remain candidate verification work, not stage closure.

Pre-device review caught a generic masked-preference edit bypass for follow-to-manual transitions with no valid manual endpoint. A regression failed before the correction and passed afterward with the focused local-DNS suite. Core `304c9f7157b74405a5037748a617aaaa5f75fe53` includes the correction and is the new Android pin. Candidate run 35356704728 was cancelled before distribution because it used the superseded core; no device was updated from that run.

Candidate 35357288592 passed CI/build/signing and the recorded Thor propagation checks. Subsequent core `5ceffeb1c66c49ab3f4f1955fb5aafe705429a77` adds only profile/store-isolation and observation-failure/mode-status tests; these passed locally and are included in the next Android pin. The user rejected the extra Save DNS setting button; specification revision 1.4 requires immediate switch persistence. Its UI correction is under candidate validation. Thor was restored to its original VPN/Guard between builds. No stage is declared complete.

Device teardown inspection found a Stage 2 defect: disconnect bypassed the auth-reconfiguration hook and left platform observers registered. A focused regression failed before the state-entry synchronization fix and passed afterward. This is current-stage unfinished verification, not a deferral to Stage 3. Recheck actual Android observer registrations on disconnect and mode changes in the next candidate before closing R02.

The correction is core `b980fd4dee00eb218819eb6c6a2c6cb1293f58ca`; all affected core package suites passed freshly after the state-entry hook change. This supersedes the earlier pin and includes the additional profile tests. Android switch autosave and keyboard-Done manual commit passed formatting; Android/native CI and device confirmation are still required.

Final candidate pin `423bcd55b5cce99e7a3bb4ed78b276e3f8ad77e0` also satisfies R02's diagnostic-history distinction: the last valid followed endpoint is retained only in memory, scoped to the current profile, shown as not in use on source failure, and never selected as a fallback. Focused invalid-source/profile-isolation tests passed; Kotlin status serialization remains redacted. This does not add persistent copies of Android provider settings.

Candidate 35361257936 passed native/Android build, affected core suites, Android tests/lint and isolated signing. Independent verification and in-place Thor update passed. Device evidence confirms the global save button is absent, switching follow off commits immediately and applies the preserved manual endpoint, and its observers disappear. Restoration re-enabled the saved follow preference while leaving TailDNS disconnected, with zero observers; the official VPN/Always-on/Guard and public DNS were verified restored. A disconnect performed after manual selection is not proof of the direct follow-enabled disconnect regression. B4 parks the stage without claiming that remaining gate.

## Stage 3 — Native Android reliability and Guard-obsolescence proof

Status: **COMPLETE**. Stages 1 and 2 remain parked on their recorded external verification blockers. At this closure checkpoint Stage 4 became the sole ACTIVE implementation stage.

Scope: audit native lifecycle/packet paths, reproduce the Guard's scenarios, implement only evidence-backed root-cause fixes, and prove the Thor no longer needs the workaround. Do not modify or embed the Guard.

Acceptance criteria:

- R12: classify and reproduce each targeted defect, identify its failing boundary and upstream disposition, and establish pre-fix failing regression evidence.
- R13: minimal native fixes pass those regressions; a single service start initializes working DNS; process recreation, repeated starts and network/TUN transitions preserve correct resource ownership without watchdogs or duplicate-connect sequences.
- R14: perform the agreed real-device matrix with the Thor Guard disabled and verified absent from execution, with a recovery procedure and appropriate live-test authority. Distinguish process reclamation from force-stop and test explicit disconnect separately.
- Verify the native fixes with normal tailnet DNS and the automatic provider override. Confirm public, local MagicDNS and split-DNS paths separately; no restart assistance or provider fallback may mask failures.

Satisfied: pre-fix cold-connect evidence showed a first request failing before backend initialization; the coroutine-worker correction now reaches Running from an absent process with exactly one request and working public/MagicDNS. Repeated requests retain one process, VPN and active TUN. The TUN-write regression fails before and passes after retrying only an explicit replacement transition. Guard-disabled Thor checks pass three Wi-Fi loss/return cycles, sleep/wake, strict/Automatic changes, direct follow disconnect/recreation, and exit-node on/off; both exit-node transitions replace the TUN in the same process while public DNS and MagicDNS remain healthy. No `injectToHost` EIO or fatal packet-pump error appeared. Candidate 35366855618 and exact evidence are in [ANDROID-VALIDATION.md](ANDROID-VALIDATION.md).

Final evidence: run [35370729766](https://github.com/Darkaxt/TailDNS/actions/runs/35370729766) passed clean build, tests, lint and isolated signing for Android `d9ba4b23152f7421ddad8e0d9a899b3c6b4e5b75`. Independent artifact verification and in-place Thor installation passed. With the Guard suspended and the fork process absent, enabling TailDNS Always-on through Android Settings caused the system `android.net.VpnService` entry to start one foreground service (`startForegroundCount=1`, process state 4) and an operational tunnel. Public DNS, local MagicDNS, direct IP and all three follow observers passed; `am kill` left the foreground PID intact. Exit-node on/off replaced the TUN in both directions, and Wi-Fi loss/return recovered public and local DNS without an EIO/fatal packet-pump failure. The official VPN, its real Always-on setting, Automatic Private DNS and the Guard were restored afterward. External root `SIGKILL` is recorded separately: no in-process code can execute after an external kill, and the specification forbids replacing the root Guard with another watchdog. Unavailable cellular handover remains a disclosed revision-1.5 validation gap, not passing evidence. Remaining: none. Blockers: none. Tracked deferrals: none.

## Stage 4 — Windows real companion workflow

Status: **COMPLETE**. At this closure checkpoint Stage 5 became the sole ACTIVE implementation stage under the revision-1.5 continuation rule.

Acceptance criteria:

- R10: a minimal frontend and compatible daemon/CLI demonstrate the real Windows workflow, authorization checks and incompatibility detection.
- R01 and R04–R09 shared semantics are verified at the Windows boundary, including profile ownership, specific routes, exit-node routing, failures and restoration.
- Use an authorized test environment; document service/package identity and recovery. Do not replace the user's live installation without deployment authority.

Satisfied: the independently branded `taildns` CLI and compatible shared-core daemon passed authenticated set/status/clear, profile-pinned persistence across a daemon restart, real Control D DoH, MagicDNS, retained split routing, exit-node on/off, invalid-input rejection, unreachable-provider SERVFAIL without fallback, visible health degradation and recovery, and exact clear/restoration on an isolated Windows node. The official service remained running and unchanged. The unmodified daemon rejected status and mutation without claiming success. Handler authorization tests reject read-only mutation with HTTP 403; a second-account named-pipe attempt is honestly untested because no disposable second Windows identity was available. Remaining: none for Stage 4. Blockers: none. Tracked deferrals: none.

## Stage 5 — Integrated reconciliation and verified handoff

Status: **COMPLETE**. Stages 1 and 2 remain parked only on the specification-1.5 disclosed validation gaps. At this closure checkpoint Stage 6 became the sole ACTIVE stage.

Acceptance criteria:

- R11: exact source provenance, license preservation, compatibility/identity decisions, reproducible evidence and honest README status are complete.
- Reconcile **every R01–R14 acceptance criterion**, including automatic propagation and Guard-disabled Thor evidence, against the integrated revisions. Reconcile R15 test-install identity before release preparation. Do not retire the Guard or claim obsolescence while R14 is incomplete.
- Run affected full suites and the required final real-device matrix; inspect the results, resolve all required blockers/deferrals, and verify restoration.
- Commit the completed verified feature. The user has authorized the release, but publication occurs only in Stage 6 after this validation gate.

Satisfied: validation run [35395256020](https://github.com/Darkaxt/TailDNS/actions/runs/35395256020) built and tested Android `186daa5a70644ea0d4f0216c25cdd28bc6fad070` with pinned core `ebe4cb48e6f37f54f469346d4a21773d2b5d1db7`, then signed it in an isolated job. Independent verification matched the workflow checksum, fork package, version, ABI set and pinned certificate. The in-place Thor update preserved login and preferences. With the Guard stopped, exact-candidate checks passed automatic invalid-to-valid propagation, no-default fallback, MagicDNS preservation, resolver-health warning/recovery, provider HTTPS packet evidence, exit-node on/off, Wi-Fi loss/return, explicit disconnect/observer teardown and an absent-process system Always-on start with foreground protection. The official Always-on VPN, Guard, Automatic Private DNS and saved provider were verified restored. [FINAL-RECONCILIATION.md](FINAL-RECONCILIATION.md) maps every R01–R14 requirement to evidence and records the specification-1.5 gaps without claiming they were tested. R15's test-install identity is reconciled; final release delivery remains in Stage 6. Remaining: none. Blockers: none. Tracked deferrals: none.

## Stage 6 — GitHub signing and public release

Status: **COMPLETE**.

Acceptance: complete R15's trusted GitHub signing/release workflow, publish the tested version, independently verify downloaded artifacts and signer/package/version/provenance, and verify update compatibility on an authorized test device. No incomplete stage can be concealed by a release.

Satisfied: tag-bound run [35399346673](https://github.com/Darkaxt/TailDNS/actions/runs/35399346673) tested Android `04631d14fa1021217208caee3e6e7317f51a6c86` and core `ebe4cb48e6f37f54f469346d4a21773d2b5d1db7`, packaged the Windows AMD64 companion, and isolated all signing/release secrets from repository execution. The non-draft [v1.0.0-taildns.2 release](https://github.com/Darkaxt/TailDNS/releases/tag/v1.0.0-taildns.2) was independently downloaded and every asset matched its checksum. The APK matched package, code `298294770`, version `1.103.262-tebe4cb48e-g04631d14f`, target SDK 36, four ABIs and the pinned signer; its v2/v3 and detached v4 signatures verified. The Windows archive contained the expected x86-64 binaries, licenses, instructions, internal hashes and truthful unsigned Authenticode status. Thor updated in place from code 100, retained its first-install identity, encrypted preferences, profile data and saved running intent; the system confirmation was not accepted, and official Always-on, public DNS and the Guard watchdog were verified restored. [RELEASE-VALIDATION.md](RELEASE-VALIDATION.md) records the evidence. Remaining: none. Blockers: none. Tracked deferrals: none.

## Stage 7 — Post-validation auto-update and current-task monitoring

Status: **COMPLETE**.

Acceptance: complete R16's dependency-ordered promotion and release workflow and R17's TailDNS product identity, then verify the recurring task monitor performs promotion/release and repairs failures without weakening gates.

Satisfied: core PR [1](https://github.com/Darkaxt/tailscale/pull/1) promoted exact checked head `43a88f96bb81206f4baad0047763646761bcc764` as core `f5de5ace94bb3fb21794d1e10184029709242aa0`; Android PR [1](https://github.com/Darkaxt/TailDNS/pull/1) then promoted exact checked head `cb270f27a2b641fc7b296d7306bce40e6fbcd3fa` as Android `ab93b54cbccd3e148ebd53b3d943548f9e85960b`. Candidate run [35455837978](https://github.com/Darkaxt/TailDNS/actions/runs/35455837978) passed the branding, version, core/toolchain, native and Android gates after two contained pipeline failures were diagnosed and repaired. Tag-bound run [35456966765](https://github.com/Darkaxt/TailDNS/actions/runs/35456966765) published the non-draft [v1.103.312-taildns.3 release](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312-taildns.3), preserving upstream `VERSION_SHORT=1.103.312` and appending only `-taildns.3`. Independent public downloads matched every checksum, exact source provenance, package, TailDNS label, monotonic code `298306220`, four ABIs, pinned signer, v2/v3 signatures and the expected Windows x86-64 unsigned boundary. The public Android repository is named TailDNS and both public forks now expose only `main`; the core fork's inherited CI and Dependabot PR creation were disabled in favor of the two TailDNS candidate workflows. The task heartbeat `monitor-taildns-upstream-updates` remains active daily at 08:30 UTC and owns dependency-ordered promotion, monotonic signed release, independent verification and bounded failure repair without device control. Remaining: none. Blockers: none. Tracked deferrals: none.

Post-closure repair: device launch exposed an invalid `.3` Go runtime version stamp. A focused regression and validation run [35463656654](https://github.com/Darkaxt/TailDNS/actions/runs/35463656654) separated the Android-visible suffix from upstream-compatible `VERSION_LONG`. Release run [35464607187](https://github.com/Darkaxt/TailDNS/actions/runs/35464607187) published verified [v1.103.312-taildns.4](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312-taildns.4) without increasing the official version component. The public APK then passed Thor startup, authentication/Tailnet Lock, Always-on, MagicDNS, Control D, and official-package replacement checks recorded in [RELEASE-VALIDATION.md](RELEASE-VALIDATION.md).

## Stage 8 — AYN Clear-all resilience and Thor hotfix release

Status: **COMPLETE**.

Objective: close R18 with the narrowest app-owned fix, publish the next signed TailDNS subversion, install it on Thor, restore the supplied Control D follow configuration and prove the real AYN Clear all workflow no longer force-stops the VPN.

Acceptance criteria:

- Root-cause evidence identifies the caller and exact vendor behavior rather than treating the process loss as a TailDNS crash.
- A pre-fix manifest regression fails because TailDNS task-owning activities are visible in Recents; the minimal manifest change makes it pass without adding restart machinery or modifying the Thor vendor whitelist.
- Focused tests, Android build/lint and the trusted candidate workflow pass; the downloaded APK's package, upstream-preserving version, signer and source provenance verify independently.
- On Thor, the signed update preserves the existing profile, selects Follow Android Private DNS provider with the supplied saved Control D hostname in Automatic mode, and reaches a working foreground VPN.
- After opening TailDNS and invoking AYN Launcher's real Clear all action, TailDNS remains absent from Recents, its process/VPN/Always-on state remains live, the package is not stopped, and Control D public resolution plus MagicDNS pass.
- Publish and independently verify the next monotonic `v1.103.312-taildns.N` release, install that public artifact on Thor, repeat the relevant checks, update the evidence documents, commit and push. Blockers: none currently. Tracked deferrals: none.

Satisfied: the caller and force-stop behavior were traced to AYN Launcher3 rather than TailDNS. The manifest regression failed before and passed after both task-owning activities received `android:excludeFromRecents="true"`; trusted candidate run [35479401193](https://github.com/Darkaxt/TailDNS/actions/runs/35479401193) and isolated signing run [35479774581](https://github.com/Darkaxt/TailDNS/actions/runs/35479774581) passed. Tag-bound release run [35480878938](https://github.com/Darkaxt/TailDNS/actions/runs/35480878938) published [v1.103.312-taildns.5](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312-taildns.5) from Android `5284a1b2211ee3258b1b9d94db5263673214f53c` with pinned core `f5de5ace94bb3fb21794d1e10184029709242aa0`, preserving upstream `1.103.312` and appending only `-taildns.5`. Independent downloads matched all release checksums; the APK's package, version code `298310800`, version, v2/v3 signatures, pinned signer and built-manifest exclusion verified. The public APK updated Thor in place. Its Follow Android and local-default switches remained enabled and derived `https://dns.controld.com/8b42rmrayt` from Android Automatic mode. AYN's real **Clear all** removed the visible test tasks while TailDNS had no card and retained PID `23301`, foreground VPN network `138`/`tun1`, package stopped=false, Always-on with lockdown off, all three settings observers, public resolution and MagicDNS. The official package stayed absent and the Guard stayed installed but stopped. Remaining: none. Blockers: none. Tracked deferrals: none.

## Stage 9 — Fold source-first interaction hotfix and signed update

Status: **BLOCKED**.

Objective: close R19 with the narrowest Android UI policy change, publish the next signed TailDNS subversion, update the authorized Galaxy Z Fold 7 in place and prove the selected Android provider remains effective.

Acceptance criteria:

- Preserve the live pre-fix evidence: Android Automatic mode and the saved Control D source are readable, both switches enabled produce an applied `<local-dns>` default, and public plus MagicDNS resolve.
- A test-first state matrix reproduces the defect by allowing local enablement with no selected source, then passes after the minimal UI policy change. The backend validation remains unchanged.
- Focused Android tests, formatting/lint, release validation and the tag-bound signing workflow pass; the public APK preserves `VERSION_SHORT=1.103.312`, appends only the next `-taildns.N`, and independently verifies against checksums, package, signer and source provenance.
- The public APK updates the Fold in place without losing login, profile, Automatic Private DNS or saved provider. On the real screen, empty manual mode cannot submit local enablement; Follow Android remains selectable; the restored enabled follow state is applied and public plus MagicDNS resolve.
- Update the evidence documents, commit and push.

Satisfied: the Android 16 Fold baseline proved that Automatic Private DNS and
the saved provider are readable and that Follow Android plus local-default
applies `<local-dns>` while public and MagicDNS resolve. The invalid first-click
path produced the expected backend HTTP 400 before the fix. The focused policy
matrix failed before and passed after the minimal source gate. Candidate run
[35520700127](https://github.com/Darkaxt/TailDNS/actions/runs/35520700127)
passed the clean native/Android build, tests and isolated signing. Tag-bound run
[35521188296](https://github.com/Darkaxt/TailDNS/actions/runs/35521188296)
published the independently verified public
[`v1.103.312-taildns.6`](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312-taildns.6)
without changing `VERSION_SHORT=1.103.312`.

Remaining: install the public APK in place on the authorized Fold and verify
profile/settings retention, the disabled empty-source control, Follow Android
selection, restored applied status, public DNS and MagicDNS. External blocker:
the Fold disconnected from ADB after the baseline; only the Thor is visible and
must remain untouched. Resolving condition: reconnect the Fold. Dependent work:
the real-device acceptance criterion, Stage 9 closure and final evidence commit.
Tracked deferrals: none.

## Stage 10 — Updater-compatible version repair and Thor deployment

Status: **COMPLETE**.

Objective: close R20 by replacing the non-standard `-taildns.N` version qualifier with the standard numeric build suffix `+N`, publish the next signed TailDNS release without changing `VERSION_SHORT=1.103.312`, and seed the corrected update line on Thor with one UI-free direct installation of the public APK.

Acceptance criteria:

- A focused compatibility contract reproduces why the legacy APK/tag pair is classified as non-standard and verifies that `1.103.312+7` followed by `1.103.312+8` is automatically comparable under ObtainX 2.10.00 and current Obtainium standard-version rules.
- The formatter and tag-bound workflow accept only positive numeric fork sequences, emit Android `1.103.312+N` and tag `v1.103.312+N`, preserve the upstream-compatible Go `VERSION_LONG`, and compare the new Android version code against either a legacy or corrected prior release.
- Trusted validation and the tag-bound signing/release workflow pass. Independent public downloads match checksums, package `io.github.darkaxt.taildns`, expected corrected version, pinned signer and exact source provenance.
- The public APK updates only Thor serial `bfa98654` in place without UI automation. The first-install identity, package data/profile, Android Private DNS provider/mode, Follow Android behavior and Always-on assignment remain intact; TailDNS runs and public plus MagicDNS resolution pass.
- Release, signing, updater and validation documentation records the one-time direct migration for installations already marked pseudo and automatic comparison for subsequent `+N` releases. Changes are committed and pushed.

Satisfied: root-cause inspection of ObtainX 2.10.00 and current Obtainium shows that `taildns` is outside their standard version qualifier grammar. ObtainX's arbitrary-shape fallback also sees legacy installed `1.103.312-taildns.5` and GitHub tag `v1.103.312-taildns.6` as different shapes because of the tag's leading `v`, causing automatic pseudo-version classification. The test-first contract reproduced that failure and verified corrected `+7` to `+8` comparison. Validation run [35524334561](https://github.com/Darkaxt/TailDNS/actions/runs/35524334561) passed the exact clean build and isolated signing after the literal-plus tag trigger received its own failing regression and repair. Tag-bound run [35524781376](https://github.com/Darkaxt/TailDNS/actions/runs/35524781376) published the independently verified [v1.103.312+7 release](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312%2B7) from Android `f408df7925fb6f140581bee0dbc6d41a5586a9c3`, keeping `VERSION_SHORT=1.103.312`. Every public checksum, APK identity/signature/signer and Windows internal hash matched. The public APK updated only Thor serial `bfa98654` in place: version code advanced to `298320570`, first-install time and data inode `577091` were retained, package stopped remained false, Always-on stayed assigned with lockdown off, Automatic Private DNS retained the saved provider, IPNService returned foreground, public DNS resolved and MagicDNS resolved `beacon.tail94fa2c.ts.net` to `100.97.195.70`. No Thor UI was opened. The task-attached monitor was updated to preserve the `+N` contract. Remaining: none. Blockers: none. Tracked deferrals: none.

## Stage 11 — Windows in-place TailDNS upgrade and Beacon deployment

Status: **COMPLETE**.

Objective: close revised R21 by replacing the proprietary-GUI compatibility pin
with a feature-complete TailDNS tray client, packaging it with a current matching
daemon/CLI, and deploying that integrated set on Beacon without a new login or
machine entry.

Acceptance criteria:

- A test-first deployment contract covers administrator and service/state
  preconditions, release checksum enforcement, exact original-daemon backup,
  binary-in-place replacement with an unchanged service path, preservation of
  Wintun and matching replacement of daemon plus CLI plus TailDNS tray client,
  auto-update rollback metadata, automatic
  rollback on activation failure, explicit restoration, and release contents.
- The installer reuses the default service pipe and existing
  `%ProgramData%\Tailscale` state; it never reads, copies or logs private state.
  The driver remains unchanged, the existing service path never changes, and
  daemon, CLI and tray client bytes match one verified current-core TailDNS
  payload. The official GUI remains installed only as rollback plumbing until
  parity passes. Official automatic update application remains disabled until
  Stage 12 owns it.
- A test-first TailDNS tray contract covers one instance per interactive session,
  persistent IPN-bus ownership, abnormal-child restart, explicit Exit, login and
  profile switching, connect/disconnect, device address, exit-node/LAN controls,
  DNS/routes/incoming/unattended/update preferences, TailDNS resolver state,
  About/version, and admin/detailed-settings access without polling or arbitrary
  synchronization sleeps.
- Trusted validation and a tag-bound Windows release workflow pass and publish
  `windows-v<upstream-version>+N` without claiming a newer Tailscale version.
  Independent downloads verify the signed manifest, checksums, installer,
  Windows payload contents and exact source provenance.
- Beacon upgrades in place. Pre/post node ID, addresses, running profile and
  trusted Tailnet Lock signing key match; no authentication URL or new machine
  appears. The supplied Control D endpoint is configured/applied through
  `taildns`, and public plus MagicDNS queries pass.
- Beacon's pre-existing read-only hosts file remains byte-for-byte and
  attribute-for-attribute unchanged. A focused regression fails before and
  passes after the daemon skips only this optional projection; writable-hosts
  behavior and other write failures remain unchanged. Repeated daemon and
  TailDNS-tray reconnect checks keep the backend `Running`, with public and
  fully qualified MagicDNS queries passing.
- The installer-based deployment and rollback evidence is documented, committed
  and pushed. The local compatibility branch is replaced by an immutable release
  tag and removed so the public fork retains only deliberate long-lived branches.

Satisfied: focused deployment regressions cover the administrator/service/state
preconditions, version/checksum contract, Wintun reuse, versioned installation,
activation rollback, explicit restoration, update-preference restoration and
release archive. Validation run
[35556275052](https://github.com/Darkaxt/TailDNS/actions/runs/35556275052)
passed for Android `5ffbd14a63e01056286cc7e4d904d3d81713b21f` with core
`f5de5ace94bb3fb21794d1e10184029709242aa0`; tag-bound run
[35556765875](https://github.com/Darkaxt/TailDNS/actions/runs/35556765875)
published the independently verified
[v1.103.312+11 release](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312%2B11).

Beacon upgraded the single existing automatic `Tailscale` service in place from
`C:\Program Files\Tailscale\tailscaled.exe` to the versioned
`C:\Program Files\TailDNS\versions\1.103.312+11\taildnsd.exe`. The official
GUI remained running and the existing Wintun binary was reused. The deployment
record's exact baseline and post-activation checks matched the node ID,
Tailnet addresses and full trusted Tailnet Lock public key; the backend returned
to `Running` with its node key and no authentication URL. Official update checks
remain enabled while automatic update application is disabled. The supplied
Control D HTTPS endpoint is retained and can report configured/applied, but the
official GUI subsequently reproduced a daemon connection failure. Root-cause
evidence shows Beacon's hosts file is explicitly read-only and contains a stale
Tailscale section; the current peer map causes the Windows DNS manager to try an
atomic replacement, which returns sharing/access errors and forces the backend
to `NoState`. R21's stable running-backend and GUI acceptance criterion remains
unsatisfied until the optional hosts projection repair is deployed on Beacon. The
read-only-hosts regression now fails before and passes after the bounded
shared-core repair at `bfc88fd8689548a7e0287178584a94c8307d6fe3`; focused
and broader shared-core tests pass, and exact-source validation run
[35585439505](https://github.com/Darkaxt/TailDNS/actions/runs/35585439505)
passed for Android `d7cddc428d35d2829054bee7d2077f722fef3f60`. The
immutable `v1.103.312+12` tag correctly produced no release because the updated
core's natural development patch had advanced to `1.103.318`, violating the
frozen official-version contract. The release repair made `1.103.312` an
explicit tested source of truth. Validation run
[35587670733](https://github.com/Darkaxt/TailDNS/actions/runs/35587670733)
passed for Android `9f4ca0da7ef4332b4a0a8ae02b71f863625bdb74`; tag-bound
run [35588941987](https://github.com/Darkaxt/TailDNS/actions/runs/35588941987)
published `v1.103.312+13`, and independent public download verified the Windows
archive and its internal executable manifest. Beacon upgraded in place and the
read-only hosts file remained byte-for-byte and attribute-for-attribute
unchanged, eliminating the original access-denied DNS failure. The daemon then
rotated its node key and became Tailnet-Lock locked out. Its recorded trusted
signer is unchanged, but local signing fails with control error `500 ... zero
serverNoiseKey` because a locked-out node cannot submit its own signature.
Rollback remains exactly recorded to the official service path, but two
administrator elevation attempts were cancelled after the user left.

The administrator-approved rollback subsequently completed. Fresh baseline
evidence shows the official service path, authenticated node ID and addresses,
trusted Tailnet Lock signer, updater preferences and original daemon hash were
restored. The prior Tailnet Lock blocker is therefore resolved.

Specification 2.5 reconciliation: the exact `v1.102.4` core backport at local
commit `6e187510953cf63e9c3c2938239e1a6fd4dd751b` passed the affected core,
LocalAPI, DNS and Windows-companion suites. Its distribution-stamped daemon and
matching CLI report `VERSION_SHORT=1.102.4` and long version
`1.102.4-taildns.1`. The administrator-approved binary-in-place transaction
preserved the original service path, GUI hash, Wintun, `%ProgramData%` state,
node ID `nCPRwrVksn11CNTRL`, tailnet addresses and trusted Tailnet Lock signer.
The supplied Control D endpoint reported configured/applied; public DNS and
fully qualified MagicDNS passed. After restarting the unmodified official GUI,
it held two live handles to the default daemon pipe, the backend remained
`Running`, and the user confirmed the tray UI worked. This closes the manual
compatibility slice, not Stage 11.

Native installer and release reconciliation: core commit
`2f687b68643c1d96bfe1eb152d4b21beaf6c4490` implements signed-manifest
verification, exact `windows/amd64` payload enforcement, administrator/service/
state preconditions, exact official-base gating, verified recovery copies,
atomic daemon/CLI replacement, resolver installation, unchanged service path,
GUI/Wintun preservation, identity and Tailnet Lock continuity, public DNS and
MagicDNS verification, automatic rollback, explicit rollback and status. The
release pipeline uses GitHub variable
`TAILDNS_WINDOWS_UPDATE_PUBLIC_KEY_BASE64` and protected secret
`TAILDNS_WINDOWS_UPDATE_PRIVATE_KEY_PEM`; the local private-key material was
deleted after GitHub confirmed both settings.

GitHub run [35648271621](https://github.com/Darkaxt/tailscale/actions/runs/35648271621)
published the public
[windows-v1.102.4+3 release](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.102.4%2B3).
The isolated signing job accepted only the exact tag, schema, platform,
architecture, source commit and four-file manifest set, independently matched
every payload size/hash, matched private and public Ed25519 keys, and verified
the signature before publication. A separate public download verified the
release-level checksums, packaged and separately published manifests/signatures,
Ed25519 signature, every payload size/hash, exact core commit, CLI and daemon
version `1.102.4-taildns.3`, embedded update public key and
`requireAdministrator` resource. Authenticode status is truthfully `NotSigned`.
Failed immutable `+1` and `+2` tags produced no release; their daemon-output and
ambient-VCS-dirty validation defects were root-caused and fixed before `+3`.
The installer/release commits were integrated into core `main`, documented and
pushed through `0fb348a4c`.

Current-core tray and deployment reconciliation: core PR
[10](https://github.com/Darkaxt/tailscale/pull/10) integrated the independent
TailDNS tray, per-session supervisor, transactional four-binary installer and
five-payload signed release workflow as core
`c36f8860764ec2654bb854012dfe0041bfb9e725`. GitHub run
[35742696688](https://github.com/Darkaxt/tailscale/actions/runs/35742696688)
published
[windows-v1.103.0+5](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.103.0%2B5).
Independent public download verified outer checksums, the Ed25519 manifest
signature, every payload size/hash, source provenance, embedded installer
public key and `requireAdministrator` resource. The binaries truthfully remain
`NotSigned` by Authenticode.

Beacon installed that public payload over the existing service without a login
or new machine. The service path remains
`C:\Program Files\Tailscale\tailscaled.exe`; daemon, CLI, resolver and tray
hashes match the signed deployment record and report `1.103.0-taildns.5` from
the exact release commit. Node ID `nCPRwrVksn11CNTRL`, addresses
`100.97.195.70`/`fd7a:115c:a1e0::ca01:c347`, DNS name and Tailnet Lock signer
`tlpub:ff4a7450ab477743b42ebef7f9c84f706a4b7b76ac36714a176eae9a39f2f523`
match the baseline. Wintun and the retained official GUI match their recorded
hashes. The official startup link and running GUI were replaced by the TailDNS
startup command and one supervisor/child pair. Killing child PID `38616`
retained supervisor PID `13724`, which started replacement child PID `7768`
with the exact installed executable and child flag.

The supplied `https://dns.controld.com/1ck0taaf0tt` endpoint reports configured
and applied. Public DNS, Beacon's FQDN, short-name `ayn-thor` and fully qualified
`ayn-thor.tail94fa2c.ts.net` resolve correctly, and tailnet ping reached Thor.
The hosts file retained its exact baseline SHA-256, attributes and length.
Official automatic update application remains disabled for Stage 12. Remaining:
none. Blockers: none. Tracked deferrals: none.

## Stage 12 — Fork-aware Windows updates and upstream promotion

Status: **COMPLETE**.

Objective: close R22 by routing the existing auto-update preference to a
TailDNS-signed GitHub update channel, supporting exact-base TailDNS updates and
verified official-base transitions, then proving that the existing GitHub and
task automation actually promotes and releases passing upstream candidates.

Acceptance criteria:

- A test-first signed-manifest contract rejects unsigned, malformed, replayed,
  lower-sequence, wrong-architecture/base and hash-mismatched updates without
  mutating the installation.
- The TailDNS tray update preference controls the TailDNS provider. A same-base
  update uses the Stage 11 transaction; a base transition installs a verified
  matching daemon/CLI/tray set and updates the Authenticode-verified official
  driver package only when the new core explicitly requires it. Mixed-version
  success is impossible.
- Beacon automatically updates between two Windows TailDNS sequences while
  preserving TailDNS tray connectivity, service path, node identity, Tailnet Lock signer,
  resolver state, public DNS and MagicDNS. Failure injection restores the last
  complete verified set.
- The Windows tray's connected, disconnected and exit-node state icons are the
  exact multi-resolution resources from Beacon's preserved official client,
  with source hash/resource-group provenance and packaged hash checks.
- GitHub detects a real or rehearsed upstream release, validates and promotes
  core first, refreshes and promotes Android/Windows candidates, publishes the
  signed platform releases and independently verifies them. A passing candidate
  is not left parked.
- The existing task-attached monitor is updated rather than duplicated, keeps
  its quiet-when-current notification policy, repairs bounded failures and
  records its automation identity/cadence. It performs no automatic device
  changes.

Verification evidence required: focused updater tests, installer failure
injection, signed public manifest verification, two-sequence Beacon update,
official-base transition rehearsal, exact icon-resource/hash comparison,
GitHub run/release URLs, independent public artifact checks, and the inspected
task automation definition.

Satisfied: updater and installer contracts reject malformed signatures/schema,
replay/lower sequence, wrong architecture/base, hash mismatch and partial-set
activation; the rehearsed base transition verifies the complete matching set
and failure restoration. Core PR
[18](https://github.com/Darkaxt/tailscale/pull/18) integrated deterministic
LocalSystem-to-active-user tray startup and public release
[windows-v1.103.0+17](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.103.0%2B17).
Core PR [19](https://github.com/Darkaxt/tailscale/pull/19) then integrated the
four exact multi-resolution official tray-state resources with source binary,
resource-group and SHA-256 provenance. GitHub run
[35795113173](https://github.com/Darkaxt/tailscale/actions/runs/35795113173)
published non-draft
[windows-v1.103.0+18](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.103.0%2B18)
from exact core `57351e8a9724e157cd1b2f2cdba0009717f1e8e7`; independent download
verified release checksums, Ed25519 manifest signature/key, manifest schema,
source/version/sequence/architecture and every packaged payload hash. The
published tray contains all four recorded ICO resources byte-for-byte.

Beacon automatically moved from `1.103.0+17` to `1.103.0+18` with both update
preferences enabled. The deployment record, installed hashes and running
service agree on exact core `57351e8a9724e157cd1b2f2cdba0009717f1e8e7`;
the service remains automatic at `C:\Program Files\Tailscale\tailscaled.exe`,
the same node ID, addresses and Tailnet Lock signer remain present, the tray
supervisor and child run in interactive session 1, and Control D, public DNS
and MagicDNS pass. Replaying the updater reported that the signed manifest was
not newer and left the record, service and tray PIDs unchanged. The user's real
taskbar screenshot confirms native transparent official-icon rendering without
the former black pixelated background. The existing task-attached heartbeat
`monitor-taildns-upstream-updates` remains ACTIVE daily at 08:30 UTC and was
updated in place to require dependency-ordered core promotion, signed Windows
release verification, exact-core Android promotion and signed Android release
verification; it stays quiet while current and never controls devices.
Remaining: none. Blockers: none. Tracked deferrals: none.

## Requirement ownership

| Requirement | Initial delivery owner | Additional required verification |
| --- | --- | --- |
| R01 local ownership | Stage 1 manual; Stage 2 follow | Windows Stage 4; final Stage 5 |
| R02 automatic propagation | Stage 2 | Final Stage 5 |
| R03 Android mode/privileges | Stage 1 manual setup; Stage 2 follow UX | Final Stage 5 |
| R04 validation | Stage 1 manual URL; Stage 2 provider conversion | Windows Stage 4; final Stage 5 |
| R05 shared core | Stage 1 | Windows Stage 4; final Stage 5 |
| R06 precedence | Stage 1 | Reliability Stage 3; Windows Stage 4; final Stage 5 |
| R07 lifecycle/policy | Stage 1 | Reliability Stage 3; Windows Stage 4; final Stage 5 |
| R08 transport/failures | Stage 1 Android | Reliability Stage 3; Windows Stage 4; final Stage 5 |
| R09 UI/diagnostics | Stage 1 manual; Stage 2 follow | Windows Stage 4; final Stage 5 |
| R10 Windows | Stage 4 | Final Stage 5 |
| R11 completion/publication | Stage 5 | Earlier stages retain accurate milestone claims |
| R12 root-cause audit | Stage 3 | Final Stage 5 |
| R13 native lifecycle fixes | Stage 3 | Final Stage 5 |
| R14 Guard-obsolescence proof | Stage 3 | Final Stage 5 |
| R15 signing/release | Stage 1 test-install identity; Stage 6 release | Stage 6 downloaded artifact and update verification |
| R16 auto-update/monitor | Stage 7 | Stage 7 rehearsal and task automation verification |
| R17 TailDNS identity | Stage 7 | Stage 7 candidate, public repository and release verification |
| R18 AYN Clear-all resilience | Stage 8 | Thor real Clear all, DNS/MagicDNS and public-release verification |
| R19 source-first interaction | Stage 9 | Fold invalid-path UI contract, signed update and restored DNS/MagicDNS validation |
| R20 updater-compatible subversion | Stage 10 | Public release verification, one-time Thor migration and next-release comparison contract |
| R21 Windows in-place upgrade | Stage 11 | Beacon state/Tailnet Lock preservation, resolver application and rollback proof |
| R22 Windows auto-update and upstream promotion | Stage 12 | Signed manifest, Beacon update transition and task-attached promotion rehearsal |
| R23 DNS screen migration preservation | Stage 12 maintenance | Exact-input conflict reconciliation, stale-callback/profile regressions, trusted candidate and signed release verification |

Before each stage closure, update its evidence, satisfied/remaining criteria, blockers and tracked deferrals. Do not substitute commit volume, component count or passing-test totals for a demonstrated workflow. Unknown implementation details must be resolved inside the owning stage without introducing speculative infrastructure.
