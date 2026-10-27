# Stage 9 local packaging contract

## October 27 upstream maintenance — normal Windows +36 published

Reviewed core PR 40 passes its exact trusted no-secret checks and merges as
09f44d462b874ba75e175f619a54ae754dfd53b9. Normal core windows-v1.105.0+42
independently verifies through 40461920682. Dependency-only TailDNS PR 30 passes
trusted Android/core/Windows checks; merge a6014591e2e3837f10f2418f058c7ed88c51cc7b
delivers normal v1.103.312+40 through 40464599257. Its package identity, pinned
signer, code 298847410, four native ABIs/exact core and all seven assets verify.

TailD advances matching require/replace/checksums and overlay/build/manifest guards
together. Both independent isolated signer checkouts select reviewed immutable
8b02b92f754b881a5931274a1fc172fd9180f093; all four closure files match in each
job. No signing key or validation logic changes. GitHub inheritance 40465790627
checks Android, DNS, core and Windows contracts and promotes exact
ca48d1874d783c3b66cf0d579441bad830600bb6 with the verified TailDNS parent.
Exact-main focused checks 40467614956 pass.

Normal windows-v1.105.0+36 passes 40467704373, including fresh isolated
install/upgrade/rollback/uninstall and actual complete-product failed-migration
recovery. No earlier installer acceptance is reused for the changed core.
Independent public retrieval verifies pinned release/package/core Ed25519
signatures and key, all 444 payload members, exact source/core provenance,
base 1.105.0/sequence 36/amd64/schema 4, bundled runtimes/notices, native-tested
UI assets and packaged R39 background maintenance in both frozen entrypoints.
Installer: 117,431,212 bytes; SHA-256
ef335e4d0a24775196c4370d2c5c656cfc9118b6c769e3c29f7277b0784c2dd6.
Installer and executables remain Authenticode unsigned.

The three normal releases, exact inherited ancestry and matching shared-core
pins reconcile; inherited release/detection workflows remain disabled. Existing
TailD Android .40 and SleepManager v0.7.3.1 assets remain unchanged and verified;
SleepManager is 17 ahead/0 behind upstream. Earlier verified releases and dirty
sibling work are preserved. No device installation/control, provider-policy write
or B12 acceptance is claimed. Reviewed cleanup removes the exact task scratch
root after compact signed metadata is retained at
D:/Tools/taildns-upstream-verification-20261027. B12 remains separately BLOCKED/open.

## October 25 upstream maintenance — normal Windows +35 published

Two successive GitHub-detected core candidates complete dependency-ordered
promotion. Reviewed core PR 38 and PR 39 pass their exact trusted no-secret checks;
normal core Windows +40 and +41 independently verify. TailDNS exact-core candidates
pass trusted checks and independently deliver Android +38 and +39, preserving the
1.103.312 upstream base, package identity and pinned signer. Latest core is
35f748d736afef777b95496742f0e9c1df9fbdb1; latest TailDNS is
6c8f5860f04d6ce0f1439dffeaa13cf38aee4000 (code 298819400, all four ABIs).

TailD's exact matching require/replace/checksums and overlay/build/manifest guards
advance together. Both isolated signer checkouts select reviewed immutable
572f10434eb418df2bb2891d94784ab777b2a9db; key and signer validation logic stay
unchanged. Actual-ref negative/positive comparisons cover the complete four-file
closure in both signing jobs. GitHub inheritance 40177179178 checks the merged
Android/core/Windows contracts and promotes exact
019f613acd7dbbc5bdc882c9bb8e8d700af61ad0 with the verified TailDNS parent.

Normal windows-v1.105.0+35 passes release 40178064355: full backend contracts,
production Windows build, fresh isolated install/upgrade/rollback/uninstall,
actual complete-product failed-migration recovery, protected canonical signing
and publication. Independent public retrieval verifies pinned release/package/core
Ed25519 signatures and key, all 444 payload members, exact source/core provenance,
base 1.105.0/sequence 35/amd64/history schema 4, bundled runtimes/notices and exact
native-tested UI assets. Packaged R39 startup/background maintenance is preserved
in both frozen entrypoints and the tray resume hook. Installer: 117,433,088 bytes;
SHA-256 8a2ceb491868a6f7cc0f57952ce4ee0736967318662287d0c9ee768a0e65f41e.
Installer and executables remain Authenticode unsigned.

The preceding normal +34 is also independently verified and preserved. Its first
run's old signer core guard correctly fails closed after fresh installer acceptance;
the reviewed immutable-ref correction resumes only through the supported exact
unchanged-product-tree evidence mechanism. The changed core in +35 receives fresh
installer acceptance instead. All six releases from both promotion cycles remain
normal and available; no updater candidate remains. SleepManager is synchronized
with upstream (17 ahead/0 behind), with unchanged verified v0.7.3.1 release assets.
Existing TailD Android .40 stays unchanged. No device installation, provider-policy
write or B12 acceptance is claimed. Dirty sibling work is preserved. Exact helper
cleanup removes the task scratch root after compact signed metadata is retained at
D:/Tools/taildns-upstream-verification-20261025. B12 remains separately BLOCKED/open.

## October 25 R39 Windows startup correction — normal +33 published

Pre-release acceptance verifies native served Connection, Preferences and Analytics
before a held retention operation completes, then its actual completion. Backend
contracts cover committed cutoffs/revisions, all retained read/export surfaces,
bounded cleanup/replay, disabled-source maintenance, quiet retained opt-in startup
and shared Windows startup serialization/failure. Exact pinned-core tray native
tests compile and pass with the changed background-resume hook. Existing tray
sign-in starts the packaged no-console entrypoint; no new scheduled task or opt-in
is introduced. The single writer handles 256 changed rows per maintenance batch
and yields to queued work between batches; idle maintenance opportunities are
60 seconds apart and never cancel operations.

Normal windows-v1.105.0+33 is published from checked source
d443e24659a258d5328850188cdd00422ac4af01 and core
0405247e03f74eb16d26ca8c010c004c7e722db7. Focused source checks 40149387866 and
release 40149393740 pass, including fresh isolated installation/upgrade/rollback,
uninstall and failed-migration recovery, protected isolated signing and publication.
Independent public retrieval verifies pinned Ed25519 release/package/core signatures,
key identity, exact source/core/base/sequence/architecture/schema, all 444 payload
members, bundled runtime/notices, native assets and frozen startup correction in
both entrypoints. Installer is 117,409,495 bytes, SHA-256
c0d3b61c14fd940e603bb72bf80f915f848c3f927d4ec25910156cd075e2a603.
Executables remain Authenticode unsigned; manifest signing does not change that.
The protected-broker-approved in-place installation exits zero. Actual tray
startup resumes TailD.Background.exe with no native window; subsequent normal
installed launch reaches UI Automation-verified Running, enabled refresh and loaded
device inventory in 2.867 seconds while physical retention is still progressing.
Traffic/DNS source reads and live DNS resume successfully; the saved collection
configuration hash is unchanged. Complete installed signed package, node addresses,
Tailnet Lock signer, DNS/context/auto-update/service continuity and real public DNS
and MagicDNS verify. No credentials/settings/history reset or provider policy change
occurred. The window is left open. This verifies the startup correction on the
existing production history without claiming separate B12 rollback acceptance.
Compact private evidence is retained at
D:/Tools/taild-retention39-evidence-20261025.

## October 24 Android .40 and authorized tablet migration

Normal v1.103.312.40 is published from exact checked source
0f1a78a3dd4ed9363793328e747f860db10d7975 and reviewed core
0405247e03f74eb16d26ca8c010c004c7e722db7. Candidate 40124150348 passes
backend/inherited contracts, core checks, Android tests, release lint/build,
TV build and isolated signing. Publication 40126745423 reuses those same bytes.
Independent public verification checks all nine assets, package/version/code,
existing pinned APK certificate, all 643 payload members/four ABIs, exact native
source/core and map/notices. Code 298811510 advances beyond the current TailDNS
origin code 298803600. APK: 107,268,655 bytes; SHA-256
2405d223ee5ae0274d54eb5b8c4c6415abf66c92df544627c7631fed3b73ec48.
Windows latest remains windows-v1.105.0+32.

The fresh isolated native origin run proves the actual TailDNS +37 -> TailD .40
upgrade, node/machine identity, DNS/folder/always-on retention, TailDrop save,
rejected downgrade and exact reinstall recovery. Its final accessibility check
requires a continuation because the fresh Accessibility Suite presents its own
notification prompt and the old assertion expects Control D's removed title.
The supported finalization-only continuation passes actual bound TalkBack focus,
activation and cleanup on that retained candidate. Live automatic light/dark
switching is also verified on the identical signed APK.

External harness corrections are absent from the production APK: select the
TailDNS origin switch beside its exact label while retaining TailD's named-switch
assertion after upgrade; reacquire a Compose scroll container between observations;
provision the owned emulator's Accessibility Suite notification permission; and
verify compact Control D through its existing content resource ID. Preserve the
failed logs separately from the completed acceptance chain.

The user's separate tablet-deployment request authorizes the Samsung SM-X910
in-place replacement. Its pulled installed APK matches the public digest and
certificate; original install time, node/public key/addresses, resolver settings,
always-on/lockdown and enabled accessibility services are retained. Actual public
DNS, MagicDNS and public/tailnet connectivity pass. Analytics stays opt-in. No
uninstall, reset, provider-policy write or production firewall change occurs.
The existing ObtainX entry now targets Darkaxt/TailD with Android-title and exact
APK filters; its real installed/latest .40 readback is Up to date. Both stopped
emulator trees and verification APKs are removed through reviewed exact cleanup.
Private evidence: D:/Tools/taild-tablet-evidence-20261024. This does not close
desktop B12 or claim validation on other physical devices.

## October 24 verified upstream maintenance delivery

Normal windows-v1.105.0+32 is published from exact checked main
9096895162818933ca198b7a795b70ed850ec1e4, containing TailDNS
d2759c12ec5a4fce62aa1705c60730210ba7d185 and reviewed shared core
0405247e03f74eb16d26ca8c010c004c7e722db7. Inheritance 40069426036 passes
after resolving the upstream LocalAPI initialization change beside TailD's scoped
TailDrop callback. The same lazy scope expression now supplies the existing
ShareFileHelper default; transfer/history behavior and injected providers remain.
Inherited Android/core/Windows checks pass on the exact promoted candidate.

Release 40070702921 passes full backend, Windows production, fresh isolated
install/upgrade/rollback/uninstall and failed-migration recovery gates, isolated
signing and publication. Signer tooling 0853242 retains pinned keys and canonical
verification, changing only the reviewed core identity constants.

Independent public download/extraction verifies every one of 444 package members,
release/package/core Ed25519 signatures, exact source/core/version/architecture,
schema 4, runtime identities/notices, frozen app-DNS modules and identical native
R38 JS/CSS assets. Installer: 117,401,367 bytes; SHA-256
bf39d535c9067902f7a234b01ff1d9b9a68977c1aa2b5a32e48a3a39c998a0be.
Executables and installer remain not Authenticode-signed. No local deployment or
physical B12 rollback/final reconciliation is claimed by this maintenance cycle.

Preceding independently verified releases are TailDNS Windows
windows-v1.105.0+39 and Android v1.103.312+37 (existing package/certificate,
code 298803600, all four libraries/exact core and all seven assets). SleepManager
v0.7.3.1 and TailD Android v1.103.312.39 remain unchanged. Evidence:
D:/Tools/taildns-upstream-verification-20261024.

## October 23 verified upstream maintenance delivery

Normal windows-v1.105.0+31 is published from exact checked main
4d6b0bfb1c0500d4c4c7761bfd1ee4f3d9400b59, containing TailDNS
398717c48e9c5320fc9fdf4b9da13881f667ab6b and reviewed shared core
2836228acf7f6b37554d913c8241d294aaf93d24. Inheritance 39910627501 and
full release 39912774748 pass, including fresh isolated installer, upgrade,
rollback, uninstall and failed-migration recovery gates. Immutable signer tooling
9adb977 changes only reviewed core identity constants in the signer closure;
key pins, isolated authority and canonical verification remain unchanged.

Independent public download and extraction verify all 444 payload members,
release/package/core Ed25519 signatures, exact source/core/architecture/schema 4,
bundled runtime identities/notices, frozen app-DNS modules and identical native
R38 JS/CSS assets. Installer: 117,401,165 bytes; SHA-256
7eec581e31e4323f782d6df54ef46e726bddaac7ae71f453dd2ddd0c7c14f2a9.
Executables and installer are not Authenticode-signed. No device deployment or
real B12 rollback/final reconciliation is claimed by this automated cycle.

Preceding independently verified releases are TailDNS Windows
windows-v1.105.0+38 and Android v1.103.312+36 (existing package/certificate,
code 298789240, all four native libraries with exact core and all seven assets).
SleepManager v0.7.3.1 and TailD Android v1.103.312.39 remain unchanged.
Compact evidence: D:/Tools/taildns-upstream-verification-20261023.

## October 22 Windows app-domain delivery

Normal windows-v1.105.0+30 delivers R38 from exact source
4cf466c7998210664a8a6c29a726ae78e6b3a175. Successful workflow 39853099554
includes fresh installer/upgrade/rollback/uninstall and failed-migration refusal
gates. Independent download verifies all 444 payload members, pinned Ed25519
release/package/core manifests, unchanged exact core 3fe3e22e43e6, schema 4,
bundled runtime identities/notices, frozen app-DNS modules and exact native-tested
JS/CSS. Installer size: 117,401,678 bytes; SHA-256:
9cda36c0f05a997c9a9d58b6681776531fdfb1e3cfab9681b86f501e24b13e90.
Executables remain without Authenticode signatures. Evidence:
D:/Tools/taild-windows-appdns40-evidence-20261022. No local installation or B12
real rollout/rollback acceptance is claimed. Android is unchanged.

## October 22 verified upstream maintenance delivery

Normal windows-v1.105.0+29 is published from exact checked main
a519e8331eee4bf317aecc1e645bc77e64e22635, containing TailDNS
7fe05ea6cdcdd6852d5a6bba8e4ccf3eb1642268 and shared core
3fe3e22e43e60d2ddb8378be418b78e810c310e5. Inheritance 39732945620 and full
release 39735041474 pass with fresh isolated installer/upgrade/rollback/uninstall
and failed-first-migration recovery gates. Immutable signer tooling is 21cde9b;
production-key isolation, canonical manifests and the TailD channel are unchanged.
Independent public extraction verifies all 444 package members, release/package/
core signatures and key identity, exact source/core/architecture/history schema,
runtime notices and identical native R36 JS/CSS assets. Installer: 117,328,339
bytes; SHA-256 efe5d60c23132620998a95ec3b047a92068b695613e72976369748e11b69b0c7.
The installer and product executables are not Authenticode-signed.

Preceding dependency releases are independently verified TailDNS Windows
windows-v1.105.0+37 (all five matching-core binaries and pinned Ed25519 manifest)
and TailDNS Android v1.103.312+35 (existing APK package/certificate, code 298774800,
four native libraries with exact core/module provenance, all seven assets and
companion Windows payloads). TailD Android v1.103.312.39 and SleepManager
v0.7.3.1 assets are unchanged. No device installation, provider change or real B12
acceptance is claimed. Evidence: D:/Tools/taildns-upstream-verification-20261022.

## Android R37 distribution contract (October 20)

October 21 authorized version correction: new Android names/tags use
`<upstream Android base>.<sequence>` / `v<upstream Android base>.<sequence>`.
The inherited three-component base and native runtime VERSION_SHORT/LONG stay
unchanged; only the Android product suffix separator changes. Continue sequence
and versionCode monotonicity across historical `+N` and new `.N` releases, retaining
their artifacts. The inherited TailDNS formatter still defaults to `+`; TailD's
version wrapper explicitly selects `.`. Windows retains its `windows-v...+N`
format, package/signing channel and latest-release designation.

The separate native Android deliverable is governed by the
[Android specification](ANDROID-EXPANSION-PROPOSAL.md). Keep application ID
`io.github.darkaxt.taildns`, existing connect/disconnect intents and the existing
TailDNS APK certificate; TailD branding and update/release origin are fork-specific.
Do not change the Windows package channel or enable inherited signing workflows.
Android builds/checks use no signing secrets. A separate isolated signing job
must use the protected existing certificate, and publication must identify the
exact checked source/core, true upstream Android base, monotonic versionCode and
TailD Android sequence. Verify the independently downloaded normal release APK,
certificate, manifest/version, ABI payloads/provenance, checksums and notices.
The implementation's final release is authorized; a physical deployment requires
its applicable authority and evidence. Existing Windows evidence below is not
Android signing, upgrade or lifecycle evidence.

The first TailD Android sequence continues after inherited TailDNS +33 as +34;
the upstream Android base remains 1.103.312. `TAILD_ANDROID_SEQUENCE.txt` records
the chosen sequence; versionCode is derived deterministically from the exact
source commit epoch using the inherited reserved-platform-digit contract.
Candidate signing uses only the existing certificate in the main-scoped
`taild-android-release` environment. `taild-android-release.yml` first builds and
signs an unpublished candidate; publication reuses that successful same-source
run after isolated delivery acceptance. Publication requires the exact main tag,
increasing Android codes/sequences and normal release state, with `--latest=false`
to preserve the Windows latest-release channel. It never checks out repository
code in a signing or publication job. Android recovery acceptance covers a
nondestructive rejected downgrade and reinstallation of the exact verified
candidate, preserving identity, settings, retained history and Keystore access;
it does not claim a physical-device rollback or close desktop B12.

Verified first Android delivery: v1.103.312+34, code 298751830, source
0f7d1ad6b993d3efbf68757ba962b71f110dddb1 and core
28b0deb7805710f50689f4aa133ed911f74e504d. Candidate 39451115770 and publication
39466380329 preserve the same tested APK bytes. Independent public verification
checks all nine assets, pinned signer and 636 payload members across four ABIs.
Previous Android correction delivery: v1.103.312+35, code 298753760, exact source
54a265e2dd27b6fae369d80ed60cb529327f4ad4 and unchanged core above. Candidate
39479150613 and normal publication 39481591655 preserve the same tested bytes.
Independent public verification covers nine assets, the existing certificate,
638 payload members and all four ABIs. Native +34 -> +35 identity continuity,
phone/rail light/dark search/navigation, rejected downgrade and reinstall pass;
the external harness-only assertion correction is documented separately from
the production APK source. The current reconciliation and physical-device
limits are in IMPLEMENTATION-PLAN.md.

Current numeric-version delivery: v1.103.312.36, code 298762150, source
d71dddeda9422163e550a721ea5f9d2932ad323f and core
d9c112d927479d092f6d1132e16613f046f6ba51. Candidate 39572906227 and normal
publication 39578304804 contain identical bytes. Independent public verification
covers all nine assets and 638 APK members across four ABIs, with the unchanged
signing certificate. APK SHA-256:
cda34a8cab94238f01c93e8ca45d942d34753614dca6a26e54c6f2cdc8aba7ac.
The initial native run owns verified +35 -> .36 identity continuity. It exposed
a test-only Back/IME race on the wide layout; a keyboard-visible condition in the
self-targeted harness fixes that test. The resumed unchanged candidate passes
all four phone/rail theme captures, search/clear, downgrade refusal and reinstall.
This harness-only change is recorded after publication and is absent from the
production APK; no production behavior was patched to hide a test failure.

Current Geography/firewall/traffic delivery: v1.103.312.37, code 298766040,
source 3f486dc847f1f3fee8f1b70fa3f5201c2df50991 and unchanged core
d9c112d927479d092f6d1132e16613f046f6ba51. Candidate 39625376476 and publication
39629850389 preserve identical signed bytes. Independent public verification
covers all nine assets, 643 APK members and four ABIs, the unchanged certificate,
map and exact ShizuWall/Shizuku notices. APK SHA-256:
8ce07eaa6a513055f7e3c33d701a557a4bd511c907b6ba2dafe258d5d69a6e4e.
The actual installed isolated-emulator APK has that same digest. The initial run
verifies .36 -> .37 identity/always-on continuity and phone/rail theme/navigation
before a later test-only exact-text assertion fails. Corrected external harness
continuation passes real shared-UID enforcement/readback/unblock, real VPN
app/DNS/byte export, auto-dark, rejected downgrade, exact reinstall and retained
traffic/identity. Harness corrections are not APK changes. No physical-device
installation or OEM acceptance is implied; Windows B12 and F1/F3 remain open.

Current Firewall analysis delivery: v1.103.312.39, code 298770200,
source 705f03f164ca4a6301429996c975e3e174271527 and unchanged core
d9c112d927479d092f6d1132e16613f046f6ba51. Candidate 39685819513 and normal
publication 39688312816 preserve identical signed bytes. Independent public
verification checks all nine assets, 643 APK members across four ABIs, the exact
source/core and existing pinned certificate. APK SHA-256:
a7c6577349b8fbda62fbd3a38790d9107fc548e02d90473a7a33cfe3f0a686fc.
The fresh isolated .38 -> .39 run passes retained identity/settings/file/history,
phone/rail and large-text automatic themes, real shared-UID block/restore,
measured VPN traffic, Vico diagnosis chart/tables with IN/OUT labels, SAF export,
downgrade rejection and exact reinstall recovery. Additional signed checks pass
app-only 24-hour export, zero-data current installation and retained historical
package metadata. The external historical-dialog assertion now uses its visible
title: the internal Compose tag is not exported as an Android resource ID in that
popup. This is a post-candidate harness-only correction, absent from the APK;
no production behavior changed to pass the test. Evidence and retained captures:
D:/Tools/taild-firewall39-evidence-20261021. Windows latest remains
windows-v1.105.0+28. No physical-phone deployment or desktop B12 acceptance is
claimed.

## Historical Windows Stage 9 contract

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
