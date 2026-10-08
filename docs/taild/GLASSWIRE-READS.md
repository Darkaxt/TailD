# GlassWire read-only source inspection

## Scope and result

On 2026-10-07 the user authorized an elevated, read-only local inspection.
One-shot hidden Python helpers completed successfully with an elevated token.
No process dump, browser/UI automation, persistent collector, service restart,
ACL change, firewall change, database backup or SQLite write was performed.
The existing GlassWire service remained running.

The initial access blocker is resolved: local SQLite data is accessible through
normal Windows elevation. This is an observed internal storage interface, **not
a documented or stable GlassWire third-party API**. This evidence does not claim
a completed TailD adapter, a DNS correlation, or the full R07 joined export.

## Observed schema

`C:/ProgramData/GlassWire/service-full/glasswire.db` contains:

- `applications(id INTEGER PRIMARY KEY, data BLOB)`
- `hostnames(address BLOB, hostname BLOB, type INTEGER)`
- `stats_databases(id, filename, timestamp, expire_time, scale)`

Separate databases below `service-full/stats` have `traffic_stats` columns:

```text
timestamp INTEGER
app_id INTEGER
remote_host BLOB
remote_port INTEGER
remote_host_region BLOB
protocol INTEGER
flags INTEGER
inbound_bytes INTEGER
outbound_bytes INTEGER
threat_level INTEGER
```

Observed filename scales include `1sec`, `30sec`, and `600sec`. Their counters
must be treated as source time-bucket/application/destination measurements.
Overlapping scales must not be summed. No PID, local port or unique socket ID
was observed in these columns; exact per-socket attribution is not established.
Protocol, flags and threat codes remain raw, with no invented enum meanings.

`C:/ProgramData/GlassWire/share/storage.db` has `app_info` identity metadata, but
the sampled traffic application ID did not resolve there. Do not assume that
table's ID namespace matches the primary application's ID namespace.

## Narrow binary-field validation

The sampled application/address BLOBs are consistent with Protocol Buffers wire
encoding. This observation is not a claim that an authoritative `.proto` or full
message schema has been obtained.

- The application record's observed length-delimited field 6 is a UTF-8 path to
  an existing executable. Field 4 is printable UTF-8 but has not been assigned
  an authoritative semantic name. Record field 1 does **not** always equal the
  SQL application ID; use the SQL primary key for the traffic-table relation.
- Observed address field 1 has values 1 and 2. The narrow IPv4 sample's field 2
  is a varint that yields its destination when its integer is converted to four
  **little-endian** bytes. IPv6 was not validated in this initial inspection;
  the subsequent Stage 4 validation below establishes the observed IPv6 layout.
- The decoded executable path, IPv4 destination and unmodified remote port were
  independently matched together against Windows `Get-NetTCPConnection` and
  the owning process's executable path. Byte-swapping the remote port and using
  big-endian IPv4 did not produce the corresponding matches.
- An actual normal read transaction returned a contemporary traffic record
  with nonnegative, nonzero inbound/outbound network counters. These are network
  measurements, not AppControl disk-I/O counters.

The first Windows cross-check helper initially failed to attach process paths:
PowerShell process IDs and connection-owner IDs had different numeric key types.
Using a consistent string-key namespace restored the path lookup and the
independent application/address/port match. This was a diagnostic helper issue,
not a change to GlassWire or production TailD behavior.

## Read consistency and privacy

The first schema-only probe used `mode=ro&immutable=1` to avoid journal/shared
memory writes; it ignores WAL and is **not** live-row verification. Subsequent
row and binary-field checks used normal `mode=ro` connections, `query_only=ON`
and explicit read transactions, with WAL participating in the SQLite snapshot.
No checkpoint, write SQL, unsafe active-file copy or service suspension was used.
Normal SQLite read-lock coordination is not a modification of application data.
See [SQLite WAL read transactions](https://sqlite.org/wal.html) and
[immutable URI caveats](https://sqlite.org/uri.html).

Application and traffic databases have separate transactions. Cross-database
atomicity and live cross-source temporal consistency are not established. A
future joined record must preserve that uncertainty rather than assert a single
globally consistent snapshot.

Reports retained format/schema and validation-result metadata only, without
publishing application identities, destinations or query history. Temporary
inspection helpers/reports are expendable and removed after recording this
evidence. No Control D requests were needed for this inspection.

## R07 still remaining

The current-stage work is a narrow verified extraction and one real local
Control D/GlassWire/Windows-device joined record with source provenance and
explicit temporal/IP and byte-attribution limitations. Unknown encodings must
fail explicitly, not be guessed. A supported Usage Table CSV is still an
alternative if internal source compatibility cannot be established.

This inspection does not authorize a full proprietary protocol implementation,
API breadth, dashboard, continuously elevated collector, deployment or release.

## Subsequent implementation evidence

The user subsequently authorized the collector/reader implementation. The
[on-demand local reader](LOCAL-READER.md) now uses the observed narrow layout.
An actual multi-row read established that `threat_level` can be SQL NULL despite
its INTEGER declaration. The reader preserves that raw null; numeric identity,
timestamp, port and network-counter checks remain strict. The real implemented
reader and join command produced the private Control D/GlassWire/Windows-device
joined export. Original inspection limits remain: this is not a stable vendor
API, full binary schema or per-socket counter interface.

## Stage 4 live validation — 2026-10-08

Approved one-shot read-only helpers inspected GlassWire **3.10.1138** without
changing its ACL, service, configuration or database contents. The actual catalog
declares `filename BLOB`: each observed value is a UTF-8 leaf filename under
`service-full/stats`. One-second records have scale 1; the observed thirty-second
record has scale 2, not 30. Only verified one-second records are ingested.
The two retained daily one-second databases have distinct Windows file/birth
identities. Rowid is implicit, not a globally unique or immutable fact key.

Family 2 addresses store 16 network-order IPv6 bytes in length-delimited field 3.
A normal TCP DNS diagnostic to the current local resolver supplied a known peer;
Windows `Get-NetTCPConnection` independently recorded its established IPv6/port53
connection. GlassWire's raw field bytes, remote port and decoded executable path
matched that exact diagnostic. Executable comparison resolved the Scoop junction
to the installed executable. No synthetic address was substituted for live proof.
Known malformed IPv6 fields reject the read; unknown families retain their bytes.

The exact same completed five-minute source window was read twice: 2,098 rowids,
zero bucket-identity changes and zero counter changes. This establishes bounded
stability only, not universal finalization. Canonical counter replacement and
retained-horizon reconciliation remain necessary; actual SQLite fixtures exercise
mutable counters, replacement, midnight rotation and identity reuse. No destructive
reset or forced source rotation was performed on the live installation.

The subsequent real on-demand ingestion/query/restart/replay proof conserved
2,550 buckets, 48,184,294 inbound bytes and 19,496,607 outbound bytes. It includes
160 decoded IPv6 buckets and the independently matched diagnostic. A separate
unelevated process queried the private durable store with conserved totals and
complete selected-window coverage. See [LOCAL-HISTORY.md](LOCAL-HISTORY.md).
The catalog retained only two daily one-second sources: earlier requested history
is reported as an expired-source gap, not fabricated zero traffic. Source reads
used `mode=ro`, `query_only=ON` and WAL-inclusive snapshots throughout; source
physical identities remained unchanged, while its own writer continued normally.

Compatibility is bounded to this observed internal schema/version, not a vendor
API or a guarantee across upgrades. Application and traffic snapshots remain
separate; PID/socket attribution, enum semantics and unseen source omissions are
not established. No API token, private application path, DNS question or peer
history is published here. Private durable history is retained outside Git;
expendable diagnostic reports/helpers are transactionally removed.
