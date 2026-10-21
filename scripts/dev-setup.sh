#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_root"
case "${1:-}" in
    --install-system-packages)
        . /etc/os-release
        [[ "$ID" == debian && "$VERSION_ID" == 13 ]] || { echo 'System provisioning supports Debian 13 only.' >&2; exit 1; }
        packages=()
        for pair in ca-certificates:/etc/ssl/certs/ca-certificates.crt curl:curl git:git nodejs:node npm:npm python3:python3 ripgrep:rg util-linux:flock; do
            probe="${pair#*:}"
            if [[ "$probe" == /* ]]; then [[ -f "$probe" ]] && continue
            else command -v "$probe" >/dev/null && continue; fi
            packages+=("${pair%%:*}")
        done
        if ((${#packages[@]})); then
            if ((EUID == 0)); then apt-get update; apt-get install -y "${packages[@]}"
            else sudo apt-get update; sudo apt-get install -y "${packages[@]}"; fi
        fi ;;
    '') ;;
    *) echo 'Usage: dev-setup.sh [--install-system-packages]' >&2; exit 2 ;;
esac
for tool in curl git node npm python3 rg flock timeout sha256sum; do
    command -v "$tool" >/dev/null || { echo "Missing $tool; run ./scripts/dev-setup.sh --install-system-packages" >&2; exit 1; }
done
if ! command -v uv >/dev/null; then
    if [[ ! -x "$HOME/.local/bin/uv" ]]; then
        # Single bootstrap installer pin; existing uv installations are preserved.
        uv_version=0.9.16
        installer="$(mktemp)"
        trap 'rm -f -- "$installer"' EXIT
        curl -fsSL "https://astral.sh/uv/$uv_version/install.sh" -o "$installer"
        UV_NO_MODIFY_PATH=1 UV_INSTALL_DIR="$HOME/.local/bin" sh "$installer"
        "$HOME/.local/bin/uv" --version
    fi
    export PATH="$HOME/.local/bin:$PATH"
fi
uv python install 3.12
uv sync --locked
hooks="$(git config --get core.hooksPath || true)"
if [[ -z "$hooks" ]]; then git config --local core.hooksPath .githooks; fi
./scripts/code-graph-setup.sh
./scripts/code-graph-doctor.sh --mcp-smoke
