#!/usr/bin/env bash
set -euo pipefail

# Run this launcher on the Debian host. Commands stay sandboxed unless you
# approve an escalation; approval requests go to you rather than auto-review.
# Forward all arguments, e.g. ./scripts/codex.sh resume --last.
exec codex \
    --sandbox workspace-write \
    --ask-for-approval on-request \
    --config 'approvals_reviewer="user"' \
    "$@"
