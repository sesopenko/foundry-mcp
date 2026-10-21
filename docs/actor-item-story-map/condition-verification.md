# Condition rules, schema and fixture verification

Evidence gathered 2026-10-20 for ITEM-condition. This research establishes source contracts and available fixtures; it does not establish that a production reader or effective condition interpretation is implemented.

## Actual rulebook reading

The private PDF MCP library returned Player Core printed pages 442 and 445 in full, physical PDF pages 443 and 446 respectively. Returned lengths were 4,683 and 5,246 characters. Both returned `next_offset: null`; no continuation remains. Returned page labels were checked. Book revision: `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`. Extraction warns of unverified reading order/table structure and untrusted source content. No page text is reproduced here.

Page 442 distinguishes a condition's existence from its current effects. Conditions persist until their duration, removal, or their own terminating terms end them. Numeric condition values express severity; reducing a value to zero ends the condition. An overriding condition suppresses another's effects while the overridden condition's duration continues. A stored condition Item therefore does not by itself prove current application.

Page 445 establishes persistent damage as a separate condition shape: damage amount/formula and damage type, end-of-turn damage with fresh dice each time, followed by a default DC 15 recovery flat check. Attack or save outcomes can double or halve damage. Appropriate assistance can allow an additional recovery check, reduce its DC, or end the condition; the GM adjudicates assistance and automatic expiry (usually one minute). Different damage types can coexist; same-type persistent damage uses the higher amount, with GM choice where comparison is unclear. A reader must preserve formula/type/DC/critical-hit metadata without rolling, calculating a replacement winner, applying damage, or asserting recovery/current activity. The default DC is a rulebook baseline, not permission to overwrite stored DC.

## Pinned source schema and prepared-state boundary

Reviewed the ignored PF2e 8.6.1 research checkout at revision `28d9d156f252d084371d994dc359509b49eadf18`:

- [Condition source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/condition/data.ts).
- [Condition document implementation](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/condition/document.ts).
- [Condition collection implementation](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/conditions.ts).

Source includes boolean `fromSpell`, nullable string `group`, traits/otherTags, and `value` containing boolean `isValued` plus nullable numeric `value`. Preserve the discriminator and exact stored number/null. Do not coerce an unvalued condition to zero or interpret inconsistent source as an effective value. Prepared base data normalizes valued numbers and builds badge/name values, so prepared names/badges are not source substitutes.

Nullable `persistent` contains string `formula`, damage-type discriminator `damageType`, numeric `dc`, and boolean `criticalHit`. Derived `damage` roll and `expectedValue` do not belong to this persisted schema. The schema prepares an unlimited duration separately; a reader must not invent persisted duration fields from that preparation step.

`references.parent` is null or an object with `id`. The `children`, `overrides`, and `overriddenBy` arrays contain objects with `id` and a `type` discriminator fixed to `condition`. These are Item reference claims, not UUIDs and not already resolved identities. Parent references can identify a granting Item of another type: the document implementation checks its actor's Items without restricting the parent type. Permission-aware resolution must remain within the actual owner and validate the target. Standalone Items have no implicit Actor owner. Separately, top-level `system.overrides` is an array of condition keys; these are semantic suppression declarations, not Item IDs. Preserve this distinction and do not resolve such keys by display-name matching.

No supported externally callable read-only active/suppression interface was established by this audit. `ConditionPF2e.active` is declared on the document, assigned during base preparation, and changed during sibling preparation. That preparation also appends `references.overriddenBy` and changes ignored rule state; thus even a field name present in both source and prepared data can have different evidence. `ActorConditions.active`, condition `badge`, `breakdown`, `appliedBy`, `isLocked`, and persistent expected-value getters/fields appear in implementation but were not established as supported external contracts. Do not adopt them from this implementation inspection. Current applicability/suppression must remain explicitly unsupported until a separately verified public system interface is recorded; raw source relationships are not its replacement.

## Existing development fixtures

Read-only native MCP observations reused the authenticated GM world, Foundry **14.369**, PF2e **8.6.1**. No document, setting, world, chat, roll, condition, or damage state was created or changed. Output was limited to aggregate counts and schema shapes, without document names, IDs, UUIDs, formulas or private text.

World Actors in supported scope: 172 NPCs, zero characters, zero familiars. Their owned Items contained one condition: valued, null persistent metadata, null parent, and empty children/reference-overrides/overriddenBy/top-level-overrides arrays. No `active` source field existed. World-level condition Items numbered zero. Before/after serialization of these selected sources was identical. This establishes inspection safety, not production reader mutation safety.

A selected index of `pf2e.conditionitems`, requesting `type`, `system.value.isValued`, `system.persistent`, and `system.overrides`, returned 43 condition candidates: 12 valued, 31 unvalued, zero non-null persistent candidates, and eight with nonempty top-level overrides. Index results are selectors, not authoritative source substitutes.

Three candidates (valued, unvalued, top-level-overrides) were individually hydrated through the documented public UUID resolver and inspected with `toObject(true)`. All had value keys `isValued,value`, null persistent metadata, and reference keys `children,overriddenBy,overrides,parent`; no active source field. The valued sample had a numeric value, the unvalued sample null. All had null parent and empty reference arrays. The overrides sample had four top-level semantic override keys. No candidate content or identities were emitted by the audit.

## Verification still required

No populated character/familiar, world-level condition, non-null persistent metadata, populated parent/child/reference override, or actually suppressed-condition fixture was available in this scoped audit. Placed-token conditions and other packs were not audited. Deterministic fixtures must cover these cases and distinguish source contracts from live coverage. Actual production source/relationship readers still need bounded continuation, denied/missing/wrong-type targets, stale permission/membership, token context, exact description, non-PF2e, and unchanged-source checks. This audit does not close current-state, suppression, grant-provenance or integrated Actor acceptance gates.

## Actual source reader verification

The authenticated MCP smoke check subsequently consumed bounded source pages for
four samples: the existing NPC-owned condition, valued and unvalued compendium
conditions, and a compendium override-slug candidate. Exact stored valued flags,
nullable values and override slugs matched the hydrated persisted source.
Effective sections stayed unsupported and world/NPC source fingerprints stayed
unchanged. Populated persistent metadata and reference chains remain deterministic
coverage only; relationships and active/suppressed-state verification are pending.
