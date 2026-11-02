"""One explicitly risk-accepted AX58 AP/Pi trial; exact-file rollback, no retries."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shlex

import reader_probe as reader

ROOT = reader.ROOT
BUILD = ROOT / 'recordings/ax58-active-build-20261101'
PEER = '88:A2:9E:94:7D:80'
MODULE = 'dabb2f7e716d63f4ffa9163773b7f87c15050cb442d021db528194f0b25e68a8'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate(plan):
    ident = plan.get('id', '')
    if (not re.fullmatch('[0-9a-f]{12}', ident) or plan.get('target') != 'ax58'
            or plan.get('interface') != 'wl0.1' or plan.get('peer') != PEER
            or plan.get('protocol') != 23 or plan.get('seconds') != 5
            or plan.get('interval_ms') != 500
            or set(plan.get('files', {})) != {'reader', 'supervisor'}):
        raise ValueError('Unrecognized active operation')
    for name, item in plan['files'].items():
        if (item['path'] != '/tmp/ruview-active-' + ident + '-' + name
                or item.get('before') != 'absent'
                or sha((BUILD / name).read_bytes()) != item['sha256']):
            raise ValueError('Active file scope/build mismatch')


def cmd(client, command):
    out, err, _ = reader.command(client, command)
    if err:
        raise RuntimeError('Unexpected diagnostic stderr; inspect retained evidence')
    return out.decode().strip()


def ready(client):
    if cmd(client, 'wl -i wl0.1 ap') != '1' or cmd(client, 'wl -i wl0.1 bss') != 'up':
        raise RuntimeError('Selected virtual AP is not up')
    if not re.search(r'Enabled:\s*0\b', cmd(client, 'wl -i wl0.1 csimon state')) or cmd(client, 'wl -i wl0.1 csimon'):
        raise RuntimeError('Virtual AP CSI state is not disabled/empty')
    peers = cmd(client, 'wl -i wl0.1 assoclist')
    if peers.upper().split() != ['ASSOCLIST', PEER]:
        raise RuntimeError('Expected only the identified Pi on the AP')
    station = cmd(client, 'wl -i wl0.1 sta_info ' + PEER)
    if not all(word in station for word in ('AUTHENTICATED', 'ASSOCIATED', 'AUTHORIZED')):
        raise RuntimeError('Pi station is not ready')
    if cmd(client, 'nvram get wl0_ifname') != 'eth1':
        raise RuntimeError('Radio mapping changed')
    module = cmd(client, 'busybox sha256sum /lib/modules/4.19.183/extra/wl.ko')
    if module.split()[0] != MODULE:
        raise RuntimeError('Driver build changed')


def check(client, plan, apply=False):
    validate(plan)
    # No monitor mutation in rollback: supervisor owns disable/delete. A reboot,
    # unknown monitor state or remaining task requires inspection, never retries.
    current = reader.baseline(client)
    if current['boot_id'] != plan['before']['boot_id']:
        raise RuntimeError('AX58 rebooted; stop for inspection')
    for name, item in plan['files'].items():
        reader.processes(client, item['path'])
        path = shlex.quote(item['path'])
        exists = cmd(client, f'if [ -e {path} ] || [ -L {path} ]; then echo present; else echo absent; fi')
        if exists not in {'present', 'absent'}:
            raise RuntimeError('Unknown file state')
        if exists == 'absent':
            continue
        if plan['status'] in {'prepared', 'restored'}:
            raise RuntimeError('Unexpected existing file')
        data = reader.remote_file(client, item['path'])
        if data != (BUILD / name).read_bytes():
            raise RuntimeError('Unowned/partial file retained')
        if apply:
            reader.processes(client, item['path'])
            if reader.remote_file(client, item['path']) != data:
                raise RuntimeError('File changed before removal')
            cmd(client, 'rm -f ' + path)
    if apply:
        check(client, dict(plan, status='restored'))
    return current


def prepare():
    import uuid
    manifest = reader.load()
    if any(p['status'] != 'restored' for p in manifest.get('active_reader_checks', [])):
        raise RuntimeError('Prior active operation needs inspection')
    ident = uuid.uuid4().hex[:12]
    plan = dict(id=ident, target='ax58', interface='wl0.1', peer=PEER,
                protocol=23, seconds=5, interval_ms=500, status='prepared',
                files={name:dict(path='/tmp/ruview-active-'+ident+'-'+name,
                                sha256=sha((BUILD/name).read_bytes()), before='absent')
                       for name in ('reader', 'supervisor')})
    client = reader.connect('ax58')
    try:
        plan['before'] = reader.baseline(client)
        ready(client)
        check(client, plan)
        manifest.setdefault('active_reader_checks', []).append(plan)
        reader.save_manifest(manifest)
    finally:
        client.close()
    print('Prepared active operation', ident)


def rollback(apply=False):
    manifest = reader.load()
    plan = manifest['active_reader_checks'][-1]
    client = reader.connect('ax58')
    try:
        plan['after_check'] = check(client, plan, apply)
        if apply:
            plan['status'] = 'restored'
        plan['rollback_checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        reader.save_manifest(manifest)
    finally:
        client.close()
    print('Active rollback', 'applied' if apply else 'checked', plan['id'])


def run(accept):
    if not accept:
        raise RuntimeError('Explicit one-trial device-risk acceptance required')
    manifest = reader.load()
    plan = manifest['active_reader_checks'][-1]
    validate(plan)
    if plan['status'] != 'prepared' or not plan.get('rollback_checked_utc'):
        raise RuntimeError('Require prepared and checked plan; no repeat trial')
    client = reader.connect('ax58')
    try:
        check(client, plan)
        ready(client)
        plan['risk_acceptance'] = 'User explicitly accepted one active trial and AX58 hang/reboot/home-client interruption on 2026-11-01'
        plan['status'] = 'uploading'
        reader.save_manifest(manifest)
        for name, item in plan['files'].items():
            path = shlex.quote(item['path'])
            out, err, _ = reader.command(client, f'umask 077; set -C; cat > {path}', input_bytes=(BUILD/name).read_bytes())
            if out or err or reader.remote_file(client, item['path']) != (BUILD/name).read_bytes():
                raise RuntimeError('Upload differs; retain partial file')
            cmd(client, 'chmod 700 ' + path)
        # Socket-free ABI tests are part of preparation, not another radio trial.
        for name, item in plan['files'].items():
            out, err, _ = reader.command(client, shlex.quote(item['path']) + ' --self-test')
            if name == 'reader':
                reader.verify_fixture(out)
            elif out or err != b'supervisor socket-free self-test; no commands\n':
                raise RuntimeError('Supervisor self-test mismatch')
        check(client, plan)
        ready(client)
        plan['status'] = 'running'
        reader.save_manifest(manifest)
        root = ROOT / 'recordings/ax58-active-20261101' / plan['id']
        out, err, status, evidence = reader.collect(client,
            'exec ' + shlex.quote(plan['files']['supervisor']['path']) + ' --one-active-trial ' + shlex.quote(plan['files']['reader']['path']),
            root, timeout=20, max_bytes=6*1024**2)
        plan['result'] = dict(exit_status=status, stdout_bytes=len(out), stderr_bytes=len(err),
                              evidence=str(evidence.relative_to(ROOT)))
        plan['outcome'] = 'records-unvalidated' if status == 0 else 'no-data' if status == 3 else 'failed'
        plan['status'] = 'finished'
        reader.save_manifest(manifest)
        if b'cleanup=failed' in err or b'exit=125' in err:
            raise RuntimeError('Supervisor reports unresolved cleanup; retain files and inspect, no retry')
        plan['after'] = check(client, plan, apply=True)
        plan['status'] = 'restored'
        reader.save_manifest(manifest)
        print(json.dumps(plan['result']))
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--accept-active-risk', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    else:
        run(args.accept_active_risk)
