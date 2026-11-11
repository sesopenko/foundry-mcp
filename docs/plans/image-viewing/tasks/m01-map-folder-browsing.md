# M01 — Map folder browsing

Points: **8** — hierarchy, permission-aware pagination, and actual MCP discovery.
Dependencies: [01](01-contracts-and-baseline.md).
Intended commit: `feat(maps): browse world Scene folders and named maps`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
Read current public folder navigation patterns and Grounded Docs FolderData,
SceneData, Game collections, document permission, and serialization contracts.

## Implementation and interfaces

- Add strict typed `browse_maps` request/response models, browser RPC, Python
  adapter, actual registration through `tools.py`, and OAuth discovery metadata.
  Keep this core Foundry behavior independent of PF2e Actor-type filters.
- Read world Scene folders and Scene membership using public documents. Return
  immediate children of root or exact `Folder.<id>`, canonical identities,
  `parent_uuid`, names, named ancestry, sort context, and concrete folder/map
  next calls. Never scrape the sidebar DOM/prepared tree or activate a Scene.
- Implement the source design's literal local `name_contains` filtering,
  folders-first alphabetical/manual ordering and deterministic UUID tie-breaks.
  Include empty readable folders and Scenes without a usable image. Duplicate
  names remain separate. Invalid/non-Scene folders fail before content access.
- Return `location`, `revision`, `entries`, `total`, `complete`, `next_cursor`,
  `scope_status`, and `limitations`. Default 10 entries/8,000 bytes; bounds
  1–100 and 1,024–48,000. Bind cursors to caller/world, selection/filter, metadata,
  sorting, and permissions; allow count/byte bound changes. Preserve exact
  UUIDs, mark clipped names, and fail if minimum identity cannot fit.
- Distinguish empty selected folders, filtered absence, denied/partial scope,
  missing folders, malformed hierarchy/cycles, and stale continuation. Publish
  all normal inputs/output/recovery semantics, not just a tool-name summary.
- Capture bounded baseline discovery plus representative current Scene browsing
  before changing tools: at most 30 calls/120 seconds, private raw output,
  aggregate calls/compact bytes/completion/catalog size. Test measurement logic.

## Tests and acceptance

Add `tests/js/map-browse.test.js` and `tests/test_map_browse.py`. Cover root and
chapter nesting, duplicate Bonus Flip Mats/map names, manual/alphabetical sort,
empty/orphan/cyclic folders, filtering, Unicode, non-GM/denied scope, no image,
cursor binding/revision change, oversized entries and exact byte bounds. Assert
no canvas activation or PF2e requirement. Exercise actual MCP schemas/list/call
and OAuth metadata, including a mocked non-PF2e world.

Run outside the sandbox:

```bash
node --test tests/js/map-browse.test.js
.venv/bin/python -m unittest discover -s tests -p 'test_map_browse.py' -v
./scripts/test.sh
```

Accept when a fresh caller can navigate folder next calls and identify a map
by UUID/ancestry with truthful completeness. Commit models, RPC/adapter,
registration, focused tests, contracts, and baseline evidence together. Follow
the module refresh/console workflow when the development browser is available.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, discovery and baseline call/byte/completion data: not run.
- Public API evidence and exact pending runtime prerequisites: pending.
