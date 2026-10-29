# ACT-npc: Read NPC and creature stat blocks

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Declared views verified; advanced limits explicit |
| Implementation status | Complete |
| Integrated status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `npc` Actor in book terminology while preserving identity, selected source, contributing Items and completeness.

- **Rules:** GM Core pp. 119–120, 123, 128: creature statistics are authored; narrative NPC role does not require a PC build.
- **Schema:** [PF2e 8.6.1 Actor definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/npc/data.ts), plus [shared creature source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts).
- **API:** [public Actor/token extraction evidence](../evidence.md#public-foundry-api). PF2e derived declarations do not establish an externally supported effective-stat API.

## Source checkpoint: ACT-npc

- [x] Extract identity/name/type/UUID and version/source/parent context through CORE-extract. Selected `system` fields: `abilities`, `details.level`, selected languages/publication/notes, `perception`, `skills`, `saves`, `attributes.ac`, `attributes.hp`, `attributes.speed`, `attributes.adjustment`.
- [x] Retain bounded original notes/descriptions and unknown codes. Label every statistic's source/effective basis; do not fill omissions with zeroes. Keep assignment/control separate from subtype.
- [x] Return embedded Item summaries and next-reader links; basic reading must work before individual Item readers and joins are complete.

Source checkpoint evidence: [field boundary and runtime verification](../npc-fields.md).
`read_actor` supplies selected source and explicit biography, with partial owned
attack/action/Lore references. `list_actor_items` supplies all supported embedded
Item summaries and concrete `read_item` next calls without requiring type-reader
completion. The separate M-NPC checkpoint below is now verified for the declared
supported/partial views; see the [closure matrix](../npc-acceptance.md).

## Integrated checkpoint: M-NPC

Required creature views: identity/level/traits; Perception/senses/languages; attributes and skills; defenses, HP and immunities/weaknesses/resistances; movement; authored Strikes and other attacks; abilities; spellcasting; equipment and supported current state. Preserve exceptional notes and source/effective limits for every section.

Prerequisites beyond the source checkpoint: [CORE-casting](CORE-casting.md), [CORE-inventory](CORE-inventory.md), [CORE-state](CORE-state.md), [ITEM-melee](ITEM-melee.md), [ITEM-action](ITEM-action.md), [ITEM-lore](ITEM-lore.md).

- [x] Join authored NPC `melee` attacks, action abilities, Lore specialties, spellcasting groups, inventory and stored state. Preserve special skill/defense/movement notes and distinguish source/base values from elite/weak/current values. Do not derive authored attacks from carried weapons.
- [x] Support world, compendium and token-instance contexts through CORE-packs/CORE-token adapters when available. Their end-to-end acceptance belongs to CORE-acceptance; they do not block basic world reading.
- [x] Preserve selected raw fields, mapped sections and contributor/source paths side by side, with bounded continuations and explicit unsupported/unread sections.
- [x] Verify supported effective interfaces and existing live fixtures before claiming full current statistics. Source-only delivery does not close this advanced gate.

## Acceptance scenarios

- Source-only NPC without spells remains useful and explicit about unread sections.
- Ranged `melee` attack, multiple damage components, special skills and duplicate names preserve context.
- Elite/weak or affected NPC reports extraction basis; source values are not advertised as complete current values.
- Re-resolve the same canonical target through a journal link and direct discovery. World, pack and synthetic Actor/Item identities never substitute for each other.
- Non-PF2e, denied, missing and unsupported-type paths are actionable; no writes, imports, rolls or activations occur.

## Readiness and outstanding gates

The [NPC acceptance audit](../npc-acceptance.md) verifies the declared joined
source/current views with scoped runtime evidence and combined-section tests.
Advanced effective limits and broader end-to-end context gates remain explicit.
The dated checkpoints below preserve historical evidence; their earlier open
status is superseded by the October 28 audit. v13/future PF2e support remains
unverified. See [evidence](../evidence.md#open-verification-gates).

This is one story with two checkpoints, not separate source/effective actor stories. Close it only when the declared delivered sections pass and every remaining advanced limitation is explicitly recorded; never mark an unsupported effective capability verified.

## Selected current-statistics checkpoint — October 23, 2026

Explicit statistics now selects transformed attributes, AC/HP, saves,
Perception/vision and movement with a separate raw/provenance basis from source.
Actual MCP verified an existing elite world NPC and an unlinked synthetic NPC,
82 records over 13 pages, with unchanged source/current snapshots. The elite
sample preserved source AC 22 separately from current 24 and source maximum HP
65 separately from current 85; no local elite arithmetic was implemented.
See [contract](../current-statistics-contract.md) and
[verification](../current-statistics-verification.md).

At that checkpoint the section remained partial and skill/sense/language/IWR,
state, casting and combined acceptance were still open. Subsequent verification
is consolidated below; full current statistics remain outside the delivered
subset rather than being certified by this historical run.

## Declared current Strike checkpoint — October 25, 2026

Explicit Strikes now combines separately identified declared current action data
with the existing authored melee Item references. Existing world/synthetic NPCs
passed independent current witnesses and canonical owned-source follow-ups with
unchanged source fingerprints. See the [current Strike contract](../strike-current-contract.md)
for the combined character/NPC verification and bounds. Damage, target-specific
application and other current attack modes remain unsupported. Shared
casting/state and M-NPC acceptance were still open at that checkpoint; their
subsequent completion is consolidated below.

## Integrated acceptance and closure — October 28, 2026

The [closure matrix](../npc-acceptance.md) audits the original requirements
against the production readers, combined JavaScript/Python acceptance at
`a87a830`, and scoped runtime verification. The newly verified current Skills
boundary closes the final identified NPC-specific live gap: an existing NPC
returned 221 current rows across 23 pages, one independent source Lore reference
and one resolved current owner-local Lore join in 36 MCP calls, with unchanged
fingerprints. Existing core/supplemental statistics, current Strikes, casting,
inventory and condition/effect evidence retain their separate precise scopes.

ACT-npc and M-NPC are Complete for the declared supported/partial views. Current
damage, conditional skill variants, target-dependent IWR/attack applicability,
complete action enumeration, casting availability and condition suppression/
application remain unsupported or unevaluated as documented. Dedicated
affliction functionality is Deferred by the user's approved decision; it is not
implemented or counted complete. Full world/compendium/token and journal
workflows remain CORE-acceptance's separate gate, including CORE-token's existing
same-base token-pair requirement. This closure does not satisfy those gates.
