# Safe upstream update pipeline

TailDNS separates detection, candidate integration, validation, signing and
release. An upstream change never replaces the last verified release merely
because it merged or compiled.

## Daily flow

1. The shared-core fork checks canonical `tailscale/tailscale` first. When its
   `main` branch is behind, it composes
   `automation/upstream-core` and opens or updates a pull request. It does not
   execute merged upstream code and has no signing secret.
2. The Android fork later checks canonical `tailscale/tailscale-android` and
   the reviewed head of `Darkaxt/tailscale:main`. It composes
   `automation/upstream-candidate`, updates the exact Go-module pin when needed,
   and opens or updates a pull request.
3. The updater explicitly dispatches a trusted default-branch check for the
   exact candidate ref. Candidate code executes with read-only repository
   access and no signing or release authority. The checks cover the affected
   core suites, Android formatting/tests/release assembly, and Windows
   cross-compilation. A candidate-branch push trigger also validates later
   human fixes without granting write or secret access.
4. The task-attached monitor reviews exact heads and passing checks, promotes
   core before Android, then creates the next owner-controlled release tag on
   the exact merged Android commit. The tag-bound workflow alone receives the
   signing identity and publication permission. The monitor independently
   downloads and verifies the release; it never controls a device. The release
   keeps upstream `VERSION_SHORT` unchanged and appends only the numeric TailDNS
   build sequence as `+N`.

The core schedule is 02:17 UTC daily and the Android schedule is 04:17 UTC
daily. Manual dry runs detect and compose locally but deliberately push no
branch or pull request.

## Failure containment and recovery

The detector permits automatic Go toolchain selection only while tidying and
inspecting the newly pinned, reviewed core module. This lets a core Go patch
upgrade update the Android `go` directive before the trusted candidate and release
jobs select their toolchain from `go.mod`. The exact module pin/replacement and
fork Go revision synchronization remain checked. This fixes the 2026-10-10
detector failure (run 38080590240): core required Go 1.27.2 while Android's base
runner was Go 1.27.1 with `GOTOOLCHAIN=local`. No failing candidate was promoted.

A merge conflict, module-resolution failure, test failure or build failure
leaves the current `main`, persistent signing key and published release
unchanged. Never bypass a failing check, expose signing secrets to the
candidate, or tag the candidate directly.

To recover, inspect the failed run and candidate diff, fix only the bounded
compatibility problem on the automation branch, and rerun its read-only checks.
If the candidate is unsuitable, close the pull request and delete only its
`automation/upstream-*` branch. Rerunning the detector recreates the branch from
the current trusted base. Rollback of a mistakenly merged but unpublished
candidate uses an ordinary reviewed revert; the last release remains available.

Signing continuity is independent of the updater. The certificate and recovery
procedure in [SIGNING.md](SIGNING.md) remain authoritative. A new upstream
revision does not authorize key rotation, silent acceptance-criteria changes,
automatic device mutation or a release.

## Enabled rehearsal and monitor evidence

On 2026-09-19, core and Android dry runs detected and composed their current
upstream inputs without creating branches, pull requests or releases:
[core run 35400995349](https://github.com/Darkaxt/tailscale/actions/runs/35400995349)
and [Android run 35400997742](https://github.com/Darkaxt/TailDNS/actions/runs/35400997742).

The real core updater [run 35401383779](https://github.com/Darkaxt/tailscale/actions/runs/35401383779)
opened [core PR 1](https://github.com/Darkaxt/tailscale/pull/1), whose exact
candidate passed trusted read-only [run 35401479720](https://github.com/Darkaxt/tailscale/actions/runs/35401479720).
The real Android updater [run 35401972916](https://github.com/Darkaxt/TailDNS/actions/runs/35401972916)
opened [Android PR 1](https://github.com/Darkaxt/TailDNS/pull/1), whose
exact candidate passed trusted read-only [run 35402092785](https://github.com/Darkaxt/TailDNS/actions/runs/35402092785).
Those initial pull requests demonstrated detection and validation while the
published release remained unchanged.

The first core bot dispatch exposed an actor-boundary mistake and skipped the
check. The trusted dispatcher was restricted to the exact automation actor and
candidate ref, then the updater and candidate checks were rerun successfully.
This rehearsed failure containment and recovery without exposing secrets,
disabling checks or publishing the candidate.

The completed promotion rehearsal then merged core PR
[1](https://github.com/Darkaxt/tailscale/pull/1) as
`f5de5ace94bb3fb21794d1e10184029709242aa0`, refreshed Android PR
[1](https://github.com/Darkaxt/TailDNS/pull/1), and passed exact-candidate run
[35455837978](https://github.com/Darkaxt/TailDNS/actions/runs/35455837978).
Two earlier Android candidate attempts failed safely on a core Go-toolchain
pin mismatch and a missing deterministic module download; neither was merged
or published. After bounded repairs, Android merged as
`ab93b54cbccd3e148ebd53b3d943548f9e85960b` and release run
[35456966765](https://github.com/Darkaxt/TailDNS/actions/runs/35456966765)
published and verified
[v1.103.312-taildns.3](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312-taildns.3).

Both public forks were reduced to the canonical `main` branch. The core fork's
1,275 inherited branches and five regenerated Dependabot branches were removed;
inherited static workflows and dependency-PR creation were disabled so the two
TailDNS core candidate workflows remain the only fork-owned Actions surface.

The task-attached heartbeat `monitor-taildns-upstream-updates` runs daily at
08:30 UTC. It stays quiet while healthy and unchanged; it owns exact-head
review, dependency-ordered merge, monotonic `v<VERSION_SHORT>+N`
release, independent verification and bounded pipeline repair. It cannot rotate
the signer, change tailnet registration or control a device.

On 2026-09-23 the same heartbeat was updated in place rather than duplicated.
Its dependency order is now explicit: merge an exact checked core candidate,
publish the next `windows-v<VERSION_SHORT>+N` from that exact core commit, wait
for isolated signing, and independently verify the signed update manifest,
installer and complete daemon/CLI/resolver/tray set before refreshing Android.
Only then may it merge the exact-core Android candidate, publish the next
`v<VERSION_SHORT>+N` APK release and independently verify package, version,
signer, checksums, branding and embedded-core provenance. It preserves the last
verified releases on failure, performs no Windows or Android device deployment,
and notifies only for a completed promotion, genuine unrecoverable blocker or
required user action.
