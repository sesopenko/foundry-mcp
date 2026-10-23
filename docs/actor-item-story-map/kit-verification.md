# Kit rulebook and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. This ledger
separates actual rulebook text, pinned source contracts and read-only runtime
observations. Fixture discovery is not proof that the new reader passed its
live acceptance checks.

## Actual rulebook read

The private PDF MCP returned Player Core Remaster printed page **268**, physical
page **269**, with 3702 characters and `next_offset=null`. The revision was
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
Reading order and table structure remain unverified.

The quick equipment packages describe batches of starting gear, with separately
listed options that are outside the base package. The adventurer's pack includes
a backpack and specified quantities of supplies. This supports presenting kit
entries as bundle definitions, preserving nested quantities and distinguishing
optional prose from persisted entries. It does not make a definition an owned
possession, establish that every Item with “kit” in its name has Foundry type
`kit`, or authorize purchase, import or inventory creation. Its listed package
price and Bulk do not license recomputing source price, current carrying Bulk
or remaining starting money from a selected kit definition.

## Pinned source contract

The [PF2e 8.6.1 kit schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/kit/data.ts)
extends the base Item data model, **not** physical Item source. Selected source
therefore includes its own `items`, `price`, class `traits.value`, `otherTags`,
slug, publication and description fields. Physical quantity, carrying state,
container IDs, Bulk and actor investment must not be invented for the kit itself.

`items` is a keyed record of entries. Each entry declares an Item UUID, image,
positive integer quantity, nonblank name, boolean `isContainer`, and nested
`items`. Keys and source paths identify serialized occurrences, not Documents.
Repeated target UUIDs remain separate entry occurrences with independent
quantities; resolving them does not make the occurrences owned Items.

The recursive field's comment says constructor depth is between zero and two,
but its actual `depth <= 2` condition constructs a nested field at depth three.
Consequently entries at zero-based depths **0, 1, 2 and 3** are admitted, and
an entry at depth three uses `NullField` for its `items`. Implementations must
check the executable schema rather than truncate valid depth-three entries
based on that comment. Empty records, absent paths and terminal null values
remain distinguishable. Serialized nesting does not recursively load the
referenced Item's own kit definition or generated possessions.

The shared [PriceField](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/schema.ts)
is independently usable by kit source. It retains explicit denominations,
`per` and optional `sizeSensitive`; initialized Price values supply derived
normalization that is not a substitute for `toObject(true)` source. Optional
own-undefined `sizeSensitive` can be absent; it must not become stored false.
Do not sum component prices or multiply bundle and entry quantities into an
invented inventory total.

The pinned [kit class](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/kit/document.ts)
has no disabled constructor or affliction-style runtime guard. Its grant
creation implementation clones and expands Items and can follow referenced
kits; none of that is a read contract or an allowed reader dependency.
The [template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json)
registers the kit type but has no separate kit source template authorizing
invented physical fields or defaults.

## Scoped read-only runtime fixture inventory

Public world Item/Actor collections, scene TokenDocument actors and all **26
installed Item compendium indexes** were inspected without creation, import,
update, activation, rolling, enrichment or chat. Actor instances were deduplicated
by actual UUID; no base-actor fallback was used.

| Scope | Observed actual kit Items |
| --- | --- |
| Standalone world Items | 0 |
| Supported Actor ownership | 0 |
| Excluded Actor ownership | 0 |
| Compendium Items | 2 |

The scan covered **894 distinct Actor instances**, including **731** supported
character/NPC/familiar instances. Both actual kits were in the equipment
compendium and were hydrated individually using public `getDocument` and
`toObject(true)`.

| Existing definition | Entries | Maximum zero-based depth | Container entries | Price basis |
| --- | --- | --- | --- | --- |
| Adventurer's Pack | 9 | 1 | 1 | 15 sp, per 1 |
| Cartographer's Kit | 5 | 0 | 0 | 42 gp, per 1 |

The adventurer's pack has one root backpack entry with eight nested supplies;
quantities include 10, 2 and 5, and each leaf has an empty nested record.
Cartographer's kit has five root equipment entries, each quantity one and an
empty nested record. Both have empty class-trait/other-tag arrays and optional
own-undefined `price.sizeSensitive`. Adventurer's pack explicitly retains zero
cp/gp/pp denominations; Cartographer's kit has only gp in source.

All **14 explicit source UUID occurrences** resolved via public `fromUuid` to
existing Item definitions: one backpack, two consumables and eleven equipment
Items. Only target type/identity was inspected; no target source expansion or
grant creation was requested. These observations establish available live
nested and flat fixtures, not yet acceptance of the published kit reader.

## Remaining verification scope

Real world, embedded and synthetic-token kit fixtures are absent. Maximum
schema depth, null terminal fields, repeated UUIDs, non-unit price basis,
missing/denied/unsupported targets and stale relationships require deterministic
coverage. Live checks should consume the two available selected kit readers,
reconstruct exact description text, follow immediate named contributor identity,
verify provenance and pagination, and compare before/after source fingerprints.
No game writes are needed to address the remaining live gaps.


## Production reader acceptance

Actual authenticated MCP reads consumed all source/description pages for both
compendium kits. Nested component paths, names, independent quantities and
price basis matched selected source exactly, including absent optional
sizeSensitive and missing denominations. Source records used the kit mapping,
without physical carrying or owned-stack fields. Exact prose reconstructed to
its canonical source hash. Explicit relationships preserved all14 source
occurrences and resolved their canonical targets; immediate read_item identity
follow-ups succeeded. Both complete Item source fingerprints stayed unchanged.

Four source-helper tests, five shared-reader tests and six Python tests cover
schema depth/escaped provenance, world/pack/token contexts, duplicate targets,
bounds, denied privacy, stale references and actual paginated cross-language
DTOs. A focused regression also proves exponent-encoded JSON integers remain
valid finite integer schema values across JavaScript/Python, without admitting
booleans or fractional counts. Book reference regressions pass after sharing
the identical immediate Item resolver. No target source, import, recursive
kit expansion or inventory mutation occurs.

Full suites pass:270 Python tests (one skipped),323 JavaScript tests. Actual
MCP discovery descriptions/schemas and kit source/mapped/effective flags match
implemented behavior. Missing world/owned/token fixtures remain deterministic
coverage limits; the two live kits establish nested/flat definition reading.
ITEM-kit is complete for its declared bundle-definition/source-link scope.
