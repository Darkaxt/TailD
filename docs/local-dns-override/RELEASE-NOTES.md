# TailDNS 1.103.312+28

This release automatically recovers default-resolver queries from provider HTTP
5xx and connection failures through Cloudflare DNS over HTTPS. The saved provider
is tried first on every query and remains unchanged; filtering may be temporarily
bypassed during recovery. MagicDNS, split DNS, valid negative/block answers,
certificate validation and managed policy remain authoritative. Complete network
blackholes can still exhaust the existing request deadline before recovery.

Android continues to follow the retained Android Private DNS provider without a
new switch. The exact core revision and APK signing identity are recorded in the
release provenance and signature assets. The package/signing identity is unchanged
and the version code increases for in-place installation.

For Windows, use the separately authenticated matching daemon/CLI/tray/native
installer release [windows-v1.105.0+31](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.105.0%2B31).
It updates the existing Tailscale directory in place; the legacy companion archive
attached to the Android release is not the supported current Windows installer.

## Historical release notes: 1.103.312+13

This release fixes a Windows startup failure when the existing hosts file is
explicitly read-only. TailDNS now treats that hosts projection as the optional
single-label lookup optimization it is: it preserves the file byte-for-byte,
leaves the read-only attribute intact, logs why the projection was skipped and
continues applying the NRPT/interface DNS configuration. Writable hosts files
retain the upstream update behavior, and unrelated read/write failures remain
fatal instead of being hidden.

The transactional Windows AMD64 in-place upgrade reuses the
existing Windows service pipe and state, preserving the authenticated machine,
tailnet addresses and Tailnet Lock signing key instead of registering a second
node. The official GUI and installed Wintun driver remain compatibility
plumbing; the service executable moves to a versioned TailDNS directory and
official automatic update application is disabled so it cannot overwrite the
fork. Checksum validation, activation verification and automatic rollback are
built into the installer. The included rollback restores the recorded official
service path and prior updater preference without deleting machine state.

The installer now waits on the daemon's authenticated backend state after
service activation instead of treating the earlier Service Control Manager
`Running` notification as LocalAPI readiness.

It also handles repeated Windows GUI reconnect transitions deterministically:
when the resolver preference is saved while the backend is temporarily
restarting, the installer remains gated on authenticated Running transitions
until the exact endpoint is applied. It uses no fixed delay or deadline. A
resolver that reaches any non-transient unapplied state still causes automatic
rollback.

The official upstream Tailscale version remains exactly `1.103.312`; TailDNS
appends only its numeric fork build as `+13`.

The preceding release corrected TailDNS versioning for ObtainX, Obtainium and other
updaters. The official upstream Tailscale version remains exactly
`1.103.312`; TailDNS appends only its numeric fork build. Future
releases use the same standard `+N` form, so their ordering is automatic.

Existing TailDNS installations whose legacy `-taildns.N` version was already
classified as a pseudo version may need this APK installed directly once.
Android treats it as an in-place update because the package, signing identity
and monotonically increasing version code are unchanged. After this transition,
subsequent `+N` releases are updater-comparable.

This release fixes the Android DNS source-selection flow. **Use local default
resolver** is now unavailable until either Follow Android is selected or a
manual HTTPS endpoint has been saved. Follow Android remains an independent,
autosaved choice, and an already configured override can always be switched
off. The backend still rejects invalid updates as a defense boundary.

It retains the AYN Thor Android 13 Clear-all fix from the previous release.
TailDNS task-owning activities remain excluded from Recents so the vendor
launcher cannot select the package for its force-stop path. TailDNS remains
launchable from its icon, Android VPN settings, deep links and shares without a
watchdog, root component, task-lock dependency or device-wide whitelist entry.

The release refreshes the reviewed upstream Android/shared-core revisions
while retaining the independently branded TailDNS behavior. The upstream
Tailscale version component is unchanged; the TailDNS release sequence is
appended only as the standard numeric build component `+N`.

TailDNS automatically
uses the provider hostname saved in Android's Private DNS settings while the
system setting remains **Automatic**. It preserves MagicDNS and more-specific
tailnet routes, fails closed instead of silently changing providers, and reacts
to Android setting changes without requiring a reconnect or an in-app save
button.

This release also includes native Android lifecycle repairs for cold VPN start,
TUN replacement, and Always-on foreground ownership. The verified Thor paths
no longer require Thor Tailscale DNS Guard. The Guard is not bundled or modified;
removing it from a device remains a separate user decision.

The Android APK uses the independent package `io.github.darkaxt.taildns` and can
be installed beside official Tailscale. Android permits only one active VPN per
user. The fork does not import the official app's login. Updates to TailDNS use
the persistent certificate fingerprint documented in `SIGNING.md`.

The Windows AMD64 archive supplies the compatible `taildns` CLI, daemon,
control CLI, in-place installer and rollback path. It does not copy or replace
the proprietary official GUI and is not Authenticode-signed. Verify release
checksums before use.

Known validation limits: the tested Thor network did not provide controlled
IPv6-only, captive-portal, or cellular-handover variants; a second Android
profile and second Windows user identity were unavailable. These paths are not
claimed as tested. The full evidence record is in the repository's
`docs/local-dns-override` directory.
