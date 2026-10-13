# Stage 9 local packaging contract

Stage 9 is ACTIVE; no installer or release is accepted yet. It has no authority to
replace the active client or activate an updater. Stage 8's native UI acceptance
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

Remaining acceptance work: hook-free Release offline launch, complete collected
license/provenance inventory; fixed-owner reader setup; installer/upgrade/uninstall/
rollback and node/service/Tailnet Lock state preservation in isolated Windows;
dedicated pinned-key signing and tamper/replay/version contracts; credential-free
GitHub candidate checks and isolated signing/release workflow design; integrated
R01–R17/pre-delivery R18 reconciliation. None is hidden as a passed Stage 8 test,
an open-ended deferral or an installed release.

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
