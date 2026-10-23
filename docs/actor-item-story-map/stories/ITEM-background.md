# ITEM-background: Background benefit packages

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Ready for source milestone |
| Implementation status | In progress |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `background` Item as **background benefit packages**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core p. 84 describes boosts, skill training, skill feat and Lore, including duplicate-training handling. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/background/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `boosts`, `trainedSkills.value`, `trainedSkills.lore`, `items`.
- Mapping and relationships: Preserve benefit package and choices. CORE-build connects the actor’s acquired feat/Lore without duplicating them or granting missing documents.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [ ] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [ ] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- The same owned Lore or feat appears once with multiple contributors.
- An unselected boost and a missing expected grant stay explicit, without modifying the actor.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

The source mapping is ready to implement. Effective actor statistics, target-dependent calculations and automatic application of rule elements are excluded; prove supported interfaces and focused live behavior before adding them.

Live source/definition checkpoint evidence is recorded below; acquired-item integration remains open. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.


Selected source and explicit immediate definition links are implemented and
verified; see [fields](../background-fields.md) and
[evidence](../background-verification.md). Actual MCP checks cover three
compendium backgrounds, exact prose and two feat identities with unchanged
source fingerprints. Null/absent choices and configured missing grants remain
explicit without modifying Actors. Source/world/pack/token and stale/denied
cases have deterministic coverage.

The acquired same-Lore/feat multi-contributor acceptance is still open. CORE-build
must join actual owned Items once and preserve every proven contributor;
resolving a definition does not close that requirement. No populated character
fixture exists in the current world. This story remains In progress; its source
checkpoint is usable while other independent build readers proceed. Empty
structured Lore can coexist with descriptive choices, and rare backgrounds can
intentionally lack the ordinary training/grant package. No generic missing-grant
or duplicate-training replacement is inferred from those empty fields.
