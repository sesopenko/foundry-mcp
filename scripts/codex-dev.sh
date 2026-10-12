#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$repo_root/scripts/browser-dev.sh"
exec "$repo_root/scripts/codex.sh" --config 'mcp_servers.chrome-devtools.enabled=true' "$@"
