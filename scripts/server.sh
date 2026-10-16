#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
service=foundry-mcp.service

wait_ready() {
    for ((attempt=0; attempt<30; attempt++)); do
        if systemctl --user is-active --quiet "$service" &&
            curl -fsS --max-time 1 http://127.0.0.1:8000/health >/dev/null 2>&1; then
            echo "Foundry MCP server is ready."
            return 0
        fi
        sleep 1
    done
    echo "Server did not become healthy; recent logs:" >&2
    journalctl --user -u "$service" -n 30 --no-pager >&2
    return 1
}

case "${1:-status}" in
    install)
        uv_path="$(command -v uv)"
        config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
        mkdir -p -- "$config_dir"
        python3 - "$repo_root" "$uv_path" "$config_dir/$service" <<'PY'
import json
import sys
from pathlib import Path
repo, uv, destination = sys.argv[1:]
template = (Path(repo) / "scripts/foundry-mcp.service.in").read_text()
# systemd expands percent specifiers even in quoted paths.
quote = lambda value: json.dumps(value.replace("%", "%%"))
directory = repo.replace("%", "%%").replace("\\", "\\\\").replace(" ", "\\x20")
Path(destination).write_text(template.replace("@REPO@", directory).replace("@UV@", quote(uv)))
PY
        systemctl --user daemon-reload
        echo "Installed $service. Run $repo_root/scripts/server.sh start."
        ;;
    start|restart)
        load_state="$(systemctl --user show "$service" --property=LoadState --value)"
        if [[ "$load_state" == not-found ]]; then
            "$repo_root/scripts/server.sh" install
        fi
        # Inactive units can be garbage-collected by systemd. Resetting one
        # unconditionally can fail with "Unit ... not loaded" before start.
        if systemctl --user is-failed --quiet "$service"; then
            systemctl --user reset-failed "$service"
        fi
        systemctl --user "${1}" "$service"
        wait_ready
        ;;
    stop)
        systemctl --user stop "$service"
        ;;
    status)
        systemctl --user status "$service" --no-pager
        curl -fsS --max-time 3 http://127.0.0.1:8000/health
        echo
        ;;
    logs)
        journalctl --user -u "$service" -n 80 --no-pager
        ;;
    *)
        echo "Usage: $0 {install|start|stop|restart|status|logs}" >&2
        exit 2
        ;;
esac
