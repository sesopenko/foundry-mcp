#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
docs_project="${COMPOSE_PROJECT_NAME:-$(basename -- "$repo_root")}-docs"
# Setup logs belong on stderr: stdout is reserved for the MCP protocol.
"$repo_root/scripts/docs-setup.sh" >&2
exec docker compose --project-name "$docs_project" -f "$repo_root/compose.docs.yml" run --rm --no-deps -T grounded-docs --protocol stdio
