# TailD for Android

TailD expands the inherited TailDNS Android client with native Tailscale device
views and observations, Control D DNS history and basic management, and a private
seven-day Dashboard. It follows Android's automatic light/dark theme.

Current release: [1.103.312+34](https://github.com/Darkaxt/TailD/releases/tag/v1.103.312%2B34)
([APK](https://github.com/Darkaxt/TailD/releases/download/v1.103.312%2B34/taild-android.apk)).
The public package, existing signer, source/core identities and all payload hashes
were independently verified. In-place upgrade and recovery checks used an isolated
emulator; installation and continuity on a physical phone remain separate.

Android releases use tags `v<upstream Android base>+<TailD Android sequence>`.
Windows releases use `windows-v...` and remain on their existing update channel.
Filter Android update tools to `^v[0-9]+\.[0-9]+\.[0-9]+\+[1-9][0-9]*$` and the
`taild-android.apk` asset; do not use the repository's Windows latest-release URL
as an Android package feed. Downloads and update origin belong to
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

App/IP traffic auditing, ambiguous DNS attribution and app blocking are later
Windows/Android work under [R33](TRAFFIC-AUDIT-AND-BLOCKING-SPECIFICATION.md).
