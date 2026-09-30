# Experiment rollback

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
