# Private map context and source geometry

M03b established this private context contract. The
[map image tools](map-image-tools.md) attach this state atomically to caller-bound
originals and use it for explicit map selectors and annotated previews.

## Supported subset and evidence

Use official public Scene.getDimensions/SceneDimensions and LevelData.textures
source serialization. Read the [note identity evidence](map-note-identities.md)
for public includedInLevel and exact selected-level revisions. The default
background mapping is the public Scene rectangle: subtract sceneX/Y, then scale
sceneWidth/Height to actual **display-oriented** original dimensions supplied
by the decoder. Crop/output transforms follow the existing image contract.
The returned rectangle already includes Scene shift; never apply shift again.

Individual Level texture transform semantics are insufficiently documented to
support arbitrary placement. Instead compare the entire declared textures value
against the public schema's cleaned initial value using
`Level.schema.getField('textures').clean(undefined,{source:level.toObject(true)})`.
This uses documented LevelData.textures, SchemaField/getField and DataField.clean
without depending on guessed individual transform properties. Nondefault or
unavailable placement is explicitly unsupported for annotation. V1 mapping is
verified on14.369, background role only; foregrounds remain ordinary fetchable
files, and Tile/composed Scene rendering is outside scope. Unknown builds and
unverified placements do not inherit a verified mapping by feature detection.

Grounded Docs official v14 pages were reread for
[Scene](https://foundryvtt.com/api/v14/classes/foundry.documents.Scene.html),
[SceneDimensions](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneDimensions.html),
[LevelData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.LevelData.html),
[Level](https://foundryvtt.com/api/v14/classes/foundry.documents.Level.html),
[SchemaField](https://foundryvtt.com/api/v14/classes/foundry.data.fields.SchemaField.html)
and [DataField.clean/getInitialValue](https://foundryvtt.com/api/v14/classes/foundry.data.fields.DataField.html).
Public members adopted here have no private/protected/internal annotation.
Installed14.369.0 public getDimensions corroborates shift is already subtracted
from grid-rounded origin; installed source explains behavior, not public status.

Two unit-tested read-only baseline calls passed in14.369/test. All50 authorized
Level texture values match their public schema defaults, so this subset covers
the existing normal maps. Public constructors created no persisted Scene:

| Case | Scene width/height | Scene origin | Shift |
| --- | --- | --- | --- |
| Normal |6800×9000|(1800,2400)|(0,0)|
| Shifted |6800×9000|(1680,2480)|(120,-80)|
| Smaller Scene |3400×4500|(1000,1200)|(0,0)|

Catalog47 tools/314317 compact SDK-model bytes. Active Scene and collection size
unchanged,zero persisted fixtures. The measured normal pin(1900,2500) therefore
maps to(100,100) for a6800×9000 original; a3400×4500 original maps the same pin
to(50,50). Geometry tests must use independent expected values/oracles and
exercise source-versus-Scene sizing, shifts and display orientation.

## Private interfaces and immutable state

Add private browser RPCs for exact explicit map image context and in-crop Note
candidates, not discoverable MCP tools. The context reader reuses the selected
Scene/level snapshot/revision and the existing byte-free configured-source
resolver. It rechecks owner/world/GM/document snapshot across every await.
It returns canonical image selector, exact source-reference digest, map identity,
selected-level revision, alias-snapshot digest/count, public rectangle, mapping
support/reason, core version and scope limitations. No source bytes are fetched.
Sensitive selectors remain private and cannot enter public tool results/logs.

The immutable Python record pins those proofs with verified Principal, exact GM
socket/world/user, original source_id/expiry/digest and actual oriented dimensions.
All collections in the record are tuples/frozen values; repr must reveal no
selectors, private identities or paths. Alias snapshot digest/count plus revision
pin the complete deterministic assignment; later candidate reads require that
exact unchanged snapshot, rather than retaining a second unbounded legend.
M05 owns attaching the record to the source-cache lifetime.

Revalidation checks current trusted principal, source lease/expiry/digest,
socket/world/GM, selected Scene/level/role, exact reference digest and canonical
source membership. Annotated issuance additionally requires unchanged metadata/
notes/alias/mapping proof and supported placement. A changed annotation context
returns MapContextChanged with fresh map-info/image-info recovery. Source expiry
and lost source authority retain existing source recovery errors. Unchanged paths
with replaced contents still use the handle's pinned original bytes. Ordinary
unannotated previews may continue when only Note metadata changes, provided
exact selected asset/permission/source context remains valid.

For a requested source crop, the browser candidate reader filters the complete
authorized level snapshot by pin center with inclusive left/top and exclusive
right/bottom edges, retaining original aliases. It pages at most100 candidates/
48000 compact bytes, with total_in_region, scope and continuation. Cursors bind
caller/map/revision/source-snapshot scope/oriented dimensions/crop, excluding
page bounds. Numeric alias order determines candidate/render priority. Python
independently validates mapped coordinates, crop membership and context; only
generated keys and bounded pixel positions reach the renderer. At most100 pins
are requested for one output; explicit over-limit counts remain available for
honest omission reporting. Never silently claim the first page is all notes.

Both private response types must fit the configured bridge ceiling including
the actual UUID response envelope, using the same byte-budget policy as the
public legend. Minimum identities fail explicitly when they cannot fit. No
unbounded Scene-note response, journal-body hydration, map activation, raw source
URL logging or game mutation is introduced.

## Implemented components and verification

`mapGeometry.js`/`map_geometry.py` own pure coordinate conversion and exclusive
crop selection. `mapContext.js` owns private document/source context and bounded
candidate dispatch. `map_context_models.py` validates private DTOs;
`map_context.py` owns frozen source binding, authority/revision revalidation and
bounded candidate collection. SourceSnapshots continues to own file/quota/expiry
lifecycle; the coordinator does not replace it or the render supervisor.

| Mapping case | Evidence/status |
| --- | --- |
| Default14.369 background | Public schema/default comparison; all50 existing levels, native real-map probe/candidates pass |
| Grid-rounded padding and Scene shift | Public getDimensions, independent measured origins and conversion tests pass |
| Different Scene/source sizes | Independent half-size and non-square-axis conversion/output tests pass |
| Eight display orientations | Real worker header/crop versus independent Pillow transpose pixels passes all8 |
| Exclusive border/one-pixel crops | Native detail alias and independent coordinate/region tests pass |
| Nondefault texture placement/unknown build | Explicit UnsupportedMapMapping; no guessed transform |
| Foreground annotation/Tile composition | Unsupported; ordinary selected file reading remains separate |

Focused context21 passes11.904s; JS geometry/context11 plus notes6 passes17.
Final direct full runner passes961 Python (1 existing skip)/794 JS before two
additional context mutation tests; the commit hook verifies those final tests.
The actual2000-byte private-frame tests use production browser dispatch and
include the36-character response-ID envelope.100-pin selection from150 reports
50 over-limit pins; a detail crop returns N101 onward without renumbering. Source
replacement bytes stay pinned at an unchanged path. Moved/removed/denied notes,
changed aliases/assets/Scene, expiry, caller changes and socket changes fail
before misplaced annotation is possible.

Demonstrated corrections retain unchanged failing tests: a bound changed asset
must compare expected_reference_digest before resolving a possibly missing new
file; empty crop objects must not select full-image defaults; malformed private
cursors must produce fixed contract errors. No limits were enlarged or errors
swallowed. Frozen records contain only immutable values/tuples and private reprs;
the renderer-facing pins carry keys and source positions, with no journal prose.

After offline checks and dedicated-tab refresh/readiness, the native verifier
`.venv/bin/python -m foundry_mcp_server.map_geometry_audit --context` passed6
MCP calls under600s. It used authenticated development RPC with actual module
dispatch, the public selected-assets reader, and actual image-info staging/
decoder. The existing map probes as6800×9000/4405816B; all25 region candidates
and a one-pixel detail retain the correct alias and independently checked
coordinates. Private handler-result sizes: context1034B, whole candidates4298B,
detail1357B. These are not direct private live GM frame measurements. Catalog
remains47 tools/314317B; no public image input changed or stub was registered.

The public map-image integration/source-cache attachment is deliberately owned
by M05; local SourceSnapshots/real-byte/Node tests verify the binding helper now.
The native info call leaves one normal30-minute private original managed by the
existing runtime prune loop. No public URL, game document/asset, persisted
fixture or extra Foundry instance was created. Active Scene unchanged; browser
14.369/test readyGM/console0. Local module3.3.1 ZIP creation passes. External
public-host/client and live configured-S3 acceptance remain later task gates.
