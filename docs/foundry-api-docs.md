# Foundry API documentation in coding sessions

Grounded Docs is registered in `.codex/config.toml` as a stdio MCP server.
Codex launches `scripts/docs-mcp.sh` for each session in this trusted project.
The wrapper uses the pinned Docker image in `compose.docs.yml`; it downloads
the image only when absent. `scripts/codex.sh` provisions it before discovery,
so first-time downloads do not consume the MCP startup timeout.

Docker Engine/Desktop with Compose must be installed and running. No host
Node upgrade, embedding API key, exposed HTTP port, or systemd service is
required for documentation search. Telemetry is disabled. Existing Foundry
bridge setup and credentials are still required by the normal Codex launcher.

## Populate the documentation index

Before Foundry API work, use `list_libraries`, then `find_version` with the
runtime's major version as `targetVersion`. Use library `foundry-vtt`, version
`13`, for the official source
`https://foundryvtt.com/api/v13/`. Match the documentation major version to
the installed Foundry runtime; do not silently substitute latest docs.

Documentation and community TypeScript declarations may lag releases. Check
source URLs and index freshness, and read signatures, deprecations, and version
notes carefully. A matching major version does not guarantee compatibility
with every build. Confirm API assumptions against installed source or the
development runtime when behavior depends on them. Community declarations
such as `anandamideio/foundry-types` are supplementary evidence, not the runtime
source of truth. This index starts from official Foundry HTML documentation;
it does not import those community declarations.

If that version is missing, use `scrape_docs` to index the source, allowing
up to 2,000 pages and depth 5. Poll the returned job
until it finishes and verify that searching for `Actor createDocuments`
returns a method signature and an official Foundry source URL. Check the
job's page count and failures before treating the crawl as complete.
Use the tool's discovered schema for exact parameter names.
Search snippets can omit part of a signature or return inherited methods from
another class. Follow the source URL with `fetch_url` or the official website
when a snippet is ambiguous; verify the declaring class and full parameters.

Do not crawl during the stdio startup handshake. After reboot, reuse the
existing index. On a new machine or clone without its volumes, populate it
again. Refresh explicitly when documentation changes; do not refresh every
session. A failed or partial version needs repair, not another blind scrape:
inspect its job status and use `refresh_version` to retry or refresh it.

## CLI recovery

These commands use the same persistent storage as MCP:

```bash
./scripts/docs-setup.sh
./scripts/docs-cli.sh list
./scripts/docs-cli.sh scrape foundry-vtt https://foundryvtt.com/api/v13/ --version 13 --max-pages 2000 --max-depth 5 --scrape-mode fetch
./scripts/docs-cli.sh search foundry-vtt 'Actor createDocuments' --version 13 --limit 3
```

Prefer MCP tools for indexing while the session's server is running. Keep the
owning process alive until its job completes. Avoid starting other CLI or MCP
processes against the index during a crawl: concurrent initialization can
disturb in-progress status, and concurrent writes can lock SQLite. Poll the
owning server's job rather than starting another process to inspect progress.
CLI searches are useful when tools are unavailable and no crawl is active.
`./scripts/docs-cli.sh --help` describes
the pinned release's supported commands.

Compose stores the index and configuration in named volumes scoped by its
project name (the checkout directory name plus `-docs`). Sessions in the same
checkout share the index. Checkouts with the same directory name on one host
also share it; set `COMPOSE_PROJECT_NAME` before launching to isolate them.
Volumes survive container exit and reboot, but do not travel with Git.
Do not remove the volumes to fix a missing MCP connection.

## Missing tools or failed startup

Run `./scripts/docs-setup.sh` to restore the pinned image. Docker permission,
daemon, or network failures may need sandbox escalation or host setup.
Starting Grounded Docs and populating the official index are authorized
routine project setup. Codex's host approval and project trust rules still
apply on a new PC.

Check `/mcp` for actual tools. `codex mcp list` confirms registration only.
If discovery failed or configuration was added during a session, reconnect
or start a new session through `./scripts/codex.sh`. Do not start a detached
HTTP server: this integration intentionally uses Codex-owned stdio processes.

Upstream references: [Grounded Docs](https://github.com/arabold/docs-mcp-server),
[installation](https://github.com/arabold/docs-mcp-server/blob/main/docs/setup/installation.md),
and [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
