# Complete map preview and legend verification

M06 verifies the complete folder → map → explicit level → annotated image →
revision-bound journal/page legend workflow. Individual behavior remains owned
by its component tests; this checkpoint joins actual published MCP calls,
production browser RPC handlers, native workers and HTTP pixels.

## Offline coverage and large map

`test_map_workflows.py` passes10 tests (13.749s), `test_map_image_tools.py`
retains17 passing cases after extracting a reusable non-TestCase fixture mixin,
and `tests/js/map-workflows.test.js` passes the complete non-PF2e/inactive Scene
RPC path. The pre-existing JS map33 cases remain passing. No world data is
mocked inside production functions; only external public Foundry documents,
FilePicker and transport are controlled fixtures.

The measured full fixture workflow uses11 MCP calls,1 original transfer,3 level
pages,2 exact-key legend pages and one Tile page. It independently distinguishes
the5940x7920 Scene/screenshot180px grid from the500-square decoded original,
then verifies the native crop's pin pixel, aliases and full journal/page identity.
Duplicate folder/map names sharing a source retain different owning Scene
selectors. Changed notes invalidate continued legends and annotated handles;
ordinary pinned pixels remain readable. A1x1 crop reports tiny-image omission
and null legend, then a tighter usable detail renders the same N1 alias without
another transfer. Grid fields match the screenshots' complete eight-field data.

| Requirement | Retained focused evidence |
| --- | --- |
| Manual/alphabetical hierarchy, duplicate names, missing/denied folders, non-PF2e/inactive maps | M01 browser/Python tests and complete JS/MCP workflow |
| Multiple levels, absent/video/foreground/Tile roles, all grid values, byte bounds | M02 tests plus3-level/Tile MCP workflow |
| Empty/null/explicit level membership, permissions, distinct shared-journal pins, stale/filtered/paged aliases | M03a public applicability and legend tests; M05/M06 exact-key streams |
| Padding/shift/source size/orientation and unsupported transforms | M03b independent geometry/all8 orientations; M06 scaled native pin and unsupported/raw fallback |
| Dark/light/edge/dense/tiny labels and per-retry final glyph sizes | M04a/M04b native pixels/metrics/reduction tests; M05 dense omissions; M06 1px/detail and native visual review |
| Signed references, identity isolation, one transfer, replacement snapshots, quota/cancel and immutable URLs | M05 actual MCP/cache/SQLite/anonymous HTTP workflows |

The separate bounded command
`.venv/bin/python scripts/map-preview-measurements.py` passed a real10000-square
annotated map using12b's streaming generator and independent region oracle.
The1536-square PNG overview is1487372B with2 rendered keys; sampled peakRSS
394256384B, scratch301494272B and0.505164s. The150-square native bottom-right
detail is1546B withN2; an unpainted24-square corner matches independent source
pixels exactly and the independently projected pin is white at(70,70).
Two render operations total0.773787s. Original/workspace cleanup passed; worker
limits remain1GiB/2GiB/90s and public output budgets remain unchanged.

The actual ZIP-manifest test also exposed a PF2e-only system relationship in the
old module package, contradicting the core tools' boundary. The unchanged test
passes after removing that restriction; PF2e Actor/Item guards remain intact.
Official [package relationships](https://foundryvtt.com/api/v14/interfaces/foundry.packages.types.PackageRelationshipsData.html)
and [module manifests](https://foundryvtt.com/article/module-development/)
were checked through Grounded Docs. Non-PF2e RPC mocks pass; an additional live
non-PF2e world was not created. Final full/package checks cover this correction.

## Existing runtime and complete payload streams

After offline1040 Python (1 existing skip)/795JS passed, the shared command
`.venv/bin/python scripts/image-preview-live-check.py --map` passed35 MCP calls
under60/900s. Two later tiny-crop/glyph-metric tests pass focused; the task commit
hook verifies the final revision. Native wall time was not separately measured.

It followed returned catalog/folder/map calls through all18 folders/50 Scenes,
preserving16 duplicate names, and read every level plus the3 selected-level
Tiles on the representative map. Independent public Scene/Note reads check the
grid, active Scene, alias order, coordinates and journal/page identities without
reading bodies. Original info is6800x9000; one bound handle issues both derivatives.

| Complete native stream | Calls | Compact JSON bytes | MCP-result bytes | Completion |
| --- | ---: | ---: | ---: | --- |
| Entire map/folder catalog |21|46260|101532|complete scope/all pages|
| All selected-map levels |1|2805|6118|complete|
| Selected-level Tile inventory |1|4126|8846|complete|
| Map image info |1|198|606|complete|
| Annotated overview result |1|1260|2912|25/25 pins|
| Exact overview key legend |3|15773|33848|all25 identities|
| Annotated detail result |1|998|2296|2/2 pins|
| Exact detail key legend |1|2130|4684|both identities|

Other calls are discovery, independent metadata/legend comparisons and the
unchanged-active-Scene guard. Every individual page stays within its8000-byte
default. Legend pagination completion and annotation completeness are separate.
The entire catalog's measured46260/101532 bytes exactly match M01's root plus
remaining complete navigation streams; no response savings are claimed.

The catalog is47 tools/323516 compact SDK-model bytes. Before M01 it was45/
275617: +47899B for map tools and subsequent image/map schema extensions.
Current records: browse11069B,map-info28172B,image-info6219B,image-URL15834B.
These are structured/schema bytes, never billed provider tokens. Minimal
pre-tool metadata samples lacked ancestry/cursors/recovery and are not equivalent
content for a savings comparison.

## Native pixels, review and cleanup

The overview is1335x1767 WebP633428B; all25 in-region pins rendered with complete
scope and no omissions. The800x600 PNG detail is508560B with2/2 pins. Anonymous
exact/query GET and HEAD pass for both through the existing real service and
14a's temporary loopback TLS proxy. The detail's independently predicted pin
pixel matches exactly. Public-host/client acceptance is still separate.

The agent inspected both private derivatives: compact keys and leaders remain
readable on dark/light terrain and grid, including the overview's edge placement.
The detail retains the same key scale. Labels/leader marks can obscure nearby
features; there is no claim of zero obstruction or target-client readability.
`.venv/bin/python scripts/map-preview-review-check.py` measured the fixed glyph
boxes for these exact reviewed alias sets: ink height14px, overview widths22/23/
32/33px and10094 label-box pixels (0.427903%); detail770 pixels (0.160417%).
Both are below5%, with no glyph shrinking. This fixed review command describes
the recorded25-key overview and N1/N10 detail, not an arbitrary future map.

The tested `--cleanup-map-review` mode removed exactly the2 owned review files
and marker directory. Native mode created no game assets/documents; existing
active Scene stayed unchanged. Private service settings were restored, temporary
TLS/certificate/derivative-store files removed, and dedicated browser refresh
confirmed readyGM14.369/test with0 console errors. Core source/worker behavior
is unchanged from13's UID10001 packaged codec/font/persistence check.

Final full verification after the manifest correction passes1043 Python tests
(1 existing skip)/795JS,148.561s for Python, including all10 workflow cases and
the5 archive tests. The module ZIP packages successfully at unchanged3.3.1.

## External handoff

14b owns separate hidden-pixel and folder/key-following prompts. Actual target
ChatGPT, an externally reachable trusted preview HTTPS origin and refreshed tool
discovery are still required. Local curl or agent image inspection does not
satisfy that client gate. Live S3 needs a configured readable bucket/CORS;
prefixed-deployment and real Auth0 login/refresh retain their existing explicit
operator prerequisites. None is reported passed by offline mocks.
