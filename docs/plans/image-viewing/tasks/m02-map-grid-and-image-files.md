# M02 — Map grid and image files

Points: **8** — selected Scene/level metadata and bounded role-specific file inventory.
Dependencies: [M01](m01-map-folder-browsing.md), [02](02-browser-source-resolution.md).
Intended commit: `feat(maps): read grid dimensions and level image files`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
Verify public Scene, LevelData, GridData, TileData, and SceneDimensions contracts
against the installed major/build. Do not substitute legacy-looking properties
for the selected level or assume screenshot values describe every scene copy.

## Implementation and interfaces

- Add typed `get_map_info` models/RPC/adapter/actual MCP registration and OAuth
  metadata. Require a world Scene UUID; optional level ID filters the exact
  owning Scene's levels. Never choose the current canvas level implicitly.
- Implement `section=assets` (default) and `section=tiles` now. M03a adds notes;
  do not publish an unimplemented notes schema branch. Common response contains
  named scene identity/ancestry, `geometry`, exact grid fields, initial level ID,
  section, paged `entries`, revision, total/complete/cursor/scope/limitations.
- Assets entries represent levels with explicit separate background/foreground
  role records, including null/missing media. Preserve level ID/name/UUID and
  safe exact stored file path, media kind/support state, and image follow-ups.
  Prepare typed `map:{scene_uuid,level_id,role}` selectors for M05; until image
  tools accept them, use supported bare-src follow-ups or explicit unavailable
  follow-ups for sensitive references. M05 switches to scene-aware next calls.
- Geometry includes width/height, padding, shifts, and public scene rectangle.
  Grid includes type/size/distance/units/style/thickness/color/alpha, preserving
  null/missing/zero meanings. Source file pixel dimensions come from probing,
  not these scene dimensions. Distinguish Original Maps copies by ancestry.
- Tiles section lists bounded declared tile identity, safe file reference,
  placement, media kind, and verified level membership when available. It is an
  inventory, not scene compositing; do not include tokens, fog-state exports,
  journal bodies or every incidental world asset. Explicitly report tile-only
  scenes, videos, missing files, unsupported references, and additional artwork.
- Use the map extension's 10-entry/8,000-byte defaults, 100/48,000 maxima,
  revision-bound continuation and expected-revision checks. Do not fetch every
  image or perform picker listings merely to list configuration. A stored path
  is a reference; M05 still resolves fresh membership before fetching bytes.
  Credential-bearing/signed references remain private; raw source text is data.

## Tests and acceptance

Add `tests/js/map-info.test.js` and `tests/test_map_info.py`. Test all screenshot
grid fields (including 180 px/5 ft, 5940×7920, 0.25 padding), contrasting scene
copies, gridless/hex grids, explicit null/zero values, multiple levels, wrong
level ownership, background plus foreground, missing/video/S3-sensitive paths,
tile inventory, denied/stale scope, full pagination, invalid sections and byte
bounds. Verify public calls do not activate Scenes or use PF2e semantics.
Exercise actual MCP input/output validation and concrete next-call shapes.

Run outside the sandbox:

```bash
node --test tests/js/map-info.test.js
.venv/bin/python -m unittest discover -s tests -p 'test_map_info.py' -v
./scripts/test.sh
```

Accept when map browsing reaches explicit level/file choices and all configuration
is named, bounded, and truthful about composition and file existence. Commit
reader, typed contracts, tests, and file/grid guidance together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and complete asset/Tile workflows: not run.
- Public API evidence and exact pending runtime prerequisites: pending.
