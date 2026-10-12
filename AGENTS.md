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

## Continuous testing

Establish tests for existing behavior before extending or refactoring it.
Run focused tests after each meaningful change and add tests alongside new
behavior, rather than leaving testing until the end. Resolve relevant failures
before building further work on top of a change.

Run tests autonomously without asking the user to prompt or approve routine
local test execution. Before committing, run `./scripts/test.sh` for both suites.
This offline runner uses the existing `.venv` and Node directly, avoiding uv
cache writes outside the sandbox. For focused Python checks use
`.venv/bin/python -m unittest discover -s tests -p 'test_<area>.py' -v`;
for focused JavaScript checks use `node --test tests/js/<area>.test.js`.
Provision dependencies separately with `uv sync --locked` when needed.
Browser mocks verify bridge behavior; use a live Foundry session separately
when a change depends on Foundry runtime APIs.

## Development browser

For active Foundry development, use `./scripts/codex-dev.sh` to enable the
Chrome DevTools MCP tools and share a dedicated visible Chrome profile with
the user. The normal launcher leaves Chrome MCP disabled. Keep automation in
this development browser and test world; do not attach to the user's ordinary
browser or use it during game sessions. After meaningful module changes, run
focused local tests, refresh the development tab, wait for bridge connectivity,
and check console errors and live behavior. See `docs/browser-development.md`.

Repository-local skills capture recurring workflows:

- `.agents/skills/foundry-dev-connect/SKILL.md`: development browser setup,
  authentication, and connection diagnosis.
- `.agents/skills/foundry-dev-loop/SKILL.md`: baseline, focused tests, refresh,
  console inspection, and live verification after code changes.

Use the relevant skill for these tasks. If a new skill is absent from the
current session's catalog, read its local file directly; a new session can
discover it normally. Keep the linked developer docs as the source of truth.
