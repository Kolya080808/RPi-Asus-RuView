# Next steps

Updated 2026-11-02. Current state and completed work: [HANDOFF.md](HANDOFF.md).
Detailed product and delivery decisions: [REQUIREMENTS.md](REQUIREMENTS.md).

## Panel repair (selected continuation on November 1)

- Peer/countdown repairs are implemented and October 6 file deployments are
  recorded as applied. Three retained short-capture reports support acquisition,
  but the capture-verification manifest still says `testing`. Finish acceptance
  and cleanup verification rather than restarting the repair from scratch.
  Evidence and remaining limits: [PANEL.md](PANEL.md#october-6-repair-status-reconciled-october-20).
- October 20 deployment `20261020T145805Z-f9c6b3` completed and verified the
  missing pause-readiness and reader-cancellation fixes. Bounded live acceptance
  passed pause/resume/stop and cleanup, but replay returned 422: the first two
  records have a provisional timer delta of 1,186.090651 s, before the pause.
  November 1: replay handling is repaired and deployed, with HTTP 200 acceptance
  on the same 21-record session. Discontinuities are explicit, all raw records
  retained, and no global time is fabricated. Initial stream/buffer provenance
  remains unresolved and is a separate next investigation. No new radio capture
  was run; the October 20 pause/resume/stop evidence remains historical. See
  EXPERIMENTS.md and PANEL.md for behavior, tests and limitations.

## One risk-accepted trial - November 1-2, 2026

The user now explicitly accepts one short active AX58 capture and possible
hang/reboot/client interruption, while keeping it in the home network. This
supersedes the historical blanket active block below for one trial only.
The authorized trial completed on November 2 after separately approved temporary
Pi roaming: nine raw datagrams, matching radio count delta, verified cleanup and
return to AX56. This one-shot authorization is consumed. Next work is offline
AX58 PHY packing/valid-length validation, followed by a bounded Pi integration
design. The initial offline structure audit is complete: known address fields
match, but candidate timer units and coefficient format remain unvalidated.
Do not choose the Managed GT backhaul or absent peer as a substitute, and do
not automatically repeat a capture. Details: AX58-READER.md and ROLLBACK.md.

## Immediate continuation of milestone 2

Current direction, October 28: the user asked to stop expanding driver-failure
investigation and concentrate on ordinary CSI acquisition without disrupting the
network. Earlier binary/emulation findings remain historical evidence in
REPEATER-CSI-RESEARCH.md; they are not a queue of further failure experiments.
The selected deliverable is still live RP-AX58 acquisition and continuous
decoding on Pi, supporting the eventual moving-object location system.

| Component | Confirmed | Still required |
|---|---|---|
| AX58 reader | November 2 active wl0.1/Pi trial: nine raw datagrams and verified cleanup | Sustained behavior and separately scoped Pi integration |
| Stock network export | No working IP/port CSI configuration identified in the examined releases | Do not assume RemoteWL forwards measurements |
| Receive layer | October 28 bounded SSH channel-to-journal adapter implemented; local validation described in RAW-PIPELINE.md | Reviewed source dispatch/termination, Pi deployment and measured capacity |
| Pi | October 28 synthetic receiver run: 32 frames / 69,118 bytes journaled, exact replay and temporary-file rollback verified | Actual live transport integration and sustained capacity; synthetic check does not qualify active CSI |
| AX58 interpretation | Nine complete raw datagrams retained; payload not decoded | Source-specific format/timing validation before decoding or motion claims |

The October 28 review and stability restrictions below are historical context.
The November 2 explicitly accepted one-shot trial superseded the active block
only for that completed operation. AX58 stays in the home network; no further
capture or continuous collection is queued for unattended execution.

Resume in this order:
1. Identify AX58 PHY packing and valid payload length from retained applicable
   source/build evidence. Preserve all raw bytes; do not reuse the GT decoder.
2. Validate candidate timing and signal interpretation independently. The nine
   unlabelled records cannot establish motion response or object position.
3. Prepare bounded AX58-to-Pi transport integration with baseline, exact scope,
   rollback and acceptance criteria before any newly authorized device trial.
4. After source-specific validation, assess motion/localization toward the
   observation system; 3D skeleton output remains a later unvalidated goal.

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
   October 16 [direct network export comparison](NETWORK-CSI-EXPORT.md) is
   complete: no working stock IP/port CSI exporter was identified for AX58 or
   AX56. RemoteWL is a command interface, not validated CSI forwarding. Fresh
   AX56 module hash and idle AP/up observations are recorded. Continue with
   separate validation of the shared helper approach, not a presumed built-in
   export setting. TP-Link is the already inventoried RE200 AC750; public-source
   identification at `.155` is complete: hardware 5.0, firmware 1.0.4 Build
   210408 Rel.37106n (8285), normal login verified. The official matching-build
   candidate is saved and decoded locally: VxWorks/MT7628 markers plus MIPS
   startup instructions rule out unchanged Linux/ARM helper reuse for this
   image. No usable CSI sender was identified. RE200 requires a separate
   platform-specific feasibility study with regional/installed-image matching;
   the earlier direct-request 401 and decompression blockers are superseded.
   The October 13 offline checkpoint found NIC Netlink export implementations in
   both exact-release images, with published image hashes verified. Both
   dispatchers reject ADD_AP command 5. At that checkpoint no repeater capture
   was validated; the November 2 AX58 AP/Pi raw trial is now confirmed.
   The October 14–15 continuation traced ordinary ADD and the reader contract:
   ADD success does not prove peer activation; the lookup/association paths
   do not establish Managed upstream support. AX58's enable path also lacks
   AX56's null-result guard. These historical findings do not authorize
   further device experiments or establish sustained safety.
   The October 15 [offline prototype](RAW-PIPELINE.md) now journals complete
   input independently of deferred decoding, including partial/error evidence.
   **Offline interrupted-journal recovery and legacy GT SQLite import are
   complete (October 15):** new-file recovery preserves committed bytes/times
   and marks completion unknown; the importer preserves exact BLOBs, sequence
   gaps and diagnostics without promoting prefixes or failed sessions. Local
   acceptance and limits are in [RAW-PIPELINE.md](RAW-PIPELINE.md).
   **User-selected target: live RP-AX58 acquisition and decoding on Pi.**
   Do not substitute GT collector integration or more offline import work for
   this target. October 15 live read-only preflight matched the installed AX58
   module hash to the inspected binary, but did not resolve the unsafe enable
   path. A subsequent SSH EOF-race fix and fresh queries confirm an AP/up eth1
   and an authenticated/associated/authorized peer on channel 4/20 MHz; the
   offline BSS audit now identifies the lookup's AP-role/up fields.
   The [minimal reader](AX58-READER.md) is built and locally tested; its
   socket-free ARM self-test passed on AX58 with exact temporary-file rollback
   verified (`54eb642bed79`), without CSI or Netlink reception in that self-test.
   Separately, passive protocol-23 reception with CSI disabled passed on October 22 with
   no data and verified cleanup. November 2 active acquisition produced nine
   raw datagrams; decoder validation and sustained Pi integration remain pending.
   The incident report and October 13 decision are
   already recorded; do not require resubmission or reopen milestone 1. Next
   establish a safe source-local reader/activation contract from the retained
   exact-build evidence before
   a reversible bounded capture. Current work follows the ordinary-acquisition scope above; historical static
   research does not require further failure experiments. The per-method evidence is in
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
