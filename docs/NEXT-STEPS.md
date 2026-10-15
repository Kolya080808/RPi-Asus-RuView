# Next steps

Updated 2026-10-15. Current state and completed work: [HANDOFF.md](HANDOFF.md).
Detailed product and delivery decisions: [REQUIREMENTS.md](REQUIREMENTS.md).

## Pending panel repair (not the selected task)

- Restore manual capture on GT-AX11000, correct the countdown and verify live
  delivery, saved replay and controls on Pi with recorded rollback.
  Results belong in [PANEL.md](PANEL.md), not in this queue.

## Ordered milestones

1. **RP-AX58 incident review — documentary milestone complete (October 13).**
   Saved evidence, exact-build GPL findings, diagnostic repairs and the A/B/C
   plan are recorded. The user confirms the CSI/DHD watchdog cause from their
   own objdump and additional analysis, and directs the project to continue.
   Record this as the user's confirmed finding; the full binary analysis has
   not been independently inspected here. Do not repeat the failed probe.
   A safe replacement acquisition method still requires validation.
   See [repeater research](REPEATER-CSI-RESEARCH.md) and [experiments](EXPERIMENTS.md).

2. **Classify each repeater's CSI acquisition support — in progress.** The
   October 13 offline checkpoint found NIC Netlink export implementations in
   both exact-release images, with published image hashes verified. Both
   dispatchers reject ADD_AP command 5; no repeater raw capture is validated.
   The October 14–15 continuation traced ordinary ADD and the reader contract:
   ADD success does not prove peer activation; the lookup/association paths
   do not establish Managed upstream support. AX58's enable path also lacks
   AX56's null-result guard. Keep capture blocked; do not reproduce the risk.
   The October 15 [offline prototype](RAW-PIPELINE.md) now journals complete
   input independently of deferred decoding, including partial/error evidence.
   Next add bounded interrupted-journal recovery and a verified legacy GT import
   adapter before planning live collector integration. Remaining static research
   is exact lookup-field/association semantics and lifecycle safety. The per-method evidence is in
   [repeater research](REPEATER-CSI-RESEARCH.md#ordinary-add-and-reader-contract-2026-10-1415).
   Plan separate per-source
   acquisition, raw storage and later processing; initially assess one supported
   link at a time. See [recording design](RECORDING.md#separate-acquisition-and-processing-decision-2026-10-13).
   No new capture is authorized
   by completing the documentary review. Before any repeater acquisition,
   resolve the relevant compatibility/reset-risk gate and review a separate
   reversible plan; success requires repeatable raw records, per-device
   format/timing evidence and verified cleanup. If blocked, document why and
   choose a separately evaluated GT-AX11000 peer-link or Pi-source experiment.
   Keep GT-AX11000 as the baseline. Durable receipt/storage and decoding belong
   on Pi/PC; a minimal source-local reader is still needed for local Netlink.
   Validate live queues, stop/drop behavior, timing and Pi capacity separately
   before device deployment; deferred offline tests do not establish these.
   This static checkpoint does not complete stage 2 or authorize acquisition.

3. **Add selectable multi-source manual capture.** Offer a single verified source,
   any subset or all verified sources from the authoritative registry/map.
   Preserve source identities, layout revisions, raw streams, gaps and timing
   uncertainty in live views and aligned replay. Unverified sources stay
   unavailable. Separate streams need measured time alignment before joint
   position estimation; compare their contribution on held-out reference
   sessions. Details: [PANEL.md](PANEL.md) and [recording design](RECORDING.md).

4. **Add local panel login.** Protect reads and API actions; verify credential and
   session handling, recovery and revocation before longer experiments or Internet
   exposure. Details: [REQUIREMENTS.md](REQUIREMENTS.md#panel-authentication).

5. **Make capture and reference data reliable.** Preserve complete raw records and
   partial failures; validate 30-minute capture, pause timing and replay beyond
   10,000 records. Use time-based processing at all supported intervals. Add
   versioned map/reference snapshots and define log retention and auditable
   export/cleanup without silent CSI deletion. See [RECORDING.md](RECORDING.md),
   [PANEL.md](PANEL.md) and [map setup questions](HOME-MAP.md#experiment-setup-questions-2026-10-06).

6. **Collect a repeatable labeled dataset.** Confirm points in R08, R07 and R02;
   record stillness, arm motion, walking/stops, empty-room and cross-room motion.
   Preserve timing uncertainty and changed conditions; reserve whole later
   sessions for evaluation. Protocol: [EXPERIMENTS.md](EXPERIMENTS.md#planned-localization-validation-protocol).

7. **Evaluate localization independently.** Compare held-out room/zone estimates
   with simple baselines; report confusion, false/missed motion, delay and
   insufficient data. Evaluate continuous positions only when evidence supports it.

8. **Validate a moving-object point on the map** against independent reference
   positions. This is the first usable sensing deliverable and the tunnel gate.

9. **Design the Pi-server tunnel and cryptography.**
10. **Implement the tunnel.**
11. **Add panel tunnel controls.** Refuse Internet access without disconnecting
    the tunnel; retain direct home-LAN access in either state.
12. **Launch and validate Internet access.** Require verified panel login and
    completed tunnel controls; test access toggling and rollback.
13. **Implement and validate 3D skeleton reconstruction** after point tracking and
    the tunnel milestones, with separate quality criteria.
14. **Migrate to C++ and package the system when the user accepts Python readiness.**
    First review/fix Python; preserve formats and behavior. Supply Pi/server and
    Windows/macOS/Linux PC installers; phone access remains a responsive browser
    panel. Scope and recovery requirements: [REQUIREMENTS.md](REQUIREMENTS.md).
