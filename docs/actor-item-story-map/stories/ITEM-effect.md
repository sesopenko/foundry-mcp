# ITEM-effect: Effects, origins and durations

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `effect` Item as **effects, origins and durations**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core p. 442 describes condition persistence; GM Core pp. 219–221 describes ongoing item benefits and sustained activations. PF2e effect Items are an automation representation, not a one-to-one rulebook category. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/effect/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `level.value`, `duration`, `start`, `badge`, `context`, `unidentified`, `fromSpell`.
- Mapping and relationships: Expose effect source, duration unit/expiry/sustained flag, badge type and linked origin. Separate tracking effects from acquired abilities; do not interpret every badge as uses or a condition value.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Counter, value and formula badges preserve their discriminator; formulas are not rolled.
- Unlimited/encounter durations are not treated as numeric zero seconds.
- Duplicate origins or a spell tracking effect do not create duplicate learned spells.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Expiry/current application and provenance traversal require supported contracts. `expired` is declared derived data, not persisted evidence or independent public API approval.

Persisted-source and explicit immediate-reference readers are verified; see [field contract](../effect-fields.md) and [rulebook/runtime evidence](../effect-verification.md). Live samples cover null context only; non-null context, linked/synthetic targets and value badges have deterministic coverage. Effective expiry/current application, suppression and recursive provenance remain explicitly unsupported and do not close state/acceptance gates. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.
