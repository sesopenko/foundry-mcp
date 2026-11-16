# PF2e loot Actor contents

Version 5.1.0 extends existing GM-only readers to world and placed-token
`loot` Actors, including merchant inventories. This is source reading, with
deterministic verification and **live verification pending**. The accepted
runtime range remains Foundry >=14.369,<15 and PF2e >=8.6.1,<9. No new tool or
response contract version is introduced.

## Discover, enumerate and read

1. Use `search_actors({"query":"Chest","types":["loot"]})` for a literal world
   Actor name substring, or navigate `get_actor_tree`. Default world discovery
   now includes loot alongside characters, NPCs and familiars. Names are
   candidates; duplicate names retain distinct UUIDs and folder context.
2. For placed contents, call `list_scene_actors` without a selector, choose a
   returned `scene_uuid`, then call it with `types:["loot"]`. Search matches
   token or Actor names. Inactive Scenes are supported without a canvas.
3. Copy the returned `read_actor` selector and add
   `select:{"details":["inventory.summary"]}`. This selects named canonical
   Item references, stored quantity and same-owner container claims. Default
   Actor reading remains identity-only.
4. Use `read_item` with a returned Item UUID and the supplied `token_uuid`, if
   present. Select `source.physical`, other source groups, exact `description`,
   or explicit `select.evidence:true` as needed. `list_actor_items` offers
   type/name filtering; `select.follow_up:true` returns exact `next_call` data.

Example after discovering the exact token:

```json
{"token_uuid":"Scene.<scene-id>.Token.<token-id>","select":{"details":["inventory.summary"]}}
```

World selectors are `Actor.<id>` UUIDs, never names, paths or owner-local Item
IDs. Placed selectors are `Scene.<id>.Token.<id>` UUIDs. An unlinked token can
have different possessions from its base Actor and from another token sharing
that base. Linked tokens retain their token context even when the Item UUID is
world-owned. Always preserve the returned selectors; do not synthesize UUIDs or
substitute base contents when the current token Actor is unavailable.

`resolve_journal_reference` also admits world/token loot references and their
supported owned Items, preserving anchors and token follow-ups. It reads no
target source automatically. Loot compendium Actors and their Items remain
unsupported, including direct UUID reads; creature pack discovery is unchanged.

## Selected contents and completeness

`read_actor` supports loot identity, `inventory.summary`, full `inventory`,
`select.item_uuids` filtering and optional evidence. Other known sections return
`status:"unsupported"` with `loot_section_unsupported`; they do not enter creature
extractors or read loot Actor system configuration. Capability discovery admits
`loot` with source/mapped support and no effective support. Request
`get_actor_types({"select":{"actor_types":["loot"],"evidence":true}})` for the
per-type restrictions and verification status.

The nine physical Item types are weapon, armor, shield, equipment, consumable,
ammo, backpack, book and treasure. Actual owned physical documents appear once,
including orphaned or cyclic components. Kit documents remain separate bundle
definition references, with the existing partial-interpretation warning; reading
never generates their components. Serialized attachments are source fields,
not additional owned Item UUIDs. Other loot-owned Item types are excluded from
Item listing and counted in `unsupported_count`; direct reads reject them.

The existing version-two Actor/Item envelope remains
`contract_version`, `identity`, `runtime`, `revision`, `sections`, `entries`,
`limitations` and `pagination`. Each entry retains its section/local key and
values with concept, value, basis, and single-contributor presence. Evidence adds
validated raw/mapped/provenance witnesses. See [selective reads](selective-reads.md).

Missing source, present null where permitted by the schema, and present zero
are distinct; quantity is stock,
not converted currency or a stack valuation. Containers resolve only against the
actual owner, with explicit missing, denied, unsupported and cycle diagnostics.
Denied Items expose no names or source. `inventory_scope` distinguishes verified
empty physical inventory from denied contents. Completion covers only the
selected physical inventory scope; Item definitions do not establish usable
abilities or active benefits. Book/kit interpretation limitations remain visible.

GM source names and descriptions can reveal unidentified Items. This is not a
player-facing identification view. No shop configuration, purchases, transfers,
imports, rolls, activation, identification, wealth or total Bulk is implemented.

## Bounds and recovery

Actor/Item reads and Item listings default to ten entries and 8,000 compact
UTF-8 JSON bytes, with limits of 1–100 entries and 8,000–48,000 bytes. World and
Scene discovery retain their existing defaults of 50 entries/48,000 bytes.
The inventory snapshot separately rejects more than 12,000 owned Items or
24,000 records. Selection precedes semantic Item pagination.

Copy `pagination.next_cursor` with every original selector, selection and bound.
On `ContentChanged`, discard accumulated pages and restart. Restore original
inputs or restart on `CursorMismatch`/`InvalidCursor`. An indivisible unit over
budget returns `ResponseTooLarge`; narrow details or raise the budget. Reads
across tools are separate observations, never an atomic inventory snapshot.

`DocumentNotFound` requires rediscovery. `ActorUnavailable` means the current
token Actor cannot be read; base substitution is invalid. `PermissionDenied`
requires authorized GM/document access. `UnsupportedSystem`/`UnsupportedVersion`
require a supported runtime; `BridgeUnavailable` requires reconnecting the
existing ready GM browser. Malformed source or membership fails with `ReadFailed`.

## Evidence and verification

Core access reuses documented [Actor embedded documents](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html),
[TokenDocument.actor and linked/synthetic semantics](https://foundryvtt.com/api/v14/classes/foundry.documents.TokenDocument.html#actor),
and public Item `parent`, `uuid`, `testUserPermission` and `toObject(true)`.
Grounded Docs v14 was checked on November 16, 2026. The release-pinned
[PF2e 8.7.0 loot schema](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/actor/loot/data.ts)
confirms the `loot` subtype and loot/merchant modes; no mode field is read.
Existing pinned physical/container schemas define quantities and containment.
The [upstream GM guide](https://github.com/foundryvtt/pf2e/wiki/GM%27s-Starter-Guide#loot-actors)
describes token-specific contents; rolling wiki guidance is not a versioned API.

Tests cover real browser-generated packets through FastMCP, all nine physical
families and kit definitions, world/linked/synthetic ownership, unsupported
sections without Actor source extraction, permissions, stale continuations,
empty/cyclic/orphan inventories, compendium rejection and journal follow-ups.
Existing creature/party tests retain their boundaries.
The feature commit's full offline runner passed 714 Python tests (one existing
skip) and 727 JavaScript tests, including loot identity binding to the actual
linked/synthetic Scene/token context.

`scripts/loot-read-audit.py` measures inert fixtures through FastMCP with a
100-call/180-second cap; `--catalog-only` measures the existing localhost tool
catalog with one discovery and no document reads. On November 16 the fixture
audit used 19 calls:

| Scenario | Calls | JSON bytes | Complete |
| --- | ---: | ---: | --- |
| Default identity | 1 | 802 | Yes |
| First inventory summary page | 1 | 6,641 | No: 10 of 47 Items |
| One selected inventory Item | 1 | 1,439 | Yes |
| First full inventory page | 1 | 8,253 | No: 3 Items |
| Selected summary with evidence | 1 | 3,408 | Yes |
| Selected Item physical properties | 1 | 2,119 | Yes |
| Complete summary traversal | 5 | 31,726 | Yes: 47 Items |
| Complete Item listing with follow-ups | 5 | 12,604 | Yes: 47 Items |
| Exact description reconstruction | 3 | 5,230 | Yes |

The full inventory first page is limited by its private validation-witness budget
as well as the requested 48,000-byte public budget. Scenarios return different
content; these are not equal-content savings or billed-token measurements.
The localhost catalog grew from 43 tools/263,156 bytes to 43 tools/265,169 bytes.
This is added capability/catalog cost without new tools. The in-memory catalog
has 42 tools/264,631 bytes because development execution is disabled there;
do not compare those differently configured catalogs as a performance result.

Live checks remain pending: the existing development world presents the
post-upgrade **Begin Migration** dialog. Migration was previously deferred and
would alter existing documents. No migration or fixture creation was performed,
and no live world, token, permission or source-fingerprint claim is made.
