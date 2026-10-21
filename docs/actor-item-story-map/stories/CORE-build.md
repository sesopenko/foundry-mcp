# CORE-build: Build choices, benefits and acquired-document joins

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 3 |
| Planning readiness | Planned |
| Implementation status | Not started |
| Prerequisites | [ITEM-ancestry](ITEM-ancestry.md), [ITEM-heritage](ITEM-heritage.md), [ITEM-background](ITEM-background.md), [ITEM-class](ITEM-class.md), [ITEM-deity](ITEM-deity.md), [ITEM-feat](ITEM-feat.md), [ITEM-lore](ITEM-lore.md) |
| Dependency reason | Needs each build contributor plus owned feat/feature and Lore interpretation. |

## User outcome and implementation

As a reader, I can see the character's selected build and its owned benefits without confusing options with acquisitions.

- Join ancestry/heritage/background/class/deity identities and selected choices to embedded feats/features/Lore using only proven persisted relationships. Do not recreate progression or import grants.
- Distinguish offered choices, selected values, level-gated references and actually acquired documents. Maintain multiple contribution links without duplicating benefits across identity/build/skills/abilities views.
- Preserve class/ancestry HP contributions, proficiency ranks and deity spell/weapon options separately from actor totals, learned spells and owned equipment.
- Audit grant/selection relationship storage before adoption. If a relationship cannot be established, retain named source references and explicitly unknown linkage rather than infer from matching names.

Acceptance: versatile heritage, duplicate skill grants, class-feature category, future class feature, unselected boost and deity-spell option are covered. Missing owner evidence does not manufacture acquisition. Trait labels and source/edition differences remain traceable.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.
