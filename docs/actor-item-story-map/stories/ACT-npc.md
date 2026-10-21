# ACT-npc: Read NPC and creature stat blocks

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; effective views gated |
| Implementation status | In progress |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `npc` Actor in book terminology while preserving identity, selected source, contributing Items and completeness.

- **Rules:** GM Core pp. 119–120, 123, 128: creature statistics are authored; narrative NPC role does not require a PC build.
- **Schema:** [PF2e 8.6.1 Actor definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/npc/data.ts), plus [shared creature source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts).
- **API:** [public Actor/token extraction evidence](../evidence.md#public-foundry-api). PF2e derived declarations do not establish an externally supported effective-stat API.

## Source checkpoint: ACT-npc

- [ ] Extract identity/name/type/UUID and version/source/parent context through CORE-extract. Selected `system` fields: `abilities`, `details.level`, selected languages/publication/notes, `perception`, `skills`, `saves`, `attributes.ac`, `attributes.hp`, `attributes.speed`, `attributes.adjustment`.
- [ ] Retain bounded original notes/descriptions and unknown codes. Label every statistic's source/effective basis; do not fill omissions with zeroes. Keep assignment/control separate from subtype.
- [ ] Return embedded Item summaries and next-reader links; basic reading must work before individual Item readers and joins are complete.

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
