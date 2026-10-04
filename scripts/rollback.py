"""Undo changes made by this experiment. Default: read-only inspection.

Usage: python rollback.py --check
       python rollback.py --apply
Requires paramiko. Router password is prompted, never stored.
"""
import argparse
import base64
import getpass
import hashlib
import json
import logging
import re
import shlex
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent
SSH = Path.home() / '.ssh'
PEER = 'A0:36:BC:9B:BF:89'
PROBE = '/tmp/ruview-csi-probe.txt'


def manifest():
    path = ROOT / 'deployment.json'
    return json.loads(path.read_text()) if path.exists() else {}


def remove_lab_key(content, key_blob):
    """Remove only lines containing our exact public key, preserving others."""
    return b''.join(line for line in content.splitlines(keepends=True)
                    if key_blob not in line.split())


def run(client, command):
    _, out, err = client.exec_command(command, timeout=15)
    value = out.read().decode(errors='replace')
    error = err.read().decode(errors='replace')
    code = out.channel.recv_exit_status()
    if code or error.strip():
        raise RuntimeError(f'{command}: exit={code}, {error.strip()}')
    return value


def connect(host, user, known_hosts, key=None):
    client = paramiko.SSHClient()
    client.load_host_keys(str(known_hosts))
    # Unknown or changed host keys are rejected.
    options = dict(hostname=host, username=user, timeout=12,
                   auth_timeout=15, allow_agent=False, look_for_keys=False)
    if key and key.exists():
        try:
            client.connect(**options, key_filename=str(key))
            return client
        except paramiko.AuthenticationException:
            client.close()
            client = paramiko.SSHClient()
            client.load_host_keys(str(known_hosts))
    client.connect(**options, password=getpass.getpass(f'Password for {user}@{host}: '))
    return client


def router(apply):
    c = connect('192.168.50.1', 'admin', ROOT / 'router_known_hosts')
    try:
        state = run(c, 'wl -i eth6 csimon state')
        peers = run(c, 'wl -i eth6 csimon')
        print('ASUS:', state.strip())
        # Do not overwrite monitoring configured later by someone else.
        addresses = set(re.findall(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', peers.upper()))
        if addresses - {PEER}:
            raise RuntimeError('Unrecognized CSI peers; refusing to alter this configuration.')
        if peers.strip() and not addresses:
            raise RuntimeError('Unrecognized CSI peer-list format; manual inspection required.')
        enabled = re.search(r'Enabled:\s*([01])\b', state)
        if not enabled:
            raise RuntimeError('Unrecognized CSI state; refusing changes.')
        # The bounded collector was already stopped and verified in the probe.
        # Never kill a new process just because it has the same executable name.
        processes = run(c, 'ps')
        if any('csimond' in line for line in processes.splitlines()):
            raise RuntimeError('A csimond process is running; its ownership must be checked first.')
        exists = run(c, f'if [ -f {PROBE} ]; then echo present; fi').strip()
        print('ASUS probe file:', exists or 'absent')
        deployed = manifest()
        if deployed:
            original = run(c, 'cat /root/.ssh/authorized_keys').encode()
            cleaned = remove_lab_key(original, deployed['router_key_blob'].encode())
            print('ASUS: Pi collector key', 'present' if original != cleaned else 'absent')
            if apply and original != cleaned:
                if run(c, 'cat /root/.ssh/authorized_keys').encode() != original:
                    raise RuntimeError('Router authorized_keys changed; retry rollback.')
                run(c, "printf '%s' "+shlex.quote(cleaned.decode())+" > /root/.ssh/authorized_keys")
                if run(c, 'cat /root/.ssh/authorized_keys').encode() != cleaned:
                    raise RuntimeError('Router key rollback verification failed.')
        if apply:
            if enabled.group(1) == '1':
                run(c, 'wl -i eth6 csimon disable')
            if PEER in addresses:
                run(c, f'wl -i eth6 csimon del {PEER}')
            if exists:
                run(c, f'rm -f {PROBE}')
            final = run(c, 'wl -i eth6 csimon state')
            if not re.search(r'Enabled:\s*0\b', final) or run(c, 'wl -i eth6 csimon').strip():
                raise RuntimeError('ASUS rollback verification failed.')
            print('ASUS: monitoring disabled, temporary peer/file removed.')
    finally:
        c.close()


def pi(apply):
    key = SSH / 'ruview_pi_lab'
    pub = (SSH / 'ruview_pi_lab.pub').read_bytes().split()[1]
    c = connect('192.168.50.100', 'pi', SSH / 'ruview_known_hosts', key)
    try:
        s = c.open_sftp()
        try:
            deployed = manifest()
            if deployed:
                processes = run(c, 'ps -eo args')
                if re.search(r'^.*python3 /home/pi/ruview-lab/web_panel.py', processes, re.M):
                    raise RuntimeError('Panel is using collector files. Use --panel-only for panel updates; full lab removal requires a separate service-removal plan.')
                if re.search(r'^python3 /home/pi/ruview-lab/recorder.py capture', processes, re.M):
                    raise RuntimeError('Bounded capture is active; wait up to 60 seconds and retry.')
                for item in deployed['pi_files']:
                    path = item['path']
                    if not path.startswith('/home/pi/ruview-lab/') or '..' in path.split('/'):
                        raise RuntimeError('Unexpected deployment path')
                    try:
                        with s.open(path,'rb') as f:
                            content = f.read()
                    except FileNotFoundError:
                        continue
                    if hashlib.sha256(content).hexdigest() != item['sha256']:
                        raise RuntimeError(f'{path} changed since deployment; refusing deletion.')
                    print('Pi experiment file:',path)
                    if apply:
                        s.remove(path)
                print('Pi: recording database and logs are retained, no service was installed.')
            try:
                with s.open('.ssh/authorized_keys', 'rb') as f:
                    original = f.read()
            except FileNotFoundError:
                print('Pi: authorized_keys absent; nothing to remove.')
                return
            cleaned = remove_lab_key(original, pub)
            print('Pi: experiment key', 'present' if cleaned != original else 'absent')
            if apply and cleaned != original:
                # Preserve concurrent edits instead of replacing someone else's update.
                with s.open('.ssh/authorized_keys', 'rb') as f:
                    if f.read() != original:
                        raise RuntimeError('authorized_keys changed during rollback; retry.')
                with s.open('.ssh/authorized_keys', 'wb') as f:
                    f.write(cleaned)
                with s.open('.ssh/authorized_keys', 'rb') as f:
                    if f.read() != cleaned:
                        raise RuntimeError('Pi key-removal verification failed.')
                print('Pi: only the experiment key removed; password login unchanged.')
        finally:
            s.close()
    finally:
        c.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--apply', action='store_true')
    parser.add_argument('--panel-only', action='store_true',
                        help='Restore the last panel update; preserve router access and all history')
    args = parser.parse_args()
    if args.panel_only:
        from deploy_panel import rollback_panel
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
        rollback_panel(args.apply)
        return
    print('APPLY rollback' if args.apply else 'READ-ONLY rollback inspection')
    failures = []
    for name, action in [('ASUS', router), ('Pi', pi)]:
        try:
            action(args.apply)
        except Exception as exc:
            failures.append(name)
            print(f'{name}: FAILED: {exc}')
    print('Local keys and research files are retained. No firmware/factory reset is performed.')
    if failures:
        raise SystemExit(1)
    print('Rollback completed.' if args.apply else 'Inspection passed; no changes made.')


if __name__ == '__main__':
    main()
