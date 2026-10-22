# Spell selected-source fields

PF2e-specific, audited against [SpellSystemSource 8.6.1](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts). The selector uses detached `toObject(true)` source, never computed variants, prepared cast state, or formula evaluation.

| Source paths under `system` | Interpretation |
| --- | --- |
| `level.value` | Base spell rank, never a cast or slot rank |
| `traits.{value,traditions,otherTags,rarity}` | Ordered codes preserved, including unknown codes |
| `time.value`, `requirements`, `cost.value`, `range.value`, `target.value` | Exact authored text; no action-count parsing |
| `area.{type,value,details}`, `duration.{value,sustained}` | Definition, including explicit null area |
| `damage.<key>.{formula,kinds,applyMod,type,category,materials}` | Ordered damage/healing kinds and unevaluated formulas; no effective damage |
| `defense.{passive.statistic,save.statistic,save.basic}`, `counteraction` | Authored defense and counteraction configuration |
| `ritual.{primary.check,secondary.checks,secondary.casters}` | Authored ritual definition, not execution |
| `location.{value,signature,heightenedLevel,autoHeightenLevel,uses.value,uses.max}` | Local casting-entry claim and stored configuration; no availability, automatic heightening or resource expenditure inferred |
| `heightening.{type,interval,area,damage}` | Interval definition, never applied |
| `heightening.levels.<1..10>` | Recursively selected partial source patches |
| `overlays.<key>.{name,overlayType,sort,system}` | Named stored variant patches; nested overlay maps excluded from overlay system |
| `slug`, `publication.{title,authors,license,remaster}` | Source metadata |

Fixed layers and overlay systems use the same explicit field allowlist as the root. Partial patches omit absent members, retain explicit empty patches, and may contain partial heightening objects without a discriminator. Keys use canonical JSON Pointer escaping; numeric heightening keys must be 1 through 10. Dynamic damage and overlay keys are retained without pretending they are document IDs.

Null, empty arrays, empty maps, absent members and optional explicit `undefined` remain distinct according to the declared schema; no defaults are inserted. Invalid selected values reject with their source path. Traversal rejects nesting beyond 12 or more than 12,000 selected descriptors rather than silently truncating or executing a patch. Description selection is separate: exact root and nested `description.value` prose is returned only for explicit description reads and subject to shared text/byte continuation. No arbitrary system objects, rules, flags, migration records, prepared state or descriptions are included in source fields.
