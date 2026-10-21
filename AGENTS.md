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

## Foundry public API requirement

Implement module features using documented, externally callable Foundry public
APIs and document schema fields for the supported Foundry versions. Standard
JavaScript and browser APIs may be used for processing returned data. Follow
Foundry's [public/private API guidance](https://foundryvtt.com/api/v14/).
Appearing in generated API documentation alone does not make a member public:
check its visibility and annotations.

Do not depend on undocumented runtime properties, private/internal members,
protected methods intended for subclass use, underscore-prefixed internals,
private fields, sheet preparation state, UI DOM structure, or publisher/module
implementation details. Do not monkey-patch Foundry internals to expose data.
Build hierarchical views from supported document relationships when a public
UI/tree API is unavailable.

Runtime object exploration and installed-source inspection may explain behavior
or verify a documented API, but neither establishes that an observed member is
supported for external use. Before adopting a Foundry dependency, identify its
official documentation, supported version, and public status. If public status
is unclear, leave it out of production code and use a documented alternative
or state the capability limitation. Feature detection and passing live tests
do not make an undocumented dependency acceptable.

Respect deprecations and declared module compatibility. Public APIs can still
change across Foundry versions; use focused tests and live verification for
supported versions rather than promising compatibility with future releases.

## PF2e-specific functionality and portability audits

Pathfinder Second Edition (`pf2e`) is the primary game system for this project.
PF2e-specific tools, document schema fields and supported system APIs are
explicitly allowed. Implement useful PF2e behavior directly when appropriate;
support for other systems is not a prerequisite, and a generic abstraction or
multi-system adapter framework is not required before delivering a feature.

Before Actor, Item or encounter-state work, read the
[PF2e Actor/Item research reference](docs/pf2e-actor-item-reference.md) and
[actor-reading handoff](docs/prompts/actor-reading-plan.md). They record the
agreed character/NPC/familiar scope, rulebook-to-schema translations, identity
and raw/mapped response requirements, and unresolved verification gaps.
Keep documented evidence and proposed behavior distinct when updating them.

This permission includes dependencies on PF2e's supported system interfaces and
document schemas despite the general restriction on publisher/module
implementation details above. It does not authorize private/internal members,
sheet preparation state, DOM scraping or monkey-patching. Use upstream PF2e
documentation and schema definitions to establish system-specific contracts;
record the supported/tested system version and verify relevant behavior in the
existing development runtime. Runtime observations alone are not an API contract.

Make system assumptions easy to find during a later portability audit:

- In every PF2e-specific function's docstring or JSDoc, explicitly say
  `PF2e-specific`, identify the relevant actor/item types, schema fields or
  system API dependencies, and describe any source-versus-derived-value
  assumptions. Link the upstream documentation/schema and record version
  constraints or the tested version at the implementation boundary.
- For an otherwise generic function with a PF2e-only branch, annotate that
  branch inline and document the conditional behavior in the function's docs.
  Keep PF2e logic in clearly identifiable helpers when that improves readability.
- Published MCP tool descriptions must state which functionality or response
  sections require PF2e and how other systems are handled. Check the system ID
  before applying PF2e semantics; return an actionable unsupported-system error
  or explicit unsupported sections instead of silently interpreting another
  system's data as PF2e.
- Add focused tests for PF2e behavior and the non-PF2e boundary. Distinguish
  verified support from untested actor types or system versions. Update these
  inline contracts alongside implementation changes, not only external docs.

## Foundry API documentation MCP

Use the `grounded-docs` MCP tools for Foundry API documentation before writing
code that calls Foundry APIs. Follow [the documentation workflow](docs/foundry-api-docs.md)
to check the `foundry-vtt` index, populate a missing runtime major version,
and verify search results. Indexing official Foundry docs is authorized.

Read documentation and type declarations critically: they can lag Foundry
releases. Community declarations (including `anandamideio/foundry-types`) are
not authoritative proof that an API exists or behaves that way in the installed
runtime. Check the runtime version, indexed documentation version, source URL,
and index freshness. Even matching major versions can differ between builds.
Verify relevant signatures and behavior against installed source or a live
development runtime when compatibility matters. State unresolved differences;
do not silently assume older declarations or cached docs describe current APIs.

Codex starts this stdio server automatically. If tools are missing, run
`./scripts/docs-setup.sh`; Docker image downloads and routine startup are
authorized. Use `./scripts/docs-cli.sh` for inspection or searches while
recovering. Reconnect or restart Codex if discovery failed; shell startup
alone does not add tools to the current session. Do not run a second detached
documentation server or delete persistent volumes. Prefer `./scripts/codex.sh`
on fresh clones to provision the image before MCP discovery.

## Self-documenting MCP tools

Design tools for a fresh LLM session with no prior repository or game-world
exploration. Tool descriptions/docstrings are part of the interface contract:
each must stand on its own in MCP discovery. For every tool, document the
following where applicable:

- Purpose, when to use it, and the next useful tool by name.
- Scope, required runtime/user permissions, supported content, and exclusions.
- Required inputs, defaults, bounds, and allowed or conflicting combinations.
- Identifier types and provenance: which tool supplies each selector, whether
  names/paths are accepted, and how document IDs differ from UUIDs.
- Exact response field names and meanings, node kinds, and hierarchy.
- Exact continuation fields and how to pass them back, including revision or
  stale-result handling. Distinguish count, depth, and byte limits; callers
  should use returned continuation data rather than construct cursors.
- Search/matching semantics and what empty results do and do not establish.
- Actionable errors for invalid inputs, unsupported content, missing documents,
  and stale continuations, with recovery steps.
- A short usage example when it resolves ambiguity.

Descriptions must match implemented schemas and behavior. Finalize concrete
defaults, bounds, response fields, and continuation contracts before release;
placeholder descriptions are insufficient. Do not rely on earlier conversation
context or require failed calls to discover normal usage.

Expose names and hierarchical context alongside stable IDs. Clearly distinguish
empty results, unsupported content, incomplete results, and missing documents.
Describe retrieval limits and search semantics so an LLM can plan a complete
investigation and avoid treating a partial response as exhaustive evidence.

When adding or changing tools, validate their actual MCP discovery descriptions
and input schemas as well as their runtime behavior. A fresh client should be
able to discover, navigate, search, read, and continue results using only the
published tool contracts and returned data.

## Required reading

Before doing work in this repository, read these files in full:

- [README.md](README.md): project overview, development setup, and dependency workflow.
- [pyproject.toml](pyproject.toml): direct Python dependencies.
- [docs/mcp_foundry_architecture.md](docs/mcp_foundry_architecture.md): architecture, RPC protocol, and design principles.
- [foundry-module/scripts/README.md](foundry-module/scripts/README.md): Foundry client script conventions.

This list carries forward the required reading from `.aider.conf.yml`. Keep the guidance in the referenced files as the source of truth rather than duplicating it here.

## Continuous testing

For behavioral MCP evaluation, follow
[the budgeted evaluation process](docs/mcp-tool-evaluation.md). Prefer focused
deterministic checks. When fresh-agent testing is warranted, select one relevant
task and use two independent runs; a third needs a concrete unresolved issue.
Declare run limits, record actual calls/statistics, and stop once the criteria
are met. Do not automatically expand into broad benchmarks or spend usage
collecting more passing examples. One question per tester makes costs
attributable. Agent self-reported counts are not measurement evidence.

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

For authentication and bridge lifecycle changes, use deterministic Python and
JavaScript tests as the default feedback loop. Cover credential validation and
role isolation, concurrent admission, acknowledgment ordering, stale socket
callbacks, timeout/retry behavior, and secret-free diagnostics without asking
for repeated Foundry logins or exploratory browser sessions. Run focused checks:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_production_auth.py' -v
node --test tests/js/authentication.test.js tests/js/bridge.test.js tests/js/main.test.js
```

Reserve live checks for behavior mocks cannot establish, such as actual Foundry
world-setting persistence, browser TLS/WSS acceptance, or LibreChat's configured
header delivery. Reuse existing evidence when those dependencies are unchanged.
If a required live session is unavailable, record the precise verification gap
and continue independent implementation/testing; do not request repeated manual
setup or present unit coverage as proof of deployment behavior.


## Reuse existing Foundry instances

Foundry setup requires significant manual work from the user. Reuse existing
instances, worlds, credentials, and browser profiles rather than creating new
ones for convenience or routine verification.

- The root `docker-compose.yml` instance is the default for active development,
  module changes, browser checks, and Foundry runtime API verification.
- The existing fixture in `.local/compose-v13.yaml` (localhost port 30013) is
  reserved for testing Docker packaging. Preserve its data and completed setup;
  do not repurpose it as another development or routine compatibility instance.
- Exploratory local Foundry testing for Docker packaging is needed only after
  significant Docker Compose changes. Routine code changes, image rebuilds,
  version bumps, and documentation changes do not justify repeating manual
  Foundry setup or package installation. Prefer automated tests and isolated
  MCP container smoke checks that do not provision another Foundry instance.
- Create a new Foundry instance only when absolutely necessary and neither
  existing instance can perform the required check. Explain the concrete need
  and expected manual setup burden to the user before provisioning it. A clean
  installation, extra version matrix, or desire for isolation alone is not a
  reason to create one automatically.
- Do not reset or delete existing instance data, repeat license activation,
  replace configured worlds, or demand fresh setup to simplify agent testing.
  If a required check cannot use the existing instances safely, report the
  verification gap rather than shifting unplanned setup work onto the user.

These rules take precedence over older plans, verification checklists, or
skills suggesting fresh disposable Foundry instances. Keep the gaming Foundry
installation outside development automation.

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


## Version bumps and Foundry module updates

For an authorized release (version bump, commit, tag and push), use the
repository-local [foundry-release skill](.agents/skills/foundry-release/SKILL.md).
The LLM selects the semantic version by reviewing Git history and the actual
release diff since the last stable release tag, including current changes;
do not default to patch increments or ask the user to manage version numbers.
An explicit user-supplied version or narrower publication scope takes precedence.


Every release version bump must keep the server, container, and Foundry module
synchronized. Follow [the release instructions](docs/operations.md#module-versioning-and-releases)
and update all of the following in the same change:

- The project version in `pyproject.toml` and the matching project entry in
  `uv.lock`; do not change unrelated dependency versions or hashes.
- Source build identities in `foundry_mcp_server/build-info.json` and
  `foundry-module/scripts/buildInfo.js`, keeping their build kind `source` and
  release tag/revision unset. Runtime application version is loaded from metadata.
- Dockerfile version argument, local Compose
  build-version argument, and version-dependent packaging test expectations.
- `foundry-module/module.json`: set `version` to the new `X.Y.Z` and `download`
  to `https://github.com/sesopenko/foundry-mcp/releases/download/vX.Y.Z/foundry-mcp.zip`.
  Keep `manifest` at the stable update URL:
  `https://github.com/sesopenko/foundry-mcp/releases/latest/download/module.json`.
  Foundry uses that manifest to discover updates; publishing only a Docker
  image does not update the installed Foundry module.
- Current version examples in deployment files, README, operator documentation,
  and the Docker Hub overview where applicable. Preserve historical verification
  records rather than rewriting their tested versions.

Before committing, run `./scripts/test.sh` and
`.venv/bin/python scripts/package-module.py --tag vX.Y.Z`, substituting the new
version. Resolve version, manifest, and archive validation failures before
creating a release tag. When publication is authorized, push the matching
`vX.Y.Z` tag and check both image publication and module release jobs. Confirm
the GitHub release contains `module.json` and `foundry-mcp.zip`, and the stable
manifest advertises the new version and matching ZIP. Never move an existing
release tag or replace an existing version's release assets.

## Docker Hub repository overview

[docs/docker-repository-overview.md](docs/docker-repository-overview.md) is the
copy-and-paste source for the public Docker Hub repository overview. Keep it
current whenever image names/tags, release behavior, Compose configuration,
environment variables, authentication, endpoints, supported capabilities,
Foundry setup, or LibreChat/Codex integration changes. Update it in the same
change as the behavior it documents.

Keep the overview self-contained: use absolute public GitHub/documentation URLs
rather than repository-relative links, include working Compose and `.env`
examples, and explain the browser bridge and client authentication. Use only
generic hosts and placeholder credentials; never include private deployment
addresses, registry information, or real secrets. Verify YAML/TOML examples
and current official client documentation when changing integration guidance.
Do not publish the Docker Hub overview automatically; the user copies it.

## Local code graph

Use the `code-graph` MCP server for structural questions about this checkout's
Python server, Foundry JavaScript, and tests. See
[setup, tool examples, freshness and recovery](docs/code-graph.md).
If tools are missing, run `./scripts/code-graph-doctor.sh`. Provision missing
dependencies with `./scripts/dev-setup.sh` before a new Codex session.
Use `./scripts/codex.sh --code-only` for source analysis without the Foundry stack.

For a known area, start with `module_overview` or named `get_ast_node`;
use `project_map` for orientation. Begin compact, with small result counts and
call depth 1–2. Use `get_ast_node(include_impact=true)` or `find_references`
before changing shared behavior. Include tests when selecting validation.
Read current source before editing: edges can be inferred, incomplete or stale.
No callers does not establish that an entry point is unused. Use `rg` for exact
RPC methods, hooks, settings keys and dynamic dispatch; trace Python and
JavaScript sides of WebSocket methods separately.

Use Grounded Docs and existing Foundry verification guidance for external API
contracts; a local graph does not establish public API status or runtime support.
For incomplete results, check local index/parse health, attempt one targeted
recovery, then fall back to `rg` and source reading. Do not dump the whole graph
or rebuild after every edit.
