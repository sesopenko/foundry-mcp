# PF2e 8.7.0 weapon control audit

The matrix uses the GM's control IDs. Paths are relative to the source Item's
`system` unless prefixed with a slash. Each prior reader selection uses source
values. The sheet projection reports transformed values separately and gives
a reason when no display witness is available. [GM workflow](item-editing.md)

| Controls | Source witness | Choices, clearing and dependency | Prior reader |
| --- | --- | --- | --- |
| Artwork, Name, Display name | /img, /name, public Item.name | Exact browse_journal_images selector for art. Stored name is editable. Display name follows PF2e. | Identity name only |
| Level, Rarity, Traits | level.value, traits.rarity, traits.value | Integer, rarity and configured weapon trait codes. Read transformed values separately. | Physical and trait source |
| Quantity, Hands | quantity, usage.value | 1–999,999 except backpacks. Four usage codes map to 0, 1, 1+, 2. | Physical |
| Bulk, Size | bulk.value, size | 0, 0.1, integers 1–50. Size picker omits sm. A stack group determines Bulk. | Physical |
| Price | price.value, price.per | Denominations change independently. Weapon sidebar preserves the existing price basis. Read adjusted unit price independently of quantity. | Physical |
| Category, Group, Base, Range | category, group, baseItem, range | Group/base/range support contextual blanks. Final group and traits constrain range. Transitions that would discard stored ammunition or switch weapon mode are rejected. | Attack and physical |
| Material and grade | material.type, material.grade | Both null or a pair in the weapon valuation table. Bombs hide the panel. | Physical |
| Potency, Striking | runes.potency, runes.striking | 0–4. Grade and automatic bonus progression affect availability. | Source |
| Property Rune (ordinal), Specific Magic Weapon | runes.property, specific | Capacity uses current potency/material, prospective changes, grade, ABP and owner. Specific snapshots source material and runes, locks property slots, retains its baseline through fundamental upgrades and limits material choices. | Source codes and baseline only |
| Base damage | damage.dice, damage.die, damage.damageType | Nullable die, no bleed as base type. Striking can change displayed dice. Preserve modifier. | Damage |
| Splash, Persistent | splashDamage.value, damage.persistent.{number,faces,type} | Flat persistent has null faces. Null record clears it. Bleed is an eligible persistent type. | Damage |
| Other Tags | traits.otherTags | Separate weapon tag vocabulary. Implement requires one-handed usage. | Traits |
| Publication | publication.{title,authors,license,remaster} | Text, text, OGL/ORC, strict boolean. | Publication |
| True description | description.value | Plain prose input, escaped on persistence. Read exact stored text in bounded fragments. | Description |
| Identification, unidentified name and description | identification.status, identification.unidentified.name, identification.unidentified.data.description.value | Identified/unidentified. Independent edits preserve alternate image. The template supplies an empty default image. | Physical |

Foundry's public Document API supplies `toObject(true/false)`,
`canUserModify(user, "update", data)`, `update` and
`updateEmbeddedDocuments("Item", [update])`. Reuse canonical Item resolution
and verify exact parent/collection membership for every write. Compendiums
remain reference sources. UUID, Source ID, roll options, slug, rule elements,
flags and serialized subitems have no writable selectors. [Document API](https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html)

The pinned release defines source and transformed Item types, configuration
domains, material grades and rune data. The installed weapon Details and physical
sidebar templates explain control ordering and constraints. Accessing those
templates or a sheet instance is unnecessary in production.
[Weapon schema](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/weapon/data.ts) ·
[Weapon choices](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/weapon/values.ts) ·
[Physical schema](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/physical/data.ts) ·
[Public system configuration](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/scripts/config/index.ts) ·
[Materials](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/physical/materials.ts) ·
[Runes](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/physical/runes.ts)

The versioned sheet and document sources explain why a specific weapon may
retain a lower baseline after a fundamental upgrade, how the sheet restricts
range and material, and when PF2e clears ammunition data during an update.
The implementation uses source and transformed document serialization,
registered variant settings and public document updates. The live verifier
opens the GM's sheet as an independent check.
[Weapon sheet](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/weapon/sheet.ts) ·
[Physical Item sheet](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/physical/sheet.ts) ·
[Weapon updates](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/item/weapon/document.ts) ·
[Automatic Bonus Progression](https://github.com/foundryvtt/pf2e/blob/52dfeee703b887237f5e454747bcae45b136f9af/src/module/actor/character/automatic-bonus-progression.ts)
