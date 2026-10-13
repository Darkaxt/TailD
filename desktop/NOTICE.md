# TailD desktop source and licensing

This desktop component is GPL-3.0-only, including its adaptations of Safing
Portmaster. Copyright Safing and contributors; TailD changes copyright 2026
TailD contributors. The inherited TailDNS/core BSD notices remain unchanged.
This component's license is not a claim that process separation eliminates
distribution obligations. Any distribution must include this notice, GPL text,
all applicable dependency notices, and the complete corresponding source and
build instructions for the covered desktop work. Windows distribution is explicitly
authorized in Stage 10; TailD remains an independent fork, not an official product.

The dashboard application/window icon is the unmodified Tailscale Windows GUI
resource inherited from the exact TailDNS core. Copyright Tailscale Inc. and
Contributors; original executable/resource/hash provenance is recorded in
`native/assets/README.md`. It is not a new TailD logo or a connection-state claim.

Portmaster source: https://github.com/safing/portmaster at
`bb6c44468a5d66bddb13bf3c43fcb2625c326ca9` (retrieved 2026-10-13).
Paths below are relative to that repository. Imports are reviewed before copying.

| Original path | Git blob | TailD adaptation |
|---|---|---|
| `LICENSE` | `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7` | Unmodified GPL text in LICENSE |
| `desktop/angular/src/app/pages/dashboard/dashboard-widget/dashboard-widget.component.ts` | `35d2668a7560a31aae9d0e0c6f420534a025008b` | Standalone Angular 20 panel, remove unused beta chrome, equivalent explicit CSS, semantic heading |
| Same directory `dashboard-widget.component.html` | `65fd80cf1b4902b18277b385975673a2bdd0c232` | Panel heading and content projection retained |
| `desktop/angular/projects/safing/ui/src/lib/toggle-switch/toggle-switch.ts` | `6b90f9610d5b34a1c0294e7181a2bc0213f04225` | Standalone Angular 20 value accessor, native input accessible name/focus/touch |
| Same directory `toggle-switch.html` | `69320c3af1d89d51410c736e0097e9d0f770a25a` | Actual slider/dot/check/cross structure retained; visible keyboard focus |
| Same directory `_toggle-switch.scss` | `246a7953117da619892ccc9c15062da82ea17536` | Equivalent explicit CSS replacing Tailwind directives |
| `desktop/angular/src/theme/_colors.scss` | `65310698037063179ef35ffb98a27a6d586b7b83` | Upstream variables retained as reference; active tokens overridden with user-requested Tailscale palette in styles.css |
| `desktop/angular/tailwind.config.js` | `ba4e7f117e5d31c79f891811c99e44327a25cb34` | Relevant panel/gray/green/spacing values resolved into component CSS; no Tailwind runtime |
| `desktop/angular/src/app/shared/netquery/line-chart/line-chart.ts` | `23a9007cf396a62059529c9e8168dfd31ec8b4ad` | D3 SVG/axes/line/area/point lifecycle adapted to standalone Angular; no zero-fill, null rate gaps and exact tooltips; owned ResizeObserver instead of upstream root coupling |
| `desktop/angular/src/app/shared/netquery/circular-bar-chart/circular-bar-chart.component.ts` | `f2b736d9ba728a1c24b9e5eeed3f7a6b234494ec` | Actual indexed D3 stacked radial bars, ticks and legend; bounded top consumers plus conserved remainder, exact values, accessible companion rows |
| `desktop/angular/src/app/pages/dashboard/dashboard.component.scss` | `ba37e52754e3342a8f1e723b90bf141054e38cd1` | Four-track / 16px / 150px dense responsive panel geometry; remove SPN/news |
| `desktop/angular/src/app/layout/navigation/navigation.scss` | `4683bec54862d4ec9af50aced9db663edf45eb8f` | 64px vertical rail with actual active/hover treatment; named native buttons instead of inaccessible clickable divs |
| `desktop/angular/src/app/shared/netquery/tag-bar/tag-bar.html` | `f1161e58aabe1cf13cf730071e89be09de1d4240` | Field/value removable filter pills; native keyboard-focusable removal button |
| `desktop/angular/src/app/shared/netquery/connection-row/conn-row.{html,scss}` | `ff09c532a4f62d92aa366db5c3eb2e834a647954`, `0d737830e303d624706f8a5c33831bd592c9484c` | Dense responsive aligned fact row; source/candidate badges replace unsupported firewall verdicts |
| `desktop/angular/src/app/shared/netquery/connection-details/conn-details.{html,scss}` | `fcbe03cbda2269f8a9487117acbf6fd18de6adb7`, `f850b0030fbb7e586c51dad6078be6d0b082f9fe` | Structured expandable evidence sections / 250px columns; observed fields and uncertainty, no invented socket/TLS/lifetime |
| `desktop/angular/projects/safing/ui/src/lib/accordion/accordion.html` | `4d47b842f610bf25f4d16eaf61b00ab0b120d8c6` | Active header/content projection replaced with native details/summary for browser keyboard and accessibility semantics |
| `desktop/angular/projects/safing/ui/src/lib/pagination/pagination.html` | `dec63df8a42e1a32ebe9193cb768622621ad2406` | Previous/Next paginator and current-page treatment, cursor history rather than unsupported arbitrary page jumps |

The native shell is an original minimal WebView2/WinForms host, not a copy of
Portmaster's service controller. The Angular application does not import upstream network,
firewall, SPN, branding, telemetry, subscription or update modules. Framework
dependency notices are separate from this source attribution; exact dependency
versions and sources are captured in package-lock.json and packages.lock.json.

Build: install locked desktop npm dependencies with `npm ci`, then `npm run build`;
build `native` with `dotnet build -p:RestoreLockedMode=true`. Python 3.13+ and pywin32 provide
the existing owning-user collector during source development. Stage 9 must bundle
and verify the supported runtime; developer commands are not the final installer.
The UI/backend protocol has no dependency on a Portmaster installation.

Native host choice: the inspected Portmaster Tao patch is pinned to 0.32.8;
current Tauri 2.12.3 requires Tao 0.37. The upstream Tauri fix PR 15411 was
still open/unmerged on 2026-10-13 (Tao PR 1334 closed unmerged). Copying the
old dependency graph or pretending its patch applies to current Tauri is not
required to reuse the Angular widgets. The Windows-only host uses the installed
WebView2 runtime, navigation restrictions, an owner-authenticated fixed pipe and
no browser-accessible token. This is a host dependency decision, not replacement
of the requested widget design or reduction of TailDNS/core versions.
