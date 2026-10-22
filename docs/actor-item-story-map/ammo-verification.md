# Ammunition source verification

PF2e-specific evidence for ITEM-ammo, collected read-only on October 22, 2026.
Runtime: Foundry **14.369**, PF2e **8.6.1**. Runtime observations illustrate
available fixtures; the pinned schema establishes selected field contracts.

## Actual rulebook pages

The GM-private PDF MCP library returned the following full canonical pages,
each with `offset: 0`, `max_characters: 8000`, and `next_offset: null`:

| Book | Printed label | Physical page | Characters | Interpretation |
| --- | --- | --- | --- | --- |
| GM Core Remaster | 220 | 221 | 5044 | Activation has its own action and trait requirements; limited activations are distinct from activation costs. Ammunition appears among magical consumables. |
| GM Core Remaster | 221 | 222 | 5872 | The Ammunition entry identifies available ammunition types. Usage describes how an item is held, worn, or attached. Consumables are normally destroyed after activation; their descriptions can specify exceptions. |
| Player Core Remaster | 267 | 268 | 5156 | Held, worn, and stowed inventory have different access requirements; carrying an item does not establish that it is wielded or ready to use. |
| Player Core Remaster | 275 | 276 | 4956 | Attack and damage results require user modifiers, proficiency, bonuses, and penalties beyond an inventory Item's source. |

GM Core document `c69e31968bda411c8940ea7d48b8786e`, revision
`8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e`;
Player Core document `6e595a7ead90468c99a4f11aa9bac6f8`, revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
The extraction warns that reading order and table structure are unverified.
No column pairing or table arithmetic was inferred.

These pages support displaying stock, stored uses and ammunition-type codes
with their provenance. They do not make `uses.value` an attack count or prove
that ammunition is loaded, compatible, accessible, activated, or applied to a
Strike. `craftableAs` is stored crafting configuration, not a runtime weapon
compatibility decision. A weapon's selected stack must remain an explicit
relationship; other carried stacks do not automatically contribute effects.

## Existing world and token sources

Read-only `execute_javascript` traversed public world collections, Scene
TokenDocuments and their Actor/Item relationships. Selected source values came
from `toObject(true)`; no prepared fields or sheet state were used.

- World-level ammunition Items: **0**.
- Ammunition owned by supported world Actors: **11**, all NPC-owned; **8**
  arrows and **3** bolts. Character and familiar owned ammunition: **0**.
- Ammunition through supported Scene token Actors: **98 occurrences**, **6
  linked** and **92 synthetic**; **55** arrows and **43** bolts. These are
  occurrences, not unique base Item counts.
- Every observed ammunition source had `craftableAs: null` and
  `uses: {value: 1, max: 1, autoDestroy: true}`. No inspected token weapon source
  had its own `selectedAmmoId` property.
- Serialized source snapshots were unchanged before and after inspection.
  No document was imported, created, updated, deleted, activated or rolled.

## Selected pack hydration

The existing readable `pf2e.equipment-srd` Item pack index contained **216**
ammunition entries: `craftableAs` was **null in 53**, **empty in 106**, and
**populated in 57**. Index fields selected candidates only. One per shape was
individually hydrated through public `pack.getUuid` and
`foundry.utils.fromUuid`; no bulk document loading was used.

| Selected source shape | Hydrated sample | `baseItem` | `craftableAs` |
| --- | --- | --- | --- |
| Null | Rounds (Three-peaked Tree) | `rounds-three-peaked-tree` | `null` |
| Empty | Godrending Ammunition | `null` | `[]` |
| Populated | Magekiller Bullet | `null` | `["rounds", "sling-bullets"]` |

All three hydrated samples had stored uses 1/1 and autoDestroy true. Their
serialized source snapshots remained unchanged. This does not prove every
indexed candidate's hydrated shape or a runtime compatibility/application API.

Dynamic selection, without fixture IDs:

```js
const pack = game.packs.get('pf2e.equipment-srd');
const index = await pack.getIndex({fields: [
  'type', 'system.baseItem', 'system.craftableAs', 'system.uses'
]});
const ammo = index.filter(entry => entry.type === 'ammo');
const choose = predicate => {
  const entry = ammo.find(predicate);
  return entry ? pack.getUuid(entry._id) : null;
};
const selectors = {
  nullCrafting: choose(entry => entry.system?.craftableAs === null),
  emptyCrafting: choose(entry => Array.isArray(entry.system?.craftableAs)
    && entry.system.craftableAs.length === 0),
  populatedCrafting: choose(entry => Array.isArray(entry.system?.craftableAs)
    && entry.system.craftableAs.length > 0)
};
```

Live gaps include standalone world ammunition, populated character/familiar
owners, missing/own-undefined fields, nondefault uses configuration and populated
weapon selections. Deterministic tests must cover these boundaries. This audit
does not by itself establish that the production ammunition reader is delivered;
its actual MCP response, bounds, provenance and permission behavior require
separate integration verification.

## Actual reader acceptance

Authenticated MCP consumed all bounded source pages for five selected samples:
two NPC-owned stacks and compendium null/empty/populated craftableAs examples.
Stored uses and crafting categories matched source; shared physical and ammo
paths were unique. Effective sections stayed unsupported and persisted source
fingerprints remained unchanged. Deterministic checks cover standalone source,
exact descriptions, stale/malformed/denied/system boundaries, and two carried
stacks with only the explicitly selected stack followed. Existing live weapons
have no populated selectedAmmoId; linked/synthetic selected-stack behavior has
prior deterministic weapon-reader evidence only. No ammo effect is applied and
counts do not prove that an attack can be made.
