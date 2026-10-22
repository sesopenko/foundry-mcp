# Armor book and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. This records rulebook and read-only source-shape evidence, not completion of the armor reader's acceptance tests.

## Rulebook evidence

Read the entire Player Core printed **271**, physical PDF **272**, through `read_pdf_pages`. The returned revision was `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`; `total_characters=4518`, `next_offset=null`. Extraction warns that reading order and table structure are unverified. These conclusions use the prose definitions and AC formula, not reconstructed table cells.

- Armor protects a creature while worn. A stored armor Item, including an unowned pack Item with a stored worn carrying state, does not establish an actual wearer's AC contribution.
- AC includes 10, capped Dexterity modifier, proficiency, armor item bonus, other bonuses, and penalties. `acBonus` is an armor source bonus, not total Actor AC.
- Dex cap limits the Dexterity modifier applied to AC while wearing the armor. It is not the wearer's Dexterity modifier.
- Strength is a **Strength modifier threshold**, not a legacy ability score. Meeting it removes the armor check penalty and reduces its Speed penalty by 5 feet. Do not convert the stored threshold into an ability score or automatically apply these adjustments without wearer context.
- Check penalties concern Strength- and Dexterity-based skill checks, excluding attacks. Speed penalties concern movement types, with a minimum Speed of 5 feet. Stored penalties are not the Actor's final skill modifiers or Speed.
- Category selects relevant proficiency; group organizes armor and can be referenced by abilities. Neither alone proves a proficiency bonus or specialization effect.

## Schema boundary

Pinned [ArmorSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/armor/data.ts) declares nullable `strength`, nullable `group` and `baseItem`, numeric `acBonus`, `dexCap`, `checkPenalty` and `speedPenalty`, rune configuration, nullable `specific` baseline material/runes, and physical source `subitems`. `runes.effects` and armor's always-worn `usage` appear in prepared data rather than persisted Armor source; do not fabricate either into `toObject(true)` source. The source interface explicitly says armor usage is not stored.

Missing Strength remains absent; explicit null remains present-null; zero remains a present numeric modifier threshold. Runtime absence of `specific` must not be filled with a schema default. Specific baseline material/runes and current rune configuration are separate source paths, not extra benefits to sum together.

## Read-only development inventory

Used public document collections/relationships and `toObject(true)` only; no sheets, rolls, chat, enrichment, preparation helpers, private members, imports or writes. Output retained aggregate shapes only, not world names, descriptions or identifiers.

- Supported world Actors contained **21 NPC-owned armor Items**, including **8** with a Strength threshold of zero. No character-owned, familiar-owned or standalone world armor was present. All 21 had source rune configuration and lacked their own `specific` source field; the selected carrying states were worn.
- Scene navigation found armor on **6 linked tokens** and **97 synthetic tokens**, totaling **103 token-context armor occurrences**. After canonical Item UUID deduplication, there were **118** distinct armor documents: 21 base-owned and 97 synthetic-owned. Synthetic sources included 43 zero Strength thresholds and no null thresholds; all 97 lacked `specific` and had rune configuration.
- SHA-256 fingerprints of all 118 selected persisted sources matched before and after source inspection. Linked Items deduplicated against base-owned Items; synthetic Items retained their distinct actual owner context.

## Selected pack hydration

Queried only `pf2e.equipment-srd` with public `getIndex({fields:["type","system.strength","system.specific","system.runes"]})`, then selected armor rows by explicit source shape. The index contained **215 armor rows**, including **23 null Strength**, **41 zero Strength**, and **149 non-null specific baseline objects**. These counts describe this installed pack, not all published armor.

Hydrated only selected documents with `getDocument(row._id)`; no bulk load or import. A non-null specific example also supplied the zero-Strength case: source `acBonus=1`, `dexCap=4`, `checkPenalty=-1`, `speedPenalty=0`, current potency 1/resilient 0, and a separate specific baseline containing nullable material and potency 1/resilient 0. A null-Strength example had `acBonus=0`, `dexCap=2`, `checkPenalty=-1`, `speedPenalty=-5`, potency/resilient 0, and absent `specific`. Both remained unowned pack Items despite stored worn carrying state. Exact serialized source comparisons before and after selected inspection matched.

Reproduce selectors dynamically from the returned index: filter `type === "armor"`; find a row with non-null object `system.specific`, a row with `system.strength === null`, and a row with `system.strength === 0`. Hydrate only those selected row IDs. Do not hard-code world selectors or infer null from a missing property.

## Remaining verification boundaries

This inventory does not prove the new production reader, its Python DTO validation, pagination, missing-value handling, denials, identity propagation, or no-write behavior across actual reader calls. Those require focused deterministic tests and live `read_item` checks recorded with the implementation. No live unworn armor, character/familiar-owned armor, standalone world armor, or missing Strength fixture was found; use explicit deterministic fixtures for those cases and retain the live gaps. Effective Actor AC, saves, movement, proficiency and rune application remain outside the source mapping.

## Actual reader acceptance

Authenticated MCP consumed all bounded source pages for five selected examples:
two NPC-owned armor Items plus compendium specific-magic, null-Strength and
zero-Strength candidates. Source AC bonus and Strength matched persisted values;
all shared physical/armor source paths were unique. Effective sections remained
unsupported and selected source fingerprints stayed unchanged. Deterministic
fixtures verify unworn/investment state, missing/null/zero thresholds, exact text,
serialized attachment identity, malformed/stale/denied/system boundaries and
specific rune/material source. Standalone and character/familiar live armor remain
unavailable. Source wearing/runes never automatically change Actor AC/saves/Speed.
