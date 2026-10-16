"""Offline search of the retained exact AX58 SquashFS for CSI network export.

Never executes firmware or contacts devices. Requires requirements-research.txt.
Markers/imports identify candidates, not proof of absence or a usable exporter.
"""
import argparse
import hashlib
import io
import json
import logging
from pathlib import Path
import re
import struct

from dissect.squashfs import SquashFS
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

IMAGE_SHA = '701d40a64c37fc032ff3bb906dc4e02f182f83d80b1b7664dfb5e077724c8542'
OFFSET = 10135456
MARKER = re.compile(rb'(?<![a-z0-9])(?:csimon|csi\b|csi[_ -](?:monitor|collect|send|recv|export|server|client|udp|tcp)|channel.state.information|netlink_csi)', re.I)
NETWORK = {'socket', 'bind', 'connect', 'recvmsg', 'recvfrom', 'sendmsg', 'sendto',
           'setsockopt', '__netlink_kernel_create', 'netlink_broadcast',
           'sock_create_kern', 'kernel_sendmsg', 'udp_sendmsg', 'tcp_sendmsg'}


def marker_strings(raw):
    """Keep context around the hit even inside a long/minified string."""
    hits = []
    for text in re.finditer(rb'[\x20-\x7e\t]{4,}', raw):
        value = text.group()
        for match in MARKER.finditer(value):
            snippet = value[max(0, match.start() - 160):match.end() + 400]
            hits.append(snippet.decode('ascii', errors='replace'))
    return list(dict.fromkeys(hits))


def inspect_elf(raw):
    elf = ELFFile(io.BytesIO(raw))
    imports, csi_functions, references = set(), [], []
    symbols = elf.get_section_by_name('.symtab')
    if symbols is not None:
        csi_functions = [s for s in symbols.iter_symbols()
                         if 'csimon' in s.name.lower() and s['st_info']['type'] == 'STT_FUNC']
    for name in ('.symtab', '.dynsym'):
        table = elf.get_section_by_name(name)
        if table is not None:
            imports.update(s.name for s in table.iter_symbols()
                           if s['st_shndx'] == 'SHN_UNDEF' and s.name in NETWORK)
    for section in elf.iter_sections():
        if not csi_functions:
            break
        if not isinstance(section, RelocationSection):
            continue
        table = elf.get_section(section['sh_link'])
        for item in section.iter_relocations():
            owners = [s.name for s in csi_functions
                      if s['st_shndx'] == section['sh_info'] and
                      s['st_value'] <= item['r_offset'] < s['st_value'] + s['st_size']]
            if owners:
                references.append({'owners': owners, 'offset': hex(item['r_offset']),
                                   'symbol': table.get_symbol(item['r_info_sym']).name})
    return {'network_imports': sorted(imports),
            'csi_functions': [s.name for s in csi_functions], 'csi_references': references}


def audit(path):
    if path.stat().st_size != 36157344:
        raise ValueError('Unexpected firmware image size')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != IMAGE_SHA:
        raise ValueError('Firmware image hash mismatch')
    if struct.unpack_from('<I', data, OFFSET)[0] != 0x73717368:
        raise ValueError('SquashFS magic mismatch')
    size = struct.unpack_from('<Q', data, OFFSET + 40)[0]
    if size != 26020498 or OFFSET + size > len(data):
        raise ValueError('Unexpected rootfs extent')
    fs = SquashFS(io.BytesIO(data[OFFSET:OFFSET + size]))
    result = {'image_sha256': IMAGE_SHA, 'entries': 0, 'regular_files': 0,
              'regular_bytes': 0, 'elf_files': 0, 'markers': [], 'network_candidates': []}

    def visit(node, parent):
        for name, child in node.listdir().items():
            full = parent + '/' + name
            result['entries'] += 1
            if result['entries'] > 10000:
                raise ValueError('Entry budget exceeded')
            if child.is_dir():
                visit(child, full)
            elif child.is_file():
                result['regular_files'] += 1
                result['regular_bytes'] += child.size
                if child.size > 32 * 1024**2 or result['regular_bytes'] > 512 * 1024**2:
                    raise ValueError('Rootfs byte budget exceeded')
                raw = child.open().read()
                if len(raw) != child.size:
                    raise ValueError('Short rootfs read: ' + full)
                hits = marker_strings(raw)
                elf = inspect_elf(raw) if raw.startswith(b'\x7fELF') else None
                if elf is not None:
                    result['elf_files'] += 1
                item = {'path': full, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                if hits:
                    result['markers'].append({**item, 'strings': hits, 'elf': elf})
                if elf and elf['network_imports']:
                    result['network_candidates'].append({**item, **elf})
    visit(fs.get('/'), '')
    result['limits'] = ['Exact rootfs only; not bootloader/kernel image or downloaded/runtime files',
                        'No unpacking of nested compressed data',
                        'Stripped/inlined numeric socket clients can evade marker/import search',
                        'Static candidate search is not proof of absence or runtime support']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        if args.output.exists():
            raise FileExistsError('Refusing to replace audit output')
        report = audit(args.image)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps({key: report[key] for key in
                          ('entries', 'regular_files', 'regular_bytes', 'elf_files')}))
        print('CSI marker paths:', [item['path'] for item in report['markers']])
        print('Network-import candidates:', len(report['network_candidates']))
    except Exception:
        logging.getLogger('ruview.network_export_audit').exception('Offline firmware audit failed')
        raise SystemExit(1)
