# TailD

Your tailnet, DNS decisions and application traffic—in one desktop.

TailD combines **TailDNS connectivity**, **Control D analytics and incident management**,
and **GlassWire traffic measurements** in a Portmaster-inspired interface with a
Tailscale-style dark theme. Investigate what applications transferred, what your
DNS provider decided, and how strong the evidence linking them actually is.

[Download for Windows](https://github.com/Darkaxt/TailD/releases/latest) ·
[Specifications](docs/taild/PRODUCT-SPECIFICATION.md) ·
[Issues](https://github.com/Darkaxt/TailD/issues)

![TailD Overview: received and sent traffic, application and DNS summaries, and DNS activity history](docs/taild/screenshots/overview.png)

*Actual native TailD UI, refreshed October 16, 2026 from development main using synthetic demo data.
The screenshots contain no real accounts, browsing history or personal application paths.*

## What TailD brings together

| Capability | What you can inspect |
|---|---|
| Control D decisions | DNS questions, raw actions and reasons, bypassed/blocked/redirected/failed outcomes, endpoint scope and decision history. |
| Application traffic | Received/sent bytes, executable identities, ranked consumers, destinations and bandwidth history from existing GlassWire counters. |
| Answer geography | Provider-reported country/ASN decision counts and an offline world map; switch explicitly to inferred traffic-byte geography. |
| Activity explorer | Typed filters, grouping, sorting, pagination, application and time-bin drill-down, saved local queries and expandable source evidence. |
| Incident management | Endpoint/profile associations, shared-device impact, searchable recent resolutions, Block / explicit Bypass / Edit rule actions, and confirmed filter/service/profile-option changes. |
| Policy inspection | READ snapshots of clients, rules, filters, services, groups, options and restrictions—with unavailable capabilities kept visible. |
| Local history | Opt-in independent collectors, ingestion progress, pause/resume, retention and deletion, coverage gaps, corrections and private JSON/CSV exports. |
| TailDNS connectivity | Inherited DNS improvements, MagicDNS-aware resolution, the Windows tray, matching daemon/CLI, and installer/updater integration. |
| Device control | Category-specific Connection, Preferences and DNS resolver pages; autosaved tray preferences, exit-node controls, and a persistent bottom-left About page. |
| Tailscale activity · development main | Opt-in visible-device presence history, connection/exit-node/DNS-recovery observations, and durable TailDrop metadata, independent of Control D and GlassWire. |

Control D remains responsible for its DNS filtering. GlassWire and Windows keep
their firewall roles. TailD does not install another packet-filtering engine or
change firewall policy. Control D policy changes require an explicit preview and
confirmation, using a separate Write credential; collection remains READ-only.

The sidebar keeps Tailscale, Control D and Analytics category icons visible while
showing only the selected category's pages. Control D opens on recent DNS activity;
profile policy is a separate tab. The tray remains available for account sign-in
and Taildrop. These navigation/control additions are available starting with
**1.105.0+11**.

![TailD Tailscale category: existing device connection, exit-node controls and network devices](docs/taild/screenshots/connection.png)

<details>
<summary>Device DNS resolver</summary>

![TailD DNS resolver: tailnet DNS enabled and custom override applied](docs/taild/screenshots/resolver.png)

</details>

### Tailscale-native history · unreleased development main

The Tailscale category now includes **Devices**, **Activity** and **TailDrop**.
Track reported device presence and connection changes, inspect resolver recovery
events, and retain daemon-reported transfer results. Collection is opt-in and
requires no Control D token or GlassWire installation.

![Development TailD Devices: synthetic online and offline peer observations](docs/taild/screenshots/devices.png)

<details>
<summary>TailDrop history</summary>

![Development TailD TailDrop: synthetic outgoing success, failure and incoming daemon receipt](docs/taild/screenshots/taildrop.png)

</details>

Online is control-plane presence, not ping reachability. Received by daemon is
not proof of a save to Downloads. Gaps and unknown outcomes stay explicit; past
unobserved transfers and uptime are not invented. Read the
[source, privacy and history contracts](docs/taild/TAILSCALE-ACTIVITY.md).

### Resolve DNS incidents without opening the browser

Inspect the enforced profile and every endpoint it affects. Review blocked
resolutions with their provider-supplied filter/list, service or rule trigger,
and descriptive category details. Create a Block or explicit Bypass exception,
or edit existing rules, filters, services and profile options.

![TailD Control D Recent DNS workspace with decisions and blocking reasons; Profile policy is a separate tab](docs/taild/screenshots/management.png)

<details>
<summary>Profile policy, separate from recent resolutions</summary>

![TailD profile policy: rules, filters, services and profile options](docs/taild/screenshots/policy.png)

</details>

Writes are never retried automatically. Changed policy/bindings invalidate the
preview; successful actions are read back. READ and Write credentials stay in
separate owning-user Windows vault entries, never in the dashboard or repository.
Live DNS streams persist independently of the window, with historical overlap
reconciled without treating collection gaps as zero traffic.

Development main reuses the collector's session policy snapshot when you revisit
Control D. **Reload policy** explicitly fetches provider-side changes; credentials
and endpoint/account bindings cannot share cached policy. Preview and Apply still
check current policy independently. Recent DNS has its own compact refresh icon
with keyboard support and an accessible label.

## Explore the network, not just a wall of counters

### DNS outcomes and geography

See the provider's decisions independently of local application attribution.
Country tiles coordinate with the map; selecting a country or outcome opens the
matching source facts. Missing geography stays visible rather than becoming a
fabricated location.

![TailD country and ASN widgets, world map and classified DNS outcomes](docs/taild/screenshots/geography.png)

### Applications and evidence

Find the busiest executables by their readable process names, retain full paths
for identity and drill-down, and inspect the underlying observations. Duplicate
basenames remain separate applications.

![TailD Applications: executable identities, received and sent traffic, last observations and DNS candidate coverage](docs/taild/screenshots/applications.png)

<details>
<summary>See the activity and evidence explorer</summary>

![TailD Activity: scoped traffic facts, private export actions and expanded source evidence](docs/taild/screenshots/activity.png)

Evidence preserves raw provider/source fields, exact counters, observation times
and the correlation method. JSON/CSV exports use the selected scope and revision,
not just the visible page.

</details>

## Honest metrics by design

- A DNS decision is not a socket or a transferred byte.
- GlassWire supplies application/time-bucket counters, not individual PID/socket lifetimes.
- A matching DNS answer is a versioned temporal candidate—not proof of which process issued the query.
- Answer geography is not a measured route or the device's physical location.
- Missing collection coverage is not zero activity. Failed and unknown provider actions are not silently classified as allowed.
- A policy snapshot describes an observation, not proof of which historical rule caused a decision.

Queries preserve one committed history revision and exact integer counters.
Completed DNS panels can appear while traffic aggregation continues; loading
state and source progress remain explicit.

## Get started on Windows

1. Download the installer from [TailD releases](https://github.com/Darkaxt/TailD/releases/latest).
2. Follow the Windows installation/migration instructions in the release notes.
   The integrated installer targets the existing Tailscale installation and
   preserves its authenticated state; do not manually delete its state or signing keys.
3. Open **TailD** from Start or left-click its tray icon. Right-click opens the
   connectivity menu.
4. In **Settings**, select the Control D account/endpoint and supply a **READ-only**
   token for DNS collection. Enable application traffic collection if GlassWire
   is installed. Collection is opt-in; viewing retained history does not enable it.
5. For incident management, register a separate Write token using the documented
   [secure credential flow](docs/taild/POLICY-READS.md). No Write token is needed
   for analytics or live DNS collection.

The analytics desktop is currently Windows amd64. Control D data requires a
readable account/endpoint; traffic analytics require an existing compatible
GlassWire installation. The restricted GlassWire reader needs administrator
setup; the dashboard and owning-user collector run without elevation.

Windows payload/installer digests and update metadata are Ed25519-signed.
The executables and installer are **not Authenticode-signed**. Review the
[packaging and trust boundaries](docs/taild/PACKAGING.md).

### Release versus development main

The latest verified public Windows release is
[1.105.0+15](https://github.com/Darkaxt/TailD/releases/tag/windows-v1.105.0%2B15).
It includes category navigation, native device controls, independent Recent DNS
loading, matching sidebar icon padding and the pinned SQLite 3.54.0 runtime.

It also includes session policy reuse and the compact DNS refresh icon.
Development main additionally fixes minimized-window activation, removes stretched
bandwidth/map grid holes, and adds the Tailscale-native history views above. These
changes are **not released or installed**. The October 16 gallery was refreshed
from current development assets with clearly disclosed synthetic facts, not
private browsing or account data; capture provenance records the asset hashes.

Stage 10 remains active for outstanding live delivery/updater acceptance; this
README does not claim every deployment, recovery or lifecycle scenario is
complete. See the [current reconciliation and validation limits](docs/taild/IMPLEMENTATION-PLAN.md).

## Built on TailDNS, kept in sync

TailD is a public, history-preserving derivative of
[Darkaxt/TailDNS](https://github.com/Darkaxt/TailDNS), with the shared Windows/core
implementation pinned through [Darkaxt/tailscale](https://github.com/Darkaxt/tailscale).
It retains the inherited Android source; use the maintained
[TailDNS Android releases](https://github.com/Darkaxt/TailDNS/releases) for that
product. A TailD Android analytics UI is not implemented.

The daily **Inherit TailDNS improvements** workflow checks the exact candidate and
core pin, preserves fork contracts and promotes passing history to main. Failed
checks or conflicts stop promotion; main is not force-pushed. Inheritance itself
does not publish releases or install updates on devices. GitHub's one-fork-per-
network limit means this repository preserves Git history without a second native
GitHub fork badge.

## Documentation and development

- [Product specification and staged acceptance](docs/taild/PRODUCT-SPECIFICATION.md)
- [Implementation status, evidence and remaining blockers](docs/taild/IMPLEMENTATION-PLAN.md)
- [Metrics, typed queries and correlation contracts](docs/taild/METRICS-QUERY.md)
- [Control D policy reads and credentials](docs/taild/POLICY-READS.md)
- [GlassWire source capabilities and limitations](docs/taild/GLASSWIRE-READS.md)
- [Collector lifecycle and privilege boundary](docs/taild/CONTINUOUS-RUNTIME.md)
- [Desktop design and native validation](docs/taild/DESKTOP-ANALYTICS.md)
- [Windows packaging and verification](docs/taild/PACKAGING.md)
- [Inherited Android build reference](docs/INHERITED-ANDROID.md)

The desktop uses Angular in a native WebView2 host. Frontend and native dependency
locks, local package tooling, isolated signing and independent artifact checks
live in this repository. Backend tests use explicitly owned scratch:

```powershell
$env:TAILD_PACKAGE_TEST_OUTPUT = 'D:\Temp\taild-tests'
New-Item -ItemType Directory -Force -Path $env:TAILD_PACKAGE_TEST_OUTPUT | Out-Null
python -B -m unittest discover -s scripts/taild -p 'test_*.py' -v
```

Screenshot reproduction uses
[scripts/taild/capture_readme_windows.py](scripts/taild/capture_readme_windows.py)
with an isolated Debug host and a new scratch directory. It creates only
synthetic facts and makes no provider requests. The
[capture provenance](docs/taild/screenshots/capture-provenance.json) records the
actual served assets, screenshot hashes and policy-revisit verification.

## Attribution and license

TailD is an independent community fork, not an official Tailscale product or
endorsed by Tailscale, Control D, GlassWire or Safing.

Original Tailscale code retains its [BSD 3-Clause license](LICENSE). The
Portmaster-derived desktop widgets retain their [GPL-3.0 license](desktop/LICENSE),
[reuse notices](desktop/NOTICE.md) and upstream attribution. See the
[Portmaster design/source map](docs/taild/PORTMASTER-DESIGN.md) for the adaptation.
Tailscale and other product names remain their owners' trademarks. WireGuard is a
registered trademark of Jason A. Donenfeld.

Contributions require Developer Certificate of Origin `Signed-off-by` lines.
