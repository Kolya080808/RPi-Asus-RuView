"""Bounded synthetic Pi storage smoke test; no router connection or package install."""
import argparse
import datetime as dt
import hashlib
import json
import logging
from pathlib import Path
import re
import shlex
import stat
import uuid

import deploy_panel as deployment
from ssh_diagnostics import collect

ROOT = Path(__file__).resolve().parents[1]
FILES = {'raw.sqlite3', 'stderr.bin', 'transport.jsonl'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def payload(path):
    """Load reviewed modules in memory; write only the three receiver outputs."""
    modules = {name: (ROOT / 'src' / (name + '.py')).read_text(encoding='utf-8')
               for name in ('decoder', 'raw_pipeline', 'raw_transport')}
    return ("import sys, types, json, hashlib, sqlite3, time\nfrom pathlib import Path\n"
            + 'sources = ' + repr(modules) + '\n'
            + '''for name, source in sources.items():
    module = types.ModuleType(name)
    module.__file__ = '<in-memory-' + name + '>'
    sys.modules[name] = module
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
import raw_pipeline as raw
from raw_transport import receive_channel
class Channel:
    closed = False
    eof_received = True
    def __init__(self, wire):
        self.wire = wire
        self.error = b'synthetic Pi transport check\\n'
    def recv_ready(self): return bool(self.wire)
    def recv(self, size):
        result, self.wire = self.wire[:min(size, 4096)], self.wire[min(size, 4096):]
        return result
    def recv_stderr_ready(self): return bool(self.error)
    def recv_stderr(self, size):
        result, self.error = self.error, b''
        return result
    def exit_status_ready(self): return True
    def recv_exit_status(self): return 0
wire = raw.MAGIC + b''.join(raw.encode_frame(bytes(range(256))*8 + bytes(16),
    source_sequence=i) for i in range(32))
source = dict.fromkeys(raw.SOURCE_FIELDS)
source.update(source_id='synthetic-pi', operation_id=sys.argv[1],
    origin='synthetic', configuration={}, kind='netlink-datagram')
''' + 'directory = Path(' + repr(path) + ')\n' + '''started = time.monotonic()
result = receive_channel(Channel(wire), directory, source, timeout_s=5, max_bytes=131072)
with sqlite3.connect(directory / 'raw.sqlite3') as db:
    saved = b''.join(row[0] for row in db.execute('SELECT raw FROM chunks ORDER BY seq'))
    integrity = db.execute('PRAGMA quick_check').fetchone()[0]
assert saved == wire and integrity == 'ok'
print(json.dumps(dict(result=result, bytes=len(wire), sha256=hashlib.sha256(wire).hexdigest(),
    integrity=integrity, elapsed_s=time.monotonic()-started,
    files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir()})))
''').encode('utf-8')


def baseline(client):
    return {'boot': deployment.run(client, 'cat /proc/sys/kernel/random/boot_id'),
            'panel': deployment.run(client, 'systemctl is-active ruview-lab-panel.service')}


def validate(plan):
    identifier = plan.get('id', '')
    if (not re.fullmatch('[0-9a-f]{12}', identifier)
            or plan.get('path') != '/tmp/ruview-transport-' + identifier
            or plan.get('before_path') != 'absent'
            or plan.get('status') not in {'prepared', 'running', 'measured', 'restored'}):
        raise ValueError('Unrecognized Pi transport plan')


def inspect(client, sftp, plan):
    validate(plan)
    if baseline(client) != plan['before']:
        raise RuntimeError('Pi boot/panel state changed; inspect before cleanup')
    if ('ruview-transport-' + plan['id']) in deployment.run(client, 'ps -eo args'):
        raise RuntimeError('Probe process still present; no signals or deletion attempted')
    try:
        info = sftp.lstat(plan['path'])
    except FileNotFoundError:
        return {}
    if not stat.S_ISDIR(info.st_mode) or plan['status'] in {'prepared', 'restored'}:
        raise RuntimeError('Unexpected probe path')
    if plan['status'] != 'measured' or set(plan.get('files', {})) != FILES:
        raise RuntimeError('Incomplete run lacks verified file inventory; retain for inspection')
    names = set(sftp.listdir(plan['path']))
    if names - FILES:
        raise RuntimeError('Unknown files; retain directory')
    contents = {}
    for name in sorted(names):
        path = plan['path'] + '/' + name
        info = sftp.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
            raise RuntimeError('Unexpected probe file type/size')
        with sftp.open(path, 'rb') as stream:
            data = stream.read()
        if digest(data) != plan['files'][name]:
            raise RuntimeError('Probe file changed; retain evidence')
        contents[name] = data
    return contents


def prepare():
    manifest = deployment.load_manifest()
    if any(p['status'] != 'restored' for p in manifest.get('pi_transport_checks', [])):
        raise RuntimeError('Previous Pi transport plan needs resolution')
    identifier = uuid.uuid4().hex[:12]
    plan = dict(id=identifier, path='/tmp/ruview-transport-' + identifier,
                before_path='absent', status='prepared')
    plan['payload_sha256'] = digest(payload(plan['path']))
    client = deployment.connect()
    try:
        plan['before'] = baseline(client)
        with client.open_sftp() as sftp:
            inspect(client, sftp, plan)
        manifest.setdefault('pi_transport_checks', []).append(plan)
        deployment.save_manifest(manifest)
    finally:
        client.close()
    print(json.dumps(plan))


def rollback(apply=False):
    manifest = deployment.load_manifest()
    plan = manifest['pi_transport_checks'][-1]
    client = deployment.connect()
    try:
        with client.open_sftp() as sftp:
            contents = inspect(client, sftp, plan)
            if apply:
                # All outputs must already have byte-identical PC evidence.
                for name, data in contents.items():
                    local = ROOT / 'recordings' / ('pi-transport-' + plan['id']) / name
                    if not local.is_file() or local.read_bytes() != data:
                        raise RuntimeError('Local evidence missing or different; retain remote files')
                if inspect(client, sftp, plan) != contents:
                    raise RuntimeError('Probe state changed before removal')
                for name in contents:
                    sftp.remove(plan['path'] + '/' + name)
                try:
                    sftp.rmdir(plan['path'])
                except FileNotFoundError:
                    pass
                inspect(client, sftp, dict(plan, status='restored'))
                plan['status'] = 'restored'
            plan['rollback_checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
            deployment.save_manifest(manifest)
    finally:
        client.close()
    print('Pi synthetic transport rollback ' + ('applied and verified' if apply else 'check passed'))


def run():
    manifest = deployment.load_manifest()
    plan = manifest['pi_transport_checks'][-1]
    validate(plan)
    code = payload(plan['path'])
    if (plan['status'] != 'prepared' or not plan.get('rollback_checked_utc')
            or digest(code) != plan['payload_sha256']):
        raise RuntimeError('Require checked prepared plan and unchanged payload')
    evidence = ROOT / 'recordings' / ('pi-transport-' + plan['id'])
    evidence.mkdir(exist_ok=False)
    client = deployment.connect()
    try:
        with client.open_sftp() as sftp:
            inspect(client, sftp, plan)
        plan['status'] = 'running'
        deployment.save_manifest(manifest)
        command = 'timeout --signal=TERM --kill-after=2s 15s python3 -B - ' + shlex.quote('ruview-transport-' + plan['id'])
        out, err, status, _ = collect(client, command, evidence, timeout=20,
                                      max_bytes=65536, input_bytes=code)
        if status != 0:
            raise RuntimeError('Pi probe failed; evidence retained, inspect before cleanup')
        report = json.loads(out)
        if (set(report['files']) != FILES or report['integrity'] != 'ok'
                or report['result']['status'] != 'received'):
            raise RuntimeError('Unexpected probe result')
        plan.update(status='measured', files=report['files'], report=report)
        deployment.save_manifest(manifest)
        with client.open_sftp() as sftp:
            contents = inspect(client, sftp, plan)
            if set(contents) != FILES:
                raise RuntimeError('Missing remote evidence')
            for name, data in contents.items():
                with (evidence / name).open('xb') as stream:
                    stream.write(data)
        (evidence / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
    finally:
        client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    {'prepare': prepare, 'run': run}[args.action]()
