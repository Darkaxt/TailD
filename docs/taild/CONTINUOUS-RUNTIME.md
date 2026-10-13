# Stage 7 runtime contract and evidence

Stage 7 is **COMPLETE** under the explicit October 13 acceptance-test waiver.
The analytics desktop/explorer, production packaging and delivery are separate
later stages; this is not overall TailD completion or an installed-client release.

## Implemented integration

The owning-user process runs unelevated and owns its SQLite connection. It starts
with collection disabled unless the same private history contains an explicit
saved opt-in. Configuration is idempotent and autosaved; no Save button is needed.
One worker serializes source reads, transactions and a bounded command queue.
Queries, pause, settings changes and deletion run between committed source slices;
they are not held behind an entire retained-horizon scan. Missed acquisition
opportunities coalesce without overlapping reads or timed cancellation.

The Windows reader exposes only installed-source catalog discovery and bounded
traffic slices by catalog-bound identity, plus authenticated shutdown. No caller
path, SQL, shell operation or provider credential crosses this boundary. The
protected pipe rejects remote clients, has an explicit owner/SYSTEM DACL, removes
client pipe-instance creation rights and checks the impersonated client's actual
SID. It reverts before source access. Pending overlapped IO is canceled by its
submitting thread on explicit stop and observed through completion before buffers
and handles are released. One collector retains one connection, avoiding a
disconnect/reconnect race. CLI readers remove unused process privileges.

The local query listener is loopback-only, uses an in-memory session token and
strict Host/Origin/content-type checks, rejects URL credentials and uses bounded
event-driven connections. Closing an incomplete request explicitly cancels owned
transports; no watchdog deadline is involved. Queries retain the Stage 5 revision,
exact-counter and field/operator contracts. Resource-limit responses identify the
need to narrow the interval/scope rather than hide capacity as a generic error.

Control D remains GET-only. A sampling cycle admits at most sixteen activity
requests: eight prioritize a two-minute analytical overlap, then eight advance a
durable retained-horizon continuation. This overlap is not a TTL guarantee or an
execution timeout. Exhausting the cycle budget leaves pending windows; it does
not assert an irreducible provider cap. Facts/checkpoints commit before the
continuation advances, so interruption can replay but cannot skip committed work.
Actual irreducibly capped seconds remain incomplete. Retry-after is a provider
boundary and survives process restart; resume/network events cannot bypass it.

Optional credentials can remain in owning-process memory or be explicitly saved
through the existing current-user vault. The privileged reader never receives
them. Private settings, status, continuation and quota files contain no tokens and
are checked alongside history ACLs. Diagnostics retain status/count/version only.
SQLite FULL freezes writes, preserves committed facts/checkpoints and requires
explicit recovery; it never silently evicts evidence.

An unshown, non-activating Windows window receives resume notifications, and
`NotifyIpInterfaceChange` schedules coalesced acquisition opportunities. These
events do not imply internet availability or unpause collection. Registration and
shutdown use native lifecycle operations, not polling, startup entries or services.

The real unelevated collection-control window now uses the adapted Portmaster
panel and toggle components, with the user-requested Tailscale dark palette.
Angular 20 renders inside a restricted WebView2 host; WinForms supplies the native
window, not replacement form widgets. Source/license provenance is in
`desktop/NOTICE.md`. Packaged assets have a strict response CSP; virtual-host
folder mapping is deliberately not mixed with response interception, which
WebView2 bypasses. The failed directory-root navigation was fixed by explicit
index/asset responses. No external navigation, frames, downloads, general shell,
filesystem bridge, browser autofill or renderer-visible API session token exists.

Controls autosave opt-in/binding/cadence, expose real source status, pause/resume
and explicitly stop. Native attachment is explicit: an unrelated read-only pipe
client disconnect cannot masquerade as closing the UI. Closing an enabled window
keeps collection; closing a disabled one stops it. The source-build launcher starts
and reattaches to the owning-user runtime without manual ingestion commands.
Worker defects settle the dequeued command before terminal shutdown, and typed
query errors remain bounded public errors rather than terminating the pipe.

## Verification at the current checkpoint

- Native owner pipe -> real synthetic SQLite/WAL -> private history -> close/
  reopen/query passes, including fixed-operation rejection, wrong-SID rejection,
  collision prevention and explicit pending-connect shutdown.
- Collector opt-in/pause/resume/restart, deleted-history catch-up suppression,
  bounded-queue backpressure and pause/query yielding at a committed slice pass.
- Actual local HTTP authorization/origin/path/injection rejection, exact private
  query output and explicit shutdown of an unfinished HTTP peer pass.
- Real SQLite `SQLITE_FULL` through a constrained page budget rolls back failed
  ingestion; reopening with available capacity recovers without duplicate facts.
- A real loopback HTTP 429 is not retried by refresh/resume or process restart.
  Bounded deterministic DNS continuation completes a capped fixture without
  fabricated gaps or duplicate decisions.
- Native Windows power/interface registration succeeds; its window is not visible
  and is destroyed on stop. Delivery of a resume message verifies wiring only,
  **not physical sleep/wake**.
- The current TailD Python contracts pass, including the changed native reader,
  runtime, history/ingestion/query boundaries and actual HTTP authorization.
  Additional focused HTTP 401 denial -> recovery -> denial conserves committed
  DNS decisions; the provider boundary is real loopback HTTP, not mocked ingestion.
- The actual WebView2 assets pass at 1440×900, 1280×800 and 1024×768 CSS pixels:
  native checkbox/button paths -> owner pipe -> SQLite acquisition/query; pause,
  resume with observed collection, OS window close, reopening, explicit stop and
  the ordinary source-build launcher. CSP headers were read from actual served
  responses, keyboard focus checked, source markup rendered literally, screenshots
  inspected and horizontal overflow rejected. Current frontend and native builds
  pass with locked dependencies; the native build has no warnings. This is not
  a claim of Windows 150% scaling acceptance, which belongs to Stage 8's matrix.
- A real LocalService non-admin account (SID S-1-5-19) was denied private history
  and pipe access (Win32 5), and could not read the owner's synthetic vault target
  (1168). The corrected supervised probe and worker exited successfully; its
  temporary task was removed. Both synthetic credentials were removed, and no
  production credential was changed. The first test-only supervisor used a
  session-local event that the service could not open; its exact failed wait was
  explicitly canceled and its task removed through the elevation gate before the
  corrected global-event/DACL run. It is not reported as a successful harness run.

Private current UI evidence is at
`D:\Tools\taild-stage7-validation-20261013\desktop`; actual different-account
evidence is `other-account-validation.json` in that parent directory. The live
Control D GET-only runtime also passes opt-in/pause/resume/restart/query, with its
READ token held only in process memory. The selected endpoint's recent interval
was empty; this proves live read/empty-state handling, not non-empty endpoint
history. Its report/history are under `provider-runtime` in the same private root.

Real protected-source evidence is private at
`D:\Tools\taild-stage7-validation-20261013\runtime-validation.json`:
GlassWire 3.10.1138 -> temporary elevated reader -> unelevated collector -> private
history -> authenticated fifteen-minute summary -> pause/restart/query -> reader
shutdown and process exit. The observed summary contained 3,285 traffic buckets
and 41,937,588 bytes. Reader privileges were exactly SeChangeNotifyPrivilege and
SeImpersonatePrivilege; the collector rejected elevated execution. Values changed
during restart and are not presented as unchanged-source replay proof. Source
coverage and separate-snapshot limitations remain explicit.

No source ACL/service, VPN/DNS/firewall, installed client or production vault was
changed. No persistent service/task or public release was created. The initial
live verifier hit a pywin32 API mismatch; its exact temporary reader was stopped
through the authenticated pipe and its exit observed. A later broad query hit the
existing fact budget; that was diagnosed, not called a passing query. The final
bounded live workflow above succeeded. Failed synthetic fixtures and accidental
bytecode were removed through cleanup transaction
`4139b101a07cb03b628b2d0ced00de04`; requested/private evidence was retained.

## Stage 7 final criterion reconciliation

| Criterion | Satisfied evidence | Remaining |
|---|---|---|
| Unelevated runtime/UI, minimal protected reader and fixed IPC | Real protected-source report; current owner pipe and native UI; elevated collector rejected; no source ACL changes | None |
| Opt-in/cadence/pause/resume/stop, source state and catch-up | Actual connected control-window workflow; current native reader outage/recovery, retained-horizon continuation and generation contracts | None |
| Private storage/credentials/query and resource boundaries | Actual other non-admin account denial, HTTP/native public errors, source-text/CSP tests, queue bounds, deletion suppression and real SQLite FULL recovery | None |
| Authorized lifecycle/security integration and quiet ownership | Actual window close/reopen/launcher/stop; live Control D READ; HTTP denial/throttle recovery; exact test/task/process cleanup | None under the user waiver below |

Stage 7 blockers: none. Tracked deferrals: none. The user explicitly waived forced
live sleep/wake, network-loss and GlassWire stop/update tests because no isolated
Windows host is available, and will report naturally occurring issues. Required
behavior remains implemented and supported by the native/isolated contracts;
those physical/live scenarios are **untested**, not simulated passes or deferrals.

## Inheritance operation observed

Run 38382663145 passed inherited Android/DNS/shared Windows-core checks and saved
exact candidate `7aafd27c36a88c8dce4067ec639c5491ee5fb5b7`, merging TailDNS
`c2116d244b05bf0e85c03e70a42d03678950c442`. Promotion failed because GitHub's
workflow token cannot update an inherited workflow file. The checked candidate
was subsequently promoted with the existing authorized workflow-capable Git
credential, using an ordinary fast-forward; remote main was independently read
back. No credential was copied into automation and inherited workflows remain
disabled. Fully automatic promotion of future workflow-file changes remains an
external R02 operational blocker requiring a TailD-scoped workflow-write identity;
do not exclude upstream source or claim the built-in token acquired that scope.
