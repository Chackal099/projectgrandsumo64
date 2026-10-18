#!/usr/bin/env python3
"""Static evidence pipeline. ROM endpoints are exclusive. No emulation or patching."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

import rabbitizer
import yaml

from import_roms import validate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'generated'
METRICS = ROOT / 'reports' / 'evidence'
CALLER_SAVED = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 31)
RUNS = []


class HexDumper(yaml.SafeDumper):
    pass


HexDumper.add_representer(int, lambda dumper, value: dumper.represent_scalar('tag:yaml.org,2002:int', hex(value)))


def words(data):
    return [x[0] for x in struct.iter_unpack('>I', data)]


def hx(n):
    return f'0x{n:08X}'


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def save_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r.get(k) for k in fields} for r in rows)


def constant_calls(data, start, end, vram):
    """Conservative straight-line constants, respecting delay slots and call clobbers.

    At branch targets and after conditional/unconditional transfers reset state.
    Unknown registers are never assumed zero. This intentionally misses loads that
    require flow joins, tables, memory values or arithmetic on unknown pointers.
    """
    instructions = words(data[start:end])
    branch_targets = set()
    for j, w in enumerate(instructions):
        ins = rabbitizer.Instruction(w, vram + j * 4)
        if ins.isBranch():
            branch_targets.add(start + j * 4 + 4 + (((w & 65535) ^ 32768) - 32768) * 4)
        if w >> 26 == 2:
            target = (w & 0x3FFFFFF) * 4 | ((vram + j * 4 + 4) & 0xF0000000)
            if vram <= target < vram + end - start:
                branch_targets.add(start + target - vram)
    regs = {0: 0}
    stack = {}
    pending = None
    calls = []
    for j, w in enumerate(instructions):
        off = start + j * 4
        ins = rabbitizer.Instruction(w, vram + j * 4)
        op, rs, rt, rd, sa, f = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31, (w >> 6) & 31, w & 63
        imm = w & 65535
        signed = (imm ^ 32768) - 32768
        if off in branch_targets or (w >> 16 == 0x27BD and signed < 0):
            regs, stack = {0: 0}, {}
        dst, value = None, None
        if op == 15:
            dst, value = rt, imm << 16
        elif op in (8, 9, 12, 13, 14):
            dst = rt
            if rs in regs:
                value = (regs[rs] + signed if op in (8, 9) else
                         regs[rs] & imm if op == 12 else
                         regs[rs] | imm if op == 13 else regs[rs] ^ imm)
        elif op == 0 and f in (0, 2, 3, 32, 33, 34, 35, 36, 37, 38):
            dst = rd
            if f in (0, 2, 3) and rt in regs:
                value = regs[rt] << sa if f == 0 else regs[rt] >> sa
                if f == 3 and regs[rt] & 0x80000000:
                    value = (regs[rt] - 0x100000000) >> sa
            elif rs in regs and rt in regs:
                a, b = regs[rs], regs[rt]
                value = (a + b if f in (32, 33) else a - b if f in (34, 35)
                         else a & b if f == 36 else a | b if f == 37 else a ^ b)
        elif op == 43 and rs in (29, 30):
            # Only SP is generally trusted. FP stack aliases need a proven move.
            if rs == 29 or regs.get(30) == 'stack':
                stack[signed] = regs.get(rt)
        elif op == 35 and rs == 29:
            dst, value = rt, stack.get(signed)
        elif ins.modifiesRt():
            dst = rt
        elif ins.modifiesRd():
            dst = rd
        if dst:
            if value is None:
                regs.pop(dst, None)
            else:
                regs[dst] = value & 0xFFFFFFFF
        if pending:
            pc, target, kind = pending
            if kind == 'call':
                calls.append({'pc': pc, 'target': target, 'regs': dict(regs), 'stack': dict(stack)})
                for r in CALLER_SAVED:
                    regs.pop(r, None)
                stack = {}  # Do not reuse outgoing stack arguments across calls.
            else:
                regs, stack = {0: 0}, {}
            pending = None
        if op == 3:
            target = ((w & 0x3FFFFFF) << 2) | ((ins.vram + 4) & 0xF0000000)
            pending = (off, target, 'call')
        elif ins.hasDelaySlot():
            pending = (off, None, 'transfer')
    return calls


def text_prefix(data, start, end):
    """A bounded prefix, not proof of section boundaries or all executable bytes."""
    if end - start < 16:
        return None
    last_return = None
    for pos in range(start, end, 4):
        w = struct.unpack_from('>I', data, pos)[0]
        ins = rabbitizer.Instruction(w)
        # Avoid interpreting RSP jumps/vector words as VR4300 code.
        if not ins.isImplemented() or (w >> 26 in (2, 3) and 0x04001000 <= (w & 0x3FFFFFF) * 4 < 0x04002000):
            break
        if w == 0x03E00008:
            last_return = pos
    if last_return is None:
        return None
    stop = min(end, (last_return + 8 + 15) & ~15)
    prefix = words(data[start:stop])
    if len(prefix) < 4 or sum(w != 0 for w in prefix) / len(prefix) < 0.35:
        return None
    return stop


def discover(data, spec):
    regions = [{'id': 'resident', 'rom_start': 0x1000, 'rom_end': spec['resident_rom_end'],
                'vram': spec['entry'], 'text_end': spec['cpu_text_end'], 'confidence': 'high'}]
    seen = {(0x1000, spec['resident_rom_end'], spec['entry'])}
    loads = {}
    idx = 0
    while idx < len(regions):
        region = regions[idx]
        idx += 1
        for call in constant_calls(data, region['rom_start'], region['text_end'], region['vram']):
            if call['target'] != spec['dma_function']:
                continue
            r, s = call['regs'], call['stack']
            if spec['dma_convention'] == 'osPiStartDma':
                src, dest, size = r.get(7), s.get(16), s.get(20)
                # OS_READ (ROM -> RAM), as opposed to writes.
                if r.get(6) != 0:
                    continue
            else:
                src, dest, size = r.get(4), r.get(5), r.get(6)
            if not all(isinstance(x, int) for x in (src, dest, size)):
                continue
            if not (0x1000 <= src < len(data) and 0 < size <= 0x800000 and
                    src + size <= len(data) and 0x80000400 <= dest < 0x80800000 and
                    dest + size <= 0x80800000 and not ((src | size | dest) & 3)):
                continue
            key = src, src + size, dest
            item = loads.setdefault(key, {'rom_start': src, 'rom_end': src + size, 'vram': dest,
                                        'size': size, 'calls': []})
            evidence = {'region': region['id'], 'rom_pc': call['pc'],
                        'vram_pc': region['vram'] + call['pc'] - region['rom_start']}
            if evidence not in item['calls']:
                item['calls'].append(evidence)
            stop = text_prefix(data, src, src + size)
            if stop is not None and key not in seen:
                seen.add(key)
                regions.append({'id': f'load_{src:06X}_{dest:08X}', 'rom_start': src,
                                'rom_end': src + size, 'vram': dest, 'text_end': stop,
                                'confidence': 'medium: static DMA + instruction prefix'})
        if len(regions) > 300:
            raise RuntimeError('Discovery cap reached; do not report complete results')
    return regions, sorted(loads.values(), key=lambda x: (x['rom_start'], x['vram']))


def fingerprint(blob, vram):
    """Keep registers, constants and branch topology; remove external addresses.

    Relocation-insensitive, not a semantic equivalence test. Different compilers
    or register allocations may miss matches. Never masks arbitrary immediates.
    """
    original = words(blob)
    norm = list(original)
    for j, w in enumerate(original):
        op = w >> 26
        if op in (2, 3):
            target = (w & 0x3FFFFFF) * 4 | ((vram + j * 4 + 4) & 0xF0000000)
            norm[j] = (w & 0xFC000000) | ((target - vram) // 4 if vram <= target < vram + len(blob) else 0)
        if op == 15 and 0x8000 <= (w & 65535) <= 0x807F:
            reg = (w >> 16) & 31
            for k in range(j + 1, min(j + 7, len(original))):
                other = original[k]
                i = rabbitizer.Instruction(other)
                if (other >> 21) & 31 == reg and other >> 26 in (8, 9, 13, 32, 33, 35, 36, 37, 43, 49, 57):
                    norm[j] &= 0xFFFF0000
                    norm[k] &= 0xFFFF0000
                if i.modifiesRt() and ((other >> 16) & 31) == reg:
                    break
                if i.modifiesRd() and ((other >> 11) & 31) == reg:
                    break
                if i.hasDelaySlot():
                    break
    return hashlib.sha256(b''.join(w.to_bytes(4, 'big') for w in norm)).hexdigest()


def run_logged(command, logfile):
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open('w') as stream:
        p = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f'Exit {p.returncode}: {command}; see {logfile}')
    RUNS.append({'command': command, 'exit_code': p.returncode, 'log': str(logfile.relative_to(ROOT))})


def splat_config(game, spec):
    config = {
        'name': spec['title'], 'sha1': spec['sha1'],
        'options': {
            'basename': game, 'base_path': '../..', 'platform': 'n64',
            'compiler': spec['compiler_hint'], 'target_path': f'baseroms/{game}.z64',
            'asm_path': f'generated/{game}/splat/asm',
            'src_path': f'generated/{game}/splat/src',
            'asset_path': f'generated/{game}/splat/assets',
            'build_path': f'generated/{game}/splat/build',
            'generated_asm_macros_directory': f'generated/{game}/splat/include',
            'ld_script_path': f'generated/{game}/splat/{game}.ld',
            'cache_path': f'generated/{game}/splat/cache',
            'symbol_addrs_path': [], 'reloc_addrs_path': [],
            'undefined_funcs_auto_path': f'generated/{game}/splat/undefined_funcs.txt',
            'undefined_syms_auto_path': f'generated/{game}/splat/undefined_syms.txt',
            'auto_link_sections': [], 'header_encoding': 'ASCII' if game == 'ozumo1' else 'shift_jis',
            'find_file_boundaries': False,
        },
        'segments': [
            {'name': 'header', 'type': 'header', 'start': 0},
            {'name': 'ipl3', 'type': 'bin', 'start': 0x40},
            {'name': 'resident', 'type': 'code', 'start': 0x1000, 'vram': spec['entry'],
             'subsegments': [[0x1000, 'asm', 'resident'], [spec['cpu_text_end'], 'data', 'resident']]},
            {'name': 'unclassified', 'type': 'bin', 'start': spec['resident_rom_end']},
            [spec['size']],
        ],
    }
    path = ROOT / 'config' / 'splat' / f'{game}.yaml'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# CPU/RSP boundary inspected manually; data includes RSP code, not only CPU data.\n' +
                    yaml.dump(config, Dumper=HexDumper, sort_keys=False, allow_unicode=True))
    return path


def disassemble(game, data, regions, spec):
    config = splat_config(game, spec)
    run_logged([sys.executable, '-m', 'splat', 'split', str(config), '--modes', 'code'],
               OUT / game / 'splat.log')
    functions = []
    for region in regions:
        folder = OUT / game / 'spim' / region['id']
        info = folder / 'functions.csv'
        run_logged([sys.executable, '-m', 'spimdisasm', 'singleFileDisasm',
                    str(ROOT / 'baseroms' / (game + '.z64')), str(folder),
                    '--start', hx(region['rom_start']), '--end', hx(region['text_end']),
                    '--vram', hx(region['vram']), '--compiler', spec['compiler_hint'],
                    '--function-info', str(info), '--save-context', str(folder / 'context.csv'),
                    '--no-write-binary', '--quiet'], folder / 'run.log')
        with info.open() as stream:
            for row in csv.DictReader(stream):
                start, vram, size = [int(row[k], 16) for k in ('vrom', 'address', 'length')]
                assert region['rom_start'] <= start < start + size <= region['text_end']
                blob = data[start:start + size]
                ws = words(blob)
                functions.append({'region': region['id'], 'rom': start, 'vram': vram,
                                  'size': size, 'name': row['name'],
                                  'sha256': hashlib.sha256(blob).hexdigest(),
                                  'normalized': fingerprint(blob, vram),
                                  'eligible': size >= 64 and sum(w != 0 for w in ws) >= 12 and 0x03E00008 in ws,
                                  'jal': sum(w >> 26 == 3 for w in ws),
                                  'jalr': sum(w >> 26 == 0 and (w & 63) == 9 for w in ws),
                                  'jr_indirect': sum(w >> 26 == 0 and (w & 63) == 8 and w != 0x03E00008 for w in ws)})
    return functions


def signatures(data):
    return [{'rom': m.start(), 'text': m.group().decode('ascii')}
            for m in re.finditer(rb'RSP Gfx ucode [\x20-\x7e]{5,85}', data)]


def graphics(data):
    """Static FD/F5/F3 or FD/F5/F4 chains. Still candidates until address resolution."""
    result = []
    fmts, bits = ['RGBA', 'YUV', 'CI', 'IA', 'I'], [4, 8, 16, 32]
    known = {0x00, 0x01, 0x03, 0x04, 0x06, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
             0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
             0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF,
             0xF0, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF}
    for off in range(0x1000, len(data) - 8 * 12, 8):
        w, addr = struct.unpack_from('>II', data, off)
        fmt, siz = (w >> 21) & 7, (w >> 19) & 3
        if w >> 24 != 0xFD or w & 0x0007F000 or fmt > 4:
            continue
        cmds = [0xFD]
        for pos in range(off + 8, off + 8 * 12, 8):
            cmd = data[pos]
            if cmd in (0xFD, 0xB8):
                break
            cmds.append(cmd)
        if len(cmds) < 5 or 0xF5 not in cmds or not ({0xF3, 0xF4} & set(cmds)) or sum(c in known for c in cmds) / len(cmds) < 0.8:
            continue
        tiles, bounds = [], []
        for pos in range(off + 8, off + 8 * 12, 8):
            a, b = struct.unpack_from('>II', data, pos)
            if a >> 24 in (0xFD, 0xB8):
                break
            tile = (b >> 24) & 7
            if a >> 24 == 0xF5 and tile != 7 and (a >> 21) & 7 <= 4:
                tiles.append({'tile': tile, 'format': fmts[(a >> 21) & 7], 'bits': bits[(a >> 19) & 3]})
            if a >> 24 == 0xF2:
                width = (((b >> 12) & 4095) - ((a >> 12) & 4095)) // 4 + 1
                height = ((b & 4095) - (a & 4095)) // 4 + 1
                if 0 < width <= 1024 and 0 < height <= 1024:
                    bounds.append({'tile': tile, 'width': width, 'height': height})
        result.append({'rom': off, 'load_format': fmts[fmt], 'load_bits': bits[siz],
                       'render_tiles': tiles, 'tile_bounds': bounds,
                       'width_field': (w & 4095) + 1, 'image_address': addr,
                       'confidence': 'candidate: static command chain; not a decoded image'})
    return result


def n64_crc(data):
    # CIC 6102 checksum, over original bytes 0x1000..0x101000.
    seed = 0xF8CA4DDC
    t1 = t2 = t3 = t4 = t5 = t6 = seed
    mask = 0xFFFFFFFF
    for d in words(data[0x1000:0x101000]):
        if t6 + d > mask:
            t4 = (t4 + 1) & mask
        t6 = (t6 + d) & mask
        t3 ^= d
        shift = d & 31
        r = ((d << shift) | (d >> ((32 - shift) & 31))) & mask
        t5 = (t5 + r) & mask
        t2 ^= r if t2 > d else t6 ^ d
        t1 = (t1 + (t5 ^ d)) & mask
    return [(t6 ^ t4 ^ t3) & mask, (t5 ^ t2 ^ t1) & mask]


def memory_map(game, spec, regions, loads):
    rows = [{'kind': 'header', 'rom_start': 0, 'rom_end': 0x40, 'vram': None, 'vram_end': None, 'confidence': 'confirmed header'},
            {'kind': 'IPL3', 'rom_start': 0x40, 'rom_end': 0x1000, 'vram': None, 'vram_end': None, 'confidence': 'boot cartridge bytes'},
            {'kind': 'resident CPU text', 'rom_start': 0x1000, 'rom_end': spec['cpu_text_end'], 'vram': spec['entry'],
             'vram_end': spec['entry'] + spec['cpu_text_end'] - 0x1000, 'confidence': 'high: entry, calls, RSP boundary'},
            {'kind': 'resident RSP + data', 'rom_start': spec['cpu_text_end'], 'rom_end': spec['resident_rom_end'],
             'vram': spec['entry'] + spec['cpu_text_end'] - 0x1000, 'vram_end': spec['bss_start'], 'confidence': 'mixed; no exact data/rodata split'},
            {'kind': 'resident BSS', 'rom_start': None, 'rom_end': None, 'vram': spec['bss_start'],
             'vram_end': spec['bss_start'] + spec['bss_size'], 'confidence': 'confirmed boot zero loop'}]
    code = {(r['rom_start'], r['rom_end'], r['vram']): r for r in regions}
    for load in loads:
        key = load['rom_start'], load['rom_end'], load['vram']
        row = {k: load[k] for k in ('rom_start', 'rom_end', 'vram')}
        row.update(vram_end=load['vram'] + load['size'], kind='DMA code candidate' if key in code else 'DMA data/unclassified',
                   confidence='static constant call; execution not traced')
        rows.append(row)
    fields = ['kind', 'rom_start', 'rom_end', 'vram', 'vram_end', 'confidence']
    save_csv(METRICS / f'{game}-memory-map.csv',
             [{k: hx(v) if isinstance(v, int) else v for k, v in row.items()} for row in rows], fields)


def analyze(game, spec):
    data = (ROOT / 'baseroms' / (game + '.z64')).read_bytes()
    validate(data, spec)
    regions, loads = discover(data, spec)
    print(f'{game}: {len(loads)} static DMA mappings; {len(regions)} CPU regions', flush=True)
    functions = disassemble(game, data, regions, spec)
    sigs, gfx = signatures(data), graphics(data)
    overlap = []
    for i, a in enumerate(loads):
        for b in loads[i + 1:]:
            lo, hi = max(a['vram'], b['vram']), min(a['vram'] + a['size'], b['vram'] + b['size'])
            if lo < hi and (a['rom_start'] - a['vram']) != (b['rom_start'] - b['vram']):
                overlap.append({'a_rom': a['rom_start'], 'b_rom': b['rom_start'], 'vram_start': lo, 'vram_end': hi})
    crc = n64_crc(data)
    expected_crc = list(struct.unpack_from('>II', data, 0x10))
    assert crc == expected_crc, 'CIC6102 CRC mismatch'
    # A full-ROM density scan is triage only, independent of discovered load mappings.
    density = []
    for start in range(0x1000, len(data), 0x1000):
        ws = words(data[start:start+0x1000])
        prologues = sum(w >> 16 == 0x27BD and bool(w & 0x8000) and w & 7 == 0 for w in ws)
        returns = ws.count(0x03E00008)
        if prologues >= 3 and returns >= 2:
            density.append({'rom': start, 'stack_decrements': prologues, 'jr_ra': returns})
    uncovered = [x for x in density if not any(max(r['rom_start'], x['rom']) < min(r['text_end'], x['rom'] + 0x1000) for r in regions)]
    result = {'game': game, 'rom_sha256': spec['sha256'], 'size': len(data),
              'entry': spec['entry'], 'startup': spec['startup'], 'initial_sp': spec['initial_sp'],
              'bss': [spec['bss_start'], spec['bss_start'] + spec['bss_size']],
              'crc6102': {'computed': list(map(hx, crc)), 'header': list(map(hx, expected_crc)), 'valid': True},
              'regions': regions, 'dma_loads': loads, 'overlap_pairs': overlap,
              'ucode_signatures': sigs, 'graphics_candidates': gfx,
              'function_count': len(functions), 'function_boundaries': 'spimdisasm heuristic, not source-level ground truth',
              'indirect_calls': sum(f['jalr'] for f in functions),
              'indirect_jumps': sum(f['jr_indirect'] for f in functions),
              'density_candidates': density, 'uncovered_density_candidates': uncovered,
              'compression_markers': {s.decode(): data.count(s) for s in (b'MIO0', b'Yay0', b'Yaz0')},
              'render_format_counts': dict(Counter(f"{t['format']}{t['bits']}" for x in gfx for t in x['render_tiles']))}
    save_json(METRICS / f'{game}.json', result)
    save_csv(METRICS / f'{game}-functions.csv', functions,
             ['region', 'rom', 'vram', 'size', 'name', 'sha256', 'normalized', 'eligible', 'jal', 'jalr', 'jr_indirect'])
    memory_map(game, spec, regions, loads)
    # No full strings, textures, assembly or original game content goes into reports.
    assert hashlib.sha256((ROOT / 'baseroms' / (game + '.z64')).read_bytes()).hexdigest() == spec['sha256']
    return result, functions


def compare(all_results):
    a, b = all_results['ozumo1'][1], all_results['ozumo2'][1]
    matches = []
    for method in ('sha256', 'normalized'):
        ia, ib = defaultdict(list), defaultdict(list)
        for f in a:
            if f['eligible']:
                ia[f[method]].append(f)
        for f in b:
            if f['eligible']:
                ib[f[method]].append(f)
        for digest in sorted(ia.keys() & ib.keys()):
            fa, fb = ia[digest], ib[digest]
            matches.append({'method': method, 'digest': digest, 'size': fa[0]['size'],
                            'unique_pair': len(fa) == len(fb) == 1,
                            'ozumo1': [{k: f[k] for k in ('region', 'rom', 'vram')} for f in fa],
                            'ozumo2': [{k: f[k] for k in ('region', 'rom', 'vram')} for f in fb]})
    save_json(METRICS / 'shared-functions.json', matches)
    d1, d2 = [(ROOT / 'baseroms' / (g + '.z64')).read_bytes() for g in ('ozumo1', 'ozumo2')]
    summary = {'tools': {p: version(p) for p in ('splat64', 'spimdisasm', 'rabbitizer')},
               'ipl3_identical': d1[0x40:0x1000] == d2[0x40:0x1000],
               'commands_completed': len(RUNS),
               'matches': dict(Counter(m['method'] for m in matches)),
               'unique_pairs': dict(Counter(m['method'] for m in matches if m['unique_pair'])),
               'games': {g: {'functions': x[0]['function_count'], 'regions': len(x[0]['regions']),
                             'dma_mappings': len(x[0]['dma_loads']), 'graphics_candidates': len(x[0]['graphics_candidates']),
                             'ucode_signatures': len(x[0]['ucode_signatures']),
                             'indirect_calls': x[0]['indirect_calls'], 'indirect_jumps': x[0]['indirect_jumps']}
                         for g, x in all_results.items()}}
    save_json(METRICS / 'summary.json', summary)
    save_json(OUT / 'run-manifest.json', RUNS)
    print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    specs = json.loads((ROOT / 'config/roms.json').read_text())
    results = {g: analyze(g, spec) for g, spec in specs.items()}
    compare(results)


if __name__ == '__main__':
    main()
