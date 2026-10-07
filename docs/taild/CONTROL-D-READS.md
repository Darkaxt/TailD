# First Control D data slice

Run from the TailD repository with Python 3.12 or newer. This is a development
command, not an installed client feature or background collector.

Only GET requests exist. Supply a **Read** token via one stdin line with
`--token-stdin`, or the process-local `CONTROLD_READ_TOKEN` environment variable.
Never put the token in arguments, examples, files in this repo, CI or diagnostics.
Interactive credentials can be gathered with Python's standard `getpass` and
passed to `controld.main` through a private in-process stdin stream. Do not type
credentials into a terminal that echoes input. No credential is persisted here.

```sh
python -B scripts/taild/controld.py inventory
python -B scripts/taild/controld.py activity --account-type personal --start 2026-10-07T07:00:00Z
```

These examples use an already supplied process-local token. Use a **current UTC**
start timestamp within the past calendar month; the example date is illustrative,
not a permanent query window. `--end` is optional. `--limit` defaults to one
decision, suitable for the first slice. `--instance` can specify a provider label;
otherwise the command reads `/users` and uses its analytics region, with the
organization region preferred when present. Domains, URLs and credentials cannot
be passed as an instance: only a DNS label under `analytics.controld.com` is used.

Inventory reads `/devices` and `/profiles`. Activity reads the provider's
`/v2/activity-log/csv` interface. Default output contains only source and counts.
`--output <file>` before the subcommand optionally exports the raw records to a
new JSON file outside this repository. Existing files are never overwritten.
Choose a private folder: Unix files are created with mode 0600; on Windows the
destination folder's ACL governs access. Returned records may contain private
query/device/IP data. Do not publish them. Tokens never enter exported records.

The records preserve source provenance and raw action/trigger/answer values. No
unverified action-code meaning or process/domain attribution is invented. A CSV
query proves Control D data access, not host application/network-byte telemetry.

## Evidence and provider-contract distinction

On 2026-10-07 the actual development command read the user's device/profile
inventory with the user-provided READ token. An authenticated account read found
no organization ID and a region label. An initial diagnostic correctly rejected
that label as a full hostname; the vendor dashboard's public source then verified
the region-to-host mapping. A single authenticated CSV read returned the documented
23-column schema and one real DNS decision. No browser session, write token or
settings changes were involved. Public evidence contains no returned identities,
queries, IPs or token.

[Control D's documentation](https://docs.controld.com/docs/how-to-export-logs-to-csv)
still labels automated CSV access organization-only. The personal-account access
is a **live observed capability**, not a universal documented entitlement. The
client does not artificially reject a permitted personal read, but server denial
is terminal: there is no cookie, permission-upgrade, retry or scraping fallback.
[Vendor mapping source inspected](https://controld.com/_next/static/chunks/pages/_app-ada2d7df9572e3d3.js).

Focused verification:

```sh
python -B -m unittest discover -s scripts/taild -p test_controld.py -v
```

Synthetic tests use a real loopback HTTP server for authentication, GET-only
inventory, redirects and sanitized errors; CSV parsing and provider URL construction
use synthetic streams. Real account and CSV reads are separate private integration
evidence, not data copied into fixtures.
