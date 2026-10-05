"""Repeater inspection/rollback; capture disabled after the October 5 reboot incident."""
import argparse
import base64
import datetime as dt
import hashlib
import json
import logging
from pathlib import Path
import re
import shlex
import uuid

import paramiko

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger('ruview.repeater')
TARGETS = {
    'ax58': ('192.168.50.136', 'RP-AX58', 'H7QJxf8Mk1QZV9OtMcWauDnvD0TSd5pyC3aVBVdY6ck'),
    'ax56': ('192.168.50.156', 'RP-AX56', 'An/5Vi554F18ohxFv6UtYNJfk8LZe7Owuotn6c08kKM'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def connect(target):
    host, model, fingerprint = TARGETS[target]
    class Pin(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            actual = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
            if hostname != host or actual != fingerprint:
                raise RuntimeError('Repeater host fingerprint changed')
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(Pin())
    credentials = json.loads((ROOT / '.secrets/local-credentials.json').read_text())['asus_main']
    try:
        c.connect(host, username=credentials['username'], password=credentials['password'],
                  look_for_keys=False, allow_agent=False, timeout=8, auth_timeout=8)
        if run(c, 'nvram get productid').strip() != model:
            raise RuntimeError('Unexpected device model')
        return c
    except BaseException:
        c.close()
        raise


def run(c, command):
    _, out, err = c.exec_command(command, timeout=10)
    value, error = out.read(), err.read()
    if out.channel.recv_exit_status():
        raise RuntimeError(f'Remote diagnostic failed: {command}: {error.decode(errors="replace")[:300]}')
    return value.decode(errors='replace')


def inspect(c, interface):
    return {'state': run(c, f'wl -i {interface} csimon state'),
            'peers': run(c, f'wl -i {interface} csimon'),
            'associated': run(c, f'wl -i {interface} assoclist'),
            'processes': run(c, 'ps'),
            'netlink': run(c, 'cat /proc/net/netlink')}


def idle(state):
    if not re.search(r'Enabled:\s*0\b', state['state']) or state['peers'].strip():
        raise RuntimeError('Monitor must be disabled with an empty peer list')
    if 'csimond' in state['processes']:
        raise RuntimeError('An existing collector is running; ownership must be inspected')
    for row in state['netlink'].splitlines()[1:]:
        fields = row.split()
        if len(fields) > 2 and fields[1] == '23' and fields[2] != '0':
            raise RuntimeError('An existing userspace Netlink 23 listener is present')


def save_manifest(data):
    p = ROOT / 'deployment.json'
    pending = p.with_suffix('.json.tmp')
    pending.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    pending.replace(p)


def validate(plan):
    if plan['target'] not in TARGETS or plan['interface'] not in ('eth1', 'eth2'):
        raise ValueError('Unexpected target or interface')
    if not re.fullmatch(r'[0-9a-f]{12}', plan['id']):
        raise ValueError('Unexpected operation ID')
    if plan['path'] != '/tmp/ruview-csimond-' + plan['id']:
        raise ValueError('Unexpected remote path')
    if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', plan['peer']):
        raise ValueError('Unexpected peer')
    if plan['seconds'] != 8 or plan['interval_ms'] != 500:
        raise ValueError('Unexpected probe bounds')
    idle(plan['before'])
    if digest((ROOT / 'csimond.bin').read_bytes()) != plan['sha256']:
        raise ValueError('Local stock collector changed')


def remote_file(c, path):
    quoted = shlex.quote(path)
    command = f'if [ -L {quoted} ]; then exit 2; fi; if [ -e {quoted} ]; then [ -f {quoted} ] || exit 2; cat {quoted}; fi'
    _, out, err = c.exec_command(command, timeout=10)
    data = out.read(100000)
    error = err.read()
    if out.channel.recv_exit_status() or error:
        raise RuntimeError('Cannot inspect temporary file')
    return data


def check(c, plan, apply=False):
    validate(plan)
    state = inspect(c, plan['interface'])
    # A completed operation does not own any monitor subsequently enabled there.
    if plan.get('status') == 'restored':
        idle(state)
    if 'csimond' in state['processes']:
        raise RuntimeError('Collector still running; wait for bounded exit, do not kill unknown processes')
    peers = state['peers'].strip()
    addresses = set(re.findall(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', peers.upper()))
    if addresses - {plan['peer']} or (peers and not addresses):
        raise RuntimeError('Unexpected CSI peer configuration; refusing rollback')
    enabled = re.search(r'Enabled:\s*([01])\b', state['state'])
    if not enabled or (enabled[1] == '1' and addresses != {plan['peer']}):
        raise RuntimeError('Unowned or unknown monitor state; refusing rollback')
    data = remote_file(c, plan['path'])
    if data and digest(data) != plan['sha256']:
        raise RuntimeError('Temporary file differs from manifest; refusing deletion')
    if apply:
        if enabled[1] == '1':
            run(c, f"wl -i {plan['interface']} csimon disable")
        if plan['peer'] in addresses:
            run(c, f"wl -i {plan['interface']} csimon del {plan['peer']}")
        if data:
            run(c, 'rm ' + shlex.quote(plan['path']))
        state = inspect(c, plan['interface'])
        idle(state)
        if run(c, f"if [ -e {shlex.quote(plan['path'])} ]; then echo present; fi").strip():
            raise RuntimeError('Temporary file remains')
    return state


def rollback_repeater(apply=False):
    manifest = json.loads((ROOT / 'deployment.json').read_text())
    plan = manifest['repeater_probes'][-1]
    validate(plan)
    c = connect(plan['target'])
    try:
        after = check(c, plan, apply)
        if apply:
            plan['after'] = after
            plan['status'] = 'restored'
            save_manifest(manifest)
        LOG.info('operation=%s target=%s rollback_%s passed', plan['id'], plan['target'], 'apply' if apply else 'check')
    finally:
        c.close()


def prepare(target, interface):
    manifest = json.loads((ROOT / 'deployment.json').read_text())
    if any(p.get('incident', {}).get('resolved') is False
           for p in manifest.get('repeater_probes', [])):
        raise RuntimeError('Unresolved repeater incident; new preparation is blocked')
    if any(p['status'] != 'restored' for p in manifest.get('repeater_probes', [])):
        raise RuntimeError('Resolve previous repeater probe before preparing another')
    c = connect(target)
    try:
        before = inspect(c, interface)
        idle(before)
        peers = re.findall(r'^assoclist ((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s*$', before['associated'], re.M)
        if len(peers) != 1:
            raise RuntimeError('Expected one associated upstream peer; inspect before selecting')
        identifier = uuid.uuid4().hex[:12]
        plan = {'id': identifier, 'target': target, 'interface': interface,
                'path': '/tmp/ruview-csimond-' + identifier, 'peer': peers[0].upper(),
                'seconds': 8, 'interval_ms': 500, 'sha256': digest((ROOT / 'csimond.bin').read_bytes()),
                'before': before, 'status': 'prepared', 'prepared_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
        if run(c, f"if [ -e {plan['path']} ]; then echo present; fi").strip():
            raise RuntimeError('Temporary path already exists')
        validate(plan)
        manifest.setdefault('repeater_probes', []).append(plan)
        save_manifest(manifest)
        LOG.info('Prepared operation=%s target=%s interface=%s; no remote changes', identifier, target, interface)
    finally:
        c.close()


def capture():
    """Fail closed after a device reboot; preserve inspection and rollback only."""
    raise RuntimeError(
        'Repeater capture disabled after RP-AX58 reboot during operation '
        '99256b673931. Investigate saved incident evidence before designing '
        'any new device experiment; this command will not upload or run a collector.'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', choices=TARGETS)
    parser.add_argument('--interface', choices=['eth1', 'eth2'], default='eth1')
    parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    if bool(args.prepare) == args.capture:
        parser.error('Choose --prepare TARGET or --capture')
    try:
        prepare(args.prepare, args.interface) if args.prepare else capture()
    except Exception:
        LOG.exception('Repeater operation failed; inspect the manifest and use narrow rollback')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
