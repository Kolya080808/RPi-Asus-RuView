"""Local file ingestion/replay only; does not connect to any device."""
import argparse
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from raw_pipeline import ingest, process
from raw_recovery import recover, import_legacy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    receive = commands.add_parser('ingest')
    receive.add_argument('--input', type=Path, required=True)
    receive.add_argument('--source', type=Path, required=True)
    receive.add_argument('--output', type=Path, required=True)
    receive.add_argument('--max-bytes', type=int, default=64 * 1024**2)
    replay = commands.add_parser('process')
    replay.add_argument('--raw', type=Path, required=True)
    replay.add_argument('--output', type=Path, required=True)
    restore = commands.add_parser('recover')
    restore.add_argument('--raw', type=Path, required=True)
    restore.add_argument('--output', type=Path, required=True)
    legacy = commands.add_parser('import-legacy')
    legacy.add_argument('--history', type=Path, required=True)
    legacy.add_argument('--session', required=True)
    legacy.add_argument('--source', type=Path, required=True)
    legacy.add_argument('--output', type=Path, required=True)
    for command in (restore, legacy):
        command.add_argument('--max-bytes', type=int, default=64 * 1024**2)
        command.add_argument('--max-rows', type=int, default=100000)
        command.add_argument('--timeout-s', type=float, default=30)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    if args.command == 'ingest':
        source = json.loads(args.source.read_text(encoding='utf-8'))
        with args.input.open('rb') as stream:
            result = ingest(stream, args.output, source, max_bytes=args.max_bytes)
    elif args.command == 'process':
        result = process(args.raw, args.output)
    elif args.command == 'recover':
        result = recover(args.raw, args.output, max_bytes=args.max_bytes,
                         max_rows=args.max_rows, timeout_s=args.timeout_s)
    else:
        source = json.loads(args.source.read_text(encoding='utf-8'))
        result = import_legacy(args.history, args.session, args.output, source,
                               max_bytes=args.max_bytes, max_rows=args.max_rows,
                               timeout_s=args.timeout_s)
    print(json.dumps(result))
    return 0 if result['status'] in {'received', 'processed'} else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        logging.getLogger('ruview.raw_cli').exception('Offline operation failed')
        raise SystemExit(1)
