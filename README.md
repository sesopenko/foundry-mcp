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

Journal preparation tools provide hierarchical navigation, page outlines,
literal text search, and exact HTML/Markdown reading through the GM browser.
See [journal tool contracts and compatibility](docs/journal-tools.md).

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

For container setup, GitHub Actions secrets, module install/update, LibreChat
cutover, troubleshooting, and rollback, see [operations](docs/operations.md).
The gaming Foundry installation is independently managed. Production deployments require separate MCP Basic Auth and browser bridge
credentials; development execution stays disabled. See the authentication and
1.5.0 migration instructions in the operations guide.
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
FOUNDRY_MCP_IMAGE=sesopenko/foundry-mcp:v1.5.0
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

## Actor and Item source reading (unreleased)

The source branch adds GM-only Actor/Item capability discovery, selected-source
reading, owned Item navigation, world Actor folders/name search, Scene/Token
navigation, and scoped Actor/Item compendium index search on Foundry
14.369/PF2e 8.6.1. Canonical world/pack/token identities, bounded pages and
explicit scope failures keep duplicate names and partial results distinguishable.

Physical Item readers expose common persisted quantity, Bulk, price/per, carry,
material, identification and serialized attachment fields. Action Items map
activation kind/count, frequency, traits and named self-effects; only an explicit
relationship request resolves the immediate effect, without applying it.
NPC attack Items preserve authored modes, bonus/damage and named effect labels,
with explicit null-range/thrown limitations. The delivered registry identifies
verified per-type support and partial or unsupported Actor sections. See the
[contracts](docs/actor-tools.md) and [development story map](docs/actor-item-story-map/index.md).
Lore Items expose owner-aware stored modifiers and labelled ranks. Actor Skills
combines independent Lore specialty references with selected transformed
character/NPC modifiers, DCs and proficiency data. Owner-local Item IDs join
current Lore to its actual contributor; rank remains distinct from a total.
NPC source reading includes authored attributes, defenses, skills, movement and
IWR with source provenance. Explicit Actor description reads separate bounded
NPC blurb, public notes and GM-private notes. Selected current NPC statistics,
Skills and Strikes are available separately; target-context application and
local elite/weak recalculation remain unsupported.
Explicit NPC strikes and abilities expose actual owned attack/action Item
references for follow-up reading, with partial completeness and token context.
Character/NPC Strikes also expose declared current attack data and bounded
alternative usages. Generated unarmed attacks retain Actor paths without invented
Item UUIDs; accessor-backed PC MAP fields stay explicitly unread. Damage and
target eligibility remain unsupported. See the
[current Strike contract](docs/actor-item-story-map/strike-current-contract.md).
Effect source preserves duration units, badge types/formulas and context fields.
Explicit relationships resolve immediate origin/target identities with permission
and token-context checks. Formula evaluation and effective expiry remain unsupported.
Condition source preserves valued flags, persistent-damage metadata, local
references and override slugs. Explicit relationships resolve actual owner-local
Item IDs; slugs remain unverified. Activity and suppression remain unsupported.
PF2e8.6.1 production disables dedicated affliction Items. Their functionality is
deferred outside this delivery until PF2e maintainers complete it. Discovery
reports `in_scope: false` and all reading support flags false; readable-type
filters omit the type. No affliction source/stage/timer interface is offered.
Poison/disease/curse descriptions on supported source Items remain readable.
Character ability navigation lists owned actions and feats/features with
canonical Item follow-ups for activation and prose. It remains partial; ownership
does not establish active benefits or an exhaustive list of available actions.
Weapon source includes damage, runes, range and ammunition configuration;
carried weapons are not automatically effective Strikes or usable attacks.
Ammunition reading preserves separate stock/uses and crafting categories. Only
explicit weapon selection follows a stack; carried effects are not applied.
Armor reading preserves stored defenses, thresholds, runes and carrying state;
source armor bonuses are not total Actor AC or automatic worn benefits.
Shield reading preserves source durability, reinforcing and integrated configuration;
held is not raised, and source values do not establish blocking or class benefits.
Equipment preserves usage, investment, traits and exact prose abilities;
uninvested mundane uses remain readable and magical benefits are not applied.
Consumable source separates stock, uses and healing/damage formulas; contained-spell
definitions and exact prose retain source-path identity without separate spell UUIDs.
Spell definitions preserve base rank, textual casting time, damage/healing and
variant source; entry links retain owner context without assuming castability.
Casting entries preserve mode-specific resource source and individual preparations;
zero slot counters do not prove exhaustion, and missing expenditure flags stay absent.
Actor casting joins owned spells, entries and individual preparations with focus
source; availability remains explicitly unevaluated in a partial section.
Containers preserve stored capacity and containment claims with unique descendants
and explicit cycles/missing parents; no total Bulk or unowned contents are inferred.
Treasure preserves category, quantity and denomination price/per independently;
Actor valuables remain readable without inferred sale proceeds or doubled value.
Actor inventory lists each actual possession once with stored container and
selected-ammunition links. Quantity, price/per and carrying source remain
independent; attachments and kit definitions do not create extra possessions.
Formula/spell book source and explicit immediate content links have deterministic
coverage; representative live book fixtures remain unavailable.
Kit readers preserve nested bundle definitions and explicit immediate component
links without importing inventory or recursively expanding referenced kits.
Ancestry readers separate offered/selected/alternate choices and source benefits
from character totals; named feature definitions do not imply acquisition.
Background readers preserve boost choices, training/Lore labels and definition
links. Character Build lists actual owned build Items once, typed source fields
and separate owner-local grant claims with exact reciprocal source evidence.
Options and future definitions do not establish acquisition; NPC/familiar Build
and effective benefits remain unsupported. See the [Build contract](docs/actor-item-story-map/build-contract.md).
Heritage readers preserve nullable ancestry associations and named links without
inferring owner ancestry, exclusivity or effective benefits.
Class readers preserve key-attribute choices, labelled starting ranks and
progression definitions without advancement, HP totals or acquired-feature claims.
Character readers preserve selected persisted identity, nullable manual attributes,
HP, labelled skill ranks, resources and recorded build choices. Biography and
language notes require explicit description reads. Explicit statistics adds selected
transformed attributes, AC/HP, saves, Perception/vision and movement for characters
and NPCs, retaining a separate basis from source. These sections remain partial.
Live checks cover character core statistics, Common language and empty
sense/IWR collections, plus broader existing NPC statistics. Populated character
sense/IWR configurations and target-dependent application remain unverified.
Character/NPC Skills and actual owner-local Lore joins passed live comparison
with public serialization and unchanged source fingerprints; conditional skill
variants and target-specific modifiers remain unevaluated. See the
[Skills contract](docs/actor-item-story-map/skills-current-contract.md).
Familiar current defenses, movement and ordinary skills use declared public
model fields after checking the recorded master's identity and permission.
Missing or denied masters retain source context without current statistics.
Combined-section tests preserve these boundaries alongside source, actions,
casting, inventory and state; normal familiar Strikes and independent attributes
remain unsupported. Live familiar current evidence covers a marked world Actor
and master unassignment; live compendium/token configurations remain unverified.
See the [familiar contract](docs/actor-item-story-map/familiar-current-contract.md).











## Private PDF references

An opt-in GM-private PDF library provides lexical lookup and source-page reading,
plus acknowledged uploads through the existing Foundry bridge. See
[PDF library setup, access policy and recovery](docs/pdf-library.md).
Do not share a PDF-enabled endpoint's MCP credentials with players.

PF2e deity reading preserves offered devotee options and explicit immediate spell
identity links. It does not infer acquired spells, prepared spells or active
character benefits. See the [deity field audit](docs/actor-item-story-map/deity-fields.md).

PF2e feat source reading distinguishes feats from features and nominal levels from
recorded taken levels, retaining prerequisites and description prose. Explicit grant claims resolve only within the actual Actor owner; reciprocal
acquisition and selection joins remain pending. Source rules never execute.

Recorded feat selections expose stored string/finite-number values only; unsupported
selection values make source partial, without acquisition or eligibility inference.
