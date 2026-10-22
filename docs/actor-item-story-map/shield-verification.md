# Shield book and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. These are rulebook and read-only persisted-source observations; they do not prove a production shield reader or effective shield state.

## Complete rulebook reads

Read the complete canonical text returned by `read_pdf_pages` for these pages. Each response had `next_offset=null`; no continuation was left unread. The extraction warns that reading order and table structure are unverified, so prose supports these conclusions without reconstructing table cells.

| Book | Printed / physical page | Characters | Revision |
| --- | --- | --- | --- |
| Player Core | 274 / 275 | 4561 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |
| GM Core | 232 / 233 | 2057 | `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` |
| Player Core 2 | 89 / 90 | 5545 | `ecdb10a329949ff9bd13ffb26e60892df7daabbb3cb5e4068ec2050d92f86596` |

Player Core separates a shield's properties from using it. Its AC bonus is a circumstance bonus requiring Raise a Shield, lasting until the next turn starts. Holding or owning a shield does not establish that it is raised. The Speed penalty applies while holding it regardless of raised state. Shield Block requires access through a class or feat; ownership grants no reaction. Its damage reduction uses Hardness, with remaining damage applying to the creature and shield. HP and Broken Threshold concern durability; they are not AC or proof that the shield is currently raised. Tower shield Take Cover benefits require further action and context.

Keep the books' rune wording visible rather than flattening it. Player Core's attack discussion broadly says shields cannot receive runes and distinguishes attached weapon bosses/spikes. GM Core explicitly permits **reinforcing** runes, including on specific shields, while prohibiting weapon, armor and property runes on the shield itself. Reinforcing increases are bounded by listed maximum durability values. Thus a blanket no-runes mapping would discard valid shield source. Weapon runes on an integrated weapon/attachment remain distinct from the shield's reinforcing rune.

Player Core 2's Blessed Shield is conditional class-granted reinforcement while the shield is in the champion's hands. Its granted rune scales with level; an already appropriate rune or same-level sturdy shield instead receives a Hardness increase. This is not evidence that the persisted `runes.reinforcing` field contains that benefit. Do not infer effective reinforcement, raised state, Block access, final durability or attachment attacks from the source Item alone.

## Schema boundary

The pinned [ShieldSystemSource and associated interfaces](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/shield/data.ts) declare `acBonus`, `speedPenalty`, nullable `baseItem`, nullable `grade`, `runes.reinforcing`, nullable `traits.integrated`, nullable `specific` baseline material/runes/integrated data, and serialized physical `subitems`. Source integrated weapons have weapon rune configuration and nullable selected versatile damage; prepared integrated data adds damage type/options. Source usage explicitly is not stored. HP and Hardness come from physical source.

Specific baseline and current configuration are separate paths, not additive benefits. Serialized subitems and nested integrated data are not independently resolved documents merely because they contain local identifiers. Preserve source-path provenance. Do not fabricate UUIDs, prepared damage options, usage or broken threshold from the schema or defaults.

## Read-only inventory and selected pack hydration

Used public world/scene document collections, token `actor`/`isLinked`, and `toObject(true)` only. No writes, imports, rolls, chat, enrichment, sheet access or preparation helpers were invoked. Aggregate inventory returned **zero** standalone world shields, **zero** shields on supported world character/NPC/familiar Actors, and **zero** linked/synthetic token-context shield occurrences. Consequently no live held/unheld, damaged, owner or token shield fixture is available from this inventory.

Selected only `pf2e.equipment-srd`. Its index contains **126 shield rows**, including **13** with reinforcing greater than zero, **8** with non-null integrated configuration, and **100** with non-null specific baseline. These are installed-pack counts, not a claim about all published shields. Hydrated one dynamically selected document per shape with public `getDocument`; no bulk loading/import occurred. All three were unowned pack Items (`parent=null`), and exact serialized persisted-source comparisons before/after inspection matched.

- Reinforcing sample: source rune tier **1**, separate specific baseline tier **1**, source Hardness **3**, AC bonus **2**, and HP **value 56 / max 12**. Preserve those exact authored values. A validator must not reject `value > max` as impossible or silently clamp it: source max and current durability can differ because derived reinforcement is outside this source read. This observation alone does not establish effective HP, Hardness or Broken Threshold.
- Integrated sample: reinforcing **0**, AC bonus **1**, Hardness **3**, HP **10/10**, `specific=null`, integrated weapon runes potency **0**, striking **0**, property **[]**, versatile **null**. No source usage field and zero serialized subitems. Integrated source config does not prove an exposed attack or separate document identity.
- Specific sample: reinforcing **0**, AC bonus **2**, Hardness **8**, HP **60/60**, separate baseline material type duskwood / grade standard and reinforcing **0**, baseline integrated **null**. No inference of granted/effective reinforcement follows.

Dynamic selectors for reproducing this bounded selected-pack check:

```javascript
const pack = game.packs.get("pf2e.equipment-srd");
const rows = Array.from(await pack.getIndex({fields: [
  "type", "system.runes.reinforcing", "system.traits.integrated", "system.specific"
]})).filter(row => row.type === "shield");
const candidates = [
  rows.find(row => row.system?.runes?.reinforcing > 0),
  rows.find(row => row.system?.traits?.integrated != null),
  rows.find(row => row.system?.specific != null)
].filter(Boolean);
for (const row of candidates) {
  const document = await pack.getDocument(row._id);
  const source = document.toObject(true);
  // Inspect only selected shield source; retain document.uuid and pack identity.
}
```

## Reader verification still required

This evidence does not prove production reader pagination, DTO validation, provenance, stale/denied handling, description bounds or no-write behavior across actual `read_item` calls. Verify those with focused deterministic fixtures and live selected compendium reads. Use explicit fixtures for absent/null/zero fields, owned/token context and missing subitems. Live character/familiar/NPC/world/token shields remain unavailable. Raised/current state, class-granted reinforcement, effective durability and attachment attack extraction remain gated by supported APIs and explicit runtime evidence.

## Actual shield reader acceptance

Authenticated MCP consumed all bounded source pages for three distinct
compendium shields selected for reinforcing, integrated and specific source.
Exact rune, HP/value, HP/max and Hardness matched persisted source, including
HP56/max12 without clamping. Shared physical/shield paths were unique, effective
sections stayed unsupported and each selected source fingerprint was unchanged
after reading. Existing delivered-reader regressions also passed. No owned,
world or token shields exist live; deterministic fixtures verify held-but-not-
raised presentation, permission/stale/malformed/system boundaries, exact text,
specific/integrated source and mixed physical/shield provenance. Raised state,
Shield Block eligibility, class reinforcement and generated attachment attacks
remain unsupported advanced gates; possession does not prove them.
