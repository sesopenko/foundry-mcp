# ACT-character: Read character build and supported current views

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; effective views gated |
| Implementation status | Source implemented |
| Integrated status | In progress |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `character` Actor in book terminology while preserving identity, selected source, contributing Items and completeness.

- **Rules:** Player Core pp. 19, 41, 84, 91, 275, 297–299, 418: build contributions, skills, Strikes and casting are related but distinct.
- **Schema:** [PF2e 8.6.1 Actor definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts), plus [shared creature source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts).
- **API:** [public Actor/token extraction evidence](../evidence.md#public-foundry-api). PF2e derived declarations do not establish an externally supported effective-stat API.

## Source checkpoint: ACT-character

- [x] Extract identity/name/type/UUID and version/source/parent context through CORE-extract. Selected `system` fields: `abilities` (nullable source modifiers), `details.level`, selected identity/biography/languages, `attributes.hp`, `skills.*.rank`, selected `resources`, build choices only where explicitly persisted.
- [x] Retain bounded original notes/descriptions and unknown codes. Label every statistic's source/effective basis; do not fill omissions with zeroes. Keep assignment/control separate from subtype.
- [x] Return embedded Item summaries and next-reader links; basic reading must work before individual Item readers and joins are complete.

## Integrated checkpoint: M-PC

Required book views: identity/build; attributes and defenses (AC, saves, HP); Perception, senses, languages, movement and skills including Lore; Strikes; activated/passive abilities and features; spellcasting; equipment/valuables; supported conditions/current effects. Each section must be supported with provenance or explicitly partial/unsupported. A source snapshot alone does not establish those effective totals.

Prerequisites beyond the source checkpoint: [CORE-build](CORE-build.md), [CORE-casting](CORE-casting.md), [CORE-inventory](CORE-inventory.md), [CORE-state](CORE-state.md), [ITEM-action](ITEM-action.md).

- [ ] Join build selections/features, abilities, Lore, weapons, inventory, spellcasting and state. Preserve total-versus-contribution and source-versus-effective distinctions. Generated Strikes, including basic unarmed, may have no Item UUID. An owned weapon is neither an effective Strike nor an exhaustive action list.
- [ ] Support world, compendium and token-instance contexts through CORE-packs/CORE-token adapters when available. Their end-to-end acceptance belongs to CORE-acceptance; they do not block basic world reading.
- [ ] Preserve selected raw fields, mapped sections and contributor/source paths side by side, with bounded continuations and explicit unsupported/unread sections.
- [ ] Verify supported effective interfaces and existing live fixtures before claiming full current statistics. Source-only delivery does not close this advanced gate.

## Acceptance scenarios

- Null source attributes are not zeroes and rank is not a total modifier.
- Future class grants do not appear acquired; same benefit can link several contributors without duplication.
- Weapon source damage is not final PC Strike damage; unsupported effective views are explicit.
- Re-resolve the same canonical target through a journal link and direct discovery. World, pack and synthetic Actor/Item identities never substitute for each other.
- Non-PF2e, denied, missing and unsupported-type paths are actionable; no writes, imports, rolls or activations occur.

## Readiness and outstanding gates

Source checkpoint is ready after shared contracts/extraction. Integrated source joins are specified; effective statistics remain gated by supported-interface evidence and representative live fixtures. No populated character/familiar was live-verified in the original research, and no browser is connected in this audit. v13 PF2e support is unverified. See [evidence](../evidence.md#open-verification-gates).

This is one story with two checkpoints, not separate source/effective actor stories. Close it only when the declared delivered sections pass and every remaining advanced limitation is explicitly recorded; never mark an unsupported effective capability verified.

## Source checkpoint delivered — October 23, 2026

The [field contract](../character-fields.md) and
[verification](../character-verification.md) record selected source, opt-in
bounded biography, strict mappings and world/pack/token identity tests.
`list_actor_items` supplies bounded owned summaries and canonical `read_item`
follow-ups independently of concrete readers. Build, inventory, source casting
and Lore sections retain their separate completeness contracts.

Actual MCP verified a marked temporary character in the existing development
world: 51 source/description records across eight pages, default biography
privacy, null attributes, source rank/resource/choice distinctions and unchanged
source fingerprints. Cleanup was confirmed. This closes the source checkpoint,
not M-PC or the story. Current statistics, generated Strikes and state remain
open; the [transformed-document proposal](../current-statistics-contract.md)
identifies the next public extraction candidate without claiming implementation.

## Selected current-statistics checkpoint — October 23, 2026

Explicit statistics now selects verified transformed attributes, AC/HP, saves,
Perception/vision and movement through the public serializer, alongside separate
source records. The [contract](../current-statistics-contract.md) and
[verification](../current-statistics-verification.md) supersede the earlier
proposal-only status for this subset. A populated marked character supplied
47 actual MCP records over seven pages with unchanged source and confirmed cleanup.

The section remains partial. Skills/Lore totals, senses/languages, IWR, generated
Strikes, state and complete integrated current views remain open; this checkpoint
does not close M-PC or mark the story Complete.

## Declared current Strike checkpoint — October 25, 2026

Explicit Strikes now reads selected public `Actor.system.actions` own data,
including generated attacks without owned Items, alternative usages and exact
bounded text. A genuine marked character with zero owned Items supplied a
generated unarmed Strike and six getter-backed MAP capabilities without invoking
their getters or inventing an Item UUID. Source fingerprints and cleanup passed.
See the [current Strike contract](../strike-current-contract.md). Current damage,
target eligibility and non-Strike kinds remain unsupported; shared casting/state
dependencies and full M-PC acceptance remain open.

## Owned ability navigation checkpoint — October 25, 2026

Explicit abilities now joins actual owned action and feat/feature Item identities
with exact persisted name/type provenance and canonical follow-ups. Duplicate
names remain distinct; denied Items expose one aggregate without source/name
access. Basic/generated/prose-only abilities and active benefits remain outside
this partial list. See the [contract](../character-abilities-contract.md).

A genuine marked world character passed three references and all source/prose
follow-ups across one Actor page and 13 Item pages, with 75 independent source
checks in 24 MCP calls. Fingerprints and exact cleanup passed. Strict Python
validation covers actual paginated JS responses and self-contained discovery.
This delivers the previously missing ability-navigation join. It does not close
M-PC: combined-section integration acceptance remains required. Casting and
condition/effect shared prerequisites are now Complete; affliction is Deferred.
