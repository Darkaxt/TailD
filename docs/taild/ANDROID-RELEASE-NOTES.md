TailD Android now includes an offline, map-first Geography view, a dedicated
Firewall tab with the official ShizuWall mark, and Applications traffic in Dashboard.
The interface follows system light/dark mode across phone and tablet layouts.

The optional Shizuku connection enables reviewed app/UID block and unblock actions.
Shared-UID packages are shown together. TailD keeps its own rule ownership record,
checks current state and offers explicit recovery after backend loss or restart.
Basic DNS views and traffic measurement work without Shizuku.

With Collect analytics enabled, Applications records IP bytes carried by the
existing Tailscale VPN, looks up supported socket owners, and retains local DNS
questions, replies and eligible domain candidates. Domain allocations use equal
weights and are estimates. Explicit resolver-block replies can be associated with
the observed query app; firewall drops before the VPN have no domain evidence.
Direct/excluded routes and unobserved or encrypted DNS remain outside that view.
Optional Android Usage Access provides separate coarse OS totals, never added to
VPN measurements. Search, detail and document export share a frozen time window.

History is private, bounded and retained for up to seven days. Recording off
preserves retained facts; Delete local history clears activity, DNS and traffic
without changing VPN settings or Control D cloud history. No second VPN, permanent
packet capture, polling service or automatic firewall activation is introduced.

This is an in-place update of the existing TailDNS/TailD package and signing
certificate. Numeric Android versions remain compatible with ObtainX. Existing
profiles, credentials, node identity, DNS ownership and SleepManager intents are
preserved. Windows has its own release channel; its later R33 work remains open.
