# CORE-token: Scene discovery and token-instance resolution

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | Blocked |
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
reads that never select those values. These identity/source tests do not prove
master-derived statistics. They close the prior reader-regression gap. Existing
live evidence covers individual synthetic NPC current values; the qualifying
two-token comparison remains open under the fixture gap recorded below.
No token or synthetic Actor was created or modified. CORE-token stays In progress.

The October 25 read-only harness subsequently scanned 50 existing Scenes and
778 placed tokens across character/NPC candidates. Linked and inactive controls
were available, but the required same-base pair with distinct HP and meaningful
Item state was absent from that eligible scope. The explicit coverage-gap result
does not close this story. See [token verification](../token-verification.md) for
the bounded selection, deterministic harness checks and unchanged original gate.

`list_scene_actors` now navigates readable scenes and placed linked/synthetic tokens without canvas access. Missing Actors/base Actors, unsupported counts, permissions and stale continuations are explicit. Focused JavaScript and Python cross-language tests plus existing-runtime MCP navigation passed. Full acceptance remains open: type-specific readers must demonstrate distinct synthetic HP/Items and any relevant master dependencies; identity-only tests do not establish those values.

### Original-criteria correction and concrete fixture blocker — October 25

The verifier no longer requires different Item definition contents or unequal
stored and current HP simultaneously. Those were extra probe conditions, not
original acceptance requirements. Distinct actual owned Item UUIDs, membership,
source follow-ups and cross-token rejection establish document separation even
when definitions match. Current HP must still differ for the required pair.

The corrected read-only census found 559 supported unlinked token Actors across
117 eligible base-Actor groups, with **zero groups containing distinct current
HP**. Owned membership/UUID checks excluded no candidates. The original live
pair is therefore unavailable; no token or Actor was created or changed.
CORE-token is Blocked on that fixture, not on different Item contents. Existing
unlinked-token state reads separately passed; see [token verification](../token-verification.md).
