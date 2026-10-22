# Spell book and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. These are rulebook reads and persisted-source observations, not proof of effective casting, availability, variant application or resource expenditure.

## Complete rulebook reads

Read complete canonical text through `read_pdf_pages`, pinned to Player Core revision `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`. All four pages returned `next_offset=null`. Reading order and table structure remain unverified; conclusions below follow prose rather than inferred table associations.

| Printed / physical page | Characters |
| --- | --- |
| 297 / 298 | 5261 |
| 298 / 299 | 5706 |
| 299 / 300 | 5273 |
| 303 / 304 | 5768 |

Player Core distinguishes a spell's listed rank, the rank at which it is known/prepared/cast, and the rank of the slot spent. Prepared casters can prepare higher-rank versions. Spontaneous casters normally need to know the desired rank, with exceptions such as signature spells. They can spend a higher-rank slot without heightening a lower-rank known spell. A reader must therefore not infer cast rank or heightened benefits from slot rank alone.

Cantrips and focus spells have their own automatic-heightening rules and resource distinctions; a stored base rank is not a computed effective rank. Innate spells have source-specific frequency and do not consume ordinary spell slots. Their granting ability can supply a higher rank without making general innate heightening available. Traditions listed on a spell definition do not by themselves establish the tradition of a particular caster's spell.

Casting time can range from actions to hours. Preserve its source text, including variable action counts; do not turn arbitrary time prose into a single guessed action count. The spell format separately describes traits, traditions, costs/requirements, range/area/targets, defense, duration, effects and heightened entries. Rank-specific heightening and cumulative interval heightening are distinct. Description remains necessary for effects and exceptions that structured fields do not encode. Reading neither rolls a spell attack nor establishes its target, modifiers, legality or outcome.

## Schema boundary

Pinned [SpellSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts) declares `level.value`, traits/traditions, string casting time, requirements/cost/range/target, nullable area/defense, duration value/sustained, keyed damage components, optional heightening/overlays, nullable ritual and casting location. Base `level.value` maps to base rank. Stored `location.heightenedLevel`, `autoHeightenLevel`, `signature` and innate `uses` remain distinct source configuration rather than verified casting results.

Damage components retain formula, optional damage/healing kinds, optional applyMod, damage type, category and material effects. A component can explicitly support both damage and healing; neither its formula nor damage type replaces the kinds array. Do not roll formulas or infer an omitted kinds array.

Interval heightening retains interval, area increment and keyed damage increments. Fixed heightening stores rank-keyed partial spell changes. Overlays are keyed override definitions with sort/name and partial system changes. Their keys are source identifiers, not Foundry document UUIDs. Nested fields need provenance on the actual spell UUID and their exact source paths. Do not instantiate variants, merge patches into effective source, run preparation methods or dump arbitrary nested objects.

Installed examples demonstrate that partial changes can be deeply partial: an overlay damage entry can contain only `category` and `formula`, and its heightening can contain only `damage`, without `type`, `interval` or `area`. Fixed-rank damage patches can omit `kinds`. Preserve these absent leaves; applying full-spell required-field assumptions to a patch would reject genuine stored spells.

`location.value` is an owner-local casting-entry claim. Resolve only through the actual owning Actor's Item collection, retaining actual identity and permission boundaries. Unassigned, missing, denied and unsupported targets must remain distinct. Pack spells commonly have a null location; a pack spell does not acquire a fictional actor or entry. No source field establishes prepared-slot membership, remaining slots or castability without CORE-casting.

## Read-only existing runtime

Used public world/scene collections, token `actor`, Item `toObject(true)`, pack `getIndex` and selected `getDocument`. No document writes, imports, activation, rolling, enrichment, chat or variant/preparation APIs were used.

There are **zero** standalone world spells, **791** spells owned by supported world Actors (all NPC), and **2758** scene-token spell occurrences. Token occurrences can repeat linked documents and are not distinct Item counts. Twenty owned spells are unassigned. None of the nonempty world-owned location claims referred to a missing Item. Character/familiar and standalone world spell cases are unavailable live; missing/denied/wrong-type entry claims need deterministic coverage rather than manufactured world data.

Selected only `pf2e.spells-srd`: **2017** spell index rows. Bounded predicates found 50 variable-time rows, 279 minute/hour/day rows, 38 with a healing-kind component, 472 interval-heightening rows, 139 fixed-heightening rows, 72 nonempty overlay maps and 167 non-null ritual records. All 2017 index rows had no assigned location. These counts describe this installed pack and these predicates; they do not establish exhaustive rules categories.

Selected hydrated examples retained:

| Case | Actual persisted example |
| --- | --- |
| Variable casting time | `1 or 2`, base rank 1 |
| Long casting time | `1 minute`, base rank 3 |
| Healing component | `7d8`, kinds `[healing]`, base rank 7 |
| Interval heightening | base `4d8` damage, interval source retained independently |
| Fixed heightening | base rank 7, separate `4d8` piercing and `4d4` void components; rank-9 patches `5d8` and `5d4` |
| Overlays | base `1d8` sonic, two override definitions; one empty system patch and one partial damage/heightening patch |
| Ritual | `2 days`, primary Arcana or Occultism (expert), secondary Deception with one caster |
| Mixed component | `3d8` vitality, kinds `[damage, healing]` |

Four selected fixed/overlay/ritual/mixed samples had exactly equal complete serialized source before and after inspection. This is a read-only source inspection result; actual MCP reader fingerprints and acceptance checks must be recorded separately after integration.

Reproducible selection uses `pack.getIndex({fields:["type","system.time","system.damage","system.heightening","system.overlays","system.ritual","system.location"]})`, filters `type === "spell"`, then hydrates only the first match per predicate with `getDocument(row._id)`:

```javascript
const predicates = {
  variable: r => /or|to/.test(r.system?.time?.value ?? ""),
  long: r => /minute|hour|day/.test(r.system?.time?.value ?? ""),
  healing: r => Object.values(r.system?.damage ?? {}).some(d => d.kinds?.includes("healing")),
  mixed: r => Object.values(r.system?.damage ?? {}).some(d =>
    d.kinds?.includes("damage") && d.kinds?.includes("healing")),
  interval: r => r.system?.heightening?.type === "interval",
  fixed: r => r.system?.heightening?.type === "fixed",
  overlays: r => Object.keys(r.system?.overlays ?? {}).length > 0,
  ritual: r => r.system?.ritual != null,
  unassigned: r => !r.system?.location?.value
};
```

Index absence is only a candidate signal. Assert actual hydrated `toObject(true)` fields before reporting a source absence or selected case.

## Remaining acceptance gates

Verify actual bounded `read_item` raw/mapped/provenance, unique source paths, exact description reconstruction, context/identity, immediate location relationship results and unchanged source fingerprints. Exercise malformed values, partial patches, null/empty/absent distinctions, permissions, stale cursors, unsupported systems and unavailable ownership contexts deterministically. Computed variants/cast ranks remain gated on CORE-casting; source reading must explicitly exclude preparation, slot availability, ritual execution, flexible casting and item-casting legality. This document alone does not close ITEM-spell.

## Actual spell-reader acceptance

Authenticated MCP read nine selected spells: seven selected pack cases and two
owned NPC cases (assigned and unassigned). All source pages were consumed;
exact base rank, text casting time, component formula and damage/healing kinds
matched persisted source. Both interval and fixed heightening, override overlays
and ritual source were read without applying them. Source paths were unique.
Exact root descriptions reconstructed to matching SHA256 fingerprints; all nine
complete source fingerprints were unchanged after reading. Effective remained
unsupported. The assigned entry resolved to the actual owner's Item and a
follow-up identity read confirmed spellcastingEntry; unassigned remained missing.

Focused deterministic tests additionally cover separate fixed/overlay prose,
large Unicode text continuation, deeply partial and empty patches, malformed
source, stale continuations, non-PF2e rejection, denied/missing/wrong-type links,
and linked/synthetic token selectors. No target entry source is read during
relationship resolution. Full regression suites passed: 228 Python tests (one skipped) and 245 JavaScript
tests. Fresh MCP discovery descriptions and schemas were checked before committing. No casting, variant application, rolls, imports,
chat or document writes occur. Live world, character and familiar spell fixtures
remain unavailable; effective casting and resource semantics remain CORE-casting.
