# Heritage rulebook and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. Rulebook,
pinned schema and read-only runtime observations are separate evidence. Fixture
discovery does not establish production reader acceptance.

## Actual rulebook read

The private PDF MCP returned complete Player Core Remaster pages with revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
Every response had `next_offset=null`; reading order and table structure remain
unverified. No private rulebook text is reproduced here.

| Printed page | Physical page | Extracted characters | Relevant evidence |
| --- | --- | --- | --- |
| 41 | 42 | 4757 | Heritage is distinct from ancestry, normally selected at first level; versatile heritage options cross ancestry boundaries. |
| 74 | 75 | 3234 | Select ancestry first, then versatile heritage in place of an ordinary heritage. Heritage benefits can modify or replace ancestry benefits; specific heritage and GM restrictions can apply. |
| 75 | 76 | 3647 | Continuation of versatile-heritage feat options, lineage feats, and examples including Changeling and Nephilim. |

These passages support displaying heritage separately from ancestry and retaining
exact benefit prose without applying it. A null schema association does not
establish unrestricted eligibility, the owner's ancestry, or absence of prose
restrictions. A non-null association identifies a named source definition; it
does not establish the owner's actual ancestry or automatic exclusivity.

## Pinned schema and source boundary

The research checkout HEAD is `28d9d156f252d084371d994dc359509b49eadf18`,
PF2e 8.6.1. The pinned
[heritage schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/heritage/data.ts)
declares nullable `ancestry`, initially null. A populated association contains
required non-null `name`, `slug` and document `uuid`; the name may be blank.
Preserve each field independently and distinguish missing from explicit null.
Traits comprise creature-trait `value`, `otherTags` and `rarity`. Heritage has
no level field in its declared model. The inherited
[base schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts)
supplies description, publication, slug and rule-element source. Rule-element
execution and effective benefits are outside this source-reader scope.

The pinned
[implementation](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/heritage/document.ts)
uses null association to classify versatile heritage and applies traits and
Actor state during preparation. It also mentions exceptions permitting multiple
heritages. This explains source versus prepared behavior; it does not authorize
using `isVersatile`, preparation, Actor heritage getters or internal roll options
as external reader dependencies. A reader must not enforce a universal one-Item
limit, calculate resistance/vision, add traits or select an Actor's heritage.

The read-only probes used the documented public `getIndex({fields})`,
`getDocument(id)`, `getUuid(id)`, `toObject(true)` and async `fromUuid` boundaries.
Grounded Docs' existing official Foundry v14 index returned current public
[CompendiumCollection signatures](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html)
and [document identity guidance](https://foundryvtt.com/api/v14/modules/foundry.documents.html).
Runtime observations verify this installed build only; v13 and future PF2e
versions remain unverified.

## Scoped existing runtime fixtures

Read-only world Item/Actor collections, scene TokenDocument actors and all
**26 installed Item compendium indexes** were inspected. Deduplicating actual
Actor UUIDs yielded **894** instances: **731** supported character/NPC/familiar
instances and **163** excluded instances. There were **zero** owned heritage
Items across these instances and **zero** standalone world heritage Items.
Only `pf2e.heritages` contained indexed heritage definitions: **334** total.
No compendium Actor documents were scanned for embedded heritage fixtures.

Three existing definitions were hydrated individually. Source was read using
`toObject(true)`; the one populated association was followed with public async
`fromUuid`. No document was created, imported, updated or deleted. An initial
combined discovery probe timed out; subsequent bounded discovery probes
completed. Timeout is not evidence of completeness; the completed probes supply
the counts above.

| Existing definition | Canonical Item UUID | Stored association | Traits / source prose length |
| --- | --- | --- | --- |
| Arctic Elf | `Compendium.pf2e.heritages.Item.1dYDucCIaZpCJqBc` | Elf / `elf` / `Compendium.pf2e.ancestries.Item.PgKmsA2aKdbLU6O0` | Empty trait list, common; 323 characters |
| Nephilim | `Compendium.pf2e.heritages.Item.1oLMOmLpurfWTTff` | Explicit null | `nephilim`, uncommon; 457 characters |
| Changeling | `Compendium.pf2e.heritages.Item.EKY9v7SF1hVsUdbH` | Explicit null | `changeling`, uncommon; 475 characters |

All three had empty `otherTags`. Arctic Elf prose describes level-dependent cold
resistance and environmental treatment; Nephilim and Changeling prose describe
traits and conditional vision benefits. These are source definitions, not
computed Actor benefits. The Arctic Elf association actually resolved to named
**Elf**, type `ancestry`, pack `pf2e.ancestries`, local ID
`PgKmsA2aKdbLU6O0`, canonical UUID
`Compendium.pf2e.ancestries.Item.PgKmsA2aKdbLU6O0`.

## Remaining live acceptance scope

Selected compendium fixtures cover populated and null ancestry associations,
empty and populated traits, rarity and benefit prose. World, embedded and
synthetic-token heritage fixtures are absent; no new world setup is needed.
Malformed/missing/oversized fields, missing/denied/unsupported association
targets, stale changes and non-PF2e rejection need deterministic coverage.

Production acceptance should consume every source/description/relationship
page, compare exact selected source and reconstructed prose, follow the immediate
Elf definition identity, and verify unchanged source fingerprints. Source-only
reads must not resolve the association; explicit relationships must not read
target source or recursively expand its features. Null association must remain
explicit, without inferred owner ancestry or eligibility. Production reader
results belong in a separate acceptance entry after those checks pass.


## Production reader acceptance

Actual MCP consumed all selected source/description pages for the three existing
compendium definitions. Null versus populated ancestry source, association
name/slug/UUID leaves and traits matched exactly. Exact prose reconstructed to
source hashes. Arctic Elf resolved the actual named Elf ancestry and canonical
read_item identity follow-up; Nephilim and Changeling returned unassociated.
Complete Item source fingerprints remained unchanged. No target source, owner
ancestry lookup, feature expansion or game write occurred.

Four helper tests, six shared-reader tests and seven Python tests cover
world/pack/token identity, absent/null/populated associations, wrong-type and
missing/denied targets, independent synthetic target context, stale source/name/
permission changes, bounds and actual paginated cross-language DTOs. A shared
regression also prevents delivered definition readers from returning stale
pending-type limitation messages. Their specific effective/acquisition limits
remain explicit.

Full suites pass:288 Python tests (one skipped),351 JavaScript tests. Actual
MCP discovery matches source/mapped support and unsupported effective benefits.
Missing owned-world/token heritage fixtures retain deterministic coverage limits;
the available compendium fixtures establish both associated and versatile-null
reading. ITEM-heritage is complete for its declared source/association scope.
