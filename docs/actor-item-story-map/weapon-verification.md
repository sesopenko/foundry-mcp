# Weapon source verification

PF2e-specific baseline: Foundry **14.369**, PF2e **8.6.1**. This records
read-only evidence for ITEM-weapon; it does not establish effective Strike
statistics or completion of the story.

## Actual rulebook evidence

`list_pdf_documents` and `read_pdf_pages` read **Pathfinder 2e - Player Core
Remaster.pdf**, document `6e595a7ead90468c99a4f11aa9bac6f8`, immutable revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.

| Printed label | Physical PDF page | Total characters | Continuation | Interpretation |
| --- | --- | --- | --- | --- |
| 275 | 276 | 4956 | `next_offset: null` | Weapons supply damage dice and traits; attack/damage rolls additionally depend on user attributes, proficiency, bonuses and penalties. Unarmed attacks can use weapon groups and traits but are not weapons under the rules. |
| 418 | 419 | 2815 | `next_offset: null` | Strike is an action with the attack trait using a wielded weapon or unarmed attack. Its attack check and damage are calculated statistics, distinct from an inventory Item's stored source. |

Both reads used `offset: 0`, `max_characters: 8000` and returned the entire
canonical page. Extraction warns that reading order and table structure are
unverified; no table arithmetic or column pairing was inferred. A Foundry
`weapon` Item category can therefore represent an unarmed attack without
asserting that it is a rulebook weapon. Authored dice, range and rune codes must
not be advertised as a complete user-specific Strike or final damage roll.

## Existing runtime source fixtures

Read-only `execute_javascript` probes inspected public document relationships
and `toObject(true)` on the existing authenticated GM development world.
Counts below are observations of available fixtures, not global schema claims.
Serialized source snapshots were equal before and after inspection. No document
was created, updated, imported or deleted.

- World-level weapon Items: **0**.
- Weapons owned by supported world Actors: **61**, all owned by NPCs; none by
  character or familiar Actors.
- Weapons reached through scene TokenDocument Actors: **406** occurrences,
  **18 linked**, **388 synthetic**, all NPC-owned. These are token occurrences,
  not distinct base Actor or Item counts.

For the 61 world-Actor-owned weapon sources:

| Path | Observed source shapes |
| --- | --- |
| `/system/range` | 44 null, 17 numeric |
| `/system/ammo` | 50 null, 11 objects |
| `/system/damage/persistent` | 58 null, 3 objects |
| `/system/specific` | 60 null, 1 object |
| `/system/meleeUsage` | 61 missing |
| `/system/traits/toggles` | 61 missing |
| `/system/selectedAmmoId` | 61 missing |
| `/system/reload/consume` | 61 missing; not a selected weapon source schema field |

For the 406 token-Actor weapon occurrences, `maxRange`, `attribute`,
`graspingAppendage`, `selectedAmmoId`, `meleeUsage` and `traits.toggles` were
missing in every source; `expend` was null in 291 and numeric in 115;
`damage.persistent` was null in 400 and an object in 6. No own-undefined value
was observed for the inspected optional paths. Missing/own-undefined/null
handling still requires deterministic tests because live absence cannot prove
all allowed source shapes.

## Selected compendium hydration

The readable existing `pf2e.equipment-srd` Item pack had **1021 weapon index
entries**. Its index was requested explicitly with these additional fields:
`type`, `system.ammo`, `system.damage.persistent`, `system.meleeUsage`,
`system.specific`, and `system.range`. One matching entry per characteristic was
then individually resolved through public `foundry.utils.fromUuid` using the
selected pack's public `getUuid`. No bulk document loading or importing was
used. Index values selected candidates; all following shapes came from hydrated
`toObject(true)` sources, not prepared data.

- Combination sample: numeric range; ammo object with string baseType, false
  builtIn and numeric capacity; null persistent damage; `meleeUsage` with
  damage die/type, group and trait strings; null specific.
- Ammunition sample: numeric range; ammo object with string baseType, false
  builtIn and **null capacity**; null persistent damage and specific.
- Persistent damage sample: numeric range; null ammo; persistent damage object
  with numeric faces/number and damage-type string; null specific.
- Specific weapon sample: null range and ammo; null persistent damage; specific
  baseline material with null grade/type and rune potency/striking integers plus
  property rune string array.

A reusable dynamic selection pattern avoids hardcoded fixture IDs:

```js
const pack = game.packs.get('pf2e.equipment-srd');
const index = await pack.getIndex({fields: [
  'type', 'system.ammo', 'system.damage.persistent',
  'system.meleeUsage', 'system.specific', 'system.range'
]});
const weapons = index.filter(entry => entry.type === 'weapon');
const select = predicate => {
  const entry = weapons.find(predicate);
  return entry ? pack.getUuid(entry._id) : null;
};
const selectors = {
  combination: select(entry => entry.system?.meleeUsage),
  ammo: select(entry => entry.system?.ammo),
  persistent: select(entry => entry.system?.damage?.persistent),
  specific: select(entry => entry.system?.specific)
};
```

These observations support selected persisted-source handling only. They do not
verify a prepared modifier/Strike API, rune application, ammunition consumption,
combination-mode activation, damage application, or character/familiar behavior.

## Actual weapon reader verification

Authenticated MCP consumed all bounded source pages for six selected examples:
NPC-owned melee/ranged sources plus compendium ammunition, persistent-damage,
combination-melee-usage and specific-magic weapon candidates. Source range,
category and damage type matched persisted values; all returned source paths were
unique across shared physical and weapon records. Effective sections stayed
unsupported and selected world/owned source fingerprints remained unchanged.
Standalone world weapons, populated character/familiar owners and selected
ammunition links remain live gaps; deterministic fixtures cover source shapes,
serialized attachments and exact description continuation. These checks do not
establish a complete effective Strike interface or alternate-use calculations.
