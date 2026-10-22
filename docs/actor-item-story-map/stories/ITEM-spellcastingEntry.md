# ITEM-spellcastingEntry: Spellcasting groups and resource sources

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `spellcastingEntry` Item as **spellcasting groups and resource sources**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 297–299 distinguishes prepared uses, shared slots, focus pools and innate uses; GM Core p. 123 permits creature-specific focus exceptions. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `tradition.value`, `prepared.value`, `prepared.flexible`, `prepared.validItems`, `ability.value`, `proficiency.value`, `spelldc.value`, `spelldc.dc`, `slots`, `autoHeightenLevel.value`.
- Mapping and relationships: Present a named spellcasting group with its mode. Preserve slot records, prepared spell IDs/expended flags and individual quantities as selected source; CORE-casting joins them to spells without flattening resources.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Prepared entries with slot value zero and nonempty preparations are not labelled exhausted.
- Repeated prepared spell IDs retain separate preparations; malformed/legacy records are partial, not coerced.
- Focus, innate and spontaneous entries retain distinct resource meanings.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Pinned interfaces declare `slots.slotN.prepared[]` with `id` and `expended`; the official template also declares slot11 beyond the interface slot0–10 union. Preserve slot11 without rank semantics. Current live preparations are arrays with absent expenditure flags; absence stays absent. Legacy/malformed preparation shapes remain explicitly partial without normalization. Representative supported expenditure checks remain required before claiming usable current resources. DC/attack source values are not final PC statistics.

Selected source/resource configuration and exact descriptions are verified; see [field contract](../spellcasting-entry-fields.md) and [book/runtime evidence](../spellcasting-entry-verification.md). Five live reads cover four modes and a token-context entry, with exact values, absent flags and unchanged source fingerprints. Deterministic fixtures cover independent repeated preparations, zero-value slot interpretation, malformed/legacy partial data, unsupported/denied/stale/system boundaries and Unicode description continuation. Entry-to-spell joins remain CORE-casting; effective resource availability and casting remain unsupported. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.
