# TailD

TailD is the public analytics-development fork of [Darkaxt/TailDNS](https://github.com/Darkaxt/TailDNS).
It retains TailDNS main history and automatically merges checked TailDNS updates,
including Android DNS improvements and the pinned shared core containing the
Windows tray/UI port. GitHub permits only one native fork in this account's
upstream network, so this is a history-preserving Git fork rather than a second
GitHub fork badge.

The planned extension combines Control D policy/decision data with application
identity and network-byte metrics. Control D and existing firewall products keep
their enforcement roles. No new packet-filtering engine is being implemented.

There is **no TailD release or installed analytics UI yet**. The inherited client
still uses the TailDNS app/package identity. Existing TailDNS installations,
update endpoints, signing keys and maintenance tasks are unchanged. The inherited
status material below describes TailDNS, not verification of TailD analytics.

The first read-only development command is implemented and verified against a
real Control D account: device/profile inventory, analytics-region discovery and
DNS-decision reads. Elevated read-only inspection has now established a narrow
GlassWire application/destination/network-byte source, with binary-field checks
against Windows' process/TCP table. The actual joined Control D record remains
unfinished; GlassWire's time-bucket counters are not proven individual PID/socket
bytes. AppControl's current MCP does not expose network-byte counters.
See the staged plan for exact status.

- [TailD authoritative specification](docs/taild/SPECIFICATION.md)
- [TailD stages, acceptance evidence and blockers](docs/taild/IMPLEMENTATION-PLAN.md)
- [Read-only Control D command and verified boundaries](docs/taild/CONTROL-D-READS.md)
- [GlassWire read-only source evidence and limitations](docs/taild/GLASSWIRE-READS.md)
- [Original analytics capability record](https://github.com/Darkaxt/TailDNS/issues/9)

## Inheritance and development

The **Inherit TailDNS improvements** workflow runs daily at 04:25 UTC and can be
run manually. It merges TailDNS main, checks the exact shared-core pin, verifies
TailD and inherited contracts, builds Android/core when source changes, then
promotes the checked Git commit to main. Conflicts or failed checks stop promotion
with a failed GitHub run; passing updates are not left as unmerged candidates.
Main is never force-pushed. Verification has no signing credentials and a separate
write job only promotes the checked candidate. No release/deployment is automatic.

Inherited TailDNS workflows are retained as source but disabled in TailD's GitHub
settings. A newly inherited workflow requires review before promotion.

```sh
python -B -m unittest discover -s scripts/taild -p 'test_*.py' -v
git remote add taildns https://github.com/Darkaxt/TailDNS.git  # if not already configured
git fetch --no-tags taildns main:refs/remotes/taildns/main
python -B scripts/taild/inherit.py
```

The last command prepares a merge in a **clean** checkout; it never pushes. The
Windows UI code is not duplicated here: `go.mod` inherits TailDNS's exact
`github.com/Darkaxt/tailscale` require/replace revision.

## Inherited TailDNS documentation

TailDNS is an independent community fork of [tailscale/tailscale-android](https://github.com/tailscale/tailscale-android), maintained by [Darkaxt](https://github.com/Darkaxt). This project is not an official Tailscale product or endorsed by Tailscale.

## Fork status

**Stages 3–8 and 10–12 are complete; Stage 9 is blocked only on the disconnected Fold, and Stage 1's unavailable network variants plus Stage 2's prohibited device-input action remain disclosed validation gaps under specification 2.9.** The exact integrated Android/core revisions passed the GitHub build and focused suites, isolated signing, independent artifact verification and the Guard-disabled Thor matrix. UI-closed provider changes fail closed, retain MagicDNS and recover without reconnecting; cold/system Always-on starts, Wi-Fi transitions, exit-node changes, observer recreation and foreground protection passed. On Windows, Beacon now runs the independently implemented TailDNS tray plus a matching current-core daemon/CLI/resolver set in the existing automatic service, preserving its authenticated node, addresses, Tailnet Lock signer, Wintun and Control D/public/MagicDNS behavior. The signed TailDNS updater completed a real unattended `windows-v1.103.0+17` to [`windows-v1.103.0+18`](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.103.0%2B18) transition and safely rejected a replay; the tray uses the exact preserved official multi-resolution state icons, including their native transparency. The current Android release is [TailDNS 1.103.312+18](https://github.com/Darkaxt/TailDNS/releases/tag/v1.103.312%2B18). Both release lines preserve their upstream Tailscale version and append only a monotonic numeric TailDNS build. The task-attached monitor promotes exact checked core first, publishes and independently verifies Windows, then promotes exact-core Android and publishes/verifies Android; it remains quiet while current and performs no device deployment.

TailDNS is the product identity. Upstream technical identifiers such as the `com.tailscale.ipn` source namespace, `tailscale.com` Go module, Tailscale service/API URLs, protocol feature names, and original license/copyright/trademark notices remain where required for compatibility, truthful attribution, and maintainable upstream merges; they do not identify the installed app or published release as an official Tailscale product.

The proposed feature lets a device choose its own DNS-over-HTTPS resolver, including a Control D endpoint/client, while preserving Tailscale's MagicDNS and applicable split-DNS routes. It does not require editing tailnet policy or changing other devices.

Specification v2.9 also requires native Android DNS/service lifecycle and AYN recent-task fixes intended to make **Thor Tailscale DNS Guard unnecessary**, with real Thor verification while the Guard is disabled. The Guard is evidence of failure scenarios, not a component to improve or embed. Native cold-start, TUN-replacement, Always-on foreground and Clear-all resilience are implemented and their accessible Thor paths pass without Guard assistance. External root `SIGKILL` remains outside an in-process application's recovery guarantee and is not replaced with another watchdog. Automated device validation uses Thor; the user tests the full release on the Samsung phone. Signing, release and the task-attached promotion monitor are active only after their verification gates.

- [Authoritative specification](docs/local-dns-override/SPECIFICATION.md): required behavior, precedence, platform boundaries, and acceptance criteria.
- [Implementation evaluation](docs/local-dns-override/EVALUATION.md): source-backed corrections to the original recommendation and unresolved runtime evidence.
- [Staged implementation plan](docs/local-dns-override/IMPLEMENTATION-PLAN.md): requirement mapping, exact stage status, verification evidence and remaining gaps.
- [Signing identity and validation workflow](docs/local-dns-override/SIGNING.md): independent TailDNS package, public certificate fingerprint, key custody and validation-only artifacts.
- [Windows deployment and validation](docs/local-dns-override/WINDOWS-VALIDATION.md): isolated-daemon proof plus the current in-place upgrade, preservation and rollback evidence.
- [Final R01–R22 reconciliation](docs/local-dns-override/FINAL-RECONCILIATION.md): exact integrated revisions, requirement evidence and disclosed validation gaps.

On Android, the setup keeps system Private DNS at **Default/Automatic** while Tailscale is active. Opt-in **automatic propagation** follows the saved hostname, not `isPrivateDnsActive()` or `getPrivateDnsServerName()`, without repeated imports or reconnects. UI-closed propagation and invalid-to-valid recovery were demonstrated on Thor Android 13, target SDK 36, without privileged app grants. Provider mappings require documented semantics. Control D and a generic manual DoH endpoint have real-query evidence; native DoT is not implemented.

This Android repository owns the specification and Android integration. The [shared Go-core fork](https://github.com/Darkaxt/tailscale/tree/main) contains the resolver path, independently implemented TailDNS Windows tray, matching CLI/daemon, transactional installer and signed updater. The proprietary official Windows GUI code is not copied; the preserved installed binary is rollback/provenance material while the TailDNS tray is active. Production packaging, publication and independent release verification are recorded in [RELEASE-VALIDATION.md](docs/local-dns-override/RELEASE-VALIDATION.md) and [WINDOWS-VALIDATION.md](docs/local-dns-override/WINDOWS-VALIDATION.md).

## Upstream client documentation

The material below describes the upstream client. Download links point to upstream/distributor builds, **not** builds containing this proposal. Existing build and release instructions are retained for reference; this documentation publication does not create or authorize a release.

https://tailscale.com

Private WireGuard® networks made easy

## Overview

This repository contains the open source Tailscale Android client.

## Using

#### Tailscale Packages

The latest stable release APK can be obtained from the [Tailscale Packages Stable Track](https://pkgs.tailscale.com/stable/#android).

Unstable releases can be obtained from the [Tailscale Packages Unstable Track](https://pkgs.tailscale.com/unstable/#android).

These APKs include all supported platforms and architectures.  For installing compact APKs, Android TV, or if you want automatic updates, visit the [Google Play Store](https://play.google.com/store/apps/details?id=com.tailscale.ipn).

#### Google Playstore

[<img src="https://play.google.com/intl/en_us/badges/images/generic/en-play-badge.png"
     alt="Get it on Google Play"
     height="80">](https://play.google.com/store/apps/details?id=com.tailscale.ipn)

Help us test new features and bug-fixes before they ship to all users! A [beta testing track](https://play.google.com/apps/testing/com.tailscale.ipn) is available on the Play Store. 

#### Amazon Appstore

The app can be downloaded from the [Amazon Appstore](https://www.amazon.com/dp/B0D38TRB3N) for Amazon Fire tablets and Fire TV devices.

#### F-Droid

The [F-Droid](https://f-droid.org/packages/com.tailscale.ipn/) project builds the source code in this repository and maintains independently-built APKs. Note that F-Droid builds are not released, updated, or verified by the Tailscale team.

## Preparing a build environment

There are several options for setting up a build environment. The Android Studio
path is the most useful path for longer term development.

In all cases you will need:

- Go runtime
- Android SDK
- Android SDK components (`make androidsdk` will install them)

### Android Studio

1. Install a Go runtime (https://go.dev/dl/).
2. Install Android Studio (https://developer.android.com/studio).
3. Start Android Studio, from the Welcome screen select "More Actions" and "SDK Manager".
4. In the SDK manager, select the "SDK Tools" tab and install the "Android SDK Command-line Tools (latest)".
3. Run `make androidsdk` to install the necessary SDK components.

If you would prefer to avoid Android Studio, you can also install an Android
SDK. The makefile detects common paths, so `sudo apt install android-sdk` is
sufficient on Debian / Ubuntu systems. To use an Android SDK installed in a
non-standard location, set the `ANDROID_SDK_ROOT` environment variable to the
path to the SDK.

If you installed Android Studio the tools may not be in your path. To get the
correct tool path, run `make androidpath` and export the provided path in your
shell.

#### Code Formatting

The ktmft plugin on the default setting should be used to autoformat all Java, Kotlin
and XML files in Android Studio.  Enable "Format on Save".

### Docker

If you wish to avoid installing software on your host system, a Docker based development strategy is available, you can build and start a shell with:

```sh
make docker-shell
```

Several other makefile recipes are available for setting up the proper build environment and running builds.

Note that the docker makefile recipes s will preserve the image and remove container on completion.
If changes are made to the build environment or toolchain, cached docker images may need to be rebuilt.
The docker build image name is parameterized in the makefile and changing it provides a simple means to do this.

### Nix

If you have Nix 2.4 or later installed, a Nix development environment can
be set up with:

```sh
alias nix='nix --extra-experimental-features "nix-command flakes"'
nix develop
```

The flake provides host tools such as Java, `make`, `curl`, and `git`, and
points the build at a repo-local Android SDK in `./android-sdk`. The SDK
directory is ignored by Git and is reused across builds.

On first use, install the Android SDK components:

```sh
make androidsdk
```

Then build normally:

```sh
make tailscale-debug
```

The debug APK is written to `./tailscale-debug.apk`.

For one-shot commands without entering an interactive shell:

```sh
nix develop --command make androidsdk
nix develop --command make tailscale-debug
```

For faster Kotlin-only iteration while avoiding the `gomobile bind` step:

```sh
nix develop --command bash -lc 'cd android && ./gradlew ktfmtCheck compileDebugKotlin'
```

## Building

```sh
make apk
make install
```

## Building a release

Use `make tag_release` to stamp the Play Store version code, update the version
name, and tag the current commit. The version code is derived from wall-clock
time (minutes since the Unix epoch) at release time and committed into
`android/build.gradle`, so it increases monotonically across all builds and
branches while staying fixed for any given commit.

We only guarantee to support the latest Go release and any Go beta or
release candidate builds (currently Go 1.14) in module mode. It might
work in earlier Go versions or in GOPATH mode, but we're making no
effort to keep those working.

## Developing on a Fire Stick TV

On the Fire Stick:

* Settings > My Fire TV > Developer Options > ADB Debugging > ON

Then some useful commands:
```
adb connect 10.2.200.213:5555
adb install -r tailscale-fdroid.apk
adb shell am start -n com.tailscale.ipn/com.tailscale.ipn.MainActivity
adb shell pm uninstall com.tailscale.ipn
```

## Bugs

Please report this fork's specification or implementation issues in the
[TailDNS issue tracker](https://github.com/Darkaxt/TailDNS/issues).
Problems reproducible in an unmodified upstream client, or with the hosted
service, belong in the [Tailscale issue tracker](https://github.com/tailscale/tailscale/issues).

## Contributing

`under_construction.gif`

PRs welcome, but we are still working out our contribution process and
tooling.

We require [Developer Certificate of
Origin](https://en.wikipedia.org/wiki/Developer_Certificate_of_Origin)
`Signed-off-by` lines in commits.

## Upstream attribution and license

The original client is developed by [Tailscale](https://tailscale.com).
See [Tailscale's company information](https://tailscale.com/company) for details.
The upstream [BSD 3-Clause license](LICENSE) and copyright notices are retained.
This fork does not claim ownership of upstream trademarks.

WireGuard is a registered trademark of Jason A. Donenfeld.
