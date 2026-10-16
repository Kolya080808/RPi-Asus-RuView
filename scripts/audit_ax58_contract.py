"""Offline, hash-locked AX58 BSS/CSI contract audit; never executes firmware.

Accepts the retained release module and GPL wlioctl.h. Exact A32 words and ELF
relocations cross-check the mapping-aware disassembly without a disassembler.
A successful audit is NOT permission to enable monitoring.
"""
import argparse
import hashlib
import json
import logging
from pathlib import Path
import re
import struct

MODULE_SHA256 = 'dabb2f7e716d63f4ffa9163773b7f87c15050cb442d021db528194f0b25e68a8'
HEADER_SHA256 = 'efcba85dff6df5ad80e82777bb04e35fea16011f5f80a41b9a04be4134fdd1d5'
LOG = logging.getLogger('ruview.ax58_contract')


def read_elf(path, expected):
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('Module exceeds audit input limit')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Input hash mismatch')
    if raw[:6] != b'\x7fELF\x01\x01':
        raise ValueError('Expected ELF32 little endian')
    h = struct.unpack_from('<HHIIIIIHHHHHH', raw, 16)
    if h[:2] != (1, 40):
        raise ValueError('Expected relocatable ARM')
    sections = [struct.unpack_from('<10I', raw, h[5] + i * h[10]) for i in range(h[11])]
    def data(section):
        return raw[section[4]:section[4] + section[5]]
    def string(table, offset):
        return table[offset:table.index(0, offset)].decode()
    names = data(sections[h[12]])
    ti = next(i for i, s in enumerate(sections) if string(names, s[0]) == '.text')
    text = data(sections[ti])
    symbols = next(s for s in sections if s[1] == 2)
    strings = data(sections[symbols[6]])
    entries = [struct.unpack_from('<IIIBBH', raw, off)
               for off in range(symbols[4], symbols[4] + symbols[5], symbols[9])]
    refs = {}
    for section in sections:
        if section[1] == 9 and section[7] == ti:
            for off in range(section[4], section[4] + section[5], section[9]):
                address, info = struct.unpack_from('<II', raw, off)
                refs[address] = string(strings, entries[info >> 8][0])
    return text, refs


def branch(word, address):
    if word & 0x0f000000 != 0x0a000000:
        raise ValueError('Expected A32 B')
    displacement = word & 0xffffff
    if displacement & 0x800000:
        displacement -= 0x1000000
    return address + 8 + displacement * 4


def audit(module, header):
    text, refs = read_elf(module, MODULE_SHA256)
    if header.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Header exceeds audit input limit')
    header_bytes = header.read_bytes()
    if hashlib.sha256(header_bytes).hexdigest() != HEADER_SHA256:
        raise ValueError('Header hash mismatch')
    for name, value in [('BSSCFG_TYPE_GENERIC', 0), ('BSSCFG_TYPE_P2P', 1),
                        ('BSSCFG_GENERIC_AP', 2), ('BSSCFG_P2P_GO', 4)]:
        if not re.search(rb'\b' + name.encode() + rb'\s*=\s*' + str(value).encode() + rb'\s*,', header_bytes):
            raise ValueError('Header enum mismatch: ' + name)

    def words(address, expected):
        actual = list(struct.unpack_from('<' + 'I' * len(expected), text, address))
        if actual != expected:
            raise ValueError(f'A32 mismatch at {address:#x}')

    # Setter: byte +6 is (generic, AP) or (P2P, GO); CLZ/LSR normalizes equality.
    words(0x29804c, [0xe5d13000, 0xe3530000, 0x0a00001e,
                     0xe3530001, 0x05d13001, 0x13a03000,
                     0x02433004, 0x016f3f13, 0x01a032a3, 0xe5c03006])
    words(0x2980d4, [0xe5d13001, 0xe2433002, 0xe16f3f13,
                     0xe1a032a3, 0xeaffffe1])
    # Independent getter maps generic +6 != 0 back to public AP subtype 2.
    words(0x2993e0, [0xe5d13078, 0xe3a00000, 0xe5c20001,
                     0xe1530000, 0xe5c23000, 0x112fff1e,
                     0xe5d13006, 0xe1530000, 0x0a000002,
                     0xe3a03002, 0xe5c23001, 0xe12fff1e])
    # BSS up writes 1 to byte +4; down writes 0 to the same byte.
    words(0x29a99c, [0xe3a03001, 0xe5c43004])
    words(0x298830, [0xe3a03000, 0xe5d42004, 0xe5c43004])
    words(0x33c754, [0xe5d13006, 0xe3530000, 0x0afffff7,
                     0xe5d13004, 0xe3530000, 0x0afffff4])
    for addr in (0x33c75c, 0x33c768):
        if branch(struct.unpack_from('<I', text, addr)[0], addr) != 0x33c740:
            raise ValueError('Lookup skip target differs')
    if refs.get(0x33c77c) != 'wlc_scbfindband':
        raise ValueError('Current-band lookup relocation differs')
    words(0x33c790, [0xe3a00000, 0xe8bd81f0])
    if refs.get(0x2b560c) != 'wlc_scbapfind':
        raise ValueError('Enable lookup relocation differs')
    words(0x2b560c, [0xebfffffe, 0xe1a0300a, 0xe1a01009, 0xe1a02000, 0xe5804210])
    return {
        'module_sha256': MODULE_SHA256, 'header_sha256': HEADER_SHA256,
        'method': 'stdlib ELF32 relocations, exact A32 words, branch arithmetic and GPL enums',
        'configuration_byte_6': 'AP role: generic AP or P2P GO',
        'configuration_byte_4': 'BSS up-state byte (paired up/down writes)',
        'lookup': 'non-null AP-role and up configuration; current-band peer; may return zero',
        'enable': 'unguarded store through lookup result at .text+0x2b561c',
        'runtime_validated': False, 'safe_to_enable': False,
        'limits': ['No live peer proof', 'No lifecycle/race safety proof',
                   'No reader compatibility or decoder validation',
                   'Does not reopen or attribute the historical incident'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--header', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        print(json.dumps(audit(args.module, args.header), indent=2))
    except Exception:
        LOG.exception('Offline AX58 contract audit failed')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
