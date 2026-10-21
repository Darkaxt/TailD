TailD Android 1.103.312.39 brings app traffic into Firewall. Each app/shared-UID
row shows received and sent bytes for the last 24 hours and a compact hourly
graph. Apps sort by combined traffic descending, then alphabetically. Viewing
traffic and installed-app metadata does not require Shizuku; optional blocking
keeps its existing explicit setup and reviewed actions.
Refreshing preserves the search field and avoids stale failure banners.

The diagnosis icon opens a separate page with a larger hourly graph, accessible
hour values, package/UID/profile/version/signing metadata, observed destinations,
DNS questions/replies, domain estimates and snapshot export. Unknown and previous
installation identities stay separate. Resolver context never inflates app totals.
Dashboard Applications remains available.

Fix Control D's "Provider record is outside the requested scope" error when its
whole-second CSV response overlaps fractional request boundaries. TailD requests
an explicit whole-second envelope and retains only the exact local half-open
interval, preserving duplicate events and scope/resource checks.

These are observed VPN bytes, not guaranteed whole-device totals. Direct/excluded
traffic, encrypted/unobserved DNS and traffic blocked before the VPN remain outside
that observer. Endpoint DNS history alone cannot identify the originating APK.
Automatic light/dark mode, retained history, existing package/signing identity and
the separate Windows channel are preserved. No provider policy, app rule, routing
or device setting changes automatically.
