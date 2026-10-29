# Local Python and JavaScript code graph

This development workflow pins [sdsrss/code-graph-mcp v0.174.0](https://github.com/sdsrss/code-graph-mcp/tree/v0.174.0)
(commit `b3553b5aca0630c28f5b20f60113ae8a7535aea7`), npm
`@sdsrs/code-graph`. The similarly named PyPI project is unrelated.
One checkout-local structural index covers the Python server, Foundry JavaScript,
tests, and useful scripts. It is a cache, not a source of external API contracts.

## Bootstrap on Debian 13 amd64

```bash
./scripts/dev-setup.sh --install-system-packages
# With Debian prerequisites already installed:
./scripts/dev-setup.sh
./scripts/codex.sh --code-only
```

System provisioning uses configured Debian repositories and sudo when needed:
ca-certificates, curl, git, nodejs, npm, python3, ripgrep and util-linux (flock).
Debian's Node 20.19.2 works; CI also retains Node 22 for application tests.
Python 3.12 comes from uv, selected by `.python-version`, rather than Debian's
system Python 3.13. A working uv on PATH is preserved; `~/.local/bin/uv` is the
fallback in both setup and launcher. If absent, setup downloads Astral's official
versioned installer (pin in `scripts/dev-setup.sh`), disables profile edits,
verifies the executable and removes its temporary installer. Existing uv is
never upgraded. `uv sync --locked` preserves Python dependency resolution.
A different existing Git hooksPath is preserved.

Setup and doctor need neither Codex/login nor Docker, systemd, Foundry, models,
a compiler, Rust, GPU, database service or embedding key. Linux arm64 packages
are selectable but arm64 is untested. Other platforms are rejected.
Only launching Codex requires your installed/authenticated CLI. Accept its
normal project trust prompt; setup does not change trust configuration.

`codex.sh --code-only` must put the wrapper option first. It prepares the graph
and disables grounded-docs, foundry-vtt and chrome-devtools for that invocation,
skipping their startup and credential loading. Normal `codex.sh` retains Docker
Docs, the Foundry service and caller-token behavior; `codex-dev.sh` also starts
the dedicated browser and rejects `--code-only`. Both preserve sandbox/approval
settings and Codex arguments. Absolute launcher paths work from another cwd.
Raw `codex` must be run from the repository root after setup, in a fresh session.
The tracked project table is the only registration; no global server is added.

## Commands and ownership

```bash
./scripts/code-graph.sh --version
./scripts/code-graph-setup.sh --check
./scripts/code-graph-doctor.sh
./scripts/code-graph-doctor.sh --mcp-smoke
```

The resolver validates the root exact dependency, installed wrapper/platform
versions, local real paths, executable permission and native version. It resolves
the platform package relative to the parent package, supporting nested or hoisted
npm layouts. The wrapper executes that file directly; upstream's shared-cache
launcher, npx and global binaries cannot override it. Runtime policy disables
auto updates, model downloads and upstream gitignore edits; snapshot seeding is
disabled in `.code-graph.toml`. No custom include/exclude schema is used.

Setup holds a checkout-local lock for at most 15 seconds. Its atomic dependency
fingerprint includes both npm manifests, Node/npm versions, platform and arch.
Every invocation also validates the executable. Warm setup skips npm. `--check`
never installs: on drift, exit this checkout's Codex sessions and run dev-setup.
Explicit setup uses `npm ci --include=dev --include=optional`, which replaces
node_modules; stop **all** consumers of this checkout's npm tooling first,
including Chrome MCP. Active graph lock ownership prevents reconciliation.
An interrupted install has no valid readiness fingerprint.

Each checkout/worktree owns its regular `.code-graph/index.db`. Queries refuse
missing local databases and symlinked graph directories/databases, preventing
upstream's main-worktree fallback. Do not share graph directories between
worktrees. Git, production Docker's allowlisted context, and module ZIP packaging
exclude these caches and development npm tools.

The scanner respects Git/ignore rules and skips hidden/dependency directories.
`.ignore` excludes `/data/` runtime module copies; this also affects default `rg`
searches. Inspect that packaging fixture explicitly with `rg --no-ignore data/`
when working on it. Source and tests stay included. Ignore rules are navigation
policy, not an authorization boundary.

## Use the discovered tools

The pinned engine's actual `tools/list` was checked with the SDK smoke client.
Start compact; read current source before edits. File paths are repository
relative. Use returned IDs for ambiguity and returned continuation instructions
for truncation; do not infer completeness from a bounded result.

| Question | First call |
| --- | --- |
| Unfamiliar checkout | `project_map(compact=true, max_tokens=2000)` |
| File/directory contents | `module_overview(path="foundry_mcp_server/ws/", compact=true, max_tokens=2000)` |
| Known symbol | `get_ast_node(symbol_name="FoundryConnectionManager", file_path="foundry_mcp_server/ws/connection.py", compact=true)` |
| Change impact | `get_ast_node(symbol_name=..., file_path=..., include_impact=true, compact=true, max_tokens=2000)` |
| Callers and callees | `get_call_graph(symbol_name=..., file_path=..., direction="both", depth=2, compact=true, include_tests=true, max_tokens=2000)` |
| Rename references | `find_references(symbol_name=..., file_path=..., compact=true, include_tests=true)` |
| Concept/phrase | `semantic_code_search(query=..., language="javascript", top_k=5, compact=true)` |
| Structural match | `ast_search(query=..., limit=10)` or filters `type`, `returns`, `params` |

Only project_map, module_overview, get_ast_node and get_call_graph advertise
`max_tokens` (100–100000; start 2000). It estimates output bytes/3, not billed
Codex tokens. Call depth is 1–10; start 1–2. Search top_k/limit and AST limit are
1–100. `get_ast_node` also accepts node_id; file_path alone is insufficient.
`find_references` accepts symbol_name or node_id. Use actual discovered schemas
for further options. There are seven tools; old tutorials naming direct
impact_analysis/dependency_graph/find_dead_code tools describe a different surface.

Doctor reports actual search_mode and embedding_status. Bootstrap passes
`--no-embed`; the environment disables model downloads but permits an already
cached model. In `fts_only` mode, semantic_code_search performs lexical search,
not vector semantics. Optional embeddings require a separately reviewed setup.
Edges may be inferred/ambiguous/incomplete; honor confidence and ambiguity
information. No callers is not proof that a hook or entry point is unused.

## Trace the WebSocket boundary explicitly

Locate Python `get_journal_tree`, read its `_call("getJournalTree", ...)`
contract and follow FoundryConnectionManager.call. Then bridge the languages:

```bash
rg -n 'getJournalTree|rpcHandlers|handleRpcMessage' \
  foundry_mcp_server foundry-module/scripts tests
```

Read JS handleRpcMessage's rpcHandlers dispatch, the imported journal handler,
and the Python/JavaScript tests. Inspect each side's graph neighborhood separately;
a combined index does not establish a Python-to-JavaScript runtime edge.
Use the same discipline for decorators, Hooks.once/on, callbacks, computed names
and Foundry globals. This indexes repository source, not Foundry core, systems,
rulebooks or game state. Grounded Docs and live verification retain their roles.

## Freshness and recovery

Before launch, setup runs incremental-index with no embeddings, a 120-second
outer timeout (5-second kill grace), and CODE_GRAPH_YIELD_TO_SERVER=1. It validates
the JSON mode and local health. Failure/timeout is not indexing success. A skipped
refresh is accepted only with an already verified healthy graph and active lock
owner. Warm setup probes the regular primary index.lock with nonblocking flock
and immediately defers freshness to the server. File/PID text alone is not
ownership. Never delete lock files or force a concurrent rebuild.

The server watches files and refreshes on the next graph **query**; health alone
is not a freshness barrier. Do not externally index while it serves: query/hash
caches may remain stale. After branch switches or large refactors, restart via
the launcher. For confirmed stale/incompatible caches, stop that checkout's
Codex graph processes, then:

```bash
./scripts/code-graph.sh rebuild-index --confirm --no-embed --json
./scripts/code-graph-doctor.sh --mcp-smoke
```

Restart Codex. Try one targeted recovery, then use rg/source if incomplete.
Doctor rejects unhealthy/interrupted/stale indices and parse errors (fields may
be absent when no errors exist). Missing tools after configuration changes need
a fresh Codex session. `codex mcp list` establishes registration only; real queries
establish usable connectivity. Setup/serve prints no banners on protocol stdout.

## Verification and upgrades

For repeated verification with one stable approval command, run:

```bash
./scripts/code-graph-verify.sh
```

It checks graph setup/health/MCP, native fixtures, both repository suites,
module packaging and whitespace. All output goes to the fixed ignored file
`.local/code-graph/verification.log`; failures print the last 35 lines.
The command does not install dependencies or start Codex, Docker or Foundry.
A lock prevents concurrent verification from overwriting that log. Reuse the
same command without adding shell redirection or changing log filenames.

Run offline repository tests separately with `./scripts/test.sh`. Native fixture checks:

```bash
CODE_GRAPH_INTEGRATION=1 .venv/bin/python -m unittest discover -s tests -p test_code_graph.py -v
```

The Debian CI job bootstraps twice in debian:13 without Codex/Foundry and runs
native fixtures. Before setup it trusts only the mounted checkout path in the
container shell user's Git configuration: checkout's action-local trust does
not cover that user's different HOME/ownership context. A real-Git regression
test simulates different ownership and verifies this step precedes local hooks
configuration, without a wildcard trust exception.
The smoke client bounds initialization, initialized notification,
list/query and shutdown to 90 seconds, asserting exact names, paths and line
locations for FoundryConnectionManager and handleRpcMessage. `--dump-schemas`
prints the observed catalog for upgrade review. Fixture tests cover local engine
selection, ignored sentinels, source/tests, Python and JS cross-file callers,
watcher create/edit/rename/delete, warm lock ownership and missing executable.

Upgrades are explicit exact npm dependency/lockfile changes. Inspect upstream
CLI/tool schemas, rerun Debian and MCP checks, and provision with consumers
stopped. Rebuild on index incompatibility only. Git preserves the prior pin/lock
for rollback. No percentage savings claim is made from this integration.

### Acceptance record (2026-10-20)

- Host: Debian 13.7 amd64, Node 20.19.2, npm 9.2.0, uv 0.9.16,
  managed Python 3.12.12, native engine 0.174.0. Initial host full index took
  170 ms (101 files at that point); later counts change as tooling is added.
- Clean `debian:13` amd64 Docker environment: installed Debian prerequisites,
  provisioned uv/Python from scratch, bootstrapped twice and passed both exact
  repository MCP probes on both runs. The second skipped npm; first npm install
  took 702 ms. Native fixture checks passed in 4.657 seconds. No Foundry, Codex
  login or model download was used. This container check preceded the final
  verification-runner/recovery-test additions; CI runs the current files.
- Repository Python/JavaScript suites, native fixtures, MCP smoke and module
  packaging are covered by the repeatable verification command above. Production
  Docker allowlisting and the module archive allowlist remain unchanged.
- Baseline suite was started before implementation but stalled in the existing
  PDF worker test inside the restricted sandbox. It was stopped; a host rerun
  passed. No pre-change failure was attributed to graph integration.
- Codex CLI 0.163.0 discovered code-graph in a fresh source-only exec session,
  but its two MCP attempts were blocked: `MCP tool call requires approval, but
  approval policy is never`. That noninteractive attempt failed; direct SDK lookup acceptance passed. No approval/trust policy was weakened.
  After the user restarted, both real MCP lookups succeeded in the interactive
  Codex session: FoundryConnectionManager at connection.py lines 15–84 and
  handleRpcMessage at foundryBridge.js lines 100–140. All seven tools were
  discovered. This closes actual Codex lookup acceptance without a
  startup-grace or approval-policy change.
- Arm64 and a paired agent efficiency measurement remain unverified. Native
  fixtures additionally create a real linked worktree, reject queries before
  its own index exists, then create and query a separate local database. No
  broad benchmark or claimed token savings was produced. The bounded Codex
  check used two failed tool calls and reported 37,921 input tokens (30,976
  cached), 171 output tokens; these are acceptance costs, not efficiency evidence.
