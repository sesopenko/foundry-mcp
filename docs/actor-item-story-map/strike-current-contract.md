# Declared current Strike view

Implemented contract for character/NPC `read_actor(sections=['strikes'])`,
Foundry14.369/PF2e8.6.1, revision
`28d9d156f252d084371d994dc359509b49eadf18`. Selected live support is recorded
below; full current damage and Actor-story completion remain separate gates.

Public [ActorData.system](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorData.html#system)
plus pinned `character/data.ts` and `npc/data.ts` declare `actions` arrays.
`actor/data/base.ts` declares BasicAttackAction/StrikeData; `modifiers.ts` declares
own `totalModifier` and `breakdown`. Sheet data and preparation methods are not
dependencies. Existing NPC authored melee references remain separate and unchanged.

## Closed selection and bounds

Select own data descriptors only. The root is `/system/actions/I`; alternate
usages extend it with `/altUsages/J`. Each node is a Strike only when own `type`
is `strike`. Area/auto-fire and unknown kinds get an aggregate unsupported marker.
Never read their statistic objects or execute attack/roll/damage/critical,
preparation, auxiliary actions, modifiers getters or MAP arithmetic.

Common scalar leaves: `type`, `slug`, `label`, `glyph`, `description`, `breakdown`
(strings), `ready`, `canAttack` (booleans), `totalModifier` (finite number).
Character-only: `visible`, `handsAvailable` (booleans). NPC-only: `sourceId`,
`attackRollType` (strings). Common arrays: `options` (strings), `variants`
(`penalty`: finite number; `label`: string), `traits` (`name`, `label`: strings;
`description`: nullable string). Character additionally exposes string `domains`
and equivalent `weaponTraits`. Preserve ordered duplicates. Empty/missing arrays
retain root markers. Alternate usages recurse without deduplicating labels.

Bounds: 12,000 owned Items; 256 action nodes including alternatives; depth four
(top-level depth zero); 16 variants, 64 traits per list, 256 options/domains;
24,000 emitted records; 300,000 UTF-16 units per selected string. Cycles, holes,
malformed selected values or exceeded bounds fail ReadFailed. These are snapshot
bounds, distinct from returned count/byte pagination. No truncation is silent.

## Exact records

Normal fields use key `strikes:current:<path>`, section `strikes`, kind `field`,
mapping `pf2e.actor.strike-current.v1`, one raw Actor witness at that exact path
with `basis: transformed`, and matching contributors. Mapped unit is null and
mapped value equals the present primitive, or null when absent/array marker.
Empty array markers retain raw `[]`; missing markers have no raw value.
Concepts use prefix `current_strike_` with this closed suffix table:
`type`, `slug`, `label`, `glyph→action_glyph`, `description`,
`breakdown→attack_breakdown`, `ready`, `canAttack→can_attack`,
`totalModifier→attack_modifier`, `visible`, `handsAvailable→hands_available`,
`sourceId→source_item_local_id`, `attackRollType→attack_roll_type`.
Array entry suffixes: `options/I→option`, `domains/I→domain`,
`variants/I/penalty→map_penalty`, `variants/I/label→variant_label`,
`traits/I/name→trait_code`, `/label→trait_label`, `/description→trait_description`;
`weaponTraits` uses corresponding `weapon_trait_*` suffixes.
Array-root suffixes are `collection` for `/system/actions`, otherwise `options`,
`domains`, `variants`, `traits`, `weapon_traits`, `alternate_usages`.

Strings exceeding 1,000 serialized UTF-8 bytes use existing `textFragments`:
kind `text`, key `strikes:current:<path>:text:<index>`, mapped value null and
`text: {path,start,end,total,complete}` in UTF-16 units. Raw value is the exact
fragment; callers reconstruct the field by returned order. No enrichment occurs.
Current-field limitations are exactly `current_strike_not_target_context`.

Own accessors are not ordinary absent fields. Emit
`strikes:unavailable:<path>`, mapping `pf2e.actor.strike-capability.v1`, kind
`field`, no raw/contributors, concept `current_strike_field_support`, value
`{status: unsupported, reason: accessor_not_read, path: <path>}`. Do not invoke
getters or reconstruct PC variant labels/penalties. Missing own fields retain
ordinary absent witnesses; inherited fields are not fallbacks.

## Origins and privacy

Check own `action.item` and all relevant Item permissions before labels, slug,
traits or totals. Verify selected Actor parent and membership. If an ephemeral
reference shares a local ID with an owned Item, check that Item's permission too;
matching names/IDs alone do not establish canonical origin.

Origin key is `strikes:origin:<node path>`, mapping
`pf2e.actor.strike-origin.v1`, kind `relationship`, concept
`current_strike_origin`, limitation `current_strike_not_target_context`.
Every origin has its Actor `.../type` transformed witness. Only exact permitted
owned object membership with expected type (character weapon/NPC melee) returns
`{status: resolved,target_uuid,type,name,name_truncated,token_uuid?}`; include
that actual Item's `/name` and `/type` source witnesses. Raw names preserve the
exact persisted string; mapped names are clipped to 256 codepoints. Follow
`read_item`, retaining token context.

A permitted ephemeral same-parent Item returns `{status: generated,target_uuid:
null}`; it acquires no canonical Item identity. An absent/accessor/foreign or
unverified origin returns `{status: unavailable,target_uuid:null}` and no other
node fields, because source privacy could not be established. Denied nodes expose
only one aggregate `strikes:current:denied` capability record, no node selectors
or labels, value `{status: denied,target_uuid:null}`. No invented UUIDs appear.

Aggregate non-Strike marker: `strikes:capability:non_strike_actions`, same
capability mapping, empty raw/contributors, concept `current_strike_capability`,
value `{status: unsupported,reason: non_strike_actions_unsupported}`.
The denied marker uses that same concept. All capability limitations match the
current-field limitation above.

## Completeness and verification

Always partial, with `target_context_not_evaluated` and
`current_strike_damage_unsupported`. Add `current_strike_fields_unavailable`
for ordinary missing/accessor fields, `non_strike_actions_unsupported` for other
kinds, `strike_items_denied` for denied nodes, and
`current_strike_origins_unavailable` for unavailable origins. Existing NPC source
reasons remain; ordinary shared pagination may add `pagination`.

Selected current values, origin identities, permissions and source witnesses
participate in revision hashing. Default/source-only requests never read actions.
Familiar Strikes stay unsupported. Test generated unarmed without owned Items,
canonical and denied origins, alternate usages, getter-backed PC MAP, text and
count/byte continuation, current-only staleness, world/pack/token identities and
strict Python DTO/discovery boundaries before live verification. No rolls or
game-document writes are permitted by this view.

## Runtime verification — October 25

The default read-only runner checked existing world/synthetic NPCs: 21 pages,
156 records, 168 raw witnesses and four canonical owned origins in 53 MCP calls.
Character data was unavailable in that existing scope; no source model or guessed
Item was substituted for a character.

The opt-in `--character-fixture` run created one exact run-marked character in
the same existing test world, with zero owned Items. Public system preparation
supplied its generated unarmed Strike without a persisted Weapon Item. Combined
with the existing NPCs, the run passed **29 pages, 214 records, 220 raw witnesses,
four owned origins and one generated origin in 78 MCP calls**. Six PC variant
accessor capabilities were independently confirmed without invoking their getters.
The character had a present finite attack modifier and no fabricated Item UUID.

Every selected witness matched independent own public-model data or exact Item
source, including text-fragment boundaries. Canonical origin follow-ups and full
source fingerprints passed. Exact UUID/type/run-marker cleanup removed only the
temporary character and confirmed no pending creation. Nine offline harness
tests cover default read-only operation, lost responses, deferred creation,
timeouts, cleanup identity and failure reporting. The reader itself never writes.

Deterministic tests also cover alternatives, denied sources, Unicode clipping
and exact raw names, long text, model-only stale continuations and world/pack/token
contexts. Live pack and alternate-usage configurations remain unverified. Damage,
target eligibility and non-Strike attack kinds remain explicitly unsupported.
ACT-character and ACT-npc remain incomplete under their original dependencies.
