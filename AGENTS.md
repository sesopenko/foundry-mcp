# Repository guidance for Codex

## MCP server lifecycle

At the start of work in this repository, check the server with
`curl -fsS --max-time 3 http://127.0.0.1:8000/health`. The project MCP
registration may be present even when the server is stopped.
If unavailable, run `./scripts/server.sh start` before using Foundry tools.
If the user service is missing, run `./scripts/server.sh install` first.
Use `./scripts/server.sh restart` when a server restart is needed,
`./scripts/server.sh status` to inspect health, and `./scripts/server.sh logs`
to diagnose failures. These commands may require sandbox escalation to access
the host's user service manager and localhost network.

Starting or restarting this project's service as needed is authorized.
Do not start a second foreground server while the service is running.
An empty `foundry_clients` list means the server is healthy but no Foundry
browser is connected; starting another server will not fix that.
If the endpoint is healthy but MCP tools are absent from the current session,
report that Codex may need to reconnect or restart; `codex mcp list` only
confirms registration, not tool availability in the current session.
Prefer `./scripts/codex.sh` when launching Codex: it starts the service and
waits for health before Codex discovers MCP tools.

## Required reading

Before doing work in this repository, read these files in full:

- [README.md](README.md): project overview, development setup, and dependency workflow.
- [pyproject.toml](pyproject.toml): direct Python dependencies.
- [docs/mcp_foundry_architecture.md](docs/mcp_foundry_architecture.md): architecture, RPC protocol, and design principles.
- [foundry-module/scripts/README.md](foundry-module/scripts/README.md): Foundry client script conventions.

This list carries forward the required reading from `.aider.conf.yml`. Keep the guidance in the referenced files as the source of truth rather than duplicating it here.
