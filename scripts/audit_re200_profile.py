"""Offline, exact-image RE200 V5 profile check; never contacts a device."""
import argparse
import hashlib
import json
import logging
import lzma
from pathlib import Path
import re
import struct

IMAGE_SHA256 = 'ad1743f5001abf10047603d4a6389fced9c1b942e9de20f50981d19e84ea4282'
MAIN_SHA256 = '2bbd40d51f1e6133ee50231843570aa2a7acd3afc1dd30333fb5dd6fc161e52a'
OFFSET = 49264
LOG = logging.getLogger('ruview.re200_audit')


def inspect(path):
    with Path(path).open('rb') as stream:
        image = stream.read(3 * 1024 * 1024 + 1)
    if len(image) != 2593412 or hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('Not the inspected public RE200 V5 210408 image')
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE, memlimit=32 * 1024 * 1024)
    raw = decoder.decompress(image[OFFSET:], max_length=16 * 1024 * 1024 + 1)
    if not decoder.eof or len(raw) != 5194576 or hashlib.sha256(raw).hexdigest() != MAIN_SHA256:
        raise ValueError('Main stream did not match the inspected bounded payload')
    strings = [(m.start(), m.group().decode('ascii'))
               for m in re.finditer(rb'[\x20-\x7e]{4,}', raw)]
    terms = ('VxWorks5.5.1', 'taskSpawn', 'semBCreate', 'mt7628', 'csimon', 'csi', 'netlink')
    hits = {term: [{'offset':offset, 'text':text} for offset, text in strings
                   if term.lower() in text.lower()] for term in terms}
    # Independent structural evidence: MIPS little-endian startup instructions,
    # not an architecture conclusion based on vendor names or bootloader strings.
    words = struct.unpack_from('<6I', raw)
    expected = (0x3c081000, 0x40886000, 0x40806800, 0x24020001, 0x40824800, 0x40805800)
    if words != expected:
        raise ValueError('Unexpected startup instruction words')
    return {'image_sha256': IMAGE_SHA256, 'main_offset': OFFSET,
            'compressed_bytes': len(image) - OFFSET - len(decoder.unused_data),
            'main_bytes': len(raw), 'main_sha256': MAIN_SHA256,
            'mips_le_startup_words': [hex(word) for word in words], 'markers': hits,
            'limits': 'Public matching-build candidate; installed hash/region unverified. '
                      'String hits do not prove CSI export; not a full driver audit.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        result = inspect(args.image)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        LOG.info('RE200 offline profile verified; report=%s', args.output)
    except Exception:
        LOG.exception('RE200 profile audit failed; no device action was performed')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
