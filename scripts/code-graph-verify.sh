#!/usr/bin/env bash
# Stable approval entry point: all verification output goes to one local log.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_root"
if (($#)); then
    echo 'Usage: ./scripts/code-graph-verify.sh' >&2
    exit 2
fi
mkdir -p .local/code-graph
log="$repo_root/.local/code-graph/verification.log"
exec 9>.local/code-graph/verification.lock
if ! flock -n 9; then
    echo "Verification is already running. Log: $log" >&2
    exit 1
fi
printf 'Verification log: %s\n' "$log"
set +e
(
    set -e
    date -u
    ./scripts/code-graph-setup.sh --check
    ./scripts/code-graph-doctor.sh --mcp-smoke
    CODE_GRAPH_INTEGRATION=1 .venv/bin/python -m unittest discover -s tests -p test_code_graph.py -v
    ./scripts/test.sh
    .venv/bin/python scripts/package-module.py
    git diff --check
) > "$log" 2>&1
result=$?
set -e
if ((result == 0)); then
    echo "Verification passed. Log: $log"
else
    tail -n 35 -- "$log" >&2
    echo "Verification failed (exit $result). Log: $log" >&2
    exit "$result"
fi
