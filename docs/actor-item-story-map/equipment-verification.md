# Equipment book and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. These are rulebook and read-only persisted-source observations; they do not prove a production equipment reader or active magical benefits.

## Complete rulebook reads

Read complete canonical text with `read_pdf_pages`; every page returned `next_offset=null`. Extraction warns that reading order and table structure are unverified. Conclusions below use prose without reconstructing table associations.

| Book | Printed / physical page | Characters | Revision |
| --- | --- | --- | --- |
| GM Core | 219 / 220 | 5038 | `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` |
| GM Core | 220 / 221 | 5044 | same revision |
| GM Core | 221 / 222 | 5872 | same revision |
| Player Core | 267 / 268 | 5156 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |

GM Core distinguishes constant abilities from activation. A constant ability can still require wearing, wielding or investment. Invested items require investment for their magical effects and activation, while mundane physical benefits remain available without it. Investment has a daily limit and ends on removal; the persisted Item's investment flag alone does not establish the actor's daily history or every requirement.

Permanent items often place Activate entries within description paragraphs. Those entries can carry action costs, activation traits, frequency, trigger and requirements. Absence of a structured activation field therefore does not establish absence of an ability. Frequency is an item limit distinct from costs; transferring or reinvesting the item does not reset it. Manipulate, spellcasting, Sustain and Dismiss requirements are separate context-dependent rules. Preserve the original description; do not infer that an owned item is usable, active or has remaining activations.

Player Core distinguishes held, worn and stowed. Holding in insufficient hands differs from wielding; drawing or changing grip can require actions. Usage describes intended use, while stored carry state describes current source configuration. Neither proves an effect is active. GM Core also notes item level is suitability and crafting information, rather than a general prohibition on using higher-level items.

## Schema boundary

The pinned [EquipmentSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/equipment/data.ts) extends investable physical source, supplies equipment traits, `usage.value`, and serialized physical `subitems`. It does **not** declare a separate structured equipment activation/frequency field. Keep exact bounded `description.value` available for prose abilities, alongside shared physical carry, investment and usage fields. Do not parse prose into invented current activation resources.

Traits, rarity, tags and publication are selected persisted metadata. An invested trait and `equipped.invested` are different facts. Serialized attachments may have local identifiers without independent document identity; retain selected metadata and source paths without fabricated UUIDs or automatic rules application.

## Read-only inventory and selected pack hydration

Used public world/scene collections, token `actor`, Item `toObject(true)`, pack `getIndex` and selected `getDocument`. No document writes, imports, activation, rolls, chat, enrichment or sheet preparation were invoked. There are **zero** standalone world equipment Items, **29** equipment Items on supported world Actors, and **169** scene-token equipment occurrences. These token counts can repeat linked Items and do not represent unique Items. Existing owned samples are NPC Items; character/familiar equipment remains unavailable live.

Owned carry states were **27 worn / 2 held**. All **29** stored `equipped.invested` values were **null**; none were true or false. Null is preserved as source rather than interpreted as explicitly uninvested. Three owned descriptions contain case-insensitive `activate`; this is a candidate selector, not a semantic count of verified abilities. No owned equipment had nonempty serialized subitems.

Selected only `pf2e.equipment-srd`: its index contains **2410 equipment rows**, **973** with the invested trait, **1649** whose description contains case-insensitive `activate`, and **zero** nonempty serialized subitems. These are installed-pack observations, not all published equipment or an exhaustive activation classification.

Hydrated two bounded selected pack documents: the first matching invested trait plus Activate prose, and the first without the invested trait. The former had usage `wornarmbands`, source carry `worn`, investment null, traits force/invested/magical, and a **617-character** description containing Activate. The latter had usage `worn`, investment null, magical trait without invested, and a **518-character** description without the substring. Both lacked an own structured `activation` field; serialized subitems were empty. Exact serialized source comparisons before and after inspection matched for both.

An owned NPC prose candidate had usage `held-in-two-hands` while source carry was `worn`, investment null, magical trait, and a **656-character** description. It also lacked a structured activation field. Preserve usage and current carry independently rather than normalizing them into an asserted wielded/active state.

Reproducible bounded pack selection:

```javascript
const pack = game.packs.get("pf2e.equipment-srd");
const rows = Array.from(await pack.getIndex({fields: [
  "type", "system.traits.value", "system.description.value"
]})).filter(row => row.type === "equipment");
const candidates = [
  rows.find(row => (row.system?.traits?.value ?? []).includes("invested") &&
    /activate/i.test(row.system?.description?.value ?? "")),
  rows.find(row => !(row.system?.traits?.value ?? []).includes("invested"))
].filter(Boolean);
for (const row of candidates) {
  const document = await pack.getDocument(row._id);
  const source = document.toObject(true);
  // Read only selected source; retain actual document UUID and pack context.
}
```

## Reader verification still required

Verify actual `read_item` source/mapped provenance, exact bounded description continuation, owner/token identity, stale/denied/malformed/system boundaries and unchanged fingerprints. Existing null investment samples cannot prove explicit false investment handling; use deterministic fixtures for uninvested mundane benefits, true investment, large Unicode prose, nonempty subitems and world/character/familiar contexts. Effective statistics, activated effects, frequency expenditure, daily investment history and automatic rule application remain excluded advanced capabilities.

## Actual equipment reader acceptance

Authenticated MCP consumed every source page for one owned NPC and two selected
compendium equipment Items. Exact usage, investment null and ordered traits
matched persisted source; shared physical and equipment paths stayed unique.
Explicit descriptions reconstructed to identical SHA256 fingerprints, including
prose-only Activate entries. All three complete source fingerprints were unchanged
after reads. No gameplay operation occurred. Effective sections stayed unsupported.
Deterministic tests verify large Unicode description continuation, explicit false
investment without erasing mundane source, attachment metadata without fabricated
UUIDs, malformed values, stale continuations, permissions and non-PF2e rejection.
The inherited canonical identity boundary covers world, owner, pack and token
contexts; no standalone world or character/familiar equipment is available live.
Full regression suites passed: 219 Python tests (one skipped) and 223 JavaScript
tests. Discovery descriptions and input schemas were inspected through a fresh
MCP client. No active benefit or activation-resource calculation is advertised.
