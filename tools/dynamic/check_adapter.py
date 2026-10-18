#!/usr/bin/env python3
"""Run the explicitly synthetic adapter harness in Node or upstream Duktape."""
import argparse
import ctypes
from pathlib import Path
import shutil
import subprocess
import json

ROOT=Path(__file__).resolve().parents[2]


def source():
    harness=(ROOT/'tests/dynamic_adapter_harness.js').read_text(encoding='utf-8')
    adapter=(ROOT/'tools/dynamic/project64.js').read_text(encoding='utf-8')
    return (ROOT/'tools/dynamic/sha256.js').read_text(encoding='utf-8')+'\n'+harness.replace('// INSERT_ADAPTER_HERE',adapter)


def run_node():
    executable=shutil.which('node')
    if not executable:
        raise RuntimeError('Node is unavailable; install Node LTS for this optional JS harness')
    result=subprocess.run([executable],input=source()+'\nprocess.stdout.write(HARNESS_RESULT);',
                          text=True,encoding='utf-8',capture_output=True,check=True)
    return json.loads(result.stdout)


def run_duktape(path):
    lib=ctypes.CDLL(str(Path(path).resolve()))
    lib.duk_create_heap.argtypes=[ctypes.c_void_p]*5
    lib.duk_create_heap.restype=ctypes.c_void_p
    lib.duk_eval_raw.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_uint]
    lib.duk_eval_raw.restype=ctypes.c_int
    lib.duk_safe_to_lstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
    lib.duk_safe_to_lstring.restype=ctypes.c_char_p
    lib.duk_get_global_string.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
    lib.duk_get_global_string.restype=ctypes.c_int
    lib.duk_destroy_heap.argtypes=[ctypes.c_void_p]
    ctx=lib.duk_create_heap(None,None,None,None,None)
    if not ctx:
        raise RuntimeError('Duktape heap creation failed')
    try:
        code=source().encode()
        # duk_peval_lstring: EVAL | SAFE | NOSOURCE | NOFILENAME, from pinned duktape.h.
        flags=(1<<3)|(1<<7)|(1<<9)|(1<<11)
        if lib.duk_eval_raw(ctx,code,len(code),flags):
            raise RuntimeError(lib.duk_safe_to_lstring(ctx,-1,None).decode())
        lib.duk_get_global_string(ctx,b'HARNESS_RESULT')
        return json.loads(lib.duk_safe_to_lstring(ctx,-1,None).decode())
    finally:
        lib.duk_destroy_heap(ctx)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duktape-library')
    args=p.parse_args()
    print(json.dumps(run_duktape(args.duktape_library) if args.duktape_library else run_node()))
