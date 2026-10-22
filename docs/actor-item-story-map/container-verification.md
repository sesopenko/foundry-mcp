# Container book and runtime verification

Verified 2026-10-23 against Foundry **14.369 / PF2e 8.6.1**. These are
read-only persisted-source observations and rulebook evidence, not proof of
production reader acceptance or effective Bulk calculations.

## Actual rulebook reads

Read complete canonical pages through the GM-private PDF MCP. Each returned
`next_offset=null`; reading order and table structure remain unverified.
Player Core revision:
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.

| Printed / physical page | Characters | Relevant evidence |
| --- | --- | --- |
| 267 / 268 | 5156 | Held, worn and stowed differ; sufficient hands matter for wielding. |
| 268 / 269 | 3702 | Retrieving stowed objects uses Interact; opening or closing the container can require Interact too. |
| 269 / 270 | 5489 | Bulk reflects handling difficulty; light-item aggregation and rounding differ from simple fractional addition. |
| 287 / 288 | 5570 | Backpack-specific capacity, ignored Bulk and worn versus carried/stowed Bulk; chest capacity. |
| 288 / 289 | 6000 | Adjacent gear descriptions checked for continuation; backpack definition is complete on p. 287. |

The ordinary backpack holds up to 4 Bulk; its first 2 Bulk of contents do not
count against the carrier's limits. Its own Bulk changes from negligible when
worn on the back to light when carried or stowed. A chest instead holds up to
8 Bulk. These are item-specific rules, not permission to subtract every
container's stored ignored Bulk from an actor total. Capacity is a limit,
not the current contents Bulk. Containment alone does not establish wearing,
access actions, current availability, investment or active magic.

## Pinned schema contract

The [PF2e 8.6.1 container schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/container/data.ts)
declares document type `backpack`, equipment traits, `stowing`, `usage.value`
and numeric `bulk.value`, `bulk.heldOrStowed`, `bulk.capacity`, `bulk.ignored`.
The type represents containers generally, including objects other than literal
backpacks. It inherits investable physical source and nullable `containerId`
from the [physical schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts).
Serialized `subitems` are explicitly excluded by the container schema. The
`collapsed` field is presentation configuration, not a contents or rules fact.

Build joins from each physical Item's persisted `containerId`, using actual
documents from its own actor instance. No prepared contents/container getter,
UI state, inferred UUID or base-actor substitution is needed. Preserve malformed
links, duplicates, missing parents and cycles explicitly; runtime preparation
can alter a bad relationship, so only `toObject(true)` establishes source.

## Read-only runtime inventory

Used public collections, token `actor`, document identity and `toObject(true)`.
Inspected each unique actor UUID from world actors and scene token actors,
without falling back to a base actor. There were **894** unique actor instances,
**3** container Items and **8** nonempty physical `containerId` links. All
parents existed in the same owner collection and were `backpack` Items;
no cycles or wrong-type parents were observed. This audit does not establish
those invalid states are impossible.

All three containers were owned **loot Actor** Items, outside the supported
character/NPC/familiar reader scope. The 172 supported world Actors had zero
containers. All three loot containers were stowing true, with own Bulk value
and held-or-stowed Bulk both 1. Their capacity/ignored pairs were 100/100,
50/50 and 25/25, with respectively 3, 2 and 3 direct child documents.
There were **zero** standalone world containers and no additional distinct
token-only containers. Nested containers, malformed parents, cycles and
supported NPC/character/familiar owners require deterministic fixtures; do not manufacture
game documents to fill the gap.

Selected only `pf2e.equipment-srd`, indexing type, stowing, bulk and usage.
Its **46** container rows include **29** stowing true, **17** false,
**26** positive ignored Bulk, and **19** whose held-or-stowed value differs
from own Bulk value. Hydrated only two distinct matching documents:

| Selector | Stowing | Own / held-or-stowed / capacity / ignored Bulk | Usage |
| --- | --- | --- | --- |
| First `stowing === false` | false | 0 / 0.1 / 1 / 1 | `worn` |
| First `stowing === true && bulk.ignored > 0` | true | 0.1 / 0.1 / 10 / 10 | `worngarment` |

Both selected documents retained identical serialized source before and after
inspection. Neither was imported, activated, rolled, enriched, updated or used
to create chat. Index counts describe this installed pack, not all published
containers. Source capacities and ignored Bulk cannot by themselves determine
the current contents total or whether an extradimensional effect applies.

## Reader acceptance still required

Verify actual paginated `read_item` responses against the selected pack source
facts. Owned-container runtime acceptance is unavailable: observed owned
containers belong to excluded loot Actors, so their identities must not be
advertised as supported owned-reader samples. Test nested contents appearing once, missing/denied/
wrong-type parents, cycles, stale continuations and same-instance isolation.
Preserve explicit incomplete/unsupported sections for pending aggregate Bulk
and actor inventory behavior. Source fingerprints and exact bounded description
continuation must remain unchanged. This evidence does not itself close the
Item story or CORE-inventory.

## Actual container-reader acceptance

Authenticated MCP read two selected compendium containers: a non-stowing shape
and a stowing/ignored-Bulk shape. All source pages completed, source paths stayed
unique, exact stored value/heldOrStowed/capacity/ignored/stowing matched hydrated
source, and descriptions reconstructed to identical SHA256 fingerprints. Both
unowned relationship reads remained partial with container_scope_unverified;
neither claimed empty contents. Complete source fingerprints were unchanged.

The production reader intentionally excludes containers owned by loot Actors.
The broad audit's three owned containers therefore cannot supply an in-scope live
fixture. There are zero containers on the 172 supported world Actors, and no
supported token-container fixture. Deterministic tests cover owned and synthetic
context, nested descendants appearing once, cycle diagnosis without repeating
root, missing/unsupported parents, malformed links, denied source privacy, source-
only no-scan behavior, source/relationship provenance and stale continuations.
Existing public document/schema contracts establish the implementation boundary;
these tests do not claim a live owned-container fixture was read.

Both full suites passed before the local unit commit. Effective Bulk/capacity use,
encumbrance, access actions and magical exception application remain unsupported.
No container, content or Actor was imported, activated, rolled, moved or modified.
