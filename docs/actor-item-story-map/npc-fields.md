# NPC selected source fields

ACT-npc source-helper evidence, October 20, 2026. Integration, live validation,
Item joins and effective statistics remain pending. No story completion claim.

`actorNpc.js` exports `npcFields(source)` and the separate, currently unwired
`npcNoteFields(source)`. Both accept detached `Actor.toObject(true)` source and
return null for other types. Descriptors have JSON Pointer `path`, `present`,
`value` when present, `concept`, and `limitations`. No Foundry APIs are called.

The audited boundary is Foundry **14.369 / PF2e 8.6.1**, immutable revision
`28d9d156f252d084371d994dc359509b49eadf18`:

- [NPCSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/npc/data.ts)
- [Creature source, senses, movement and attributes](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts)
- [Actor source, traits and HP](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/base.ts)
- [IWR sources](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/iwr.ts)
- [Compound IWR exceptions](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/rules/rule-element/iwr/base.ts)

Existing rulebook evidence in the [ledger](evidence.md) and [ACT-npc](stories/ACT-npc.md)
records GM Core pp. 119–120, 123 and 128. Authored creature statistics need not
follow PC construction; an NPC narrative role does not establish a PC build.
No additional rulebook reading or new live evidence is claimed here.

## Exact default allowlist

Paths are relative to `/system/`. Dynamic keys retain JSON Pointer escaping.
Only listed children are returned; arbitrary sibling objects are excluded.

| Fields | Mapping and boundary |
| --- | --- |
| `details.level.value`; `details.alliance` | Creature level and recorded alliance; alliance is not user assignment or narrative role |
| `traits.size.value`, `traits.rarity`, `traits.value/<index>` | Exact size/rarity/trait codes; unknown values preserved |
| `abilities/{str,dex,con,int,wis,cha}.mod` | Attribute modifiers; no legacy ability-score reconstruction or label lookup |
| `attributes.adjustment` | Recorded elite/weak/null; adjustment math never applied |
| `attributes.ac.{value,details}` | Authored Armor Class and exceptional notes |
| `attributes.hp.{value,max,temp,details,tempSource}` | Stored HP/max/temp and notes; `tempSource` is a local Item ID, not a verified UUID or effective application |
| `attributes.allSaves.value`; `saves/{fortitude,reflex,will}.{value,saveDetail}` | Authored save bonuses plus common/specific notes; separate from attribute modifiers |
| `perception.{mod,details,vision}` | Authored Perception bonus, notes and vision source |
| `perception.senses/<index>.{type,acuity,range,source}` | Source sense codes/range/reference; missing optional special-vision fields remain absent |
| `details.languages.value/<index>`, `details.languages.details` | Ordered language codes and communication exceptions |
| `attributes.speed.{value,details}` | Authored land Speed and exceptional movement notes |
| `attributes.speed.otherSpeeds/<index>.{type,value,label,source}` | Other source movement; prepared `total` excluded |
| `skills/<key>.{base,note}` | Authored skill bonus and exceptions; null base remains null, not a calculated attribute fallback |
| `skills/<key>.special/<index>.{label,base,predicate}` | Authored special skill variant; predicate retained as primitive leaves and never evaluated |
| `attributes.immunities/<index>.{type,exceptions}` | Immunity codes and exceptions; no fabricated numeric immunity value |
| `attributes.weaknesses/<index>.{type,value,exceptions,applyOnce}` | Stored weakness and optional applicability flag; no default or target application |
| `attributes.resistances/<index>.{type,value,exceptions,doubleVs}` | Stored resistance; no damage reduction/doubling calculation |
| `initiative.statistic` | Source statistic selector, no initiative bonus |
| `spellcasting.rituals.dc` | Authored ritual DC; not castability evidence |
| `resources.focus.{value,max}` | Recorded source resource fields; no complete effective expenditure claim |
| `details.publication.{title,authors,license,remaster}` | Exact source publication metadata; no edition/errata precedence inferred |

IWR exceptions and `doubleVs` accept code strings or compound `{label,definition}`
records. Compound definitions and special-skill predicates retain JSON primitive
leaves with source paths; empty arrays/objects get explicit markers. No arbitrary
sibling payload is returned. Predicate traversal rejects cycles, non-JSON values,
non-finite numbers, depth above 32 and more than 10,000 visited values, rather
than silently truncating. Reader integration must convert these selector failures
into the established structured error and enforce response pagination/byte bounds.

Absence and optional own `undefined` remain absent. Explicit nullable fields
remain null, zero stays zero, false stays false, and empty collections have
`[]`/`{}` markers. Nonempty collections flatten into leaves. No finite numeric
source field is coerced or recalculated. Source validation is not a rules
legality checker: unknown codes and authored exceptional values remain exact.

## Notes and integration boundaries

Default `npcFields` excludes `details.blurb`, `details.publicNotes` and
`details.privateNotes`. The separate `npcNoteFields` helper selects those exact
strings only, through an explicit Actor `description` request. Three separate
paths preserve blurb, public notes and GM-private notes with mapping
`pf2e.npc.notes.v1`. Present text uses exact UTF-16 fragments and bounded byte
pages; missing fields remain absent records. No HTML is parsed or enriched.
Character/familiar descriptions remain explicitly unsupported. No biography is
included by a default/source-only request.

Seven focused deterministic tests cover authored-versus-effective semantics,
exceptional text, senses/movement/languages, IWR compound and string exceptions,
null/absent/zero/false/empty distinctions, hostile skill-key pointer escaping,
malformed/cyclic/excessive predicates, source immutability and separate notes.
Run `node --test tests/js/actor-npc.test.js`.

Pending integration must connect selected fields to source/mapped sections,
provenance, revisions and pagination; validate Python DTOs and actual MCP
contracts; preserve world/pack/token identity and permissions; and perform focused
read-only checks in the existing runtime. Embedded attacks, abilities, Lore,
casting, inventory and conditions/effects require the story's separate joins.
Prepared `actions`, custom modifiers, derived class/spell DCs, rule elements,
flags, sheet state and complete elite/weak/conditional effective statistics are
excluded. This helper alone does not complete ACT-npc or milestone M-NPC.

## Reader integration checkpoint — October 20, 2026

The shared reader now emits these descriptors in `source`, with mapping
`pf2e.npc.source.v1`, exact raw source paths and contributors. Source remains
partial: integrated sections are pending. Biography is available only through
the explicit description section; private text is never implicitly included.

Focused helper/reader tests cover paginated authored values, no elite arithmetic,
source immutability, malformed source, stale continuations and excluded notes.
Python validates actual Node paginated DTOs, exact paths/concepts/types/provenance,
empty markers and bounded predicate leaves. Actual authenticated MCP on existing
Foundry14.369/PF2e8.6.1 passed three source pages, exact NPC AC/HP and unchanged
source fingerprints. Existing action, attack, Lore, pack and token checks passed.
This is an implementation checkpoint, not completion of ACT-npc or M-NPC.

Final offline validation: 161 Python tests (one skipped) and 136 JavaScript
tests passed with zero failures before the local checkpoint commit.

## Explicit biography verification — October 20, 2026

Focused JavaScript/Python checks passed exact Unicode reconstruction across
multiple bounded pages, empty/missing distinctions, strict provenance and text
keys, stale-note continuations, malformed source, denied GM access, and unsupported
character/familiar descriptions. Actual MCP reconstructed the existing NPC's
three biography paths and compared each present text's SHA-256 with persisted
source, without logging content. Source fingerprints remained unchanged.

## Owned attack and ability references

Explicit `strikes` and `abilities` sections select actual NPC-owned `melee` and
`action` Items respectively. They do not reinterpret carried weapons as attacks
or claim that every acquired benefit is an action Item. Each relationship keeps
exact source name/type, canonical Item UUID, owner and selected token context,
with mapping `pf2e.npc.item-reference.v1`. Duplicate names remain separate.
Follow `mapped.value.target_uuid` with `read_item` and pass its `token_uuid` when
present. No recursive Item source reads occur until that explicit follow-up.

Both sections remain partial with `other_attacks_pending` or
`other_abilities_pending`. A denied marker has no identity/name/raw fields and
adds `related_items_denied`. Permission or membership changes invalidate cursors.
Character/familiar sections remain unsupported. Focused checks cover duplicate
names, strict provenance, linked/synthetic contexts, denied privacy and staleness.

Actual authenticated MCP on Foundry14.369/PF2e8.6.1 followed three existing NPC
attack/action references with correct type and owner. Source and biography
fingerprints stayed unchanged, and prior delivered readers still passed. Live
linked/synthetic reference fixtures remain covered only by deterministic tests;
this does not establish effective-state completeness or finish M-NPC.
