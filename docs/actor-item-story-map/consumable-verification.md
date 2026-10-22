# Consumable book and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. This records rulebook reads and persisted-source observations. It does not establish complete contained-spell mapping, activation legality or resource expenditure.

## Complete rulebook reads

Read complete canonical text through `read_pdf_pages`; all three pages returned `next_offset=null`. Reading order and table structure remain unverified, so these conclusions rely on prose rather than inferred table associations.

| Book | Printed / physical page | Characters | Revision |
| --- | --- | --- | --- |
| GM Core | 220 / 221 | 5044 | `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` |
| GM Core | 221 / 222 | 5872 | same revision |
| Player Core | 303 / 304 | 5768 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |

GM Core distinguishes activation actions and traits, requirements, triggers and limited daily activations. A daily frequency limit is independent of activation costs and does not refresh merely because someone else acquires or invests the item. An item that replicates a spell can require the spell's casting actions and a spellcasting class feature; reading a stored spell does not establish those requirements are met. Manipulate activations also depend on wielding or touching the item. Consumable activation is not necessarily magical.

The consumable trait normally means one use, with destruction after activation unless a specific exception applies. This rule does not justify equating a stack's stored quantity with one object's remaining uses or a daily frequency. Preserve the actual persisted values independently, including reusable consumable-type Items such as wands and their `autoDestroy=false` configuration. Do not consume or destroy anything during reading.

Player Core's spell format distinguishes spell rank, traditions, casting time and costs, range/area/targets, defense, duration, description and heightened effects. A spell source is therefore a separate interpretation dependency, not an arbitrary object that can be passed off as a fully mapped spell. The specific spell definition and item activation rules remain relevant; a damage/healing formula alone does not establish every outcome or castability.

## Schema boundary

Pinned [ConsumableSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/consumable/data.ts) extends shared physical source with `category`, `uses.value/max/autoDestroy`, nullable `damage`, nullable `spell`, `usage.value` and consumable traits/tags. `damage` is a formula plus damage type and a distinct damage/healing kind; preserve the kind without rolling or inferring it solely from damage type. The source has no independent structured frequency field. Exact bounded description remains necessary for prose activation details.

`spell` is a serialized `SpellSource`, not proof of a separately addressable Item document. An internal `_id` does not authorize inventing a Foundry UUID. Any selected nested fields must retain provenance under `/system/spell/...` on the consumable's actual UUID. Preserve base spell rank separately from an optional stored heightened rank; do not calculate a cast rank or apply heightened effects before the spell reader's contract is verified. Raw spell source, rules, overlays, flags and description must not become an unrestricted nested dump.

## Read-only existing runtime

Used public world/scene collections, token `actor`, Item `toObject(true)`, pack `getIndex` and selected `getDocument`. No writes, imports, activation, rolling, enrichment, chat or sheet preparation occurred.

There are **zero** standalone world consumables, **25** consumables on supported world Actors, and **134** scene-token occurrences. All owned samples are NPC Items; character/familiar and standalone world consumables remain unavailable live. Token occurrences can repeat linked documents and are not unique Item counts.

Owned categories are 2 scrolls, 7 elixirs, 7 poisons, 2 potions, 5 wands, 1 drug and 1 talisman. Three have healing-kind damage, none have damage-kind damage, and 22 have null damage. Six have a non-null spell source. Five have `autoDestroy=false`. The two selected owned scrolls each have quantity 2 but per-object uses 1/1 with auto-destruction true. This directly exercises the distinction between stock and per-object use data.

Selected only `pf2e.equipment-srd`: **1724** consumable index rows, **28** healing-kind formulas, **53** damage-kind formulas and **109** explicit contained spell sources. There are **10** scroll template rows whose index data omits `spell`. Two selected template hydrations both expose an own `spell:null` in `toObject(true)`. Index omission therefore must not be reported as document-source absence. These observations describe this installed pack, not all published consumables.

Four selected, hydrated pack source cases were inspected; each serialized source matched exactly before and after inspection:

| Case | Persisted selected values |
| --- | --- |
| Empty scroll template | category scroll, quantity 1, uses 1/1, autoDestroy true, damage null, spell null; description 807 characters |
| Healing potion | formula `1d8`, kind healing, type vitality, spell null; description 309 characters |
| Damage snare | formula `3d6`, kind damage, type poison, spell null; description 658 characters |
| Contained-spell wand | autoDestroy false, damage null, nested spell type spell, base `level.value=4`, stored `location.heightenedLevel=7`; description 1345 characters |

The contained wand source includes a nested `_id`, but it is treated as source metadata without a fabricated UUID. Its distinct base and heightened values must not be collapsed. No embedded spell was instantiated or cast.

Reproducible bounded candidate selection:

```javascript
const pack = game.packs.get("pf2e.equipment-srd");
const rows = Array.from(await pack.getIndex({fields: [
  "type", "system.category", "system.damage", "system.spell", "system.uses"
]})).filter(row => row.type === "consumable");
const predicates = [
  row => row.system?.category === "scroll" && row.system?.spell == null,
  row => row.system?.damage?.kind === "healing",
  row => row.system?.damage?.kind === "damage",
  row => row.system?.spell?.type === "spell"
];
for (const predicate of predicates) {
  const candidate = rows.find(predicate);
  if (!candidate) continue; // Missing candidate does not prove no published case.
  const item = await pack.getDocument(candidate._id);
  const source = item.toObject(true);
  // Assert actual selected document fields; index omission is not source absence.
}
```

## Remaining acceptance gates

Verify actual `read_item` source/mapped provenance and continuations, null-versus-absent spell distinction, separate stock/uses, exact descriptions, owner/pack/token identity and unchanged source fingerprints. Exercise malformed values, permissions, stale continuation, non-PF2e rejection and unavailable world/character/familiar contexts deterministically. Contained spell mapping remains gated on ITEM-spell; an incomplete spell interpretation must remain explicit. Poison/scroll legality, damage outcomes, daily frequency, resource expenditure and effective actor benefits are not established by these source observations.

## Actual source-checkpoint reader verification

Authenticated MCP consumed all bounded source pages for five selected cases:
one owned NPC consumable, an empty scroll template, healing and damage formulas,
and a contained-spell wand. Exact category, quantity, per-object uses, autoDestroy,
formula/type/kind and selected spell metadata matched hydrated persisted source.
Every source path was unique; all nested spell provenance remained on the actual
consumable UUID. All five complete source fingerprints were unchanged after reads.
Source stayed partial with `contained_spell_mapping_pending`; effective state
remained unsupported. Full suites passed: 223 Python tests (one skipped) and
232 JavaScript tests. Fresh discovery exposes the source checkpoint and explains
base rank, nested-source identity and the unfinished spell mapping.

This does not close ITEM-consumable. Full contained-spell mechanics and prose
need the spell reader and shared mapping; poison/scroll castability, activation,
frequency expenditure and effective benefits remain unsupported. Standalone world
and character/familiar consumables are unavailable live; inherited deterministic
identity/permission tests cover those boundaries without manufacturing fixtures.
