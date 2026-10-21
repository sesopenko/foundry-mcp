# CORE-state: Conditions, effects and affliction provenance joins

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 3 |
| Planning readiness | Planned |
| Implementation status | Not started |
| Prerequisites | [ITEM-condition](ITEM-condition.md), [ITEM-effect](ITEM-effect.md), [ITEM-affliction](ITEM-affliction.md) |
| Dependency reason | Needs condition, effect and affliction source identities/status/origins. |

## User outcome and implementation

As a reader, I can distinguish stored state records, their origins and the portions of effective state that are actually supported.

- Join same-owner condition/effect/affliction source relationships and documented external origins. Preserve duration unit, start, expiry timing, badge discriminator, tracked affliction stage and override links.
- Stored presence/recorded stage is not evidence of complete active application. Map unknown/suppressed/unsupported sections explicitly; do not run PF2e preparation or recreate suppression/expiry calculations.
- Avoid duplicating a granted ability with its tracking effect. Missing/deleted origins and overlapping effects remain separate evidence.

Acceptance: valued/unvalued conditions, persistent damage, suppressed-but-present conditions, multiple origins, formula badges, encounter durations and out-of-range stages are covered. Effective suppression, expiry and application require separately proven supported interfaces plus existing live fixtures. Source-only state may proceed without them.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.
