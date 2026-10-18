#!/usr/bin/env python3
"""Import only the expected ROM bytes; never extract arbitrary archive paths."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def validate(data, expected):
    if len(data) != expected['size'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
        raise ValueError('ROM size or SHA-256 differs from the supplied reference')
    if data[:4] != bytes.fromhex('80371240'):
        raise ValueError('Expected original big-endian z64; no conversion is performed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', choices=['ozumo1', 'ozumo2'])
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    expected = json.loads((ROOT / 'config/roms.json').read_text())[args.game]
    source_bytes = args.source.read_bytes()
    if zipfile.is_zipfile(args.source):
        with zipfile.ZipFile(args.source) as archive:
            members = [m for m in archive.infolist() if m.filename.lower().endswith('.z64')]
            if len(members) != 1 or members[0].file_size != expected['size']:
                raise ValueError('Expected exactly one 16 MiB z64 member')
            data = archive.read(members[0])  # CRC verification stays enabled
    else:
        data = source_bytes
    validate(data, expected)
    dest = ROOT / 'baseroms' / (args.game + '.z64')
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        validate(dest.read_bytes(), expected)
    else:
        with dest.open('xb') as stream:
            stream.write(data)
    assert args.source.read_bytes() == source_bytes
    print(f'{args.game}: original bytes verified; {dest.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
