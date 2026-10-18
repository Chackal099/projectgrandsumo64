.PHONY: setup test analyze verify setup-native upstream smoke-recompiler check-publish

setup:
	bash tools/setup.sh

test:
	.venv/bin/python -m unittest discover -s tests -v

analyze:
	.venv/bin/python tools/analyze.py
	.venv/bin/python tools/render_maps.py
	.venv/bin/python tools/render_reports.py

verify:
	.venv/bin/python tools/verify.py

# Native tools use a separate environment and never rerun the ROM analysis.
setup-native:
	UV_CACHE_DIR=.cache/uv uv venv --allow-existing --python python3 .tools/venv
	UV_CACHE_DIR=.cache/uv uv pip sync --python .tools/venv/bin/python --require-hashes tools/development/requirements.lock

upstream:
	.tools/venv/bin/python tools/development/build_upstream.py --jobs 2

smoke-recompiler:
	.tools/venv/bin/python tools/development/smoke_recompiler.py

check-publish:
	.venv/bin/python tools/check_publishable.py
