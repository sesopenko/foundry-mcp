# sesopenko/foundry-mcp

This project provides a Model Context Protocol (MCP) bridge between a Large Language Model (LLM) and a running Foundry VTT game.  
It consists of a Python MCP proxy server and a Foundry VTT client module that communicate over a WebSocket-based RPC channel.

The Python side exposes a small, well-defined set of MCP tools (over HTTP) that the LLM can call. Those tool calls are forwarded over WebSockets to the Foundry browser runtime, which is the single source of truth for game state and executes all Foundry API calls. Responses flow back over the same channel so that, from the LLM’s perspective, each tool call is synchronous and deterministic.

Key goals of this project:

- Enable safe, synchronous LLM interaction with a live Foundry VTT world
- Keep all game logic and state inside Foundry’s browser/Electron runtime
- Use a simple, explicit JSON-RPC style protocol over WebSockets
- Provide a minimal, maintainable Python server that focuses on validation, orchestration, and error handling rather than mirroring Foundry APIs

In practice, you run the Python MCP server, load the companion module in Foundry, and then connect an MCP-aware LLM client. The LLM can then call tools like “get world information”, “inspect actors”, or other narrowly scoped operations that are implemented in the Foundry module and mediated by the Python server.

Further reading: [docs/mcp_foundry_architecture.md](docs/mcp_foundry_architecture.md)

This is currently in an experimental state, not a foundry module that is ready to share on foundry's module listing.

## Foundry (Docker) Dev Env Setup

`docker-compose.yml` reads Foundry credentials from a local `.env` file (gitignored).

1. Copy `.env.example` to `.env` and fill in values.
2. Start Foundry: `docker compose up -d foundry`

Foundry data is persisted in `./data`.

## Python and dependencies with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
these commands from the repository root:

```bash
uv python install
uv sync --locked
git config --local core.hooksPath .githooks
```

`.python-version` selects Python 3.12. `pyproject.toml` restricts the project to
Python 3.12 and declares the direct dependencies, retaining the previous exact
pins. Python 3.12 satisfies FastAPI 0.128.0's Python >=3.9 requirement and
FastMCP 2.14.1 and Uvicorn 0.40.0's Python >=3.10 requirements.
`uv.lock` records the resolved dependency versions. The uv constraint on
Fakeredis preserves compatibility with the locked Pydocket release. Commit all three files.
`uv sync` creates and manages `.venv`; manual activation is unnecessary.

### Run the server

```bash
./scripts/start-server.sh
```

The launcher works from any working directory and runs the server in the
foreground. Press Ctrl+C to stop it.

The server listens on port 8000. Foundry connects to `/ws/foundry`, and MCP
clients connect to `/mcp/mcp`.

### Manage the server in the background (Linux)

Install the systemd user service once per clone, then start it:

```bash
./scripts/server.sh install
./scripts/server.sh start
```

Use `./scripts/server.sh restart`, `stop`, `status`, or `logs` to manage it.
Start and restart wait up to about 60 seconds for the health endpoint.
The service runs without the development reloader and restarts on failure.
It is started on demand, not enabled at login, and runs independently of the
launching terminal. Logs are captured by the user journal. If you move the
clone or change the uv installation, stop the service and run `install` again.
Stop any foreground server before starting the service to free port 8000.

### Change dependencies

Use `uv add 'package==version'` or `uv remove package` to update the project
and lockfile together. After editing `pyproject.toml` manually, run `uv lock`
and `uv sync --locked`. Use `uv lock --upgrade` to refresh transitive dependencies
within the declared constraints, then sync and test. Commit `pyproject.toml`
and `uv.lock` together. The former requirements files are replaced by these files.

### Unit tests and commit hook

PyUnit is Python's built-in `unittest` framework; no additional package is needed.
Run both suites offline, without dependency installation or uv cache access:

```bash
./scripts/test.sh
```

For focused Python checks, use
`.venv/bin/python -m unittest discover -s tests -p 'test_<area>.py' -v`. Provision `.venv` once with `uv sync --locked`.

The Python suite covers RPC correlation, errors and cleanup, the player-name
MCP tool, and application health and WebSocket lifecycle. Add tests as
`tests/test_*.py` using `unittest.TestCase`.

Run the JavaScript suite with `npm test` (Node.js 18 or newer; no npm install
needed). It uses Node's built-in test runner with Foundry globals, WebSockets,
and controlled timers to exercise player filtering, RPC errors, lifecycle
hooks, reconnect backoff, and manual disconnect. These mocks verify bridge
behavior; Foundry API compatibility requires a separate live check.

The setup command above installs the tracked `.githooks/pre-commit` hook for this
clone. Each new clone must run that command once. The hook runs both suites
and blocks commits if tests fail or the local Python environment or Node.js cannot run them. It tests the
current working tree, so stage the intended changes before committing.

## LLM

### Codex

The repository's `.codex/config.toml` enables the `foundry-vtt` MCP server
at `http://127.0.0.1:8000/mcp/mcp` for Codex sessions in this project.
Codex loads project configuration only for trusted projects; accept the
project trust prompt if shown. This setup does not add a global MCP server.

After installing the user service above, launch Codex with:

```bash
./scripts/codex.sh
```

The launcher starts the service and waits for health before launching Codex
from this repository. `AGENTS.md` tells Codex how to start and restart the
server through the shell when needed. Restart existing Codex sessions to
load the configuration. Run `codex mcp list` here to check the registration;
this lists configured servers and does not verify a live MCP connection.
The Foundry browser must also be connected for tools that access game state.

### Other MCP clients

An LLM Web Interface is not included.  You can use [LibreChat](https://www.librechat.ai/) and then connect it to the mcp server.  Example configuration:

```yaml
mcpServers:
  foundry-vtt:
    type: streamable-http
    url: http://192.168.10.137:8000/mcp/mcp
    timeout: 30000
    serverInstructions: true
```

## License

This software is licensed under the MIT license, viewable in [LICENSE.txt](LICENSE.txt)

Copyright (c) Sean Esopenko 2025

## Development JavaScript exploration

An optional `execute_javascript` MCP tool supports live API exploration in a
local GM browser. It is disabled by default and requires separate caller and
browser credentials plus browser opt-in. See [setup, usage, and limitations](docs/js-exploration.md).

For a visible development browser that both you and Codex can use, install
browser tooling with `npm ci` and launch `./scripts/codex-dev.sh`. Chrome MCP
supports automatic refreshes, console and network inspection, and UI checks.
It is disabled in normal sessions. See [shared browser setup](docs/browser-development.md).
