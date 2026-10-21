# ITEM-weapon: Weapon definitions and instance configuration

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | In progress |
| Prerequisites | [CORE-physical](CORE-physical.md) |
| Dependency reason | Uses common physical source rules and identity/bounds. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `weapon` Item as **weapon definitions and instance configuration**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 275, 418 distinguishes weapon properties, Strikes and unarmed attacks; final attacks include actor-dependent modifiers. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/weapon/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `category`, `group`, `baseItem`, `damage`, `range`, `reload.value`, `runes`, `material`, `equipped.handsHeld`, `ammo`, `selectedAmmoId`, selected `subitems`.
- Mapping and relationships: Show source weapon and configuration. Keep final Strikes separate, preserving supported source links; no item UUID is invented for a generated fist or alternate attack.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [ ] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [ ] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [ ] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [ ] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- A carried weapon is not automatically wielded or usable.
- NPC authored attack data is not recalculated from a weapon.
- A non-document nested attachment retains source-path identity.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Effective PC Strikes and alternate-use calculations require a supported system interface and a populated character live check.

No live type-reader MCP implementation has been verified. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.
