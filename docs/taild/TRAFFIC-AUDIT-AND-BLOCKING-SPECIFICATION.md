# Deferred cross-platform traffic audit and app blocking — R33

Date: 2026-10-16. Status: required later scope; implementation NOT STARTED.

## Authority and ordering

The user requested that app/IP traffic auditing, domain attribution estimates and
app traffic blocking be retained for **both Windows desktop and Android**, after
the other Android features are implemented. The user supplied FireWall-Blocks and
ShizuWall as implementation references and proposed equal probability for recent
DNS names associated with a contacted IP. The subsequent direction prefers
measuring inside TailD's existing Tailscale VPN and using its DNS-resolution facts.

This document is authoritative for that deferred R33 scope. It supplements
PRODUCT-SPECIFICATION.md; it does not replace current R10/R11 behavior, broaden
desktop Stage 10/B12, or activate Android A1–A4. Current authority covers research,
specification/roadmap updates and their commit. It does not authorize installing
either reference app, granting Shizuku/ADB/root access, changing routing/DNS or
firewall rules, provisioning a privileged backend, changing a schedule, publishing
or implementing the deferred feature now.

Prerequisites: existing desktop Stage 10 acceptance and Android A1–A4 acceptance
must be reconciled and satisfied before F1 implementation begins. Do not quietly
substitute a prototype, source-only checks or omitted Android integration for
those prerequisites. The maintenance automation must not activate R33 merely
because this specification exists. No release/install authority is added here.

## Required product behavior

1. Show source-observed app-to-IP traffic on Windows and Android, with time,
   direction, protocol and byte counters where genuinely provided. Preserve
   unknown app identity and source coverage. Distinguish a connection attempt,
   firewall permit/block decision, established flow and measured transferred bytes.
2. Prefer passive observations inside the existing Tailscale resolver and VPN
   packet/flow path for traffic that actually traverses that path. Reuse supported
   existing Windows GlassWire facts for their measured scope; do not replace a
   functioning source just to introduce another collector.
3. Link traffic to locally observed DNS questions/answers when available, using
   Control D device/client-aware history as another separately attributed source.
   Display the measured IP/app evidence and the candidate domain evidence together.
4. Assign equal conditional weight to every distinct eligible domain candidate;
   provide optional estimated per-domain byte allocations without multiplying
   physical traffic totals. Unsupported/ambiguous association is acceptable when
   honestly represented; deterministic domain attribution is not a prerequisite.
5. Provide explicit user-selected app-level block/unblock controls on both
   platforms, with verified effectiveness, ownership and recovery. Recording or
   opening a dashboard never implicitly blocks an app or changes routing.
6. Retain local privacy, opt-in acquisition, bounded storage, retention/deletion,
   responsive controls and matching scoped drill-down/export. Audit-only use must
   not require enabling enforcement.

## Preferred observation design and coverage

Tailscale is a VPN. Its configured routes determine the traffic carried through
it. Default split-tunnel operation does not mean all public Internet traffic
crosses its TUN; an enabled exit node supplies default routes, subject to explicit
exclusions. Resolver handling and data routing are separate settings.

For each platform, first inspect and prove the actual existing Tailscale route,
resolver and packet/flow observation boundaries. Do not add a second Android
VpnService, redirect all traffic, enable an exit node or change split tunneling
merely to populate a dashboard. Existing-path measurement can be narrower than
whole-device measurement and must be labeled accordingly.

The inspected shared core exposes DNS request/response processing in
`net/dns/resolver/tsdns.go` (`Resolver.Query`) and packet filter hooks in
`net/tstun/wrap.go`. These establish source seams, not an already implemented or
validated analytics API. Existing hooks have engine/netstack/filter consumers;
never overwrite them or make slow persistence/UI operations block packet handling.
Prefer small passive metadata observations over raw payload capture. Any change
to the separately maintained core requires its existing fork/pin/integration gates.

Record app/UID or process identity only when supported by the observation boundary.
Android's active VPN connection-owner API can associate observable TCP/UDP tuples
with UIDs on API 29+, but TailD's current Android minimum is API 26; older versions
need a separately proven supported path or an explicit unavailable capability.
Shared UIDs, work profiles, process/UID reuse and missing identities remain visible.
Do not assign all app traffic to an arbitrary package sharing its UID.

Windows GlassWire currently supplies application/destination/time-bucket counters,
not unique sockets. Keep that distinction. Windows Filtering Platform connection
audit events are a candidate for process/IP/port permit/block evidence, but those
events are not flow byte counters or proof a remote server completed a connection.
Do not time-join aggregate app counters onto arbitrary destination events and
present the result as measured per-flow bytes. Choose additional sources only
where required coverage is not supplied by the existing path.

Each observation records source, host/profile, app identity quality, address
family, route/interface scope, time range, available counters, counter/reset
semantics and allow/block/attempt/flow meaning. Canonical measured totals count a
fact once; overlapping source counters are not summed. Tunnel payload and encrypted
transport overhead must not be silently mixed. Unseen traffic is not zero traffic.

## DNS evidence and equal-weight attribution

An observed resolver reply establishes that a question received particular IP
answers. A later IP packet establishes its destination IP, not the original DNS
name chosen by the application. Several queried names can share the same answer;
cached results, direct IP use and HTTP connection reuse can also leave ambiguity.
Even locally observed DNS improves evidence without creating an application-layer
domain field in every packet. No TLS interception/decryption is required or planned.

Candidate selection must match the traffic's actual host/profile and resolver
binding, endpoint/client scope where applicable, parsed destination IP, and a
preceding resolution within the recorded analytical time window. Start with the
existing 300-second desktop analytical default, recorded with the result and
configurable through the existing bounded query contract. This is an inference
window, not a networking timeout, a DNS TTL claim or a flow-cancellation deadline.
Local observed TTLs may constrain their own evidence; missing TTL is unknown.
Never use a future DNS reply to retrospectively label an earlier flow. Scope or
resolver changes partition candidate selection. Shared endpoint data without a
verified matching client cannot masquerade as this device's DNS history.

Normalize names with a versioned comparison rule and retain original spellings
and source records. Deduplicate candidate **names**, not DNS events: repeated
lookups of one name do not make it more probable than another name. Preserve
genuine repeated DNS events in DNS request totals. Merge matching local/provider
evidence without treating it as independent votes for a name.

For N eligible distinct names, each candidate gets the exact rational weight
`1/N`. This is the user's equal-probability model **conditional on the candidate
set**, not a calibrated probability that the traffic truly belongs to that name.
The candidate set itself can be incomplete. N=1 has all candidate weight but is
still not proof of domain attribution; N=0 stays unmatched/unknown.

Example: one app/IP fact has 12 MB of measured traffic and three eligible names.
Show the measured fact once, list all three names at 1/3 weight, and optionally
show 4 MB estimated attribution to each. Never report 12 MB measured usage for
each domain or 36 MB overall. If allocation is fractional, retain exact rational
amounts and reconcile display rounding without changing measured totals.

Required presentation: `Observed destination`, `DNS candidates`,
`Equal-weight estimate`, analytical window, evidence source/time, ambiguity and
coverage. Preserve the raw measured IP-level view and a separate unknown group.
Give this derived metric its own algorithm/version, such as
`equal-domain-candidate-v1`; do not silently reinterpret current R11's unique-only
inferred-domain results or historical exports.

Estimated domain candidates must never automatically generate IP/domain/app
blocking rules. Blocking an app, an IP and a Control D profile-domain rule have
different effects and must be explicitly described and selected.

## Blocking design candidates

### Android

Prefer a small optional system-firewall integration informed by ShizuWall when
an explicitly authorized Shizuku/ADB/root backend is available and validated.
This avoids claiming another VPN slot and can operate independently of data
being routed through Tailscale. Do not require privileged setup for basic DNS
dashboards or audit viewing, silently select a backend, start a daemon, or change
the existing Android minimum SDK just to copy a reference project.

Verify device/OS/OEM support, shared-UID and cross-profile scope, current firewall
state, rule ownership, reboot/backend-loss behavior and real block/unblock
effectiveness before accepting this path. A successful shell/Binder return alone
does not prove enforcement. Preserve other firewall tools' rules and chain state;
do not copy global disable/reset behavior that clears unrelated policy. Keep a
defined recovery path if backend access disappears with a block still active.

Filtering within the existing Tailscale packet path remains a candidate for
explicitly scoped routed traffic. It is not whole-device blocking unless all
required traffic paths are covered and that routing arrangement is authorized.
Backend selection and any required privilege decision must be resolved in F3;
unsupported operation is visible and cannot be relabeled successful enforcement.

### Windows

Evaluate the existing Windows Firewall/WFP policy interfaces for narrowly owned
app rules, coexisting with GlassWire and current security software. Preserve
existing policy and rules; require exact app/scope preview, explicit confirmation,
readback, real enforcement verification and removal/restoration of only owned
rules. Any necessary administrator action uses the installed elevation workflow.
No new packet driver or replacement firewall is selected by this specification.

## Source review: supplied Android projects

Read-only source review on 2026-10-16; neither app was installed, run or built.

| Project/pin | Useful precedent | Integration limit |
| --- | --- | --- |
| FireWall-Blocks `8bca2c22eca77ad0675da35865af5936878a34e2` | TCP/UDP tuple parsing, Android UID lookup and a live attempted-access log; separate Shizuku-based app blocking. | Monitoring routes IPv4 into its own VPN and reads/logs packets without a forwarding path. It does not provide transparent bidirectional byte metering. Normal blocking routes selected blocked apps into a sink. A second VPN conflicts with Tailscale ownership. |
| ShizuWall `297b673fe15c5aec0cf454c57cebe572692ab675` | System app/UID firewall commands, Shizuku/ADB/root control paths, work-profile handling and per-operation outcomes. Better reference for optional non-VPN app blocking. | Reviewed paths set app/UID firewall policy; they do not supply destination-IP flow counters. Backend permissions and OS/OEM support need real proof. Chain ownership and recovery cannot be copied blindly. |

FireWall-Blocks' LICENSE contains permissive MIT-style terms, although GitHub's
license API reports NOASSERTION. ShizuWall declares GPLv3; its bundled tracker data
has a separate ODbL license. Check exact component licenses, dependencies, source
distribution and notices before importing code. No code or tracker data was copied
for this planning task, and tracker scanning is outside R33.

## Named stages and tracked deferrals

These are required later features, not missing acceptance work in current desktop
Stage 10 or Android A1–A4. Those stages can meet their existing criteria without
them. All R33 stages must eventually pass before the R33 extension is called complete.

| ID / stage | Status | Dependencies | Required final verification |
| --- | --- | --- | --- |
| F1 — Windows app/IP audit and weighted domain view | NOT STARTED | Existing desktop Stage 10 and Android A1–A4 acceptance complete; implementation subsequently authorized. | Real existing-path/source traffic -> measured app/IP record -> local/provider DNS candidates -> equal weights -> matching dashboard/drill-down/export; IPv4/IPv6, shared-IP/dedup/scope-change/unknown cases and exact once-only byte reconciliation. Extra connection/permit/block claims need their actual source proof. |
| F2 — Android app/IP audit and weighted domain view | NOT STARTED | F1 COMPLETE, so the shared semantics are verified before the Android slice; no parallel ACTIVE stage. | Real traffic through the current Tailscale path -> UID/app identity where supported -> measured IP/counters -> local/provider DNS candidates -> identical weighted semantics -> native dashboard/drill-down/export. Verify excluded routes, version capabilities, process restart, network transitions and unchanged VPN/DNS behavior. |
| F3 — Explicit app traffic blocking on both platforms | NOT STARTED | F1 and F2 COMPLETE. | User selects exact app/scope -> preview/confirm -> authorized platform rule -> real prevented connection -> visible effective state -> unblock -> restored connectivity. Verify separate audit-only use, owned-rule recovery, reboot/backend loss, shared identities and coexistence with existing firewall/Tailscale policy on Windows and Android. |

Future source/backend capability gaps belong to their named stage and block that
stage's acceptance until resolved. They do not authorize starting R33 early or
substituting simulated enforcement for real boundaries. The final audit evidence
must identify exactly which traffic is seen, attributed, counted or blocked.

## Pinned evidence

- [FireWall-Blocks VPN/monitor parser](https://github.com/shynoiddev/FireWall-Blocks/blob/8bca2c22eca77ad0675da35865af5936878a34e2/app/src/main/java/com/shayan/firewall/FirewallVpnService.kt), lines 208–249, 256–320; only IPv4 TCP/UDP parsing at 274–286 and DNS-query parsing at 299–301.
- [FireWall-Blocks Shizuku control](https://github.com/shynoiddev/FireWall-Blocks/blob/8bca2c22eca77ad0675da35865af5936878a34e2/app/src/main/java/com/shayan/firewall/ShizukuManager.kt).
- [FireWall-Blocks monitoring record](https://github.com/shynoiddev/FireWall-Blocks/blob/8bca2c22eca77ad0675da35865af5936878a34e2/app/src/main/java/com/shayan/firewall/MonitoringLog.kt) and [license](https://github.com/shynoiddev/FireWall-Blocks/blob/8bca2c22eca77ad0675da35865af5936878a34e2/LICENSE).
- [ShizuWall commands](https://github.com/AhmetCanArslan/ShizuWall/blob/297b673fe15c5aec0cf454c57cebe572692ab675/app/src/main/java/com/arslan/shizuwall/firewall/FirewallCommands.kt), [per-UID handling](https://github.com/AhmetCanArslan/ShizuWall/blob/297b673fe15c5aec0cf454c57cebe572692ab675/app/src/main/java/com/arslan/shizuwall/firewall/PerUidFirewall.kt), [routing executor](https://github.com/AhmetCanArslan/ShizuWall/blob/297b673fe15c5aec0cf454c57cebe572692ab675/app/src/main/java/com/arslan/shizuwall/shell/PerUidRoutingExecutor.kt), [Shizuku user service](https://github.com/AhmetCanArslan/ShizuWall/blob/297b673fe15c5aec0cf454c57cebe572692ab675/app/src/main/java/com/arslan/shizuwall/shizuku/ShizuWallUserService.kt), [README](https://github.com/AhmetCanArslan/ShizuWall/blob/297b673fe15c5aec0cf454c57cebe572692ab675/README.md) and [license](https://github.com/AhmetCanArslan/ShizuWall/blob/297b673fe15c5aec0cf454c57cebe572692ab675/LICENSE.md).
- Existing local `GLASSWIRE-READS.md`, `METRICS-QUERY.md`, `scripts/taild/analytics.py` and `join.py`; Android `libtailscale/net.go` route construction; shared core `net/dns/resolver/tsdns.go` and `net/tstun/wrap.go`.
- [Android VPN connection ownership](https://developer.android.com/reference/android/net/ConnectivityManager#getConnectionOwnerUid(int,%20java.net.InetSocketAddress,%20java.net.InetSocketAddress)).
- [Windows permitted-connection audit fields](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-5156) and [WFP interfaces](https://learn.microsoft.com/en-us/windows/win32/fwp/about-windows-filtering-platform).
- [Tailscale split-tunnel/exit-node routing](https://tailscale.com/docs/features/exit-nodes) and [HTTP/2 multi-origin connection reuse](https://www.rfc-editor.org/rfc/rfc9113.html#section-9.1.1).
