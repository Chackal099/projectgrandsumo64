#!/usr/bin/env python3
"""Audit the Git index, including previously tracked files, before publication."""
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOTS = {'.tools', '.venv', 'baseroms', 'generated', 'local', 'build', 'dist'}
BINARY_SUFFIXES = {
    '.z64', '.n64', '.v64', '.rom', '.bin', '.elf', '.o', '.obj', '.a', '.lib',
    '.dll', '.exe', '.so', '.dylib', '.pdb', '.zip', '.7z', '.rdram', '.sav',
    '.srm', '.eep', '.fla', '.png', '.jpg', '.jpeg', '.wav', '.ogg', '.mp3',
    '.sra', '.mpk', '.dmp', '.pj', '.m64', '.state', '.jsonl',
}
MAGICS = (bytes.fromhex('80371240'), bytes.fromhex('37804012'), bytes.fromhex('40123780'),
          b'\x7fELF', b'PK\x03\x04', b'MZ')


def audit(root):
    records = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--stage', '-z'])
    violations = []
    for record in records.split(b'\0'):
        if not record:
            continue
        metadata, raw_path = record.split(b'\t', 1)
        mode, object_id, stage = metadata.split()
        path = raw_path.decode('utf-8')
        parts = PurePosixPath(path).parts
        if stage != b'0' or mode not in (b'100644', b'100755'):
            violations.append(f'{path}: unresolved index entry, symlink or nested repository')
            continue
        if parts[0] in PRIVATE_ROOTS or PurePosixPath(path).suffix.lower() in BINARY_SUFFIXES:
            violations.append(f'{path}: private output or binary/asset extension')
            continue
        # Read the actual staged blob: an unstaged edit must not hide forbidden data.
        data = subprocess.check_output(['git', '-C', str(root), 'cat-file', 'blob', object_id.decode()])
        if data.startswith(MAGICS) or b'\0' in data:
            violations.append(f'{path}: binary bytes or known ROM/executable/archive signature')
    return violations


def main():
    violations = audit(ROOT)
    if violations:
        print('\n'.join(violations), file=sys.stderr)
        return 1
    print('Git index: no private output paths, binary/asset extensions or known ROM/binary signatures')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
