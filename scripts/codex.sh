#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"
if ! command -v uv >/dev/null && [[ -x "$HOME/.local/bin/uv" ]]; then
    export PATH="$HOME/.local/bin:$PATH"
fi
code_only=false
if [[ "${1:-}" == --code-only ]]; then code_only=true; shift; fi
"$repo_root/scripts/code-graph-setup.sh" --check
extra_config=()
if "$code_only"; then
    for server in grounded-docs foundry-vtt chrome-devtools; do
        extra_config+=(--config "mcp_servers.$server.enabled=false")
    done
else
"$repo_root/scripts/docs-setup.sh"
"$repo_root/scripts/server.sh" start

# Read only the caller credential; never execute dotenv contents as shell code.
if [[ -f "$repo_root/.env.mcp" ]]; then
    FOUNDRY_MCP_CALLER_TOKEN="$("$repo_root/.venv/bin/python" - "$repo_root/.env.mcp" <<'PYTOKEN'
from pathlib import Path
import sys
for line in Path(sys.argv[1]).read_text().splitlines():
    key, separator, value = line.partition("=")
    if separator and key.strip() == "FOUNDRY_MCP_CALLER_TOKEN":
        print(value.strip())
        break
PYTOKEN
)"
    export FOUNDRY_MCP_CALLER_TOKEN
fi

fi

# Run this launcher on the Debian host. Commands stay sandboxed unless you
# approve an escalation; approval requests go to you rather than auto-review.
# Forward all arguments, e.g. ./scripts/codex.sh resume --last.
exec codex \
    --sandbox workspace-write \
    --ask-for-approval on-request \
    --config 'approvals_reviewer="user"' \
    "${extra_config[@]}" \
    "$@"
