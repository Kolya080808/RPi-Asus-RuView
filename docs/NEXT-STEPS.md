# Next steps

Updated 2026-10-06. Current state and completed work: [HANDOFF.md](HANDOFF.md).
Detailed product and delivery decisions: [REQUIREMENTS.md](REQUIREMENTS.md).

## Current repair

- Restore manual capture on GT-AX11000, correct the countdown and verify live
  delivery, saved replay and controls on Pi with recorded rollback.
  Results belong in [PANEL.md](PANEL.md), not in this queue.

## Ordered milestones

1. **Resolve the RP-AX58 incident gate.** Analyze saved evidence and exact-firmware
   compatibility; improve disconnect-resilient diagnostics. Record a testable
   explanation or the evidence gap and a separately reviewed reversible test
   plan. Do not repeat the failed probe. See [repeater research](REPEATER-CSI-RESEARCH.md).

2. **Classify each repeater's CSI acquisition support.** Only after the incident
   gate closes, require repeatable raw records, per-device format/timing evidence
   and verified cleanup. If blocked, document why and choose a separately evaluated
   GT-AX11000 peer-link or Pi-source experiment. Keep GT-AX11000 as the baseline.

3. **Add selectable multi-source manual capture.** Offer a single verified source,
   any subset or all verified sources from the authoritative registry/map.
   Preserve source identities, layout revisions, raw streams, gaps and timing
   uncertainty in live views and aligned replay. Unverified sources stay
   unavailable. Details: [PANEL.md](PANEL.md).

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
