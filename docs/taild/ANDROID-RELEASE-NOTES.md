## TailD Android 1.103.312.49

- Inherits TailDNS Android 1.103.312+68 with the verified shared core e0c03b1
  (upstream base 1.107.0): upstream serve configuration handling, PCP
  port-mapping updates and connector fixes. No TailD behaviour changes.

## TailD Android 1.103.312.48

- Inherits TailDNS Android 1.103.312+67 with the verified shared core 4f3a77f
  (upstream base 1.107.0, test-only core change): the upstream DNS settings
  screen now reads the DNS configuration from LocalAPI and refreshes it on
  self-node changes, alongside the retained local-DNS controls. No TailD
  behaviour changes.

## TailD Android 1.103.312.47

- Inherits TailDNS Android 1.103.312+66 with the verified shared core 1057748
  (upstream base 1.107.0): node-key expiry handling after wake, a fix for node
  keys moving between nodes, Tailscale-only bootstrap DNS fallback and an
  upstream check that the Go toolchain matches the shared core. No TailD
  behaviour changes.

## TailD Android 1.103.312.46

- Inherits TailDNS Android 1.103.312+65 with the verified shared core 7ecf387:
  upstream WireGuard status timestamps, safer app-connector hooks, an Android
  network-interface fallback and an early HTTP/2 control-connection check. No
  TailD behaviour changes.

## TailD Android 1.103.312.45

- Inherits TailDNS Android 1.103.312+64 with the verified shared core 55384a4:
  upstream network-monitor shutdown fix, removal of a decommissioned DERP
  fallback server and a wireguard-go update. No TailD behaviour changes.

## TailD Android 1.103.312.44

- Updating TailD in place no longer leaves the VPN down. Replacing the package
  stopped the VPN service and nothing restarted it, so the backend came back
  "Running" with no tunnel. TailD now reconnects after an update when the VPN was
  wanted or paused while idle; a VPN you disconnected stays off.
- The Connect switch now starts the VPN when the backend reports Running without
  a tunnel; previously it did nothing in that state.

## TailD Android 1.103.312.43

- Pause while idle: after the screen has been off for 10 minutes (Android may
  deliver the check up to about 7 minutes later) with no media playing and no
  call active, TailD disconnects the VPN, which stops keepalives, DERP and control
  traffic. It reconnects when the screen turns on, when audio playback starts, or
  from the "Paused while idle" notification's Connect action. Turn it off in
  Settings > Pause while idle.

## Earlier

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
