# Control D policy reads and optional credentials — Stage 6

The development command now closes the read -> private history -> typed policy
query path. It does not install a background collector, change provider policy,
alter the VPN or claim a full public Control D SDK.

## Commands

Use hidden, transient input (not stored):

```powershell
python -B scripts/taild/controld.py --token-prompt policy --endpoint ENDPOINT_ID --account-scope local-account --history D:/Private/TailD
```

Alternatively explicitly save a **Read** token in the current Windows user's
Credential Manager, then use that credential. Enter the token at the hidden
prompt, never in the command line:

```powershell
python -B scripts/taild/credentials.py set --confirm-read-only
python -B scripts/taild/credentials.py status
python -B scripts/taild/controld.py --token-vault policy --endpoint ENDPOINT_ID --account-scope local-account --history D:/Private/TailD
python -B scripts/taild/credentials.py remove
```

`set` replaces one fixed TailD-owned generic credential atomically; `remove`
removes only that local reference, not the provider token. The Windows
`CRED_PERSIST_LOCAL_MACHINE` setting persists across logons of the **same user on
this computer**, not across users or machines. There is no plaintext settings or
environment/transcript recovery fallback. Noninteractive `getpass` warnings fail
closed instead of allowing echoed input. Native temporary buffers are cleared;
Python string memory is not claimed to be securely zeroized. See Microsoft's
[credential structure](https://learn.microsoft.com/en-us/windows/win32/api/wincred/ns-wincred-credentialw)
and [replacement API](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credwritew).

The existing `--token-stdin`/process-local environment interface remains for the
original development commands; new vault and hidden-input options are mutually
exclusive with stdin. Credentials never appear in summaries or policy exports.
`--organization` remains an explicit user-selected scope, never auto-impersonation.
Policy history and optional `--output` destinations enforce owner-private access.
Existing broad directories are rejected, not silently given new ACLs.

## Maintained READ capability matrix

### Separate management credential (October 15)

Explicit owner authorization adds a separate Windows vault target
`Darkaxt/TailD/ControlD/WriteToken/v1`. The existing Read target and all collectors
remain unchanged and selected by default. Register a Write token using hidden input:

```powershell
python -B scripts/taild/credentials.py set --permission write --confirm-write-access
python -B scripts/taild/credentials.py status --permission write
```

`--token-stdin` supports an explicitly private non-echoed input pipe for authorized
registration; tokens must never be literal command arguments, logged, or put in
source/settings files. Status does not reveal the credential. A Write token grants
account-wide Read/Write, not just one profile; no provider policy mutation is
performed by credential registration. This does not implement management UI or
change the READ integration's permitted operations.

For authorized browser-assisted setup without clipboard history, run:

```powershell
python -B scripts/taild/credential_entry.py --confirm-write-access
```

The one-use entry URL is emitted only by the local command. Open it locally and
enter the token; the listener binds only 127.0.0.1 on an OS-selected port. Exact
Host/Origin, an unguessable entry path and CSRF header protect registration. The
token must authenticate to the existing READ account before vault persistence;
read-back and READ continuity are checked before success. The listener exits
after the registration result. No startup entry, service, secret-bearing log or
clipboard transfer is created. An existing Write entry refuses this creation-only
flow; explicit hidden/STDIN replacement remains a separate CLI action.

### Existing live READ coverage

Verified 2026-10-13 using the already supplied READ credential. Every row is a
GET, with no provider mutation, credential-bearing redirect, permission upgrade,
browser cookie, account impersonation or failed-request retry. Policy reads are
for an explicit endpoint and its verified associated profile; inventory remains
account-scoped. Arrays may be empty without implying denial.

| Resource | Route / response | Source contract | Live result |
| --- | --- | --- | --- |
| Account/analytics region | `/users`; whitelisted region and explicit org-selection flag | [Authentication](https://docs.controld.com/reference/authentication) | Available |
| Endpoints/profile associations | `/devices?last_activity=1`; `body.devices[]` | [Endpoint reference](https://docs.controld.com/reference/get_devices) | Available |
| Profiles | `/profiles`; `body.profiles[]` | [Profile reference](https://docs.controld.com/reference/get_profiles) | Available |
| Observed clients | regional `/v2/client?endpointId=...`; `body.items` map | Vendor dashboard source A below | Available; only selected endpoint items retained |
| Native filters | `/profiles/{profile}/filters`; `body.filters[]` | Source A | Available |
| External filters | `/profiles/{profile}/filters/external`; `body.filters[]` | Source A | Available |
| Services | `/profiles/{profile}/services`; `body.services[]` | Source B | Available |
| Custom rules | `/profiles/{profile}/rules/all`; `body.rules[]` | Source A | Available |
| Folders | `/profiles/{profile}/groups`; `body.groups[]` | Source A | Available |
| Profile options | `/profiles/{profile}/options`; `body.options` | Source A | Available |
| Restriction catalog | `/profiles/restrictions`; `body.restrictions[]` objects | [Catalog reference](https://docs.controld.com/reference/get_profiles-restrictions) | Available |
| Enabled restrictions | `/profiles/{profile}/restrictions`; `body.restrictions[]` identifiers | [Enabled reference](https://docs.controld.com/reference/get_profiles-profile-id-restrictions) | Available |
| Default rule | `/profiles/{profile}/default`; `body.default` | Source A | Available |
| DNS activity | regional `/v2/activity-log/csv`; raw columns and query bounds | [CSV guide](https://docs.controld.com/docs/how-to-export-logs-to-csv) | Available on this personal account; not a universal entitlement |

Source A: vendor-owned public dashboard module
[`_app-9271d14cae999d91.js`](https://controld.com/_next/static/chunks/pages/_app-9271d14cae999d91.js),
UTF-8 SHA-256 `c5cb403324d77cc4ecb813d4c98223599124db087681862754ba2bec423aa2f6`.
Its query definitions establish these routes; the shared fetch boundary's omitted
method is the normal GET default. The client source independently establishes the
regional analytics host, endpoint query parameter and `body.items` client map.
Source B: vendor module
[`3622-b5490dd45f8ebe30.js`](https://controld.com/_next/static/chunks/3622-b5490dd45f8ebe30.js)
establishes the profile services query. No proprietary application source was
copied into TailD; only the verified READ contracts are implemented independently.
These observed vendor routes are not promised stable APIs. Changed envelopes stop
that category visibly, without substituting invented policy data.

No pagination protocol for these policy routes is documented/verified. Snapshots
say `returned-response-only`, not universal completeness. Observed next/cursor/
has-more/truncation indicators produce `incomplete`; the reader never invents a
next-page URL. Four-MiB responses, 10,000-element arrays and nesting depth 24 are
resource bounds, not execution deadlines. Response budgets fail visibly.
Each capability includes route, source, permission/scope, shape, validation time,
retention uncertainty and rate-limit behavior. HTTP 401/403 means denied, 429
retains sanitized seconds/HTTP-date Retry-After metadata without retry, transport
failures mean stale, and changed schemas mean incompatible. Raw unknown fields,
action codes and provider reasons remain raw; credential-shaped fields are omitted
and actual bearer echoes are rejected. No guessed allow/block action mapping is
introduced. Missing, denied, stale, incompatible and incomplete are not zero.

## Historical knowledge and integrated verification

Policy snapshots reuse the private schema-v4 history and existing typed query
surface. A capture is a one-microsecond point observation, not an invented
continuous interval or proof of the policy causing an earlier decision. Repeated
identical captures are idempotent. Retention and deletion suppress their replay.
No database migration or cached traffic-byte duplication is introduced.

Live verification read every available category on the explicitly selected
Windows endpoint/profile. A private owned store was closed and reopened; the
typed policy query returned exactly the captured resources and their uncertainty.
The old endpoint-inventory client field was absent. The independently verified
regional client interface then succeeded; absence of that legacy field was not
misreported as provider denial. The selected endpoint's 15-minute activity sample
was empty. A separately scoped account-wide sample returned 100 actual decisions
and explicitly reported truncation. It was retained as a bounded sample, never
attributed to this Windows host or declared a complete ingestion interval.
The live CSV additionally returned `categories` and `userId`; unknown columns
remain preserved alongside action/trigger/value, answers, profile/client,
protocol/type/status and answer-geography metadata. No queried names, account
values, addresses or token are included in public fixtures or documentation.

The existing READ credential was used transiently for the authorized validation,
not installed in the product vault. Native credential round-trip, replacement and
removal were tested using a synthetic temporary target. Product hidden/vault
input -> GET policy capture -> private SQLite -> reopen/query is covered by a
real loopback HTTP/SQLite contract. Fixtures cover path/scope validation, unknown
fields/codes, malformed envelopes, denied access, redirects, logical HTTP-200
errors, rate limits, pagination/truncation and non-echoed credential failure.
Private live evidence remains outside Git; the one-shot diagnostic harness is
expendable and is removed through the cleanup helper after reconciliation.
