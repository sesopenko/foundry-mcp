# CORE-token: Scene discovery and token-instance resolution

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | Not started |
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
