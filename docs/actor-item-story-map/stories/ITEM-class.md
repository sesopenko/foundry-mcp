# ITEM-class: Class definition and progression

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Ready for source milestone |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `class` Item as **class definition and progression**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 91, 194 distinguishes class contribution, advancement and later features. Page 91’s boost amount conflicts with p. 19 in this PDF; record the discrepancy rather than implement arithmetic from it. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/class/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `keyAbility`, `hp`, `perception`, `savingThrows`, `attacks`, `defenses`, `spellcasting`, `trainedSkills`, `items`, `ancestryFeatLevels`, `classFeatLevels`, `generalFeatLevels`, `skillFeatLevels`, `skillIncreaseLevels`.
- Mapping and relationships: Present source class identity, selected key attribute, starting proficiencies and progression separately from current actor values and acquired features. Do not implement advancement or recompute HP.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Later progression references remain future options.
- Class HP contribution is not reported as total actor HP; rank is not a total modifier.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

The source mapping is ready to implement. Effective actor statistics, target-dependent calculations and automatic application of rule elements are excluded; prove supported interfaces and focused live behavior before adding them.

Delivered source/reference verification and remaining live coverage limits are recorded below. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.


Selected class source and immediate progression-feature definitions are
delivered; see [fields](../class-fields.md) and
[verification](../class-verification.md). Raw starting ranks retain numeric
values with rulebook labels, never bonuses. Source HP is a contribution, not
Actor HP. Future definitions and progression are not acquired features or
advancement. Actual MCP verified Fighter/Rogue/Wizard,51 feature references,
exact prose and unchanged source fingerprints. Deterministic tests cover
world/pack/token scope, repeated references, permissions, stale/bounded reads
and non-PF2e rejection. The boost-text discrepancy remains documented without
arithmetic from it. Full suites pass:294 Python tests (one skipped),360 JavaScript
tests. No grants, imports, progression writes or effective calculations occur.
