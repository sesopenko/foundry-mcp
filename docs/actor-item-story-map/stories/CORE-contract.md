# CORE-contract: Shared read contracts, identity and permissions

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Contract design required |
| Implementation status | Not started |
| Prerequisites | None; start here. |
| Dependency reason | No prerequisite; settle shared contracts and version boundaries first. |

## User outcome and implementation

As a fresh GM-trusted MCP client, I can discover the supported type/source/section matrix and use every selector and continuation without prior exploration.

- Finalize typed world/compendium/scene-token selectors and embedded Item selection. Use returned canonical UUIDs and explicit relative-origin context; names are search inputs, never unique read selectors. Never synthesize a UUID for a generated statistic or nested source object.
- Finalize `identity`, selected `raw`, `mapped`, provenance/completeness sections and uniform unsupported/partial/error semantics. Separate source/transformed/supported effective values, allowed types/supported types, and actor subtype/narrative role.
- Finalize reader defaults, section names, bounded counts, UTF-8 response bytes, source expansion limits, exact continuation fields and stale-result behavior. Include a concrete request/response example for world, pack and unlinked token before coding. Reuse journal conventions where appropriate, without asserting its cursor format is a new public contract.
- Define explicit document/pack permission checks using the authenticated GM identity. Never trust caller role claims; reject non-PF2e semantics, unsupported types, missing or denied targets distinctly.
- Publish a version/section support matrix: PF2e 8.6.1 requires core 14; core v13 API similarity does not establish a supported PF2e v13 pairing. Either verify a pinned compatible v13 system or explicitly declare the new capability unavailable there; any manifest policy change needs its own reviewed implementation decision.

Acceptance: schemas and discovery descriptions are concrete and agree; every input/default/bound/recovery path is documented; duplicate names, unsupported systems and denied targets have deterministic cases. No tool implementation is required to complete the contract artifact itself.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.
