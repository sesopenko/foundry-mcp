# Integrating code-graph-mcp into foundry-mcp development

## Goal and implementation choice

Add a repeatable Debian 13 development workflow that gives Codex CLI a local structural index of the Python server, Foundry JavaScript module, and their tests. An agent should be able to bootstrap the tools, discover their MCP interface, locate relevant symbols, inspect callers and dependencies, and read the right source without repeatedly scanning the repository.

**Recommended upstream:** [sdsrss/code-graph-mcp](https://github.com/sdsrss/code-graph-mcp), distributed as **`@sdsrs/code-graph`** on npm. Start with exact version **`0.174.0`**, release tag `v0.174.0`, upstream commit `b3553b5aca0630c28f5b20f60113ae8a7535aea7`. This implementation bundles Python and JavaScript Tree-sitter parsers and a native executable. One npm development dependency covers both languages. [U1]

The PyPI distribution named `code-graph-mcp` is a different implementation. This plan deliberately identifies its upstream and package coordinates; do not substitute packages based on the shared display name.

**Review baseline:** `sesopenko/foundry-mcp` main at `4f18bf8fe73df1fb6363dc093d490591b147047a`, reviewed on October 20, 2026. The repository was inspected read-only. The npm registry confirms that version 0.174.0 of the wrapper, Linux x64, and Linux arm64 packages exists. This is an implementation plan; installation, Debian execution, and Codex acceptance must still be completed by the implementing agent.

## 1. Fit the existing repository

The current repository already has the pieces this integration should extend. [R1–R4]

| Existing component | Integration decision |
| --- | --- |
| `pyproject.toml`, `.python-version`, `uv.lock` | Keep using uv-managed Python 3.12 for the application. Code-graph adds no Python runtime dependency. |
| Root `package.json` and `package-lock.json` | Add an exact npm development dependency alongside `chrome-devtools-mcp` 1.10.1. |
| `.codex/config.toml` | Add a project MCP server named `code-graph`. |
| `scripts/codex.sh` | Prepare the graph before Codex starts and discovers tools. |
| `scripts/codex-dev.sh` | Inherit the graph integration through the existing launcher. |
| Root `AGENTS.md` | Add a short operational section linking to the detailed guide. |
| `scripts/test.sh` and existing launcher tests | Extend focused coverage and retain the existing Python and JavaScript verification workflow. |
| Production Dockerfile and allowlisted Docker build context | Keep graph tooling confined to development files and npm development dependencies. |

Index the checkout root so the graph can include:

- `foundry_mcp_server/**/*.py`
- `foundry-module/scripts/**/*.js`
- `tests/**/*.py` and `tests/js/**/*.js`
- Useful source helpers under `scripts/`

Use the same graph for both languages. A graph containing both languages does not establish runtime connections between them; the WebSocket boundary is handled explicitly in section 7.

## 2. Debian 13 baseline

Debian 13 provides Python 3.13 by default, while this project requires `>=3.12,<3.13`. The project environment must therefore use the existing uv-managed 3.12 interpreter. Debian's system Python remains useful for existing shell helpers that invoke `python3`. [D1, R1]

Debian 13's Node package is currently 20.19.2. This satisfies the graph wrapper's `node >=16` requirement and the already locked Chrome DevTools package's `^20.19.0` range. The existing CI uses Node 22; keep that coverage and add Debian 13 coverage for the actual target environment. [D2, U1, R2]

### Planned first-run command

```bash
./scripts/dev-setup.sh --install-system-packages
```

This is a **new project command to implement**, not a command currently present in the repository. On a machine with prerequisites installed, `./scripts/dev-setup.sh` should suffice.

The optional system-package flag should install missing packages from the machine's configured Debian repositories:

```text
ca-certificates curl git nodejs npm python3 ripgrep util-linux
```

`util-linux` supplies `flock`. Native graph packages are available for Linux x64 and arm64; make Debian 13 amd64 the initial required acceptance target, and claim arm64 support only after a corresponding test. A prebuilt engine should not require Rust, a compiler toolchain, a graph database service, a GPU, or an embedding API key. [U1]

### uv provisioning

Reuse a working `uv` already on PATH. If absent, first check `~/.local/bin/uv`; if it is also absent, install the repository's existing CI baseline, uv **0.9.16**, through Astral's versioned official installer into the user executable directory. Download the installer to a temporary file, fail on HTTP errors, execute it with shell-profile modifications disabled, verify the resulting executable, and clean up the temporary file. Pin the installer version in one documented location. Do not silently upgrade an existing uv installation during graph setup. Astral documents version-specific installer URLs and the no-PATH-modification option. [D3]

Both `dev-setup.sh` and `codex.sh` must handle the `~/.local/bin` fallback. PATH changes made by a bootstrap subprocess do not persist into the user's next terminal command.

Once prerequisites are available, the language/bootstrap portion performs:

```bash
uv python install 3.12
uv sync --locked
./scripts/code-graph-setup.sh
./scripts/code-graph-doctor.sh --mcp-smoke
```

Use the existing `.python-version` and lockfile; do not regenerate dependency locks during bootstrap. Where the existing Git commit hook is provisioned, preserve a different pre-existing `core.hooksPath` rather than overwriting it.

### Keep source analysis independently usable

The existing normal launcher also requires Docker, Compose, and the systemd user service because it starts Grounded Docs and the Foundry bridge. Those are existing application-development prerequisites, not requirements of the code graph. [R3]

Add one project-wrapper option:

```bash
./scripts/codex.sh --code-only
```

Consume this option before forwarding arguments to Codex. In this mode, prepare the graph, skip documentation-container and Foundry-service startup and credential loading, and disable `grounded-docs`, `foundry-vtt`, and `chrome-devtools` for that Codex invocation using existing Codex configuration overrides. Preserve the launcher's sandbox and approval settings. This mode requires the user's installed and authenticated Codex CLI, but no running game or browser.

The normal `./scripts/codex.sh` and `./scripts/codex-dev.sh` retain their established purposes. Reject `--code-only` in `codex-dev.sh` with a clear message because its purpose is to start the development browser. Keep the new wrapper flag in prefix position: `./scripts/codex.sh --code-only [Codex arguments...]`.

## 3. Pin the engine that actually runs

Add the dependency once during implementation:

```bash
npm install --save-dev --save-exact @sdsrs/code-graph@0.174.0
```

Commit `package.json` and the resulting `package-lock.json` together. Subsequent provisioning uses:

```bash
npm ci --include=dev --include=optional
```

The native engine is delivered through an optional platform dependency. An npm install can finish while an optional package is missing, so the executable must be checked explicitly. `npm ci` uses the lockfile without rewriting it, and replaces an existing `node_modules` tree when it runs. [U1, D4]

### Important upstream launcher behavior

The upstream npm launcher can prefer a binary in a shared user cache whose version is newer than the installed package. An exact npm version alone therefore does not pin the executed engine. [U2]

Implement `scripts/resolve-code-graph.cjs` to select the executable from this checkout's installation only. The `.cjs` extension is intentional because the project declares `"type": "module"`.

The resolver must:

1. Read the exact expected version from the root `package.json` development dependency.
2. Resolve `@sdsrs/code-graph/package.json` from the checkout root and verify the installed version equals that pin.
3. Select `@sdsrs/code-graph-linux-x64` or `@sdsrs/code-graph-linux-arm64` using Node's platform and architecture.
4. Resolve the platform package from the parent package directory so both hoisted and nested npm layouts work.
5. Verify its version equals the same pin and its real path lies inside this checkout's `node_modules`.
6. Locate `code-graph-mcp` beside the platform package's `package.json`, verify it is executable, and verify its native `--version` output.
7. Print only the absolute executable path on stdout; diagnostics go to stderr and failures return nonzero.

The Bash wrapper executes that native file directly. It does not go through `node_modules/.bin/code-graph-mcp`, global PATH discovery, `npx`, or the upstream Claude plugin launcher. This is what makes the selected engine reproducible. [U1, U2]

## 4. Script contracts and idempotence

Keep a small set of entry points with distinct responsibilities.

| New file | Required behavior |
| --- | --- |
| `scripts/dev-setup.sh` | Debian prerequisite checks, optional apt provisioning, uv provisioning, locked Python sync, graph setup, and first-run verification. |
| `scripts/code-graph-setup.sh` | Verify or install locked npm dependencies, prepare the checkout's local index, and report concise readiness. A `--check` mode used by launchers must never install or replace dependencies. |
| `scripts/resolve-code-graph.cjs` | Resolve and validate the exact native engine described above. |
| `scripts/code-graph.sh` | Establish checkout cwd, apply graph policy, resolve the native binary, and `exec` the requested upstream command. |
| `scripts/code-graph-doctor.sh` | Check package/native versions, local index health, language coverage, and optionally the MCP protocol. |
| `scripts/code_graph_smoke.py` | Implement the bounded MCP handshake and real-query checks behind `--mcp-smoke`, using the MCP SDK already installed through the project's locked dependencies. |

Setup and doctor must work without the Codex executable, a Codex login, Docker, or a running Foundry instance. Check Codex availability only when launching Codex or running the separate real-session acceptance gate.

Every shell script should use Bash, `set -euo pipefail`, quoted arguments, and a root derived from `BASH_SOURCE`. Scripts must work when called by absolute path from outside the repository and when the checkout path contains spaces. Use `exec` for the long-running MCP process so signals and shutdown reach it.

### Setup algorithm

1. Acquire a bounded, checkout-local setup lock, for example under `.local/code-graph/`. It covers dependency reconciliation and is released before a long-running server is executed.
2. Compute a fingerprint from `package.json`, `package-lock.json`, Node version, npm version, platform, and architecture.
3. Validate the installed package and native executable even when a saved fingerprint matches.
4. If everything matches, skip npm entirely.
5. If it differs, `--check` fails with one actionable instruction: exit this checkout's Codex sessions and run `./scripts/dev-setup.sh`. Explicit setup can run `npm ci` when consumers of this checkout's npm tools are stopped.
6. Write the successful dependency fingerprint atomically only after npm and executable validation succeed. A failed install must not be recorded as ready.
7. If the dependencies and checkout-local index are valid and the native primary index lock is held, skip external indexing immediately. Report that the active server owns freshness.
8. Otherwise run the bounded index preparation command below, then validate the actual JSON result and local health.

The key invariants are no lockfile changes on repeated setup, no dependency reinstall on a warm launch, no automatic upgrades, no overwritten user configuration, and no successful-looking marker after a failed operation. Index caches may be updated as source changes; idempotence does not require an immutable cache timestamp.

### Valid upstream commands

These command names and flags are verified for v0.174.0. [U3]

```bash
./scripts/code-graph.sh --version
./scripts/code-graph.sh incremental-index --no-embed --json
./scripts/code-graph.sh health-check --json
./scripts/code-graph.sh serve
```

There is no general `serve --root` flag in this release. The wrapper must `cd` to the checkout root.

For setup's incremental-index invocation, set the yield flag and impose an outer timeout:

```bash
CODE_GRAPH_YIELD_TO_SERVER=1 \
  timeout --kill-after=5s 120s \
  ./scripts/code-graph.sh incremental-index --no-embed --json
```

The 120-second limit is an initial project choice to measure on Debian, not an upstream requirement. A timeout must return an actionable failure and must not mark indexing complete. Upstream can wait up to 600 seconds for its build lock before it checks the yield flag, so the warm-checkout precheck avoids an unnecessary wait. [U3]

Upstream's ordinary incremental-index command warns about an active server's index lock but can still proceed. With the yield setting it returns a successful JSON result with `mode: "skipped"` if another process owns the index. Keep the setting as a race guard even after the precheck. Treat a skipped result as a skipped refresh, not evidence that indexing completed; accept it only for an already verified warm checkout whose running server owns freshness. [U3]

Probe the existing regular `.code-graph/index.lock` with nonblocking `flock`: file existence or PID text is not proof of a running process. This probe is not a substitute for the pre-session rule when replacing npm dependencies. Never unlink a supposedly stale lock file: OS lock ownership is authoritative, and unlinking can split the lock across different inodes. Do not build a PID-managed graph daemon.

### Launcher shape

This illustrates the wrapper to implement; error handling and the resolver must be completed with the contracts above.

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$repo_root"

export CODE_GRAPH_DISABLE_MODEL_DOWNLOAD=1
export CODE_GRAPH_NO_GITIGNORE=1
export CODE_GRAPH_NO_AUTO_UPDATE=1

binary="$(node "$repo_root/scripts/resolve-code-graph.cjs")"
exec "$binary" "$@"
```

Add a guard for commands that read or serve an index: require the checkout's own `.code-graph/index.db`. Permit first-time index creation through `incremental-index`. This prevents the worktree fallback described below. The wrapper's serve path must perform no installs, downloads, banners, or setup chatter on stdout.

## 5. Index ownership, exclusions, and freshness

### Local ownership

The upstream database lives at `.code-graph/index.db`. Add `/.code-graph/` to the tracked `.gitignore`. Upstream normally adds an ignore rule to local Git exclusions when missing; `CODE_GRAPH_NO_GITIGNORE=1` lets the project own this policy. [U4]

Each checkout and worktree must build its own database. The native CLI may fall back to the main checkout's database when a linked worktree has no local index. Require a local database before queries and never share or symlink `.code-graph` across worktrees. The upstream itself rejects a symlinked graph directory. [U5]

Treat the graph database as a regenerable local cache. Keep it out of Git, release archives, and container images. Existing production Docker allowlisting already excludes development tooling. [R4]

### Exclusions

The scanner respects `.gitignore`, `.ignore`, global Git ignores, and `.git/info/exclude`; it skips hidden directories and hard-excludes common dependency directories such as `node_modules`. There is no verified `.codegraphignore` format or include-roots schema to introduce. [U4]

Review exclusions for:

```text
.git/  .venv/  node_modules/  .code-graph/  .local/
.browser-dev/  foundry-data/  pdf-library/  pdf-state/
dist/  build/  coverage outputs  generated releases
```

Most are already excluded by the repository or by the hidden-file rule. Add only missing rules. Use a small tracked `.ignore` entry for `/data/` if needed to exclude runtime/module copies that are tracked for packaging purposes. Explain that `.ignore` also affects ripgrep's default searches; inspect that packaging fixture explicitly when working on it.

Verify exclusions with harmless sentinel files in a disposable fixture. In particular, ensure an excluded directory containing a `.py` or `.js` file contributes no symbols. Keep tests and actual source included. Ignore rules control navigation, not an authorization boundary.

### Disable external snapshot seeding

Create `.code-graph.toml` with the supported snapshot setting:

```toml
[snapshot]
disabled = true
```

The verified config parser supports snapshot settings; do not invent `[index]`, `include`, or `exclude` fields. Local source should build this project's graph. [U6]

### Model policy

Bootstrap uses `--no-embed`, and the launcher sets `CODE_GRAPH_DISABLE_MODEL_DOWNLOAD=1`. Structural navigation and full-text retrieval must work without downloading a model. [U3, U7]

That environment variable disables model downloads, not use of an already cached model. Health diagnostics should report the actual `search_mode` (`fts_only` or `hybrid`) and embedding state. In FTS-only mode, the MCP tool named `semantic_code_search` provides lexical retrieval without vector semantics. Optional embeddings can be evaluated later as a separately pinned setup change; they are not an initial acceptance prerequisite.

### Freshness lifecycle

Prepare the initial graph before Codex launches. During the session, the native server starts its watcher and refreshes changed files on the next graph query. No extra watcher, Git hook, port, container, or systemd service is needed. A health/status call alone does not guarantee pending source edits were indexed. [U7]

After a branch switch or large refactor, prefer restarting through the project launcher so pre-session incremental preparation runs. While a server is live, use its normal query freshness path. The server keeps query and hash caches that arbitrary external index writes do not reliably invalidate. Do not run a competing external refresh or full rebuild. [U7]

For a confirmed stale/incompatible index, stop that checkout's Codex graph processes and run:

```bash
./scripts/code-graph.sh rebuild-index --confirm --no-embed --json
```

Then run doctor and start a new Codex session. Keep `--force` out of normal recovery instructions. [U3]

## 6. Codex CLI configuration and startup

Append this project configuration, preserving existing MCP tables:

```toml
[mcp_servers.code-graph]
command = "bash"
args = ["./scripts/code-graph.sh", "serve"]
enabled = true
required = false
startup_timeout_sec = 60
tool_timeout_sec = 120
enabled_tools = [
  "project_map",
  "module_overview",
  "get_ast_node",
  "get_call_graph",
  "find_references",
  "semantic_code_search",
  "ast_search",
]
```

Codex supports these settings and project MCP configuration for trusted repositories. The timeout values are starting integration choices to validate. The seven names are the actual advertised tool surface of the pinned release. [C1, U8]

The relative script argument follows the repository's existing convention: `scripts/codex.sh` establishes the repository root before starting Codex. This is an explicit launcher contract, not an assumption that Codex interpolates arbitrary path strings. Test normal and source-only launch from another directory via the launcher's absolute path. Document root invocation if users run raw `codex` directly.

Modify `scripts/codex.sh` in this order:

1. Resolve and enter the checkout root; handle the uv executable fallback.
2. Consume the optional `--code-only` prefix.
3. Run `scripts/code-graph-setup.sh --check` to verify dependencies and refresh the graph without installing packages.
4. For normal mode, retain the existing documentation setup, server startup, and caller-token handling.
5. For source-only mode, supply per-invocation disables for the three other MCP servers.
6. `exec codex` with the existing sandbox/approval settings and all remaining arguments preserved.

Do not register a second global MCP server during bootstrap. The tracked table is the registration and remains idempotent across clones.

The current Codex documentation describes an initial catalog wait for optional servers. Check that graph tools are available in the first usable session turn, especially on cold startup. If the installed CLI's catalog timing causes a failure, use its documented startup-grace setting for the project launcher and record the tested version; avoid changing this setting speculatively for all existing servers. [C1]

A project trust prompt must be handled by the user in Codex's normal flow. Setup must not edit user trust configuration to bypass it. After an integration/configuration change, start a fresh session. `codex mcp list` checks registration; a successful MCP query checks connectivity and usable indexing.

## 7. Guidance that improves agent efficiency

Create `docs/code-graph.md` with installation, commands, tool routing, freshness, recovery, and limitations. Add a short section to the existing root `AGENTS.md`; keep detailed schemas and examples in the linked guide. Codex loads repository agent guidance, and the current root file already contains substantial required instructions. [C2, R5]

### Suggested AGENTS.md addition

```markdown
## Local code graph

Use the `code-graph` MCP server for structural questions about this checkout's
Python server, Foundry JavaScript, and tests. Setup, examples, and recovery:
[docs/code-graph.md](docs/code-graph.md).

If tools are missing, run `./scripts/code-graph-doctor.sh`. Provision missing
dependencies with `./scripts/dev-setup.sh` before a new Codex session. Use
`./scripts/codex.sh --code-only` when only source analysis is needed.

For a known area, start with `module_overview` or a named `get_ast_node`.
Use `project_map` when orientation is needed. Begin with compact output,
small result counts, and call depth 1–2; expand the relevant symbol only.
Use `get_ast_node(include_impact=true)` or `find_references` before changing
shared behavior. Include tests when selecting validation.

Read current source before editing. Graph edges can be inferred, incomplete,
or stale. No callers does not establish that an entry point is unused.
Use `rg` for exact RPC methods, hook names, settings keys, and dynamic dispatch.
Trace the Python and JavaScript sides of a WebSocket method separately.

Use Grounded Docs and existing Foundry verification guidance for external API
contracts. A local graph does not establish that a Foundry API is public or
available in the installed runtime.

If graph results are incomplete, check local index and parse health, perform
one targeted recovery, and fall back to `rg` plus source reading. Do not dump
the whole graph or rebuild it after every edit.
```

### Tool routing

| Question | Initial tool and bounds |
| --- | --- |
| How is this unfamiliar checkout organized? | `project_map(compact=true, max_tokens=2000)` |
| What is in this file or directory? | `module_overview(path=..., compact=true, max_tokens=2000)` |
| Where is a known symbol and what does it expose? | `get_ast_node(symbol_name=..., file_path=..., compact=true)` |
| What may a change affect? | `get_ast_node(..., include_impact=true, compact=true, max_tokens=2000)` |
| Who calls this, and what does it call? | `get_call_graph(symbol_name=..., file_path=..., direction="both", depth=2, compact=true, include_tests=true, max_tokens=2000)` |
| Which references matter for a rename? | `find_references(symbol_name=..., file_path=..., compact=true, include_tests=true)` |
| Which symbols match a concept or phrase? | `semantic_code_search(query=..., language="python" or "javascript", top_k=5, compact=true)` |
| Which definitions match a structural condition? | `ast_search(query=... or a structural filter, limit=10)` |

The exact schemas vary by tool: do not add `max_tokens` to tools that do not advertise it. The upstream budget is an output-size estimate, not a measurement of Codex's billed token usage. Honor ambiguity, confidence, truncation, and continuation information returned by tools. [U8]

Older examples mentioning direct tools such as `impact_analysis`, `dependency_graph`, or `find_dead_code` do not describe the current advertised interface. The guide must be derived from actual `tools/list` on the pinned engine, not older tutorials.

### The Python–JavaScript boundary

A concrete project example is the journal-tree operation. Python `get_journal_tree` calls `_call("getJournalTree", ...)`; the helper uses `FoundryConnectionManager.call` to send RPC. JavaScript `handleRpcMessage` selects `rpcHandlers[method]`, where `getJournalTree` names the imported handler. [R6]

Teach the agent to:

1. Locate the Python tool and its call path using the graph.
2. Read the literal RPC method and parameter contract in source.
3. Search the literal method across both source roots.
4. Inspect the JavaScript handler and local graph neighborhood.
5. Inspect the relevant Python and JavaScript tests.

For example, this source query bridges what static analysis cannot prove:

```bash
rg -n 'getJournalTree|rpcHandlers|handleRpcMessage' \
  foundry_mcp_server foundry-module/scripts tests
```

Apply the same discipline to `Hooks.once`, `Hooks.on`, callbacks, decorators, computed property names, and runtime Foundry globals. A graph of repository code is not an index of Foundry core, installed game systems, rulebook PDFs, or live game state. Existing documentation and runtime tools serve those purposes.

## 8. Acceptance criteria and focused tests

### First establish the baseline

Run the existing test suite once before implementation and retain relevant failures. The integration must not be credited with existing failures or silently work around them.

### Deterministic acceptance

Implement black-box script tests and a small MCP smoke client. Use a disposable fixture for source mutation/exclusion tests, not live Foundry data.

| Gate | Required evidence |
| --- | --- |
| Debian compatibility | Clean Debian 13 amd64 environment installs the pinned packages, runs the native engine, and indexes both languages. Record OS, architecture, Node, npm, uv, Python, engine, and Codex versions. |
| Repeatability | Two consecutive setups succeed; the second makes no tracked-file or lockfile changes and skips npm reconciliation when its inputs and installation are unchanged. |
| Exact engine | Wrapper and platform package versions equal the root pin; the executable path is local. A newer shared-cache binary does not change selection. |
| Recovery | Missing platform executable or stale dependency fingerprint is detected; an interrupted install has no successful marker. |
| Path handling | Absolute launcher invocation from outside the repository and a checkout path with spaces both work. |
| Worktree ownership | Two worktrees have separate local databases; a worktree with no local graph cannot query the main checkout's graph through project wrappers. |
| Index coverage | Known Python and JavaScript symbols resolve to their exact expected files; required source/test files are represented. |
| Exclusions | Sentinel `.py` and `.js` files under excluded runtime/dependency directories are absent from results. |
| Freshness | Create, edit, rename, and delete fixture symbols; subsequent MCP queries reflect the changes within a bounded timeout. |
| MCP protocol | Initialize, send initialized notification, list tools, call tools, and cleanly close the child process. Parse stdout as protocol data so banners or install output fail the check. |
| Active-session behavior | Repeated warm setup immediately skips external indexing when the primary lock is held; the yield flag guards races and an outer timeout bounds waiting. Package-changing setup requires sessions to stop; no forced concurrent rebuild or lock-file deletion occurs. |
| Codex usability | A fresh trusted session actually calls a Python lookup and a JavaScript lookup through `code-graph`; listing configuration alone does not pass. |
| Source-only launch | Codex receives graph configuration with other project MCP servers disabled, without Docker/systemd/Foundry startup. |
| Existing workflow | Normal and browser-development launchers preserve argument forwarding, credentials, and sandbox settings; existing suites pass. |
| Packaging | Graph packages and databases are absent from the production build context/image and module ZIP. |

Use these real repository probes initially:

```text
Python: FoundryConnectionManager
        foundry_mcp_server/ws/connection.py

JavaScript: handleRpcMessage
            foundry-module/scripts/foundryBridge.js
```

For MCP calls, use `get_ast_node` with the exact `file_path` and `symbol_name`; assert the returned identity and location, not a brittle total symbol count. Also use a tiny fixture with an explicit Python import/call and JavaScript ES-module import/call to validate cross-file relationships. Do not demand a fabricated Python-to-JavaScript call edge.

`health-check --json` exposes `healthy`, index-version state, search mode, and parse-error information. A nonempty graph alone is insufficient: reject incomplete/interrupted indexing and inspect parse errors in required source paths. Fields for parse-error files can be absent when there are none. [U3]

Run focused launcher/tooling tests during implementation, then `./scripts/test.sh`. Add a small development-tool smoke job in a Debian 13 container; it should need neither the Codex executable/login, Foundry credentials, nor model access. Record the Codex version separately when doing the real-session acceptance check. Avoid making Docker image publication depend on a live browser or an LLM session.

### Measure usefulness without a broad benchmark

Follow the existing budgeted MCP evaluation guide. Choose one representative task, such as tracing `get_journal_tree` through RPC to its handler and identifying the tests. Use one baseline session and one graph-enabled session with the same task, model, and checkout. Record correctness, actual calls, source bytes read, elapsed time, and available token usage. Treat this as a small adoption check, not a statistically reliable percentage-savings claim. [R7]

Installation and deterministic verification require no model-generated answers. Do not spend LLM usage repeatedly proving the same setup works.

## 9. Implementation sequence and completion checklist

### Phase 1 — Dependency and executable selection

- Add the exact npm devDependency and lockfile changes.
- Implement the native binary resolver and wrapper.
- Validate executable identity and `--help`/`--version` on Debian 13.
- Add local graph ignores and the disabled-snapshot configuration.

**Done when:** the pinned native engine is executable from any working directory and cannot be replaced by a shared-cache version.

### Phase 2 — Bootstrap and local indexing

- Implement Debian prerequisite handling, uv fallback, and locked environment sync.
- Implement setup fingerprints, atomic successful state, bounded locking, and `--check` behavior.
- Build the local index without requiring a model download.
- Add doctor and MCP smoke verification.

**Done when:** a fresh checkout and repeated bootstrap pass both language probes and exclusion/freshness tests.

### Phase 3 — Codex integration and Markdown guidance

- Append the project MCP table.
- Extend the existing launcher, including the `--code-only` prefix option.
- Update launcher tests and preserve existing credential behavior.
- Add `docs/code-graph.md`, the short `AGENTS.md` section, and README quickstart links.

**Done when:** a fresh Codex CLI session uses both language lookups, and source-only launch works independently of the Foundry stack.

### Phase 4 — Verification and handoff

- Run deterministic Debian and repository checks.
- Perform the small paired usefulness check if warranted by the existing evaluation budget.
- Record tested versions, observed timings, unresolved graph limitations, and any acceptance gaps in the guide.

**Done when:** another agent can follow the Markdown quickstart, bootstrap with one command, launch Codex, and use the graph without reconstructing this conversation.

### Upgrade and recovery policy

Updates are explicit dependency changes: choose a new exact upstream version, regenerate the npm lockfile, inspect its tool/schema changes, and rerun focused Debian and MCP checks. Provision the updated environment with active consumers stopped. Treat index schema changes as cache lifecycle events, and rebuild only when required. Keep the previous package pin and lockfile available through Git for rollback.

## 10. Ready-to-use implementation brief

> Implement this plan in `sesopenko/foundry-mcp` after reading the existing repository guidance and required architecture files. Use `sdsrss/code-graph-mcp`, npm package `@sdsrs/code-graph` pinned to 0.174.0, for a single local graph of Python, JavaScript, and tests. Extend the current npm, uv, Codex, and script conventions. Resolve and execute the exact local native platform binary, because the upstream npm launcher can select a newer shared-cache binary. Add idempotent Debian 13 setup, local-worktree index preparation, a doctor/MCP smoke check, project Codex configuration, a source-only launcher option, concise AGENTS.md instructions, and a detailed Markdown guide. Verify real symbols in both languages, ignored runtime data, edit/rename/delete freshness, repeated setup, and unchanged packaging boundaries. Report the resulting diff, executed checks, and any remaining acceptance gaps. Use this plan's cited pinned source to resolve CLI/schema uncertainty; do not invent flags or assume the graph understands WebSocket dispatch.

## Sources

### Target repository at the reviewed commit

- **R1:** [Python manifest](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/pyproject.toml), [.python-version](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/.python-version), [README](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/README.md).
- **R2:** [npm manifest](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/package.json), [npm lockfile](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/package-lock.json), [CI](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/.github/workflows/ci.yml).
- **R3:** [Codex project configuration](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/.codex/config.toml), [Codex launcher](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/scripts/codex.sh), [browser launcher](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/scripts/codex-dev.sh), [server service helper](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/scripts/server.sh).
- **R4:** [Dockerfile](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/Dockerfile), [Docker build allowlist](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/.dockerignore), [Git ignores](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/.gitignore).
- **R5:** [AGENTS.md](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/AGENTS.md), [architecture](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/docs/mcp_foundry_architecture.md).
- **R6:** [Python journal tools](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/foundry_mcp_server/mcp_server/journals.py), [JavaScript RPC dispatch](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/foundry-module/scripts/foundryBridge.js).
- **R7:** [Budgeted MCP evaluation](https://github.com/sesopenko/foundry-mcp/blob/4f18bf8fe73df1fb6363dc093d490591b147047a/docs/mcp-tool-evaluation.md).

### Pinned code-graph implementation

- **U1:** [v0.174.0 package manifest](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/package.json), [Linux x64 manifest](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/npm/linux-x64/package.json), [release](https://github.com/sdsrss/code-graph-mcp/releases/tag/v0.174.0), [published wrapper metadata](https://registry.npmjs.org/@sdsrs%2Fcode-graph/0.174.0), [published Linux x64 metadata](https://registry.npmjs.org/@sdsrs%2Fcode-graph-linux-x64/0.174.0).
- **U2:** [Native binary selection](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/claude-plugin/scripts/find-binary.js).
- **U3:** [Index CLI and concurrency](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/cli/index_ops.rs), [index locks](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/indexer/lock.rs), [health output](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/cli/health.rs), [command dispatch](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/main.rs).
- **U4:** [Scanner and ignore behavior](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/indexer/merkle.rs), [ignore maintenance](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/utils/gitignore.rs).
- **U5:** [Project/worktree root selection](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/cli/paths.rs).
- **U6:** [Supported snapshot configuration](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/snapshot/config.rs).
- **U7:** [MCP server lifecycle](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/mcp/server/mod.rs), [embedding model loading](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/embedding/model.rs).
- **U8:** [Exact MCP tool schemas](https://github.com/sdsrss/code-graph-mcp/blob/v0.174.0/src/mcp/tools.rs).

### Platform and client documentation

- **D1:** [Debian 13 Python package](https://packages.debian.org/trixie/python3).
- **D2:** [Debian 13 Node package](https://packages.debian.org/trixie/nodejs).
- **D3:** [uv installation](https://docs.astral.sh/uv/getting-started/installation/), [installer options](https://docs.astral.sh/uv/reference/installer/), [managed Python](https://docs.astral.sh/uv/guides/install-python/).
- **D4:** [npm ci contract](https://docs.npmjs.com/cli/v10/commands/npm-ci/).
- **C1:** [Codex MCP setup](https://developers.openai.com/codex/mcp), [configuration reference](https://developers.openai.com/codex/config-reference).
- **C2:** [Codex AGENTS.md guidance](https://developers.openai.com/codex/guides/agents-md).
