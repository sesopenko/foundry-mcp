# Current casting resources and contextual options

Implemented contract for selected CORE-casting resources. The
[acceptance audit](casting-acceptance.md) records story completion and the
remaining unsupported advanced capabilities. Baseline: Foundry14.369 /
PF2e8.6.1, upstream revision `28d9d156f252d084371d994dc359509b49eadf18`.

`actorCastingCurrent.js` prepares a pure detached-data selector, covered by
`tests/js/actor-casting-current.test.js`. The explicit Actor `spellcasting`
reader now integrates it with strict Python validation and packaged runtime
dependencies. Deterministic tests establish field selection, provenance and
pagination behavior. Two existing NPCs now pass representative current-resource
verification; character/familiar coverage and complete availability remain open.
Independent contextual-option verification is recorded in the
[option contract](casting-options-contract.md#independent-live-verification--october-25).

## Public serialization boundary

The official [Actor toObject documentation](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject)
defines `toObject(false)` as selecting transformed document values. The analogous
Item document boundary was also verified through the official v14 indexed API
documentation before integration. These reads
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

Implemented records use key `spellcasting:current:<document UUID>:<path>`,
mapping `pf2e.actor.casting-current.v1`, and limitation
`casting_availability_not_evaluated`. Concepts are `current_focus_points`,
`current_focus_pool_maximum`, `current_focus_pool_cap` and
`current_spell_focus_point_cost`. Missing fields map to null while preserving
`present: false` and add `current_fields_unavailable` to section reasons.
The section remains partial with `availability_not_evaluated`. Familiar-owned
spell costs use the same spell schema; familiar Actor focus remains excluded.

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

## Existing NPC resource verification — October 25

The bounded live runner passed on two existing NPCs, covering prepared,
spontaneous, innate and focus modes plus current focus pools and spell focus
costs. It retained 171 spellcasting pages, 1,052 records and 57 selected current
records, plus 46 source/default pages. Returned current presence and values
matched independent public serialization; source fingerprints and selected
current snapshots remained unchanged. Character/familiar current resources,
final ranks, signature alternatives and complete availability remain unverified.

The run made 323 requested / 322 completed MCP calls. One legitimate record
exceeded the initial 8,000-byte budget at page 102. Following `ResponseTooLarge`
recovery, the verifier discarded 101 prior pages and restarted that section at
48,000 bytes without its old cursor or revision. Five offline tests cover this
bounded single retry, UTF-8 limits, stale revisions and secret-free diagnostics.
The smaller-budget failure was a caller-limit condition, not an empty result or
proof of a Foundry API failure. No world data was written.

## Advanced contextual limitations

Current resource counts alone do not prove contextual options. Preserve the original
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

Implemented contextual-option records join actual spell/entry identities,
mode, preparation position where applicable, definition/configured/slot rank
and resource contributors. Preserve explicit unresolved claims. Option keys
are response-local identifiers, never document UUIDs or mutation selectors.
Prepared repeated uses stay separate. A spontaneous repertoire record can
retain its recorded signature flag without inventing signature rank alternatives.
Innate uses belong to the individual spell, while ordinary spontaneous slots
and focus resources belong to their shared entry/Actor. A focus entry without
a focus trait must not acquire a fabricated consumption cost.

Canonical Player Core printed 99 and 297–299 have now been re-read completely;
see the [October 25 evidence](casting-verification.md). The class feature permits
signature heightening and lower-rank versions, while a recorded signature flag
alone does not establish acquired feature eligibility. Runtime
rank getters and sheet collection builders may explain upstream behavior but
are not adopted by this contract. Automatic-heightening source overrides must
remain separate until their exact rulebook mapping is verified.
