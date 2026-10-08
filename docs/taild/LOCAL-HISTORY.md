# Stage 4 durable history

2026-10-08. **Stage 4 is COMPLETE.** Live validation is recorded below. The prior elevation
blocker B02 is resolved. This is an on-demand development data path, not a
continuous collector, installed analytics product or vendor-supported API.
See the [stage ledger](IMPLEMENTATION-PLAN.md) for closure status.

## Implemented boundary

`scripts/taild/history.py` owns a private SQLite database. `ingestion.py` is an
on-demand developer command, not an installed collector, service or UI. The
Portmaster source-design separation in [PORTMASTER-DESIGN.md](PORTMASTER-DESIGN.md)
is retained: acquisition/storage are separate from the later query/metrics and
presentation modules. No Portmaster code, filter engine or runtime is embedded.

Facts and source-run/checkpoint updates commit together. Traffic replay replaces
the canonical bucket counters rather than adding cumulative observations. Physical
identity uses filesystem device/file ID and available birth time, not filename,
mtime or a changing database content hash. Paths remain provenance. Row incarnations
include the source rowid and bucket identity; rowid reuse with different identity
preserves the preceding fact. Application-record changes do not duplicate counters.
Filesystems without birth identity have a weaker identity guarantee; the required
production target is Windows; live daily sources have distinct file/birth IDs.

The catalog reader verifies installed Windows service/uninstall metadata
or an explicit directory override, validates catalog schema/path containment and
selects only one-second filenames with catalog scale 1. GlassWire 3.10.1138 stores
UTF-8 leaf filenames as BLOBs, with files below `service-full/stats`; the live
catalog and faithful fixtures now verify this contract. Unsupported schema stops the read. Existing
history remains intact. The original read-only SQLite decoder and WAL-inclusive
transactions are reused; application and traffic snapshots remain separate.
Unknown well-formed address families keep their counters and unknown address.
Observed family 2 uses a 16-byte length-delimited field 3 in IPv6 network order.
The destination, remote port and executable were independently matched to a
known TCP DNS diagnostic and Windows' own connection table before enabling it.
Malformed known-family fields fail closed; unsupported families remain unknown.
Two reads of the same completed five-minute window reobserved 2,098 rowids with
no identity/counter changes. This bounded observation is not an immutability or
finalization guarantee. Replay remains correction-aware across the retained
horizon; mutation, in-place identity reuse and replacement are exercised with
real SQLite fixtures without resetting the live source.

Control D imports require an explicit account/endpoint and bounded UTC interval.
Local ownership is half-open even when the CSV route includes its upper boundary.
A complete slice replaces that interval's multiset; identical equal events retain
their multiplicity. Overlapping slices and late corrections reconcile by timestamp
ownership. Truncated DNS slices do not erase earlier facts or advance completeness.
Requests subdivide deterministically, down to one second. A still-capped interval
or the explicit 1,024-slice operation budget records a gap; it is not successful
completion. Traffic subdivision similarly reconciles capped reader windows.
The budget limits work, not elapsed execution, and does not cancel transactions.
Coverage exposes gaps, unresolved attempts, retention and deliberate deletion.
The live catalog exposes two daily one-second sources, less than the default
seven-day owned retention. Requests older than available sources report an
expired-source gap, not observed zero traffic. Gaps are scoped to the selected
interval; a DNS endpoint cannot borrow another endpoint's observed coverage.
Later successful reconciliation resolves previous failed/truncated attempts without
erasing their evidence. A complete-through checkpoint is a snapshot/reconciliation
statement, not a provider guarantee that later arrivals are impossible. Undocumented
provider-side omissions cannot be ruled out by an untruncated CSV response.

## Store and privacy

Schema migrations are transactional: v1 facts/runs, v2 deletion suppression,
v3 a monotonic data revision covering imports, expiry and deletion. The subsequent
[Stage 5 query module](METRICS-QUERY.md) adds v4 observed context/policy snapshots
required by R10/R11, with no early policy acquisition. Unknown future versions
fail closed. Facts and totals use Python/SQLite integers; totals avoid
SQLite SUM overflow. JSON byte counters are decimal strings, including fact rows.

Detailed retention defaults to seven days. `--retention-days` explicitly changes
it; an expiry floor never moves backwards to resurrect expired history. Startup,
ingest and cleanup enforce it. Deleting an interval/application/source adds minimal
hashed application/scope suppression, so replay cannot restore those facts.
Orphan application records are removed. Stage 5 computes versioned correlations
and summaries on demand, so no stale derived rows survive deletion or expiry.
Retention/deletion never changes GlassWire or Control D records.

History and query exports must stay outside Git. The selected new owned directory
gets owner/SYSTEM/Administrators access on Windows (or owner-only Unix modes).
Existing directories and database/journal/WAL/SHM files must already be private;
public ACLs, links and hard-linked database files are rejected, not relaxed.
Python's Windows OWNER RIGHTS entry is accepted only with a checked owning user,
SYSTEM or Administrators owner. No source ACL is changed. SQLite is plaintext:
OS account/disk protection remains necessary; no application encryption is claimed.
The CLI prints counts/status, not application paths, DNS questions or tokens.
Query exports are new, non-overwriting files inside the private history directory.
Token input is stdin only; no credential persistence or new provider writes.

## Developer commands

Run with Python 3.11+ from the repo. Use a dedicated directory with an existing
parent; replace example scope/bounds with the intended local scope. These are
development commands, not instructions to change the installed TailDNS client.
The GlassWire command requires source read permission; ordinary Windows elevation
was needed on the validated installation. No source permission is relaxed.

```powershell
python -B scripts/taild/ingestion.py --history D:/Maintenance/TailD-history glasswire --scope local-host --start 2026-10-08T10:00:00Z --end 2026-10-08T10:05:00Z
python -B scripts/taild/ingestion.py --history D:/Maintenance/TailD-history glasswire --scope local-host --resume --end 2026-10-08T10:10:00Z
python -B scripts/taild/ingestion.py --history D:/Maintenance/TailD-history health
python -B scripts/taild/ingestion.py --history D:/Maintenance/TailD-history query --kind traffic --start 2026-10-08T10:00:00Z --end 2026-10-08T10:05:00Z --output D:/Maintenance/TailD-history/selected.json
python -B scripts/taild/ingestion.py --history D:/Maintenance/TailD-history delete --kind traffic --start 2026-10-08T10:00:00Z --end 2026-10-08T10:05:00Z
python -B scripts/taild/ingestion.py --history D:/Maintenance/TailD-history cleanup
```

`--resume` rechecks the retained horizon, rather than assuming old buckets/events
are finalized. Existing endpoints can be ingested using `controld` with explicit
`--scope`, `--endpoint`, `--account-type`, `--instance`, bounds and `--token-stdin`.
`import-dns` accepts a previously authorized private bounded slice; it does not
make a provider request. Query filters are allowlisted, parameter-bound equality
filters (source/application/destination/port or source/endpoint/question), not
arbitrary SQL. The [Stage 5 analytics module](METRICS-QUERY.md) now supplies
metrics, cursors, charts and compound queries over this history. The desktop
presentation remains Stage 8 work and is not claimed here.

## Verification evidence

Focused checks cover WAL/read-only behavior, mutable counters, physical replacement,
midnight/rowid reuse fixtures, identical events, overlapping and late DNS slices,
truncation/subdivision/irreducible gaps, missing source history, exact large sums,
retention, deletion suppression, migration/rollback, injection and private ACLs.
Subprocess crashes immediately before and after the real COMMIT prove facts and
checkpoints recover together; replay conserves the fixture's totals after restart.

Actual data: the 2026-10-07 authorized private Control D slice was imported into
`D:/Maintenance/TailD-stage4-validation-20261008/history.sqlite3`, closed, reopened
and reimported. All **113** decisions and coverage were conserved. This is real
retained provider data, **not a new authenticated API read**. No old token was
recovered or persisted. The initial inputs remain unchanged in their private folder.

Actual GlassWire 3.10.1138: approved hidden one-shot elevated reads validated the
catalog, schema, raw row identities and two physical daily generations. All source
connections used `mode=ro`, `query_only=ON` and read transactions including WAL.
The interval `[2026-10-08T17:08:28Z, 2026-10-08T17:14:00Z)` supplied **2,550**
buckets: **48,184,294 inbound** and **19,496,607 outbound** bytes. Independent raw
SQL row/counter reads matched persisted totals. Application/destination/port
filtering returned 305 buckets with exactly reconciled totals. All 160 observed
IPv6 buckets decoded; one matched the known diagnostic's executable/peer/port.
The private store was closed, reopened and the source re-read/replayed: facts,
totals and coverage were unchanged. A separate unelevated Python process then
queried the durable store with the same totals and complete selected-window
coverage; all 113 retained Control D decisions remained present. Reconciliation
and retention maintenance revisions can advance even when facts do not change.
Both source physical generations remained unchanged. No source write SQL,
checkpoint, ACL change, service operation or unsafe active-file copy occurred;
the running GlassWire writer was not stopped, so no whole-file immutability claim
is made. No process dump, packet capture, installed-client operation, provider
write, release, deployment or later-stage implementation occurred.

Verification commands inspected for this implementation:

```powershell
python -B -m unittest discover -s scripts/taild -p 'test_*.py' -v
python -B -m unittest test_history test_glasswire -v  # from scripts/taild
```

Both completed successfully. Earlier unchanged Control D, join and inheritance
results remain applicable; no native source, core pin, workflow or installed client
changed, so no unrelated Android/Windows build was run. The private real-DNS
restart/replay command also passed. Private real inputs and durable validation
history are preserved. Temporary diagnostic helpers/reports are expendable and
removed through reviewed transactional cleanup after recording this evidence.
The completed scope is committed locally, not pushed, released or deployed.
