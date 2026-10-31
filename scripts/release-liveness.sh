#!/usr/bin/env bash
# Fixed anonymous HTTPS release checks; never accepts URLs or curl options.
set -euo pipefail
if (($# != 1)); then
    echo 'Usage: release-liveness.sh {runs|release|manifest|module|images}' >&2
    exit 2
fi
case "$1" in
    runs) endpoint='https://api.github.com/repos/sesopenko/foundry-mcp/actions/runs?per_page=5' ;;
    release) endpoint='https://api.github.com/repos/sesopenko/foundry-mcp/releases/latest' ;;
    manifest) endpoint='https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json' ;;
    module) endpoint='https://github.com/sesopenko/foundry-mcp/releases/latest/download/foundry-mcp.zip' ;;
    images) endpoint='https://hub.docker.com/v2/repositories/sesopenko/foundry-mcp/tags?page_size=10' ;;
    *) echo 'Unknown release check; choose runs, release, manifest, module or images.' >&2; exit 2 ;;
esac
# --disable must be first: ignore ~/.curlrc credentials, uploads and overrides.
# Never accept extra flags/URLs. Module checks headers to avoid binary output.
if [[ "$1" == module ]]; then
    exec curl --disable --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --max-time 20 --request HEAD --head --url "$endpoint"
fi
exec curl --disable --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --max-time 20 --request GET --url "$endpoint"
