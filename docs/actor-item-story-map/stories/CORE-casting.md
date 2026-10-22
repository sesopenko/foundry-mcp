# CORE-casting: Spell/group/resource joins

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 3 |
| Planning readiness | Planned |
| Implementation status | In progress |
| Prerequisites | [ITEM-spell](ITEM-spell.md), [ITEM-spellcastingEntry](ITEM-spellcastingEntry.md) |
| Dependency reason | Needs spell definitions and casting group/resource source records. |

## User outcome and implementation

As a reader, I can distinguish listed spells, casting options and recorded resources in the selected actor instance.

- Join `spell.location.value` and prepared spell IDs within the same actor/token snapshot; preserve unassigned/missing/wrong-type relationships. Do not depend on completion of any actor-specific presentation story.
- Keep base rank, configured heightened/cast rank and slot rank distinct. Present prepared repeated uses/expended flags, spontaneous repertoire/shared slots, innate per-spell uses, focus shared pool and cantrip context separately.
- Select actor resource source paths from the pinned schema: character `resources.focus.value` is persisted while `max` is excluded from that character source interface; creature source allows an optional focus value/max record. Do not pretend a prepared capacity is a persisted character field. Creature focus exceptions retain source context; missing resource data means unknown, not exhausted or unlimited.
- Keep ritual/flexible/item-casting identities and source text, with explicit partial sections until verified. Contained consumable spell mapping is optional after ITEM-consumable and ITEM-spell, not a recursive dependency.

Acceptance: repeated preparations, zero generic slot counter, legacy string/object preparation data, signature exceptions, shared focus pool, innate cantrip and absent entry are covered. Reading never casts/prepares/rolls. Before claiming complete current availability, verify a representative existing live entry per supported mode. Unsupported modes do not block safe spell-definition reading.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

## Implemented source checkpoint — October 22, 2026

The explicit Actor `spellcasting` section now returns actual group/spell references,
selected stored resources, same-owner assignment and per-index preparation joins,
and persisted focus fields. See [field contract](../casting-fields.md) and
[rulebook/runtime verification](../casting-verification.md). Repeated preparations,
zero counters, legacy malformed partial data, signature flags, separate ranks,
innate cantrip traits, unknown focus and absent/mismatched entries have deterministic
coverage. Live source reads cover four contexts across the four common modes and
a scene token; exact identities, joins, focus values and source fingerprints match.

This does not complete CORE-casting. Availability remains `not_evaluated` and the
section remains partial; explicit contextual option presentation, including
signature/heightening distinctions and specialized-mode boundaries, remains work.
The original acceptance condition applies before any claim of complete current
availability; it does not authorize casting or expenditure tests that write state.
No casts, preparation, rolls or writes occur.
