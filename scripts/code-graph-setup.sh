#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_root"
check=false
case "${1:-}" in --check) check=true ;; '') ;; *) echo 'Usage: code-graph-setup.sh [--check]' >&2; exit 2 ;; esac
recover() { echo "code-graph: $*. Exit this checkout's Codex sessions and run ./scripts/dev-setup.sh" >&2; exit 1; }
for tool in node npm flock timeout python3; do command -v "$tool" >/dev/null || recover "Missing $tool"; done
mkdir -p .local/code-graph
exec 9>.local/code-graph/setup.lock
flock -w 15 9 || recover 'Setup lock busy (15s limit)'
fingerprint="$( { cat package.json package-lock.json; node --version; npm --version; node -p 'process.platform + "/" + process.arch'; } | sha256sum | cut -d ' ' -f 1)"
marker=.local/code-graph/dependencies.sha256
active() {
    [[ -f .code-graph/index.lock && ! -L .code-graph/index.lock ]] || return 1
    ! flock -n .code-graph/index.lock true
}
installed=false
if node scripts/resolve-code-graph.cjs >/dev/null 2>&1; then installed=true; fi
if [[ "$installed" != true || ! -f "$marker" || "$(cat "$marker")" != "$fingerprint" ]]; then
    "$check" && recover 'Dependency installation or fingerprint differs'
    if active; then recover 'Stop active graph consumers before replacing dependencies'; fi
    echo 'code-graph: reconciling locked npm dependencies (stop checkout consumers first).' >&2
    # Invalidate readiness before a potentially interrupted install.
    printf '' > "$marker"
    npm ci --include=dev --include=optional >&2
    node scripts/resolve-code-graph.cjs >/dev/null || recover 'Native engine validation failed'
    printf '%s\n' "$fingerprint" > "$marker.tmp"
    mv -- "$marker.tmp" "$marker"
else
    echo 'code-graph: locked dependencies verified; skipping npm.' >&2
fi
warm=false
if [[ -f .code-graph/index.db ]] && ./scripts/code-graph-doctor.sh >/dev/null 2>&1; then warm=true; fi

if active; then
    "$warm" || recover 'Active index owner but local index is not healthy'
    echo 'code-graph: active server owns freshness; skipping external indexing.' >&2
    exit 0
fi
result="$(mktemp .local/code-graph/index-result.XXXXXX)"
trap 'rm -f -- "$result"' EXIT
if ! CODE_GRAPH_YIELD_TO_SERVER=1 timeout --kill-after=5s 120s ./scripts/code-graph.sh incremental-index --no-embed --json > "$result"; then
    recover 'Index preparation failed or exceeded 120 seconds; inspect health after stopping sessions'
fi
mode="$(python3 - "$result" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
assert r.get('mode') in ('full', 'incremental', 'skipped'), r
assert not r.get('files_with_parse_errors'), r
print(r['mode'])
PY
)"
if [[ "$mode" == skipped ]]; then
    if ! "$warm" || ! active; then recover 'Skipped refresh without a verified warm server'; fi
    echo 'code-graph: refresh skipped; active server owns freshness.' >&2
fi
./scripts/code-graph-doctor.sh
