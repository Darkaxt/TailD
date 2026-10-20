TailD Android adds native Tailscale device/status views, opt-in scoped activity
and TailDrop history, Control D setup/Recent DNS/basic management, and a private
seven-day Dashboard with matching drill-down and document export.

The interface follows system light/dark mode, supports phone/tablet layouts and
keeps existing VPN/DNS/profile ownership. History catch-up uses bounded reads;
recording is off by default, with no new polling service. Separate READ/Write
credentials and uncertain-write reconciliation preserve provider boundaries.

This APK updates the existing TailDNS package using its existing certificate.
Official Tailscale compatibility and SleepManager intents remain preserved.
Android and Windows have separate release assets/channels. App bandwidth,
per-app auditing and blocking remain later work. DNS observations do not measure
traffic bytes or attribute a connection to an app.
