# Stage 9 local packaging contract

Stage 9 is COMPLETE for local release-readiness; no public release exists. Its
original scope did not authorize replacing the active client or activating an
updater. Stage 10 is now explicitly authorized and ACTIVE. Stage 8's native UI acceptance
is recorded separately in [DESKTOP-ANALYTICS.md](DESKTOP-ANALYTICS.md).

The first required packaging path reuses the verified Python implementation,
freezes it as a windowed one-directory `TailD.exe`, and publishes the native
WebView2 host self-contained for Windows amd64. No production rewrite of the
query/correlation engine or developer Python/Node/Go requirement is introduced.
The owning-user launcher starts the same bundled executable in collector mode;
the reader remains a separate privileged, fixed-schema operation. No automatic
collection opt-in, production credential installation or source ACL change.

Build-only dependencies are pinned in `desktop/packaging-requirements.txt`.
`scripts/taild/build_package.ps1` requires a new exact task-owned output directory
and the explicit build Python. It does not install globally, overwrite an old
candidate, publish, elevate, install a service or touch an existing client.
Frontend inputs use the npm lock and native inputs use the NuGet lock. Outputs
identify the actual source commit, dirty state, exact inherited core replace pin,
architecture and every file digest. This is provenance, not a signed updater
manifest or an Authenticode claim.

Candidate 1's bundled owning-user launcher -> bundled collector -> authenticated
pipe -> existing native UI -> explicit stop passes. That check uses the already
verified Debug inspector host; it does not establish Release offline UI/installer
acceptance. Release compilation exposed a Debug-only unused exception variable,
now corrected at the conditional declaration. The first publish also produced a
narrow generated `desktop/native/bin/Release` output; subsequent builds route it
explicitly to the task output and the expendable first copy is cleanup-owned.

Final acceptance evidence below supersedes the first-candidate diagnostics. The
installed client, updater and source services remain untouched. No Stage 8 Debug
host check is substituted for production Release or installer acceptance.

Local Sandbox is disabled. Hyper-V is installed/running, but the current process
cannot inventory its VMs; no host feature, VM, service or privilege was changed.
Use an isolated authorized Windows test host or credential-free hosted Windows
runner for installer tests; do not exercise an incomplete installer on Beacon.
The earlier forced-outage waiver does not waive these Stage 9 installer criteria.

The owned `taild-package-checks` workflow is manual, read-only and credential-free.
It builds an explicitly verification-only trust variant with an ephemeral Windows
vault identity on a fresh GitHub-hosted Windows VM. It does not receive production
signing secrets or publish installer artifacts. The real installer/SCM matrix
uses opaque synthetic account/node/signer/provider state, not a claimed real
tailnet login. Original-user SID is captured through Inno's original-user launch,
not the elevated administrator's username. Uninstall confirmation/preflight is
nondestructive; reader removal occurs only in the actual uninstall phase.
Package callbacks write bounded, value-free error type/Win32/frame diagnostics
into the installer log. Private values and exception text are not logged.

## Signing and eventual delivery boundary

The dedicated production Ed25519 public key is pinned in `package_manifest.py`;
the matching private identity stays in the owning Windows vault at
`Darkaxt/TailD/ReleaseManifest/Ed25519/v1`. It is not a Control D token, Tailnet
Lock key, TailDNS secret or Authenticode certificate. Production signing refuses
fixture trust, dirty builds, mismatched key, changed payload hashes or a version
different from the actual pinned core's `VERSION.txt` plus the build subversion.
The unsigned Windows executable/installer label remains explicit.

The Stage 10 release arrangement is deliberately separated from candidate CI:

1. A read-only pinned-source build job creates the toolchain-free payload,
   complete hashes/notices and provenance. No signing credential is available.
2. A dedicated protected signing job consumes that exact immutable inventory,
   checks the selected commit/version/core/schema and monotonic sequence, and
   signs only canonical manifest bytes using reviewed pinned signing tooling.
   It does not import or execute downloaded application/candidate code.
3. A credential-free packaging job combines the exact payload and detached
   signature into the reviewed Inno installer. The protected signer then signs
   a release envelope containing that installer digest and component identity.
4. A separate publication job can upload only those checked immutable artifacts;
   independent download verification precedes any explicitly selected migration
   or updater activation. Branch checks/untrusted PRs never receive signing keys.

No production signing secret, protected release environment, publication job or
updater activation is created by Stage 9. Its real Windows workflow exercises the
build/sign/package boundary with an explicitly disposable fixture key instead.
Public source and pinned notices accompany any later GPL frontend distribution.

Recovery runs the verified helper from the external package's payload directory,
never from the installation it will restore. Its frozen libraries must also be
outside the installed directory. The normal installer already extracts this
complete external helper before making changes; manual rollback follows the same
rule. Installed-helper rollback is refused before service/file changes, rather
than trying to replace its own loaded executable or weakening Windows file locks.
Rollback commits owner/sequence metadata with fsync and atomic replacement; it
never copies an older watermark over the current one first. A failed metadata
commit leaves the prior committed floor intact and can be retried by the detached
helper. Explicit history removal recognizes only the runtime's exact reserved
filenames plus its cache subtree; similarly named unrelated files cause refusal
before any history is deleted.

## Verified Stage 9 result — 2026-10-13

Production source: `ca73b3094ddf03cc44c9be2afdd48da138daf202`.
Exact inherited core pin remains
`github.com/Darkaxt/tailscale v1.103.0-pre.0.20261013063423-de6111f507ae`;
its actual `VERSION.txt` is `1.105.0`. The local candidate is `1.105.0+1`, not an
invented upstream version. Subsequent closure changes affect documentation and
observer log capture only, not this product payload.

1. A clean committed-source build produced the frozen windowed owner launcher,
   collector/reader and setup helper; self-contained .NET 10.0.12 Windows host;
   current production Angular assets and collected Python/OpenSSL/pywin32/
   cryptography/.NET/WebView2/frontend notices. The pinned signed inventory covers
   404 files. Python, Node, Go and a developer .NET installation are not needed to
   run the package. Windows x64 with the installed Microsoft Evergreen WebView2
   runtime is the target environment; WebView2 is an explicit system prerequisite,
   not falsely described as a bundled browser runtime.
2. [Windows run 38450846929](https://github.com/Darkaxt/TailD/actions/runs/38450846929)
   passed the actual Inno installer and LocalSystem reader lifecycle: original-owner
   SID/pipe, visible source-unavailable state on the clean host, nondestructive
   preflight, unknown-history refusal, upgrade, replay/tamper rejection, detached
   rollback with preserved watermark, normal uninstall retaining history and
   explicit own-history removal. The independent synthetic Tailscale SCM entry
   and opaque node/signer/provider sentinel remain unchanged at every checkpoint.
   These are actual Windows operations over synthetic account state, not a live
   authenticated tailnet migration. Native interrupted-metadata and signature/
   path/version contracts also pass in that run.
3. The production key signed the real local payload. Independent Inno extraction
   followed by verification against the repository-pinned public key reconciled
   every file, component identity and version. Local installer SHA-256:
   `2897ee645b5505b7c0a64b111fdb7c4d7ddee937e4215524c66d5247bfa481a0`.
   This is a manifest-signed payload; the Windows executables/installer are **not
   Authenticode-signed**. CI fixture signatures are separately labeled and never
   substituted for this production-key check.
4. Actual hook-free Release WebView2 plus the frozen collector loaded Overview
   metrics and navigated to Settings through native UI Automation, with deliberate
   source unavailability and collection disabled. The real screenshot was reviewed;
   no CDP/debug readiness hook, developer runtime, provider credential, source
   connection or live network configuration change was used. Both owned processes
   exited normally. The final native DLL SHA-256 is
   `d9dd024d2defacc43e95da052ad834e086cc5ad2ea0e845da8d4e294ed2139bb`;
   launcher SHA-256 is
   `45a705002a00869a77891c05cb020385b62b89c784edb7af4e0608c16b47d810`.

The single Start menu shortcut opens TailD analytics. The inherited TailDNS tray
continues to own connectivity controls; it is not a competing analytics GUI or
another VPN. This Stage 9 installer adds only analytics and the read-only reader
under `C:/Program Files/Tailscale/TailD`. No in-place connectivity migration has
been selected or performed; matching-core migration and active-client validation
remain explicit Stage 10 obligations before any replacement claim.

R01–R07 retain their recorded public lineage, live provider/source and inheritance
evidence. R08–R16 retain the unchanged source/query/runtime/desktop acceptance in
their owning documents, including the user's physical-outage waiver. R17 and the
pre-delivery R18 requirements are satisfied by the evidence above and the signing
arrangement. No current-stage blocker or tracked deferral remains. Full product
delivery is not complete: release download proof, authenticated migration,
updater activation and real update/interruption recovery belong to Stage 10.

Private local installer/payload and verification evidence are retained outside
GitHub. Superseded outputs are removed through reviewed exact-file cleanup. No
signing identity, requested deliverable, source history or installed client is
part of that cleanup.

## Stage 10 integrated delivery contract — ACTIVE

The October 13 explicit "go ahead" authorizes publication, in-place Windows
migration and updater activation. The Stage 9 analytics-only installer is not
the deliverable for that migration. A v2 package additionally binds the matching
inherited daemon, CLI, resolver, tray, core installer, core provenance/notices and
dedicated signed core manifest in its complete signed inventory.

`core_overlay.py` owns a narrowly reviewed build overlay against exact inherited
core `de6111f507aea869fbf6d4c7b8f2419a79150496`. Its distribution labels, dedicated
ProgramData ownership and fixed signed-installer dispatcher change; DNS, LocalAPI,
connectivity controls, icons and the existing Tailscale service/executable paths
remain inherited. The existing TailDNS run-value name is retained so the migration
does not create competing startup entries. A changed core pin deliberately requires
overlay review rather than applying unchecked string edits to new source.
Go forbids overlays within GOMODCACHE, and its linker reads COFF resources from
the physical source path. Build tooling therefore exports the verified module ZIP
into exact task-owned scratch and generates the installer resource there; it never
edits the shared module cache or maintained TailDNS/core repositories.

`delivery.py` journals signed old/new package identities before mutation, then
coordinates analytics backup/extraction, inherited connectivity activation, reader
setup and user preference restoration. The external verified helper owns recovery.
An interrupted extraction/activation is recovered from the journal and verified
immediate-predecessor records, preserving the anti-replay floor. Manual core update
rollback now restores the preceding update rather than silently returning to the
original migration. Node keys and provider configuration are never copied or edited.
Complete-product uninstall returns to the original pre-TailD connectivity baseline
and original updater preference; it must not leave a TailD daemon whose signed
updater helper was removed. Analytics-only v1 removal remains connectivity-neutral.
Explicit rollback of the first migration invokes the ordinary uninstaller from
the external recovery helper, retaining history and removing its installer
registration. A later update rollback restores its immediate predecessor and
retains the anti-replay floor instead. Recovery gracefully stops any resumed
collector before restoring files, including an interrupted final journal commit.
The actual fresh-host negative migration check exposed Inno's post-install
exception boundary: extraction/registration had committed and setup returned 0
after connectivity failed. Success now requires the complete product transaction;
first-failure recovery uses Inno's own uninstaller for its framework/registration,
only after core restoration. A signed, protected first-migration journal permits
verified partial uninstall to resume without another unmigration or history loss.
See the [Inno event contract](https://jrsoftware.org/ishelp/topic_scriptevents.htm).
This correction passed actual fresh-host verification in run 38468405916.

The frozen collector exposes only an owner/instance-bound maintenance-stop event
to its owner, SYSTEM and Administrators. Updating signals a graceful stop, closes
the owned analytics window and waits for exact process exits; no forced collector
kill, arbitrary sleep or deadline substitutes for transaction completion. The
installer waits for the exact downloading helper PID/start identity to exit before
replacing loaded libraries. A windowless background entry resumes only the recorded
owning user's already-enabled collection; it neither opts in nor opens a window.

The channel accepts only a normal release from Darkaxt/TailD, its exact versioned
asset URL and a pinned-key envelope binding installer size/hash, architecture,
source/core identities and complete package-manifest hash. A partial download is
never executable; replay, upstream downgrade, tamper and wrong-repository assets
are refused. HTTP inactivity limits stay at the transport boundary only.

Run 38468405916 at bde37693a2575b7bd3d5708d18a161a798cffe32 passed complete Windows
build, isolated installer matrix, full-product failed-first-migration recovery and
dedicated protected signing. The exact 1.105.0+1 installer is published normally,
independently downloaded, envelope/hash verified and extracted: all 414 signed
members, source/core/version/architecture and notices match. Installer SHA-256:
`dcfdfde7c5d2f717ef34ea55377c2d8da52d2f54f037f5dcda1910476011fdce`.
Current hook-free Release/frozen-collector Overview -> Settings -> normal close
and reviewed screenshot pass. The serialized CI diagnostic's boolean fields were
null from bare PowerShell literals; the executed assertions/job pass are the proof,
that report is not published, and subsequent source uses real `$true` values.

Authorized Beacon installation passed the elevation gate, full signed installed-
payload matching, node/address/public-signer/service/DNS preference continuity,
and actual public/MagicDNS resolution. Private baseline, installer log and retained
external recovery payload stay outside GitHub. Live installed analytics and real
update/rollback are still required. The October 14 clarification also requires
left-click analytics open/focus and unchanged right-click connectivity controls.
The narrow tray integration reuses Windows window/process/owner identity and the
existing desktop/collector ownership; it adds no alternate UI, RPC or background
schedule. These remaining workflows are Stage 10 advancement blockers.

Live collection exposed an actual Windows status-observer sharing conflict:
atomic diagnostic JSON replacement failed and incorrectly set the source/history
write-error flag. Reproduction holds the real file without delete sharing.
Diagnostic publication now reports its own sanitized health over the authenticated
state API; it does not disable ingestion. Genuine facts/checkpoint write failures
still stop safely. Later core updates also preserve the current auto-update choice
rather than reapplying the immutable pre-migration preference; only the first
migration restores the temporarily disabled choice. Current production verification
of these corrections is required before the next public update.

October 14 native regression correction: dashboard `state`, catalog, query/export
and window lifecycle reads no longer queue behind source acquisition. Queries use
physically read-only SQLite connections to the already-validated owner store;
the one writer and explicit native close receipt remain. The native gated-source
workflow verifies navigation, ingestion notice, close, retained opt-in/reopen and
explicit stop. The diagnostic notice reports real intervals and committed reads,
not percentages or coverage inferred from events. It observes only while visible
and does not alter filters, graph revisions or acquisition. The dashboard PE and
window icon use the unmodified inherited ICO with original resource/hash notice.
Local production frontend/native verification passes; the prior +2 candidate is
superseded. This is not yet proof of an installed/published corrected update.

## Windows packaged-agent verification boundary

An MSIX-packaged diagnostic host can transparently redirect LocalAppData to its
package's LocalCache. The October 14 +7 deployment proved this with
GetFinalPathNameByHandle: ordinary shell reads saw stale history and status,
while the authenticated installed collector read normal physical AppData.
Read-only SQL against that redirected copy produced SQLITE_READONLY_ROLLBACK;
neither journal deletion nor a product fallback addresses the wrong storage view.

Before capturing a live baseline, verify handle-resolved storage paths. For an
unelevated external verifier, obtain the desktop Explorer automation object through
Shell.Application.Windows().FindWindowSW with SWC_DESKTOP and SWFO_NEEDDISPATCH,
then use its Document.Application.ShellExecute. A newly created Shell.Application
object alone can retain the package identity. Use a no-console runtime, a named
completion event, private output and read-only access. Verify the resulting physical
path and actual collector PID; do not infer them from a stale status JSON. Normal
installed desktop launch should use that same unredirected shell boundary.

The +7 actual physical history passes quick_check and includes both new dashboard
indexes. The cached pre-install sample is not a fresh physical baseline and is
not proof of exact before/after history equality. Keep this limitation explicit;
the source benchmark snapshot is likewise not a current-live startup guarantee.
