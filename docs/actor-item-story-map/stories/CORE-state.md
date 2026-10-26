# CORE-state: Conditions, effects and affliction provenance joins

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 3 |
| Planning readiness | Planned |
| Implementation status | In progress |
| Prerequisites | [ITEM-condition](ITEM-condition.md), [ITEM-effect](ITEM-effect.md), [ITEM-affliction](ITEM-affliction.md) |
| Dependency reason | Needs condition, effect and affliction source identities/status/origins. |

## User outcome and implementation

As a reader, I can distinguish stored state records, their origins and the portions of effective state that are actually supported.

- Join same-owner condition/effect/affliction source relationships and documented external origins. Preserve duration unit, start, expiry timing, badge discriminator, tracked affliction stage and override links.
- Stored presence/recorded stage is not evidence of complete active application. Map unknown/suppressed/unsupported sections explicitly; do not run PF2e preparation or recreate suppression/expiry calculations.
- Avoid duplicating a granted ability with its tracking effect. Missing/deleted origins and overlapping effects remain separate evidence.

Acceptance: valued/unvalued conditions, persistent damage, suppressed-but-present conditions, multiple origins, formula badges, encounter durations and out-of-range stages are covered. Effective suppression, expiry and application require separately proven supported interfaces plus existing live fixtures. Source-only state may proceed without them.

## Evidence and completion

The explicit Actor `state` source view joins actual owned conditions/effects,
typed selected source and immediate local/external provenance. See the
[state contract](../state-contract.md). Overlapping Items remain separate;
application stays unknown. Every result explicitly reports unsupported
affliction reading, including an empty supported collection.

This partial implementation does not pass the remaining affliction dependency
or complete the story. Production PF2e8.6.1 disables affliction construction;
tracked/out-of-range-stage acceptance remains open. Effective suppression,
application and expanded live state-view verification also remain open. Two
existing NPC source-state views now pass independent read-only verification;
see the state contract for exact scope. Serialized owned
effect expiry is selected separately through public `Item.system` and the pinned
`EffectSystemData.expired` own data declaration;
its boolean retains transformed provenance and never establishes application.
missing model data remains unknown even if source/serialization contains a value.
The existing NPC run verifies a present false flag with unchanged source;
expired-true and other Actor/token fixtures remain unverified. The
existing prerequisite graph and original acceptance criteria are unchanged.

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

## Character and expired-true checkpoint — October 25, 2026

A genuine marked world character passed 27 state pages, 173 records, 238 raw
witnesses and 12 resolved relationships in 40 MCP calls. Both expiry booleans,
same-name effects with distinct Item origins, an unevaluated encounter formula
badge and valued/unvalued/persistent-damage conditions matched independent public
document reads. Read fingerprints and exact fixture cleanup passed; see the
[verification record](../state-contract.md#marked-character-state-verification--october-25).
This closes the earlier expired-true/character fixture gap. Effective suppression,
application, familiar/token state and the original affliction prerequisite remain
open. CORE-state stays In progress.

## Existing token-state checkpoint — October 25, 2026

Two existing unlinked token instances passed 10 state pages/51 records, 71 raw
witnesses and two owned Item follow-ups in 67 MCP calls. Actual Actor/base/token
identity, source/current witnesses and origin token context matched independent
public documents; source/current fingerprints stayed unchanged. The sample
included condition/effect Items and a present false expiry flag. See the
[token-state record](../state-contract.md#existing-unlinked-token-state-verification--october-25).
This supersedes the earlier selected token-state source gap, without claiming
effective suppression/application, token expired-true, familiar or affliction support.
