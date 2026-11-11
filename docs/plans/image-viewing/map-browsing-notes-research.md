# Map browsing and note-label overlays: research handoff

Research date: 2026-11-11. Runtime inspected: **Foundry 14.369**, existing local
world **`test`**, authenticated Gamemaster in the dedicated development browser.
This file records findings and planning state; it does not claim that map
browsing or note overlays have been implemented.

## Recover context before continuing

After every context compression, resume, or handoff, read this file in full
alongside the [planning assignment snapshot](../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[authoritative image-preview design](../../prompts/foundry-image-previews-plan.md),
and [current task-plan index](README.md). Follow AGENTS.md and its required
reading before implementation. Recover the user's later map-browsing and
annotation requirements from this file; the source design now includes their
normative map extension. The measured observations below remain research facts.

The planning work through the 22-task sizing pass was committed as **`71b9065`**
(`docs: plan image previews as sized tested task graph`). It contains the source
design, assignment snapshot, dependency graph, and 22 task files. The hook
skipped tests under the staged Markdown-only rule; staged whitespace checks
passed. The existing task estimates total **140 points**, maximum **8**; eight
original 13-point tasks were split. Do not rerun their historical parents.

**Current planning state:** the user subsequently authorized augmentation. The
source design/index now include map browsing and annotation contracts, with
M01/M02, M03a/M03b, M04a/M04b, M05 and M06 as eight new tasks. Note extraction/
mapping and text/layout were each estimated at 13 and split into 5+8 tasks.
Final visual handoff 14b was re-estimated from 3 to 5. The current plan totals
**30 tasks / 200 points, maximum 8**. No feature implementation or new live
verification has been performed by this documentation update. Use the index
and amended source design for execution; the earlier candidate discussion here
is preserved as research history. Changes after `71b9065` remain uncommitted
unless later Git history shows otherwise.

## User intent and agreed direction

The user first requested an optional flag that renders map notes as text on the
image before delivery. The text identifying journals/notes must remain readable
without obscuring the map. They suggested inspecting real browser screenshots
to assess scale and explicitly requested findings before adding tasks.

They then requested a map-browsing capability that communicates the folder
hierarchy from the Scenes sidebar, map names, configured image file(s), scene
dimensions, and grid settings. The intended workflow is:

1. Browse map folders and distinguish similarly named maps.
2. Inspect the selected map's scene/level configuration and image files.
3. Fetch that map or a crop with map-note identifiers rendered on it.
4. Follow returned note/journal/page identities when more detail is needed.

The user said the proposed behavior works. The direction communicated back was
scene-aware browsing, explicit scene/level context, compact note keys in pixels,
and full note/journal/page identities in response metadata. The later planning
augmentation finalized tool names, selectors, pagination, layout policy and task
boundaries in the source design/index. Those are future implementation
requirements, not already-published interfaces. Do not replace pending
verification with assumed support.

The user supplied three screenshots: a Whistlefang Lair scene configuration,
its Grid tab, and the Seven Dooms for Sandpoint Scene-folder hierarchy. These
show a Current Level background reference, a 180-pixel square grid representing
5 ft, solid 1-pixel black grid lines with opacity 0.35, scene dimensions
5,940 × 7,920, padding 0.25, and shift 0/0. The sidebar includes chapter folders,
Original Maps, Bonus Flip Mats, and named maps within them. These are user
screenshot observations, not a live read of that exact scene copy.

## Documentation evidence and freshness

Used Grounded Docs `list_libraries`, `find_version(foundry-vtt,14)`, bounded
`search_docs`, and direct `fetch_url` reads of the official pages below. The
local v14 index reports completion, 1,978 unique URLs, 17,801 chunks, and an
index date of **2026-10-12T22:52:58Z**. Direct official-page reads supplement
that index. A matching major version alone does not prove exact build behavior.

| Contract | Official documentation | Finding |
| --- | --- | --- |
| Folder relationships | [FolderData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html) | `type`, `folder` parent ID, `name`, `sort`, and `sorting` (`a`/`m`) support reconstructing Scene-folder hierarchy from documents. |
| Scene configuration | [SceneData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneData.html), [Scene](https://foundryvtt.com/api/v14/classes/foundry.documents.Scene.html) | Scene folder, width/height, padding, shift, grid, initial level, embedded levels, and notes are core data; scene reading need not activate its canvas. |
| Scene coordinates | [SceneDimensions](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneDimensions.html), Scene `getDimensions()` | Public dimensions include `sceneX`, `sceneY`, `sceneWidth`, and `sceneHeight`; padding is rounded to grid alignment. |
| Grid settings | [GridData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.GridData.html) | `type`, `size`, `distance`, `units`, `style`, `thickness`, `color`, and `alpha` cover the screenshots' grid configuration. |
| Level image roles | [LevelData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.LevelData.html), [LevelTexture](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.LevelTexture.html) | Levels have separate background/foreground references, name, sort, elevation, visibility, and texture configuration. `LevelTexture.src` identifies the image/video reference. |
| Note content/coordinates | [NoteData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.NoteData.html), [BaseNote schema](https://foundryvtt.com/api/v14/classes/foundry.documents.BaseNote.html) | Note coordinates, `entryId`, `pageId`, `text`, `fontSize`, `fontFamily`, `textAnchor`, `textColor`, and `iconSize` are documented. Current BaseNote schema additionally includes `levels`. |
| Resolved note labels | [NoteDocument](https://foundryvtt.com/api/v14/classes/foundry.documents.NoteDocument.html) | Public getters `label`, `entry`, and `page` expose the label and linked journal/page. `text` is an optional override, not the full journal body. |
| Level applicability | [SceneLevelsSetField](https://foundryvtt.com/api/v14/classes/foundry.data.fields.SceneLevelsSetField.html) | Publicly described as a nullable set of specific Scene Level references. Empty/null membership semantics still need verification before use. |
| Scene thumbnails | Scene `createThumbnail()` | Documented as a scene-background thumbnail, default 300 × 100. It does not promise an export of arbitrary note text overlays. |
| Native note rendering | [Canvas Note](https://foundryvtt.com/api/v14/classes/foundry.canvas.placeables.Note.html) | `_getTextStyle()` is explicitly **protected** and describes tooltip styling. It must not become a production dependency. |
| Extra scene artwork | [TileData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.TileData.html) | Tiles can use image/video textures with their own positions, dimensions, anchors, and rotation; a background file is not necessarily the complete rendered Scene. |
| Server-side text composition | [libvips text](https://www.libvips.org/API/current/ctor.Image.text.html) | Supports font selection/font files, DPI, text masks/RGBA, and Pango markup. Its DPI and font units must be controlled and measured; arbitrary strings must not be passed as trusted markup. |

Use documented document relationships and serialized fields. Do not scrape the
Scene sidebar DOM, use a UI-prepared tree, call protected note styling methods,
or monkey-patch Foundry. Runtime observations below corroborate behavior but do
not establish public status for otherwise undocumented dependencies.

## Live catalog observations

The existing test world contains **50 Scenes and 18 Scene folders**. Multiple
folders have the same name, including Bonus Flip Mats under different parents.
Names alone are insufficient selectors. Return stable UUIDs, parent identity,
and named ancestry; preserve folder sorting mode and document sort context.

Read-only scene samples:

| Scene | Folder | Dimensions | Grid | Level/artwork observations |
| --- | --- | --- | --- | --- |
| C2. Whistlefang Ledge | The Pit | 1,100 × 1,500 | Square, 100 px, 5 ft; black solid 1 px lines, alpha 0.2 | One initial level, background present, foreground absent, one Tile. |
| Shrine of the Sandpoint Devil | Chapter 4: Footprints on the Roof | 6,800 × 9,000 | Square, 200 px, 5 ft; black solid 1 px lines, alpha 0.35 | One initial level, background **and foreground** present, three Tiles. |
| Whistlefang Lair | Original Maps | 3,300 × 4,600 | Square, 100 px, 5 ft; black solid 1 px lines, alpha 0.2 | One initial level, background present, foreground absent, one Tile. |

All samples used padding 0.25 and shift 0/0. The live Whistlefang Lair sample is
an Original Maps copy, with different dimensions/grid from the user's
screenshot. Do not claim those are the same configuration or overwrite one
with the other. This demonstrates why folder identity matters.

Runtime 14.369 exposes both embedded levels and legacy-looking `background`
serialization. Read declared level/background/foreground contracts rather than
assuming the legacy Scene field is the authoritative image for every level.
Level texture serialization contained `anchorX`, `anchorY`, `offsetX`, `offsetY`,
`fit`, `scaleX`, `scaleY`, and `rotation`. The exact supported public contract
and mapping for nondefault transforms still need a focused evidence check.
The generated TextureData docs describe a SchemaField but did not make these
individual transform semantics clear in the inspected sections.

## Coordinate and sizing measurements

Selected the existing 25-note Shrine map using public `Scene.view()` and fitted
its view with public `canvas.pan()` in the dedicated browser. No scene, note,
journal, grid, or asset document was changed.

- Native background image: **6,800 × 9,000**, verified with a browser Image decode.
- Scene rectangle: origin **(1800, 2400)**, extent **6,800 × 9,000** from
  `scene.getDimensions()`.
- Example note at canvas **(1900, 2500)** maps to original-image **(100, 100)**
  for this untransformed background. A second note at (6400, 6000) maps to
  (4600, 3600). Ignoring padding would place both incorrectly.
- Observed transform: centered anchor 0.5/0.5, fill, scale 1/1, rotation 0,
  offset 0/0. Only this normal mapping was measured; do not claim arbitrary
  rotations, offsets, or tile-local mapping were verified.
- Notes: **25**, configured font sizes **100 or 128** map pixels. Label lengths
  span **1–29 characters**, not all short room keys. Sampled note `levels` sets
  were empty; that alone does not establish their cross-level meaning.
- Existing preview scale formula gives factor **0.1963430371** and integral
  dimensions about **1,335 × 1,767**, within 2,048 per edge and 2,359,296 area.
  Copying those source font sizes through that scale would yield about
  **19.6 or 25.1 pixels** in the delivered overview, assuming ordinary scaling.
- Browser viewport: **1,137 × 1,038**. The fitted map used scale **0.0953333**;
  the analogous scaled note-font sizes would be **9.5–12.2 screen pixels**.
  These are arithmetic size projections, not measured native tooltip bounds.
- Using standard browser canvas `measureText` with **16 px sans-serif**, `A1`
  measured **19.5703125 px** wide, while a representative 16-character
  alphanumeric journal ID measured **141.421875 px** wide, over **7× wider**.
  At a 1,335-pixel map width that ID alone spans about 10.6% of the image.
  A bundled worker font will need its own real glyph measurements.

For a verified normal map rectangle, the proposed mapping is:

```text
source_x = (note_x - sceneX) * original_width / sceneWidth
source_y = (note_y - sceneY) * original_height / sceneHeight
preview_x = (source_x - region.x) * output_width / region.width
preview_y = (source_y - region.y) * output_height / region.height
```

Apply the appropriate verified inverse transform before source/crop conversion
for transformed textures. Use original display-oriented dimensions consistently
with the image-preview EXIF/crop contract. Decline unsupported mappings rather
than place labels using guessed coordinates.

## Screenshot observations and temporary artifacts

Captured and inspected the same existing map at a detailed view and overview.
The overview makes small room features and note pins difficult to read. A full
journal ID rendered at every pin would occupy substantially more map area than
short keys. This is a qualitative observation; no annotated derivative or
collision-layout prototype has been generated or visually accepted yet.

The screenshot also includes native lighting/darkness, tokens, controls, and a
Game Paused overlay. It is a reference for inspection, not a clean original
image export or proof that a canvas capture meets the image-preview contract.
Do not confuse labels already present in the map artwork or pin icons with
newly rendered note text.

Session-local artifacts, **not committed and not guaranteed on another host**:

- `/tmp/foundry-map-note-research.jpg`: final fitted-map screenshot. The earlier
  detailed screenshot was inspected but this path was later overwritten.
- `/tmp/foundry-map-note-research.py`: small scoped CDP helper; fixed actions
  reload/inspect/view-map/fit-map/catalog/screenshot, restricted to the dedicated
  `http://localhost:30000/` tab and test-world GM for scene inspection. It reads
  documents and changes only the client view. No credentials are printed.
- An initial PNG capture exceeded the helper WebSocket client's 1-MiB message
  limit (reported frame about 1.34 MiB). A bounded JPEG capture at quality 85
  succeeded. This was a research-helper payload limit, not a Foundry or project
  transfer-protocol failure; no project transport limit was changed.

## Historical candidate capability shape

These candidates informed the now-augmented plan. The source design's map
extension supersedes tentative names/shapes below. None has been implemented
in actual MCP discovery yet.

- Add a core Foundry map-folder browser, independent of PF2e Actor filtering.
  Existing `list_scene_actors` is a flat, PF2e-specific Scene/Token discovery
  interface; it does not satisfy this requirement. Reuse safe low-level identity,
  pagination, and document relationship patterns without expanding Actor scope.
- A bounded folder-navigation tool (candidate `browse_maps`) should expose
  immediate child folders/maps with UUIDs, names, named ancestry, sort context,
  and concrete follow-up calls. Reconstruct the hierarchy from Scene folders and
  document membership, preserving duplicate names. Do not crawl file directories
  to discover maps or require the Scene to be active.
- A selected-map reader (candidate `get_map_info`) should expose scene dimensions,
  padding/shift, grid configuration, initial level and explicit level identities,
  and separate background/foreground file references. Return exact safe stored
  paths and image follow-ups. Identify maps without usable backgrounds, videos,
  missing files, and additional Tile artwork explicitly. A background preview
  must not be represented as a composite of the entire Scene. Decide how much
  additional Tile inventory belongs in an optional bounded detail section.
- Bind map image selection to scene UUID + level ID + asset role rather than
  guessing the Scene from a bare image path. Multiple Scenes can use the same
  file even though the bounded live sample did not find a reused path. Keep
  credential-bearing or signed asset information private.
- A possible typed `map` selector can become an additional exclusive input form
  for image info/URL requests; `get_map_info` would return concrete next calls.
  URL-only `map_notes` would default false. Setting true would require explicit
  map context or a source handle carrying that context. Existing image/src
  workflows remain available. Exact extension shape still needs to be frozen.
- Keep note text extraction bounded and distinct from full journal-body reading.
  Use public NoteDocument label/entry/page plus permission-checked identity.
  Select applicable scene/level notes and carry a revision/snapshot identity so
  repeated crops and note-key lookup cannot silently join different versions.
- Render compact stable keys (for example N1/N2) over source positions and return
  key → full Note UUID, JournalEntry UUID, optional page UUID, and label metadata
  through a bounded legend/read path. Full raw IDs in pixels are unnecessarily
  wide. Preserve distinct pins that link the same journal/page.
- Start font experiments around **16 pixels at final delivered resolution**,
  with a fixed bundled font and small contrasting outline instead of large
  opaque boxes. Compose after source crop/resizing and repeat that composition
  if byte-budget retries change delivered dimensions. Never let encoding
  fallback silently shrink labels into illegibility.
- Choose and test collision/edge/density policy before finalizing tasks: compact
  keys, small placement offsets/leader marks, bounding-box checks, and explicit
  completeness/omission reporting or a typed tighter-crop recovery are possible.
  Do not claim that a fixed font size alone prevents obscuring map features.
  Handle one-pixel crops and dense clusters explicitly.
- Keep original-byte snapshots separate from annotation state and public
  derivatives. Recheck authority/current membership before issuance. A note,
  level, grid, layout, or asset-reference change must not silently reuse a stale
  mapping. Previously issued seven-day links remain immutable; annotation text
  becomes part of the pixels governed by that same capability lifetime.
- Preserve 128-MiB source, 32,768-edge/128-million-pixel source limits; 2,048-edge,
  2,359,296-pixel, 2-MiB output limits; and independent 1-GiB RSS, 2-GiB scratch,
  one-render, 90-second worker budgets. Bound legend/discovery responses too.

## Implementation verification gaps

1. Implement and validate the now-specified typed map discovery/detail/annotation
   interfaces and limits: 10 entries, 8,000 JSON bytes by default, explicit
   maximum 48,000 bytes, and the declared continuation/revision semantics.
2. Verify public texture-transform semantics against documentation and installed
   14.369 behavior. Normal padding mapping is measured; rotated/scaled/offset
   backgrounds and tile-only maps are not verified. Keep unsupported cases
   explicit rather than using internal mesh transforms.
3. Verify per-level note membership, including empty/null sets and duplicate pins,
   permission denial, missing/unlinked journals/pages, and level changes. Reading
   a note must not hydrate journal bodies or infer player-visible information
   from GM access. The feature remains an authenticated GM capability.
4. Prototype worker text at delivered size and visually compare overview/detail
   crops, short/full labels, dense clusters, dark/light map areas, and edge notes.
   Bundle/measure a deterministic font; libvips text supports Pango markup, so use
   generated safe keys and escape any untrusted text. No prototype exists yet.
5. Extend typed MCP discovery and actual invocation tests, cursor/revision tests,
   cross-context snapshot tests, pixel/geometry oracles, byte budgets, shipped
   font checks, and real local browse-map → select-level → annotated-crop checks.
   Do not weaken the existing independent target-ChatGPT pixel acceptance test
   by including its hidden answer in a note label or legend.
6. Execute the new sized tasks and downstream package/visual gates using their
   independent tests and commits. Keep any later scope changes below 13 points
   by splitting responsibilities and re-estimating. Maintain the dependency
   graph, point totals and context-recovery snapshot as implementation progresses.

Only research and the earlier planning commit have been performed. There have
been no new production feature changes, no new Foundry instance/world, no
publication/release, and no edits to existing game documents. The existing root
Compose instance was started with its persisted data, normal saved-credential
login was used, and the dedicated browser was left viewing the inspected map.
