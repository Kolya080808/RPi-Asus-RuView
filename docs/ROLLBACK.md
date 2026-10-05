# Experiment rollback

## Panel update (2026-10-04)

The panel and an enabled `ruview-lab-panel.service` were discovered already
running on the Pi. The update preserves that service configuration and all
recordings. It does not remove the earlier bootstrap installation.

Use the narrow panel rollback, not the original whole-lab rollback:

```powershell
python scripts/rollback.py --panel-only --check
python scripts/rollback.py --panel-only --apply
```

`scripts/deploy_panel.py --prepare` records the ten exact target paths, original
bytes/modes/hashes, replacement hashes, service unit hash/enablement/active state,
SQLite counts/integrity and a raw-record digest in `deployment.json.panel_updates`.
Backups live in ignored `recordings/panel-deploy-OPERATION_ID/`. Keep both the
manifest and these local backups; do not commit them. Preparation changes no
remote files. Run the rollback check before applying the prepared deployment.

Files relative to `/home/pi/ruview-lab`: `web_panel.py`, `panel_signal.py`,
`live_signal.py`, `decoder.py`, `web/index.html`, `web/app.css`,
`web/theme.css`, `web/app.js`, `maps/home/floorplan.json`, `docs/API.openapi.json`. Uploads use tracked sibling `.panel-upload` files and
atomic rename. Only the known service is stopped/restarted. The service unit,
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
