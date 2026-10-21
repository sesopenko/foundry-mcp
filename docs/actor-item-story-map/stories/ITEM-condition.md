# ITEM-condition: Conditions and persistent damage

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `condition` Item as **conditions and persistent damage**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 442, 445 defines valued conditions, suppression and persistent damage/recovery. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/condition/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `value.isValued`, `value.value`, `persistent.formula`, `persistent.damageType`, `persistent.dc`, `persistent.criticalHit`, `references`, `overrides`, `fromSpell`.
- Mapping and relationships: Present stored condition/value, persistent-damage details and origin/override links. A stored override relationship does not establish final activity; preserve state uncertainty.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Valued and unvalued conditions remain distinct; stored presence is not claimed active.
- Overridden conditions remain present; suppression does not mean removal.
- Multiple persistent damage types and uncertain same-type dominance are not flattened.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Public/supported active/suppressed-state extraction needs proof and live fixtures. Do not adopt prepared condition collections or recompute suppression from rulebook text.

Persisted source and explicit owner-local relationship readers are verified; see [field contract](../condition-fields.md) and [rulebook/runtime evidence](../condition-verification.md). Live checks cover owned/compendium source and empty reference lists/override slugs. Populated reference chains and persistent-damage metadata have deterministic coverage only. Active/suppressed state, effective duration and damage dominance remain explicitly unsupported advanced gates. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.
