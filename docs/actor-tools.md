# Actor and Item reading contracts

**Contract version 1, reviewed October 20, 2026.** This document settles
CORE-contract for implementation. Tools described here are not thereby
registered or implemented. The [story map](actor-item-story-map/index.md) owns
implementation tracking; the [evidence ledger](actor-item-story-map/evidence.md)
owns evidence and open gates. All tools are read-only and require the existing
authenticated, GM-trusted MCP endpoint and a ready authenticated GM browser.
They never import, activate, cast, roll, enrich HTML, update documents or emit chat.

## Compatibility and discovery

`get_actor_types()` has no inputs and returns `contract_version`, `runtime`,
`availability`, `actor_types`, `item_types`, `actor_sections`, `item_sections`,
`limits`, and `limitations`. Runtime contains `core_version`, `system_id`,
`system_version`. Availability has `supported` and `reason` (null when supported,
otherwise an explanation string). Each type/section
entry distinguishes `allowed` (runtime declaration), `in_scope` (this backlog),
`source_supported`, `mapped_supported`, `effective_supported`, and `limitations`.
Type entries have `type` (system subtype) and `name` (display label); section entries have `name`. Limits are `{default_limit:50,max_records:100,min_bytes:8000,max_bytes:48000,max_text_units:6000,max_cursor_characters:4096,max_selector_characters:512}`.
These support flags describe delivered behavior, never merely planned behavior.
Each type/section entry also contains `verification={deterministic,live}`;
each of those two properties is `{status,evidence}`, with status `not_run`,
`passed`, `failed`, or `not_required`, and evidence a list of repository
evidence references. A source reader can be delivered and
deterministically tested while `live=not_run` remains explicit; do not force all
support flags false because a different advanced section still has an open gate.
Enable runtime-dependent claims only after their required live verification.
The registry is maintained per delivered milestone; the full section/type lists
below describe the planned contract, not simultaneous delivery requirements.
`effective_supported` may be false while source and deterministic mappings work.
The tool works on any ready core runtime to explain incompatibility, but performs
no PF2e interpretation outside the pairing below. Next: `get_actor_tree`,
`search_actors`, `list_actor_compendiums`, or `list_scene_actors`.

| Runtime/type | Version-1 policy |
| --- | --- |
| Foundry 14.369 + PF2e 8.6.1 | Documentary target; enable sections only after their story tests and required live verification pass |
| Other core 14 builds / PF2e releases | Unsupported until explicitly verified and added to this matrix; no inferred future compatibility |
| Core 13 | New Actor/Item tools unavailable; no verified compatible PF2e pairing. Existing tools and manifest policy are separate |
| Non-PF2e systems | Discovery reports unsupported system; reader/discovery tools below return `UnsupportedSystem` |
| Actors | character, npc, familiar; no narrative role/control inference from subtype |
| Items | melee, action, feat, spell, spellcastingEntry, lore, condition, effect, affliction, ancestry, heritage, background, class, deity, weapon, armor, shield, equipment, consumable, ammo, backpack, book, kit, treasure |
| Excluded | hazard, vehicle, loot, party, army, base/unknown Actors; campaignFeature, base/unknown Items |

Current development baseline was separately checked through Foundry MCP on
October 20: ready GM browser, Foundry 14.369/PF2e 8.6.1, bridge/server source
1.5.0, 172 NPC Actors and no character/familiar Actors. This establishes runtime
availability for subsequent focused checks; it does not verify the proposed
readers, effective sections or missing populated Actor fixtures. Historical
audit observations in the evidence ledger retain their original dates/status.

Do not change the module's minimum core version as a side effect of this
contract. A matching installed manifest is not proof of the connected runtime.
Every response includes the actual runtime and delivered support information.

## Identity, resolution and permissions

Names, directory paths, local IDs and response-local keys are never read
selectors. Discovery returns canonical absolute UUIDs supplied by Foundry.
Accepted patterns include `Actor.<id>`, `Item.<id>`,
`Actor.<id>.Item.<id>`, `Compendium.<scope>.<pack>.Actor.<id>`,
`Compendium.<scope>.<pack>.Item.<id>`, and embedded Items within a pack Actor.
Treat pack IDs as opaque `collection` strings, not a fixed number of segments.
All UUID selectors are strings of 1–512 characters. Validate resolved document
kind as well as UUID syntax. Never manufacture a
UUID from an Item name, nested source record, generated Strike or casting option.

Token reads use `token_uuid="Scene.<scene-id>.Token.<token-id>"`. `actor_uuid`
and `token_uuid` are mutually exclusive. Obtain current state through public
`token.actor`; report `baseActor` independently. Never substitute the base Actor
when a synthetic Actor is missing. Token Items use their actual resolved Item
UUIDs returned by `list_actor_items`; any synthetic Actor UUID is descriptive
identity, not an accepted `actor_uuid` shortcut. A synthetic-owned Item read also requires its `token_uuid` so the reader
rechecks instance identity before returning data. Linked-token reads may supply
`token_uuid` with a world-owned Item UUID: accept it only if that Item belongs
to the selected `token.actor`. Preserve token context in the response even when
the linked Actor and Item retain world UUIDs. Never reject valid linked context
merely because the Item UUID is world-owned.

A uniform `identity` record contains `document_name`, `id`, `uuid`, `name`,
`type`, `source_kind` (world, compendium, token), `folder` (null or `{id,uuid,name}`),
`pack` (null or `{id,title}`), `actor` (null or `{uuid,name}`), and `instance`.
`instance` is null outside token context; otherwise it contains `scene_uuid`,
`scene_name`, `token_uuid`, `token_name`, `actor_link`, and `base_actor`
(null or `{uuid,name}`). Actor identities have null `actor`; owned Item identities
retain their actual owning actor. IDs/UUIDs are never clipped; display names may
be clipped to 256 Unicode code points with `name_truncated=true` on that record.
Names are context, not identity guarantees.

Resolve full documents asynchronously. Resolve relative journal references only
against their actual originating document, then return canonical selectors;
reader inputs themselves accept absolute UUIDs only. Recheck authorization on
every call, including continuations. The browser must be GM and target documents
must pass explicit `testUserPermission(game.user, "OBSERVER")`; pack documents
also require pack OBSERVER permission. Owned Items require owner permission;
token reads require Scene, Token and resolved Actor permission. Check related
records independently; a denied optional relationship returns a named unresolved
relationship without its private contents. Never accept caller role assertions.
A missing target returns `DocumentNotFound`; a resolved denied target returns
`PermissionDenied`. These tools are intentionally GM-private, not player-safe.

## Reader interfaces and bounded representation

All parameters are keyword inputs. Unknown inputs, duplicate/unknown section
names and incompatible combinations are `InvalidRequest`. Optional values are
omitted rather than empty strings. `read_actor(actor_uuid?, token_uuid?,
sections=["identity","source"], limit=50, max_bytes=48000, cursor?)` requires
exactly one actor selector. `read_item(item_uuid, token_uuid?,
sections=["identity","source"], limit=50, max_bytes=48000, cursor?)` accepts a
world, pack or owned Item UUID; `token_uuid` is required for synthetic-owned
Items and permitted for linked-token context. If supplied, the Item must belong
to the selected current `token.actor`, otherwise return `InvalidRequest`. `list_actor_items` takes the same actor selector pair,
optional `types`, `query`, `limit=50`, `max_bytes=48000`, `cursor`.

`sections` is a nonempty unique list with at most 11 Actor sections or 6 Item
sections; unknown names are invalid even when unsupported known sections remain
valid requests. `types` is a nonempty unique list with at most 3 Actor types or
24 Item types as appropriate; excluded/unknown types are invalid filters.

Identity always appears once per page. Actor sections are `identity`, `source`,
`build`, `statistics`, `skills`, `strikes`, `abilities`, `spellcasting`,
`inventory`, `state`, `effective`. Item sections are `identity`, `source`,
`description`, `rules`, `relationships`, `effective`. `source` contains approved
fields with deterministic book-term mappings, not complete effective values.
Other sections are purpose-specific selections of the same representation.
`description` exposes exact stored description text; `rules` exposes allowlisted
serialized rule-element source without evaluating it. Neither is implicit in
`source`. No arbitrary field path, flags dump, object depth, source-mode switch,
or unrestricted `toObject(false)`/roll-data export is exposed.

Every reader response contains `contract_version`, `runtime`, `identity`,
`revision`, `sections`, `records`, `pagination`, and `limitations`.
`sections` has one entry per requested section: `{name,status,reasons}`, where
status is `complete`, `partial`, `unsupported`, or `not_applicable`. Complete
means all contractually selected records for that section are enumerated after
all pages, not that all PF2e rules/actions are represented. While more records
remain its status is partial with reason `pagination`. Unsupported sections
return no invented values and explain the missing capability/gate.

Each `records` entry is `{key,section,kind,raw,mapped,provenance}`. `key` is a
stable response-local string within the revision, never a mutation selector.
`kind` is `field`, `relationship`, or `text`. `raw` is a list of
`{document_uuid,path,present,value,basis}`; `basis` is `source` or
`supported_effective`. Paths are JSON Pointers into documented serialized data;
`present=false` omits `value`, distinguishing missing from JSON null and zero.
`mapped` contains `{concept,value,unit}` with null unit where inapplicable.
`provenance` contains `contributors` (document UUID/source path/basis triples),
`mapping` (stable mapping identifier), and `limitations` (reason strings).
Nonpersisted concepts have local keys and contributors, never fabricated UUIDs.
Each type story must publish its allowlisted fields and mappings before enabling
that type; this contract intentionally does not invent those 27 field registries.

An unresolved relationship is a record with `kind="relationship"`, raw source
preserved, mapped `{concept,value:{target_uuid,status},unit:null}`; status is
`resolved`, `missing`, `denied`, `unsupported`, or `unverified`. A resolved synthetic
Item target also has `token_uuid` in mapped.value; pass it with target_uuid to
read_item, because its UUID alone is not a sufficient instance selector. Resolve only the
immediate relationship; no recursive source expansion or automatic cross-pack
fetch. Next call: `read_actor`, `list_actor_items`, or `read_item` using returned
selectors. Mere membership, Item presence, rules source and slot counts do not
prove castability, acquired benefits, active conditions or effective statistics.

### Counts, text and continuations

`limit` is an integer 1–100, default 50, bounding records (or discovery nodes)
per page. `max_bytes` is an integer 8000–48000, default 48000, bounding the entire
UTF-8 compact JSON response before RPC framing. Count and byte limits apply
independently; no caller can disable them. All cursors are opaque bounded strings
(maximum 4096 ASCII characters); callers must return them unchanged.

`pagination` is `{complete,next_cursor,returned}`. `returned` counts this page's
records/nodes. `complete=true` requires null cursor; false requires a usable
cursor. Repeat the identical tool and all original inputs plus `cursor`.
Cursors bind tool, normalized selectors/filters/sections/bounds, runtime, revision
and position. Any changed input is `CursorMismatch`; restart without cursor.

Text fields are exact stored strings, never enriched/normalized/sanitized source.
Long text emits `kind="text"` records with `raw[0].value` holding a fragment and
`text={path,start,end,total,complete}` alongside the ordinary record fields.
Positions count UTF-16 code units, never split surrogate pairs, and each fragment
is at most 6000 code units subject to byte bounds. Concatenate ordered fragments
with matching document/path/revision to reconstruct exact source. Fragments may
split markup; no repair wrapper is added. Mapped text references its source path
rather than duplicating the text. Non-text metadata records are indivisible;
`ResponseTooLarge` identifies the record/path if it cannot fit. Never silently
skip records or truncate source arrays; flatten selected arrays into records.

Revision is an opaque digest of the selected source snapshot, identity,
relationship selector fields, scope membership/order and runtime needed for this
request. Effective sections additionally include every supported effective
contributor. An aggregate cannot be advertised consistent if its dependency
snapshot cannot be verified. Capture once, serialize detached values, and
recheck the dependency digest before returning; change returns `ContentChanged`.
Each continuation recomputes and compares revisions; restart without cursor on
change. No old/new page mixing or persistent authoritative cache. Revision is a
change marker, not a lock or promise the world cannot change after the response.
Changes outside the request's selected dependencies need not invalidate it.

## Discovery tools

All discovery responses share `contract_version`, `runtime`, `revision`,
`nodes`, `scopes`, `pagination`, `limitations`. Each scope has `{id,status,reason}`;
status is `searched`, `failed`, `incomplete`, or `denied`. Completion covers
selected scopes only. A failed/incomplete scope prevents an exhaustive-absence
claim even if node pagination completes. Node `kind` is `folder`, `actor`,
`item`, `pack`, `scene`, or `token`; document nodes carry `identity`, hierarchy
nodes carry stable IDs/names and `parent_uuid` (null at root). Discovery may
return source-supported types before their mapped sections ship; never advertise
an unimplemented reader path as available.

| Tool and exact additional inputs | Behavior and next step |
| --- | --- |
| `get_actor_tree(folder_uuid?, depth=2, limit=50, max_bytes=48000, cursor?)` | World Actor folders, including empty folders and unfiled Actors. Depth 1–5; root is depth 0. Flattened preorder nodes, folders first, names case-insensitive then UUID tie-break; no UI tree dependency. A depth-limited folder has `children_complete=false` and `expand={folder_uuid}`; expand without cursor. Pagination completeness differs from `tree_complete`, also returned. Next read an Actor or expand |
| `search_actors(query, types?, folder_uuid?, recursive=true, limit=50, max_bytes=48000, cursor?)` | World Actor names only; query 1–200 code points after trim. Locale-independent lowercase literal substring, no regex/fuzzy/biography search; type list intersects in-scope types. Folder filter uses actual relationships. Return duplicates with identity/folder context, ordered name then UUID. Empty means no literal match in completed scope, not no creature exists. Next read using `actor_uuid=node.identity.uuid` |
| `list_actor_compendiums(document_type="Actor", query?, limit=50, max_bytes=48000, cursor?)` | document_type is Actor or Item; query optional title/collection substring with same bounds. Enumerate readable packs, `{id,title,document_type,visible}`; directory folder context only when verified publicly, otherwise null with limitation. No imports/hydration; title never selector. Next search selected pack IDs |
| `search_compendium_actors(pack_ids, query, types?, document_type="Actor", limit=50, max_bytes=48000, cursor?)` | Explicit 1–10 unique pack IDs from listing, each 1–256 characters; document_type Actor or Item. Index only, selected type/name fields; no all-pack implicit scan or full hydration. Return one scope status per requested pack, preserving partial failures; indexed names/types/UUIDs with pack context, ordered pack ID/name/UUID. Absent index type stays incomplete until supported narrow hydration establishes type; never misclassify. Next read using `actor_uuid=node.identity.uuid` or `item_uuid=node.identity.uuid` |
| `list_scene_actors(scene_uuid?, query?, types?, limit=50, max_bytes=48000, cursor?)` | Without scene_uuid list readable scenes (no token enumeration; query/types forbidden); with it list placed tokens with resolved in-scope Actors, including linked/synthetic/base relationships, hidden token included for GM. Query matches token or Actor name literally. No prototype tokens/canvas dependency. A token lacking Actor is an explicit node with resolution limitation, not silently dropped. Next read_actor(token_uuid=...) |
| `list_actor_items(actor_uuid?, token_uuid?, types?, query?, limit=50, max_bytes=48000, cursor?)` | In-scope embedded Items, identities plus named container/casting/master/grant relationships only where allowlisted; unsupported Item types contribute `unsupported_count` without claiming a complete ability list. Query matches Item name literally. Sort type/name/UUID. Next read_item with returned instance context |

Each discoverable readable document node also has `next_call`, either null
with an actionable limitation or `{tool,arguments}`. `tool` is a published
reader/navigation name and `arguments` is its complete selector object. For
example, an Actor node returns `{tool:"read_actor",arguments:{actor_uuid:
"Actor.example"}}`; a token node returns `{tool:"read_actor",arguments:
{token_uuid:"Scene.example.Token.example"}}`; a synthetic Item node returns
`{tool:"read_item",arguments:{item_uuid:"<returned identity.uuid>",
token_uuid:"<returned instance.token_uuid>"}}`. The strings inside angle
brackets here describe returned values, not literal selectors. Identity has
`uuid`; it has no `actor_uuid` or `item_uuid` property. Callers may copy
`next_call.arguments` directly and add section/limit inputs. If only source
reading is delivered, next_call still points to that source-capable reader;
never offer a reader that has not shipped. Folder expansion uses the separately
defined `expand` object. Scene nodes point to their scoped list tool with
`scene_uuid`. Pack nodes have `next_call:null`,
`search_scope={pack_ids:[id],document_type}` and an actionable limitation: add a
literal `query` and call `search_compendium_actors`. A pack title is never
invented as the search query.

World Actor nodes include `parent_uuid`, `depth` and `folder_path` (ordered
`{id,uuid,name,name_truncated}` ancestors). Folder nodes contain `id`, `uuid`,
`name`, `name_truncated`, `parent_uuid`, `depth`, `children_complete` and `expand`.
Scene nodes contain `id`, `uuid`, `name`, `name_truncated`, `parent_uuid:null` and
`next_call`. Token nodes additionally contain nullable current Actor `identity`,
`actor_link`, nullable `base_actor`, and `limitations`; their `parent_uuid` is the
Scene UUID. `list_scene_actors` also returns `unsupported_count`, counting placed
tokens whose resolved Actor type is outside this backlog, separately from
caller type filters (zero when only listing scenes). Missing current Actors
remain visible with `next_call:null` and an actionable limitation.

Optional query uses the search normalization above; blank is invalid. Omitted
types means all in-scope types; empty lists/unknown types are invalid. Bounds are
integers, not booleans/coerced strings. Standalone world Items are readable by
canonical UUID; no general world Item search is promised in v1. Journal link
integration returns typed `next_call` objects for these tools while preserving
existing journal source/reference continuation semantics.

## Errors and evidence gates

Tool failures return MCP `isError=true` with structured `{code,message,recovery}`;
transport/RPC failures preserve their existing outer framing, carrying these
fields without traceback or secrets. Invalid whole requests produce no partial
records; optional section/relationship limitations belong in successful data.

| Code | Recovery |
| --- | --- |
| `InvalidRequest` | Correct named input/bounds/selectors; error identifies the input |
| `UnsupportedSystem`, `UnsupportedVersion` | Inspect get_actor_types; use supported pairing; no PF2e mapping attempted |
| `UnsupportedType` | Target exists but type excluded; inspect get_actor_types; do not coerce |
| `DocumentNotFound` | Rediscover canonical selector in its original scope |
| `PermissionDenied` | Authorized GM must grant required document/pack access; retry does not bypass checks |
| `ActorUnavailable` | Token exists but current actor cannot resolve; inspect scene/base association; no template fallback |
| `NotReady`, `BridgeUnavailable` | Restore existing ready GM bridge and retry; do not create another world/server |
| `InvalidCursor`, `CursorMismatch` | Restart same investigation without cursor |
| `ContentChanged` | Discard accumulated pages for that request; restart without cursor |
| `ResponseTooLarge` | Select fewer sections or raise max_bytes within bounds; failing path/record is named |
| `ReadFailed` | Retry once or inspect runtime diagnostics; no silent empty result |

PF2e-specific mappings must identify type/schema dependency and source-versus-
derived assumptions in implementation docs/JSDoc. The ledger's G-PC,
G-FAMILIAR, G-CAST, G-STATE, G-SPECIAL and G-LINKS remain gates: default source
reading never closes them. In particular no complete PC Strike, familiar-derived
statistic, prepared expenditure, focus maximum, condition activity/expiry or
advanced book/affliction interpretation is advertised until its own supported
contract, fixtures and required existing-runtime check pass. An explicitly
requested gated `effective` section is `unsupported`, leaving verified requested
sections usable. No reimplementation of PF2e calculations fills a gate.

## Concrete reader examples

Examples use illustrative IDs/revisions and minimal source data, not live proof.
All responses have the complete top-level shape; byte counts are enforced by the
implementation, not stored as a self-referential serialized-size field.

World request: `read_actor(actor_uuid="Actor.worldNpc", sections=["identity","source"])`.

```json
{"contract_version":1,"runtime":{"core_version":"14.369","system_id":"pf2e","system_version":"8.6.1"},"identity":{"document_name":"Actor","id":"worldNpc","uuid":"Actor.worldNpc","name":"Guard","name_truncated":false,"type":"npc","source_kind":"world","folder":null,"pack":null,"actor":null,"instance":null},"revision":"opaque-world-revision","sections":[{"name":"identity","status":"complete","reasons":[]},{"name":"source","status":"complete","reasons":[]}],"records":[{"key":"source.level","section":"source","kind":"field","raw":[{"document_uuid":"Actor.worldNpc","path":"/system/details/level/value","present":true,"value":2,"basis":"source"}],"mapped":{"concept":"level","value":2,"unit":null},"provenance":{"contributors":[{"document_uuid":"Actor.worldNpc","path":"/system/details/level/value","basis":"source"}],"mapping":"pf2e.npc.level.v1","limitations":[]}}],"pagination":{"complete":true,"next_cursor":null,"returned":1},"limitations":["Illustrative selected source; no effective statistics claimed."]}
```

Compendium request: `read_item(item_uuid="Compendium.pf2e.spells-srd.Item.packSpell", sections=["identity"])`.

```json
{"contract_version":1,"runtime":{"core_version":"14.369","system_id":"pf2e","system_version":"8.6.1"},"identity":{"document_name":"Item","id":"packSpell","uuid":"Compendium.pf2e.spells-srd.Item.packSpell","name":"Example Spell","name_truncated":false,"type":"spell","source_kind":"compendium","folder":null,"pack":{"id":"pf2e.spells-srd","title":"Spells"},"actor":null,"instance":null},"revision":"opaque-pack-revision","sections":[{"name":"identity","status":"complete","reasons":[]}],"records":[],"pagination":{"complete":true,"next_cursor":null,"returned":0},"limitations":[]}
```

Unlinked token request: `read_actor(token_uuid="Scene.sceneA.Token.tokenA", sections=["identity","effective"])`.

```json
{"contract_version":1,"runtime":{"core_version":"14.369","system_id":"pf2e","system_version":"8.6.1"},"identity":{"document_name":"Actor","id":"baseNpc","uuid":"Scene.sceneA.Token.tokenA.Actor.baseNpc","name":"Wounded Guard","name_truncated":false,"type":"npc","source_kind":"token","folder":null,"pack":null,"actor":null,"instance":{"scene_uuid":"Scene.sceneA","scene_name":"Gate","token_uuid":"Scene.sceneA.Token.tokenA","token_name":"Guard A","actor_link":false,"base_actor":{"uuid":"Actor.baseNpc","name":"Guard"}}},"revision":"opaque-token-revision","sections":[{"name":"identity","status":"complete","reasons":[]},{"name":"effective","status":"unsupported","reasons":["Required effective-value evidence gate remains open."]}],"records":[],"pagination":{"complete":true,"next_cursor":null,"returned":0},"limitations":["Use token_uuid for this instance; do not read base_actor as current state."]}
```

The token example's Actor UUID illustrates a runtime-returned identity; its
spelling must never be constructed by the caller. For Items returned from that
instance, pass both their returned `item_uuid` and `token_uuid` to `read_item`.

## CORE-contract review acceptance

This checklist validates the design artifact, not registered MCP tools or runtime
support. Implementation acceptance separately compares real discovery schemas
and descriptions to this contract and executes the relevant story tests.

- [x] Canonical world/pack/owned selectors, explicit linked/synthetic token context,
  duplicate-name behavior and returned next-call selectors are defined.
- [x] Identity, selected raw fields, deterministic mappings, provenance, absent/null
  values, source/effective separation and section completeness are concrete.
- [x] Defaults, unique-list/count/string/UTF-8/text bounds, cursor inputs, revision
  dependencies, stale-result recovery and error distinctions are specified.
- [x] GM authentication, document/pack/owner/token permission checks and non-PF2e
  boundaries are explicit; clients cannot claim their own authority.
- [x] Documentary version target, unsupported v13 pairing and incremental delivered
  registry are distinct; required effective/live evidence gates remain visible.
- [x] World Actor, compendium Item and unlinked-token responses are concrete JSON;
  examples are illustrative and make no new live-verification claim.
- [x] Main-agent review approves this contract before dependent implementation.
- [ ] Delivered tools match their actual MCP descriptions/input schemas and pass
  focused boundary tests plus required existing-runtime verification.

## Incremental delivery registry

The extraction foundation initially reads canonical identity and selected core `/name` and `/type` source fields. Item `description` reads the bounded PF2e `/system/description/value` source explicitly. Type-specific system fields and book mappings are added only after their individual stories pass. Initial source sections are partial with `type_reader_pending` even when all available common records have been paginated; this does not represent a completed type story. `source_supported` can describe that explicitly limited foundation, while `mapped_supported` and `effective_supported` remain false. Later type registrations replace that limitation only for the fields/sections actually delivered.

### Shared physical source milestone

For nine physical types, `source` now includes the exact [physical field registry](actor-item-story-map/physical-fields.md), including price.per and concrete source omissions. Serialized attachments carry local source paths, not invented document UUIDs. Alternate unidentified description text appears only in an explicit `description` request. Source remains partial with `type_reader_pending` until the concrete type reader ships; no effective Bulk, investment bonus or market price is calculated. The schema-permitted undefined price.sizeSensitive source field is reported absent, never as prepared false.

### Action source milestone

Action Items now deliver the [selected field registry](actor-item-story-map/action-fields.md), deterministic activation labels and explicitly requested immediate self-effect references. Source records are complete after pagination; this does not imply current action usability. Source-only calls never hydrate effects. Relationship target permissions/identity and synthetic token context are rechecked for revisions. All other concrete Item readers retain their own pending status; rules and effective sections remain unsupported.

### NPC attack source milestone

The [NPC attack field registry](actor-item-story-map/melee-fields.md) is delivered for `melee` Items. Authored attack mode, bonus and separate damage components are preserved independently of carried gear. Null stored range means no_explicit_range, not exclusive melee capability. Explicit relationship records preserve additional-effect labels as unverified references; they never guess UUIDs or activate an effect. Source/relationship sections are complete for their selected allowlist after pagination. Effective attack calculations remain unsupported; live checks cover Strikes while other modes have schema/fixture coverage.
