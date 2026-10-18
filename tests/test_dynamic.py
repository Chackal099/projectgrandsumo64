"""Synthetic trace tests. None of these observations come from a game capture."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.dynamic import trace
from tools.dynamic.check_adapter import run_node


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.rom=bytes((i*17+i//256*29+13)&255 for i in range(4096))
        self.session=dict(schema_version=2,run_id='SYNTHETIC',source_kind='synthetic_test',
                          rom_sha256=trace.sha(self.rom),rdram_bytes=4*1024*1024)
        self.evidence=dict(regions=[dict(rom_start=256,vram=0x8012c860)],
                           dma_loads=[dict(rom_start=256,rom_end=320,vram=0x8012c860,size=64),
                                      dict(rom_start=512,rom_end=640,vram=0x8012c860,size=128)],
                           ucode_signatures=[])
        self.events=[]
        self.add('capture_start',rom_sha256=trace.sha(self.rom),rdram_bytes=4*1024*1024,
                 source_kind='synthetic_test',cpu_mode='interpreter')

    def add(self,kind,**values):
        self.events.append(dict(schema_version=2,run_id='SYNTHETIC',sequence=len(self.events)+1,
                                cpu_step=len(self.events),event=kind,context='test',**values))

    def load(self,key,start,size,dest=0x8012c860,bad=False):
        self.add('dma_submit',transfer_id=key,layer='PI',direction='cart_to_ram',
                 cart_address=trace.hx(0xb0000000+start),dest_vram=trace.hx(dest),byte_count=size)
        digest=trace.sha(self.rom[start:start+size])
        self.add('dma_visible',transfer_id=key,rom_start=trace.hx(start),dest_vram=trace.hx(dest),
                 byte_count=size,ram_sha256='0'*64 if bad else digest,rom_sha256=digest)

    def result(self):
        return trace.reconcile(self.session,self.events,self.rom,self.evidence)

    def test_submit_is_not_visible_or_executed(self):
        self.add('dma_submit',transfer_id='p1',direction='cart_to_ram',cart_address='0xB0000100',
                 dest_vram='0x8012C860',byte_count=64)
        self.add('exec',pc='0x8012C860',image_id=None)
        result=self.result()
        self.assertEqual(result['images'],[])
        self.assertEqual(result['static_comparison'][0]['status'],'not_seen')

    def test_visible_data_is_not_automatically_cpu_code(self):
        self.load('p1',256,64)
        self.assertEqual(self.result()['static_comparison'][0]['status'],'loaded_not_executed')

    def test_alias_pc_confirms_execution(self):
        self.load('p1',256,64)
        self.add('exec',pc='0xA012C864',image_id='p1')
        result=self.result()
        self.assertEqual(result['static_comparison'][0]['status'],'executed')
        self.assertEqual(result['capture_status'],'synthetic_test')

    def test_b_to_a_partial_overwrite_and_a_b_a_identity(self):
        self.load('a1',256,64)
        self.add('exec',pc='0x8012C860',image_id='a1')
        self.load('b1',512,128)
        self.add('exec',pc='0x8012C860',image_id='b1')
        self.load('a2',256,64)
        self.add('exec',pc='0x8012C860',image_id='a2')
        images=self.result()['images']
        self.assertEqual([i['id'] for i in images],['a1','b1','a2'])
        self.assertEqual(images[0]['live'],[])
        self.assertEqual(images[1]['live'],[['0x0012C8A8','0x0012C8E0']])
        self.assertTrue(images[1]['invalidations'])

    def test_corrupted_memory_never_gets_rom_identity(self):
        self.load('p1',256,64,bad=True)
        self.add('exec',pc='0x8012C860',image_id=None)
        result=self.result()
        self.assertEqual(result['static_comparison'][0]['status'],'mismatch')
        self.assertEqual(result['images'][0]['exec_observations'],0)

    def test_return_correlates_ra_sp_and_subrange_without_double_count(self):
        self.add('wrapper_submit',call_id='c1',caller_ra='0x80001000',caller_sp='0x800FF000',
                 rom_start='0x00000100',dest_vram='0x8012C860',byte_count=64)
        self.load('p1',256,32)
        self.load('p2',288,32,dest=0x8012c880)
        self.add('wrapper_return',call_id='c1',pc='0x80001000',caller_sp='0x800FF000')
        result=self.result()
        self.assertEqual(result['wrapper_calls'][0]['pi_transfers'],['p1','p2'])
        self.assertEqual(len(result['images']),2)

    def test_write_attempt_makes_modified_pc_unknown(self):
        self.load('p1',256,64)
        self.add('write_attempt',pc='0x80001000',start_physical='0x0012C860',byte_count=4)
        self.add('exec',pc='0x8012C860',image_id=None)
        self.assertEqual(self.result()['images'][0]['exec_observations'],0)

    def test_disabled_write_hooks_cannot_confirm_executed_rom_image(self):
        self.events[0]['watch_writes']=False
        self.load('p1',256,64)
        self.add('exec',pc='0x8012C860',image_id='p1')
        result=self.result()
        self.assertEqual(result['static_comparison'][0]['status'],'loaded_not_executed')
        self.assertFalse(result['cpu_writes_observed'])
        self.assertTrue(result['issues'])

    def test_tlb_addresses_are_not_silently_mapped_to_ram(self):
        self.load('p1',256,64)
        self.add('exec',pc='0x0012C860',image_id=None)
        self.assertTrue(self.result()['unknown_exec_samples'])
        self.assertIsNone(trace.physical(0x0012c860))

    def test_out_of_order_and_inconsistent_pi_are_rejected(self):
        self.load('p1',256,64)
        self.events[-1]['byte_count']=32
        with self.assertRaisesRegex(ValueError,'submission/visibility'):
            self.result()
        self.events[-1]['byte_count']=64
        self.events[-1]['sequence']=99
        with self.assertRaisesRegex(ValueError,'sequence'):
            self.result()

    def test_pc_cannot_claim_the_previous_generation(self):
        self.load('a1',256,64)
        self.load('b1',512,128)
        self.add('exec',pc='0x8012C860',image_id='a1')
        with self.assertRaisesRegex(ValueError,'generation'):
            self.result()

    def test_reset_invalidates_all_images(self):
        self.load('a1',256,64)
        self.add('emulator_state',state=2,memory_reset=True)
        self.add('exec',pc='0x8012C860',image_id=None)
        result=self.result()
        self.assertEqual(result['images'][0]['live'],[])
        self.assertEqual(result['images'][0]['lifecycle'],'invalidated')
        self.assertEqual(result['images'][0]['exec_observations'],0)

    def test_closed_file_does_not_turn_synthetic_events_into_real_capture(self):
        self.add('capture_stop',reason='operator',pending_pi=0,pending_wrappers=0)
        self.assertEqual(self.result()['capture_status'],'synthetic_test')
        session=dict(self.session,source_kind='emulator')
        with self.assertRaisesRegex(ValueError,'provenance'):
            trace.reconcile(session,self.events,self.rom,self.evidence)

    def test_missing_or_truncated_capture_is_not_accepted_as_closed(self):
        session=dict(self.session,source_kind='emulator')
        events=[dict(self.events[0],source_kind='emulator')]
        result=trace.reconcile(session,events,self.rom,self.evidence)
        self.assertEqual(result['capture_status'],'incomplete')
        with self.assertRaisesRegex(ValueError,'no capture_start'):
            trace.reconcile(self.session,[],self.rom,self.evidence)

    def test_functions_are_matched_using_rom_and_ram_not_reused_pc_alone(self):
        self.load('b1',512,128)
        self.add('exec',pc='0x8012C860',image_id='b1')
        functions=[dict(rom=256,vram=0x8012c860,size=64,region='A',name='func_A'),
                   dict(rom=512,vram=0x8012c860,size=64,region='B',name='func_B')]
        result=trace.reconcile(self.session,self.events,self.rom,self.evidence,functions)
        self.assertEqual(result['images'][0]['observed_functions'],['B:func_B'])

    def test_prepare_is_unique_and_does_not_overwrite_sessions_or_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            executable=root/'not-a-real-emulator.exe'
            executable.write_bytes(b'Synthetic executable metadata fixture; never run')
            args=argparse.Namespace(run_id='TEST_PREPARED_ONLY',rom='synthetic',emulator_exe=str(executable),
                emulator_revision='synthetic-unit-test',backend=['mock; not an emulator'],rdram_mib=4,
                save=[],empty_save=True,no_watch_writes=False,max_events=10000)
            with patch.object(trace,'ROOT',root), patch.object(trace,'read_rom',return_value=self.rom), contextlib.redirect_stdout(io.StringIO()):
                trace.prepare(args)
                run=root/'local/traces/ozumo2/TEST_PREPARED_ONLY'
                before=(run/'session.json').read_bytes()
                session=json.loads(before)
                self.assertEqual(session['state'],'prepared_not_captured')
                self.assertEqual(trace.sha((run/'capture.js').read_bytes()),session['adapter_sha256'])
                self.assertFalse((run/'events.jsonl').exists())
                with self.assertRaises(FileExistsError):
                    trace.prepare(args)
                self.assertEqual((run/'session.json').read_bytes(),before)
                self.assertEqual(executable.read_bytes(),b'Synthetic executable metadata fixture; never run')

    def test_summary_outputs_are_structured_unique_and_preserve_raw_input(self):
        self.load('p1',256,64)
        self.add('exec',pc='0x8012C860',image_id='p1')
        self.add('capture_stop',reason='operator',pending_pi=0,pending_wrappers=0)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            run=root/'local/traces/ozumo2/SYNTHETIC'
            run.mkdir(parents=True)
            script=b'// Synthetic test fixture only; never executed as an emulator script\n'
            (run/'capture.js').write_bytes(script)
            session=dict(self.session,adapter_sha256=trace.sha(script),events='events.jsonl')
            (run/'session.json').write_text(json.dumps(session),encoding='utf-8')
            raw=''.join(json.dumps(e)+'\n' for e in self.events).encode()
            (run/'events.jsonl').write_bytes(raw)
            rom_path=root/'synthetic-input'
            rom_path.write_bytes(self.rom)
            evidence_path=root/'reports/evidence'
            evidence_path.mkdir(parents=True)
            (evidence_path/'ozumo2-functions.csv').write_text('region,rom,vram,size,name\nA,256,2148714592,64,synthetic_A\n')
            (evidence_path/'ozumo2-memory-map.csv').write_text('synthetic map fixture\n')
            (root/'config/splat').mkdir(parents=True)
            (root/'config/splat/ozumo2.yaml').write_text('name: synthetic_fixture\n')
            args=argparse.Namespace(run_dir=str(run),rom=str(rom_path))
            with patch.object(trace,'ROOT',root), patch.object(trace,'ROM_SHA256',trace.sha(self.rom)), \
                    patch.object(trace,'static_evidence',return_value=(self.evidence,'synthetic-static-hash')), \
                    contextlib.redirect_stdout(io.StringIO()):
                trace.summarize(args)
                trace.summarize(args)
            outputs=list(run.glob('summary-*'))
            self.assertEqual(len(outputs),2)
            for out in outputs:
                result=json.loads((out/'overlays.json').read_text())
                self.assertEqual(result['capture_status'],'synthetic_test')
                self.assertEqual(result['images'][0]['status'],'executed')
                self.assertIn('synthetic_test',(out/'observations.md').read_text())
                self.assertTrue((out/'static-comparison.csv').is_file())
            self.assertEqual((run/'events.jsonl').read_bytes(),raw)
            self.assertEqual(rom_path.read_bytes(),self.rom)

    def test_rsp_consumer_compares_hash_and_signatures_without_calling_it_cpu(self):
        self.evidence['ucode_signatures']=[dict(rom=260,text='synthetic test signature')]
        self.load('p1',256,64)
        self.add('rsp_task',task_type=1,ucode_vram='0x8012C860',ucode_size=16,
                 ucode_sha256=trace.sha(self.rom[256:272]),ucode_data_vram='0x8012C870',
                 ucode_data_size=16,ucode_data_sha256=trace.sha(self.rom[272:288]))
        result=self.result()
        self.assertEqual(result['static_comparison'][0]['status'],'loaded_not_executed')
        self.assertEqual(result['rsp_tasks'][0]['mapped_components'][0]['static_signature_offsets'],['0x00000104'])
        self.assertTrue(result['rsp_tasks'][0]['mapped_components'][0]['hash_match'])

    def test_adapter_synthetic_harness(self):
        if not shutil.which('node'):
            self.skipTest('Optional Node harness is unavailable')
        result=run_node()
        self.assertFalse(result['real_emulator_executed'])
        self.assertGreaterEqual(result['assertions'],15)

    def test_sha256_matches_python_across_padding_boundaries(self):
        if not shutil.which('node'):
            self.skipTest('Optional Node harness is unavailable')
        vectors=[bytes((i*13+7)&255 for i in range(n)) for n in (0,1,15,16,55,56,63,64,65,127,128,513,100000)]
        js=(Path(trace.__file__).parent/'sha256.js').read_text()
        js+='\nconst vectors='+json.dumps([list(v) for v in vectors])+';\n'
        js+='process.stdout.write(JSON.stringify(vectors.map(ozSha256)));'
        result=subprocess.run([shutil.which('node')],input=js,text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(result.stdout),[hashlib.sha256(v).hexdigest() for v in vectors])


if __name__=='__main__':
    unittest.main()
