# Ancestry rulebook and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. Rulebook text,
pinned schema and read-only runtime observations are separate evidence. Fixture
discovery alone does not establish production reader acceptance.

## Actual rulebook read

The private PDF MCP returned complete Player Core Remaster pages with revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
Every response had `next_offset=null`; reading order and table structure remain
unverified.

| Printed page | Physical page | Extracted characters | Relevant evidence |
| --- | --- | --- | --- |
| 19 | 20 | 5118 | Separate ancestry, background, class and free attribute boosts; fixed, limited-choice and free offers; flaws decrease attributes. |
| 24 | 25 | 4998 | Alternate two-free-boost choice replaces ancestry defaults entirely; voluntary flaws have no remaster compensating boost; total starting HP combines ancestry and class contributions. |
| 41 | 42 | 4757 | Ancestry HP, size, Speed, languages, traits, special abilities and scheduled ancestry feat choices; distinguish heritage and ancestry. |
| 43 | 44 | 3876 | Dwarf example has 10 ancestry HP, Speed 20 feet, Constitution/Wisdom/free boosts, Charisma flaw, languages, darkvision and clan-dagger prose. |

These rules support presenting offered boosts separately from persisted choices,
and ancestry HP as a contribution rather than total character HP. Alternate
boost choices remain distinct from default boosts/flaws. Language offers do
not establish currently selected additional languages. Scheduled ancestry feats
and named feature definitions do not prove acquisition by an Actor. Exact
description prose preserves special abilities without executing grants or
recalculating effective statistics.

## Pinned schema and source boundary

The [ancestry schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ancestry/data.ts)
declares keyed `boosts` and `flaws` slots, each with offered `value` attributes
and nullable `selected`. `alternateAncestryBoosts` is nullable: null differs from
an explicitly empty or populated alternate-choice array. The source schema
does not itself require exactly two selected values; a reader must not repair
incomplete choices. `voluntary.legacy`, `voluntary.boost` and `voluntary.flaws`
retain the legacy pre-remaster model independently of the remaster rulebook.
A stored legacy boost must not be advertised as a general remaster benefit.

Other source fields include `hp`, `size`, `speed`, `vision`, `hands`, `reach`,
`languages.value/custom`, `additionalLanguages.count/value/custom`, traits and
standard metadata. The source bounds specify integer HP 4–12 in steps of two,
Speed/reach 0–100 in steps of five, hands 0–12 in steps of two, and additional
language count 0–99. Source contributions and offers remain distinct from
effective Actor HP, movement, reach, capacity and known languages.

The shared [ABC feature entry schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts)
declares `items` as a keyed record of `uuid`, `img`, `name` and nonnegative
integer `level`. These keys represent source occurrences, not Documents.
Preserve each occurrence's path and level even when targets repeat. Resolving
the explicit UUID identifies a definition; it does not establish an owned grant,
current eligibility or automatic acquisition. Follow immediate target identity
without recursively expanding feature definitions or creating Items.

The pinned [ancestry implementation](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ancestry/document.ts)
explains why source and prepared values differ: preparation fills singleton
boost/flaw selections, clears invalid selections and applies contributions to
the Actor. The reader uses selected `toObject(true)` source, never those
preparation methods, prepared fields or `lockedBoosts`/`getLinkedItems` getters.
Source inspection explains behavior; it does not establish these members as
supported external APIs. No disabled-constructor guard like affliction exists
for this ancestry type.

## Scoped existing runtime fixtures

Read-only public world Item/Actor collections, scene TokenDocument actors and
all **26 installed Item compendium indexes** were inspected. Actor instances
were deduplicated by actual UUID with no base-actor fallback. There were **894**
distinct instances: **731** supported character/NPC/familiar instances and
**163** excluded instances. Neither group contained an ancestry Item, and no
standalone world ancestry existed. The only indexed ancestry Items were **51**
definitions in `pf2e.ancestries`.

Three definitions were hydrated individually using public `getDocument` and
`toObject(true)`; explicit feature UUIDs were followed via public `fromUuid`.
No source, grant, inventory or Actor was changed.

| Existing definition | Source HP / Speed | Offered boosts and flaw | Named references |
| --- | --- | --- | --- |
| Dwarf | 10 / 20 feet | Constitution, Wisdom, free; Charisma flaw | Clan Dagger, level 0, resolves to a `feat` definition |
| Human | 8 / 25 feet | Two free slots, empty third slot; empty flaw slot | Empty source record |
| Leshy | 8 / 25 feet | Constitution, Wisdom, free; Intelligence flaw | Plant Nourishment, level 1, resolves to a `feat` definition |

All selected boost/flaw values were null, including singleton offers. All three
had null alternate boosts, `voluntary.legacy=false`, null voluntary boost and
empty voluntary flaws. Each had two hands and reach five. Dwarf had darkvision,
Human normal vision and Leshy low-light vision. Their default language counts
were two, one and two; additional offered-language counts were six, zero and
six. Human had `additionalLanguages.count=1`, the others zero. These stored
counts do not prove effective capacity or intelligence-based selections.

## Remaining live acceptance scope

The selected compendium fixtures cover default fixed/free offers, a flaw,
empty slots, language contributions and empty/populated feature references.
World, embedded and synthetic-token ancestry fixtures are absent. Populated
alternate or voluntary choices, legacy mode, repeated feature targets,
missing/denied/unsupported targets and stale references need deterministic
coverage. No additional world setup or game writes are required.

Production acceptance should consume every source/description/relationship
page, compare exact selected source and reconstructed prose, follow the two
immediate target identities, and verify unchanged source fingerprints. This
ledger records fixture discovery; production reader results belong in a
separate acceptance entry after those checks pass.


## Production reader acceptance

Actual MCP consumed all source/description pages for the three existing
compendium ancestries. Offered/selected slots, null alternate/voluntary values,
HP/size/Speed/hands/reach/vision and language contributions matched exact stored
source, including null singleton selections. Exact description fragments
reconstructed to source hashes. Human returned an explicit empty feature scope;
Dwarf/Leshy resolved their two immediate feat definitions, with canonical
read_item identity follow-ups and no acquisition fields. Complete source
fingerprints stayed unchanged after reads.

Four helper tests, five shared-reader tests and five Python tests cover
world/pack/token identity, alternate and legacy voluntary source, escaped paths,
repeated future-feature targets, malformed/oversized input, denied privacy,
stale source/target/permission changes and actual paginated cross-language DTOs.
Source-only reads do not resolve references; explicit links do not read target
source. Exponent-encoded finite integer feature levels retain their source
numeric meaning across JSON boundaries while booleans/fractions reject.

Full suites pass:275 Python tests (one skipped),332 JavaScript tests. Actual
MCP discovery describes ancestry source/mapped support and unavailable effective
statistics. Unavailable populated character/token fixtures remain documented
coverage limits. ITEM-ancestry is complete for its declared source/definition
scope; character Build joins and effective integration remain separate stories.
