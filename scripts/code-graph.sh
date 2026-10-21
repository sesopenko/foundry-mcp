#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_root"
export CODE_GRAPH_DISABLE_MODEL_DOWNLOAD=1 CODE_GRAPH_NO_GITIGNORE=1 CODE_GRAPH_NO_AUTO_UPDATE=1
if [[ -L .code-graph ]]; then
    echo 'code-graph: .code-graph must be checkout-local, not a symlink.' >&2
    exit 1
fi
case "${1:-serve}" in
    incremental-index|rebuild-index|--version|-V|--help|-h) ;;
    *) if [[ ! -f .code-graph/index.db || -L .code-graph/index.db ]]; then
        echo 'code-graph: missing local index. Run ./scripts/dev-setup.sh before querying this checkout.' >&2
        exit 1
    fi ;;
esac
binary="$(node "$repo_root/scripts/resolve-code-graph.cjs")"
exec "$binary" "$@"
