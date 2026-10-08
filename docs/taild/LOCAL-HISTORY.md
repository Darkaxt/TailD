# Stage 4 durable history candidate

2026-10-08. **Stage 4 is BLOCKED, not COMPLETE.** The implementation below is
verified with real SQLite fixtures and previously authorized real Control D
data. Fresh GlassWire compatibility and live traffic persistence are still
required. See B02 in the [stage ledger](IMPLEMENTATION-PLAN.md).

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
production target is Windows, whose actual source still needs B02 validation.

The candidate catalog reader verifies installed Windows service/uninstall metadata
or an explicit directory override, validates catalog schema/path containment and
selects only one-second filenames with the corresponding catalog scale. This
candidate catalog contract is fixture-tested, **not yet certified against the
current GlassWire installation**. Unsupported schema stops the read. Existing
history remains intact. The original read-only SQLite decoder and WAL-inclusive
transactions are reused; application and traffic snapshots remain separate.
Unknown well-formed address families keep their counters and unknown address.
IPv6 decoding is **not implemented or declared unavailable**: independent layout/
Windows-peer validation is still required, not a waived acceptance criterion.
In-place file reset, finalization and actual key-field mutability also need live
evidence before this source contract can be called production-compatible.

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
Later successful reconciliation resolves previous failed/truncated attempts without
erasing their evidence. A complete-through checkpoint is a snapshot/reconciliation
statement, not a provider guarantee that later arrivals are impossible. Undocumented
provider-side omissions cannot be ruled out by an untruncated CSV response.

## Store and privacy

Schema migrations are transactional: v1 facts/runs, v2 deletion suppression,
v3 a monotonic data revision covering imports, expiry and deletion. Unknown future
versions fail closed. Applications, traffic, DNS, runs and checkpoints are the
only current logical data areas; later correlation/policy/context tables are not
created speculatively. Facts and totals use Python/SQLite integers; totals avoid
SQLite SUM overflow. JSON byte counters are decimal strings, including fact rows.

Detailed retention defaults to seven days. `--retention-days` explicitly changes
it; an expiry floor never moves backwards to resurrect expired history. Startup,
ingest and cleanup enforce it. Deleting an interval/application/source adds minimal
hashed application/scope suppression, so replay cannot restore those facts.
Orphan application records are removed. No correlations or summaries exist yet.
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
The GlassWire command must not be treated as live-certified until B02 closes.

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
arbitrary SQL. Production metrics, cursors, charts and compound queries remain
Stage 5/8 work and are not claimed here.

## Verification and remaining evidence

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

Actual GlassWire: the service is running, version 3.10.1138. The unelevated process
cannot open its primary database read-only. Both one-shot `RunAs` attempts were
canceled at the Windows elevation boundary, before the inspection helper ran.
There is no fresh catalog/mutability/IPv6 or live traffic import/restart proof.
Do not substitute the earlier Stage 3 export for those Stage 4 criteria. No source
permission change, service operation, process dump, packet capture, installed
client operation, release, deployment or later-stage implementation occurred.

B02 resolves with a user-approved one-shot elevated **read-only** inspection and
validation against the current source. Inspect catalog/key/address layout first;
only then finalize any decoder/catalog corrections, prove actual mutable-row and
generation behavior, and run actual traffic -> private store -> query -> restart/
replay with conserved totals. Existing history is retained for that closure.

Verification commands inspected for this candidate:

```powershell
python -B -m unittest discover -s scripts/taild -p 'test_*.py' -v
# After the final generation/subdivision changes, rerun affected contracts:
python -B -m unittest test_history test_glasswire -v  # from scripts/taild
```

Both completed successfully. Earlier unchanged Control D, join and inheritance
results remain applicable; no native source, core pin, workflow or installed client
changed, so no unrelated Android/Windows build was run. The private real-DNS
restart/replay command also passed. Temporary inspection-helper and failed-test
fixture files were removed with reviewed exact-file cleanup; the private real
inputs and durable validation history were preserved. The blocked candidate is
committed locally, not pushed, released or deployed.
