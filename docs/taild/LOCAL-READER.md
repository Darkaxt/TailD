# On-demand local analytics reader

GlassWire already collects and retains traffic. TailD reads that existing source;
it does not need another packet collector, firewall engine, service or scheduled
polling loop for this first slice. The implementation is a Python development
command, **not yet an installed TailD/native GUI feature**. Python 3.12+ suffices;
only the standard library is used.

## Workflow

Choose a private export folder outside Git. On Windows restrict its ACL to your
account, SYSTEM and Administrators; Unix exports are created with mode 0600.
Existing output files are never overwritten. Every command prints only counts,
not paths, domains, destinations or credentials.

1. Read Control D decisions for the device's endpoint and UTC window:

   ```powershell
   python -B scripts/taild/controld.py --token-stdin --output D:/Private/decisions.json activity --account-type personal --endpoint YOUR_ENDPOINT --start START_UTC --end END_UTC --limit 5000
   ```

   Supply the READ token through a non-echoing stdin source, not by typing it into
   an echoing terminal. Alternatively use the existing process-local
   `CONTROLD_READ_TOKEN` mechanism without `--token-stdin`. The documented
   interactive `getpass` wrapper refuses insecure echo fallback. Tokens are not
   persisted. No browser cookies or API writes are used.

   Activity CLI exports now include `rows`, the requested `query_window`,
   `endpoint_id`, `collected_at_utc` and `truncated`, rather than a bare array.
   The library's `activity()` still returns the raw record list;
   `activity_slice()` performs one read with an extra sentinel row to establish
   truncation. An exact-size result is not automatically called truncated.

2. In an elevated terminal, read the matching one-second GlassWire database:

   ```powershell
   python -B scripts/taild/glasswire.py --stats-db C:/ProgramData/GlassWire/service-full/stats/glasswire_stats_1sec_DAY_EPOCH.db --start START_UTC --end END_UTC --limit 10000 --output D:/Private/traffic.json
   ```

   Substitute an actual observed filename. Database selection is explicit;
   there is no hidden rotation, multi-scale summation or full-history scan.
   `--main-db` overrides the primary application DB when necessary. The UTC
   traffic interval is half-open `[start,end)`; the provider CSV uses its own
   requested end bound. Neither is an execution deadline.

   SQLite opens with `mode=ro`, `query_only=ON` and read transactions including
   WAL. No immutable live reads, checkpoint, source copy, permission change or
   service operation occurs. Schema/binary incompatibility and malformed byte
   counters terminate the read before export. Observed nullable `threat_level`
   stays null; it is not converted into a safety verdict. Well-formed unknown
   address families remain records with an explicit unknown destination.

3. Join local files with the actual Windows TailDNS device context:

   ```powershell
   python -B scripts/taild/join.py --traffic-file D:/Private/traffic.json --decisions-file D:/Private/decisions.json --endpoint YOUR_ENDPOINT --max-age-seconds 300 --output D:/Private/joined.json
   ```

   The default existing CLI path is `C:/Program Files/Tailscale/tailscale.exe`;
   `--tailscale-cli` overrides it. Only `status --json` and `debug prefs` are read.
   TailDNS must be Running on Windows with DNS acceptance and the local override
   enabled, using `https://dns.controld.com/YOUR_ENDPOINT`. The endpoint binding
   must match both sources. Only whitelisted device identity/IP fields are
   exported, never private node keys, complete preferences or peer maps.

   The age parameter is explicitly chosen analytical evidence, not a timeout,
   TTL, cache-validity guarantee or process/domain attribution proof. The live
   verification used 300 seconds. Different analytical windows are recorded in
   output; they do not change execution lifetime or provider policy.

## Meaning of the output

Each traffic bucket appears once with its original database/table/row/application
provenance, binary SHA-256 fingerprints, network counters and raw flags/protocol/
threat codes. It contains zero or more `dns_candidates`, each retaining the raw
Control D decision and input index, match method and age. A candidate requires
the selected endpoint, an exactly parsed answer IP matching the destination and
a decision preceding the traffic timestamp inside the analytical age window.

Single IP answers are documented. Semicolon-separated IP answers were observed
live and are parsed explicitly. Arbitrary strings, CNAME targets and malformed
answer formats are not searched for IP-like substrings; unsupported answers are
counted. No undocumented action-code meaning is assigned.

Statuses distinguish unmatched, unusable identity/address, one temporal-IP
candidate and ambiguous candidates. No per-domain byte total is fabricated by
duplicating one bucket across every possible domain. Records and source metadata
retain truncation, separate snapshots, unknown TTL/cache validity, shared-IP/DNS
reuse, collection-time rather than historical endpoint binding, and lack of
individual PID/socket byte attribution. IPv6 GlassWire decoding is not claimed.

## Real verification

On 2026-10-07 the actual implementation read the authorized personal Control D
endpoint and a matching five-minute GlassWire window without truncation. The
actual join CLI read the laptop's Running TailDNS identity and active resolver,
and created a private local joined export containing application/destination
records with nonzero network bytes and matching real DNS decisions. Ambiguous,
unknown-address and unsupported-answer records remained explicit.

The first live read found nullable threat metadata; a reproducing SQLite fixture
and focused correction preserve null without relaxing identity/byte validation.
Unit/integration fixtures verify WAL visibility, unchanged source content,
read-only enforcement, bounds, limits, binary errors, identity mapping, unknown
families, source/endpoint checks, analytical matches/ambiguity and CLI privacy/
non-overwrite behavior. Fixtures contain only synthetic records.

Private inputs and the joined deliverable are retained outside Git in an
ACL-restricted validation folder. Public source/evidence contains no actual
domains, application identities, destination/device/account values or credential.
No client deployment, release, collector installation or policy change occurred.
