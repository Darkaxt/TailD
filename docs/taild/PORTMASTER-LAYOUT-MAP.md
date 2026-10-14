# Portmaster full layout and widget inventory

## Scope and evidence

Source: `safing/portmaster`, `development` commit
`bb6c44468a5d66bddb13bf3c43fcb2625c326ca9`, committed
2026-10-12 15:29:31 UTC; branch identity checked 2026-10-14.
This is a source-level map of the main desktop Angular application. It covers
all declared page routes, page layouts, internal tab groups, contextual
overlays and shared user-facing widget families. It does not claim a runtime
walkthrough, exhaustive backend configuration values, external website layouts,
or an inventory of the separate browser extension and native tray menus.

The pinned [source inventory](portmaster-source-inventory.json) contains 73
HTML templates under `desktop/angular/src/app/`, including 27 page templates.
All 73 were scanned for active tab declarations with HTML comments excluded;
the seven tab-owning templates are accounted for below. Relevant templates,
controllers and layout styles were inspected for conditions and navigation.
The [short report and navigation graph](PORTMASTER-LAYOUT-REPORT.md) provide
the overview. Source references below all use the same immutable commit.

Notation: **BW** means the Bandwidth feature entitlement; **History** means
the History entitlement; **SPN** means the Safing Privacy Network entitlement.
The inspected UI labels bandwidth/history upgrades as Plus and SPN upgrades
as Pro. These are source labels, not a separately verified current pricing
catalogue. **Advanced** and **Developer** identify expertise visibility gates.
Widget names describe UI labels, not independently audited metric semantics.

## Global shell and layout

Sources: [application shell][shell], [shell controller][shell-ts],
[shell styles][shell-css], [navigation][nav], [sidebar][side],
[sidebar styles][side-css].

| Region | Layout and contents | Navigation or behavior |
|---|---|---|
| Navigation rail | Persistent 64 px strip at the left | Dashboard via logo/security lock; Network Activity; Apps and Profiles; SPN; Global Settings; Get Help |
| Expandable sidebar | 419 px application/status panel beside the rail | Can collapse; at window widths ≤1200 px it overlays content with a dismissal backdrop; forced overlay is also supported |
| Main page | Remaining width; page-specific scrolling within a viewport-height shell | Router outlet; content-width breakpoint classes at 640, 768, 1024, 1280 and 1536 px |
| Header controls | Breadcrumbs/title and expertise selector on applicable pages | Simple and Advanced Interface; Developer choice exposed when the saved level is Developer |
| Shell loading state | Full-screen blurred, semitransparent layer, animated logo and message | Connection/reconnection/loading presentation, separate from individual chart/list loading states |
| Notifications and prompts | Bell/sidebar, conditional prompt indicator and pending count | Notification details and in-app actions; prompt list grouped by application |
| Tools menus | Bottom rail menus | Version/tools, pause/resume, shutdown/restart; details below |

The Dashboard's 1024 px layout switch depends on **available main-content
width**, not simply monitor width. Expanding a non-overlay sidebar can change
the Dashboard composition without resizing the window.

### Sidebar widgets

Sources: [network scout][scout], [scout controller][scout-ts],
[feature scout][feature-scout], [security indicator][lock],
[notification list][notifications], [notification detail][notification],
[prompt list][prompts], [expertise selector][expertise].

| Widget | Contents | Actions and conditions |
|---|---|---|
| Security indicator | Protection state and notification cue | Opens Dashboard |
| Feature scout | Feature badges and SPN connection/home-node state | Developer-gated; package-dependent; SPN link and transport/IP tooltip |
| Notification list | Severity/broadcast icon, title/message preview, eligible action buttons | Opens notification detail: Markdown message, actions and selected/invalid state |
| Application scout search | Search input and application count | Filters the sidebar application list |
| Scout sorting | Static, A–Z, Z–A, total/denied/allowed connections, SPN identities; sent/received/total bytes when BW allows | Changes ranking; byte sort replaces the connection count indicator with sent/received totals |
| Application rows | App icon/name, allowed/total indicator or byte totals, app/settings/map shortcuts | Opens application or SPN context; identity expansion requires SPN enabled |
| Identity cards | Country flag, exit IP, connection count, hop count | Connection count opens a scoped monitor query; hops opens SPN with app/pin parameters; initially up to four identities with show-more/less |
| Login branch | Account login instead of scout when `spnLoginRequired` | Template branch exists, but sidebar controller initializes this to false; not assumed to appear automatically |
| Prompt panel | Per-app pending count, domain/IP prompts, allow/block buttons | Allow/block all current prompts; change default app policy; app settings shortcut; show-more/less and empty state |

### Rail tools and overlays

| Menu or overlay | Available controls |
|---|---|
| Version and Tools | Core version, release channel/nonstable marker, check updates, changelog, reload UI, introductory setup (Developer), reinitialize SPN, logout completely, reset notification state, clear DNS cache, cleanup history, open data directory, copy debug information |
| Pause and Resume | Current paused state/until time; SPN-only or all interception pause for 5 minutes, 15 minutes or 1 hour; resume. SPN options depend on SPN/paused state and are disabled while interception is paused |
| Shutdown and Restart | Shutdown and restart actions |
| Global quick search | Ctrl+Space opens an inline connection-query search overlay; suggestions and keyboard selection; searchable attributes feed the shared explorer |
| Contextual information | Tip-up help, optional Markdown setting help dialog, tooltips and rotating expert tips |
| Action feedback | Success/error indicator, optional title/message and dismissal |
| Close UI screen | Clarifies UI closure versus engine shutdown; never-show-again checkbox and close/cancel actions |
| Standalone prompt entrypoint | Application icon/name/path, requested domain/IP/country and server-supplied decision actions; separate surface, not a main navigation tab |

Sources: [navigation][nav], [quick search][quick-search],
[setting help][generic-setting], [action feedback][feedback],
[close UI][close-ui], [standalone prompts][prompt-window].

## Page routes and navigation

Source: [route declarations][routes].

| Route | Surface | Entry and exit relationships |
|---|---|---|
| `/` | Redirect to Dashboard | Default entry |
| `/dashboard` | Dashboard | Logo/security lock; widgets open monitor/app/settings/account contexts |
| `/monitor` | Network Activity | Rail; dashboard summaries; SPN exits; scout identities |
| `/app` | Redirect to `/app/overview` | Rail Apps and Profiles |
| `/app/overview` | Application/profile catalogue | Opens `/app/:source/:id`; profile management dialogs |
| `/app/:source/:id` | Selected application | Four tabs; breadcrumb returns to catalogue; connection/settings query parameters carry context |
| `/monitor/profile/:source/:profile` | Legacy redirect to monitor | Declares redirect, not a separate page; retained profile filtering is not established by this declaration |
| `/spn` | SPN map | Rail; app/scout links can supply app/pin query parameters |
| `/settings` | Global settings | Rail or contextual setting link, optionally `setting` query parameter |
| `/support` | Get Help | Rail; resources or internal support form |
| `/support/:id` | Selected report form | Three configured report types; breadcrumb returns to help |
| `**` | Fallback redirect to Dashboard | Source places this before the Dashboard route; intended flow is mapped, runtime routing requires separate validation |

Internal application tabs use IDs `connections`, `settings`, `details`,
`insights`, with tab/query state handled by the tab/router integration. They
are not four separate page routes. Country/node/profile/process dialogs also
use tab groups but do not create primary navigation destinations.

## Dashboard

Sources: [template][dashboard], [controller][dashboard-ts],
[grid styles][dashboard-css], [feature cards][feature-card],
[feature navigation][feature-card-ts]. No top-level tab bar; the News panel
internally uses a dynamic tab carousel.

### Spatial organization

Four-column grid; cells below denote relative areas, not pixel dimensions.

```text
Main content at least 1024 px           Main content below 1024 px
┌───────────────────────────────┐      ┌───────────────────────────────┐
│ Header                        │      │ Header                        │
├───────────────────────┬───────┤      ├───────────────────────────────┤
│ Features              │ News  │      │ Features                      │
├───────────────────────┤       │      ├───────────────┬───────────────┤
│ Recent Activity       │       │      │ Recent        │ News          │
├───────────────────────┴───────┤      │ Activity      │               │
│ Connection charts             │      ├───────────────┴───────────────┤
├───────────────┬───────────────┤      │ Connection charts             │
│ Country tiles │ World map     │      ├───────────────┬───────────────┤
├───────────────┤               │      │ Blocked apps  │ Country tiles │
│ Blocked apps  │               │      ├───────────────┴───────────────┤
├───────────────┼───────────────┤      │ World map                     │
│ Top consumers │ Bandwidth     │      ├───────────────┬───────────────┤
└───────────────┴───────────────┘      │ Top consumers │ Bandwidth     │
                                       └───────────────┴───────────────┘
```

Feature cards auto-fit with a 300 px minimum; summary/country/application
tiles auto-fit at 150 px. Map and entitled bandwidth panels have a 400 px
minimum height. The narrower definition still retains a four-column grid;
it is not evidence of a fully mobile layout.

### Available widgets

| Widget | Presentation | Conditions and interaction |
|---|---|---|
| Plan/account header | Plan name, expiry or next renewal; login/account button | Opens account dialog; Free fallback label; prominent username greeting is commented out |
| Features | Dynamic cards: icon/name, package ribbon, comment, beta/coming-soon/disabled/active state, optional toggle | Supplied by enabled-features service; disabled card opens pricing; enabled card opens relevant global setting/scope; configured boolean can be toggled |
| Connections Blocked | Summary metric | Opens monitor with verdict 3/4 filter |
| Active Connections | Summary metric | Opens monitor with active filter |
| Active Apps | Summary metric | Opens monitor with active filter and profile grouping |
| Data Received and Data Sent | Two byte totals | BW; otherwise upgrade placeholders; no click action declared |
| SPN Identities | Summary metric | SPN value or upgrade placeholder; opens tunneled connections grouped by exit node |
| Active/Blocked Connections | Time-series chart | Label opens monitor |
| Connections Tunneled through SPN | Time-series chart | SPN; label opens tunneled monitor query |
| Recent Connections per Country | Flag/name/count tiles | Click filters monitor by country; hover highlights the corresponding map country |
| Recently Blocked Applications | App icon/name/count ranking | Click opens app; hover highlights associated countries; explicit no-blocked-apps state |
| Recent Connection Countries | World map, beta label | Highlights countries with observed connections; linked hover from country/app tiles. Do not assume the SPN page's country/node dialogs exist here |
| Recent Top Consumers | Circular stacked sent/received application bars, beta | BW or upgrade placeholder; controller ranks up to ten nonzero consumers |
| Recent Bandwidth Usage | Sent/received time series, beta | BW or upgrade placeholder |
| News | Dynamic carousel: title/link, Markdown body/footer, optional progress, dot navigation | Pending/loading state; disabled-intel-updates state links to its setting |

The controller queries live connection data. The UI's “recent” wording and
ten-minute empty-state text are not a universal configurable dashboard time
range. There is no global dashboard date-range control in this template.

## Network Activity and the shared explorer

Sources: [monitor page][monitor], [explorer][explorer],
[explorer controller][explorer-ts], [search][search], [filter chips][chips].

### Page frame

Breadcrumb/title, expertise selector, help tip, history earliest-date/count,
clear-history action, and history-enable or subscription prompt. The page
explains live recent connections versus optional retained history. It embeds
one explorer and persists its global filter. There are no separate DNS,
traffic and history tabs declared on this page; these are query dimensions.

### Explorer widgets in visual order

| Region | Widgets and available behavior |
|---|---|
| Applied query | Removable field/value chips, copy-query control, clear-all action; sticky while chips exist |
| Search row | Typed field query/free text, suggestions with connection counts, keyboard selection and Reload |
| Primary filters | Multi-select domain, AS organization, country, application/profile and allowed state by default; searchable suggestions and arbitrary dynamic values |
| More filters | Combined network scope, incoming/outgoing direction, active state and SPN-tunneled state |
| History selector | History-gated date range, clear range and presets: Today, Last 24 Hours, Last 7 Days, Last Month |
| Grouping | Multi-select domain, AS organization, country, direction, binary path, application/profile |
| Ordering | Same fields plus started and ended timestamps |
| Charts | Connections time series; BW-gated Data Usage beside it; loading/empty-chart overlay |
| Results metadata | Filtered result count versus total connections; last-reload age |
| Automatic refresh | Disabled, every 10 seconds, every minute or every 5 minutes; interval/countdown display |
| Results | Paginated accordion rows; multiple expansions allowed; nested pagination/accordions for grouped results |
| Group header | Allowed/total count indicator, grouped field labels, optional app/node/location rendering and mini time series; use-as-filter and app-settings actions |
| Loading and expired groups | Loading-connections indicator; explanation when grouped live connections have aged out |
| Advanced tips | Rotating keyboard/filter interaction hints |

Free text searches domain, AS organization, path, application name and remote
IP. Additional typed fields include IPs/ports, protocol, verdict, encryption,
connection type, internal status, timestamps, ASN, exit node and profile
revision. These are not all separate visible dropdowns. Shift-click adds a
supported attribute to the filter; Ctrl-click copies it.

### Connection row and expanded evidence

Sources: [row][row], [details][connection], [process dialog][process].

| Surface | Available widgets and fields | Actions or gates |
|---|---|---|
| Collapsed row | Verdict indicator/reason tooltip, domain or network scope, location/flag, app icon/name, direction, peer IP/port or DNS marker, started/ended age, applied setting/scope | Expand; attribute filter/copy; menu for app/global setting, allow/block domain/IP, Advanced JSON copy. Location/time/reason columns hide progressively at narrower breakpoints |
| Common evidence | Start/end/duration, binary path, decision reason, applied app/global setting | Advanced: local address/verdict; Developer: connection ID, profile revision, internal flag |
| IP evidence | Direction, protocol, encrypted/SPN states, optional received/sent bytes, domain/scope, peer, country, ASN and organization | Filterable supported attributes |
| TLS evidence | Version, SNI, leaf certificate and trust chain | Only when TLS extra data is present |
| DNS evidence | Domain, question and response code | DNS records only; Advanced cache/expiry fields |
| SPN route | Device → home/transit/exit hops → destination | Tunneled global connection with route evidence; Advanced node/operator/ASN, Developer node IDs/path cost/algorithm; explicit unavailable-route message |
| Split Tunnel | Interface and IP | Only when split-tunnel evidence exists |
| Connection bandwidth | Received/sent time series, start/end markers, tooltips | Only when bandwidth samples exist |
| Footer actions | Process Details, JSON copy, allow/block, App Setting, Global Setting | Process lookup availability; Advanced JSON; rule actions depend on supported connection type; setting links require an applied option key |

Process Details has **General** and **Environment** tabs. General includes
name/icon, user, executable/path, command line and tags; Advanced adds PID,
group and parent IDs with group/parent navigation. Path and command line can
start profile creation. Environment lists key/value pairs with profile
creation actions, or an explicit empty state. Close returns to the explorer.

## Apps and Profiles

Sources: [catalogue][apps], [application page][app],
[application controller][app-ts], [Insights][insights],
[Insights controller][insights-ts].

### Application catalogue

Search plus expertise control precede grouped profile cards: Active, Recently
Edited and All. Cards show icon/name, Advanced path, modified-settings dot and
fingerprint tooltip; internal profiles are Developer-only. Loading placeholders
and a no-search-match state are defined.

Manage offers create/import and merge/delete selection mode. Selected cards
gain checkboxes and a selected-count menu with merge, delete and cancel.
Ordinary selection opens the application's detail page.

### Shared application header

| Region | Widgets and conditions |
|---|---|
| Identity | Apps breadcrumb, expertise, icon/name, path/directory, binary, active connection count; collapsible header |
| History | Earliest retained date/count and remove-history action; empty or entitlement state |
| Quick controls | Block Connections or Prompting link; Keep History (History); Use SPN and SPN Exit (SPN); Split Tunnel; interfering-settings indicators |
| Profile menu | Edit, export and delete profile |
| Summary metrics | Connections, blocked percentage, received and sent bytes; stats-dependent visibility, BW upgrade labels for bytes |

### Application tabs

| Tab | Widgets | Navigation and important conditions |
|---|---|---|
| **Connections** | Shared explorer, with allowed/AS organization/country/domain dropdowns; charts, grouped rows, pagination and expanded evidence | Unmodifiable merged profile predicate uses source and ID; global explorer behavior otherwise shared |
| **Settings** | Setting search, external help, app-specific guidance, compact settings hierarchy, modified markers, inheritance locks, stacked values/reset-to-global | Empty state when entirely inherited, with Edit Settings action; global-setting deep links; obsolete View All/View Active selector is commented out |
| **Details** | Name/presentation path, creation/edit times, description/warning Markdown, warning update time, fingerprints, delete panel and copy-debug action | Developer metadata includes source/ID/revision/internal state and linked layers; fingerprint type/key/operation/value; warning flag on tab |
| **Insights** | Connections line chart; beta Data Usage line chart; beta Countries circular bar chart | Two-column grid, minimum-height panels. Template does not repeat BW gates; actual backend data availability still applies |

**Source correctness caution:** Insights applies the selected profile to its
connection and bandwidth chart requests, but its country aggregation filters
only internal status and nonempty country. Its placement inside an application
does not establish that the country values are application-specific. Do not
copy that predicate omission into TailD.

### Quick control details

Sources: [connection policy][qs-policy], [history][qs-history],
[SPN use][qs-spn], [exit choice][qs-exit], [split tunnel][qs-split].

- Block Connections toggles the default policy; prompting opens the app's
  default-action setting. Conflict tooltip links to interfering settings.
- Keep History is disabled when the overall history feature is disallowed.
- Use SPN and SPN Exit show a disabled link to the SPN page if SPN is not
  enabled. Exit selection includes Automatic and supplied rule presets.
- Split Tunnel links to its global module setting when disabled, and explains
  conflicts with SPN or other settings.

### Profile management dialogs

Sources: [edit/create][edit], [merge][merge], [import][import], [export][export].

| Dialog or tab | Available widgets |
|---|---|
| Create/Edit — General | Required name, description, icon chooser/reset/preview/errors; Developer ID. UI states PNG/JPG, ≤512×512 and smaller than 10 kB |
| Create/Edit — Process Matching | Fingerprint rows: Tag, Command Line, Environment or Path; conditional key/tag selector; Equals/Prefix/Regex; value; add/remove |
| Create/Edit — Copy Settings | Searchable profile selector, add, ordered drag/drop source list and remove; precedence explanation |
| Create/Edit footer | Cancel, Save with form validity, Delete in edit mode |
| Merge | Primary profile selector, new name, merge/cancel; primary settings retained while metadata/fingerprints/icons are combined into a new profile |
| Import profile/settings | Editable YAML/paste or Choose File; parsed warnings; conditional allow-unknown, allow-replacement, reset-settings, restart options; Import |
| Export profile/settings | Export content with syntax presentation; copy to clipboard and Save |

## SPN

Sources: [page][spn], [country hover][country-hover],
[country dialog][country], [node overlay][node-overlay],
[node dialog][node], [node list][node-list], [route widget][route-widget],
[legend][legend], [promotion carousel][spn-carousel].

### Map page and overlays

| Region | Available widgets | Conditions and flow |
|---|---|---|
| Main canvas | Geographic basemap, node symbols and route paths | Full-page map, not Dashboard's connection-country map |
| Page controls | Expertise selector, loading banner, rotating interaction tips | A live-mode toggle exists only in a disabled HTML comment |
| Disabled/account gate | Feature carousel, Login or Enable SPN button, Pricing link | No current user or SPN disabled; entitled user can enable instead of login |
| Default legend | Safing/community node counts, transit and exit counts | Replaced by country hover summary while hovering |
| Country hover | Flag/name, Safing and community counts, click-for-details hint | Country click opens a draggable details dialog |
| Node overlay | Flag/name, IPv4/IPv6, operator and current home/exit/transit role explanations | Draggable/pinnable presentation; menu opens details/exit connections or copies ID |
| Node interaction | Selection, route highlighting and contextual overlays | Ctrl-click opens details directly; Shift permits multiple overlays; moved overlays persist; double-click resets overlay position |

### Country dialog tabs

| Tab | Widgets and navigation |
|---|---|
| **Nodes** | Node table; hover highlight; open selected node details |
| **Statistics** | Total live nodes, exit nodes and nodes in use, each with applicable Safing/community breakdown |
| **Apps** | App icon/name, exit-connection count, connection/settings shortcuts; connections carry the country-node filter |

### Node dialog tabs

| Tab | Widgets and navigation |
|---|---|
| **Details** | Country/name/operator, offline/issues state, ID, verified owner, first seen, IPv4/IPv6 with ASN/organization, states, session-active flag, hop distance and exit-connection count; count opens monitor filtered by exit node |
| **Route** | Device/hops/destination route diagram; only when the node has a route |
| **Connected Nodes** | Node table; this instance explicitly disables click/hover drill-down |

The reusable node table shows name, operator, role, IPv4/IPv6 and optional
latency/capacity when lane data is provided. The route widget labels Home and
Exit; Advanced adds node/operator/ASN information and Developer adds IDs.

The disabled-SPN promotion carousel has five active slides: multiple identities,
privacy customization, privacy-oriented architecture, VPN comparison messaging,
and a VPN/SPN/Tor feature table. Arrow and dot controls switch slides. Regional
access and automatic geo-unblocking items are commented out, not available
widgets. Marketing claims are not verified functionality in this mapping.

## Global Settings

Sources: [settings page][settings], [settings hierarchy][config],
[subsystem definitions][subsystems], [generic control][generic-setting],
[basic inputs][basic-setting], [filter-list tree][filter-list],
[rule editor][rule-list], [ordered list][ordered-list].

No page-level tabs. Search/help/expertise sit above a two-region settings view:
a subsystem/category anchor navigator and the scrollable settings cards.
The navigator hides below its medium breakpoint. Groups can collapse and show
modified-value markers. Known subsystem definitions cover Core, Secure DNS,
Privacy Filter, Network History, SPN and Split Tunnel, with an Other fallback;
actual groups and visibility depend on returned metadata and expertise.

| Control family | Available widgets and states |
|---|---|
| Basic values | Boolean toggle; text and numeric inputs with optional units; enumerated dropdown; JSON/text-area fallback |
| Endpoint rules | Allow/block action, entity input, edit/confirm/reset, reorder, add, select and bulk remove/cancel |
| Filter lists | Hierarchical checkboxes, expand/collapse, selected-child marker, name/ID/description, license and website |
| Ordered/string lists | Add/edit/delete/reorder; fixed-order variant where appropriate; read-only inherited lists |
| Setting chrome | Name/help tip, quick presets, saved/rejected/restart/reload/upgrade status; beta/experimental/Advanced/Developer labels |
| Application inheritance | Lock/unlock, inherited-global link, reset-to-global, user override marker and stacked global values |
| Import/export | Import dialog; export-selection mode with per-setting checkboxes, Save and Cancel Export; content/copy/download dialog |

The exact option/category catalogue is backend-driven. Listing a universal
fixed set of option names here would conflate a particular engine build with
the frontend layout. Dynamic list contents and feature-card names are the
remaining runtime-data boundary, not missing page/tab mappings.

## Get Help and report forms

Sources: [help page][help], [configured choices][help-types],
[report form][help-form], [submission progress][help-progress].

| Surface | Available widgets and flow |
|---|---|
| Resources | Wiki/FAQ, settings handbook and blog external links |
| Communities and Support | Discord, Mastodon, Twitter and support-email links |
| Make a Report | Bug report, improvement suggestion, compatibility report → `/support/:id` |
| Shared form frame | Breadcrumb, expertise, title/introduction, required summary/title input with Copy, form-specific text areas with Copy; optional repository selector if configured |
| Bug report | What happened, expected behavior, reproduction steps, additional information; editable debug information |
| Improvement suggestion | Proposed change and reason/need; no debug panel configured |
| Compatibility report | What worked, what did not, additional information; editable debug information |
| Debug information | Version/build details, editable content and Copy; warning about uploaded diagnostic information |
| Related Issues | Up to eight matches, open/closed status, repository/user/time and external issue link; empty state |
| Submission | GitHub preparation/open action or private ticket; progress dialog with upload/create/error/done states, generated issue URL/open/copy actions and Close |

The old FAQ search/results block is commented out. Report repository arrays
are empty in the inspected configuration, so the optional repository selector
is not treated as currently populated. Submitting a report is an external
write; nothing was submitted during this analysis.

## Account and introductory setup

Sources: [account][account], [login][login], [intro sequence][intro],
[welcome][intro-1], [tracker setup][intro-2], [DNS setup][intro-3],
[help introduction][intro-4].

Account Details is a dialog reachable from Dashboard and SPN. It shows plan,
subscription/access dates, payment provider where applicable, username and
device name; Developer adds account state, feature IDs, device ID and login
time. Actions: external account page, logout, refresh and close. A logged-out
account instead displays username/password login, sign-in, registration link
and a forced-logout warning when applicable.

Introductory setup is a four-step overlay, not four rail tabs:
Welcome/Quick Setup → tracker-list customization → DNS quick presets/custom
state → contextual-help introduction. Its stepper permits aborting at the first
step. The rail's replay action is Developer-gated.

## Source boundaries and reuse cautions

1. All seven active tab-owning templates are represented: application detail,
   Dashboard news, SPN country, SPN node, SPN promotion carousel, profile editor
   and process details. No additional primary tabs were inferred from filenames.
2. The wildcard-before-Dashboard route ordering is preserved as an observation;
   the graph represents intended/declared navigation, not proof of route success.
3. Application Insights geography is not visibly profile-scoped in its query.
4. Shared SPN status/network-status templates exist, but the inspected main
   shell/sidebar does not instantiate them. They are not extra active tabs.
   The former defines SPN status/toggle/chart/identities and upgrade controls;
   the latter defines expandable network-issue cards with external links.
5. Feature/setting/news catalogues and optional DNS/TLS/route/process evidence
   depend on backend/account/record state. Missing data is not evidence of a
   missing layout; a defined layout is not evidence of available telemetry.
6. This analysis changes no TailD acceptance criteria or implementation scope.
   UI reuse must preserve TailD's source coverage and honest metric semantics;
   Portmaster rule actions or SPN controls cannot be imported as pretend support.

[routes]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/app-routing.module.ts
[shell]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/app.component.html
[shell-ts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/app.component.ts
[shell-css]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/app.component.scss
[nav]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/layout/navigation/navigation.html
[side]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/layout/side-dash/side-dash.html
[side-css]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/layout/side-dash/side-dash.scss
[scout]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/network-scout/network-scout.html
[scout-ts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/network-scout/network-scout.ts
[feature-scout]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/feature-scout/feature-scout.html
[lock]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/security-lock/security-lock.html
[notifications]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/notification-list/notification-list.component.html
[notification]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/notification/notification.html
[prompts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/prompt-list/prompt-list.component.html
[expertise]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/expertise/expertise-switch.html
[quick-search]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/netquery/search-overlay/search-overlay.html
[feedback]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/action-indicator/indicator.html
[close-ui]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/exit-screen/exit-screen.html
[prompt-window]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/prompt-entrypoint/prompt.html
[dashboard]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/dashboard/dashboard.component.html
[dashboard-ts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/dashboard/dashboard.component.ts
[dashboard-css]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/dashboard/dashboard.component.scss
[feature-card]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/dashboard/feature-card/feature-card.component.html
[feature-card-ts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/dashboard/feature-card/feature-card.component.ts
[monitor]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/monitor/monitor.html
[explorer]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/netquery/netquery.component.html
[explorer-ts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/netquery/netquery.component.ts
[search]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/netquery/searchbar/searchbar.html
[chips]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/netquery/tag-bar/tag-bar.html
[row]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/netquery/connection-row/conn-row.html
[connection]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/netquery/connection-details/conn-details.html
[process]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/process-details-dialog/process-details-dialog.html
[apps]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/overview.html
[app]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/app-view.html
[app-ts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/app-view.ts
[insights]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/app-insights/app-insights.component.html
[insights-ts]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/app-insights/app-insights.component.ts
[qs-policy]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/qs-internet/qs-internet.html
[qs-history]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/qs-history/qs-history.component.html
[qs-spn]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/qs-use-spn/qs-use-spn.html
[qs-exit]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/qs-select-exit/qs-select-exit.html
[qs-split]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/qs-use-splittun/qs-use-splittun.html
[edit]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/edit-profile-dialog/edit-profile-dialog.html
[merge]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/app-view/merge-profile-dialog/merge-profile-dialog.component.html
[import]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/import-dialog/import-dialog.component.html
[export]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/export-dialog/export-dialog.component.html
[spn]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/spn-page.html
[country-hover]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/country-overlay/country-overlay.html
[country]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/country-details/country-details.html
[node-overlay]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/pin-overlay/pin-overlay.html
[node]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/pin-details/pin-details.html
[node-list]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/pin-list/pin-list.html
[route-widget]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/pin-route/pin-route.html
[legend]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/map-legend/map-legend.html
[spn-carousel]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/spn/spn-feature-carousel/spn-feature-carousel.html
[settings]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/settings/settings.html
[config]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/config-settings.html
[subsystems]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/subsystems.ts
[generic-setting]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/generic-setting/generic-setting.html
[basic-setting]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/basic-setting/basic-setting.html
[filter-list]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/filter-lists/filter-list.html
[rule-list]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/rule-list/rule-list.html
[ordered-list]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/config/ordererd-list/ordered-list.html
[help]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/support/support.html
[help-types]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/support/pages.ts
[help-form]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/support/form/support-form.html
[help-progress]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/pages/support/progress-dialog/progress-dialog.html
[account]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/spn-account-details/spn-account-details.html
[login]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/shared/spn-login/spn-login.html
[intro]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/intro/intro.module.ts
[intro-1]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/intro/step-1-welcome/step-1-welcome.html
[intro-2]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/intro/step-2-trackers/step-2-trackers.html
[intro-3]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/intro/step-3-dns/step-3-dns.html
[intro-4]: https://github.com/safing/portmaster/blob/bb6c44468a5d66bddb13bf3c43fcb2625c326ca9/desktop/angular/src/app/intro/step-4-tipups/step-4-tipups.html
