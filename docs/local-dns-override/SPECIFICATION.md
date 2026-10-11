# Local DNS override — authoritative specification

2026-10-11 authorized amendment: ordinary transport outages now prioritize
connectivity. The shared-core [encrypted outage recovery specification](https://github.com/Darkaxt/tailscale/blob/main/docs/dns-outage-recovery.md)
supersedes R08's prior no-other-provider rule for eligible default-route queries
only. Missing/unsupported Android settings, specific routes and management gates
are unchanged. This is implementation authorization, not a claim that an APK has
been released or installed.

Version: 2.9. Date: 2026-09-23. Status: **Stage 12 COMPLETE**. Beacon now runs the independently implemented TailDNS Windows tray and matching current-core daemon/CLI/resolver set from the independently verified public `windows-v1.103.0+18` release. The signed TailDNS update provider is active through the tray's existing update preference; the real `+17` to `+18` unattended transition preserved the service path, machine identity, addresses, Tailnet Lock signer, resolver state, tray connectivity, public DNS and MagicDNS, and a replay correctly made no changes. The tray uses the exact preserved official multi-resolution icon resources, and the user's real taskbar confirmation shows the native transparent background without the former black pixelated tile. The existing task-attached promotion monitor was updated in place to require dependency-ordered core, signed Windows and Android releases plus independent verification. Stage 9 remains BLOCKED only on the target Fold's current ADB disconnection. Stages 3–8 and 10–12 are complete; Stages 1 and 2 remain parked only on the explicitly disclosed validation gaps.

Revision 2.9 records completion of R22. Core PR [18](https://github.com/Darkaxt/tailscale/pull/18) fixed service-to-interactive-session tray launch at the owning Windows token boundary and produced independently verified release [windows-v1.103.0+17](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.103.0%2B17). Core PR [19](https://github.com/Darkaxt/tailscale/pull/19) embedded the exact connected, disconnected, exit-node-online and exit-node-offline icon groups extracted from Beacon's preserved official `tailscale-ipn.exe` SHA-256 `5CB12834487A18C7356995BE33AA12ED59D9F533B9DC134069C0DCA42D44B133`; release run [35795113173](https://github.com/Darkaxt/tailscale/actions/runs/35795113173) published and independently verified [windows-v1.103.0+18](https://github.com/Darkaxt/tailscale/releases/tag/windows-v1.103.0%2B18) from exact core `57351e8a9724e157cd1b2f2cdba0009717f1e8e7`. Beacon's updater consumed the signed manifest, replaced all four payloads transactionally, retained `C:\Program Files\Tailscale\tailscaled.exe` as the automatic service path, kept node `nCPRwrVksn11CNTRL`, addresses `100.97.195.70`/`fd7a:115c:a1e0::ca01:c347` and signer `tlpub:ff4a7450ab477743b42ebef7f9c84f706a4b7b76ac36714a176eae9a39f2f523`, and left the backend Running with public and MagicDNS resolution passing. `AutoUpdate.Check` and `AutoUpdate.Apply` are true; replay rejected the current manifest as not newer without changing the deployment record, service or tray processes. The existing heartbeat `monitor-taildns-upstream-updates`, daily at 08:30 UTC, now requires exact-head core promotion, a signed and independently verified Windows release, then exact-core Android promotion and signed release; it performs no device deployment and stays quiet while current.

Revision 2.8 records the real Beacon deployment and removes the final proprietary-GUI compatibility assumption. Public Windows release `windows-v1.103.0+5`, produced from core `c36f8860764ec2654bb854012dfe0041bfb9e725` by GitHub run `35742696688`, was independently verified before installation. Beacon reports `VERSION_SHORT=1.103.0` and `VERSION_LONG=1.103.0-taildns.5`; its original node ID `nCPRwrVksn11CNTRL`, addresses, DNS name and Tailnet Lock signer remained unchanged. The default `Tailscale` service path stayed `C:\Program Files\Tailscale\tailscaled.exe`; all four installed payload hashes match the signed deployment record; Wintun and the retained official GUI match their original hashes; and the read-only hosts file retained SHA-256 `0F3B44BB6C1E5AA31E526959C4C98A57DE8A9CDB7FF72F9FE6A5008D900C50F3`, attributes `33` and length `127816`. The official startup link was removed, the TailDNS per-machine startup command was installed, the old GUI stopped, and supervisor PID `13724` replaced deliberately killed tray child PID `38616` with PID `7768`. The resolver reports the supplied Control D endpoint configured and applied; public DNS, self MagicDNS, `ayn-thor` and `ayn-thor.tail94fa2c.ts.net` resolved correctly, and a real tailnet ping reached Thor through DERP. Official automatic update checks and application remain disabled pending Stage 12.

Revision 2.7 records the user's correction that the official Windows GUI is not mandatory and must not force TailDNS onto an older daemon solely for binary compatibility. The requirement is feature-complete Windows control and reliable per-user tray lifecycle, not preservation of a proprietary executable. TailDNS may retain the official GUI during migration, but final Windows activation uses an independently branded tray client and the current matching TailDNS daemon/CLI. Missing official-menu behavior is a blocker; a command-line-only replacement or a presentation-only icon is insufficient.

Revision 2.6 records the Stage 11 native installer and Windows release evidence. Core commit `2f687b68643c1d96bfe1eb152d4b21beaf6c4490` produced public release `windows-v1.102.4+3` in GitHub run `35648271621`. The isolated signing job did not check out or execute repository code; it enforced the tag/schema/platform/source/file-set/size/hash contract, matched the protected Ed25519 private key to the configured public key, signed the manifest, verified the signature, and published. Independent public download reverified release checksums, signature, manifest payload hashes/sizes, exact source commit, `VERSION_SHORT=1.102.4`, `VERSION_LONG=1.102.4-taildns.3`, embedded public key and UAC resource. The executables are truthfully `NotSigned` by Authenticode. The first two immutable tags produced no release: `+1` exposed an incorrect daemon-output assertion and `+2` exposed ambient VCS dirtiness; both root causes were corrected before `+3`. The source and release workflow are integrated and pushed on core `main` through `0fb348a4c`. Real installer replay still requires one accepted UAC elevation and is not claimed complete.

Revision 2.5 records the successful Windows compatibility proof and the user's requirement to retain automatic updates through the TailDNS project. The proprietary GUI `1.102.4` failed against a newer `1.103.312` daemon even when the CLI matched; an exact `v1.102.4` shared-core backport with TailDNS changes succeeded after replacing both daemon and matching CLI while preserving the official GUI, driver, service path and state. R21 is corrected to that proven boundary. R22 requires a TailDNS update provider rather than a URL-only redirect of Tailscale's built-in Windows updater, whose metadata, MSI layout, version grammar and Authenticode contract are Tailscale-specific. The TailDNS provider must consume a signed project manifest, preserve the exact upstream GUI/core compatibility line, perform transactional rollback, and integrate with the already-authorized GitHub promotion and task monitor.

Revision 2.0 records the ObtainX/Obtainium update failure caused by the non-standard Android version name `VERSION_SHORT-taildns.N`. TailDNS releases now append the fork sequence as the standard numeric build component `VERSION_SHORT+N`; the corresponding GitHub tag is `vVERSION_SHORT+N`. Product identity remains TailDNS in the package, application, repository, release title and artifacts. Existing installations already classified as pseudo versions require one direct in-place installation of the corrected public APK; subsequent `+N` releases must compare automatically. This migration fact must be documented rather than hidden by increasing the upstream Tailscale version.

Revision 1.9 records the Fold validation showing that Android Automatic Private DNS and the saved Control D provider were readable and worked once Follow Android was selected, but the enabled empty-manual presentation allowed **Use local default resolver** to submit first and receive a backend HTTP 400. R19 requires the UI to prevent that invalid submission while keeping source selection explicit, autosaved and reversible.

Revision 1.8 records the user's correction that the final Thor replacement must survive AYN Launcher's Clear all behavior without the rooted Guard. R18 requires TailDNS activities to stay out of Recents on Android so the vendor launcher has no TailDNS task to force-stop, while preserving normal launcher/settings access, Always-on VPN operation and the selected Control D follow configuration. This must be solved at the task-visibility boundary, not with a restart watchdog or privileged whitelist mutation.

Revision 1.7 records the user's correction that the fork product is TailDNS, not an app still presented as Tailscale. R17 requires TailDNS naming across the public repository and user-visible app/release identity while retaining technically required upstream namespaces, protocol terminology, URLs, licenses, copyrights and attribution.

Revision 1.6 records the user's correction that GitHub already owns upstream detection and candidate validation. The scheduled Codex task owns the remaining outcome: consume exact passing results, merge the validated core and Android candidates in dependency order, create the next signed release, independently verify it, and repair failures. A passing current candidate must not be parked indefinitely as a supposed safety measure.

Revision 1.5 records the user's explicit delivery instruction to complete deployment and test what can be tested rather than stopping on an unavailable edge case. This changes verification gating, not required product behavior: inaccessible IPv6/captive-portal variants and a tool-prohibited device-input action become disclosed validation gaps, not release blockers. No untested path may be described as tested, and the original Thor Guard scenarios remain required where they can be exercised on Thor.

Revision 1.4 records the user's correction that Tailscale settings autosave. Local-resolver switches must commit immediately; there is no global Save DNS setting button. Manual URL text commits on keyboard Done with backend validation, not on each partially typed character. Explicitly selecting manual mode with no saved endpoint leaves the local override disabled until configured and enabled; an unusable source while follow remains selected still fails closed.

Revision 1.3 records the user's explicit test-scope change: automated device validation uses Thor only; the user will test the full release on the Samsung phone. Samsung pre-release observation is no longer an acceptance prerequisite. Root may be used for diagnostics and test setup on Thor, but the application must still work without privileged grants. Other requirements are unchanged.

Revision 1.2 records the user's authorization to implement, establish GitHub signing, and publish a proper release. R15 adds signed release delivery; R16 adds upstream auto-update and current-task monitoring only after validation. The historical documentation-only boundaries below describe the earlier delivery, not a revocation of this authorization. Live device changes remain subject to the explicit safety boundaries in R10 and R14.

Revision 1.1 adds R12–R14: native Android DNS reliability fixes intended to make Thor Tailscale DNS Guard unnecessary. It also corrects R02 to automatic propagation (not manual import), records the ordinary-app access test, and clarifies the transport work required by R08. No feature implementation is authorized by this documentation revision.

Owner repository: the public Darkaxt TailDNS fork of `tailscale/tailscale-android`.
Related documents: [evaluation and evidence](EVALUATION.md), [implementation stages](IMPLEMENTATION-PLAN.md).

## 1. Objective and delivery boundary

Let a user explicitly choose a device-local DNS-over-HTTPS default resolver while Tailscale is running, without changing tailnet policy or another device. Preserve MagicDNS and applicable more-specific DNS routing. Initial provider-specific assistance targets Control D; manually entered DoH endpoints are also supported.

On Android, an opt-in follow mode automatically propagates the saved system provider into Tailscale. Independently, fix native Android DNS/service lifecycle defects so the rooted Thor Guard is unnecessary for its demonstrated failure scenarios. The Guard is diagnostic history, not an implementation template or a component to improve.

The feature covers Android and a Windows shared-core/tray path. Android delivery is established; the Windows current-core tray, transactional installer, signed public release, fork-aware client updater and guarded upstream automation are implemented and verified on Beacon.

This specification controls behavior and acceptance. A plan or implementation cannot weaken it. Changes require an explicit specification revision that identifies the changed requirements.

## 2. Non-goals

- Editing tailnet ACLs, grants, tags, node attributes, provider accounts, or Control D profiles.
- Copying or forking proprietary Windows GUI code, supporting other desktop platforms, or replacing the Tailscale control server. An independently implemented Windows client using public LocalAPI/core contracts is in scope.
- A second Android VPN, root helper, watchdog, system Private DNS writer, or permanent OS resolver modification.
- Arbitrary DoT-to-DoH inference, plaintext custom resolvers, automatic provider failover, or a general DNS-provider framework.
- Improving, embedding, or shipping the Thor Guard, duplicate-connect recovery sequences, or process-restart watchdog loops as the native solution.
- Intercepting applications that use their own DNS/DoH or making a whole-device anonymity/leak-proof guarantee.

## 3. Required behavior

### R01 — Local ownership, opt-in and persistence

Default is **Use Tailscale DNS**: upstream behavior unchanged. The second mode is **Custom DoH** with exactly one validated endpoint. Configuration is local to the device **and current Tailscale profile**, persisted using existing protected preference storage, never sent to the control plane. New profiles start in upstream mode. Disabling custom mode retains its saved endpoint for later explicit reuse; deleting a profile removes its associated override.

Android additionally offers **Follow Android Private DNS provider**. The opt-in choice is profile-local; its provider source is the device's saved system hostname. Manual and follow modes are mutually exclusive. Disabling follow unregisters its observation and prevents queued callbacks from applying to another mode/profile.

All writers use one backend-owned preference contract. Invalid edits do not replace the previously committed configuration. Switching profiles cannot temporarily apply the previous profile's endpoint to the new profile.

Acceptance: first-run, save/restart, disable/re-enable, two-profile switching, deletion, and invalid-edit tests prove these semantics without a tailnet configuration change.

### R02 — Automatic propagation of the saved Android provider

After the user enables follow mode once, changes to `private_dns_specifier` propagate without an import button, another confirmation, opening the fork UI, or reconnecting the VPN. Read the saved hostname independently of `private_dns_mode`; do not use `isPrivateDnsActive()` or `getPrivateDnsServerName()` as the provider source. Mode changes update R03 conflict status without erasing the saved provider.

Use lifecycle-owned settings observation, an initial read, and re-read on backend/service recreation. Serialize updates through backend ownership and reject stale profile/configuration generations. Register/read ordering must not miss a concurrent save. Do not use periodic polling, arbitrary debounce delays or sleeps. Observe only while the relevant service/follow state needs it and unregister on teardown.

A missing, denied, invalid or unsupported current value is a visible follow error, not permission to revert to generic tailnet DNS or silently keep using an obsolete provider. Retain the last value for diagnostics only; ordinary default-domain queries must fail closed while follow remains selected and has no usable source. Preserve applicable specific routes. Manual mode or explicitly disabling follow remains the user's escape hatch. A transport outage uses R08 encrypted recovery; an unavailable settings source is not a transport outage.

Acceptance: real system saves propagate while the fork UI is closed; successive edits converge on the latest value; restart, observer teardown, profile switches and invalid-to-valid recovery are tested. A saved provider is consumed in Default/Automatic even without an active Private DNS server name. Verify observer delivery on Thor; the successful one-shot Samsung read test does not establish notification delivery. Record the Thor OS build and target SDK and test permission/read failures without privileged app grants. The user performs Samsung testing of the full release.

### R03 — Android operating mode and privilege boundary

The documented supported setup uses system Private DNS **Default/Automatic** with Tailscale active. The feature neither enables strict system Private DNS nor writes its settings. If strict provider mode is detected, report a configuration conflict and guide the user to system settings; do not claim the custom resolver is effective. If mode cannot be determined, show that uncertainty rather than guessing.

An already selected override must not silently revert to other defaults because of this conflict. Keep its configured state, mark effectiveness unverified/conflicted, and let the user resolve the OS setting. No root, ADB permission grant, privileged signature, or hidden-API reflection may be required.

Acceptance: ordinary installation works, mode changes are reported on return to the screen and relevant platform events, and failure to read settings does not crash or mutate them. No arbitrary polling, sleep, or timeout-based mode switching.

### R04 — Endpoint parsing and validation

Manually entered endpoints must be absolute `https` URLs with a nonempty DNS hostname, an explicit path, and port absent or 443. Reject user information, fragments, whitespace/control characters, malformed escaping, raw IP hosts, and query strings. These are intentional initial input constraints, not claims about all possible DoH services. Preserve path case and content. Do not follow redirects to another origin or downgrade TLS.

Control D hostname conversion accepts a single label before the exact `.dns.controld.com` suffix. Normalize hostname case and allow one DNS trailing dot. In the supported grammar the resolver ID is nonempty ASCII alphanumeric; an optional first hyphen introduces a nonempty client name containing only ASCII letters, digits and hyphens. Preserve subsequent client hyphens. Do not impose the example ID length as a rule. Reject extra labels, invalid DNS label lengths and ambiguous/unsupported forms; manual DoH entry is the escape hatch.

Examples, using fictional identifiers:

| Saved hostname | Derived endpoint |
| --- | --- |
| `abcd1234.dns.controld.com` | `https://dns.controld.com/abcd1234` |
| `abcd1234-name-goes-here.dns.controld.com` | `https://dns.controld.com/abcd1234/name-goes-here` |

The mapping follows [Control D documentation](https://docs.controld.com/docs/device-clients). Provider-independent observation must not be hard-wired to this mapping. Additional mappings require documented provider semantics; unknown providers cannot be guessed from a hostname. Until a mapping or native DoT implementation exists, report unsupported follow input and permit explicit manual DoH configuration. Universal DoT support is not claimed or silently added by this revision.

Acceptance: table-driven positive/negative parser cases, exact-suffix spoof rejection, client preservation, and validated real queries for one Control D and one other DoH endpoint. Syntax validity alone does not claim service reachability.

### R05 — Shared-core integration

Carry the local preference through the existing backend/LocalAPI and Android binding boundaries. Keep the backend authoritative. Do not overload the IP-only Android platform-DNS string or `dns.OSConfig.Nameservers` with URLs.

Build the normal eligible `dns.Config`, then select the custom `dnstype.Resolver` as its sole **default** resolver through an explicit composition boundary covering upstream early-return paths. Never mutate a shared netmap or append the custom resolver to competing defaults. Preserve upstream underlying-network discovery and DNS restoration. An immutable shared-core revision must be pinned in the Android dependency before feature integration is claimed.

Acceptance: focused core tests prove local selection, unchanged upstream mode, non-mutation, and propagation from the real Android editor to applied engine configuration; dependency provenance identifies the exact core commit.

### R06 — DNS precedence and preserved routes

Apply this order:

1. Upstream lifecycle/management eligibility gates remain authoritative (R07).
2. Upstream applicable **more-specific** MagicDNS, authoritative empty routes, split DNS, extra records, search domains and app-connector DNS behavior are preserved.
3. For names not covered above, the enabled manual/follow override replaces tailnet, DHCP and exit-node default resolvers. In the user's Control D setup, this replaces the generic tailnet profile with the Android-selected profile; the generic profile is not a fallback.
4. With custom mode disabled, the entire upstream selection path is restored.

An explicit root (`.`) route is a catch-all, not a more-specific route: while custom mode is active it must not bypass the custom default. Handle that case in composition without editing the original netmap. Preserve more-specific empty routes; they must not fall through to the public provider. Preserve upstream exit-node filtering of split routes rather than re-enabling routes upstream would omit.

Acceptance: tests cover overlapping suffixes, an empty authoritative route, a root route, MagicDNS enabled/disabled, extra records, search expansion, connector routes, tailnet defaults present/absent, and restoration after disabling. Real private and public queries reach their respective intended destinations.

### R07 — Lifecycle and policy gates

Apply custom DNS only while the backend is in an eligible running state with an authenticated, nonexpired configuration and accept-DNS enabled (`CorpDNS`). Missing netmap, expired key, logout, stopped VPN, DNS-disabled builds, or accept-DNS off must retain upstream lifecycle behavior; never force DNS installation around these guards. Retain the saved preference but report why it is inactive. Existing local management policies that prohibit DNS changes must also prohibit custom selection through both UI and API.

Reconfiguration is event-driven by preference, profile, netmap, relevant policy and network changes. Serialize changes through existing backend ownership; do not use sleeps, restart loops or arbitrary cancellation deadlines as synchronization. Restore normal OS DNS through the existing shutdown path.

Acceptance: transition tests and real restart/disconnect/reconnect/profile-change evidence show no stale endpoint, accidental reactivation, or stranded OS DNS. Policy tests verify that bypassing a disabled UI through the API does not bypass its restriction.

### R08 — Transport, exit nodes and failures

Reuse Tailscale's existing DoH transport where supported, with certificate and hostname verification. The pinned core only accepts recognized DoH endpoints, including Control D and NextDNS; arbitrary HTTPS resolvers and `tls://` resolvers are explicitly rejected in its forwarder. Generic manual DoH support therefore requires an actual transport/bootstrap extension and tests, not merely accepting URLs in the editor. See the [pinned forwarder](https://github.com/tailscale/tailscale/blob/b5e07cbf538e2558eac3c5fe5c34be288819fff6/net/dns/resolver/forwarder.go) and [provider table](https://github.com/tailscale/tailscale/blob/b5e07cbf538e2558eac3c5fe5c34be288819fff6/net/dns/publicdns/publicdns.go).

While custom mode is eligible, try the selected default endpoint first. On HTTP
5xx or connection failure, automatically recover through Cloudflare DoH using
the same TLS-verified, route-aware transport and maintained bootstrap addresses.
This intentionally bypasses provider filtering during an outage, without
changing saved settings; subsequent queries try the selected endpoint first.
Negative/block answers and DNS SERVFAIL, HTTP 4xx, redirects, configuration errors
and certificate rejection do not trigger recovery. Never fall back to plaintext
or an exit-node DNS proxy. MagicDNS, authoritative/split routes, policy gates and
exit-node egress remain unchanged. Expose recovery health, not permanent provider
reachability. See the shared-core specification for exact acceptance criteria.

The custom endpoint remains selected when an exit node is selected. Its traffic follows the intended exit-node route; it must not silently use a protected/direct socket to bypass the exit node. Audit actual transport behavior rather than assuming a `DefaultResolvers` assignment guarantees this. Preserve the user's existing exit-node configuration.

Resolver-host bootstrap is distinct from an ordinary DNS query. Reuse and document the existing supported bootstrap mechanism; prove it cannot recurse into itself. Record whether bootstrap exposes the resolver hostname to a base resolver, and its exit-node egress behavior. Do not advertise zero plaintext traffic if bootstrap requires such a lookup. Never use that exception to leak ordinary query names, disable TLS validation, or invent unmaintained provider IPs.

Stage 1 transport decision: known providers use the core's maintained address table. Generic endpoints use explicit base nameservers supplied by the platform OS configurator, through Tailscale's protected system dialer and DNS-over-TCP. Only the provider hostname is bootstrapped; it may be visible in plaintext outside the exit node. Reject loopback and Tailscale/service addresses to prevent recursion, and fail if usable base DNS is unavailable. Do not substitute another public DNS provider. DERP bootstrap is not a generic resolver and must not be used for this path. The provider's subsequent HTTPS connection uses route-aware user dialing with normal TLS validation. Host tests do not satisfy the Android network matrix.

Acceptance: packet/provider evidence covers successful DoH, cold bootstrap, TLS rejection, DNS/HTTPS outage, no unintended fallback, exit node on/off, IPv4-only, IPv6-only, dual stack, network handover and captive-portal failure/recovery. Diagnostic/protocol timeouts may report failure but must not change provider selection. Connection recovery follows real network/transport events. Per revision 1.5, matrix variants unavailable in the authorized environment are recorded as untested known limitations and do not by themselves block deployment or release; accessible primary paths, failure semantics and host-level invariants must still pass.

### R09 — Truthful Android UI and diagnostics

Switch changes save immediately, following existing Tailscale settings behavior. Do not require a separate Save DNS setting action for enabling or selecting follow. Manual URL editing commits on keyboard Done after backend validation; invalid input cannot replace committed configuration.

The DNS screen shows source, configured endpoint, backend-applied mode, inactivity/conflict/error reason, and applicable routing caveats. Do not derive effective local DNS solely from the tailnet netmap. Distinguish **configured**, **applied**, and **lookup verified**; a successful lookup is historical evidence tied to the configuration/network generation, not permanent proof. Never show a stale successful result after a relevant change.

Resolver paths and Control D IDs/client names can identify a user. Display them only where needed for deliberate local configuration; redact from ordinary logs, exported diagnostics, telemetry, screenshots in public evidence, and crash reports. Do not add background diagnostic queries or provider-account access.

Acceptance: editor/screen tests cover all modes and error states; actual status corresponds to backend state; logging and diagnostic review finds no unredacted identifier. A lookup check uses a disclosed non-sensitive test name and reports what it actually verified. If device automation policy prohibits one input action, retain the host regression and source/UI contract evidence, record the missing device action, and leave final full-release phone interaction to the user without blocking deployment.

### R10 — Windows implementation boundary

Use the same shared-core preference and DNS composition contract in a forked Windows daemon, matching CLI and independently branded TailDNS tray client. The tray client must view, set and clear the local custom resolver, inspect effective state through the authenticated local interface, and preserve the complete user-visible control set of the installed Windows client. It must detect incompatible/unmodified daemons and never display a successful apply when unsupported. It must keep the backend's interactive client lifecycle alive, start once per interactive user session, reconnect on deterministic service state changes, and supervise its tray child so abnormal exits recover without converting an explicit user Exit into a restart loop.

Do not copy or claim to fork the proprietary official GUI. Do not silently replace an installed official service. Device testing requires an explicitly selected test installation and documented install/uninstall/restoration procedure; normal implementation authorization does not authorize user-host deployment.

Acceptance: a real Windows test system proves frontend → authenticated local API → daemon → DoH, persistence, disable/restore, MagicDNS/split DNS, exit-node behavior, policy gates, unauthorized local mutation rejection, and incompatible-daemon handling. Windows resolver selection is explicit; Android saved-setting follow has no Windows analogue.

### R11 — Compatibility, verification and publication honesty

Keep upstream license/copyright notices. Before any distributed build, define independent app identity, signing, update and migration behavior; never assume an independently signed APK can update the official package or preserve its login automatically. Document how the fork tracks the exact Android and core revisions. No release, deployment or artifact build is authorized by this documentation task.

Future feature completion requires all acceptance criteria here, integration across both platforms, and recorded reproducible evidence. Mocks cannot substitute for required real queries or device behavior. Maintain the README's unimplemented status until the stated behavior has actually been implemented and verified; intermediate milestones must identify what remains.

Acceptance: requirement-to-evidence reconciliation is complete, licenses and dependencies are auditable, both platform workflows have real evidence, and publication statements match the delivered code. A feature release remains a separately authorized action.

### R12 — Root-cause audit of Android DNS reliability

Audit the native Android service/backend startup, underlying-network callbacks, TUN replacement, internal DNS/netstack packet handling and upstream forwarding boundaries. Use [Thor Guard v1.1.0](https://github.com/Darkaxt/ThorTailscaleDnsGuard/tree/v1.1.0) as evidence of process-loss recovery and connected-but-DNS-dead scenarios. Do not modify the Guard. Its public-name probes do not independently establish a MagicDNS defect.

For each scenario distinguish: process absent; service not initialized; locally answered MagicDNS failure; default/split upstream forwarding failure; Android resolver plumbing failure; upstream outage; or general connectivity loss. Capture actual DNS answers over UDP/TCP, not just ICMP reachability to `100.100.100.100`. Compare a locally answered tailnet name, a public name, a split-domain name, direct upstream queries, raw-IP connectivity, and PeerAPI where relevant. Associate observations with process, network and TUN generations, without exposing private names or provider identifiers in public evidence.

Audit upstream issue/fix history against the exact pinned revision before duplicating changes. [Issue #21155](https://github.com/tailscale/tailscale/issues/21155) is a handover/netstack lead, not proof of the Thor's cause; [#19445](https://github.com/tailscale/tailscale/issues/19445) is a separate exit-node lead and its closure is not fix evidence. Record each candidate's current disposition and whether a relevant fix is already present.

Acceptance: a reproducible baseline or captured failing-device evidence isolates the failing boundary for each targeted defect, with a test that fails before the proposed fix. Unreproduced scenarios remain explicitly unresolved; successful restarts, similar issue reports and symptom matching cannot substitute for causal evidence.

### R13 — Native lifecycle fixes, not embedded recovery workarounds

Fix the defects established by R12 at their owning lifecycle/packet boundaries. Once Android invokes a legitimate service start/restart, one start must initialize an operational tunnel and DNS path; repeated calls must be safe and idempotent, not required for success. Preserve explicit disconnect, logout, policy and accept-DNS intent. Handle Android process recreation and Always-on service entry without force-stop/connect loops, duplicate broadcasts, arbitrary sleeps or privileged helpers.

Network handover, Wi-Fi roaming and TUN replacement must not leave the internal resolver permanently unable to receive or send while the VPN reports an otherwise healthy connection. Preserve correctly owned packet processing and resource teardown across replacement. Propagate actual failures to health reporting; do not label every external DNS timeout as internal corruption or restart the whole app to mask it. Recovery from ordinary external outages must not change the chosen resolver or violate R06–R08.

An app cannot execute while its process is absent. Measure Android's actual restart behavior on the Thor. If the OS does not schedule the required restart and no supported unprivileged native mechanism resolves that scenario, record it as a blocker to Guard-obsolescence rather than silently excluding it or claiming guaranteed resurrection.

Acceptance: pre-fix failing regressions pass after the minimal native changes; a single platform start restores real DNS; repeated starts do not create competing resources. Controlled process reclamation (not force-stop as a substitute), explicit disconnect, handover in both directions, Wi-Fi loss/return, and relevant TUN write/close failure tests preserve or correctly restore DNS without external assistance. Never kill or disrupt a user's device for testing without applicable live-test authority.

### R14 — Demonstrate that Thor Guard is unnecessary

The product objective is to make the Guard obsolete for its demonstrated scenarios, not improve the workaround. Perform real acceptance testing on the intended AYN Thor with the Guard disabled and absence of its monitor verified. Disabling/removing the Guard is a separately authorized live-device action; this document does not perform or authorize it. Keep an explicit recovery procedure and restore the previous setup if testing fails. Do not uninstall the user's Guard merely because unit tests pass.

Record baseline and fixed app/core/OS revisions, Guard state, triggers, process/network generations and sanitized query results. The matrix must cover process reclamation with Always-on, a single subsequent service start, connected-but-DNS-dead reproductions, Wi-Fi loss/return and roaming, available network handovers, sleep/wake, exit node on/off, and both normal tailnet DNS and the automatic Android override. Cellular handovers unavailable on the console may be exercised on the Samsung phone, but do not replace Thor-specific reclamation and Wi-Fi evidence. Test locally answered MagicDNS, split DNS, public forwarding and direct-IP controls separately.

Define a repeatable transition sequence and a recorded observation window based on the reproduced failure cadence before testing; observation bounds are diagnostics, not application recovery timers. A single successful lookup is insufficient. A demonstrated original Guard scenario that can be exercised on Thor remains unresolved until tested. Unavailable cellular, captive-portal or other environment variants are disclosed validation gaps under revision 1.5: they do not block release, but they cannot support a claim that those variants were tested.

Acceptance: R12–R13 defects are fixed, the recorded repeatability/observation criteria pass without the Guard or manual restart assistance, explicit disconnect remains respected, and provider propagation retains R06–R08 behavior. Final reconciliation explicitly states whether every original Guard scenario is covered. Only then recommend retirement; actual removal still requires user authorization.

### R15 — GitHub signing and verified release delivery

Establish an independent persistent Android signing identity and package/update identity before installing the fork for acceptance tests. Preserve the official app and its credentials; do not overwrite it or reuse unrelated application signing keys. Store private signing material only in protected local storage and GitHub encrypted secrets, never repository content, artifacts, logs or pull-request jobs. Record the public certificate fingerprint. Make artifact version codes deterministic and monotonically increasing for published updates.

A tag-bound GitHub workflow must test the exact Android/core revisions, build the production APK, sign it with the pinned identity, verify package/version/certificate, generate checksums and publish a clearly branded release with source provenance and known limitations. Preserve the upstream-derived Tailscale `VERSION_SHORT` exactly; TailDNS releases must append only the monotonic fork subversion as the standard numeric build component `+N` to form the APK version name and release tag. Never manufacture a higher Tailscale version for a fork release. Restrict signing/release permissions to trusted release execution; untrusted pull requests must never receive secrets. Preserve the identity for future updates and document recovery without disclosing secrets. Account for the Windows deliverable's packaging, license and integrity evidence. Publish a signed update manifest and verify its pinned public identity before trusting Windows payload hashes. Do not describe manifest signing as Authenticode and do not imply Authenticode signing if no certificate exists.

Acceptance: after integrated validation, publish the completed release, independently download its artifacts and verify checksum, package/version and Android signer against the recorded expected values. Confirm the release corresponds to the tested commits and that update installation preserves fork preferences on an authorized test device. Do not publish intermediate incomplete feature releases. Signing configuration required for earlier live testing belongs to that test's stage; final public release belongs to Stage 6.

### R16 — Post-validation upstream auto-update and task monitoring

Only after successful integrated validation and the signed release gate, use GitHub's upstream detection and trusted candidate checks to integrate Android/core updates in reviewable candidate branches. Keep Android/core version compatibility and fork behavior intact. Failed or unverified candidates must not replace the last good release, and signing secrets must not be exposed to untrusted upstream changes. Once an exact current candidate passes its required trusted checks, the scheduled Codex task must review and merge it rather than leaving the fork stale. Promote core first, refresh and validate the Android candidate against that merged revision, then merge Android and create the next monotonic signed release from the exact merged commit. Independently download and verify the release. Do not turn CI success into a claim of new device validation.

Use one recurring monitor attached to this existing Codex task, not a new standalone task. Inspect existing automations to avoid duplicates. It must consume GitHub's detection/check results, perform the gated merge/release sequence above, investigate and fix bounded pipeline/regression failures, verify corrections, and remain attached through independent release verification. Stay quiet while healthy with no new candidate. Notify on a completed release, a genuine blocker or required user action. Do not weaken acceptance criteria, rotate signing identity, bypass security gates or perform device changes automatically. Record the automation identity and chosen cadence.

Acceptance: an end-to-end upstream rehearsal demonstrates detection, exact-head validation, dependency-ordered core and Android promotion, signed release publication, independent artifact verification, failure containment and recoverability. The task-attached monitor is verified with that scope. Unresolved failures cannot be hidden by leaving passing candidates parked, disabling tests or publishing an unverified build.

### R17 — TailDNS product identity

Present the fork as **TailDNS** in the repository title, Android launcher/activity/tile labels, onboarding, About/settings identity, app-owned status and failure notifications, release titles and public documentation. The public repository name must also identify the project as TailDNS. Do not present the fork itself as the official Tailscale Android app.

Retain Tailscale where it truthfully names the upstream service, protocol concepts, Tailscale DNS/addresses/subnets, control/admin endpoints, Go module, source namespace, binary compatibility boundary, original copyright/trademark notice or upstream attribution. Do not perform a source-namespace rewrite that would obscure provenance or make upstream integration needlessly fragile.

Acceptance: a repeatable branding contract checks the public project heading and Android product-identity strings; the manifest uses the independent TailDNS label; the trusted candidate and release workflows execute that contract; the public repository and release identify TailDNS while the README explains which Tailscale-derived technical identifiers intentionally remain.

### R18 — AYN Clear-all resilience without a watchdog

On the AYN Thor Android 13 build, the vendor Launcher3 Clear all implementation calls `ActivityManager.forceStopPackage()` for each unlocked recent task unless its package is on a vendor system whitelist. TailDNS must not expose `MainActivity`, `ShareActivity`, or another app-owned task in Recents, so Clear all cannot select the TailDNS package for force-stop. The app remains launchable from its launcher icon, deep links, shares and Android VPN settings; excluding tasks from Recents must not disable, disconnect or hide the foreground VPN service itself.

Do not modify the device-wide vendor whitelist, require task locking, add a root helper, restart loop, broadcast loop, periodic poll or watchdog. An explicit user or administrator force-stop remains authoritative and is not bypassed.

Acceptance: a regression contract fails when either task-owning activity is not excluded from Recents; the built manifest confirms the exclusion; and a real Thor run proves that after opening TailDNS and using AYN Launcher's Clear all, the TailDNS foreground process and VPN owner remain present, the package is not marked stopped, Always-on still names TailDNS, Android Private DNS remains Automatic with the saved provider, and public Control D resolution plus MagicDNS both pass. The exact launcher/package/OS evidence and release artifact identity are recorded. Publish and install the required release without increasing the official Tailscale version component. The legacy `-taildns.N` form used by the already-completed R18 release is superseded for later releases by R20.

### R19 — Source-first local DNS interaction

When the local override is off, manual mode has no committed HTTPS endpoint and Follow Android is not selected, **Use local default resolver** must be disabled. The screen must not submit an empty manual endpoint or surface a generic backend error for that invalid first-click path. Follow Android remains independently selectable and autosaves without enabling the override; once a valid source is selected or committed, the local enable switch becomes available. An already configured override must always remain disableable even when its current source later becomes unavailable.

Do not silently select Android follow mode, write Android Private DNS settings or merge source selection with override enablement. The backend continues to reject invalid mutations as a defense boundary; the Android UI prevents the known invalid interaction before it reaches that boundary.

Acceptance: a focused state-matrix regression fails before and passes after the UI policy change, covering empty manual, saved manual, Follow Android and already-configured states. A signed update installed in place on the authorized Fold preserves its profile and selected provider. The real screen proves the empty-manual local-enable control is unavailable, Follow Android remains selectable, and restoring Follow Android plus local enablement again reports the derived endpoint as applied; public DNS and MagicDNS resolve. Publish and independently verify the required release without increasing `VERSION_SHORT`. The legacy version syntax of the already-published `.6` artifact is superseded for later releases by R20.

### R20 — Updater-compatible fork subversion

Preserve the upstream-derived numeric `VERSION_SHORT` exactly and identify each TailDNS build with a positive, monotonically increasing numeric build component: Android `versionName=<VERSION_SHORT>+<sequence>` and GitHub tag `v<VERSION_SHORT>+<sequence>`. Do not manufacture a higher Tailscale major, minor or patch value. Keep TailDNS branding in the independent package/application identity, repository, release title, documentation and artifact names rather than in a non-standard version qualifier.

The release contract must reject zero, non-numeric and malformed sequences, preserve the Go runtime's upstream-compatible `VERSION_LONG`, keep Android `versionCode` monotonic, accept both legacy `-taildns.N` and corrected `+N` releases when locating the previous published version-code evidence, and prove that two successive corrected releases are comparable by ObtainX 2.10.00 and current Obtainium standard-version rules. Do not overwrite or delete immutable legacy releases.

An updater that has already stored a legacy TailDNS release as a pseudo version cannot be repaired by code it refuses to install. Seed the corrected scheme with one direct, signed, in-place public-APK installation on the authorized Thor. Preserve the package data, signer, login/profile, Android Private DNS state, TailDNS follow configuration and Always-on assignment. Do not open or drive Thor's UI; target only its explicit ADB serial. After installation, verify the corrected package/version, retained install identity and runtime DNS behavior. Document that other legacy installations may need the same one-time direct update, after which future `+N` releases are automatically comparable.

Acceptance: the focused version contract reproduces the legacy incompatibility and passes the corrected current-to-next comparison; trusted validation and tag-bound signing succeed; the public release is independently verified against checksum, package, version, signer and provenance; and Thor receives only that public APK in place with its state retained and public plus MagicDNS resolution working. The release and evidence documents identify the one-time migration boundary and the automatic behavior of later corrected releases.

### R21 — Transactional Windows in-place upgrade

Provide a supported Windows AMD64 upgrade that attaches the TailDNS daemon and
resolver CLI to the already-installed `Tailscale` Windows service rather than
creating a second daemon, profile or machine. Reuse the existing default named
pipe and `%ProgramData%\Tailscale` state so the machine login, node identity,
tailnet IPs and Tailnet Lock signing key remain unchanged. Do not copy, export,
log or recreate private state. The required driver and official installation
may remain as migration plumbing; do not remove the official MSI or GUI before
the TailDNS tray client and current matching daemon/CLI are running and verified.

Keep the existing service image path byte-for-byte unchanged. After verifying
release checksums, service identity, state presence and administrator context,
stop the service and atomically replace its installed `tailscaled.exe` and
`tailscale.exe` with the mutually matching current TailDNS build. Keep the
Wintun runtime and `%ProgramData%\Tailscale` state untouched. Install the
independently branded tray client and resolver companion beside them. Before
activation, retain exact hash-verified copies of both original binaries in a
narrowly owned recovery directory and record all original/replacement hashes,
the unchanged service path and prior auto-update preferences in a non-secret
deployment manifest. Disable official automatic application of updates until
R22 is verified so it cannot silently replace only part of the compatible set.
A failed activation or verification must restore both exact original binaries
and updater preferences while leaving the service path unchanged. Deliberate
rollback has the same contract and must not delete machine state.

After activation, verify the same node ID, tailnet addresses, running backend,
Tailnet Lock enabled state and local trusted signing key. Apply the explicitly
supplied Windows Control D HTTPS endpoint through the authenticated TailDNS
LocalAPI, then verify configured/applied status, a public lookup and MagicDNS.
Treat the Windows hosts-file projection as an optional single-label lookup
optimization, not a prerequisite for the VPN or DNS engine. If the existing
hosts file is explicitly read-only, preserve its contents and attributes,
skip that optional projection with a diagnostic log, and continue applying the
NRPT/interface DNS configuration. Do not clear the attribute, replace the file
or let the optional write force the backend to `NoState`. A writable hosts file
must retain the upstream update behavior, and non-read-only write failures must
remain visible failures rather than being silently ignored.

The tray client must cover connect/disconnect, login and profile switching,
current device/address access, exit-node selection and LAN access, route and DNS
acceptance, incoming-connection shielding, unattended mode, TailDNS resolver
configuration/status, update preference, version/about information, access to
the admin and detailed settings surfaces, and explicit Exit. A persistent IPN
bus watch owns the interactive backend connection. Startup is per interactive
logon and single-instance per session. A small same-binary supervisor may
restart an abnormally terminated tray child, but an explicit Exit must terminate
both processes. Do not use periodic polling or arbitrary sleeps for lifecycle
or service synchronization. The Windows tray must use the preserved official
client's actual multi-resolution connected, disconnected, exit-node-online and
exit-node-offline icon groups with recorded source hash and resource IDs rather
than visually approximating those states. A generated icon is permitted only
for a transient state for which that official binary contains no corresponding
grouped resource.

The release archive must include the tray client, installer, rollback/status path and an
automated contract covering fail-closed preconditions, state preservation,
rollback metadata, checksum enforcement and release packaging. Windows
executables remain truthfully documented as unsigned unless Authenticode
signing is added.

Acceptance: a test-first deployment contract fails before and passes after the
installer implementation; trusted validation and tag-bound release workflows
package the exact reviewed installer and binaries; independently downloaded
assets match their checksums and provenance; and Beacon performs an in-place
upgrade from the existing official service with no login or new machine entry.
The pre/post node ID, addresses and trusted Tailnet Lock signing key match,
official auto-update no longer applies updates, the supplied resolver is
configured and applied, public plus MagicDNS lookups pass, and the documented
rollback remains available. On Beacon's read-only hosts file, repeated daemon
and TailDNS tray reconnect verification must keep the backend `Running`, preserve the
file's hash and read-only attribute, and pass public plus fully qualified
MagicDNS lookups. Publish a Windows release identified as
`windows-v<upstream-version>+<sequence>` without increasing the upstream
Tailscale version component. The daemon, CLI and tray client keep
`VERSION_SHORT=<upstream-version>`; TailDNS sequence metadata is recorded
separately and in the release manifest rather than presented as a newer
official Tailscale version.

### R22 — Fork-aware Windows auto-update and upstream promotion

The TailDNS tray client's **Automatically install updates** preference is the
single user control. A TailDNS daemon must never use it to install an
official-only MSI over a fork deployment. When the TailDNS update provider is
present and verified, the existing `AutoUpdate.Apply` preference controls that
provider. Until then it remains false. Do not implement this as a blind base-URL
substitution: the upstream Windows updater expects Tailscale-specific latest
metadata, official MSI filenames/version grammar and Tailscale Authenticode.

Publish a small signed update manifest from the public TailDNS project. It must
identify the exact upstream version, positive TailDNS sequence, Windows
architecture, source revisions, installer asset URL, payload size and SHA-256,
minimum supported installed state, and signing-key identity. The client embeds
only the verification public key and project endpoint. The private manifest key
exists only in protected GitHub release secrets. Reject unsigned, malformed,
replayed, lower-sequence, wrong-architecture, wrong-upstream-base or
hash-mismatched updates without changing the installation. Logs and diagnostics
must not expose private state or resolver identifiers.

For another TailDNS sequence on the same upstream base, invoke the verified
transactional installer directly. For a newer upstream base, update only when a
matching TailDNS release is available. The update transaction replaces daemon,
CLI and TailDNS tray client as one verified set. It preserves the installed
driver when the new core declares it compatible; only an explicit driver
requirement may stage the corresponding official package after verifying its
version and Tailscale Authenticode. It must not reinstall the proprietary GUI as
a version-lock dependency. The bootstrapper must remain outside binaries being replaced,
preserve `%ProgramData%\Tailscale`, node identity, addresses and Tailnet Lock
material, and restore the last verified complete set if overlay activation fails.
Never leave a mixed daemon/CLI/tray version set classified as successful.

GitHub remains responsible for upstream discovery and trusted candidate checks.
The existing task-attached monitor must consume those results, promote core
first, refresh and promote Android/Windows candidates, create the next signed
platform releases, independently verify public artifacts and repair bounded
failures. A passing candidate is merged and released rather than merely
reported. The monitor stays quiet when current and healthy, and notifies only
on a completed release, genuine blocker or required user action. Device changes
are never automatic.

Acceptance: test-first contracts cover manifest signature and schema validation,
version/sequence ordering, same-base update, official-base transition, mixed-set
rejection, interrupted activation rollback and updater-preference mapping. A
GitHub rehearsal publishes a signed candidate manifest and independently verifies
it. Beacon then updates between two TailDNS Windows sequences with automatic
updates enabled while retaining the TailDNS tray connection, service path,
machine identity, Tailnet Lock signer, resolver configuration, public DNS and
MagicDNS. A rehearsed upstream-base transition verifies the official MSI before
overlay and proves failure containment. The task-attached monitor performs the
dependency-ordered promotion/release path and records its automation identity.

## 4. Evidence record and completion rule

For each requirement record: implementation commit(s), exact core/Android revision, test command and outcome, platform/OS/target SDK, configuration generation, real-boundary evidence where required, and redacted failure/restoration observations. Record unsupported environments explicitly. A compatibility claim must name the actual tested matrix rather than imply every OEM works.

For each blocker record the requirement, concrete cause, internal/external ownership, resolving condition and dependent work. A deferral is valid only when assigned to a named later stage without weakening the current stage's acceptance criteria. All required blockers and deferrals must be resolved before overall completion.

The final evidence set is indexed by [FINAL-RECONCILIATION.md](FINAL-RECONCILIATION.md), [RELEASE-VALIDATION.md](RELEASE-VALIDATION.md) and [UPSTREAM-UPDATES.md](UPSTREAM-UPDATES.md). It includes exact source revisions and GitHub runs, independently verified release artifacts, Guard-disabled Thor workflows, isolated Windows integration, real upstream candidate rehearsals, and the verified task-attached monitor. The unavailable environments and prohibited device-input action remain explicitly untested rather than being inferred from the passing evidence.
