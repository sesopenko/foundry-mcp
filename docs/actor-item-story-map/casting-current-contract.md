# Current casting resources and contextual options

Implementation contract for the remaining CORE-casting work. This does not
declare the story complete or certify live behavior. Baseline: Foundry14.369 /
PF2e8.6.1, upstream revision `28d9d156f252d084371d994dc359509b49eadf18`.

`actorCastingCurrent.js` prepares a pure detached-data selector, covered by
`tests/js/actor-casting-current.test.js`. It is not connected to published
readers or the packaged runtime yet. Its passing tests establish field
selection and validation only; runtime delivery remains subject to the gates
below. Existing tool behavior and completed-story count are unchanged.

## Public serialization boundary

The official [Actor toObject documentation](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject)
defines `toObject(false)` as selecting transformed document values. The analogous
Item document boundary must be checked before runtime integration. These reads
must use selected own data properties, preserve missing values, and never invoke
PF2e preparation, sheet data builders, getters or casting methods.

Pinned upstream document-data contracts permit the following selected leaves:

| Document | Transformed path | Contract and meaning |
| --- | --- | --- |
| Character, NPC | `/system/resources/focus/value` | Finite number; current pool value, separately labelled from source. |
| Character, NPC | `/system/resources/focus/max` | Finite number; current pool maximum. Character source explicitly excludes this field. |
| Character, NPC | `/system/resources/focus/cap` | Finite number; system capacity, distinct from current pool maximum. |
| Spell Item | `/system/cast/focusPoints` | Integer 0–3; prepared casting focus cost, distinct from entry mode and the spell's focus trait. |

Contracts: [CharacterResources](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts),
[CreatureResources](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts),
and [SpellSystemData / SpellCastData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts).
Do not impose undocumented integer or 0–3 constraints on Actor fields declared
as numbers. Reject booleans and nonfinite values. Familiar resources require a
separate familiar document-data contract; creature inheritance alone is insufficient.

## Integration and verification requirements

Keep current-resource records separate from existing
`pf2e.actor.casting-source.v1` records. Use `basis: transformed` for both raw and
contributor provenance, an explicit current-resource mapping and distinct keys.
Do not silently switch existing source records to current values or replace an
absent current field with source. Include every selected current value in the
revision snapshot, so current-only changes invalidate continuations.

Python must validate the exact path/type/document-owner contract and provenance,
including spell Item relationships within the selected Actor/token context.
Discovery must state current-resource support and its exclusions independently
of source support. Missing serialized fields require explicit incomplete reasons.
Source-only and default identity/source reads must not serialize current data.

Before claiming runtime support, compare returned values with the public
serializer in representative existing or marked temporary authorized fixtures;
preserve source fingerprints, consume all pages and confirm cleanup. Cover
zero versus absent, character source max exclusion, nonplain own-data containers,
inherited/getter rejection, malformed values, permissions and current-only stale
continuations deterministically. Do not substitute a passing mock for that live gate.

## Contextual options still required

Current resource counts do not complete CORE-casting. Preserve the original
[story acceptance](stories/CORE-casting.md) and [rulebook evidence](casting-verification.md).
Prepared options must retain individual preparation positions and expenditure
flags; a generic zero slot counter cannot erase them. Spontaneous options must
distinguish known/configured cast rank from the rank of a slot spent. Spending
a higher slot does not itself heighten a spell; signature exceptions require
explicit evidence. Cantrip/focus automatic heightening and innate granted ranks
have distinct contracts. Missing use counters remain unknown, not unlimited.
Flexible, ritual, item casting and unknown modes retain explicit boundaries.

Availability must remain unevaluated until all required mode-specific evidence
and representative live verification are satisfied. Resource sufficiency alone
does not establish actions, components, targets, requirements or spell legality.

The next contextual-option record should join actual spell/entry identities,
mode, preparation position where applicable, definition/configured/slot rank
and resource contributors. Preserve explicit unresolved claims. Option keys
are response-local identifiers, never document UUIDs or mutation selectors.
Prepared repeated uses stay separate. A spontaneous repertoire record can
retain its recorded signature flag without inventing signature rank alternatives.
Innate uses belong to the individual spell, while ordinary spontaneous slots
and focus resources belong to their shared entry/Actor. A focus entry without
a focus trait must not acquire a fabricated consumption cost.

The existing evidence paraphrases do not establish the precise signature
exception well enough to generate all alternatives. Re-read canonical Player
Core printed 297–299 and the signature passages before that expansion. Runtime
rank getters and sheet collection builders may explain upstream behavior but
are not adopted by this contract. Automatic-heightening source overrides must
remain separate until their exact rulebook mapping is verified.
