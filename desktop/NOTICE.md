# TailD desktop source and licensing

This desktop component is GPL-3.0-only, including its adaptations of Safing
Portmaster. Copyright Safing and contributors; TailD changes copyright 2026
TailD contributors. The inherited TailDNS/core BSD notices remain unchanged.
This component's license is not a claim that process separation eliminates
distribution obligations. Any distribution must include this notice, GPL text,
all applicable dependency notices, and the complete corresponding source and
build instructions for the covered desktop work. No distribution is authorized
or performed by the current implementation stage.

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
