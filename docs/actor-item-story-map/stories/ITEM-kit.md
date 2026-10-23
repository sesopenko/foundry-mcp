# ITEM-kit: Bundle definitions

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `kit` Item as **bundle definitions**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core p. 268 describes starting equipment packages as batches of gear; names containing “kit” are not proof of Foundry kit type. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/kit/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `items` (nested UUID/name/quantity/isContainer/items entries), `price`.
- Mapping and relationships: Show the bundle definition and nested component references, never import it or treat the definition plus expanded possessions as two inventories.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Nested container/components retain their quantities and names.
- Reading a kit creates no inventory and does not load every component recursively.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

A kit is not a PhysicalSystemSource subtype; use shared document extraction and its own items/price schema, not the physical allowlist.

Delivered source/reference verification and its remaining live coverage limits are recorded below. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.


Selected bundle source and explicit immediate component references are delivered;
see [field contract](../kit-fields.md) and [verification](../kit-verification.md).
Actual MCP reads consumed two existing compendium kits, preserved nested
quantities/names and all14 immediate references, reconstructed exact prose and
retained source fingerprints. Deterministic tests cover world/owned/token scope,
maximum nesting, duplicate UUIDs, escaped keys, absent/null/empty maps, strict
price fields, permission failures and stale continuations. Source-only reads
never resolve components; explicit links never read target source or recursively
expand referenced kits. Actor inventory keeps definition references separate
from actual possessions. No import, activation, game write or release occurred.
