# Experiment rollback

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
for eight seconds. Whether the collector, monitor, their interaction or another
event caused the reboot is unknown.

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

After the bounded run, the tool checks restoration and deletes only the temporary
file matching its recorded checksum. Full available terminal output is kept locally
in ignored `recordings/repeater-OPERATION_ID/capture.txt`; this preserves the stock
utility's printed output, not a guarantee of complete kernel payloads. There is
no automatic raw-record deletion. Log retention remains pending the user's choice.

For interruption recovery, wait for the bounded shell to finish, then run
`python scripts/rollback.py --repeater-only --check`, followed by `--apply`.
This scope uses only the latest recorded repeater operation. It refuses an active
collector, unknown peer configuration, unexplained enabled monitor, or modified
temporary file. A failed or partial upload requires inspection rather than blind
deletion. SSH loss or a hung device can prevent trap verification; report that
condition and reconnect before claiming restoration. All earlier history remains.

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

## Recorded changes

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
