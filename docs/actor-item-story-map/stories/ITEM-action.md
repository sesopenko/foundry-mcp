# ITEM-action: Actions, reactions and passive abilities

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Ready for source milestone |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `action` Item as **actions, reactions and passive abilities**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 15, 414 distinguishes actions/activities, reactions and free actions; pp. 212–213 includes familiar abilities. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. The implemented [exact field registry](../action-fields.md) finalizes this allowlist against the pinned source. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `actionType.value`, `actions.value`, `category`, `frequency`, `selfEffect.uuid`, `selfEffect.name`, `traits.value`.
- Mapping and relationships: Use the activation discriminator, not null count, to label activation. Preserve trigger, requirements and exceptions in source descriptions; link self-effects without applying them.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [x] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Passive, free action and reaction with null counts stay distinct.
- A familiar action is an ability, and a self-effect reference causes no activation.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

The source mapping is ready to implement. Effective actor statistics, target-dependent calculations and automatic application of rule elements are excluded; prove supported interfaces and focused live behavior before adding them.

The selected source and explicit relationship reader passed live MCP checks on Foundry14.369/PF2e8.6.1; v13 system compatibility and future releases remain unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.

## Delivery evidence — October 20, 2026

`read_item` maps activation kind independently from nullable action count, preserves selected raw frequency/traits/publication and named self-effect source, and resolves only an explicitly requested immediate relationship. Resolved synthetic references return their revalidated token_uuid so clients can follow them without base-Actor substitution. Rules/effective benefits remain unsupported, never implicitly evaluated.

Pure helper, browser reader and actual JavaScript-to-Python DTO tests cover activation/null-count distinctions, unknown codes, schema-optional undefined values, stale/permission boundaries, bounded exact descriptions, ordinary/synthetic target follow-ups and no hydration during source-only reads. Live MCP verified four activation kinds, familiar pack identity/category, existing token action identity and a self-effect follow-up. Selected action/self-effect/token source fingerprints stayed unchanged. No standalone world action or live synthetic self-effect-target fixture was available; those paths have deterministic public-boundary coverage, without claiming complete familiar/Actor derived support.
