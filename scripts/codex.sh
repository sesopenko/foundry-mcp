#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$repo_root"
"$repo_root/scripts/server.sh" start

# Run this launcher on the Debian host. Commands stay sandboxed unless you
# approve an escalation; approval requests go to you rather than auto-review.
# Forward all arguments, e.g. ./scripts/codex.sh resume --last.
exec codex \
    --sandbox workspace-write \
    --ask-for-approval on-request \
    --config 'approvals_reviewer="user"' \
    "$@"
