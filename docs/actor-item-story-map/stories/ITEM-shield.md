# ITEM-shield: Shield properties and state

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | Complete |
| Prerequisites | [CORE-physical](CORE-physical.md) |
| Dependency reason | Uses common physical source rules and identity/bounds. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `shield` Item as **shield properties and state**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core p. 274 requires Raise a Shield for AC and separates Shield Block access; GM Core p. 232 adds reinforcing runes. Player Core 2 p. 89 illustrates class-granted reinforcement. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/shield/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `acBonus`, `hp`, `hardness`, `runes.reinforcing`, `speedPenalty`, `specific`, `traits.integrated`, selected `subitems`.
- Mapping and relationships: Show shield definition/durability separately from raised state and Shield Block access. Separate source rune configuration from class-granted effective reinforcement and linked attacks.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- A held shield is not automatically raised; ownership does not grant Shield Block.
- Retain reinforcing rune and publication provenance despite Player Core p. 274’s broader no-runes wording.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Raised/current state, class-granted reinforcement and attachment attacks require supported live extraction. Do not infer these from possession.

Source/configuration reading is verified; see [field contract](../shield-fields.md) and [rulebook/runtime evidence](../shield-verification.md). Live checks cover three distinct compendium sources only; no world/owned/token shields exist. Held-source and mixed provenance have deterministic coverage. Raised state, Shield Block eligibility, class-granted reinforcement and generated attachment attacks remain explicitly unsupported. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.
