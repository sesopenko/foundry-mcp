# ACT-familiar: Read familiar and master-linked abilities

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; effective views gated |
| Implementation status | Not started |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `familiar` Actor in book terminology while preserving identity, selected source, contributing Items and completeness.

- **Rules:** Player Core pp. 212–213, 259: familiar rules build on pet rules, use master relationships and distinguish familiar/master abilities.
- **Schema:** [PF2e 8.6.1 Actor definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts), plus [shared creature source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts).
- **API:** [public Actor/token extraction evidence](../evidence.md#public-foundry-api). PF2e derived declarations do not establish an externally supported effective-stat API.

## Source checkpoint: ACT-familiar

- [ ] Extract identity/name/type/UUID and version/source/parent context through CORE-extract. Selected `system` fields: `master.id`, `master.ability`, `attributes.hp.value`, `attributes.hp.temp`, `details.creature.value`; source schema explicitly omits ordinary independent attributes/saves/skills.
- [ ] Retain bounded original notes/descriptions and unknown codes. Label every statistic's source/effective basis; do not fill omissions with zeroes. Keep assignment/control separate from subtype.
- [ ] Return embedded Item summaries and next-reader links; basic reading must work before individual Item readers and joins are complete.

## Integrated checkpoint: M-FAMILIAR

Prerequisites beyond the source checkpoint: [ITEM-action](ITEM-action.md), [CORE-state](CORE-state.md), [CORE-casting](CORE-casting.md).

- [ ] Resolve the master through the same permission-aware document resolver and expose its identity. Read selected familiar/master abilities as action Items and optional sourced spell/state data. Master-linked values require a supported effective contract; do not fabricate independent attributes or normal Strikes. Ordinary pet/animal/companion roles require explicit evidence beyond name, trait or ownership.
- [ ] Support world, compendium and token-instance contexts through CORE-packs/CORE-token adapters when available. Their end-to-end acceptance belongs to CORE-acceptance; they do not block basic world reading.
- [ ] Preserve selected raw fields, mapped sections and contributor/source paths side by side, with bounded continuations and explicit unsupported/unread sections.
- [ ] Verify supported effective interfaces and existing live fixtures before claiming full current statistics. Source-only delivery does not close this advanced gate.

## Acceptance scenarios

- Missing/deleted/denied master produces a partial familiar response with no fabricated statistics.
- A familiar action and master ability retain their Item identities and descriptions.
- Source HP survives while master-derived saves/skills are marked unsupported until verified.
- Re-resolve the same canonical target through a journal link and direct discovery. World, pack and synthetic Actor/Item identities never substitute for each other.
- Non-PF2e, denied, missing and unsupported-type paths are actionable; no writes, imports, rolls or activations occur.

## Readiness and outstanding gates

Source checkpoint is ready after shared contracts/extraction. Integrated source joins are specified; effective statistics remain gated by supported-interface evidence and representative live fixtures. No populated character/familiar was live-verified in the original research, and no browser is connected in this audit. v13 PF2e support is unverified. See [evidence](../evidence.md#open-verification-gates).

This is one story with two checkpoints, not separate source/effective actor stories. Close it only when the declared delivered sections pass and every remaining advanced limitation is explicitly recorded; never mark an unsupported effective capability verified.
