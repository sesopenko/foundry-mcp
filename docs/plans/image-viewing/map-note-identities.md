# Map note identity and legend contract

M03a contract fixed before implementation. M03b owns source coordinate
mapping and original-byte context binding; M04 owns pixels/layout. No annotation
support is claimed by this note-identity task.

## Public applicability evidence

Grounded Docs version14 searches/fresh official pages establish
[NoteDocument label/entry/page](https://foundryvtt.com/api/v14/classes/foundry.documents.NoteDocument.html),
[BaseNote schema](https://foundryvtt.com/api/v14/classes/foundry.documents.BaseNote.html)
and the nullable [SceneLevelsSetField](https://foundryvtt.com/api/v14/classes/foundry.data.fields.SceneLevelsSetField.html).
The field description alone does not explain empty/null applicability.

The official public
[CanvasDocumentMixin](https://foundryvtt.com/api/v14/functions/foundry.documents.abstract.CanvasDocumentMixin.html)
returns [CanvasDocument](https://foundryvtt.com/api/v14/classes/foundry.CanvasDocument.html).
Its `includedInLevel(level: string|Level): boolean` explicitly answers whether
the document belongs to a selected Level. It has no private/protected/internal
annotation. Installed14.369 NoteDocument source extends
`CanvasDocumentMixin(BaseNote)` despite the generated Note page's incomplete
ClientDocumentMixin summary. Production will call the documented member on the
authorized Note and actual owning Level; it will not reproduce the method's
internal logic or depend on private viewed/mesh/tooltip members.

Installed public-member implementation explains empty sets include all levels
and explicit IDs select membership. An actual1-call read-only verification using
public unpersisted marked Note constructors establishes empty, null and explicit
own-level inputs include the selected owning Level, while an explicit foreign
ID excludes it. Supplied null becomes non-null source after cleaning. All10
existing empty-set notes in the sampled Scene are included by the same public
query. Level object and exact ID agree, collection size and active Scene remain
unchanged, and zero persisted fixtures require cleanup. This is tested14.369;
raw malformed/uninitialized null membership is not treated as equivalent by fiat.

## Baseline

`.venv/bin/python -m foundry_mcp_server.map_notes_audit` passed2 calls under120s:
47 tools/309786 compact SDK-model catalog bytes;483 authorized notes in50 Scenes,
all483 source levels empty, all finite coordinates and linked readable entries,
208 stored text overrides. No null/omitted/explicit memberships or denied/missing
entry samples. No labels, paths, IDs, journal bodies or game mutations are output.
Static schema label/hint metadata is absent. Helper tests3 pass outside sandbox,
including consistency/privacy and public membership-verification assertions.

`--membership` runs the separate1-call/60-second method/constructor verification.
It creates no database documents or assets and never activates/views a Scene.
Native existing-world observations do not replace future denial/multilevel/
mutation/cursor tests, which belong alongside the implementation.

## Frozen reader interface

Extend flat `get_map_info` with `section:notes`, requiring exact `level_id`.
Optional `note_keys` is1–100 distinct returned N-positive-integer keys and
requires `expected_revision`. Reject note_keys for assets/tiles and reject note
requests without a level before any document reads. Existing count/byte bounds
and cursors remain. Keys are local to the exact Scene/level/revision, never
standalone UUID selectors. Unknown keys produce InvalidNoteKeys and exact
Scene/level fresh-notes recovery; no silently missing filtered key.

Notes retain the common configuration response. Entries have kind=note,
`note_uuid`, `key`, `x`, `y`, `level_id`, `label`, `label_truncated`, `target_status`,
`journal` and `page`. Journal/page identities are either null or
`{journal_uuid|page_uuid,name,name_truncated}` with canonical owner context;
denied/missing identities are null, not leaked raw source target IDs.
target_status is unlinked, missing_entry, denied_entry, missing_page,
denied_page, linked_entry or linked_page. Coordinates are finite source Scene
coordinates, not original image pixels. Labels clip256 codepoints with explicit
marker; absent/denied labels are null. Linked body content is never hydrated.

Authorize the Note, select applicability via public includedInLevel(actual
owning Level), then inspect source target IDs and public entry/page identities.
Check entry and page permissions before reading their names or the Note label
getter, even when text override is present. Denied linked content makes scope
partial and label null, retaining only authorized Note identity/coordinates/key.
Missing/unlinked targets are explicit states rather than treated as denied.

Assign N1,N2,... in canonical Note UUID order over the complete authorized
applicable-level snapshot, before note_keys filtering/pagination. Duplicate pins
to one target remain separate. Alias numeric order is inherited from this UUID
order. Every selected-level asset/Tile/notes response shares the same revision,
which includes selected level identity and note/membership/target permission/
label witnesses along with mapping-relevant configuration. Changing the level
requires its own revision; bounds, section and note_keys are excluded from the
revision and included where appropriate in cursor scope. All-level assets retain
their own unfiltered catalog revision. This extends M02's broader revision rule
so a legend for another level cannot accidentally agree.

Expose a Python-internal one-page candidate reader for M03b/M05, reusing the
same projection/validation/revision logic. It requires exact Scene/level and
expected revision and returns at most100 notes/48000 compact bytes with normal
continuation. It is not separately discoverable through MCP. The adapter clamps
the requested byte budget to the configured bridge frame budget after computing
the exact UUID-response envelope overhead; an insufficient minimum response
fails ResponseTooLarge without sending an oversized frame. Tests cover a reduced
configured ceiling as well as the default65536-byte limit. No unbounded whole-
Scene note RPC is introduced.

## Implemented verification

Focused notes13 (including actual MCP/production browser dispatch), selected-map17
and combined map JS33 pass. Final full runner passes942 Python (1 existing
skip)/783 JS. Module ZIP creation packages mapNotes.js and its actual imports.
The forged ordinal regression failed accepting N999 at cursor offset0 before
the adapter enforced exact unfiltered alias ordinals; the same test passes.

After restarting the existing Python service and refreshing only the dedicated
development tab, browser14.369/test is readyGM with zero console errors. The
bounded `.venv/bin/python -m foundry_mcp_server.map_notes_audit --legend` passed9
calls under30/120s: discovery, private sample selection, selected-level assets,
3 default notes pages, an exact2-key lookup, an expanded complete notes page and
the active-Scene guard. All21 applicable notes retain agreeing canonical
Note/journal/page identities and selected-level revision across views/filters.
The complete scope/stream and active Scene are unchanged. No bodies, raw labels,
IDs, paths or game data are printed by the harness.

| Workflow stream | Calls | Compact result bytes | MCP envelope bytes | Complete |
| --- | ---: | ---: | ---: | --- |
| Selected-level default assets |1|2962|6394|yes|
| Default complete21-note legend |3|13883|29852|yes|
| Exact2-key follow-up |1|2138|4700|yes|
| Expanded complete21-note legend |1|11021|23492|yes|

Expanded legend and default pagination return equal note content; the fewer
metadata/cursor repetitions reduce this full stream by2862 structured bytes
and6360 MCP bytes, using1 rather than3 calls. This is an equal-content page-bound
comparison, not a claim that the new tool reduces unrelated baseline responses.
Catalog remains47 tools, growing from309786 to314317 compact SDK-model bytes
(+4531B); live tool record27629B versus23098B. Bytes are not billed tokens.

Configured3000-byte internal candidate frames pass exact envelope assertions;
insufficient1024-byte minimum and missing expected revision fail before RPC.
Aliases across20-note pagination/key filters, duplicate pins, denied getter
traps, missing/unlinked targets, schema constraints and clipped malicious text
are tested independently of geometry/rendering. All synthetic subprocesses and
unit-owned files clean up; runtime constructors persisted zero fixtures and
existing game assets/documents were not modified. Installed package14.369.0
corroborates browser14.369 despite the older outer container image label.
