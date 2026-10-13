# Build compendium journal reading tools

Implement MCP functionality for discovering, browsing, searching, and reading
JournalEntry documents in compendium packs. Start by reading AGENTS.md and its
required project documentation. This prompt captures requirements and exploration
so work can resume in a fresh session. No compendium implementation has started.

## Agreed scope and context

The world-journal reading feature is complete for now. Existing tools are
`get_journal_tree`, `get_journal_contents`, `search_journals`, and
`read_journal_page`; their contracts are in `docs/journal-tools.md`.

Compendiums are a separate part of Foundry's app. Expose a separate compendium
tool interface, rather than extending the world-journal tools to accept
compendium selectors. Shared internal processing is appropriate where it keeps
behavior consistent. Initial scope is finding and reading journal entries in
compendium packs, with text support only. Do not expand into reading Actors,
Items, Scenes, maps, images, PDFs, videos, macros, or importing content.

The user wants the LLM to browse an organization recognizable from Foundry:
compendium directory folders, packs, journal entries, then their pages and
outlines. Preserve names and hierarchical context alongside stable selectors.
Do not assume PF2e's layout applies to another system or publisher.

Return exact stored HTML, preserving markup, tables, emphasis, attributes,
entities, and Foundry link notation. Do not replace source with a lossy text
conversion. Derived text and excerpts can support search, clearly distinguished
from source. Original stored Markdown can be supported consistently with the
existing journal reader. Do not enrich or execute journal content.

Design every tool for a fresh LLM that has only MCP discovery and tool responses.
Follow the project-level self-documenting tool requirements in AGENTS.md:
purpose, next tools, scope, selector provenance, defaults/bounds, exact fields,
continuations, matching semantics, actionable errors, and examples where useful.

## GM goals

These journals help a GM understand how to play the game, rather than understand
an adventure. They are used both during preparation and for quick mid-game
reference. Representative goals include:

- Learn a procedure: “How does dying and recovery work?”
- Understand a concept: “What is the difference between concealed and hidden?”
- Resolve a situation: “A character falls unconscious while flying. What happens?”
- Look up a fact: “What is the DC for treating wounds?”
- Understand an option: “How does the champion class work?”
- Compare rules: “How do exploration activities differ from encounter actions?”
- Follow dependencies: “What should I understand before running a chase?”
- Prepare a reading list: “What rules should I review before an underwater session?”
- Refresh knowledge: “Remind me how persistent damage works.”
- Understand documented changes: “What changed about this rule in the remaster?”

Support finding relevant terminology when the GM does not know its official
name. Give source context suitable for citations and further reading. Keep
exceptions and conditions attached to rules; distinguish explicit rules,
advice, and inference. Report missing or conflicting evidence honestly.
Preparation favors explanation and further reading; mid-game use favors a
direct supported answer with optional detail. These are usage goals, not a
requirement that literal search itself perform semantic inference.

## API exploration already performed

Read-only exploration on October 12, 2026 observed Foundry **14.369**, world
`test`, system **pf2e 8.6.1**. Official v14 documentation then described build
14.368, so verify relevant behavior against the running build. Recheck versions
and connectivity when resuming; these observations are not permanent fixtures.

Documented public entry points:

- `game.packs`: collection of CompendiumCollection instances.
- `pack.documentName`: document type; restrict initial reads to JournalEntry.
- `pack.collection`: canonical package-and-pack identifier, e.g. `pf2e.journals`.
- `pack.title`, `folder`, `sort`, `visible`, `locked`, and `ownership`: useful
  pack presentation/access metadata. Locked means editing is locked, not that
  the pack cannot be read.
- `game.folders` includes folders with `type === "Compendium"`. The observed
  directory folder “Journals” contains the `pf2e.journals` pack. Its folder ID
  was `XLKUpnz8neK2AImF`; do not hard-code it.
- `await pack.getIndex({fields: [...]})`: lightweight entry index. Distinguish
  the index from documents currently loaded/cached in the collection.
- `await pack.getDocument(id)`: loads a complete document, using Foundry's
  browser cache when available. No world import is required.
- Loaded JournalEntry documents expose their embedded `pages`; page schema
  includes name, type, sort, title metadata, category, and text sources.
- `game.system.id`, `game.system.version`, and `game.version` identify system
  and core versions separately.

In this runtime the PF2e Journals index held seven entries:

| Entry | Pages |
| --- | ---: |
| Ancestries | 55 |
| Classes | 31 |
| Domains | 61 |
| Archetypes | 268 |
| GM Screen | 61 |
| Hero Point Deck | 53 |
| Remaster Changes | 7 |

All 536 pages were text pages. These seven entries had no assigned internal
folder and empty categories. Other packs may differ. Pages had title levels
and numeric sort values; collection iteration order was not always numeric
sort order. Represent ordering deliberately. A sampled maximum HTML length
was 34,705 UTF-16 units, so source reads need bounded continuation support.

The other available JournalEntry pack was `pf2e.criticaldeck`, titled
“Critical Hit/Fumble Deck”; its contents were not explored in detail.

Observed identifiers returned by documents:

```text
Compendium.pf2e.journals.JournalEntry.<entry-id>
Compendium.pf2e.journals.JournalEntry.<entry-id>.JournalEntryPage.<page-id>
```

Concrete sample: Ancestries entry ID `45SK8rdbbxvEHfMn`, Anadi page ID
`9dpHTBpL3j8ZpqTS`. Obtain current selectors from discovery, not these examples.

HTML contains cross-journal page UUID links, including heading anchors, and
many links to Item packs (heritages, feats, spells, deities, conditions, etc.).
Preserve labels and notation. Journal targets can be followed within scope;
Item targets must be marked outside supported reading scope rather than
silently fetched or presented as read evidence. Check relative/legacy UUID
resolution using documented APIs before choosing a supported contract.

Official documentation starting points:

- [Game](https://foundryvtt.com/api/v14/classes/foundry.Game.html)
- [CompendiumCollection](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html)
- [CompendiumPacks](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumPacks.html)
- [JournalEntry](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntry.html)
- [JournalEntry schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryData.html)
- [JournalEntryPage schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageData.html)
- [System](https://foundryvtt.com/api/v14/classes/foundry.packages.System.html)

Use grounded-docs according to `docs/foundry-api-docs.md`. Only documented,
externally callable public APIs and supported schema fields are dependencies.
Runtime observations, generated docs containing private members, sheet state,
DOM inspection, and publisher internals do not establish public support.
Internal pack-folder retrieval was not established during this exploration;
verify its supported API before claiming full internal hierarchy support.

## Cache idea: requested direction, unresolved contract

The user proposed caching compendium reads in the Python MCP server to avoid
repeated browser round trips, keyed by pack, system ID, and system version.
Those fields are available, but do not establish complete freshness:
module/world packs and user edits can change independently of system version.

Before implementing a cache, determine owning-package identity/version through
supported APIs, isolate Foundry instances/worlds and authorized access contexts,
and specify invalidation after edits, package changes, reconnects, and world
changes. Consider core version and output/schema version where relevant.
Investigate documented `updateCompendium` hooks and their coverage rather than
assuming they cover every change. Foundry already caches loaded documents in
the browser; a server cache is an additional layer. Record whether data is
cached and what freshness is guaranteed. Do not serve stale/unauthorized data
silently when the browser disconnects. Cache persistence, eviction, lifetime,
and offline behavior have not been agreed. Explain the proposed tradeoff before
making an architectural change; existing architecture describes Python as a
proxy and the browser as authoritative, and will need updating if caching lands.

## Proposed build plan

1. Establish the baseline: inspect repository status, current implementation,
   supported Foundry versions, actual MCP discovery, health, and connected test
   world. Follow repository development skills. Native MCP sessions were stale
   after a prior server restart; exploration succeeded with a fresh authenticated
   FastMCP client. Reconnect once rather than restarting a healthy server.
2. Verify the public APIs for directory folders, pack indexes, document/page
   retrieval, internal folders, permissions, links, ordering, and change events.
   Check declared minimum version as well as the current runtime. Probe small
   representative samples; avoid dumping entire compendiums into context.
3. Define concrete separate compendium contracts. Candidate operations are
   directory discovery, pack entry browsing, entry page/heading outlines,
   scoped text search, and exact page reading. Names and grouping are proposals,
   not already-approved schemas. Provide useful names/context and stable IDs,
   explicit unsupported types, completeness, revisions, count/byte limits,
   returned continuations, and error recovery. Keep scope clear when browsing
   directory folders containing unsupported pack types.
4. Resolve cache behavior and bounded search loading. Metadata browsing should
   use indexes; text search may require loading documents. Avoid an implicit
   unbounded scan of every pack. Specify scope, lazy loading, resource bounds,
   and whether results are partial. Choose a minimal justified cache design.
5. Establish deterministic tests for existing behavior before refactoring shared
   code. Implement read-only Foundry module handlers and Python MCP validation/
   orchestration. Reuse source slicing/search/outline logic where appropriate
   while keeping compendium and world selectors distinct. Add tests alongside
   behavior, including duplicate names, ordering, links, unsupported content,
   large pages, exact source reassembly, permissions, stale cursors, and any
   implemented cache isolation/invalidation. Validate actual discovery contracts.
6. Run focused checks after meaningful changes, then the repository's live
   development loop: refresh changed browser code, wait for readiness/bridge,
   inspect console errors, and verify public API behavior in the test world.
   Run `./scripts/test.sh` before a commit. Keep fixtures read-only unless a
   disposable mutation fixture is deliberately needed for invalidation tests.
7. Document final contracts, API support, cache guarantees, and limitations.
   When implementation is ready, commit code before beginning fresh-agent
   behavioral evaluation, as previously requested by the user.
8. Follow `docs/mcp-tool-evaluation.md`: deterministic checks first; one small
   relevant GM task, two independent fresh contexts, fixed limits, measured
   tagged calls, and source references prepared independently of tester answers.
   Stop when enough evidence is obtained. A third run needs a specific unresolved
   issue; no broad benchmark campaign. Preserve answers for GM review and mark
   unreviewed references exploratory. Bytes/timing are not billed GPT usage.

The prior world-journal E1 evaluation used two fresh agents, two calls each,
within 8-call/120-second caps. It confirmed a narrow search/read path, not
compendium usability or broad rule-answering reliability. Do not reuse it as a
compendium baseline. Reserve GPT usage for building rather than excessive tests.

