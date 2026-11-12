# Selected map configuration

M02 contract fixed before reader implementation. M01 browsing supplies exact
world Scene UUIDs; `get_map_info` reads their configuration. M03 owns notes and
their shared revision; M05 owns map-aware image-tool inputs. Task completion
and measured verification are recorded separately from those later features.

`get_map_info` is authenticated, ready-GM, read-only core14, independent of PF2e
and active canvas. Flat inputs: required `scene_uuid`, optional `level_id`,
`section:assets|tiles|notes` (default assets), `expected_revision`, `cursor`, `limit`
(10,1–100) and `max_bytes` (8000,1024–48000). Reject unknown fields and conflicting
note-only arguments before reads. Scene names/paths/compendium UUIDs are not selectors.
The [note legend extension](map-note-identities.md) requires exact level identity
for notes and adds revision-bound `note_keys`. No implicit current/active/initial
level selection: omitted level means all
authorized levels, exact level ID means that embedded owner only.

Common output: `scene` (scene_uuid,name,name_truncated,parent_uuid,ancestry),
`geometry` (stored width,height,padding,shiftX,shiftY plus `scene_rect` with
sceneX,sceneY,sceneWidth,sceneHeight from public getDimensions), `grid` (stored
type,size,distance,units,style,thickness,color,alpha), `initial_level_id`,
`level_id` (selected filter or null), `section`, `revision`, `entries`, `total`,
`complete`, `next_cursor`, `scope_status`, `limitations`, `artwork` (authorized
level/Tile counts and background/foreground reference counts). Optional missing
source primitives stay omitted; explicit null/zero stay null/zero. Scene sizes
are configuration, not probed original image pixels.

Assets entries are complete level records with kind=level, level_id, level_uuid,
name/name_truncated, stored sort, elevation bottom/top when declared, and two
distinct `background`/`foreground` media records. Each media record has role,
`reference` (safe exact src or null), `reference_status` (missing, empty, null,
safe, sensitive, unsupported), `media_kind` (image,video,unknown,none),
`support_status` (reference_only,missing,unsupported_video,unsupported_reference,
map_context_required), a typed `map` selector (scene_uuid,level_id,role), and
nullable info/preview next calls. Level images use exact nested
`request:{map:{scene_uuid,level_id,role}}` follow-ups, including privately resolved
sensitive references. Sensitive references expose no source text or raw-file
follow-up; credential-bearing/unsupported sources still fail resolver checks.
See [map-aware image tools](map-image-tools.md). Tile file followups use `src`.
Listing
never fetches media, lists FilePicker directories or claims a path exists.
Image/video classification is a filename hint; only the image probe establishes
actual type. Unknown extensions remain explicit unsupported references.

Tiles entries have kind=tile, tile_uuid, optional name/name_truncated, stored
sort, `placement` (x,y,width,height,rotation,elevation and declared texture
transforms), media without a guessed level-role map selector, and
`level_membership` (declared_ids or null, status explicit/not_evaluated).
Explicit nonempty ID membership is checked against owning Scene levels before
filtering. Null/empty/absent membership does not establish applicability: include
these rows under a selected-level Tile inventory with partial-scope limitation
until M03's public-contract/runtime membership evidence resolves semantics.
Never hide unknown membership and imply an exhaustive selected-level inventory.
No composition, tokens, fog, lights, walls or journal bodies are read/exported.
The Tile's documented `placement.rotation` remains separate from texture data.
Texture anchors, scale and fit are returned as declared stored configuration;
undeclared texture rotation/offsets are excluded. Their presence is not a claim
that composed transform semantics have been verified.

Levels/tiles order by declared sort then canonical UUID; null sort orders as0.
Pagination counts complete level/Tile records and includes all metadata/cursor
in its byte bound. Names clip256 codepoints with marker; identity, media paths,
levels and ancestry never clip. Fail ResponseTooLarge if minimum complete
identity cannot fit. Empty levels and tile-only maps remain represented.

Revision describes the selected Scene's authorized metadata/permissions,
geometry, ancestry, levels, declared artwork and note witnesses. M03a binds the
selected level as well, sharing its revision across sections/key filters while
all-level assets have a separate revision. Pagination bounds are excluded.
It does not detect changed bytes at an
unchanged src. Cursors additionally bind section/filter and verified caller/
world/GM. Changed metadata or expected_revision mismatch returns ContentChanged
before offset checks; discard prior pages and restart. Recheck socket/context
and detached metadata across async hashes. Unavailable/invalid embedded data
makes scope partial without leaking denied names/paths/IDs. Missing Scene,
wrong-level owner, malformed hierarchy, unsupported public APIs and non-GM
scope have fixed actionable errors, never browser diagnostics.

## Public API and baseline

Grounded Docs foundry-vtt14 search/fresh official pages were read for
[Scene](https://foundryvtt.com/api/v14/classes/foundry.documents.Scene.html)
(public getDimensions/getEmbeddedCollection/testUserPermission/toObject),
[SceneData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneData.html),
[GridData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.GridData.html),
[SceneDimensions](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneDimensions.html),
[LevelData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.LevelData.html),
[LevelTexture](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.LevelTexture.html),
[TileData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.TileData.html),
and BaseScene/BaseLevel/BaseTile public schema definitions. BaseTile explicitly
declares levels although TileData omits it. The public
[SceneLevelsSetField](https://foundryvtt.com/api/v14/classes/foundry.data.fields.SceneLevelsSetField.html)
describes nullable specific-level references; it does not settle empty/null
applicability. No internal Scene texture configuration method is adopted.

Two unit-tested read-only calls via
`.venv/bin/python -m foundry_mcp_server.map_info_audit` passed in14.369/test:
50 Scenes/50 levels/78 Tiles,48 background and14 foreground references,2 empty
levels. Source and embedded level counts agree; public embedded UUIDs/parents
and finite scene rectangles agree. All8 grid fields, all8 declared texture
transform keys and Tile levels are present in aggregate. Catalog46 tools/
286687 compact SDK-model bytes; active Scene unchanged. No raw file paths,
names, IDs, credentials or game documents were output or changed. This is
metadata corroboration, not proof of arbitrary transform rendering support.

The public `TileDocument.schema.getField('texture').keys()` check additionally
confirms anchorX,anchorY,fit,scaleX,scaleY,src in14.369; texture rotation/offsets
are not declared for Tiles. It uses documented public SchemaField getField/keys
and BaseTile schema, not internal preparation or runtime mesh properties. Level
texture mapping remains a separate M03 verification requirement.

## Implemented verification

Focused Python17 and JS16 pass; with M01 regressions the focused JS run has27
passing tests. Actual MCP discovery/invocation validates strict flat requests,
typed responses, caller/socket isolation, metadata/cursor revisions, concrete
image follow-ups, forged owner/role rejection and OAuth discovery metadata.
The pre-commit full runner passed928 Python (1 existing skip)/777 JS; the hook
verifies the final staged declarations and extra diagnostic test. The local
module ZIP packages mapInfo.js and its shared primitives without a version bump.

After existing-service restart and dedicated-tab refresh/readiness, the bounded
`.venv/bin/python -m foundry_mcp_server.map_info_audit --read` passed7 calls
(discovery, selection,4 reads and active-Scene guard) under30/120s. The two
distinct samples cover foreground artwork, absent backgrounds and Tile files.
Every section stream is complete with agreeing revisions and unchanged active
Scene; scope is complete for these selected inventories. No game documents,
assets, uploads or temporary live fixtures were created or changed.

| Representative stream | Entries | Calls | Compact result bytes | MCP envelope bytes |
| --- | ---: | ---: | ---: | ---: |
| Sample1 assets |1|1|2852|6172|
| Sample1 Tiles |2|1|3043|6584|
| Sample2 assets |1|1|1785|3976|
| Sample2 Tiles |1|1|1883|4162|

Final catalog47 tools/309786 compact SDK-model bytes versus46/286687 baseline
(+23099B); live tool record23098B, separate from focused by-alias record23091B.
Byte conventions are distinct and do not measure billed tokens. No equal-content
savings claim is made for the newly added configuration interface.

The live handler exposed a source-versus-JSON distinction absent from initial
mocks: optional Tile name may be an own undefined property. The matching native
TypeError stack was reproduced in a focused test before omission was corrected;
the unchanged test passes. Sensitive-reference hashing, encoded traversal and
independent response privacy also have failing-then-passing focused evidence.
Tile rotation remains its documented value rather than being overwritten by
unsupported texture fields. M03 must still establish note membership and verified
annotation geometry; neither inventory nor schema introspection proves rendering.
