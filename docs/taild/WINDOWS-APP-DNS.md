# Windows app DNS and Android-led refinement — R38

2026-10-22. Authoritative bounded amendment to PRODUCT-SPECIFICATION.md and R33.
The user explicitly switches implementation focus to Windows, requests Android's
existing per-app domains/blocked-resolution feature, and asks for refinement of
the Windows modules where Android's design was judged stronger. Implementation,
integration, focused verification and one normal independently verified Windows
release are already authorized. Android changes and new Windows firewall rules
are outside this update. GlassWire remains the byte source and enforcement owner.

The new instruction activates this bounded Windows scope without requiring B12
to close first. B12 remains parked BLOCKED, with every original real rollout,
rollback and reconciliation requirement intact. R33's wider F1/F3 acceptance is
not claimed merely by completing R38.

## Behavior and acceptance

- W01: Opt-in local Windows DNS observations retain original event time, query,
  type, result, originating process path and process-instance identity when
  supported. Use the existing protected reader/owner runtime, with fixed-schema
  authenticated operations; no arbitrary ETW providers, shell, paths or queries
  from the renderer. Do not enable global DNS event logging. Stop observation on
  opt-out/service shutdown. Bound buffers, expose lost/unassigned observations,
  preserve unknown ownership, avoid PID reuse attribution and filter other users.
- W02: Applications include DNS-only apps with zero observed traffic. App diagnosis
  has searchable/sortable domain rows with count, first/last seen, latest outcome,
  evidence source and expandable observations. Failed/NXDOMAIN/REFUSED alone are
  not proof of policy blocking. Correlate explicitly selected same-host Control D
  endpoint decisions with local query names/time; retain ambiguity and unknowns.
  Provider-only observations must never be silently assigned to an app. Confirmed
  provider matches are labeled correlated, distinct from the observed app lookup.
- W03: Retained GlassWire IN/OUT counters and app/IP facts remain authoritative.
  Domain candidates and 1/N byte estimates are separate, never multiply measured
  totals. Unknown/unmatched traffic remains visible. Do not imply the app-issued
  DNS question proves an actual connection. Retain existing IPv6/unsupported
  source limitations honestly rather than claiming expanded GlassWire coverage.
- W04: Private history, WAL, retention, opt-in lifecycle, READ/WRITE separation,
  source scope, exports and revision consistency remain intact. Reuse the existing
  versioned snapshot storage for process-DNS observations; no schema watermark
  change without a genuine migration requirement. Test retention/deletion and
  unchanged older readers. Export the same selected app/window/revision as shown.
- W05: Android-led UI refinements apply to connection status, Preferences/exit
  settings, DNS resolver status, Recent DNS, per-app traffic/diagnosis and TailDrop.
  Retain Windows' device comparison tables, dashboard/geography, policy editing,
  activity explorer and native navigation. No second DNS policy-writing path.
- W06: Preserve policy-gated controls, explicit disconnect/reset safety, source
  unknowns, TailDrop exact Enabled/Disabled labels, keyboard access/focus, icon
  accessible names, tooltips and readable automatic theme behavior.
- W07: Validate real Windows process DNS (including a DNS-only failed lookup),
  source-to-history-to-native-UI/export, loss/ownership behavior, retained real
  provider read correlation, native layouts, backend/build/package and isolated
  install/upgrade/rollback/uninstall/recovery gates. Final release must preserve
  exact source/core provenance, pinned signing identity, channel and every payload.

## Design contract

Use the existing Android compact list -> app diagnosis direction, not a new visual
brand. At 1280x720 and 150% scaling, keep search/filter controls compact and results
reachable without an introduction section. At 1440x900, diagnosis shows a domain
table in the initial viewport; the hourly chart and raw/coverage details collapse
without shifting the whole page into a debug report. Use IN/OUT, relative times
with exact values available, native-size labeled icon actions, a recognizable app
identity and All/Blocked/Allowed/Unknown filters. Preserve responsive scrolling,
48px touch targets where applicable and visible keyboard focus. Validate with
native served-asset screenshots, not only source or static mockups.

## Execution and reconciliation

| Stage | Status | Acceptance satisfied | Remaining / blockers |
| --- | --- | --- | --- |
| Windows app-domain workflow | COMPLETE | Private DNS Client source works under reduced reader privileges through the actual owner-authenticated pipe; stopped final batches drain and acknowledge. Real Windows success/failure and same-endpoint Control D blocked correlation pass without provider writes. Private snapshots, DNS-only apps, conservative outcomes, exact 1/N accounting, revision-bound app export/deletion and 100%/150% native served layout/search/filter/drill-down checks pass. | None for this feature stage. Final packaged source, installer and release gates belong to final delivery. |
| Remaining Android-led module refinements | COMPLETE | Actual connection state/account, compact analytics and exit preference rows, resolver status/editor disclosure, rounded Recent DNS search and denser relative-time rows, opposite-action icons/floating editor, TailDrop IN/OUT/relative dates and fixed Windows Known Folder action verified in the actual native host at 100%/150%; keyboard/search/deletion/error/permission contracts preserved. | None. |
| Final Windows delivery | COMPLETE | Exact-source checks, fresh hosted package/install/upgrade/rollback/uninstall and complete-product failed-migration refusal gates pass. Normal windows-v1.105.0+30 is independently downloaded and verified: pinned release/package/core signatures, source/core/base/sequence/channel, every payload member, runtime identities/notices, frozen app_dns/dns_trace modules and exact native-tested UI assets. | None. |

No required tracked deferrals. B12 and wider F3 are preserved separate scope.

Feature evidence: D:/Tools/taild-windows-appdns40-evidence-20261022 and owned
D:/Temp/taild-windows-appdns40/native-w1-final. Native provider decisions in UI
interaction fixtures are synthetic; the separate real-source/real-provider check
observed googleads.g.doubleclick.net blocked under the unchanged installed resolver.
Windows API parameter failure 87 is explicitly excluded from provider inference.
Provider decision matches use a matching active-resolver point observation plus a
five-second name/type window, not continuous proof of process/provider ownership.
Native observations are harvested every five seconds; this cadence never cancels
or classifies running work. The direct sources and measured totals stay separate.
Stage-closure design-debt assessment: no material duplicate state owner or required
consolidation was found. The existing reader, writer, snapshot table and native
export path are reused; no new service, dependency, privilege or schema is added.

Final reconciliation: W01–W04 pass real source/owner-pipe/history and focused
behavioral checks; W05–W06 pass native served-asset module/interaction checks.
The complete backend contracts and production Angular build pass on the current
source. W07 passes fresh hosted package/installer gates, normal publication and
independent delivered-artifact verification. Local device
installation is not part of this release. The exact UI bundle and compact evidence
are preserved under the evidence directory above. DNS counts explicitly count
resolver observations, including separate A/AAAA completions, not unique app requests.

Delivery: [windows-v1.105.0+30](https://github.com/Darkaxt/TailD/releases/tag/windows-v1.105.0%2B30),
source 4cf466c7998210664a8a6c29a726ae78e6b3a175, successful release run
39853099554. Installer size 117,401,678 bytes; SHA-256
9cda36c0f05a997c9a9d58b6681776531fdfb1e3cfab9681b86f501e24b13e90.
History schema remains 4; Ed25519 manifest signing does not add Authenticode
signatures. All R38 requirements are satisfied; B12 and wider R33 acceptance stay
separately open. The original temporary native histories/build mirrors are
expendable after compact evidence preservation; their paths are historical.
