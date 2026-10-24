TailD Android 1.103.312.40 includes the verified October 24 TailDNS/core updates
and supports an in-place upgrade from current TailDNS Android installations.
It retains the existing package and signing identity, settings, node identity,
local DNS configuration and SleepManager compatibility. New upstream LocalAPI
requests resolve the application backend per request and deliver provider errors
through the callback. TailD's scoped TailDrop history integration is preserved.

The existing Firewall analysis features remain: each app/shared-UID
row shows IN and OUT bytes for the last 24 hours and a compact hourly
graph. Apps sort by combined traffic descending, then alphabetically. Viewing
traffic and installed-app metadata does not require Shizuku; optional blocking
keeps its existing explicit setup and reviewed actions.
Refreshing preserves the search field and avoids stale failure banners. Expanded
setup appears below the search row so its controls stay visible.

The diagnosis icon opens a separate analysis page with a Vico hourly chart,
separate IN/OUT series, byte/time axes and sortable destination/DNS tables.
Destination traffic bars show concentration; DNS shows questions, replies and
observed blocked replies. App metadata, coverage and packet records open on demand.
Accessible hourly values and exact snapshot export remain available. Unknown and previous
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
