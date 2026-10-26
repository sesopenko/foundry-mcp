# Book rulebook and runtime verification

Verified 2026-10-22 and 2026-10-25 against Foundry **14.369 / PF2e 8.6.1**. This ledger
separates rulebook interpretation, pinned source contracts and the available
read-only runtime inventory and subsequent genuine-fixture reader verification.

## Actual rulebook reads

### October 25 runtime-gate clarification

The absence of representative books is a fixture gap, not a proven constructor
restriction. Pinned PF2e8.6.1
[BookPF2e](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/document.ts)
has no production constructor rejection. The base Item creation dialog omits
book from its interactive type chooser; that UI restriction does not establish
that documented programmatic document creation is unsupported. By contrast,
affliction explicitly rejects production construction.

Once the existing GM session is connected, a genuine marked temporary book
created through documented public document creation is a valid verification
candidate. Confirm runtime behavior, both categories and actual content links,
preserve source fingerprints and remove only that fixture. Do not retype an
equipment Item, bypass constructors or claim successful creation from this
source inspection alone. Live acceptance remains unproven.

The GM-private PDF MCP returned complete canonical pages with `next_offset=null`:

| Book | Printed / physical page | Characters | Revision |
| --- | --- | --- | --- |
| Player Core Remaster | 194 / 195 | 4878 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |
| Player Core Remaster | 288 / 289 | 6000 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |

Extraction reading order and table structure remain unverified. Page 194
separately describes the wizard's written spellbook and daily spell preparation:
studying the book supplies a collection from which preparation happens, while
prepared slots and current availability are different facts. A book's stored
spell reference does not establish a prepared slot, actor ownership of a spell,
casting eligibility, spell expenditure or a current casting option.

Page 288 describes formula books holding formulas for up to 100 different items.
It also allows formulas on other media that can be kept available for reference.
This does not prove a character knows every formula in a referenced document,
can currently craft a referenced Item, or must possess a particular physical
book. Preserve the Item's stored capacity independently of this rulebook example;
do not replace a source value or an absent field with 100.

## Pinned source contract

The [PF2e 8.6.1 book schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts)
extends physical source with `category` (`formula` or `spell`), numeric
`capacity` and an ordered `contents` array of Item UUIDs. Traits use equipment
traits. `subitems` is explicitly excluded. Ordinary physical source and metadata
remain separate fields; source contents are document-reference claims, rather
than embedded Item objects or generated possessions.

The [pinned template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json)
contains category `formula`, capacity `1`, contents `[]`. These are template
values, not permission to fabricate values omitted from a selected persisted
source. The [book class](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/document.ts)
is a physical Item subclass with equipment traits. It does not implement a
public book-specific prepared-spell, known-formula or crafting-eligibility engine.

The pinned standard [blank formula book](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/packs/pf2e/equipment/formula-book-blank.json)
and [blank spellbook](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/packs/pf2e/equipment/spellbook-blank.json)
are both **`equipment`**, not `book`. Names or prose must not silently change
Item types or fabricate book fields for equipment. This physical `book` Item
type is unrelated to the private PDF document library.

## Scoped read-only runtime inventory

Inspected public world Item/Actor collections, scene TokenDocument.actor and all
**26 installed Item compendium indexes**, requesting only type and book source
fields. Actor instances were deduplicated by actual UUID; there was no base-actor
fallback or document creation, import, update, cast, roll or activation.

| Scope | Observed book Items |
| --- | --- |
| Standalone world Items | 0 |
| Supported Actor ownership (world and synthetic) | 0 |
| Excluded Actor ownership | 0 |
| Installed Item compendium indexes | 0 |

There were **894 distinct world/synthetic Actor instances**, of which **731**
were within the supported character/NPC/familiar owner scope. The scene scan
encountered 778 token-Actor occurrences before deduplication. Counts describe
this development world and installed content only, not all PF2e publications.
The class/schema exists despite no representative book fixture being present.

## Earlier reader verification gap

At the October 22 inventory, no actual existing book Item was available to exercise paginated `read_item`,
exact source-description reconstruction or real book-to-content resolution.
Existing spell/equipment reader results are not substitute book-reader evidence.
The later constructor audit established the legitimate temporary-fixture route.

Deterministic acceptance should independently cover formula/spell categories,
capacity zero and non-default values, source omission/null/type errors, empty
and duplicate content references, full UUID resolution, named permitted targets,
missing/denied/unsupported targets, cross-owner and synthetic-token identity,
relationship changes invalidating continuations, bounds and unsupported systems.
Content references must preserve source-path evidence and occurrence order;
resolving a reference must neither import a document nor recursively expand
its rules or claim preparation, known-formula ownership or crafting eligibility.
These were the original live gates, subsequently exercised below.


## Implemented deterministic checkpoint

Five shared-reader tests and five Python boundary tests supplement the four
source helper tests. Actual paginated JavaScript DTOs cross the strict Python
boundary. Both categories, exact prose, common physical fields, duplicate-index
links, empty/absent markers, unsupported/denied targets, synthetic follow-ups,
resolution guards and stale target/source/permission checks pass. Source-only
reads never resolve contents, and relationship reads never request target source.

Full regression suites pass:264 Python tests (one skipped),314 JavaScript tests.
Actual MCP discovery confirms book source/mapped support with effective support
false and `live=not_run`; existing delivered readers still pass live regression.
The dedicated development tab is refreshed for the implementation. This confirms
module loading and discovery, not actual book source/content behavior. The
representative fixture gate remains open and ITEM-book remains In progress.

## Genuine world-book verification — October 25

`scripts/actor-book-live-check.py --world-id test` passed on the existing
localhost development world and GM session: **two books, 26 pages, 82 raw source
witnesses, six relationships, 48 description fragments and 40 MCP calls**. Cleanup
and unchanged complete fixture source fingerprints were confirmed.

The harness used documented public `Item.implementation.create` to create actual
`book` Items, one formula and one spell category. Both preserved capacity 100,
ordered duplicate compendium-definition references and a valid missing Item
claim. Source values were independently compared with public `toObject(true)`;
long Unicode HTML was reconstructed exactly through bounded pages. Immediate
links resolved named actual equipment/spell definitions, duplicates retained
their occurrence keys, and the missing reference returned `status: missing`
with null target. Canonical target identity follow-ups passed. The effective
section remained unsupported; references acquired no formula or prepared spell.

Only those two unpredictable run-marked books were deleted through public
`Item.delete`; existing Items, Actors and packs were not modified or imported.
Cleanup verifies zero remaining marked Items and zero pending creations. An
offline deferred-creation regression proves late creation self-deletes after a
timeout closes the run, without starting a second creation or deleting unrelated
documents. Lost responses and cleanup failures cannot report success. Another
regression reproduces the exploration serializer's aggregate string budget and
verifies compact fixture metadata avoids it; prose travels through `read_item`.

World books and populated compendium target links are now live-verified.
Owned/synthetic contexts, denied/unverified targets, empty/absent content and
stale continuations retain deterministic coverage. No pack book was written,
equipment retyped or constructor bypassed. ITEM-book's original source/content
gate is complete. Formula knowledge, preparation, crafting eligibility and
casting remain unsupported, consistent with the read rulebook passages.
