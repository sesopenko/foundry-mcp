# ACT-familiar: Read familiar and master-linked abilities

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; effective views gated |
| Implementation status | Complete |
| Integrated status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `familiar` Actor in book terminology while preserving identity, selected source, contributing Items and completeness.

- **Rules:** Player Core pp. 212–213, 259: familiar rules build on pet rules, use master relationships and distinguish familiar/master abilities.
- **Schema:** [PF2e 8.6.1 Actor definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts), plus [shared creature source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts).
- **API:** [public Actor/token extraction evidence](../evidence.md#public-foundry-api). PF2e derived declarations do not establish an externally supported effective-stat API.

## Source checkpoint: ACT-familiar

- [x] Extract identity/name/type/UUID and version/source/parent context through CORE-extract. Selected `system` fields: `master.id`, `master.ability`, `attributes.hp.value`, `attributes.hp.temp`, `details.creature.value`; source schema explicitly omits ordinary independent attributes/saves/skills.
- [x] Retain bounded original notes/descriptions and unknown codes. Label every statistic's source/effective basis; do not fill omissions with zeroes. Keep assignment/control separate from subtype.
- [x] Return embedded Item summaries and next-reader links; basic reading must work before individual Item readers and joins are complete.

Source checkpoint verified on Foundry14.369/PF2e8.6.1; see
[field contracts](../familiar-fields.md) and [verification](../familiar-verification.md).
Identity resolves the stored world-character master claim without the system's
master getter. Owned action references remain unclassified: this schema does
not encode familiar/master benefit scope; read their exact Item descriptions.
Integrated acceptance and the remaining capability limits are recorded below
and in the [closure matrix](../familiar-acceptance.md).

## Integrated checkpoint: M-FAMILIAR

Prerequisites beyond the source checkpoint: [ITEM-action](ITEM-action.md), [CORE-state](CORE-state.md), [CORE-casting](CORE-casting.md).

- [x] Resolve the master through the same permission-aware document resolver and expose its identity. Read selected familiar/master abilities as action Items and optional sourced spell/state data. Master-linked values require a supported effective contract; do not fabricate independent attributes or normal Strikes. Ordinary pet/animal/companion roles require explicit evidence beyond name, trait or ownership.
- [x] Support world, compendium and token-instance contexts through CORE-packs/CORE-token adapters when available. Their end-to-end acceptance belongs to CORE-acceptance; they do not block basic world reading.
- [x] Preserve selected raw fields, mapped sections and contributor/source paths side by side, with bounded continuations and explicit unsupported/unread sections.
- [x] Verify supported effective interfaces and existing live fixtures before claiming full current statistics. Source-only delivery does not close this advanced gate.

## Acceptance scenarios

- Missing/deleted/denied master produces a partial familiar response with no fabricated statistics.
- A familiar action and master ability retain their Item identities and descriptions.
- Source HP survives while master-derived saves/skills are marked unsupported until verified.
- Re-resolve the same canonical target through a journal link and direct discovery. World, pack and synthetic Actor/Item identities never substitute for each other.
- Non-PF2e, denied, missing and unsupported-type paths are actionable; no writes, imports, rolls or activations occur.

## Readiness and outstanding gates

### Current-statistics implementation checkpoint — October 25, 2026

Explicit statistics now verifies the recorded world-character master before
declared public model reads, then selects familiar defenses,
movement and ordinary skills. Source master ID/ability remain separate raw
witnesses. Missing/deleted/denied/unassociated/unsupported master returns a
partial source-context response without transformed values. See the
[contract](../familiar-current-contract.md). No private master getter, local
derivation, independent attributes or normal Strikes are used. Item-linked
skills are withheld before exposing their keys or labels.

World/pack/token deterministic checks and actual paginated JavaScript-to-Python
responses pass, including permission/reassignment races. Actual MCP discovery
also passes. Representative world-familiar current data now passes live checks:
127 present fields, zero missing, in 128 records over 64 pages. Source/master,
action descriptions, omission of current rows after master unassignment, and exact fixture cleanup
also pass. See the current contract for 108-call evidence and scope. Compendium/
token current fixtures were not added by that run. This historical checkpoint
did not close the story or certify local recalculation behavior; the subsequent
combined acceptance below closes the declared supported/partial views.

Source and selected current checkpoints are verified as described above.
Combined casting/state composition is now verified deterministically; complete
world/pack/token and journal workflows retain their separate CORE-acceptance gate.
The original research had no populated character/familiar runtime fixture;
subsequent verification is recorded in the linked ledger. v13 PF2e support
remains unverified. See [evidence](../evidence.md#open-verification-gates).

This is one story with two checkpoints, not separate source/effective actor stories. Close it only when the declared delivered sections pass and every remaining advanced limitation is explicitly recorded; never mark an unsupported effective capability verified.

## Integrated acceptance and closure — October 28, 2026

The [closure matrix](../familiar-acceptance.md) checks the original requirements
against production readers, combined JavaScript/Python acceptance at `a87a830`,
and the existing master-linked runtime proof. Master identity, source HP,
ordinary current statistics, exact action prose, optional casting/inventory/state
and unsupported sections coexist in one bounded snapshot. No extra fixture or
new runtime claim is needed to establish that composition.

ACT-familiar and M-FAMILIAR are Complete for these declared supported/partial
views. Full current statistics, Item-linked familiar skills, normal Strikes,
automatic ability classification, pet/companion roles, casting availability and
effective condition suppression/application remain unsupported or unverified as
specified in the contracts. Dedicated affliction functionality is Deferred by
the user's approved scope decision, not implemented or counted complete.
The existing same-base token-pair requirement and full contextual end-to-end
acceptance remain in CORE-token/CORE-acceptance; this closure does not satisfy them.
