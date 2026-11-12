# World map folder navigation

M01 implementation contract, fixed before production edits. Status/evidence are
in [taskM01](tasks/m01-map-folder-browsing.md). M02 owns selected-map grid/assets;
M03 owns notes. This page does not claim those later tools are implemented yet.

`browse_maps` is authenticated, ready-GM, core Foundry14 read-only navigation.
It does not require PF2e or activate/render a Scene. Scope is loaded world
Scenes and Scene-type Folders, including imported adventure Scenes; unimported
compendium indexes and sidebar/prepared-tree/DOM reconstruction are excluded.

Inputs are flat typed fields: `folder_uuid` (null/default root; exact `Folder.id`
UUID from this tool), literal case-insensitive `name_contains` (default empty,
maximum256 characters), `limit` (default10,1–100), `max_bytes` (default8000,
1024–48000 compact UTF8 bytes), opaque `cursor` (default null). Bounds may change
between pages; folder/filter and caller/world context must remain identical.

Output fields: `location`, `revision`, `entries`, `total`, `complete`,
`next_cursor`, `scope_status` and `limitations`. Location identifies selected
folder UUID/name/name_truncated, named ancestor identities and sorting mode.
Root is named World Scenes, with null folder UUID and alphabetical ordering.
Location also reports `locale`, the standard browser collation locale; it
participates in revisions so a changed collation cannot silently reorder pages.
Folders precede maps; each selected folder uses its declared `sorting` a/m,
then canonical UUID ties. Manual mode sorts by source sort, alphabetical mode
by full original names; display-name clipping never changes matching/order.
Root ordering is explicit rather than inferred from undocumented UI settings.

Folder entries contain kind=folder, `folder_uuid`, `parent_uuid`, `name`,
`name_truncated`, `ancestry`, `sort`, `sorting`, and `next_call` to browse_maps.
Map entries contain kind=map, `scene_uuid`, the same parent/name/ancestry/sort
context, `image_status:not_checked`, and `next_call` to get_map_info. Browsing
includes every readable Scene, including those without usable image media;
availability must be checked in that tool's asset inventory. A map file preview
does not compose fog, lighting, tokens, walls or Tiles.

Each ancestor identity contains folder_uuid/name/name_truncated. Ancestry excludes
the object itself and runs from root to parent. Names over256 codepoints are
clipped with name_truncated=true; UUIDs and ancestry are never silently clipped.
Unknown source sort is reported null; ordering treats it as zero with UUID ties.
An unknown folder sorting mode is unsupported rather than a guessed UI mode.

`total` counts authorized immediate children after the local literal filter.
`complete` covers this selected stream only. `scope_status:partial` and explicit
limitations expose denied content without leaking names/paths; even a complete
empty stream cannot establish exhaustive availability under partial scope.
Public collection `invalidDocumentIds` also makes scope partial when source
records could not initialize; their identifiers never appear in the response.
Selected missing/denied/non-Scene folders and malformed/orphan/cyclic hierarchy
produce explicit recovery errors; no document names appear in those diagnostics.

Opaque cursors bind trusted authenticated caller, world/GM, folder/filter and
observed hierarchy/metadata/permission revision; bounds are excluded. Metadata
revision is not a file-byte revision. A changed revision returns ContentChanged,
requiring discarding prior pages and restarting. Bad/foreign cursor inputs fail
before returning content. If location/one complete identity cannot fit, return
ResponseTooLarge with larger-bound/shallower-scope recovery rather than truncate.

## Public API and baseline evidence

Grounded Docs foundry-vtt14 is completed, indexed2026-10-12T22:52:58Z from the
official version14 source,1978 URLs/17801 chunks. Fresh official pages confirm:

- [FolderData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html)
  and [SceneData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneData.html):
  declared name/folder/sort, plus Folder type/sorting.
- [ForeignDocumentField](https://foundryvtt.com/api/v14/classes/foundry.data.fields.ForeignDocumentField.html):
  schema foreign references by ID; initialized properties are used as documented
  document relationships, never private source storage.
- [Folder](https://foundryvtt.com/api/v14/classes/foundry.documents.Folder.html)
  and [Scene](https://foundryvtt.com/api/v14/classes/foundry.documents.Scene.html):
  public id/uuid, testUserPermission and toObject(source=true), without private/
  protected/internal annotations on adopted APIs. Production extracts declared
  metadata from authorized source serialization, then discards other fields.
  This preserves stored parent IDs even if a foreign reference is unresolved,
  allowing explicit orphan detection. It scans loaded world documents before
  pagination; it does not hydrate files or linked journal/Actor bodies.
- [Folders](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.Folders.html)
  and [Scenes](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.Scenes.html):
  game.folders/game.scenes, contents arrays and exact get(id).
  Their public invalidDocumentIds sets identify uninitialized data omissions;
  they affect availability/revision, not returned identities.

Pre-production baseline `.venv/bin/python -m foundry_mcp_server.map_browse_audit`
passed2 actual MCP calls within120s on existing14.369/test GM. Catalog45 tools/
275617 compact SDK-model bytes;50 readable Scenes/18 Scene folders. A minimal
public-metadata root sample has3 entries/367B, first-folder sample2/285B, both
complete. The helper does not constitute a pre-existing browse_maps interface:
its minimal records lack the new ancestry/cursor/recovery contract, so these
are context/cost observations, not equal-content savings comparisons.
Public relationship values match source serialization in six bounded samples,
and active Scene remains unchanged. No names/UUIDs/raw data are printed. Two
focused baseline tests verify counts/completion and private diagnostic handling.

## Implemented workflow verification

After passing offline checks, restarted the existing Python service and refreshed
only the dedicated development tab. Foundry14.369/test is ready as GM with zero
console errors. The read-only command
`.venv/bin/python -m foundry_mcp_server.map_browse_audit --browse` passed26 calls
within its30-call/120-second budget. It followed returned folder next calls and
pagination through all18 folders/50 Scenes, preserved4 duplicate folder names
and12 duplicate map names, reported complete scope, and left the active Scene
unchanged. No game document, asset or fixture was created or changed.

| Selected stream | Calls | Compact result bytes | MCP envelope bytes | Complete |
| --- | ---: | ---: | ---: | --- |
| Root default |1|1279|2896|yes|
| Root expanded100/48000 |1|1279|2896|yes|
| Literal root filter |1|759|1784|yes|
| Remaining complete folder navigation |20|44981|98636|yes|

Other calls are discovery and2 active-Scene guards. Complete navigation includes
the root default plus the remaining20 calls; the expanded/filter probes are
separate comparisons. Catalog46 tools/286687 compact SDK-model bytes versus
45/275617 baseline: +11070 bytes for the new discoverable tool. These counts
are bytes, not measured billed tokens. Full navigation and minimal baseline
records differ in content; no equal-content savings claim is made.

Focused JS11/Python12 pass, including actual MCP discovery/invocation, real
production browser dispatch under public-document mocks and Basic/OAuth
boundaries. Full runner passes912 Python (1 existing skip)/761 JS. Packaging4
and actual local module ZIP creation pass, including mapBrowse.js. Tests cover
shrinking revisions, invalid-document partial scope and the archive dependency
omission with demonstrated failing tests before corrections. All synthetic
fixtures/processes are test-owned and cleaned; live browsing is read-only.
