# Encrypted outage recovery integration

The 2026-10-11 user-authorized change prioritizes public internet availability
over retaining provider filtering during an actual resolver outage. The shared
core [authoritative specification](https://github.com/Darkaxt/tailscale/blob/main/docs/dns-outage-recovery.md)
defines eligibility, exclusions and acceptance criteria. Recovery is automatic;
no new Android switch or manual DNS edit is required.

Android pins core `45572acd39ad7d2c50600543e17d2ad3d9388745` as
`v1.103.0-pre.0.20261011173409-45572acd39ad`, module checksum
`h1:aZBEq3IwPfWuUMJHdYRWohLigNsQhKoxRwIPSCNmQ+s=`. Both the require and
replacement versions agree, and go.sum records the actual committed module.
Source was resolved locally from that Git commit for verification, without a
persistent local-path replacement or pushing an unverified release.

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

This task generated no APK/AAR release, ran no Gradle command, changed no Android
system settings and installed nothing on any device. ARM64 native compilation
does not claim a signed full-app build or phone validation. The existing request
deadline is unchanged: complete transport blackholes can exhaust it before
recovery; no arbitrary timeout or polling loop is introduced.
