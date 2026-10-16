"""Rollback-owned AX58 helper self-test only. Never opens Netlink or enables CSI."""
import argparse
import datetime as dt
import hashlib
import json
import logging
from pathlib import Path
import re
import shlex
import struct
import uuid

from repeater_probe import ROOT, connect, inspect, idle, remote_file, save_manifest
from ssh_diagnostics import collect

LOG = logging.getLogger('ruview.reader_probe')
BINARY = ROOT / 'recordings/ax58-reader-build-20261015/ax58-netlink-reader'
EXPECTED = 'e54178c7e7a5159bf5902140bf3e087c8953f03ef32fe789e5c482ce417d393c'


def load():
    return json.loads((ROOT / 'deployment.json').read_text())


def binary():
    data = BINARY.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise RuntimeError('Reader build differs from reviewed self-test binary')
    return data


def validate(plan):
    if (not re.fullmatch(r'[0-9a-f]{12}', plan['id']) or
            plan['path'] != '/tmp/ruview-nl-' + plan['id'] or
            plan['sha256'] != EXPECTED or plan['target'] != 'ax58' or
            plan['action'] != 'socket-free-self-test' or plan['before_file'] != 'absent'):
        raise RuntimeError('Unrecognized reader self-test plan')
    binary()


def command(client, text, *, input_bytes=None):
    out, err, status, folder = collect(client, text, ROOT / 'recordings/reader-probe',
                                     timeout=10, max_bytes=262144, input_bytes=input_bytes)
    if status:
        raise RuntimeError(f'Reader diagnostic exit={status}; evidence={folder}')
    return out, err, str(folder.relative_to(ROOT))


def processes(client, path):
    # Read only executable links; do not print unrelated cmdlines or signal PIDs.
    quoted = shlex.quote(path)
    out, err, _ = command(client,
        'for p in /proc/[0-9]*/exe; do v=$(readlink "$p" 2>/dev/null); '
        f'case "$v" in {quoted}|{shlex.quote(path + " (deleted)")}) echo "$p";; esac; done')
    if err or out.strip():
        raise RuntimeError('Reader process present or inspection failed; no cleanup attempted')


def baseline(client):
    boot, err, _ = command(client, 'cat /proc/sys/kernel/random/boot_id')
    if err or not re.fullmatch(rb'[0-9a-f-]{36}\s*', boot):
        raise RuntimeError('Invalid boot identity')
    radios = {name: inspect(client, name) for name in ('eth1', 'eth2')}
    for state in radios.values():
        idle(state)
        # The older idle helper checks protocol 23 only.
        for row in state['netlink'].splitlines()[1:]:
            fields = row.split()
            if len(fields) > 2 and fields[1] in ('22', '23') and fields[2] != '0':
                raise RuntimeError('Existing reader on CSI Netlink protocol')
    return {'boot_id': boot.decode().strip(), 'radios': radios}


def check(client, plan, apply=False):
    validate(plan)
    processes(client, plan['path'])
    path = shlex.quote(plan['path'])
    presence, err, _ = command(client, f'if [ -e {path} ] || [ -L {path} ]; then echo present; else echo absent; fi')
    if err or presence.strip() not in (b'present', b'absent'):
        raise RuntimeError('Reader file presence is unknown')
    exists = presence.strip() == b'present'
    data = remote_file(client, plan['path'])
    # Fail closed on partial/empty uploads: they need explicit inspection,
    # rather than interpreting a common ELF prefix as ownership proof.
    recovery = plan.get('inspected_partial')
    partial_owned = (recovery is not None and plan['status'] == 'uploading' and
                     recovery.get('bytes', 0) > 0 and
                     len(data) == recovery['bytes'] < len(binary()) and
                     data == binary()[:recovery['bytes']] and
                     hashlib.sha256(data).hexdigest() == recovery.get('sha256'))
    if exists and (plan['status'] in ('prepared', 'restored') or
                   (data != binary() and not partial_owned)):
        raise RuntimeError('Remote reader bytes are not owned by this operation')
    current = baseline(client)
    if current['boot_id'] != plan['before']['boot_id']:
        raise RuntimeError('Device boot identity changed; stop for inspection')
    for name in ('eth1', 'eth2'):
        for key in ('state', 'peers'):
            if current['radios'][name][key] != plan['before']['radios'][name][key]:
                raise RuntimeError('CSI baseline changed; no automatic monitor restoration')
    if apply and exists:
        # Recheck directly before deletion; never remove a symlink/unknown file.
        processes(client, plan['path'])
        if remote_file(client, plan['path']) != data:
            raise RuntimeError('Reader file changed during rollback')
        out, err, _ = command(client, 'rm -f ' + path)
        remaining, check_err, _ = command(client, f'if [ -e {path} ] || [ -L {path} ]; then echo present; else echo absent; fi')
        if out or err or check_err or remaining.strip() != b'absent':
            raise RuntimeError('Reader cleanup could not be verified')
    return current


def prepare():
    data = binary()
    manifest = load()
    if any(p['status'] != 'restored' for p in manifest.get('reader_self_tests', [])):
        raise RuntimeError('Resolve previous reader self-test first')
    identifier = uuid.uuid4().hex[:12]
    path = '/tmp/ruview-nl-' + identifier
    client = connect('ax58')
    try:
        # Unlike an empty cat, this distinguishes absent from an existing empty file.
        out, err, _ = command(client, f'if [ -e {path} ] || [ -L {path} ]; then echo present; else echo absent; fi')
        if err or out.strip() != b'absent':
            raise RuntimeError('Temporary path is not absent')
        processes(client, path)
        plan = {'id': identifier, 'path': path, 'sha256': EXPECTED, 'bytes': len(data),
                'target': 'ax58', 'action': 'socket-free-self-test', 'before_file': 'absent',
                'before': baseline(client), 'status': 'prepared',
                'prepared_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
        manifest.setdefault('reader_self_tests', []).append(plan)
        save_manifest(manifest)
        print('Prepared socket-free reader self-test:', identifier)
    finally:
        client.close()


def verify_fixture(data):
    if data[:8] != b'RUVRAW1\n':
        raise RuntimeError('Self-test magic mismatch')
    offset = 8
    for seq, length in enumerate((2064, 17)):
        header_len, payload_len = struct.unpack_from('<II', data, offset)
        offset += 8
        if header_len > 256 or payload_len != length:
            raise RuntimeError('Self-test size mismatch')
        header = json.loads(data[offset:offset + header_len])
        offset += header_len
        expected = {'source_sequence': seq, 'source_monotonic_ns': 123456789 + seq,
                    'truncated': bool(seq), 'receive_error': 'MSG_TRUNC' if seq else None}
        if header != expected or data[offset:offset + length] != bytes(i % 256 for i in range(length)):
            raise RuntimeError('Self-test content mismatch')
        offset += length
    if offset != len(data):
        raise RuntimeError('Self-test unexpected tail')


def run_test():
    manifest = load()
    plan = manifest['reader_self_tests'][-1]
    if plan['status'] != 'prepared' or not plan.get('rollback_checked_utc'):
        raise RuntimeError('Prepare and dry-check rollback before upload')
    client = connect('ax58')
    try:
        check(client, plan)
        plan['status'] = 'uploading'
        save_manifest(manifest)
        path = shlex.quote(plan['path'])
        # A failing/interrupted upload remains for the narrow rollback command.
        out, err, _ = command(client, f'umask 077; set -C; cat > {path}', input_bytes=binary())
        if out or err or remote_file(client, plan['path']) != binary():
            raise RuntimeError('Upload verification failed')
        out, err, _ = command(client, 'chmod 700 ' + path)
        if out or err:
            raise RuntimeError('Executable mode change failed')
        plan['status'] = 'running-self-test'
        save_manifest(manifest)
        out, err, folder = command(client, path + ' --self-test')
        verify_fixture(out)
        if err != b'self-test complete records=2; synthetic data only\n':
            raise RuntimeError('Unexpected self-test diagnostic')
        plan['self_test_evidence'] = folder
        plan['status'] = 'self-test-passed'
        save_manifest(manifest)
        plan['after'] = check(client, plan, apply=True)
        check(client, dict(plan, status='restored'))
        plan['status'] = 'restored'
        save_manifest(manifest)
        print('ARM self-test passed; exact temporary file removed; CSI baseline unchanged.')
    finally:
        client.close()


def rollback(apply=False):
    manifest = load()
    plan = manifest['reader_self_tests'][-1]
    client = connect('ax58')
    try:
        check(client, plan, apply)
        if apply:
            check(client, dict(plan, status='restored'))
            plan['status'] = 'restored'
        plan['rollback_checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_manifest(manifest)
        print('Reader rollback', 'applied' if apply else 'checked', plan['id'])
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'self-test'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        prepare() if args.action == 'prepare' else run_test()
    except Exception:
        LOG.exception('Reader self-test stopped; preserve evidence and inspect narrow rollback')
        raise SystemExit(1)
