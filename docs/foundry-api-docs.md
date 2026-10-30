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

## PF2e wiki: discovery, indexing, and refresh

The upstream [PF2e wiki](https://github.com/foundryvtt/pf2e/wiki) is indexed
separately as `pf2e-wiki`. Use it for system workflows, rule elements, content
authoring, and research for PF2e feature requests. `pf2e-schema` is a separate,
versioned source; its presence does not establish that the wiki was indexed.
The wiki is rolling documentation, so omit `version` in the calls below. Do
not label it with the installed PF2e version or treat it as a release snapshot.

For a future LLM session:

1. Call `list_libraries` and `find_version({"library":"pf2e-wiki"})`.
   Reuse an existing index rather than scraping every session.
   `No matching version ... but unversioned docs exist` is the expected
   `find_version` response for this library, not a missing-index error.
2. Search with a bounded request, for example
   `search_docs({"library":"pf2e-wiki","query":"rule elements predicates","limit":3})`.
   Check that results cite pages under the upstream wiki URL. Follow a relevant
   URL with `fetch_url` when the snippet is insufficient. Empty search results
   do not prove that a capability is unsupported or that the whole wiki is absent.
3. If the library is missing, call `scrape_docs` with the following arguments.
   Inspect the current tool schema if its interface has changed.

   ```json
   {
     "library": "pf2e-wiki",
     "url": "https://github.com/foundryvtt/pf2e/wiki",
     "scope": "subpages",
     "maxDepth": 4,
     "maxPages": 100,
     "includePatterns": ["/^https:\\/\\/github\\.com\\/foundryvtt\\/pf2e\\/wiki(?:\\/[^/?#]+)?\\/?$/"],
     "excludePatterns": ["/\\/wiki\\/(?:_.*|.*\\/(?:_history|_edit|_compare))(?:[/?#]|$)/"],
     "followRedirects": true
   }
   ```

   This limits crawling to wiki root/page URLs, excluding query strings,
   history/edit/compare routes, repository code, issues and external sites.
4. Poll `get_job_info` using the returned `jobId` until completion. Keep the
   owning MCP session alive; do not start a concurrent CLI indexing process.
   Inspect failures and page counts, and compare coverage with the wiki's
   current page list. Hitting the page/depth limit is not proof of completeness.
   Search for both rule elements and a player/GM workflow to verify retrieval
   from distinct pages, rather than merely checking the library name.
   If MCP job details omit counts, run `./scripts/docs-cli.sh list` after the
   job has finished; inspect `status`, `uniqueUrlCount`, `documentCount` (text
   chunks, not pages), `indexedAt`, and `sourceUrl` for this library.
5. When an update is requested or the index is stale, call
   `refresh_version({"library":"pf2e-wiki"})`, then poll and verify again.
   Inspect a failed/partial job before retrying; do not delete the index or
   repeatedly launch blind scrapes. If GitHub prevents page discovery, compare
   the wiki's page list with crawl results and report the precise coverage gap.

Wiki guidance is evidence of documented PF2e usage, not permission to depend on
private system internals. Before implementing a feature, establish its schema
or supported API contract for the installed system version and verify relevant
runtime behavior. Continue to use `foundry-vtt` for core Foundry public APIs and
the [Actor/Item reference](pf2e-actor-item-reference.md) for existing research.

The index lives in the same persistent local Docker volumes described below.
These instructions travel with Git; scraped content does not. Other machines
or clients need access to that Grounded Docs index or must populate their own.

### Verification record

On 2026-10-30 UTC (2026-10-29 America/Denver), no `pf2e-wiki` library was
present. The bounded crawl above completed as job
`9c18ba4d-ff2a-476d-abfd-90cd5d831d98`. The catalog reported status `completed`,
13 unique URLs and 290 text chunks, indexed at `2026-10-30T03:01:02Z` from the
wiki root. The upstream homepage advertised 13 wiki pages; matching counts
support coverage but are not a page-by-page content audit. Actual MCP searches
for `rule elements predicates` and `Making a PC character creation` returned
content from `Quickstart-guide-for-rule-elements` and `Making-a-PC`, respectively.
The MCP job summary did not expose per-page failure details. Search text can
retain GitHub navigation and expiring screenshot URLs; indexing text does not
establish that screenshot content was captured. Existing `pf2e-schema@8.6.1`
had only one unique URL, so it must not be treated as a complete system schema
index.

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
