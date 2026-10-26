# CORE-state: Conditions and effects provenance joins

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 3 |
| Planning readiness | Planned |
| Implementation status | Complete |
| Prerequisites | [ITEM-condition](ITEM-condition.md), [ITEM-effect](ITEM-effect.md) |
| Dependency reason | Needs condition/effect source identities/status/origins; dedicated affliction functionality is deferred outside current delivery. |

## User outcome and implementation

**Approved scope update — October 25, 2026:** dedicated affliction Items are
incomplete upstream and outside this delivery, per the user's explicit decision.
The original affliction join/stage requirements are retained as future
context in ITEM-affliction; they are not current acceptance blockers.
Existing state responses must continue reporting affliction support as
unsupported, including when no readable condition/effect Items exist.

As a reader, I can distinguish stored state records, their origins and the portions of effective state that are actually supported.

- Join same-owner condition/effect source relationships and documented external origins. Preserve duration unit, start, expiry timing, badge discriminator and override links.
- Stored presence/recorded stage is not evidence of complete active application. Map unknown/suppressed/unsupported sections explicitly; do not run PF2e preparation or recreate suppression/expiry calculations.
- Avoid duplicating a granted ability with its tracking effect. Missing/deleted origins and overlapping effects remain separate evidence.

Acceptance: valued/unvalued conditions, persistent damage, suppressed-but-present conditions, multiple origins, formula badges and encounter durations are covered. Effective suppression, expiry and application require separately proven supported interfaces plus existing live fixtures. Source-only state may proceed without them. Dedicated affliction tracked/out-of-range stages remain deferred in ITEM-affliction.

## Evidence and completion

The explicit Actor `state` source view joins actual owned conditions/effects,
typed selected source and immediate local/external provenance. See the
[state contract](../state-contract.md). Overlapping Items remain separate;
application stays unknown. Every result explicitly reports unsupported
affliction reading, including an empty supported collection.

The declared reading contract is verified; see the
[requirement audit](../state-acceptance.md). Two existing NPCs, a genuine marked
character and two existing unlinked tokens provide scoped live evidence.
Owned effect expiry is selected separately through public `Item.system` and
the pinned `EffectSystemData.expired` own-data declaration. Both boolean values
are verified; transformed provenance never establishes application. Missing own
model data stays unknown without a source/serialization fallback.

The state section remains partial because complete application and suppression
are unsupported. Familiar state and expired-true token configurations remain
unverified live. Story completion accepts this explicit supported/unknown
boundary; it does not certify those advanced capabilities. Dedicated affliction
functionality is deferred under the explicit scope decision above.

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

## Character and expired-true checkpoint — October 25, 2026

A genuine marked world character passed 27 state pages, 173 records, 238 raw
witnesses and 12 resolved relationships in 40 MCP calls. Both expiry booleans,
same-name effects with distinct Item origins, an unevaluated encounter formula
badge and valued/unvalued/persistent-damage conditions matched independent public
document reads. Read fingerprints and exact fixture cleanup passed; see the
[verification record](../state-contract.md#marked-character-state-verification--october-25).
This closed the earlier expired-true/character fixture gap. At that checkpoint,
token verification and the then-required affliction prerequisite remained open;
the later token evidence and approved deferral below supersede those blockers.

## Existing token-state checkpoint — October 25, 2026

Two existing unlinked token instances passed 10 state pages/51 records, 71 raw
witnesses and two owned Item follow-ups in 67 MCP calls. Actual Actor/base/token
identity, source/current witnesses and origin token context matched independent
public documents; source/current fingerprints stayed unchanged. The sample
included condition/effect Items and a present false expiry flag. See the
[token-state record](../state-contract.md#existing-unlinked-token-state-verification--october-25).
This supersedes the earlier selected token-state source gap, without claiming
effective suppression/application, token expired-true, familiar or affliction support.

## Acceptance audit — October 25, 2026

The [requirement matrix](../state-acceptance.md) verifies every current acceptance
case against actual implementation, focused regressions and the recorded live
checks. Stored override claims retain both condition identities with unknown
application, without reading an unestablished activity interface. No extra full
application engine is required by the original supported-portions contract.
CORE-state is Complete; its partial response and capability limitations remain.
