# TailD 1.105.0+3 for Windows

- Control D and GlassWire acquire independently. A slow GlassWire history read
  no longer prevents Control D from starting or committing DNS reads.
- GlassWire reads current traffic before bounded older-history backfill. Progress
  is retained across interruption without skipping pending windows.
- Pause/resume preserves fresh-source scheduling; SQLite writes remain serialized.
- Existing themed ingestion notices, transparent Tailscale icons, tray behavior,
  DNS improvements and authenticated in-place installation are preserved.

Upstream version remains **1.105.0**; only TailD subversion advances to **+3**.
Source: `0a76e1dd917995aa9a4ce0bf2d47315c144544a2`.
Build, protected signing and isolated installer verification:
https://github.com/Darkaxt/TailD/actions/runs/38489010515

The complete signed 415-member payload, installer digest and pinned core were
independently verified. Beacon's actual +2 to +3 installation passed node,
addresses, Tailnet Lock signer, service, DNS preference, public DNS and MagicDNS
continuity checks. The opted-in owner collector restarted automatically without
the dashboard and committed reads from both sources. These checks do not claim
completion of the remaining Stage 10 recovery/UI acceptance criteria.

Verify the detached manifests against the project's pinned Ed25519 key. The
installer and executables are **not Authenticode signed**. Windows x64 and
Evergreen WebView2 are required; first migration requires an existing authenticated
Tailscale/TailDNS installation. TailD is an independent fork.
