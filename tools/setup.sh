#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export UV_CACHE_DIR="/workspace/.cache/ozumo64"
mkdir -p "$UV_CACHE_DIR"
if [[ ! -x .venv/bin/python ]]; then
    uv venv --python python3 .venv
fi
uv pip sync --python .venv/bin/python --require-hashes requirements.lock
.venv/bin/python -m splat --version
.venv/bin/python -m spimdisasm --version
.venv/bin/python -m unittest discover -s tests -v
