# CORE-token: Scene discovery and token-instance resolution

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | In progress |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Adds instance-correct resolution to the shared extraction pipeline. |

## User outcome and implementation

As a GM reader, I can select a placed token and read its current linked/synthetic actor without receiving a different base template.

- Enumerate a selected scene's token documents with names, scene/token selectors, actual `token.actor`, separate `token.baseActor` identity, and link state using public APIs after world readiness.
- Feed the resolved Actor into the same extraction/type-reader pipeline. Preserve the actual token Actor and embedded Item UUIDs; never concatenate guessed identities or merge ActorDelta manually.
- Define revision inputs that detect relevant actor/token/master changes across continued or joined reads. Report deleted token, missing actor/base, unsupported type and permission errors explicitly.

Acceptance: two unlinked tokens from one base retain different HP/Items/identities; linked tokens point to their world actor; reading an inactive scene does not require canvas objects. Readiness and missing-master behavior are explicit. No new instance, synthetic actor creation or document updates.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

## Navigation checkpoint — October 20, 2026

### Reader acceptance evidence added October 25, 2026

`tests/js/actor-token-readers.test.js` verifies the complete inactive-scene
discovery → Actor read → owned Item listing → Item read flow. Two unlinked
tokens share one base but preserve distinct source HP (7/19), current HP (5/17),
actual Item UUIDs and duplicate local Item IDs. Linked controls retain world
Actor/Item identities. Canvas access throws in the fixture; source fingerprints
remain unchanged. Selected token/Actor/Item changes invalidate continuations.

Token-selected familiar tests separately resolve two recorded masters, preserve
missing/null/absent/denied states and reject stale master identity/permission
changes. Unrelated master state and master HP do not invalidate identity/source
reads that never select those values. Master-derived statistics stay unsupported.
These deterministic checks close the prior reader-regression gap. Existing live
evidence still covers only one synthetic NPC's current values; a read-only
comparison of two existing same-base tokens remains pending GM connectivity.
No token or synthetic Actor was created or modified. CORE-token stays In progress.

`list_scene_actors` now navigates readable scenes and placed linked/synthetic tokens without canvas access. Missing Actors/base Actors, unsupported counts, permissions and stale continuations are explicit. Focused JavaScript and Python cross-language tests plus existing-runtime MCP navigation passed. Full acceptance remains open: type-specific readers must demonstrate distinct synthetic HP/Items and any relevant master dependencies; identity-only tests do not establish those values.
