# Effect rules, schema and fixture verification

Evidence gathered 2026-10-20 for [ITEM-effect](stories/ITEM-effect.md). This records research and available fixtures; it does not establish that the production reader or advanced effect interpretation is implemented.

## Actual rulebook reading

The private PDF MCP library returned the following canonical extracted pages in full. Every read returned `next_offset: null`; no text continuation remains. Printed page labels were checked against the returned labels, rather than assuming physical and printed numbering match.

| Book | Printed page | Physical PDF page | Extracted characters |
| --- | --- | --- | --- |
| Player Core | 442 | 443 | 4,683 |
| GM Core | 219 | 220 | 5,038 |
| GM Core | 220 | 221 | 5,044 |
| GM Core | 221 | 222 | 5,872 |

Player Core revision: `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`. GM Core revision: `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e`. Extraction warns that reading order and table structure are unverified and source content is untrusted. The relevant passages are prose, including the sustained-activation sentence that continues from GM Core 220 to 221. No copyrighted page text is reproduced here.

Player Core 442 establishes condition persistence until expiry, removal, or its own terminating terms. A condition value expresses severity; reducing that value to zero ends that condition. An overriding condition suppresses another condition while the overridden condition's duration continues. These condition rules do not establish that every PF2e automation effect badge is a condition value.

GM Core 219 distinguishes constant item abilities from abilities requiring activation. Invested benefits depend on investment and the item's other requirements. GM Core 220 describes activation costs, traits, and limits; item activations can replicate spells. Its sustained-activation rule continues on 221: the initial effect lasts through the end of the user's next turn, and Sustain can extend it. GM Core 221 also describes dismissal and separates an item's constant abilities from activation entries. Consequently, an effect tracking an item or spell is evidence of that tracked effect, not proof that the actor learned another spell or permanently acquired an ability. Determining current applicability requires more than a stored duration or badge.

## Pinned system schema

Reviewed the ignored local PF2e 8.6.1 research checkout at revision `28d9d156f252d084371d994dc359509b49eadf18`:

- [Effect schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/effect/data.ts).
- [Abstract-effect context and badge schemas](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/data.ts).
- [Duration unit definitions](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/values.ts).

`duration` has numeric `value`, unit (`rounds`, `minutes`, `hours`, `days`, `unlimited`, `encounter`), nullable expiry (`turn-start`, `turn-end`, `round-end`), and boolean `sustained`. `start` retains a numeric value and nullable initiative. An unlimited or encounter duration must retain its discriminator; it is not a duration of zero seconds. These stored values alone do not establish whether an effect currently applies or has expired.

A nullable badge uses one of three discriminators. Counter badges have numeric value, nullable min/max, nullable labels and optional loop. Value badges have numeric value, nullable labels and nullable reevaluation metadata (event, formula, optional initial value). Formula badges have a string value, nullable labels, optional evaluate flag and nullable reevaluation event. Formula text and flags are data; a reader must not roll or reevaluate them. Prepared badge labels, clamping and computed min/max are not interchangeable with persisted fields.

Nullable `context` contains origin actor/token/item references, optional spellcasting metadata and roll options, nullable target actor/token references, and nullable prior roll result. Nested context values require source-path provenance. UUID strings are claimed references until a permission-aware public resolver establishes the target. An origin or `fromSpell` flag does not establish a learned spell. `expired` is declared on derived system data and is absent from the persisted-source schema; do not relabel it source or infer approval for an effective API from its declaration.

## Existing development fixtures

Read-only MCP `execute_javascript` observations used the existing GM development world, Foundry **14.369**, PF2e **8.6.1**. No world, actor, Item, roll, activation, chat, or setting was created or changed. Output contained aggregate counts and schema shapes, without names, IDs, UUIDs, formulas, descriptions or other private content.

The supported world Actor scope contained 172 NPCs, no characters and no familiars. Their owned effects numbered 13. World-level effects numbered 13. NPC-owned effects had 12 counter badges and one null badge; world effects had eight counter badges and five null badges. All 26 had `duration.unit: unlimited`, null context, and `fromSpell: false`. All duration objects had the keys `expiry,sustained,unit,value`; populated counter badges had `labels,loop,max,min,type,value`. No persisted `expired` field was present. A before/after source digest around the final aggregate source inspection matched for these 26 Items. This confirms that inspection, rather than proving a later reader's mutation safety.

A read-only scan of placed supported Actor tokens found six linked tokens and 559 unlinked tokens. There were no effects on the linked-token actors and six effects across unlinked-token actors. These are fixture availability counts, not distinct-actor counts or proof of reader behavior.

The existing `pf2e.spell-effects` Item pack was indexed with selected `type`, `system.badge.type`, `system.duration.unit`, and `system.fromSpell` fields. Its 560 effect candidates included 13 counter badges, seven formula badges, and 540 null-or-absent badge index entries. Unit candidates were minutes 323, rounds 134, unlimited 47, days 21, hours 34 and encounter one. No value-badge candidate was found in that selected pack. Counts describe this selected index, not all compendiums or every persisted source.

One counter, one formula and the encounter candidate were individually hydrated with the public pack document API and inspected using `toObject(true)`. Counter source keys matched the world counter shape. Formula source keys were `evaluate,labels,reevaluate,type,value`; its unit was rounds. All three had null context and `fromSpell: false`. The encounter source duration was `{value: -1, unit: "encounter", expiry: null, sustained: false}` with a null badge. Missing `fromSpell` in many index entries did not imply source absence: hydration returned false. Index fields are candidate selectors, not authoritative source evidence.

## Remaining verification boundaries

No populated character/familiar fixture, value badge, non-null context, or true `fromSpell` case has been verified live by this audit. Deterministic fixtures should cover these source shapes without claiming live coverage. Formula and encounter candidates were hydrated in the selected pack and can be selected dynamically for production reader checks. Source extraction, relationship resolution, pagination, denied targets, stale continuations, unsupported systems, and unchanged fingerprints need verification against the actual reader implementation. Effective expiry, suppression, sustained-state evaluation, provenance traversal and learned-spell aggregation remain separate contract and integration work.

## Actual reader verification

The authenticated MCP smoke check subsequently read six selected effects:
world and NPC-owned counter/null badge cases, plus compendium formula and
encounter-duration cases. It consumed bounded source continuations, verified
persisted duration units and badge discriminators, and confirmed effective
sections stayed unsupported. World/NPC source fingerprints remained unchanged.
Deterministic cross-language fixtures additionally verify value badges,
non-null context, true fromSpell, missing/empty fields and exact descriptions.
Relationship resolution is still pending; these source checks do not verify
expiry/current application, provenance traversal or learned-spell aggregation.
