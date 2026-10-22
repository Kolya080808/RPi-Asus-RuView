"""Bounded AX58 passive reader with explicit risk acceptance and narrow rollback."""
import argparse
import datetime as dt
import hashlib
import logging
import re
import shlex
import uuid

import reader_probe as reader

LOG = logging.getLogger('ruview.passive_reader')
ACTION = 'passive-netlink-csi-disabled'
STATES = {'prepared-blocked', 'uploading', 'uploaded', 'running', 'finished', 'restored'}


def validate(plan):
    identifier = plan.get('id', '')
    if (not re.fullmatch(r'[0-9a-f]{12}', identifier) or
            plan.get('path') != '/tmp/ruview-passive-' + identifier or
            plan.get('action') != ACTION or plan.get('target') != 'ax58' or
            plan.get('sha256') != reader.EXPECTED or
            plan.get('before_file') != 'absent' or
            type(plan.get('protocol')) is not int or plan['protocol'] not in (22, 23) or
            type(plan.get('seconds')) is not int or plan['seconds'] != 2 or
            plan.get('status') not in STATES):
        raise RuntimeError('Unrecognized passive reader plan')
    reader.binary()


def outcome(stdout, stderr, exit_status):
    """Classify retained transport results without claiming a CSI measurement."""
    if (exit_status == 3 and stdout == b'RUVRAW1\n' and
            stderr == b'bounded reader exit=3 records=0; driver loss unknown\n'):
        return 'expected-no-data'
    raise RuntimeError('Unexpected passive reader result; retain all output for inspection')


def check(client, plan, apply=False):
    validate(plan)
    reader.processes(client, plan['path'])
    path = shlex.quote(plan['path'])
    presence, error, _ = reader.command(client,
        f'if [ -e {path} ] || [ -L {path} ]; then echo present; else echo absent; fi')
    if error or presence.strip() not in (b'present', b'absent'):
        raise RuntimeError('Passive reader file presence is unknown')
    exists = presence.strip() == b'present'
    data = reader.remote_file(client, plan['path'])
    if not exists and data:
        raise RuntimeError('Passive reader file appeared during inspection')
    if exists and (plan['status'] in ('prepared-blocked', 'restored') or
                   data != reader.binary()):
        raise RuntimeError('Passive reader file is not owned; retain partial/unknown files')
    current = reader.baseline(client)
    if current['boot_id'] != plan['before']['boot_id']:
        raise RuntimeError('Device boot identity changed; stop for inspection')
    for interface in ('eth1', 'eth2'):
        for field in ('state', 'peers'):
            if current['radios'][interface][field] != plan['before']['radios'][interface][field]:
                raise RuntimeError('CSI baseline changed; no automatic restoration')
    if apply and exists:
        reader.processes(client, plan['path'])
        if reader.remote_file(client, plan['path']) != data:
            raise RuntimeError('Passive reader file changed during rollback')
        output, error, _ = reader.command(client, 'rm -f ' + path)
        if output or error:
            raise RuntimeError('Passive reader removal failed')
        check(client, dict(plan, status='restored'))
    return current


def prepare(protocol):
    if type(protocol) is not int or protocol not in (22, 23):
        raise ValueError('Only Netlink 22 or 23 can be planned')
    binary = reader.binary()
    manifest = reader.load()
    for collection in ('reader_self_tests', 'passive_reader_checks'):
        if any(plan['status'] != 'restored' for plan in manifest.get(collection, [])):
            raise RuntimeError('Resolve the previous reader plan before preparing another')
    identifier = uuid.uuid4().hex[:12]
    plan = {'id': identifier, 'path': '/tmp/ruview-passive-' + identifier,
            'target': 'ax58', 'action': ACTION, 'before_file': 'absent',
            'sha256': hashlib.sha256(binary).hexdigest(), 'bytes': len(binary),
            'protocol': protocol, 'seconds': 2, 'status': 'prepared-blocked',
            'initial_execution_gate': 'blocked-pending-review-or-explicit-risk-acceptance',
            'unresolved_review': 'Global NETLINK_URELEASE listeners and installed kernel correspondence',
            'prepared_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    client = reader.connect('ax58')
    try:
        plan['before'] = reader.baseline(client)
        check(client, plan)
        manifest.setdefault('passive_reader_checks', []).append(plan)
        reader.save_manifest(manifest)
        LOG.info('operation=%s passive plan prepared; no upload/socket; execution blocked', identifier)
    finally:
        client.close()
    return plan


def rollback(apply=False):
    manifest = reader.load()
    plans = manifest.get('passive_reader_checks', [])
    if not plans:
        raise RuntimeError('No passive reader plan')
    plan = plans[-1]
    validate(plan)
    client = reader.connect('ax58')
    try:
        current = check(client, plan, apply)
        if apply:
            check(client, dict(plan, status='restored'))
            plan['after'] = current
            plan['status'] = 'restored'
        plan['rollback_checked_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        reader.save_manifest(manifest)
        LOG.info('operation=%s passive rollback %s passed', plan['id'], 'apply' if apply else 'check')
    finally:
        client.close()


def run(identifier, accept_passive_risk=False):
    if not accept_passive_risk:
        raise RuntimeError('Explicit acceptance of the documented passive lifecycle risk is required')
    manifest = reader.load()
    plans = manifest.get('passive_reader_checks', [])
    if not plans or plans[-1]['id'] != identifier:
        raise RuntimeError('Select the exact latest passive plan')
    plan = plans[-1]
    validate(plan)
    if plan['status'] != 'prepared-blocked' or not plan.get('rollback_checked_utc'):
        raise RuntimeError('Prepare and dry-check the passive rollback before execution')
    client = reader.connect('ax58')
    try:
        plan['execution_before'] = check(client, plan)
        plan['risk_acceptance'] = {
            'scope': 'One bounded passive run; CSI disabled; lifecycle uncertainty accepted',
            'utc': dt.datetime.now(dt.timezone.utc).isoformat()}
        plan['status'] = 'uploading'
        reader.save_manifest(manifest)
        path = shlex.quote(plan['path'])
        output, error, _ = reader.command(client, f'umask 077; set -C; cat > {path}',
                                           input_bytes=reader.binary())
        if output or error or reader.remote_file(client, plan['path']) != reader.binary():
            raise RuntimeError('Passive helper upload verification failed')
        output, error, _ = reader.command(client, 'chmod 700 ' + path)
        if output or error:
            raise RuntimeError('Passive helper executable mode change failed')
        plan['status'] = 'uploaded'
        reader.save_manifest(manifest)
        check(client, plan)
        evidence_root = reader.ROOT / 'recordings/passive-reader' / plan['id']
        plan['receive_evidence_root'] = str(evidence_root.relative_to(reader.ROOT))
        plan['status'] = 'running'
        reader.save_manifest(manifest)
        stdout, stderr, status, folder = reader.collect(
            client, f'exec {path} {plan["protocol"]} {plan["seconds"]}',
            evidence_root, timeout=10, max_bytes=6 * 1024 * 1024)
        plan['receive'] = {'exit_status': status, 'stdout_bytes': len(stdout),
                           'stderr_bytes': len(stderr),
                           'evidence': str(folder.relative_to(reader.ROOT))}
        plan['status'] = 'finished'
        reader.save_manifest(manifest)
        try:
            plan['outcome'] = outcome(stdout, stderr, status)
        except RuntimeError:
            plan['outcome'] = 'unexpected-result'
        reader.save_manifest(manifest)
        plan['after'] = check(client, plan, apply=True)
        check(client, dict(plan, status='restored'))
        plan['status'] = 'restored'
        plan['cleanup_verified_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        reader.save_manifest(manifest)
        if plan['outcome'] != 'expected-no-data':
            raise RuntimeError('Passive result was unexpected; cleanup verified, evidence retained')
        LOG.info('operation=%s passive no-data interval complete; cleanup and baseline verified', identifier)
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--protocol', type=int, choices=(22, 23))
    parser.add_argument('--plan')
    parser.add_argument('--accept-passive-risk', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare' and (args.protocol is None or args.plan or args.accept_passive_risk):
        parser.error('prepare requires only --protocol')
    if args.action == 'run' and (not args.plan or args.protocol is not None or not args.accept_passive_risk):
        parser.error('run requires --plan and --accept-passive-risk; bounds come from the plan')
    logging.basicConfig(level=logging.INFO)
    try:
        if args.action == 'prepare':
            prepare(args.protocol)
        else:
            run(args.plan, args.accept_passive_risk)
    except Exception:
        LOG.exception('Passive reader operation failed; preserve diagnostics and inspect narrow rollback')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
