#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_root"
case "${1:-}" in --mcp-smoke|'') ;; *) echo 'Usage: code-graph-doctor.sh [--mcp-smoke]' >&2; exit 2 ;; esac
./scripts/code-graph.sh --version >&2
./scripts/code-graph.sh health-check --json | python3 -c '
import json, sys
h = json.load(sys.stdin)
if not h.get("healthy") or h.get("index_version_stale") or h.get("files_with_parse_errors"):
    sys.exit("code-graph: unhealthy/stale index or parse errors: " + str(h))
langs = h.get("resolution", {}).get("edges_by_language", {})
if not all(x in langs for x in ("python", "javascript")):
    sys.exit("code-graph: missing Python or JavaScript coverage")
print("code-graph: healthy; search_mode=" + h["search_mode"] + "; embeddings=" + h.get("embedding_status", "unknown"), file=sys.stderr)
'
if [[ "${1:-}" == --mcp-smoke ]]; then
    [[ -x .venv/bin/python ]] || { echo 'Run ./scripts/dev-setup.sh to provision Python.' >&2; exit 1; }
    exec .venv/bin/python scripts/code_graph_smoke.py
fi
