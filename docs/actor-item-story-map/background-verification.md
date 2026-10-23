# ITEM-background verification

Read-only evidence gathered October 22, 2026 for [ITEM-background](stories/ITEM-background.md). This records source-contract research and existing live fixtures; it does not implement the reader or prove acquired character benefits.

## Actual rulebook reads

The GM-private PDF tools returned the complete canonical text for each following page in one call (`offset=0`, `next_offset=null`). No snippets were substituted for page reads. Reading order and table structure remain unverified.

| Book / printed page | Physical page | Document revision SHA-256 | Characters |
| --- | --- | --- | --- |
| Player Core, 84 | 85 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` | 4868 |
| Player Core, 240 | 241 | same revision | 4131 |
| Player Core 2, 52 | 53 | `ecdb10a329949ff9bd13ffb26e60892df7daabbb3cb5e4068ec2050d92f86596` | 5295 |

Player Core p. 84 gives the ordinary background package: two boosts, a skill feat, and trained proficiency in two skills including one Lore. Duplicate background/class training at first level permits another skill. Lore choices require GM acceptance. Acolyte specifies Intelligence/Wisdom plus a free boost, Religion, Scribing Lore, and Student of the Canon. Animal Whisperer specifies Wisdom/Charisma plus a free boost, Nature, a terrain Lore choice, and Train Animal. Page 240 establishes each Lore subcategory as a separate skill. These rules do not establish the character's final choices or effective modifiers.

Player Core 2 p. 52 describes rare-background selection after group discussion. Amnesiac instead supplies three free boosts, two chosen by the player and one by the GM. Therefore the ordinary two-boost/skill-feat/Lore package must not be imposed on every background. Its empty skill/grant fields are a useful real exception, not proof of a broken record.

## Pinned schema and extraction boundary

The existing ignored `.local/pf2e-research` checkout was verified at commit `28d9d156f252d084371d994dc359509b49eadf18` (PF2e 8.6.1). The similarly named `.local/pf2e-research8.6.1` directory was absent. Files were read using immutable `git show`:

- [Background source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/background/data.ts): `boosts` is a numbered record of offered `value: AttributeString[]` and `selected: AttributeString | null`; `trainedSkills.value` is `SkillSlug[]`; `trainedSkills.lore` is `string[]`; no background level is defined.
- [ABC source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts): `items` is a keyed record with `uuid`, `img`, `name`, `level`. These are references, not acquired embedded Items. Keys identify source paths, not documents. Level is a nonnegative integer in the field schema.
- [Static template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json): two default boost slots have empty offered arrays; `items={}` and both training arrays default empty. The static slots omit `selected`, despite the TypeScript source interface. Live selected source also omits it on ordinary unselected slots. Preserve omission separately from explicit null; do not manufacture a selected value or infer completed choices.

Grounded Docs `foundry-vtt` version 14 was located, and its official CompendiumCollection search verified public `getIndex({fields?})` and `getDocument(id)`. A direct official DataModel page read verified public [`toObject(source=true)`](https://foundryvtt.com/api/v14/classes/foundry.abstract.DataModel.html#toObject), which copies underlying source rather than transformed values. These public APIs support extraction; they do not authorize PF2e prepared members or establish compatibility beyond the tested runtime. [Compendium API](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html#getDocument).

## Existing live fixtures

Native MCP `execute_javascript` worked against the existing GM development browser: Foundry **14.369**, PF2e **8.6.1**. All 26 Item-pack indexes were inspected by exact `type === 'background'`; only `pf2e.backgrounds` contributed, with **540** background entries (540 total entries in that pack). World background Items: **0**. Backgrounds owned by scoped world `character`/`npc`/`familiar` Actors: **0**. Scoped actors were 172 NPCs, zero characters and zero familiars. Counts exclude unsupported actor types, scene synthetic actors and Items embedded in compendium Actors; they are not global absence claims.

Three selected definitions were hydrated without importing them. Public compendium UUIDs below identify content, not private campaign records.

| Definition / UUID | Offered boosts and selection source | Training source | ABC grant source |
| --- | --- | --- | --- |
| Acolyte / `Compendium.pf2e.backgrounds.Item.CAjQrHZZbALE7Qjy` | slot 0 `int,wis`; slot 1 all six; `selected` absent in both | `religion`; Lore `Scribing Lore` | key `1v9gz`, Student of the Canon, level 1, `Compendium.pf2e.feats-srd.Item.x7EMZNMavris2aHY` |
| Animal Whisperer / `Compendium.pf2e.backgrounds.Item.5RGLAPi5sLykRcmm` | slot 0 `cha,wis`; slot 1 all six; `selected` absent in both | `nature`; Lore array empty | key `e036p`, Train Animal, level 1, `Compendium.pf2e.feats-srd.Item.nowEaHgIyij7im8F` |
| Amnesiac / `Compendium.pf2e.backgrounds.Item.0ZfBP7Tp2P3WN7Dp` | slots 0,1,2 all six; selected absent in 0,1 and explicit null in 2 | both arrays empty | empty object |

All-six means the exact stored sequence `cha,con,dex,int,str,wis`. Acolyte and Animal Whisperer publication metadata identified Player Core / ORC / remaster; Amnesiac identified Player Core 2 / ORC / remaster. The two explicit grant UUIDs were resolved asynchronously: both returned the expected same-UUID named `feat` definition. Resolving a definition does not prove an owned grant exists.

Animal Whisperer's complete description retained a terrain Lore choice while the structured Lore array was empty. Thus an empty structured array must not become “no Lore benefit”; retain the description and report the unrepresented choice explicitly. Do not invent a selected Lore document from suggested examples. The ignored reproducible selector is `.local/background-selector.js`; it checks the system ID and uses source data, public collection/index/document APIs and async UUID resolution only.

## Contract consequences and remaining gates

Source reading can expose numbered boost offers, each selection's present/absent/null state, stored skill slugs/Lore strings and named grant references with source-path provenance. It must preserve arbitrary slot counts and empty objects/arrays. Neither book text nor a compendium offer establishes a character's final training, chosen boosts, actual granted feat, duplicate-training substitution, or effective statistic.

Owned-character verification remains blocked by fixture absence: no existing populated character/familiar or owned background was available. Do not claim live success for acquisition joins, feat/Lore deduplication, actor source-versus-current choice behavior, duplicate training handling, synthetic-token identity, or a dangling owned grant. Deterministic fixtures can cover these source cases later; they cannot replace a live acquisition check. No new worlds, actors, Items, grants, settings or gameplay writes were made. No tests of a new background reader were run because none was implemented. v13, other PF2e releases and future Foundry builds remain unverified.


## Production source checkpoint

Actual authenticated MCP consumed every source/description page of the three
selected compendium backgrounds. Boost offer lists, absent versus explicit-null
selections, trained skill/Lore arrays and keyed feature metadata matched exact
stored source. Exact prose reconstructed to source hashes. Two immediate feat
references resolved and canonical identity follow-ups passed; the rare empty
feature map retained an explicit empty scope. Complete source fingerprints
remained unchanged. No target source, feature acquisition or Actor mutation
occurred.

Four helper tests, five shared-reader tests and six Python tests cover
world/pack/token identities, unknown codes and source presence, escaped keys,
repeated definition targets, unsupported/missing/denied links, bounded resolution,
stale source/target/permission changes and actual paginated cross-language DTOs.
The full suites pass:281 Python tests (one skipped),341 JavaScript tests.

This proves the source/definition checkpoint, not the acquired-item acceptance.
CORE-build still needs to demonstrate one actual owned Lore/feat with multiple
proven contributors and no fabricated grants, plus duplicate-training handling
within its stated scope. ITEM-background stays In progress until that acceptance
is verified. The absence of a populated existing character remains a live gap;
no new world or game writes were introduced for this checkpoint.
