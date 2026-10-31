# sesopenko/foundry-mcp

Version 2.5.0 adds [read-only compendium rules lookup](docs/compendium-tools.md).
It includes [Auth0 OAuth](docs/oauth-auth0.md) and
[PF2e inline builders](docs/pf2e-inline-builders.md).
It retains the [à la carte read contracts](docs/selective-reads.md) introduced
in 2.0.0: nine heavy tools default to compact results with typed `select`
requests and responses. Clients upgrading from 1.x must refresh schemas and
migrate Actor/Item `records` to `entries[].values[]`.

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

The source tree also provides three [typed PF2e inline builders](docs/pf2e-inline-builders.md)
for roll, check and compendium Item embed notation. They require a ready GM on
Foundry14.369/PF2e8.6.1 and never send chat, write documents or evaluate rolls.
These builders are included in v2.3.0.

Journal tools provide navigation, outlines, search and exact HTML/Markdown
reading through the GM browser. Version 2.5.0 adds
[compendium rules references](docs/compendium-tools.md) alongside
[world journals](docs/journal-tools.md).

Chat tools provide bounded reading and HTML sending with explicit
audiences and character speakers. See [chat tools and compatibility](docs/chat-tools.md).

Selected journal UUID references can be followed lazily to supported PF2e Actors
and Items with `resolve_journal_reference`, preserving anchors and token context.

Use `get_bridge_versions` to compare the packaged server and loaded browser
module releases, including when the GM is disconnected. Foundry warns about
tagged mismatches without blocking tools. See [version diagnostics](docs/bridge-version-diagnostics.md).

Use [budgeted MCP evaluations and call tracing](docs/mcp-tool-evaluation.md)
to test fresh-agent usability and compare tool changes without broad benchmark
runs. Recording is opt-in; the statistics command consumes no GPT usage.

This is currently in an experimental state, not a foundry module that is ready to share on foundry's module listing.

## Standalone LAN deployment and module releases

Version 2.3.0 added optional [Auth0 OAuth](docs/oauth-auth0.md) for
[ChatGPT](docs/oauth-chatgpt.md), with a separate deployment template.
Basic and OAuth are mutually exclusive per
instance. See [automated evidence and live acceptance gates](docs/oauth-verification.md).

For container setup, GitHub Actions secrets, module install/update, LibreChat
cutover, troubleshooting, and rollback, see [operations](docs/operations.md).
The gaming Foundry installation is independently managed. Production deployments require MCP Basic Auth or OAuth and separate browser bridge
credentials; development execution stays disabled. See the authentication and
2.3.0 migration instructions in the operations guide.
See [verification evidence and pending operator checks](docs/operationalization-verification.md).

Save this as `compose.yaml` in a separate deployment directory to run only the
MCP server. It requires no Foundry container, source mounts, or data volumes:

```yaml
services:
  foundry-mcp:
    image: ${FOUNDRY_MCP_IMAGE:?set a pinned image tag or digest}
    platform: linux/amd64
    restart: unless-stopped
    environment:
      FOUNDRY_MCP_HOST: 0.0.0.0
      FOUNDRY_MCP_PORT: "8000"
      FOUNDRY_MCP_DEV_EXECUTION: "false"
      FOUNDRY_MCP_AUTH_MODE: basic
      FOUNDRY_MCP_BASIC_USERNAME: ${FOUNDRY_MCP_BASIC_USERNAME:?set MCP username}
      FOUNDRY_MCP_BASIC_PASSWORD: ${FOUNDRY_MCP_BASIC_PASSWORD:?set MCP password}
      FOUNDRY_MCP_BRIDGE_TOKEN: ${FOUNDRY_MCP_BRIDGE_TOKEN:?set browser credential}
    ports:
      - "${FOUNDRY_MCP_LAN_ADDRESS:?set the host LAN IP}:8000:8000"
    stop_grace_period: 15s
```

Create a private `.env` alongside it, setting your LAN address. Fill in nonempty credentials of your choosing; empty values deliberately
prevent startup:

```dotenv
FOUNDRY_MCP_IMAGE=sesopenko/foundry-mcp:v2.5.0
FOUNDRY_MCP_LAN_ADDRESS=192.0.2.10
FOUNDRY_MCP_BASIC_USERNAME=librechat
FOUNDRY_MCP_BASIC_PASSWORD=
FOUNDRY_MCP_BRIDGE_TOKEN=
```

Keep `.env` out of version control and restrict it with `chmod 600 .env`. The public image requires no registry login. Start the service:

```bash
docker compose config --quiet
docker compose pull
docker compose up -d --wait --wait-timeout 90
```

The MCP endpoint is `http://<LAN-IP>:8000/mcp/mcp`; `/health` reports liveness.
Configure your MCP client with HTTP Basic Auth. In the Foundry module's world
settings, enable production authentication and enter the separate bridge token.
For an HTTPS Foundry page, supply a browser-trusted
`wss://<bridge-host>/ws/foundry` endpoint through your reverse proxy. Use HTTPS
for MCP connections crossing an untrusted network. See the operations guide
for LibreChat headers, module installation, and credential handling.

## Foundry (Docker) Dev Env Setup

`docker-compose.yml` reads Foundry credentials from a local `.env` file (gitignored).

1. Copy `.env.example` to `.env` and fill in values.
2. Start Foundry: `docker compose up -d foundry`

Foundry data is persisted in `./foundry-data`; module source is bind-mounted
from `./foundry-module`.

## Python and dependencies with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
these commands from the repository root:

```bash
uv python install
uv sync --locked
git config --local core.hooksPath .githooks
```

`.python-version` selects Python 3.12. `pyproject.toml` restricts the project to
Python 3.12 and declares exact dependency pins. The framework baseline is
FastAPI 0.162.0 and FastMCP 4.1.4 with MCP SDK 2 and Starlette 1.x.
`uv.lock` records the resolved versions. FastMCP no longer pulls Pydocket/Fakeredis;
the old Fakeredis constraint is removed. HTTP client helpers use httpx2.
Commit all three files.
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
clone. Each new clone must run that command once. The hook skips local tests
without confirmation when there is at least one staged change and every affected
path ends in case-sensitive `.md`, including deletions and both sides of renames.
Unstaged files do not affect that decision. Keep applicable documentation link,
example, consistency and whitespace checks for these commits. GitHub Actions
still runs tests for Markdown changes.

For non-Markdown, mixed or empty staging, the hook runs both suites and blocks
commits if tests fail or the local Python environment or Node.js cannot run them.
Git inspection failures also block commits. When tests run, they test the current
working tree, so stage the intended changes before committing.

## LLM

### Codex

For Debian 13 development bootstrap, run `./scripts/dev-setup.sh` (or add
`--install-system-packages` to provision missing Debian prerequisites).
This installs locked Python/npm tools and a local Python/JavaScript code graph.
See [code graph setup and navigation](docs/code-graph.md).
Use `./scripts/codex.sh --code-only` for source analysis without Docker,
Foundry, or the development browser. An installed, authenticated Codex CLI is
required only when launching Codex.

The repository's `.codex/config.toml` enables the `foundry-vtt` MCP server
at `http://127.0.0.1:8000/mcp/mcp` for Codex sessions in this project.
Codex loads project configuration only for trusted projects; accept the
project trust prompt if shown. This setup does not add a global MCP server.

After installing the user service above, launch Codex with:

```bash
./scripts/codex.sh
```

The launcher installs the user service if missing, starts it, and waits for health before launching Codex
from this repository. `AGENTS.md` tells Codex how to start and restart the
server through the shell when needed. Restart existing Codex sessions to
load the configuration. Run `codex mcp list` here to check the registration;
this lists configured servers and does not verify a live MCP connection.
The Foundry browser must also be connected for tools that access game state.

Grounded Docs also starts automatically as a project-scoped stdio MCP server
in trusted Codex sessions. Its pinned Docker image is provisioned by the
launcher, and its documentation index persists across reboots. Agents can
populate the official Foundry API index on a fresh machine. Docker with
Compose must be running; no documentation API key is required. See
[setup, indexing, and recovery](docs/foundry-api-docs.md).

The upstream PF2e wiki is available through the separate `pf2e-wiki` library
for system workflows and feature research. See the
[LLM search, indexing, and refresh workflow](docs/foundry-api-docs.md#pf2e-wiki-discovery-indexing-and-refresh).

### Other MCP clients

An LLM Web Interface is not included.  You can use [LibreChat](https://www.librechat.ai/) and then connect it to the mcp server.  Example configuration:

```yaml
mcpServers:
  foundry-vtt:
    type: streamable-http
    url: http://mcp-host.example:8000/mcp/mcp
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

## Actor and Item source reading (v2.5.0)

Version 2.1.0 added `get_party_members` for official PF2e world-party
membership, with named party selection and canonical `read_actor` follow-ups.
Use character members for PC-group questions. Version 2.2.0 added
`read_actor` selections `wealth`, `bulk`, `wealth.items` and `bulk.items`, with
guarded runtime fields reporting `available` or `potentially_missing`. Party
stash remains unsupported. See [metric contracts](docs/character-inventory-metrics.md)
and [party contracts](docs/party-tools.md).

Version 2.5.0 includes GM-only Actor/Item capability discovery, selected-source
reading, owned Item navigation, world Actor folders/name search, Scene/Token
navigation, and scoped Actor/Item compendium index search on Foundry
14.369/PF2e 8.6.1. Canonical world/pack/token identities, bounded pages and
explicit scope failures keep duplicate names and partial results distinguishable.

Explore supported PF2e characters, NPCs, familiars and their Items through read-only tools; see the
[Actor and Item guide](docs/actor-tools.md) for supported features and limitations.

## Private PDF references

An opt-in GM-private PDF library provides lexical lookup and source-page reading,
plus acknowledged uploads through the existing Foundry bridge. See
[PDF library setup, access policy and recovery](docs/pdf-library.md).
Do not share a PDF-enabled endpoint's MCP credentials with players.

PF2e deity reading preserves offered devotee options and explicit immediate spell
identity links. It does not infer acquired spells, prepared spells or active
character benefits. See the [deity field audit](docs/actor-item-story-map/deity-fields.md).

PF2e feat source reading distinguishes feats from features and nominal levels from
recorded taken levels, retaining prerequisites and description prose. Explicit
grant claims resolve only within the actual Actor owner. Character Build lists
each actual acquired Item once and reports agreeing, disagreeing, absent or
unevaluated reciprocal grant evidence separately. Source rules never execute.

Recorded feat selections expose stored string/finite-number values only;
unsupported selection values make source partial. These delivered source
selections remain separate from acquired-document joins and do not establish
eligibility or active benefits. See the
[selection contract](docs/actor-item-story-map/feat-selection-contract.md) and
[Build verification](docs/actor-item-story-map/build-verification.md).
