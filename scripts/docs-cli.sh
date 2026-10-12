#!/usr/bin/env bash
# Recovery/inspection when MCP tools are unavailable in the current session.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
docs_project="${COMPOSE_PROJECT_NAME:-$(basename -- "$repo_root")}-docs"
"$repo_root/scripts/docs-setup.sh" >&2
exec docker compose --project-name "$docs_project" -f "$repo_root/compose.docs.yml" run --rm --no-deps -T grounded-docs "$@"
