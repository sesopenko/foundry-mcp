# CORE-state acceptance audit

Baseline: Foundry14.369/PF2e8.6.1. This audit closes the declared condition/effect
reading contract, preserving explicit unknown application and unsupported
suppression. The user deferred dedicated affliction Items until upstream support
is complete; their original stage requirements remain in ITEM-affliction.

The original outcome is to distinguish stored records, origins and “the portions
of effective state that are actually supported.” It requires unknown/unsupported
sections to remain explicit and forbids running preparation or recreating expiry
and suppression calculations. Complete active application is not claimed.

| Current requirement | Authoritative evidence |
| --- | --- |
| Actual same-owner state identities, immediate local/external origins and distinct tracking/granting documents | `actorState.js` uses the shared public document/permission boundary and existing condition/effect relationship helpers. `actor-state.test.js` and `actor-state-readers.test.js` assert exact owners, independent origins, duplicate names, source contributors and world/token identity. |
| Valued/unvalued conditions, persistent damage, badge discriminators/formulas, duration/start/expiry timing | Typed condition/effect source selectors retain exact primitives. `validate_fixture_records` in `actor-state-live-check.py` asserts these cases on genuine Documents; the character run passed 173 records and 238 witnesses with unchanged read fingerprints and exact cleanup. |
| Suppressed-but-present records remain distinct from removed records or established activity | The paginated override regression retains both condition identities and resolves reciprocal stored override claims, with application unknown. Its activity getter throws if accessed; the reader invokes it zero times. This proves safe source handling, not a supported effective suppression interface. |
| Separate overlapping effects and multiple origins without duplicating a learned ability | The genuine character fixture has two same-name effects linked to two distinct inert action Items. Both identities and canonical origin links remain; no granting ability is inferred active or copied as a second acquisition. |
| Supported current expiry, separate from application | Own `EffectSystemData.expired` is independently verified true and false on the character. Existing NPC and token samples verify false. Source/serializer omission never supplies a fallback. Strict Python tests reject wrong types, paths, owners or provenance and preserve false versus missing. |
| Permissions, actionable gaps, bounded continuations and staleness | JS state/reader tests and `test_actor_state.py` cover denial without source leakage, unsupported capabilities, 12,000 Items/24,000 records/200 external claims, UTF-8/count pagination, stale source/permission/membership/external identity and model-only expiry changes. Actual MCP discovery and strict DTO checks pass. |
| Existing-runtime verification and read-only behavior | Existing NPCs passed 56 state records/76 witnesses; the marked character passed 173/238; two existing unlinked instances passed 51/71 plus canonical Item follow-ups. Complete selected read fingerprints matched. Fixture setup/cleanup is separately opt-in and tested; the reader never writes, casts, activates or rolls. |

Code paths above are under `foundry-module/scripts/` or `scripts/`; regression
paths are under `tests/js/` or `tests/`. Exact records, limits, runtime counts,
cleanup and proof boundaries are in the [state contract](state-contract.md).

Dedicated affliction stages are outside this delivery, not marked implemented.
Condition activity/suppression, general effect application, familiar live state
and expired-true token configurations remain unsupported or unverified. The
registry records verification limits; state pages retain explicit partial status
and unsupported application/affliction markers. CORE-state is Complete
for this documented reading contract, with no full application claim.
