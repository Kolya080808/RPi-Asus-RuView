# Experiment rollback

## Temporary Pi roam guardian - November 2, 2026

User explicitly authorized temporary Pi reconnection to AX58 AP
A0:36:BC:9B:BF:8A and return afterward. `scripts/pi_roam_probe.py prepare`
records the original NetworkManager UUID, BSSID and boot ID, code hash and
absence of `/tmp/ruview-roam-<12hex>.jsonl` in `deployment.json:pi_roam_checks`.
Check with `scripts/rollback.py --pi-roam-only --check` before launch.

No NetworkManager profile is cloned, edited or saved. A foreground Python
process started through nohup issues the standard transient wpa_cli roam,
waits 60 seconds and requests return to the original BSSID. It runs independently
of SSH and attempts return in finally on command failure or TERM/INT. Each
subprocess has an eight-second timeout; return state is checked for twelve
seconds. A different active profile is treated as external user intervention
and is not overwritten. One ordinary directed SSID scan refreshed the BSS cache
before the successful attempt; no radio restart or package installation.

The only added file is its private mode-600 JSONL log; the process/code/target
and original identifiers are manifest-scoped. Log records include its PID,
operation ID, boot and final profile/BSSID status. After the timed return,
`--pi-roam-only --check` verifies original profile/BSSID/boot, a successful final
log event and absence of the exact owned process. `--apply` copies the complete
log to recordings/pi-roam-<12hex>.jsonl, compares bytes again and deletes only
that exact regular file. A separate final check verifies absence. If return
fails or evidence is incomplete, preserve it and inspect; do not reset Wi-Fi
or silently change a profile. This is separate from AX58 monitor/file rollback.

Local fake-command tests passed: timed return, rejected target and refusal to
overwrite an externally changed profile. Plan 70f638a52d74 confirmed the target
and timed return; check/apply/check passed, log preserved locally and removed
from Pi. Original profile/BSSID/boot independently matched. The earlier rejected
roam 19d800f2a36b was also restored and its log retained.

## One active AX58 operation - November 1-2, 2026

User accepted one ordinary short CSI trial despite possible AX58 hang/reboot;
no automatic repeat. Operation ee8a83f9ee78 completed with nine datagrams and
verified cleanup: unchanged boot, disabled/empty monitors, no owned processes
or CSI userspace listeners, both exact temporary files absent. A later scoped
check passed. Baseline and after-state remain in deployment.json.

`scripts/active_reader_probe.py prepare` must record idle monitors, boot ID,
exact installed module hash, virtual AP/Pi readiness and absence of two paths
in `deployment.json:active_reader_checks`. It fixes AP `wl0.1`, Pi peer
`88:A2:9E:94:7D:80`, protocol 23, five seconds and 500 ms requested interval.
Run `scripts/rollback.py --active-reader-only --check` before upload. Only the
exact ARM builds recorded in `recordings/ax58-active-build-20261101/build.json`
may be uploaded to `/tmp/ruview-active-<12hex>-reader` and `...-supervisor`.
Files start at mode 600 and become 700; socket-free self-tests precede dispatch.

The supervisor waits for a dedicated post-bind readiness byte, then invokes
`wl -i wl0.1 csimon add <Pi-MAC> 500` and `enable`. After five seconds, or on
HUP/INT/TERM, it attempts `disable` and `del <Pi-MAC>`. Each wl child is waited
for one second, then only that still-unreaped child is signalled. A kernel-
blocked child is explicitly reported. Reader lifetime is eight seconds plus its
existing emergency alarm, with at most 64 datagrams and bounded output waits.
The source-local cleanup cannot recover a stuck kernel. No settings outside
this monitor/peer, services, startup, packages, firmware or keys are in scope.

All stdout/stderr/exit evidence is retained on PC. First-trial source validation
is not continuous Pi integration. Only after source cleanup, idle monitors,
no CSI userspace listeners, unchanged boot and absence of owned processes are
confirmed can file rollback remove the two exact-byte files and verify absence.
It never removes partial/unknown files or signals unknown tasks. Cleanup failure,
reboot or unknown state stops automation for inspection; no silent ioctl retry,
factory reset or automatic active rerun. A separate final narrow check is required.

## Replay repair deployment — November 1, 2026

Operation `20261101T181210Z-31c28c` is applied and verified. Pre/post rollback
checks passed, service active, whole-history counts/raw digest unchanged. Saved
replay acceptance passed (HTTP 200, 21 records, one explicit break). Original
file backups are in `recordings/panel-deploy-20261101T181210Z-31c28c/`.

Use the existing panel-only file deployment/rollback scope. Preparation records
all 17 mapped panel files, their original bytes/modes, service unit/state and
history counts/raw digest in `deployment.json:panel_updates`; backups are retained
under its operation-specific recordings directory. Changes affect saved-record
replay, API documentation and UI; applying restarts the existing panel briefly.
No router, capture, package, schema or startup-setting change is included.
Before apply run `scripts/rollback.py --panel-only --check`. After apply check
the same scope, read the known failed session through GET measurements/export,
and verify the raw digest/counts and service state. Restoration uses
`--panel-only --apply`, retaining current history rather than restoring an old DB.

## Synthetic Pi receiver check — October 28, 2026

Executed operation `39ab258501ff`: pre-run check, post-run check, scoped apply
and independent final check passed. Status `restored`; all three generated
files and diagnostics retained on PC under `recordings/pi-transport-39ab258501ff/`.
Temporary directory/process absent; boot/panel baseline unchanged.

`scripts/pi_transport_probe.py prepare` records the Pi boot ID, panel service
state and absence of `/tmp/ruview-transport-<12hex>` in the separate ignored
`deployment.json:pi_transport_checks` scope. The payload SHA-256 locks the exact
reviewed in-memory source. Before execution, run
`scripts/rollback.py --pi-transport-only --check`.

The only new remote files are `raw.sqlite3`, `stderr.bin`, `transport.jsonl`
inside that unique directory. Python modules arrive through SSH stdin and are
loaded in memory with bytecode writes disabled. The foreground command is
`timeout --signal=TERM --kill-after=2s 15s python3 -B - ruview-transport-<12hex>`;
it creates no service, package, socket listener or configuration. Its synthetic
32-frame stream is below 128 KiB; the receive polling deadline is five seconds.
No router commands or private recordings are used. The outer timeout owns only
its child process; rollback never signals unknown processes.

After execution, retain all three files byte-for-byte on PC under
`recordings/pi-transport-<12hex>/`, plus SSH diagnostics and the report. Run the
same narrow rollback check, then `--pi-transport-only --apply`. Removal requires
unchanged boot/panel state, no matching probe process, only expected regular
files, matching result hashes, and identical local evidence. Files are individually
removed, then the empty directory; no recursive removal. A separate final check
verifies absence and baseline. Unknown/partial output, changed bytes, symlinks
or failed execution require inspection and are not automatically erased.
Existing panel files, history, credentials and other deployment scopes are untouched.

## Active AX58 preparation — October 22, 2026

The active-trial design in AX58-READER.md is not a runnable rollback plan.
The exact binary audit now records timer delete/free/rearm ordering, but the
dispatcher/callback locks and peer lifetime remain unverified. No active entry
was added to the deployment manifest and no remote changes occurred during
this preparation. Preserve the restored passive entry and its evidence.

Before an active trial, implement a separate scope covering exact temporary
supervisor/reader files, owned tasks, the selected monitor and single peer.
Prove the bounded supervisor/failure paths locally, record baseline and dry-check
that scope, then verify actual stop/cleanup without deleting raw evidence.
The passive scope never owns monitor settings and must not be used to disable CSI.

## Passive AX58 reader plan — October 22, 2026

Outcome of the subsequently authorized trial: operation `b9821d3edd5f` is
`restored`, with `expected-no-data` and `cleanup_verified_utc`. Pre-run and
independent post-run `--passive-reader-only --check` passed. The wrapper removed
only `/tmp/ruview-passive-b9821d3edd5f` after exact-byte verification, checked no
owned process or userspace Netlink listener remained, and compared boot/monitor
state with the baseline. No standalone rollback apply or monitor command ran.

Preparation only: `scripts/passive_reader_probe.py prepare --protocol 23`
records fresh boot identity, both disabled/empty CSI monitors and counters,
process/socket observations and absence of the unique temporary path. It writes
only the local ignored manifest; it creates no device file, process or socket.
The entry is separate from `reader_self_tests`, under `passive_reader_checks`.

Inspect with `scripts/rollback.py --passive-reader-only --check`. Applying this
scope verifies absence and closes an unused plan as restored. For a future
uploaded plan it can remove only the exact full reviewed helper at that plan's
path, after process/boot/monitor checks and immediate byte revalidation. It
verifies absence and baseline afterward. Partial, empty, foreign or symlinked
files require inspection; it never signals processes or changes monitors.
If a bounded helper survives its alarm, stop automatic cleanup and investigate.
Do not reuse the socket-free self-test plan for passive reception.

The user subsequently authorized one bounded passive trial despite the documented
remaining lifecycle uncertainty. Execution now requires the exact prepared ID,
an earlier rollback check and explicit `--accept-passive-risk`. It rechecks the
baseline before upload and receive, exclusively uploads/verifies the helper,
records state before each action and preserves receive diagnostics. Complete
results invoke narrow cleanup; transport failures retain the last known state
for inspection with this same rollback scope. There is no automatic retry.
The planned device changes are one exclusive temporary executable (600 on
upload, 700 for execution), its bounded foreground process and kernel-managed
socket. No settings, services, startup entries, credentials, history or Pi files
are in scope. Local stdout/stderr and exit diagnostics must be preserved.

## Panel correction deployment — October 20, 2026

Operation `20261020T145805Z-f9c6b3` records a fresh Pi baseline and exact
17-file deployment mapping in ignored `deployment.json:panel_updates`.
Original files are retained under
`recordings/panel-deploy-20261020T145805Z-f9c6b3/`; application also saves
`history-before.sqlite3` with the service stopped. Scope is the existing panel
files and restart of `ruview-lab-panel.service`, preserving its unit, enablement,
keys and history. Existing `rollback.py --panel-only` implements this exact scope;
no new rollback action is needed. The pre-apply `--check` passed.
Recovery uses `python scripts/rollback.py --panel-only --check`, then
`--panel-only --apply` if restoration is needed. It restores file bytes/modes,
checks service state and preserves current history rather than replacing it.
No capture or router configuration change is included in this deployment.

Separate acceptance plan `panel-acceptance-20261020` is recorded in
`deployment.json:panel_capture_verification`; the prior plan is preserved in
`panel_capture_verification_archive`. Fresh GT boot/idle-monitor/peer/process
observations and Pi database counts/digest are in
`recordings/panel-acceptance-20261020/baseline.json`. Scope: one bounded
20-second, 200 ms GT eth6 capture using the already configured AX56 peer,
pause/resume/stop and retention of the resulting session. Existing
`rollback.py --capture-only --check` verifies no active panel capture, disabled
monitor, empty peer list and no collector. Normal cleanup is the capture's EXIT
trap; on failure stop the owned session and inspect before any recovery.
`--capture-only --apply` only permits the documented peer cleanup when marked
`recovery_required` and refuses unknown collectors/state. No repeater change,
key change, session deletion or persistent monitor is authorized by this plan.
Boot identity must also match the saved baseline after acceptance.

Outcome: file deployment is `applied`; checks passed before and after application,
with unchanged database counts/raw digest. The acceptance session
`210ad70f-fd78-4bfb-bb92-f776e36ef038` was stopped normally. Post-test
`--capture-only --check` passed and GT boot identity matched. Replay failed,
so its plan is `acceptance_failed_cleanup_verified`. No rollback apply was
needed or run. All old records plus the 21 new prefixes remain on Pi; no
temporary capture monitor/peer/collector remained. Full acceptance is not closed.

## AX58 diagnostic correction and local reader candidate (2026-10-15)

The socket-free self-test deployment is now implemented separately in
`scripts/reader_probe.py`. `prepare` records a fresh AX58 baseline (boot ID,
both disabled/empty monitors with counters, process/Netlink state), a unique
absent `/tmp/ruview-nl-<12hex>` path and the exact reviewed binary hash in
`deployment.json:reader_self_tests`. Run `scripts/rollback.py --reader-only
--check` before `scripts/reader_probe.py self-test`. The latter creates only
that file exclusively with mode 600, verifies bytes, changes its mode to 700,
runs only `--self-test` (no socket/CSI), verifies both synthetic envelopes,
removes the exact file and checks baseline again. No service or radio setting
is touched. SSH command/output/exit evidence is retained locally under
`recordings/reader-probe/` and `recordings/repeater-diagnostics/`.

Recovery: `scripts/rollback.py --reader-only --apply`. It refuses live processes
using that executable path (including deleted executables), changed boot or CSI
state, symlinks, unrecognized bytes, and files attached to a restored/prepared
operation. It never signals processes or changes a monitor. A full verified
upload is removable; interrupted/empty/partial uploads are retained and require
explicit inspection because a common binary prefix is not ownership proof.
The plan remains active on failure. Do not retry the upload or delete a partial
file automatically. Restore means exact path absent plus unchanged boot/CSI
baseline, not merely SSH disconnection. The original incident block is retained.

For a separately inspected nonempty partial upload, the manifest can record
`inspected_partial` with its exact size, SHA-256 and inspection reason. Cleanup
additionally requires that exact data equal the same-length prefix of the
reviewed binary and that the operation still be `uploading`; it is not a generic
prefix-based deletion rule. Operation `794b24803b6e` stopped while sending stdin,
before chmod or execution. Independent readback found exactly 24,576 bytes,
SHA-256 `5f4f3b3563e2e5f1ba7927c77296f3c24dcd8ba1924dadd65e9eaee575654938`,
matching that prefix, with no matching process and unchanged boot identity.
Its recovery is limited to `/tmp/ruview-nl-794b24803b6e` and the inspected hash.

The earlier preflight used read-only queries; subsequent socket-free test
`54eb642bed79` uploaded/executed/removed the exact owned helper successfully.
Both it and the interrupted upload `794b24803b6e` are restored, verified by
narrow rollback. No monitor was enabled and no persistent process/service was
installed. The paragraphs above govern the self-test plans. Retain old evidence;
do not treat earlier empty output as verified absence after the race discovery.
Before deploying the candidate, implement its exact temporary-file/process
ownership check here and in `scripts/rollback.py`, record its baseline in the
manifest, dry-check, and verify actual cleanup. Details: [AX58-READER.md](AX58-READER.md).

## Offline recovery and legacy import (2026-10-15)

Local code/tests/documentation only. Recovery and import use read-only source
snapshots and exclusively created output paths; no migration or in-place repair
is performed. Inputs with SQLite sidecars are refused without removing or
checkpointing them. Failed output files are retained for inspection rather than
deleted/reused. Recovery copies are explicitly incomplete, even when all copied
frames parse. Reverting this code must not remove user-created outputs/history.

No device connections, files/processes/settings, services or existing lab history
changed. `deployment.json` and `scripts/rollback.py` are unchanged and no remote
rollback check/apply ran. The user-requested local checkpoint is complete;
live integration still requires its own device baseline and rollback plan.

## Offline raw-pipeline prototype (2026-10-15)

New local modules/tests/documentation only; no remote operation was prepared or
applied. `deployment.json`, device files/processes/settings and operational
history are unchanged. The CLI requires new output paths and never migrates or
overwrites existing databases. Its synthetic tests use disposable local files.
No new remote rollback action is necessary or claimed. Journals and diagnostics
created by a later explicit local import must be retained; reverting the code
must not delete them. A live deployment still needs exact baseline/rollback
coverage before any device change; this prototype is not such authorization.

## Offline ADD/reader inspection (2026-10-14–15)

Only PC analysis outputs/helpers under ignored
`recordings/managed-contract-20261014/` and project documentation were added or
updated. Firmware inputs and existing recordings were read-only; no credentials
were read, dependencies installed or devices contacted. `deployment.json` and
`scripts/rollback.py` are unchanged. No remote rollback check/apply was run.
The new static AX58 guard concern does not clear or take ownership of any
existing operation. Retain the analysis evidence; no automatic cleanup is added.

## Offline source classification (2026-10-13)

The current stage only inspected public firmware/GPL files on the PC and
updated documentation. No device files, processes, monitor settings, services
or access keys changed. `scripts/rollback.py` and `deployment.json` therefore
remain unchanged; there is no new remote operation to undo. The existing
repeater operation is still recorded as restored with an unresolved operational
incident. Static exporter findings do not clear that safety gate.

Local additions are the optional venv dependencies in `requirements-research.txt`
and retained evidence/helpers under ignored
`recordings/source-classification-20261013/`. Device rollback does not uninstall
PC packages or delete this evidence. No exact pre-install venv snapshot was
recorded, so an automatic package removal would not be a verified restoration.
Keep the artifacts for reproduction and do not remove shared dependencies
merely because they appear in the research requirements.

The planned raw forwarder and separate Pi storage/processing workers are not
implemented or deployed and are **not covered by the existing rollback plan**.
Before any such deployment, record exact original files, hashes/modes, owned
processes and monitor/service state; extend the rollback implementation and
manifest for that concrete operation, verify the plan before applying changes,
and verify restoration afterward. Preserve raw records and later history.
See [RECORDING.md](RECORDING.md#off-router-processing-boundary-for-the-next-implementation).

Local review validation: `.venv/Scripts/python.exe -m unittest discover -s tests
-p TEST_FILE -q` passed for `test_repeater_probe.py` (9 tests),
`test_capture_rollback.py` (4), and `test_panel_deployment.py` (5).
`git diff --check` passed. These use local fixtures; no remote `--check` or
`--apply` was run, and current device state was not verified.

## Bounded repeater probes (October 5, 2026)

**Incident: capture is now disabled in code for both repeaters.** Operation
`99256b673931` coincided with a confirmed RP-AX58 reboot. The capture command
fails before connection/upload; inspection and narrow rollback remain available.
The details below record the historical attempted scope, not instructions to
repeat it. Do not run `--prepare` or `--capture` while the incident is unresolved.
See `EXPERIMENTS.md` for evidence and remaining uncertainty.
New preparation also stops before connecting while an unresolved incident exists
in the manifest. A plan marked restored requires an idle monitor on subsequent
checks/apply; it cannot take ownership of later monitoring, even with the same peer.

`scripts/repeater_probe.py --prepare ax58` (or `ax56`) records the initial
disabled monitor, empty peer list, associated upstream peer, processes and Netlink
listeners in ignored `deployment.json.repeater_probes`. `--interface eth2` selects
the other radio; default is `eth1`. Preparation makes no remote changes.
Before the incident, the historical sequence was `--prepare`, rollback `--check`,
then `--capture`. Capture is now disabled; do not repeat that sequence.

The historical attempt uploaded the locally retained GT-AX11000 `csimond.bin` to
one temporary `/tmp/ruview-csimond-OPERATION_ID` path. It was stock for the main
router but had not been verified for the repeater. No `csimond` package or service
was installed persistently. The file was absent after AX58 reboot; no current
repeater-side collector file needs removal. The built-in CSIMON kernel component
is part of the firmware and was not installed by the probe. The attempted
collector used Netlink 23 while a single upstream peer was monitored at 500 ms
for eight seconds. The initial record left the cause unknown. On October 13,
the user confirmed the CSI/DHD watchdog cause from their binary analysis;
that finding is attributed to the user in REPEATER-CSI-RESEARCH.md. The full
supporting binary evidence has not been independently reviewed here, and a safe
replacement acquisition method remains unvalidated. This does not clear the
manifest's operational incident block.

The intended shell cleanup would disable the monitor, delete its peer and stop
the exact child process. Because the node rebooted and the SSH stream timed out,
completion of those traps was not verified. No NVRAM, access keys, firmware,
services, channel settings or Pi files were modified. Device counters and login
logs are observations and are not erased.

For operation `99256b673931`, read-only inspection after reboot found the exact
temporary path absent, monitors disabled, peer lists empty and no collector.
The manifest records `restored` for that verified configuration and separately
an unresolved reboot incident. This does **not** mean the shell trap completed
or the probe was safe/successful. Raw capture output is empty; diagnostic
snapshots and saved device logs are in ignored
`recordings/repeater-inspection-20261005/`. No rollback deletion was necessary.

The historical capture procedure was intended to check restoration and delete
only the temporary file matching its recorded checksum. Its output destination
was ignored `recordings/repeater-OPERATION_ID/capture.txt`; during the incident
that file remained empty. This did not guarantee delivery of diagnostics or
complete kernel payloads. Capture is now disabled. There is no automatic
raw-record deletion. Log retention remains pending the user's choice.

For interruption recovery, wait for the bounded shell to finish, then run
`python scripts/rollback.py --repeater-only --check`, followed by `--apply`.
This scope uses only the latest recorded repeater operation. It refuses an active
collector, unknown peer configuration, unexplained enabled monitor, or modified
temporary file. A failed or partial upload requires inspection rather than blind
deletion. SSH loss or a hung device can prevent trap verification; report that
condition and reconnect before claiming restoration. All earlier history remains.

### Local diagnostic repair and read-only plan (2026-10-13)

Only PC files changed. `scripts/ssh_diagnostics.py` now supplies incremental
stdout/stderr journaling to the existing repeater `run()` and `remote_file()`
helpers. It neither adds an acquisition command nor changes rollback ownership
rules. The existing `--capture` and unresolved-incident `--prepare` blocks remain.
No remote rollback was applied or checked in this task, and `deployment.json`
was not changed. The optional read-only inventory plan in
`REPEATER-CSI-RESEARCH.md` needs no remote files/processes/settings restored and
must not automatically invoke the broader repeater rollback.

Each diagnostic command creates a unique directory under ignored
`recordings/repeater-diagnostics/` on the PC, containing `stdout.bin`,
`stderr.bin`, and `events.jsonl`. Raw streams are private evidence; do not pass
credentials or secret-bearing commands to this helper. The journal records the
reviewed command, UTC start, elapsed receive events, byte counts, exit status
or incomplete outcome. Data are flushed and synced after each chunk. A missing
final event means completion is unknown (for example after local interruption).
Neither separate stream arrival order nor PC timestamps reconstruct device
execution order or acquisition time.

Default bounds are 10 seconds and 4 MiB combined output, with a 100,000-byte
bound for inspecting the manifest-listed temporary file. The optional inventory
plan uses a tighter 256 KiB cap. Both streams are drained, including queued
data on disconnect; missing exec acknowledgement and missing exit status fail
explicitly. A nonzero remote status is recorded and rejected by `run()`.
There is no automatic reconnect, retry, process kill or device recovery. A local
disk failure prevents a success claim but can prevent the final journal marker
from being written. Closing a channel does not verify remote termination.
The helper requires a dedicated SSH client. If channel close stalls (including
rekey), it closes that client's transport locally instead of waiting indefinitely
to send the close packet. Dispatch/read budgets and bounded cleanup waits are
not hard real-time guarantees for local disk I/O or thread scheduling.

Read the journal locally with `Get-Content PATH/events.jsonl`; inspect raw
streams only when required. Existing incident evidence and these bounded files
are not automatically deleted. The project-wide several-week diagnostic-log
retention duration remains awaiting the user's exact choice; this repair adds
no cleaner or permanent logger and makes no retention-policy decision. Do not
delete CSI records or incident evidence as a side effect of future log cleanup.

## Panel update (2026-10-04)

The panel and an enabled `ruview-lab-panel.service` were discovered already
running on the Pi. The update preserves that service configuration and all
recordings. It does not remove the earlier bootstrap installation.

Use the narrow panel rollback, not the original whole-lab rollback:

```powershell
python scripts/rollback.py --panel-only --check
python scripts/rollback.py --panel-only --apply
```

`scripts/deploy_panel.py --prepare` records the exact target paths, original
bytes/modes/hashes, replacement hashes, service unit hash/enablement/active state,
SQLite counts/integrity and a raw-record digest in `deployment.json.panel_updates`.
Backups live in ignored `recordings/panel-deploy-OPERATION_ID/`. Keep both the
manifest and these local backups; do not commit them. Preparation changes no
remote files. Run the rollback check before applying the prepared deployment.

Files relative to `/home/pi/ruview-lab` include the panel modules, workspace
assets, browser API documentation, locally bundled Swagger UI assets and license,
map source, and OpenAPI contract. Uploads use tracked sibling `.panel-upload`
files and atomic rename. Only the known service is stopped/restarted. The service unit,
enablement, collector, router credentials, maps, and router settings are unchanged.

Rollback checks every target and backup before any modification. It rejects
unrecognized content, changed service settings, simultaneous captures and
unowned panel processes. It restores replaced files with original permissions
and removes only the new manifest-listed files with matching hashes. It supports
a mix of original and fully uploaded files after an interrupted deployment.
An unknown or partially uploaded staging file requires inspection; it is not
silently deleted. Errors stop the operation with a traceback. If an update
fails after stopping the service, inspect with `--panel-only --check` and then
apply the narrow rollback; do not blindly restart mixed files.

The database recovery copy is taken after stopping the panel. Automatic rollback
never restores this copy: it preserves any subsequently added points, routes,
labels and raw recordings. The restored bootstrap can read the unchanged schema,
but may display v2 provenance envelopes as plain notes. Source/device hashes are
references, not a historical geometry archive. Python bytecode caches may remain
as harmless generated artifacts; no recursive cleanup is performed.

### Swagger UI API reference update (2026-10-05)

Operation `20261005T180439Z-f02d7e` deployed 17 panel, documentation and
Swagger UI files. The only service action was a stop/start of the existing
`ruview-lab-panel.service`; database schema, rows, raw CSI, service settings,
and router state were preserved. Rollback inspection passed before and after
deployment. Original files and the history recovery copy are under the ignored
`recordings/panel-deploy-20261005T180439Z-f02d7e/` directory; exact hashes and
service/database baselines are in ignored `deployment.json.panel_updates`.

The embedded workspace iterations are operations `20261005T182058Z-b87df7`,
`20261005T182459Z-1ea6df`, `20261005T183004Z-5260ff`, and
`20261005T183337Z-e75028`. Each prepared an exact backup for the same 17 panel
files, passed the panel rollback check before apply, stopped/restarted only the existing panel
service, and passed the check again after apply. The theme operation adds dark
mode overrides; a later operation corrects OpenAPI response codes/schemas and
the last preserves Swagger's direct operation links inside the workspace. The
latest exact
baseline, file hashes, service state and database/raw-history comparison are in
`deployment.json`; the latest backup is in the ignored
`recordings/panel-deploy-20261005T183337Z-e75028/` directory. To restore the
previous panel files while preserving later session data, run:

```powershell
python scripts/rollback.py --panel-only --check
python scripts/rollback.py --panel-only --apply
python scripts/rollback.py --panel-only --check
```

No capture was active during deployment, and no capture, API write, or router /
repeater operation was used for browser verification. Rollback refuses if a
capture is active or paused; stop it through the panel before attempting file
restoration.

An initial operation, `20261005T180209Z-d4259d`, was rolled back after SFTP
reported that the nested remote `web/swagger-ui/` directory did not exist.
That exact rollback passed and restarted the original service before a corrected
flat-file deployment was prepared. Its backups remain under
`recordings/panel-deploy-20261005T180209Z-d4259d/` for audit/recovery.

The old full-lab command is not a panel-uninstall command and refuses Pi file
removal while the panel is running. The historical notes below describe the
earlier collector-only installation; their "no service" statement predates the
discovered bootstrap. See [PANEL.md](PANEL.md) for operation and limitations.

## Earlier collector-only rollback

The direct-PC live viewer (`scripts/live_motion.py`) installs no remote files
and does not change persistent settings. Its temporary CSI peer and owned
collector are cleaned up on Stop or bounded completion, followed by a read-only
state check. Before using rollback, stop the viewer and wait for completion.
If cleanup is unverified, use `--check`; do not force-stop an unidentified
csimond process. See [LIVE-MOTION.md](LIVE-MOTION.md) for logs and lifecycle details.

From PowerShell on this computer:

```powershell
python C:\Users\Nikolay\Downloads\ruview-lab\scripts\rollback.py --check
python C:\Users\Nikolay\Downloads\ruview-lab\scripts\rollback.py --apply
```

The first command only checks. The second rolls back the changes listed below.
The ASUS password is entered at a hidden prompt. The Pi uses the generated SSH key;
after that key is removed, a subsequent run will require the Pi password. Passwords
are not stored in files. Python with paramiko must be installed (already available on this PC).

## Recorded changes (historical collector-only baseline)

These entries describe the earlier installation, not a fresh device inventory.
Later panel/repeater operations and their rollback scopes are documented above
and below; the manifest defines the exact recorded operation.

* ASUS 192.168.50.1: csimon was temporarily enabled on eth6 for
  A0:36:BC:9B:BF:89 at a 500 ms interval. Before the test, the monitor was disabled and the list was empty.
  That state has already been restored after the test. Only
  /tmp/ruview-csi-probe.txt remains. The script removes this file and checks the state.
* Pi 192.168.50.100: the ruview_pi_lab key was added to pi/.ssh/authorized_keys;
  permissions were set to 700 for .ssh and 600 for authorized_keys. The script removes only
  the added key, preserving other entries and password access.
* Repeaters and TP-Link: no changes were made.
* Collector: files in /home/pi/ruview-lab on the Pi (decoder.py, recorder.py,
  router_key, router_key.pub, router_known_hosts) and a dedicated public key,
  ruview-pi-collector, in /root/.ssh/authorized_keys on the ASUS. The original ASUS
  key file was empty, with permissions 700; the change log is deployment.json.
  Rollback removes only our key and files with matching hashes.
  The history.sqlite3 database, logs, and directory are retained to preserve history.
  There are no services or autostart. Run rollback after the current capture finishes.
* PC: research files in Downloads/ruview-lab and dedicated keys
  .ssh/ruview_pi_lab, .pub, ruview_known_hosts. These are retained for auditing.

## Recovery limits

A complete byte-for-byte snapshot was not taken before work began. The original permissions
and existence of authorized_keys were not recorded; the script leaves the file with secure permissions.
The counter of 16 measurements, system logs, and SSH connection history are not erased.
This rolls back the functional changes made; it does not restore a disk image.
The script refuses to modify an unfamiliar CSI configuration or stop a new
csimond process. A failure on one device does not prevent a rollback attempt on the other.

Before subsequent changes, record the initial state and add a rollback action
and a result check to this toolkit. The current version
covers only the changes already listed; it is not a universal
rollback for any future installations.

## Capture UI update (2026-10-05)

Use the same `--panel-only --check` / `--panel-only --apply` operations for this
update. The latest manifest entry and its local backups define the exact prior
files, modes, service state and database digest. No schema migration is required.
Preflight now also rejects an active or paused panel capture reported by health,
not just a separate recorder process. Stop recording before deployment/rollback.
Rollback preserves later recordings and does not undo explicit session deletion.

Verified operation: `20261005T102745Z-8897cc`; backups are in
`recordings/panel-deploy-20261005T102745Z-8897cc/`. A subsequent 30-second UI
verification session is retained. Its router before/after inspection is saved
under `verification_capture` in the same ignored manifest entry: monitor disabled,
empty peer list and no collector process after bounded completion. No permanent
router setting or new service was introduced by verification.

### Incremental live refresh follow-up

The live refresh update uses the same ten-file manifest preparation and narrow
panel rollback. The new cache is process memory only (600 points); database schema,
raw history and service configuration are unchanged. Stop an active capture before
rollback. Restoring the previous files removes the incremental endpoint and returns
to the previous client polling behavior; no data migration or cleanup is required.

Verified live-update operation: `20261005T104835Z-2915cd`, backups in
`recordings/panel-deploy-20261005T104835Z-2915cd/`. Both rollback checks passed.
The manifest records before/after router inspections for the two retained live
verification captures. These captures are not removed by panel-file rollback.

## Capture repair, October 6, 2026

The file update uses the existing `--panel-only` prepare/check/apply workflow;
only manifest-listed panel files and the existing service restart are involved.
History and service configuration are preserved. The capture receiver remains
GT-AX11000 eth6; the fixed peer is updated from the disconnected AX58 2.4 GHz
radio to the associated AX56 2.4 GHz radio, without a repeater collector.

Before verification captures, `deployment.json.panel_capture_verification`
records the router/interface/peer, idle baseline, temporary `csimond 23 64`
process and shell-owned sleeper, monitor add/enable and EXIT-trap disable/delete,
plus each session ID. No router file or persistent setting is changed.
`python scripts/rollback.py --capture-only --check` verifies no active panel
capture, disabled eth6 monitor, empty peer list and no csimond. The narrow
`--capture-only --apply` recovery refuses unknown peers or any running collector;
use it only for a recorded operation marked as requiring recovery. It never
removes keys, history, services or unrelated files. Panel-file rollback also
restores the former peer configuration, which may still be unavailable.
