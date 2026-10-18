#!/usr/bin/env python3
"""Recompile self-authored MIPS only, compile the generated C and check a delay slot."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='cc')
    args = parser.parse_args()
    cc = shutil.which(args.cc)
    if cc is None:
        parser.error('A host C compiler is required')
    output_root = ROOT / '.tools/smoke/recompiler'
    output_root.mkdir(parents=True, exist_ok=True)
    # A fresh directory prevents an earlier generated function from masking a failure.
    work = Path(tempfile.mkdtemp(prefix='run-', dir=output_root))
    # addiu v0, zero, 42; jr ra; addiu v0, v0, 1 (return delay slot).
    # This input was authored for the test and is unrelated to either commercial ROM.
    (work / 'synthetic.bin').write_bytes(struct.pack('>III', 0x2402002A, 0x03E00008, 0x24420001))
    (work / 'symbols.toml').write_text('''[[section]]
name = ".text"
rom = 0
vram = 0x80000400
size = 12
functions = [{ name = "ozumo_toolchain_smoke", vram = 0x80000400, size = 12 }]
''')
    (work / 'config.toml').write_text('''[input]
symbols_file_path = "symbols.toml"
rom_file_path = "synthetic.bin"
output_func_path = "output"
functions_per_output_file = 1
''')
    executable_suffix = '.exe' if sys.platform == 'win32' else ''
    tool = ROOT / '.tools/build/N64Recomp' / ('N64Recomp' + executable_suffix)
    subprocess.run([str(tool), str(work / 'config.toml')], check=True, cwd=ROOT)
    generated = work / 'output/ozumo_toolchain_smoke.c'
    if not generated.is_file():
        raise RuntimeError('The expected synthetic function was not generated')
    (work / 'main.c').write_text('''#include "recomp.h"
#include "funcs.h"
int main(void) {
    recomp_context context = {0};
    ozumo_toolchain_smoke(NULL, &context);
    return context.r2 == 43 ? 0 : 1;
}
''')
    binary = work / ('synthetic-test' + executable_suffix)
    include = ROOT / '.tools/src/N64Recomp/include'
    command = [cc, '-std=c17', '-I', str(include), '-I', str(work / 'output'),
               str(generated), str(work / 'main.c'), '-o', str(binary)]
    if sys.platform != 'win32':
        command.append('-lm')
    subprocess.run(command, check=True)
    subprocess.run([str(binary)], check=True)
    receipt = {'input': '12 self-authored bytes; no game ROM input', 'tool_revision':
               json.loads((ROOT / 'config/toolchain.lock.json').read_text())['repositories']['N64Recomp']['revision'],
               'functions_recompiled': 1, 'expected_v0': 43, 'status': 'passed', 'host_cc': cc,
               'run_directory': str(work.relative_to(ROOT))}
    (output_root / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
