# ACT-npc: Read NPC and creature stat blocks

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; effective views gated |
| Implementation status | Source implemented |
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
completion. Full integrated views remain the separate M-NPC checkpoint below.

## Integrated checkpoint: M-NPC

Required creature views: identity/level/traits; Perception/senses/languages; attributes and skills; defenses, HP and immunities/weaknesses/resistances; movement; authored Strikes and other attacks; abilities; spellcasting; equipment and supported current state. Preserve exceptional notes and source/effective limits for every section.

Prerequisites beyond the source checkpoint: [CORE-casting](CORE-casting.md), [CORE-inventory](CORE-inventory.md), [CORE-state](CORE-state.md), [ITEM-melee](ITEM-melee.md), [ITEM-action](ITEM-action.md), [ITEM-lore](ITEM-lore.md).

- [ ] Join authored NPC `melee` attacks, action abilities, Lore specialties, spellcasting groups, inventory and stored state. Preserve special skill/defense/movement notes and distinguish source/base values from elite/weak/current values. Do not derive authored attacks from carried weapons.
- [ ] Support world, compendium and token-instance contexts through CORE-packs/CORE-token adapters when available. Their end-to-end acceptance belongs to CORE-acceptance; they do not block basic world reading.
- [ ] Preserve selected raw fields, mapped sections and contributor/source paths side by side, with bounded continuations and explicit unsupported/unread sections.
- [ ] Verify supported effective interfaces and existing live fixtures before claiming full current statistics. Source-only delivery does not close this advanced gate.

## Acceptance scenarios

- Source-only NPC without spells remains useful and explicit about unread sections.
- Ranged `melee` attack, multiple damage components, special skills and duplicate names preserve context.
- Elite/weak or affected NPC reports extraction basis; source values are not advertised as complete current values.
- Re-resolve the same canonical target through a journal link and direct discovery. World, pack and synthetic Actor/Item identities never substitute for each other.
- Non-PF2e, denied, missing and unsupported-type paths are actionable; no writes, imports, rolls or activations occur.

## Readiness and outstanding gates

Source checkpoint is ready after shared contracts/extraction. Integrated source joins are specified; effective statistics remain gated by supported-interface evidence and representative live fixtures. No populated character/familiar was live-verified in the original research, and no browser is connected in this audit. v13 PF2e support is unverified. See [evidence](../evidence.md#open-verification-gates).

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

The section remains partial; remaining skill/sense/language/IWR views, state,
casting and full integrated current acceptance remain open. This checkpoint does
not close M-NPC or mark the story Complete.

## Declared current Strike checkpoint — October 25, 2026

Explicit Strikes now combines separately identified declared current action data
with the existing authored melee Item references. Existing world/synthetic NPCs
passed independent current witnesses and canonical owned-source follow-ups with
unchanged source fingerprints. See the [current Strike contract](../strike-current-contract.md)
for the combined character/NPC verification and bounds. Damage, target-specific
application and other attack modes remain unsupported. Shared casting/state and
complete M-NPC acceptance remain open.
