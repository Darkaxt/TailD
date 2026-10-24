# TailD for Android

TailD expands the inherited TailDNS Android client with native Tailscale device
views and observations, Control D DNS history and basic management, and a private
seven-day Dashboard. It follows Android's automatic light/dark theme.

Current release: [1.103.312.40](https://github.com/Darkaxt/TailD/releases/tag/v1.103.312.40)
([APK](https://github.com/Darkaxt/TailD/releases/download/v1.103.312.40/taild-android.apk)).
The public package, existing signer, source/core identities and all payload hashes
were independently verified. In-place upgrade and recovery checks used an isolated
emulator. The authorized Samsung SM-X910 in-place upgrade from TailDNS +37 also
preserved its identity, DNS settings and connectivity. Other devices require
their own deployment evidence.

This release includes current inherited core updates, a compact offline Geography
map, optional Shizuku app control and 24-hour IN/OUT app traffic in Firewall.
Diagnosis opens hourly charts and destination/DNS tables; Dashboard Applications
also remains available. Numeric versions
continue to support ObtainX ordering. Phone/tablet layouts follow automatic system
light/dark mode.

New Android releases use tags `v<upstream Android base>.<TailD Android sequence>`
and the same four-component numeric APK versionName without the `v`. This makes
the TailD sequence participate in ObtainX's version ordering rather than being
discarded as `+` build metadata. Historical `+34`/`+35` releases remain unchanged.
Windows releases use `windows-v...` and remain on their existing update channel.
Filter Android update tools by release title `^TailD Android ` and the
`taild-android.apk` asset; do not use the repository's Windows latest-release URL
as an Android package feed. Enable fallback to older releases so newer Windows
releases do not hide the latest Android release. Installed-version detection stays
Standard, without pseudo tracking or version trimming. Downloads and update origin belong to
[Darkaxt/TailD](https://github.com/Darkaxt/TailD/releases).

The application ID remains `io.github.darkaxt.taildns`, with the existing TailDNS
certificate SHA-256:
`dcd0ede91eb7e0ed88a72b5289f84f8d4a61ccc22707f36378e15540b99d32e1`.
Installing TailD therefore updates the existing TailDNS application and preserves
its app data; these two forks cannot be installed side by side under that ID.
The official Tailscale application keeps its separate package and compatibility.

Keep data when updating. Android rejects lower version codes and different
certificates; never work around that by silently uninstalling the application.
Recovery uses a verified update with the same signer and a higher version code.
Existing DNS, profiles, node identity and SleepManager disconnect/restore intent
contracts remain inherited. Android lifecycle and real-device continuity require
their own evidence; emulator checks do not establish validation of your phone.

Analytics is opt-in and retains seven days locally. Provider DNS records and local
Tailscale/TailDrop observations have separate scopes and coverage. Recording off
preserves retained facts; an explicit recent provider read can display transient
data. Catch-up has no additional periodic job or permanent DNS stream. DNS data
does not measure app bandwidth or establish which app opened a connection.

Configure separate READ access in Control D. Optional Write access remains
separate; adding credentials does not change DNS configuration or provider policy.
Confirm the exact endpoint/client rather than inferring it from a device name.
Allow/Block incident actions apply directly after fresh safety checks; only Edit
opens the full rule editor. A known decision offers only its opposite action; the
editor also uses one inverse check/cross icon with an accessible label. Other
management changes have explicit review.

Android Applications measures IP bytes carried by the existing Tailscale VPN and
records supported socket-owner and local DNS evidence. Shared UIDs stay grouped;
domain byte allocations are equal-weight estimates. Explicit resolver-block
responses can retain the observed query app identity. Direct/excluded traffic,
encrypted DNS and drops before the VPN remain unobserved. Optional Usage Access
provides separate coarse OS totals, never added to overlapping VPN counters.

Firewall uses an optional Shizuku connection for reviewed app/UID block and unblock
actions, with a private ownership journal and explicit recovery. It never globally
resets another tool's rules. Neither audit collection nor opening the page enables
enforcement. Windows auditing/enforcement and remaining cross-platform acceptance
remain later [R33](TRAFFIC-AUDIT-AND-BLOCKING-SPECIFICATION.md) work.
