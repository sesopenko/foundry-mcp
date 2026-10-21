# CORE-world: World actor discovery and embedded Item navigation

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Lists source identities without waiting for type mapping. |

## User outcome and implementation

As a fresh client, I can discover supported actors in folders, distinguish duplicate names and navigate owned Items.

- Implement the handoff's candidate type-capability, actor-tree, world search and embedded-item list contracts after CORE-contract finalization. Keep world/pack searches explicit.
- Build hierarchy from document folder relationships, retaining empty folders/unfiled actors and folder paths. Do not read sidebar trees or DOM.
- Search scope/type/name semantics and truncation are discoverable; list character/npc/familiar only. A direct excluded-type read remains an actionable unsupported result.
- Enumerate Items with actual parent UUID/type/name and useful relationship labels without requiring every type reader to be implemented.

Acceptance: duplicate names produce candidates; folder cycles/depth/count/byte limits are explicit; empty folders and unsupported/unknown Item types remain distinguishable. An empty scoped search does not establish global absence. Follow returned IDs through source readers without name guessing.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

## Delivery evidence — October 20, 2026

Implemented world Actor folder/navigation and literal scoped search with canonical identities, duplicate names, empty/unfiled folders, depth expansion, byte/count pagination and revision/permission checks. Tests: `tests/js/actor-world.test.js`, `tests/js/actor-dispatch.test.js`, `tests/test_actor_discovery.py`. Existing-runtime HTTP MCP discovery, world tree/search and reader follow-ups passed on Foundry14.369/PF2e8.6.1. This closes discovery only, not type-specific or effective reading.
