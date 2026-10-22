# Treasure book and runtime verification

Verified 2026-10-23 against Foundry **14.369 / PF2e 8.6.1**. Evidence here
establishes rulebook interpretation, pinned schemas and available read-only
fixtures; it does not by itself establish production reader acceptance.

## Actual rulebook reads

The GM-private PDF MCP returned complete canonical pages with `next_offset=null`:

| Book | Printed / physical page | Characters | Revision |
| --- | --- | --- | --- |
| Player Core Remaster | 267 / 268 | 5156 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |
| GM Core Remaster | 221 / 222 | 5872 | `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` |

Extraction reading order and table structure remain unverified. Player Core
establishes cp/sp/gp/pp exchange ratios (10 cp = 1 sp, 10 sp = 1 gp,
10 gp = 1 pp). Art objects, gems and crafting raw materials can exchange
at their full Price, unlike the usual half-Price resale of ordinary items.
This is a rulebook distinction, not evidence of a completed sale, buyer,
market access, negotiated offer or party wallet. Price describes typical
purchase cost. GM Core distinguishes selected item variants and their
individual Prices; an item's level does not itself bar a character from using
it. Preserve the selected source Item rather than inferring a different variant.

## Pinned source contract

The [PF2e 8.6.1 treasure schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/treasure/data.ts)
declares nullable `category`, traits (`value`, `rarity`, `otherTags`), quantity,
price and ordinary physical source fields. [Category values](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/treasure/values.ts)
are `art-object`, `coin`, `gem`, `material`, `credstick`; nullable category is
not proof that an object is valueless or lacks a rulebook category. Unknown
stored codes must remain raw rather than silently reclassified. Base metadata
includes slug and publication. `usage`, `subitems` and investment are excluded
from treasure source; prepared `stackGroup`, `usage`, size normalization and
prepared price behavior are not persisted fields.

The [price schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/schema.ts)
stores independently optional nonnegative integer denomination leaves in
`price.value`, positive integer `price.per` (default 1) and optional
`price.sizeSensitive`. Preserve these alongside quantity: they do not describe
an already computed stack total, sale proceeds or spendable aggregate balance.
An index's omitted category can hydrate to explicit source null; index omission
is not a supported missing-field conclusion about the hydrated document.

## Scoped read-only runtime inventory

Inspected public world collections and each scene token's actual `actor`,
deduplicating actor instances by actual UUID and using `toObject(true)`.
No base-actor fallback, computed valuation getter, import or update was used.

| Scope / Actor type | Distinct Actors | Treasure Items |
| --- | --- | --- |
| World NPC | 172 | 5 |
| Additional synthetic NPC | 559 | 9 |
| World character / familiar | 0 / 0 | 0 / 0 |
| Additional synthetic character / familiar | 0 / 0 | 0 / 0 |
| World loot (excluded owner scope) | 89 | 52 |
| World hazard (excluded owner scope) | 18 | 0 |
| Additional synthetic hazard (excluded owner scope) | 55 | 0 |
| World party (excluded owner scope) | 1 | 0 |

There are **zero standalone world treasure Items**. Supported NPC ownership
has 14 distinct treasure Items: 2 category `coin`, 12 explicit null.
The five world-NPC treasures comprise a coin stack quantity **21**, stored
`price.value.gp=1`, `price.per=1`, and four null-category quantity-1 objects
with stored gp values 4, 3000, 1440 and 50 respectively. Their serialized
sources were identical before and after inspection. Do not infer a stack
valuation or sale operation from these independent source facts. No character,
familiar or supported owned gem/art fixture is available.

Indexed only `pf2e.equipment-srd` with type/category/quantity/price fields.
Its **153** treasure rows include 4 coin, 50 gem, 96 art-object and 3 omitted
categories. Hydrated only the first selected row of each shape:

| Dynamic selector | Hydrated category | Quantity | Stored price value / per |
| --- | --- | --- | --- |
| First coin | `coin` | 1 | sp 1 / 1 |
| First gem | `gem` | 1 | sp 5 / 1 |
| First art-object | `art-object` | 1 | gp 250 / 1 |
| First index-omitted category | null | 1 | gp 1000 / 1 |

Each selected source remained byte-for-byte equal under `JSON.stringify`
before and after inspection. These are equality checks of serialized source,
not independently measured cryptographic fingerprints. No material or credstick
row was observed in this pack. Index counts describe only this installed pack;
there was no whole-pack document hydration or claim about all published treasure.

## Reader acceptance still required

Read the selected supported owned and pack Items through actual paginated
`read_item`, comparing category, quantity, denomination leaves and price basis.
Check explicit description reconstruction, unique paths and source fingerprints.
Retain deterministic coverage for source null/absence/unknown categories,
non-unit price basis, mixed denominations, zero quantity, denied/malformed data,
stale cursors, synthetic identity and unsupported systems. No computed balance,
resale, transfer, purchase, sale, coin conversion or state mutation is implied.

## Actual treasure-reader acceptance

Authenticated MCP consumed all source pages for six selected cases: NPC-owned
valuables, a synthetic-token Item and coin/gem/art-object/null-category pack Items.
Exact quantity, price.per and each stored denomination matched persisted source.
Category used the treasure mapping; shared physical source kept its original
mapping with unique paths. No usage or investment was synthesized. Exact source
descriptions reconstructed to identical SHA256 fingerprints; all six complete
source fingerprints were unchanged. Effective sections remained unsupported.

Focused deterministic fixtures cover character, NPC and familiar valuables in
linked and synthetic context while loot-Actor ownership is rejected. They keep
non-unit price.per and quantity independent, explicit category null, unknown
codes and description source, malformed values, changed-price continuations,
permissions and non-PF2e rejection. No asset-value getter, stackGroup, conversion,
sale proceeds or double multiplication is used. Full suites passed: 251 Python
tests (one skipped) and 291 JavaScript tests. A pre-existing private-data test
used the ordinary word 'excluded' as a sentinel, colliding with legitimate scope
documentation; it now uses a unique fake source marker with the leak check intact.

No Item was imported, sold, consumed, rolled, enriched or modified. No standalone
world, character or familiar treasure fixture is available live; their source and
identity boundaries have deterministic coverage. Source valuation basis does not
establish market conditions, effective wealth or any automatic transaction.
