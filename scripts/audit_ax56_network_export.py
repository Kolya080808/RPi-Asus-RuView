"""Read-only audit of the previously extracted exact AX56 UBIFS rootfs.

Uses the same marker/ELF analysis as the AX58 audit. No device execution.
"""
import argparse
import hashlib
import json
import logging
from pathlib import Path, PurePosixPath

from ubireader.ubi_io import ubi_file
from ubireader.ubifs import ubifs, walk
from ubireader.ubifs.misc import process_reg_file
from audit_ax58_network_export import marker_strings, inspect_elf

VOLUME_SHA = '56aac5855686dc994fed2885c471be6d75b420c2fb6a6a59789e4b24a4880bbf'


def audit(path):
    if path.stat().st_size != 41902080 or hashlib.sha256(path.read_bytes()).hexdigest() != VOLUME_SHA:
        raise ValueError('Unexpected retained AX56 rootfs volume')
    result = {'volume_sha256': VOLUME_SHA, 'entries': 0, 'regular_files': 0,
              'regular_bytes': 0, 'elf_files': 0, 'markers': [], 'network_candidates': []}
    with ubi_file(str(path), 126976) as stream:
        fs = ubifs(stream)
        inodes, bad = {}, []
        walk.index(fs, fs.master_node.root_lnum, fs.master_node.root_offs, inodes, bad)
        if bad:
            raise ValueError('UBIFS index errors')

        def visit(inum, parent, ancestors):
            if inum in ancestors:
                raise ValueError('Directory cycle')
            for dent in inodes[inum].get('dent', []):
                full = str(PurePosixPath(parent) / dent.name)
                inode = inodes[dent.inum]
                result['entries'] += 1
                if result['entries'] > 10000:
                    raise ValueError('Entry budget exceeded')
                if dent.type == 1:
                    visit(dent.inum, full, ancestors | {inum})
                elif dent.type == 0:
                    size = inode['ino'].size
                    result['regular_files'] += 1
                    result['regular_bytes'] += size
                    if size > 32 * 1024**2 or result['regular_bytes'] > 512 * 1024**2:
                        raise ValueError('Rootfs byte budget exceeded')
                    raw = process_reg_file(fs, inode, full, inodes)
                    if len(raw) != size:
                        raise ValueError('Short rootfs read: ' + full)
                    hits = marker_strings(raw)
                    elf = inspect_elf(raw) if raw.startswith(b'\x7fELF') else None
                    if elf is not None:
                        result['elf_files'] += 1
                    item = {'path': full, 'bytes': size, 'sha256': hashlib.sha256(raw).hexdigest()}
                    if hits:
                        result['markers'].append({**item, 'strings': hits, 'elf': elf})
                    if elf and elf['network_imports']:
                        result['network_candidates'].append({**item, **elf})
        visit(1, '/', set())
    result['limits'] = ['Retained extracted rootfs only; excludes kernel/bootloader/runtime additions',
                        'Nested compressed contents not unpacked',
                        'Stripped/inlined numeric socket clients may evade this search',
                        'Static candidate search does not prove absence or working acquisition']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--volume', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        if args.output.exists():
            raise FileExistsError('Refusing to replace report')
        result = audit(args.volume)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps({k: result[k] for k in ('entries', 'regular_files', 'regular_bytes', 'elf_files')}))
        print('CSI marker paths:', [x['path'] for x in result['markers']])
        print('Network-import candidates:', len(result['network_candidates']))
    except Exception:
        logging.getLogger('ruview.network_export_audit').exception('Offline AX56 audit failed')
        raise SystemExit(1)
