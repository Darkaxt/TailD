# TailD: inherited TailDNS client and Control D analytics

Authoritative specification, 2026-10-07. Implementation is already authorized.

## Scope and lineage

TailD is a public, history-preserving derivative of **Darkaxt/TailDNS**.
It is not a fresh fork of vanilla Tailscale or an independent DNS/UI rewrite.
GitHub returned the owner's existing TailDNS fork when a second native fork in
the same network was requested. TailD therefore uses a normal public repository
with the complete TailDNS main history and explicit upstream synchronization;
it must not misrepresent a GitHub fork badge or detach the existing repository.

The approved product direction is Control D policy/analytics combined with host
application identity and network traffic metrics. Control D remains the DNS
policy engine; GlassWire/AppControl retain their existing enforcement roles.
This first implementation increment establishes inheritance and begins the
narrow read-only data slice from [TailDNS issue 9](https://github.com/Darkaxt/TailDNS/issues/9).
It does not promise full API breadth, dashboards, or a released TailD client.

## Requirements and acceptance criteria

- **R01 Public lineage:** create Darkaxt/TailD from verified TailDNS main
  57c220e807b0d295c5946d8293bd3f636a4f85f5, preserving ancestry, source, licenses
  and attribution. Do not copy existing dirty working files, signing secrets,
  release tags or unrelated branches. Verify public visibility and ancestry.
- **R02 Automatic inheritance:** a daily and manually runnable GitHub workflow
  must merge captured TailDNS main into TailD main after checks, not merely detect
  updates or leave passing candidates indefinitely unmerged. Preserve local
  analytics commits, fail on genuine merge conflicts/check failures, never force
  push main, and never deploy/publish a release as a side effect. Test no-update,
  successful merge, local preservation and conflict behavior with real Git repos.
  Verify the workflow against the real TailDNS boundary.
- **R03 DNS and UI inheritance:** keep TailDNS DNS behavior and its exact shared
  core require/replace pin. The core at github.com/Darkaxt/tailscale contains the
  Windows tray/UI port, daemon, resolver, installer and updater. TailDNS pin
  updates must reach TailD without a copied UI implementation. Verify the pin
  against captured upstream plus inherited DNS/branding/lifecycle contracts and
  a no-signing Linux Android/core build gate when source changes.
- **R04 Workflow isolation:** disable inherited TailDNS release/detection jobs in
  TailD's GitHub settings, preserving their source for merges. TailD CI uses no
  production credentials; verification jobs have read-only repository authority.
  A separate promotion job may push only the exact checked candidate, with
  ordinary fast-forward semantics and an unchanged starting-main check. New
  inherited workflow names require explicit review before promotion. Do not
  modify existing TailDNS/core repositories or their maintenance heartbeat.
- **R05 Truthful identity:** TailD README describes its actual implementation
  status, upstream and development commands. Retain inherited app/package names
  until a separately verified TailD distribution exists; do not publish a second
  app with the existing signing identity or redirect installed TailDNS updates.
- **R06 First Control D reads:** implement a narrowly scoped, read-only command
  for documented device/profile inventory and the documented CSV route, including
  the personal-account availability verified with the user's READ token below.
  Resolve the analytics region from authenticated account metadata or an explicit
  instance label; validate it before constructing a provider-owned hostname.
  No API writes, retry loops, browser scraping or guessed
  analytics endpoints. Use a Read bearer token supplied locally, never a resolver
  ID as authentication. No token in command arguments, URLs, output, logs or Git.
  Reject credential-bearing redirects and malformed response envelopes, report
  sanitized errors, preserve raw decision codes rather than inventing meanings.
  Private returned data remains local. Test real HTTP boundary behavior with
  synthetic fixtures, then verify at least one real account read and DNS decision
  using authorized credentials before considering this requirement complete.
- **R07 First joined record:** obtain one real application connection including
  destination and transferred network bytes from a validated AppControl or
  GlassWire interface; join it to one Control D decision and Windows TailDNS
  device context. Export a local joined record with original-source provenance,
  match method and uncertainty. Temporal/IP correlation is not deterministic
  process-to-domain attribution. Do not build broad storage, adapters, UI or
  background telemetry before this real slice passes.

### R07 current implementation contract

The October 7 continuation authorizes the collector/reader implementation.
The first product-purpose slice is an on-demand local reader, not installation
of a continuous elevated service. Query one explicitly selected observed
`1sec` statistics database and UTC interval, using SQLite read-only transactions
including WAL. Read application identities from the primary application table;
retain row/table/database provenance, raw codes and original binary field
fingerprints. Do not sum overlapping `1sec`/`30sec`/`600sec` sources or claim
individual socket/PID byte attribution from these time-bucket counters.
Reject malformed records/schema; keep well-formed unsupported address families
explicitly unknown rather than guessing or silently discarding them. Export
query bounds, truncation and separate-database consistency limitations.

Correlate only with an explicitly identified Control D endpoint and captured
Windows TailDNS device context. Require a matching destination IP from the DNS
answer plus a preceding decision inside an explicitly chosen correlation age
window. Preserve all matching candidates and ambiguity. This is an analytical
time window, not an execution timeout or a proof of DNS TTL/cache validity.
Do not allocate the same bucket's bytes repeatedly across candidate domains or
interpret undocumented action codes as allowed/blocked. Private raw inputs and
joined output stay outside Git; summaries contain counts only. A real joined
record remains required before R07 is COMPLETE.

## Confirmed boundaries, not presumed capabilities

As of 2026-10-07:

- Control D documents Read/Write bearer permissions and device/profile APIs.
  [Authentication](https://docs.controld.com/reference/authentication),
  [devices](https://docs.controld.com/reference/get_devices),
  [profiles](https://docs.controld.com/reference/get_profiles),
  [response conventions](https://docs.controld.com/reference/response-conventions).
- The documented automated activity CSV API is labeled **organization-only**.
  On October 7, actual authenticated reads proved the same v2 CSV route accepts
  this user's READ token without an organization ID and returns the documented
  23-column schema with a real DNS decision. This is observed account capability,
  not a claim that the documentation guarantees it for every personal plan.
  Account metadata returns a region label. The current vendor dashboard's public
  code constructs `https://<region>.analytics.controld.com/v2/activity-log/csv`;
  the client uses that verified mapping, not a guessed host or private browser
  session. API denial remains an error, with no cookie/scope-upgrade fallback.
  [CSV export](https://docs.controld.com/docs/how-to-export-logs-to-csv).
  [Vendor dashboard source inspected](https://controld.com/_next/static/chunks/pages/_app-ada2d7df9572e3d3.js).
- A live read-only AppControl MCP probe exposed process identity plus CPU,
  memory and disk counters, but no connection destinations or network-byte
  counters. Disk bytes must not be relabeled as network bytes.
- Elevated read-only inspection on October 7 established an internal GlassWire
  SQLite source with application, destination, time-bucket and network-byte
  fields. A narrow IPv4/application-path decode matched Windows' independent
  TCP/process table. No documented stable third-party interface, full binary
  schema, IPv6 decode or individual PID/socket byte attribution is established.
  See [inspection evidence and limitations](GLASSWIRE-READS.md).
  Its remote monitoring UI alone is not an API contract. Do not bypass licensing,
  authentication or access controls. Do not publish private host/query data.
- The user supplied a token and explicitly restricted it to READ. Live reads of
  devices/profiles and account metadata succeeded, without publishing account
  values. The token is session-held only and is not persisted in this repository,
  arguments, logs, CI or credential files.

## Constraints and non-goals

No changes to installed clients, VPN state, tailnet membership, signing keys,
firewall/DNS policy, existing update endpoints or device data. No new packet
filter, Android-wide application telemetry, proprietary UI copy, generalized
provider framework or speculative database. No TailD release/deployment in this
increment. Existing upstream sync maintenance remains scoped to TailDNS and
SleepManager; TailD owns a separate GitHub workflow.

Completion is determined by the acceptance criteria, not the presence of client
wrappers or passing synthetic tests. Missing credentials or a missing telemetry
interface remain explicit external blockers; they do not satisfy the real slice.
