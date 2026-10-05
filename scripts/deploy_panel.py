"""Prepare/apply a file-only update of the existing Pi panel, with exact rollback.

No router changes, service installation, packages or database schema changes.
"""
import argparse
import datetime as dt
import hashlib
import json
import logging
from pathlib import Path
import shlex
import stat
import sys
import time
import uuid

import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = '/home/pi/ruview-lab'
SERVICE = 'ruview-lab-panel.service'
UNIT = '/etc/systemd/system/' + SERVICE
FILES = {'src/web_panel.py': 'web_panel.py', 'src/panel_signal.py': 'panel_signal.py',
         'src/live_signal.py': 'live_signal.py', 'web/index.html': 'web/index.html',
         'src/decoder.py': 'decoder.py',
         'web/app.css': 'web/app.css', 'web/theme.css': 'web/theme.css', 'web/app.js': 'web/app.js',
         'web/api-docs.html': 'web/api-docs.html', 'web/api-docs.css': 'web/api-docs.css',
         'web/api-docs.js': 'web/api-docs.js',
         'web/swagger-ui-bundle.js': 'web/swagger-ui-bundle.js',
         'web/swagger-ui-standalone-preset.js': 'web/swagger-ui-standalone-preset.js',
         'web/swagger-ui.css': 'web/swagger-ui.css',
         'web/swagger-ui-LICENSE.txt': 'web/swagger-ui-LICENSE.txt',
         'maps/home/floorplan.json': 'maps/home/floorplan.json',
         'docs/API.openapi.json': 'docs/API.openapi.json'}
LOGGER = logging.getLogger('ruview.deploy')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def connect():
    ssh = Path.home() / '.ssh'
    client = paramiko.SSHClient()
    client.load_host_keys(str(ssh / 'ruview_known_hosts'))
    client.connect('192.168.50.100', username='pi', key_filename=str(ssh / 'ruview_pi_lab'),
                   allow_agent=False, look_for_keys=False, timeout=10, auth_timeout=10)
    return client


def run(client, command, timeout=30):
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    error = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if code:
        raise RuntimeError(f'Remote operation failed (exit={code}): {error.strip()[:500]}')
    return out.strip()


def read_optional(sftp, path):
    try:
        info = sftp.lstat(path)
    except FileNotFoundError:
        return None, None
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f'Refusing non-regular file: {path}')
    with sftp.open(path, 'rb') as stream:
        return stream.read(), stat.S_IMODE(info.st_mode)


def load_manifest():
    return json.loads((ROOT / 'deployment.json').read_text(encoding='utf-8'))


def save_manifest(manifest):
    target = ROOT / 'deployment.json'
    pending = target.with_suffix('.json.tmp')
    pending.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    pending.replace(target)


def safe_backup(item):
    target = (ROOT / item['backup']).resolve()
    if not target.is_relative_to((ROOT / 'recordings').resolve()):
        raise RuntimeError('Backup path escapes recordings directory')
    data = target.read_bytes()
    if digest(data) != item['before_sha256']:
        raise RuntimeError('Backup checksum mismatch')
    return data


def validate_items(plan):
    allowed = {REMOTE + '/' + remote for remote in FILES.values()}
    if {item['path'] for item in plan['files']} != allowed or len(plan['files']) != len(allowed):
        raise RuntimeError('Deployment plan contains unexpected files')
    for item in plan['files']:
        if item['source'] not in FILES or REMOTE + '/' + FILES[item['source']] != item['path']:
            raise RuntimeError('Unexpected source mapping')
        if item['staging'] != item['path'] + '.panel-upload':
            raise RuntimeError('Unexpected staging path')
        if item['before_sha256'] is not None:
            safe_backup(item)


def device_state(client, sftp):
    unit, _ = read_optional(sftp, UNIT)
    if unit is None or b'ExecStart=/usr/bin/python3 /home/pi/ruview-lab/web_panel.py --host 0.0.0.0 --port 80' not in unit:
        raise RuntimeError('Unexpected panel service; refusing to manage it')
    state = {}
    for line in run(client, f'systemctl show {SERVICE} -p ActiveState -p UnitFileState -p MainPID').splitlines():
        key, value = line.split('=', 1)
        state[key] = value
    state['unit_sha256'] = digest(unit)
    state['unit_content'] = unit.decode()
    script = '''import pathlib,json
captures=[]
panels=[]
for p in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
 try:
  a=p.read_bytes().split(b'\\0')
 except (PermissionError,FileNotFoundError,ProcessLookupError):
  continue
 if any(x.endswith(b'/recorder.py') for x in a) and b'capture' in a: captures.append(p.parent.name)
 if any(x.endswith(b'/web_panel.py') for x in a): panels.append(p.parent.name)
print(json.dumps({'captures':captures,'panels':panels}))'''
    processes = json.loads(run(client, 'python3 -c ' + shlex.quote(script)))
    if processes['captures']:
        raise RuntimeError('A capture is active; wait until it finishes')
    if set(processes['panels']) - {state['MainPID']}:
        raise RuntimeError('An unowned panel process is active')
    if state['ActiveState'] == 'active' and health(client).get('active_capture'):
        raise RuntimeError('A panel capture is active or paused; stop it before deployment or rollback')
    return state


def database_state(client):
    script = '''import sqlite3,json,hashlib
c=sqlite3.connect('file:/home/pi/ruview-lab/history.sqlite3?mode=ro',uri=True)
h=hashlib.sha256()
for sid,seq,raw in c.execute('SELECT session,seq,raw FROM records ORDER BY session,seq'):
 h.update(sid.encode());h.update(str(seq).encode());h.update(raw)
tables=['sessions','records','map_points','map_routes','session_annotations']
print(json.dumps({'raw_sha256':h.hexdigest(),'counts':{t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in tables},'integrity':c.execute('PRAGMA quick_check').fetchone()[0]}))'''
    result = json.loads(run(client, 'python3 -c ' + shlex.quote(script)))
    if result['integrity'] != 'ok':
        raise RuntimeError('History integrity check failed')
    return result


def prepare(client):
    manifest = load_manifest()
    if any(p['status'] in ('prepared', 'applying') for p in manifest.get('panel_updates', [])):
        raise RuntimeError('An unfinished deployment already exists; inspect it first')
    identifier = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
    folder = ROOT / 'recordings' / ('panel-deploy-' + identifier)
    folder.mkdir(parents=True)
    with client.open_sftp() as sftp:
        state = device_state(client, sftp)
        if state['ActiveState'] != 'active':
            raise RuntimeError('Expected the existing panel service to be active')
        db_before = database_state(client)
        items = []
        for source, remote in FILES.items():
            data = (ROOT / source).read_bytes()
            path = REMOTE + '/' + remote
            before, mode = read_optional(sftp, path)
            item = {'source': source, 'path': path, 'sha256': digest(data),
                    'before_sha256': digest(before) if before is not None else None,
                    'before_mode': mode, 'backup': None, 'staging': path + '.panel-upload'}
            staged, _ = read_optional(sftp, item['staging'])
            if staged is not None:
                raise RuntimeError('Unexpected staging file already exists')
            if before is not None:
                backup = folder / remote
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(before)
                item['backup'] = backup.relative_to(ROOT).as_posix()
            items.append(item)
        plan = {'id': identifier, 'status': 'prepared',
                'prepared_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'service_before': state, 'database_before': db_before, 'files': items,
                'scope': 'Panel files and restart only; preserve database and service settings'}
        validate_items(plan)
        manifest.setdefault('panel_updates', []).append(plan)
        save_manifest(manifest)
    LOGGER.info('Prepared operation=%s files=%d; Pi unchanged', identifier, len(items))
    return plan


def current_plan(manifest):
    plans = [p for p in manifest.get('panel_updates', []) if p['status'] != 'rolled_back']
    if not plans:
        raise RuntimeError('No active panel deployment recorded')
    return plans[-1]


def preflight(client, sftp, plan, rollback=False):
    validate_items(plan)
    state = device_state(client, sftp)
    if state['unit_sha256'] != plan['service_before']['unit_sha256'] or state['UnitFileState'] != plan['service_before']['UnitFileState']:
        raise RuntimeError('Service settings changed since preparation')
    for item in plan['files']:
        content, _ = read_optional(sftp, item['path'])
        actual = digest(content) if content is not None else None
        acceptable = {item['before_sha256'], item['sha256']} if rollback else {item['before_sha256']}
        if actual not in acceptable:
            raise RuntimeError(f"File changed outside this deployment: {item['path']}")
        staged, _ = read_optional(sftp, item['staging'])
        if staged is not None and digest(staged) not in {item['sha256'], item['before_sha256']}:
            raise RuntimeError('Unexpected staging content; manual inspection required')
        if not rollback and digest((ROOT / item['source']).read_bytes()) != item['sha256']:
            raise RuntimeError('Local source changed after prepare')
    return state


def write_file(sftp, path, staging, data, mode):
    with sftp.open(staging, 'wb') as stream:
        stream.write(data)
    sftp.chmod(staging, mode)
    content, _ = read_optional(sftp, staging)
    if digest(content) != digest(data):
        raise RuntimeError('Upload checksum mismatch')
    sftp.posix_rename(staging, path)


def health(client):
    script = "import urllib.request,json; d=json.load(urllib.request.urlopen('http://127.0.0.1/api/health',timeout=5)); print(json.dumps({k:v for k,v in d.items() if k!='write_token'}))"
    for attempt in range(12):
        try:
            return json.loads(run(client, 'python3 -c ' + shlex.quote(script), timeout=10))
        except RuntimeError:
            if attempt == 11:
                raise
            time.sleep(.5)


def apply(client, manifest, plan):
    with client.open_sftp() as sftp:
        preflight(client, sftp, plan)
        if database_state(client) != plan['database_before']:
            raise RuntimeError('History changed since preparation; inspect before applying')
        LOGGER.info('Rollback plan validated operation=%s', plan['id'])
        plan['status'] = 'applying'
        save_manifest(manifest)
        run(client, f'sudo -n systemctl stop {SERVICE}')
        if run(client, f'systemctl show {SERVICE} -p ActiveState --value') != 'inactive':
            raise RuntimeError('Panel did not stop')
        folder = ROOT / 'recordings' / ('panel-deploy-' + plan['id'])
        sftp.get(REMOTE + '/history.sqlite3', str(folder / 'history-before.sqlite3'))
        for item in plan['files']:
            write_file(sftp, item['path'], item['staging'], (ROOT / item['source']).read_bytes(), item['before_mode'] or 0o644)
        for item in plan['files']:
            content, _ = read_optional(sftp, item['path'])
            if digest(content) != item['sha256']:
                raise RuntimeError('Deployed checksum mismatch')
        run(client, f'sudo -n systemctl start {SERVICE}')
        if health(client)['api_version'] != 'v2':
            raise RuntimeError('Unexpected running API version')
        plan['database_after'] = database_state(client)
        if plan['database_after'] != plan['database_before']:
            raise RuntimeError('History unexpectedly changed')
        final = device_state(client, sftp)
        if final['ActiveState'] != 'active' or final['unit_sha256'] != plan['service_before']['unit_sha256']:
            raise RuntimeError('Service verification failed')
        plan['status'] = 'applied'
        plan['verified_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_manifest(manifest)
        LOGGER.info('Applied and verified operation=%s files=%d raw_history_unchanged=true', plan['id'], len(plan['files']))


def rollback_panel(do_apply=False):
    manifest = load_manifest()
    plan = current_plan(manifest)
    client = connect()
    try:
        with client.open_sftp() as sftp:
            preflight(client, sftp, plan, rollback=True)
            LOGGER.info('Panel rollback inspection passed operation=%s status=%s files=%d', plan['id'], plan['status'], len(plan['files']))
            if not do_apply:
                return
            db_before = database_state(client)
            run(client, f'sudo -n systemctl stop {SERVICE}')
            for item in plan['files']:
                current, _ = read_optional(sftp, item['path'])
                if item['before_sha256'] is None:
                    if current is not None:
                        sftp.remove(item['path'])
                else:
                    write_file(sftp, item['path'], item['staging'], safe_backup(item), item['before_mode'])
                staged, _ = read_optional(sftp, item['staging'])
                if staged is not None:
                    sftp.remove(item['staging'])
            for item in plan['files']:
                data, mode = read_optional(sftp, item['path'])
                actual = digest(data) if data is not None else None
                if actual != item['before_sha256'] or (data is not None and mode != item['before_mode']):
                    raise RuntimeError('Rollback file verification failed')
            if plan['service_before']['ActiveState'] == 'active':
                run(client, f'sudo -n systemctl start {SERVICE}')
                health(client)
            if database_state(client) != db_before:
                raise RuntimeError('History changed during rollback')
            final = device_state(client, sftp)
            if final['ActiveState'] != plan['service_before']['ActiveState']:
                raise RuntimeError('Rollback service-state mismatch')
            plan['status'] = 'rolled_back'
            save_manifest(manifest)
            LOGGER.info('Panel rollback verified operation=%s; database retained', plan['id'])
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        rollback_panel(False)
        return
    client = connect()
    try:
        if args.prepare:
            prepare(client)
        else:
            manifest = load_manifest()
            plan = current_plan(manifest)
            if plan['status'] != 'prepared':
                raise RuntimeError('Only prepared plans can be applied')
            apply(client, manifest, plan)
    finally:
        client.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    try:
        main()
    except Exception:
        LOGGER.exception('Deployment failed; inspect manifest, then use rollback.py --panel-only --check before recovery')
        sys.exit(1)
