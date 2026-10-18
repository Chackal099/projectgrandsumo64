#!/usr/bin/env python3
"""Prepare Project64 captures and reconcile observations with retained static evidence.

No disassembly, ROM patching, emulation or invented observations occur here.
Python 3.10+, standard library only. Run outputs belong under ignored local/.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parents[2]
ROM_SHA256 = '3ff701b4735c84b17f8d80a996db59801caa766ee7da4d3e5a3b88eb34d99a17'
PROJECT64_REVISION = '24376e868350792a181d2121fec20d37354559d6'
ADAPTER_REVISION = 'ozumo2-pj64-v1'
SCHEMA = 2


def sha(data):
    return hashlib.sha256(data).hexdigest()


def address(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{8}', value):
        raise ValueError(f'Invalid 32-bit address: {value!r}')
    return int(value, 16)


def hx(value):
    return f'0x{value:08X}'


def physical(value):
    value = address(value) if isinstance(value, str) else value
    return value & 0x1FFFFFFF if 0x80000000 <= value < 0xC0000000 else None


def positive(value, limit=8 * 1024 * 1024):
    if type(value) is not int or not 0 < value <= limit:
        raise ValueError(f'Invalid byte count: {value!r}')
    return value


def subtract(spans, start, end):
    result = []
    for lo, hi in spans:
        if end <= lo or start >= hi:
            result.append((lo, hi))
        else:
            if lo < start:
                result.append((lo, start))
            if end < hi:
                result.append((end, hi))
    return result


def covering(images, start, size=4):
    if start is None:
        return None
    for image in reversed(images):
        if any(lo <= start and start + size <= hi for lo, hi in image['live']):
            return image
    return None


def static_evidence():
    path = ROOT / 'reports/evidence/ozumo2.json'
    return json.loads(path.read_text(encoding='utf-8')), sha(path.read_bytes())


def static_rows(evidence):
    regions = {(r['rom_start'], r['vram']): r for r in evidence['regions']}
    return [dict(rom_start=hx(d['rom_start']), rom_end=hx(d['rom_end']),
                 vram=hx(d['vram']), byte_count=d['size'],
                 static_cpu_candidate=(d['rom_start'], d['vram']) in regions,
                 status='not_seen', visible_transfers=0, executed_transfers=0, mismatches=0)
            for d in evidence['dma_loads']]


def matching_rows(rows, rom_start, dest, size):
    """Include PI chunks only if the source->destination offset agrees exactly."""
    for row in rows:
        lo, hi = address(row['rom_start']), address(row['rom_end'])
        base = physical(row['vram'])
        if base is not None and dest - rom_start == base - lo and lo < rom_start + size and rom_start < hi:
            yield row


def reconcile(session, events, rom, evidence, functions=None):
    """Strict event validation, independently checked ROM hashes and partial liveness.

    A synthetic session is allowed for unit tests but remains labelled synthetic.
    Only operator-closed emulator sessions can receive a complete capture status.
    """
    if session.get('schema_version') != SCHEMA or session.get('rom_sha256') != sha(rom):
        raise ValueError('Session schema or ROM identity mismatch')
    if session.get('source_kind') not in ('emulator', 'synthetic_test'):
        raise ValueError('Unsupported capture provenance')
    rows = static_rows(evidence)
    images, submissions, wrappers, tasks, indirect = [], {}, {}, [], []
    counts, markers, unknown = {}, [], []
    seq, step, started, stopped = 0, 0, False, None
    watch_writes = False
    issues = []
    functions = sorted(functions or [], key=lambda f: int(f['rom']))
    function_starts = [int(f['rom']) for f in functions]
    ram_size = session['rdram_bytes']
    if ram_size not in (4 * 1024 * 1024, 8 * 1024 * 1024):
        raise ValueError('Unsupported session RAM size')
    def invalidate(start, end, cause):
        for image in images:
            if any(start < hi and lo < end for lo, hi in image['live']):
                image['invalidations'].append({'sequence': seq, 'start': hx(start), 'end': hx(end), 'cause': cause})
                image['live'] = subtract(image['live'], start, end)
    for e in events:
        if stopped:
            raise ValueError('Events after capture_stop')
        if (e.get('schema_version') != SCHEMA or e.get('run_id') != session['run_id']
                or type(e.get('sequence')) is not int or e['sequence'] != seq + 1
                or type(e.get('cpu_step')) is not int or e['cpu_step'] < step):
            raise ValueError('Non-contiguous sequence, CPU step or run/schema mismatch')
        seq, step = e['sequence'], e['cpu_step']
        kind = e['event']
        if not started and kind != 'capture_start':
            raise ValueError('First event must be capture_start')
        counts[kind] = counts.get(kind, 0) + 1
        if kind == 'capture_start':
            if started or e['rom_sha256'] != sha(rom) or e['rdram_bytes'] != ram_size:
                raise ValueError('Captured ROM/RAM identity mismatch or duplicate start')
            if e['source_kind'] != session['source_kind']:
                raise ValueError('Capture/session provenance mismatch')
            if e.get('cpu_mode') != 'interpreter':
                raise ValueError('Execution hooks require interpreter mode')
            watch_writes = e.get('watch_writes', session['source_kind'] == 'synthetic_test') is True
            if not watch_writes:
                issues.append({'sequence': seq, 'reason': 'CPU stores unobserved; execution cannot confirm ROM provenance'})
            started = True
        elif kind == 'dma_submit':
            key = e['transfer_id']
            if key in submissions:
                raise ValueError('Duplicate transfer ID')
            size = positive(e['byte_count'], 0x1000000)
            submissions[key] = dict(e, size=size)
            dest = physical(e['dest_vram'])
            if e['direction'] == 'cart_to_ram' and dest is not None and dest + size <= ram_size:
                invalidate(dest - dest % 8, min(ram_size, (dest+size+7)//8*8+8), 'PI_submit_conservative')
        elif kind == 'overwrite' or kind == 'write_attempt':
            start = address(e['start_physical'])
            end = start + positive(e['byte_count'])
            if end > ram_size:
                raise ValueError('Invalid RAM invalidation span')
            invalidate(start, end, e.get('cause', kind))
        elif kind in ('dma_visible', 'resident_visible'):
            key = e['transfer_id']
            lo, dest, size = address(e['rom_start']), physical(e['dest_vram']), positive(e['byte_count'])
            if dest is None or dest + size > ram_size or lo + size > len(rom):
                raise ValueError('Visible transfer outside ROM/RAM')
            if any(i['id'] == key for i in images):
                raise ValueError('Duplicate materialization ID')
            if kind == 'dma_visible':
                submission = submissions.get(key)
                if submission is None or submission.get('visible'):
                    raise ValueError('Missing or repeated PI submission')
                cart = physical(submission['cart_address'])
                if (submission['direction'] != 'cart_to_ram' or cart != lo + 0x10000000
                        or physical(submission['dest_vram']) != dest or submission['size'] != size):
                    raise ValueError('PI submission/visibility mismatch')
                submission['visible'] = True
            elif (lo, dest, size) != (0x1000, 0x80400, 0x4AF50 - 0x1000):
                raise ValueError('Unexpected resident bootstrap image')
            digest = sha(rom[lo:lo+size])
            matched = e.get('ram_sha256') == digest and e.get('rom_sha256') == digest
            affected = list(matching_rows(rows, lo, dest, size))
            for row in affected:
                row['visible_transfers' if matched else 'mismatches'] += 1
                row['status'] = ('loaded_not_executed' if matched else 'mismatch') if row['status'] != 'executed' else 'executed'
            if not matched:
                issues.append({'sequence': seq, 'reason': 'RAM/ROM digest mismatch', 'transfer_id': key})
            # Never accept producer claims about generation identity without a verified hash.
            images.append(dict(id=key, rom_start=lo, dest=dest, size=size, hash_match=matched,
                               live=[(dest, dest+size)] if matched else [], sequence=seq,
                               first_exec=None, last_exec=None, exec_observations=0,
                               contexts=[], observed_functions=[], invalidations=[],
                               static_matches=[rows.index(r) for r in affected], executed_static_matches=[]))
        elif kind == 'exec':
            p = physical(e['pc'])
            image = covering(images, p) if watch_writes else None
            if image and e.get('image_id') != image['id']:
                raise ValueError('Execution generation disagrees with verified live memory')
            if image:
                image['first_exec'] = image['first_exec'] or seq
                image['last_exec'] = seq
                image['exec_observations'] += 1
                if e.get('context') not in image['contexts']:
                    image['contexts'].append(e.get('context'))
                rom_pc = image['rom_start'] + p - image['dest']
                index = bisect_right(function_starts, rom_pc)-1
                if index >= 0:
                    function = functions[index]
                    if (rom_pc < int(function['rom'])+int(function['size'])
                            and physical(int(function['vram'])) == image['dest']+int(function['rom'])-image['rom_start']):
                        name = function['region']+':'+function['name']
                        if name not in image['observed_functions']:
                            image['observed_functions'].append(name)
                for index in image['static_matches']:
                    row = rows[index]
                    if address(row['rom_start']) <= rom_pc < address(row['rom_end']):
                        row['status'] = 'executed'
                        if index not in image['executed_static_matches']:
                            image['executed_static_matches'].append(index)
            else:
                if e.get('image_id') is not None and watch_writes:
                    issues.append({'sequence': seq, 'reason': 'Claimed image is not live/verified', 'pc': e['pc']})
                if len(unknown) < 100:
                    unknown.append({'sequence': seq, 'pc': e['pc'], 'claimed_image': e.get('image_id')})
        elif kind == 'wrapper_submit':
            if e['call_id'] in wrappers:
                raise ValueError('Duplicate wrapper call ID')
            wrappers[e['call_id']] = dict(e, returned=False, pi_transfers=[])
        elif kind == 'wrapper_return':
            call = wrappers.get(e['call_id'])
            if (not call or call['returned'] or call['caller_ra'] != e['pc']
                    or call['caller_sp'] != e['caller_sp']):
                raise ValueError('Unmatched wrapper return')
            call['returned'] = True
            # Match covered subranges within the call lifetime. Scheduler threads
            # are unknown: an overlap is a candidate correlation, never a queue proof.
            for image in images:
                if call['sequence'] < image['sequence'] < seq:
                    start = address(call['rom_start'])
                    size = call['byte_count']
                    dest = physical(call['dest_vram'])
                    if (dest is not None and start <= image['rom_start'] and image['rom_start'] + image['size'] <= start+size
                            and image['dest'] - image['rom_start'] == dest-start):
                        call['pi_transfers'].append(image['id'])
        elif kind == 'marker':
            markers.append({'sequence': seq, 'name': e['name']})
        elif kind == 'indirect':
            indirect.append(dict(e, confirmation=None))
        elif kind == 'indirect_outcome':
            found = next((i for i in reversed(indirect) if i['branch_id'] == e['branch_id']), None)
            if found is None:
                raise ValueError('Unmatched indirect outcome')
            found['confirmation'] = dict(e)
        elif kind == 'rsp_task':
            task = dict(e, mapped_components=[])
            for prefix in ('ucode', 'ucode_data'):
                size = e[prefix+'_size']
                p = physical(e[prefix+'_vram'])
                image = covering(images, p, size) if type(size) is int and size > 0 else None
                if image:
                    start = image['rom_start'] + p - image['dest']
                    expected = sha(rom[start:start+size])
                    task['mapped_components'].append(dict(component=prefix, image_id=image['id'],
                        rom_start=hx(start), byte_count=size, hash_match=e.get(prefix+'_sha256') == expected,
                        static_signature_offsets=[hx(s['rom']) for s in evidence['ucode_signatures'] if start <= s['rom'] < start+size]))
            tasks.append(task)
        elif kind == 'emulator_state':
            # Reset state is explicitly supplied by adapter, with no inferred lifecycle.
            if e.get('memory_reset'):
                for image in images:
                    if image['live']:
                        image['invalidations'].append({'sequence': seq, 'cause': 'emulator_reset'})
                    image['live'] = []
        elif kind == 'capture_stop':
            stopped = e
        elif kind not in ('boot_checkpoint', 'input_poll', 'callback_write', 'rsp_task_upload', 'sdk_call'):
            raise ValueError(f'Unknown event kind: {kind}')
    if not started:
        raise ValueError('Trace contains no capture_start')
    for row_index, row in enumerate(rows):
        row['executed_transfers'] = sum(row_index in i['executed_static_matches'] for i in images)
        row['status'] = ('executed' if row['status'] == 'executed' else
                         'loaded_not_executed' if row['visible_transfers'] else
                         'mismatch' if row['mismatches'] else 'not_seen')
    for image in images:
        image['lifecycle'] = ('partial_overwrite_unresolved' if image['invalidations'] and image['live'] else
                              'invalidated' if image['invalidations'] else 'end_not_observed')
        image['live'] = [[hx(lo), hx(hi)] for lo, hi in image['live']]
        image['rom_start'], image['dest'] = hx(image['rom_start']), hx(image['dest']+0x80000000)
        image['status'] = 'executed' if image['first_exec'] else ('loaded_not_executed' if image['hash_match'] else 'mismatch')
    complete = bool(stopped and stopped['reason'] == 'operator' and not stopped['pending_pi'] and not stopped['pending_wrappers'])
    source = session['source_kind']
    return dict(schema_version=SCHEMA, run_id=session['run_id'], source_kind=source,
                capture_status=('closed' if complete else 'incomplete') if source == 'emulator' else 'synthetic_test',
                rom_sha256=sha(rom), event_counts=counts, markers=markers, issues=issues,
                cpu_writes_observed=watch_writes,
                static_comparison=rows, images=images, rsp_tasks=tasks, indirect=indirect,
                wrapper_calls=list(wrappers.values()), unknown_exec_samples=unknown,
                limitations=['Dispatch hooks precede instruction execution; no retirement claim.',
                             'Loaded without PC observations does not establish data_only.',
                             'CPU stores invalidate conservatively; RSP-initiated writes and TLB mappings are not fully covered.',
                             'VI acknowledgements and PIF polls are not a VI or simulation tick count.',
                             'Wrapper correlations by interval/RA/SP do not establish thread or queue identity.'])


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def write_rows(path, rows):
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def private_dir(value):
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT / 'local'):
        raise ValueError('Capture and derived outputs must be inside the ignored repository local/ directory')
    return path


def read_rom(path):
    rom = Path(path).read_bytes()
    if sha(rom) != ROM_SHA256:
        raise ValueError('ROM SHA-256 differs from the previously investigated revision')
    return rom


def prepare(args):
    rom = read_rom(args.rom)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_id):
        raise ValueError('Use a simple unique run ID (letters/digits/_/-)')
    positive(args.max_events, 100_000_000)
    exe = Path(args.emulator_exe).resolve()
    exe_hash = sha(exe.read_bytes())
    saves = [{'name': Path(p).name, 'sha256': sha(Path(p).read_bytes())} for p in args.save]
    run = ROOT / 'local/traces/ozumo2' / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    session = dict(schema_version=SCHEMA, run_id=args.run_id, state='prepared_not_captured',
        source_kind='emulator', rom_sha256=sha(rom), rom_size=len(rom), rdram_bytes=args.rdram_mib*1024*1024,
        emulator={'name':'Project64','revision':args.emulator_revision,'executable_sha256':exe_hash,
                  'cpu_mode':'interpreter','backends':args.backend},
        initial_saves=saves, empty_save_declared=args.empty_save,
        cold_boot_required=True, adapter_revision=ADAPTER_REVISION,
        events='events.jsonl', input_recording='input_poll events in events.jsonl',
        notes='Preparation is not a real capture; no scene has been observed.')
    cfg = dict(run_id=args.run_id, rom_sha256=sha(rom), rom_size=len(rom), rdram_bytes=session['rdram_bytes'],
               adapter_revision=ADAPTER_REVISION,emulator_revision=args.emulator_revision,
               events=(run/'events.jsonl').as_posix(), control=(run/'control.json').as_posix(),
               watch_writes=not args.no_watch_writes,max_events=args.max_events)
    script = 'var OZTRACE = '+json.dumps(cfg,ensure_ascii=True)+';\n'
    for filename in ('sha256.js','project64.js'):
        script += (Path(__file__).parent/filename).read_text(encoding='utf-8')+'\n'
    session['adapter_sha256'] = sha(script.encode())
    write_json(run/'session.json',session)
    (run/'capture.js').write_text(script,encoding='utf-8')
    print(run)
    print('Copy capture.js into the Project64 Scripts directory. See re/ozumo2/dynamic/windows.md.')


def command(args):
    run = private_dir(args.run_dir)
    session=json.loads((run/'session.json').read_text(encoding='utf-8'))
    if session['schema_version'] != SCHEMA:
        raise ValueError('Unexpected session schema')
    target=run/'control.json'
    if target.exists():
        previous=json.loads(target.read_text(encoding='utf-8'))
        events=run/'events.jsonl'
        observed=[json.loads(line) for line in events.read_text(encoding='utf-8').splitlines()] if events.exists() else []
        if any(e['event']=='capture_stop' for e in observed):
            raise ValueError('Capture already stopped; prepare a new run')
        applied=any(e.get('command_id')==previous['id'] for e in observed)
        if not applied:
            raise ValueError('Previous command has not been acknowledged; resume emulator and wait')
    value=dict(id=uuid.uuid4().hex,event='stop' if args.stop else 'marker',name=args.marker,note=args.note)
    temporary=run/('control-'+uuid.uuid4().hex+'.tmp')
    write_json(temporary,value)
    os.replace(temporary,target)
    print('Command queued; resume CPU and wait for the OZTRACE acknowledgement in Project64.')


def summarize(args):
    run=private_dir(args.run_dir)
    session=json.loads((run/'session.json').read_text(encoding='utf-8'))
    rom=read_rom(args.rom)
    script=(run/'capture.js').read_bytes()
    if sha(script) != session['adapter_sha256']:
        raise ValueError('Capture script differs from the prepared manifest')
    path=run/session['events']
    def events():
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                yield json.loads(line)
    evidence,evidence_hash=static_evidence()
    with (ROOT/'reports/evidence/ozumo2-functions.csv').open(newline='') as stream:
        functions=list(csv.DictReader(stream))
    result=reconcile(session,events(),rom,evidence,functions)
    result['events_sha256']=sha(path.read_bytes())
    result['static_evidence_sha256']=evidence_hash
    result['static_sources']={name:sha((ROOT/name).read_bytes()) for name in
        ('config/splat/ozumo2.yaml','reports/evidence/ozumo2-memory-map.csv','reports/evidence/ozumo2-functions.csv')}
    # A unique output directory preserves previous reconciliations and raw traces.
    out=run/('summary-'+uuid.uuid4().hex[:12])
    out.mkdir()
    write_json(out/'overlays.json',result)
    write_rows(out/'static-comparison.csv',result['static_comparison'])
    observed=[i for i in result['images'] if i['status']=='executed']
    lines=['# Observações dinâmicas — '+session['run_id'],'',
           f"Proveniência: **{result['source_kind']}**. Captura: **{result['capture_status']}**.",
           f"Imagens com PC correlacionado e hash válido: **{len(observed)}**.",'',
           '| Imagem | ROM | RAM | Bytes | Contextos |','| --- | --- | --- | ---: | --- |']
    for i in observed:
        contexts=', '.join(str(c).replace('|','/') for c in i['contexts'])
        lines.append(f"| {i['id']} | {i['rom_start']} | {i['dest']} | {i['size']} | {contexts} |")
    if not observed:
        lines += ['','Nenhum overlay executado foi confirmado por este trace.']
    lines += ['','A tabela enumera gerações observadas; não comprova fronteiras completas de módulos.',
              'Consulte overlays.json para invalidações parciais, divergências e pendências.']
    (out/'observations.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(out)
    print(json.dumps({'capture_status':result['capture_status'],'verified_executed_images':len(observed),
                      'issues':len(result['issues'])}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare',help='Create a new local capture session without running the game')
    p.add_argument('--run-id',required=True)
    p.add_argument('--rom',default=str(ROOT/'baseroms/ozumo2.z64'))
    p.add_argument('--emulator-exe',required=True)
    p.add_argument('--emulator-revision',default=PROJECT64_REVISION)
    p.add_argument('--backend',action='append',required=True,help='Record each graphics/audio/RSP/input plugin and version')
    p.add_argument('--rdram-mib',type=int,choices=(4,8),required=True)
    saves=p.add_mutually_exclusive_group(required=True)
    saves.add_argument('--save',action='append',default=[])
    saves.add_argument('--empty-save',action='store_true')
    p.add_argument('--no-watch-writes',action='store_true',help='Weaker invalidation coverage, for performance diagnosis only')
    p.add_argument('--max-events',type=int,default=2000000)
    p.set_defaults(func=prepare)
    p=sub.add_parser('command',help='Queue marker or stop; applied by the CPU callback')
    p.add_argument('--run-dir',required=True)
    choice=p.add_mutually_exclusive_group(required=True)
    choice.add_argument('--marker')
    choice.add_argument('--stop',action='store_true')
    p.add_argument('--note',default='')
    p.set_defaults(func=command)
    p=sub.add_parser('summarize',help='Verify real traces against the unchanged ROM and retained static map')
    p.add_argument('--run-dir',required=True)
    p.add_argument('--rom',default=str(ROOT/'baseroms/ozumo2.z64'))
    p.set_defaults(func=summarize)
    args=parser.parse_args()
    try:
        args.func(args)
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as error:
        parser.exit(1,f'Error: {error}\n')


if __name__=='__main__':
    main()
