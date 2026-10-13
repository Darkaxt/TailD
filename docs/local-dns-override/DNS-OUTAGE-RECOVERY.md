# Encrypted outage recovery integration

The 2026-10-11 user-authorized change prioritizes public internet availability
over retaining provider filtering during an actual resolver outage. The shared
core [authoritative specification](https://github.com/Darkaxt/tailscale/blob/main/docs/dns-outage-recovery.md)
defines eligibility, exclusions and acceptance criteria. Recovery is automatic;
no new Android switch or manual DNS edit is required.

Android pins public core `a950a8448904171bd058d0ce74bc3ed990001f97` as
`v1.103.0-pre.0.20261012090911-a950a8448904`, module checksum
`h1:M6II7rdRrEiRuR6pUkBfrEVm1bp0XWR49feFrOV+FLg=`. Both the require and
replacement versions agree, and go.sum records the actual committed module.
The public module was downloaded and its outage implementation matches the
previously tested source byte-for-byte. The original source-only integration
pinned `45572acd39ad7d2c50600543e17d2ad3d9388745`; subsequent core changes only
recorded verification and the newly authorized delivery scope.

## Verification

- Native `./libtailscale` builds with `-mod=readonly`, Android ARM64, CGO enabled,
  Android API 26 and the existing NDK 23.1.7779620. The resulting native archive
  contains Go and Android C objects. Its imported outage implementation has
  SHA-256 `DD0F1EEE05B16A8939FA7AC86C1A1167A0C9E4117A441288C704C961F0C864B6`,
  matching the tested core source.
- Existing Android models accept the unchanged LocalDNS API and the new
  string-coded low-severity health warning. `DNSSettingsView` already displays
  the backend's Reason, which now discloses encrypted recovery and temporary
  filtering bypass. No Kotlin API/schema change or new settings source exists.
- Core regression tests reproduce provider HTTP 503, prove ordered encrypted
  recovery and return to the selected provider, and preserve private routes and
  negative answers. A controlled 503 followed by a real Cloudflare HTTPS query
  passed on the host. Focused transport/health tests passed under the race
  detector; this is not a new Android VPN/exit-node packet capture.

The original source-only task generated no APK/AAR release, ran no Gradle command,
changed no Android system settings and installed nothing on any device. ARM64 native compilation
does not claim a signed full-app build or phone validation. The existing request
deadline is unchanged: complete transport blackholes can exhaust it before
recovery; no arbitrary timeout or polling loop is introduced.

## Public delivery authorization, 2026-10-12

The user authorized public Windows/Android releases and local Windows activation.
Android release `v1.103.312+29` must pass the existing GitHub exact-source build,
test and isolated signing pipeline, followed by independent download verification
of package/version/code, signer, SHA-256 and this exact public core provenance.
Publication is not an Android device installation claim. Delivery stage status
and final verification belong to the linked authoritative core specification.
The unpublished +28 attempt was canceled after the separate dependency-tidy
gate detected obsolete module checksums; its immutable tag is not reused.
