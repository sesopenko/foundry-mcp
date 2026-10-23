# Class definition verification

Evidence date: October 22, 2026. This record separates rulebook reading,
pinned schema evidence and read-only live observations. It does not establish
effective character statistics, advancement or future-version compatibility.

## Rulebook evidence

The private PDF MCP returned complete canonical pages with `next_offset: null`
for Player Core printed pp. 11, 19, 91 and 194 (physical pages 12, 20, 92,
195). Revision SHA-256:
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
Reading-order and table-structure warnings remain; extracted table adjacency
alone is not a verified relationship.

- Page 91 distinguishes key attribute, class HP contribution, initial training
  and class features, with later advancement part of the class definition.
- Page 194 distinguishes starting wizard features from abilities gained later.
  Its progression names are future definition references, not proof that an
  owning character has acquired them. Spellcasting details do not establish a
  selected Actor's slots, preparations or castability.
- Page 11 names the five proficiency ranks in order: untrained, trained, expert,
  master, legendary. A rank is separate from a calculated proficiency bonus or
  total check modifier. The reader must not calculate either.
- The PDF contains an unresolved discrepancy: page 91 describes the class boost
  as increasing the attribute modifier by 2; page 19 describes a normal boost
  as increasing it by 1, with partial-boost rules for higher modifiers. Preserve
  offered/selected attribute codes and source provenance; do not resolve this
  discrepancy by assumption or implement boost arithmetic.

## Pinned schema evidence

PF2e 8.6.1 commit `28d9d156f252d084371d994dc359509b49eadf18`:
[class schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/class/data.ts),
[shared rank field](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/model.ts),
[ABC feature-entry schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts).

- `keyAbility.value` contains offered attribute codes; `selected` is explicitly
  nullable. A null selection must remain null rather than choose a singleton.
- `hp` is a class contribution (schema range 4–12), not an Actor total.
- Perception, saving throws, attacks, defenses and spellcasting use integer
  `ProficiencyRankField` values 0–4. These are starting rank definitions.
- `trainedSkills.value` names training definitions; `additional` is a source
  count, not generated selected skills or a calculated Intelligence adjustment.
- The five feat/increase level arrays are independent progression definitions.
  Retain authored arrays rather than reconstructing defaults.
- `items` is keyed source data with feature name, UUID, image and level. Preserve
  key/source path and named immediate reference; keys are not document IDs.
  Reading a class must not recursively hydrate all future feature definitions.
- Class traits replace the generic trait schema: `rarity` and `otherTags` exist;
  no `traits.value` is declared. Do not import generic trait-value assumptions.
- `attacks.other.name` uses bare `new fields.StringField()` rather than explicit
  required/nonnullable/initial options. A public field-instance probe in Foundry
  14.369 observed `required: false`, `nullable: false`, `initial: undefined`.
  Missing stays missing; null must not be accepted merely because selected
  fixtures contain an empty string. This observation verifies runtime defaults,
  rather than claiming an underscore-prefixed defaults accessor is public.

## Live fixture evidence

Existing development runtime: Foundry 14.369 / PF2e 8.6.1, authorized GM browser.
Read-only index scan covered all 26 available Item packs; all completed, with
29 class entries solely in `pf2e.classes`. World Items and owned Items on
in-scope character/NPC/familiar Actors contained no class fixtures. This does
not establish absence on excluded Actor types or future worlds.

Only three selected class documents were hydrated with public `getDocument`
and serialized with source-default `toObject()`. No import, creation, mutation,
roll, activation, preparation or recursive feature hydration occurred.

| Fixture | Canonical UUID | Offers; selected | HP | Perception; Fort/Ref/Will | Spellcasting | Features |
| --- | --- | --- | --- | --- | --- | --- |
| Fighter | `Compendium.pf2e.classes.Item.8zn3cD6GSmoo1LW4` | dex,str; null | 10 | 2; 2/2/1 | 0 | 16 |
| Rogue | `Compendium.pf2e.classes.Item.LO9STvskJemPkiAI` | dex; null | 8 | 2; 1/2/2 | 0 | 20 |
| Wizard | `Compendium.pf2e.classes.Item.RwjIZzIxzPpUglnK` | int; null | 6 | 1; 1/1/2 | 1 | 15 |

All three had `attacks.other.name` present as an empty string and rank 0;
`traits` had common rarity and empty otherTags, with no trait-value array.
Fighter had simple/martial/unarmed rank 2 and advanced rank 1; Rogue had
simple/martial/unarmed rank 1 and advanced rank 0; Wizard had simple/unarmed
rank 1 and martial/advanced rank 0. Armor defense source differed as expected:
Fighter all four ranks 1; Rogue light/unarmored 1; Wizard unarmored 1, with
remaining sampled armor ranks 0. Trained-skill source was respectively empty
plus 3 additional, stealth plus 7 additional, and arcana plus 2 additional.

All five progression arrays were inspected in full for each fixture. Rogue
skill feats span every level 1–20 and skill increases 2–20; Fighter/Wizard use
even skill-feat levels and odd increases beginning at 3. Wizard class feats
begin at 2, while Fighter/Rogue include 1. These are stored definitions,
not acquired feats. All sampled ancestry arrays were 1,5,9,13,17 and general
feat arrays 3,7,11,15,19.

All 51 named feature entries, levels, source keys and UUID strings were
inspected without target hydration, including future definitions through level
19. Examples: Fighter Reactive Strike at 1 and Versatile Legend at 19; Rogue
Sneak Attack at 1 and Master Strike at 19; Wizard Wizard Spellcasting at 1 and
Legendary Spellcaster at 19. Target resolution, permission rechecks, bounded
relationship output and actual MCP reader behavior require separate tests.

The ignored `.local/class-selector.js` returns only these three index-derived
names/UUIDs for bounded reader verification. Existing owned/world fixtures
remain unavailable; deterministic tests must cover those contexts, null/missing
source, malformed ranks/arrays and non-PF2e rejection. Live v13 and other PF2e
versions remain unverified.


## Production reader acceptance

Actual authenticated MCP consumed all source/description pages for Fighter,
Rogue and Wizard. Key-attribute offers/null selections, HP contribution,
starting ranks and canonical rank labels, trained-skill source, all five full
progression lists and named feature levels matched stored source. Optional
other-attack names stayed empty strings, with no unsupported trait-value array.
Exact prose reconstructed to source hashes. All51 immediate feature references
resolved; canonical read_item identity follow-ups passed. Complete source
fingerprints remained unchanged after reads.

Four helper tests, five shared-reader tests and six Python tests cover
world/pack/token identity, source omissions/nulls, strict rank labels/types,
optional name handling, escaped/repeated feature definitions, source bounds,
denied/missing/unsupported references, stale permissions/targets and actual
paginated cross-language DTOs. There is no target-source expansion, feature
acquisition, character advancement, HP arithmetic or automatic grant.

Full suites pass:294 Python tests (one skipped),360 JavaScript tests. Actual
MCP discovery descriptions and source/mapped/effective flags match implemented
behavior. Owned/world/token class fixtures remain deterministic coverage limits;
the three compendium definitions establish contrasting martial/skill/spellcaster
source and later progression reading. ITEM-class is complete for its declared
definition/progression scope; effective character integration remains separate.
