"""Local file ingestion/replay only; does not connect to any device."""
import argparse
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from raw_pipeline import ingest, process


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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    if args.command == 'ingest':
        source = json.loads(args.source.read_text(encoding='utf-8'))
        with args.input.open('rb') as stream:
            result = ingest(stream, args.output, source, max_bytes=args.max_bytes)
    else:
        result = process(args.raw, args.output)
    print(json.dumps(result))
    return 0 if result['status'] in {'received', 'processed'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
