# Tailscale activity and TailDrop

The Tailscale **Connection** page includes the live device inventory. **Activity**
and **TailDrop** show recorded history. Offline last-contact is distinct from the
time TailD read a status snapshot; starting snapshots are not activity events.

Enable **Collect analytics** under **Tailscale → Preferences**. This single
recording decision selects Tailscale observations plus available Control D and
GlassWire integrations; Tailscale itself requires neither of those integrations.
New installations are off by default. Previously enabled installations migrate
to unified recording without a new persisted settings schema. Collection continues
when the window closes. Turning it off stops recording without deleting history
or preventing live devices and Control D policy management from working.
The existing global collector pause/resume and retention controls still apply.

| Source | Recorded information | What it does not establish |
|---|---|---|
| Tailscale status / IPN notifications | Visible peer ID, name, OS, reported presence; baselines, connection changes, exit-node changes and observation gaps | Ping reachability, historical uptime before tracking, or devices hidden from this client |
| Custom resolver status / structured health | Configured/applied override, captive-portal state and the encrypted-recovery warning | Provider latency, complete packet capture, or active fallback inferred merely from a configuration description |
| TailDrop notifications | Incoming/outgoing basename, available peer ID, source start time, declared/observed bytes and explicit reported result | File contents, complete paths, unobserved past transfers, or proof of a local save to Downloads |
| GlassWire | Existing application/time-bucket byte counters and destinations | Tailscale peer presence or TailDrop completion |
| Control D | Endpoint DNS questions, decisions, reasons and answer geography | Application traffic bytes or proof a process issued a particular query |

## Reading the history

Connection shows live daemon-reported presence, owner, addresses, OS, reported
routes/tags, creation/key-expiry timestamps, advertised SSH evidence and TailDrop
send eligibility/reason. Missing metadata is not proof a feature is disabled.
The local status API omits client versions, detailed OS versions and signing-node
roles; no extra administrative API credential is assumed. **Last online**
is Tailscale's supplied last control-plane contact for offline peers, **Online now**
for online peers, or explicitly unavailable for missing/legacy metadata. Reading
an offline snapshot now is not device activity now. Activity defaults to observed
changes and gaps; **Include starting snapshots** reveals initial state separately.
Starting snapshots are retained as provenance, not fabricated transitions. Online means
connected to the control plane, not necessarily reachable. Missing peers and
subscription gaps become **unknown**, never fabricated offline transitions.
Restart/reconnection starts a fresh baseline rather than filling an uptime gap.

TailDrop uses the daemon's explicit `Finished` / `Succeeded` or incoming `Done`
fields. **Received by daemon** does not mean saved to Downloads. Disappearance
without a completion signal is **unknown outcome**. Replayed completed transfers
are de-duplicated; source-local offsets and nanosecond timestamps normalize to
UTC without collapsing their identity precision.

Profile, period and Enter-applied search narrow a bounded local view of the newest
200 matching records. A truncation notice asks you to narrow the scope. Displayed
times use the local timezone; storage and query bounds use UTC. The existing
retention policy applies. **Delete activity history** removes these observations
for all profiles and suppresses old transfer replay, without deleting other
source history or changing VPN settings. New observations can resume afterwards.

## Implementation and validation boundary

The existing owning-user collector holds a read-only LocalAPI named-pipe
subscription. It persists only whitelisted metadata to the existing private
SQLite store; there is no additional service, scheduled task or administrator
requirement. It never stores raw notifications, authentication URLs or keys.
Cancellation settles pending Windows IO before the thread exits. A lost
subscription gets a ten-second monitoring opportunity; expiry does not cancel a
healthy read. Explicit resume/wake also creates a fresh observation opportunity.
Activity progress does not scan or expire GlassWire traffic or application rows.

Verification covers real daemon READ subscription, durable metadata and the
native-served interface, including 19 visible peers on the validation laptop.
Transfer completion/failure, malformed inputs, replay, profile changes, gaps,
retention/deletion and restart use explicit synthetic protocol fixtures. No real
file was transferred for these tests. Both native zoom levels (100% / 150%) and
560 CSS-pixel layouts are checked, including action failure visibility and
keyboard refresh. The running installed client, provider policy and devices are
unchanged. Release signing, installer activation and post-deployment validation
are not claimed by these development checks.
