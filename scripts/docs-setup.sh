#!/usr/bin/env bash
# Provision before MCP discovery; never crawl documentation during startup.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
docs_project="${COMPOSE_PROJECT_NAME:-$(basename -- "$repo_root")}-docs"
if ! command -v docker >/dev/null 2>&1; then
    echo 'Grounded Docs requires Docker with Compose. Install them, then rerun scripts/docs-setup.sh.' >&2
    exit 1
fi
docker compose version >/dev/null
docker info >/dev/null
image="$(docker compose --project-name "$docs_project" -f "$repo_root/compose.docs.yml" config --images)"
if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker compose --project-name "$docs_project" -f "$repo_root/compose.docs.yml" pull grounded-docs >&2
fi
