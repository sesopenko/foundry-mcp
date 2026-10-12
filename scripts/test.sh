#!/usr/bin/env bash
# Offline feedback: dependencies are provisioned separately with uv sync --locked.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"
if [[ ! -x .venv/bin/python ]]; then
    echo 'Missing .venv. Run uv sync --locked once before running tests.' >&2
    exit 1
fi
.venv/bin/python -m unittest discover -s tests -v
node --test tests/js/*.test.js
