# ITEM-melee: NPC attacks and Strikes

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `melee` Item as **npc attacks and strikes**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 418, 303 separates Strikes from spell attacks; GM Core pp. 119–120 describes authored creature attack bonuses/damage. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/melee/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. The implemented [exact field registry](../melee-fields.md) finalizes this allowlist against the pinned source. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `action`, `area`, `bonus.value`, `damageRolls`, `traits.value`, `range.increment`, `range.max`, `attackEffects.value`, `subjectToMAP`.
- Mapping and relationships: Label only `action=strike` records Strikes; preserve other attack modes explicitly. Show melee/ranged context, separate damage components and additional-effect labels. NPC attacks are authored records, independent of carried weapons.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- A ranged attack stored as `melee` remains ranged; a non-Strike attack is not renamed Strike.
- Preserve mixed damage types/categories and non-UUID effect labels. A carried matching weapon does not replace authored damage.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

All attack-mode variants need representative fixtures. Effective elite/weak and target-dependent attack math remain gated; source bonus/damage is safe to expose.

The selected source reader passed live MCP checks on Foundry14.369/PF2e8.6.1. Non-Strike modes have representative deterministic fixtures but no live sample; v13 and future releases remain unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.

## Delivery evidence — October 20, 2026

`read_item` preserves authored attack mode, bonus, range/area, separate damage components, traits and named effect labels. Only action=strike maps to Strike. Null source range maps to no_explicit_range, retaining thrown traits and an explicit limitation rather than claiming exclusive melee capability. Matching carried weapons never replace authored data; no roll, import, activation, enrichment, MAP or elite/weak calculation occurs.

Pure selector, browser integration and actual JS-to-Python DTO tests cover every declared mode, unknown codes, escaped map keys, mixed damage/categories, absent/null/zero/empty values, UUID-looking labels without resolution, exact descriptions, limits/staleness, unsupported systems/effective sections, and relationship-only section isolation. Empty/absent additional-effect arrays retain distinct raw markers.

Live actual MCP checked explicit ranged source, null range with thrown trait, additional-effect labels and an embedded attack on a hydrated compendium NPC. Source fingerprints stayed unchanged. The wider read-only source audit covered 202 existing attacks; all were Strikes. No live non-Strike or standalone world-attack fixture was available; those source paths have deterministic schema/identity coverage and no complete effective-mechanics claim.
