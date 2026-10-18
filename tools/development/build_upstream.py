#!/usr/bin/env python3
"""Fetch pinned public sources and build tools/libraries; never reads game ROMs."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()


def checked(command, *, log=None):
    print('Running:', ' '.join(map(str, command)), flush=True)
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'Command exited {result.returncode}; inspect {log}')
    else:
        subprocess.run(command, check=True)


def prepare_source(path, spec):
    if not path.exists():
        path.mkdir(parents=True)
        checked(['git', 'init', '--quiet', str(path)])
        checked(['git', '-C', str(path), 'remote', 'add', 'origin', spec['url']])
        checked(['git', '-C', str(path), 'fetch', '--depth', '1', 'origin', spec['revision']])
        checked(['git', '-C', str(path), 'checkout', '--detach', spec['revision']])
    if Path(git(path, 'rev-parse', '--show-toplevel')).resolve() != path.resolve():
        raise RuntimeError(f'Not the expected checkout: {path}')
    if git(path, 'remote', 'get-url', 'origin').removesuffix('.git') != spec['url'].removesuffix('.git'):
        raise RuntimeError(f'Unexpected origin in {path}; left unchanged')
    if git(path, 'rev-parse', 'HEAD') != spec['revision']:
        raise RuntimeError(f'Unexpected revision in {path}; use a new source directory, do not reset local work')
    if git(path, 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError(f'Checkout has changes: {path}; left unchanged')
    checked(['git', '-C', str(path), 'submodule', 'update', '--init', '--recursive', '--depth', '1'])
    observed = {}
    for line in git(path, 'submodule', 'status', '--recursive').splitlines():
        # .strip() removes the leading space from the first clean entry.
        revision, name, *_ = line.strip().split()
        if revision.startswith(('-', '+', 'U')):
            raise RuntimeError(f'Unresolved submodule in {path}: {name}')
        observed[name] = revision
    if observed != spec['submodules']:
        raise RuntimeError(f'Submodule revisions differ from config/toolchain.lock.json: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=['all', 'N64Recomp', 'N64ModernRuntime'], default='all')
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--source-root', type=Path, default=ROOT / '.tools/src')
    parser.add_argument('--c-compiler')
    parser.add_argument('--cxx-compiler')
    parser.add_argument('--cxx-flags')
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    executable_suffix = '.exe' if sys.platform == 'win32' else ''
    bin_dir = Path(sys.executable).parent
    cmake, ninja = [bin_dir / (name + executable_suffix) for name in ('cmake', 'ninja')]
    if not cmake.is_file() or not ninja.is_file():
        parser.error('Run with the Python from .tools/venv after installing tools/development/requirements.lock')
    lock = json.loads((ROOT / 'config/toolchain.lock.json').read_text())
    receipt = {'scope': 'upstream tools and static libraries only; no game recompilation', 'builds': {}}
    for name, spec in lock['repositories'].items():
        if args.only not in ('all', name):
            continue
        source = (args.source_root / name).resolve()
        prepare_source(source, spec)
        build = ROOT / '.tools/build' / name
        configure = [str(cmake), '-S', str(source), '-B', str(build), '-G', 'Ninja',
                     '-DCMAKE_BUILD_TYPE=Release', f'-DCMAKE_MAKE_PROGRAM={ninja}']
        if args.c_compiler:
            configure.append(f'-DCMAKE_C_COMPILER={args.c_compiler}')
        if args.cxx_compiler:
            configure.append(f'-DCMAKE_CXX_COMPILER={args.cxx_compiler}')
        if args.cxx_flags:
            configure.append(f'-DCMAKE_CXX_FLAGS={args.cxx_flags}')
        checked(configure, log=ROOT / '.tools/logs' / f'{name}-configure.log')
        checked([str(cmake), '--build', str(build), '--parallel', str(args.jobs), '--target', *spec['targets']],
                log=ROOT / '.tools/logs' / f'{name}-build.log')
        receipt['builds'][name] = {'revision': spec['revision'], 'targets': spec['targets'], 'status': 'built'}
    dest = ROOT / '.tools/build-status.json'
    dest.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
