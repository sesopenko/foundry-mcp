#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for arg in "$@"; do
    if [[ "$arg" == --code-only ]]; then
        echo 'codex-dev.sh starts the development browser; use codex.sh --code-only for source analysis.' >&2
        exit 2
    fi
done
"$repo_root/scripts/browser-dev.sh"
exec "$repo_root/scripts/codex.sh" --config 'mcp_servers.chrome-devtools.enabled=true' "$@"
