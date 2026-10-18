#!/usr/bin/env python3
"""Cross-check actual artifacts and input integrity after a complete analysis run."""
import csv
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from analyze import n64_crc
from import_roms import validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    specs = json.loads((ROOT / 'config/roms.json').read_text())
    summary = json.loads((ROOT / 'reports/evidence/summary.json').read_text())
    runs = json.loads((ROOT / 'generated/run-manifest.json').read_text())
    assert len(runs) == summary['commands_completed'] > 2
    assert all(r['exit_code'] == 0 and (ROOT / r['log']).is_file() for r in runs)
    counts = {}
    for game, spec in specs.items():
        data = (ROOT / 'baseroms' / (game + '.z64')).read_bytes()
        validate(data, spec)
        assert [f'0x{x:08X}' for x in n64_crc(data)] == json.loads((ROOT / 'reports/evidence' / (game + '.json')).read_text())['crc6102']['header']
        evidence = json.loads((ROOT / 'reports/evidence' / (game + '.json')).read_text())
        assert evidence['rom_sha256'] == hashlib.sha256(data).hexdigest()
        with (ROOT / 'reports/evidence' / (game + '-functions.csv')).open() as stream:
            functions = list(csv.DictReader(stream))
        assert len(functions) == evidence['function_count'] > 0
        generated_count = 0
        for r in evidence['regions']:
            assert 0x1000 <= r['rom_start'] < r['text_end'] <= r['rom_end'] <= len(data)
            folder = ROOT / 'generated' / game / 'spim' / r['id']
            with (folder / 'functions.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            assert rows, f'Zero-function disassembly: {folder}'
            assert list(folder.glob('*.s')), f'Missing disassembly: {folder}'
            generated_count += len(rows)
        assert generated_count == len(functions)
        assert evidence['overlap_pairs'], 'No overlay evidence emitted'
        assert evidence['graphics_candidates'] and evidence['ucode_signatures']
        assert list((ROOT / 'generated' / game / 'splat/asm').rglob('*.s'))
        ElementTree.parse(ROOT / 'reports' / (game + '-memory-map.svg'))
        counts[game] = {'functions': len(functions), 'regions': len(evidence['regions']), 'rom_unchanged': True}
    print(json.dumps({'checks': 'passed', 'tool_commands': len(runs), 'games': counts}, indent=2))


if __name__ == '__main__':
    main()
