# ITEM-spell: Spell definitions and contextual ranks

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `spell` Item as **spell definitions and contextual ranks**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 297–299, 303 distinguishes base spells, heightening, casting resources and spell stat-block fields. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `level.value`, `traits.traditions`, `traits.value`, `time.value`, `requirements`, `cost.value`, `range.value`, `target.value`, `area`, `duration`, `damage`, `defense`, `heightening`, `overlays`, `ritual`, `location`.
- Mapping and relationships: Rename this type’s level to base rank. Keep spell definition separate from cast rank, slot rank, variants and availability. `location.value` is an owning actor’s casting-entry ID; return the link without requiring the casting-entry reader.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Variable or long casting time remains text rather than a guessed action count.
- A slot above the known rank does not necessarily heighten a spontaneous spell (Player Core p. 298).
- Unassigned/missing entries and damage-versus-healing components remain explicit.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Supported computed variants/cast ranks require CORE-casting. Ritual, flexible and item-casting execution semantics remain partial; do not evaluate overlay/preparation methods merely to read.

Definition/source reading and immediate casting-entry references are verified; see [field contract](../spell-fields.md) and [rulebook/runtime evidence](../spell-verification.md). Nine live spell cases cover variable/long time, mixed healing/damage, interval/fixed heightening, overlays, ritual and owned assigned/unassigned entries. Exact root and nested source prose use bounded continuation without merging variants. Deterministic checks cover missing/denied/wrong-type links, canonical linked/synthetic contexts, malformed/empty/optional source and stale reads. Computed cast ranks, variants, slot resources and castability remain explicitly unsupported under CORE-casting. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.
