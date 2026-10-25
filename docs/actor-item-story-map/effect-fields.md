# Effect persisted-source contract

The October25 boundary regression audit verifies selected own data descriptors
for type, containers, badge discriminators, scalar fields and array indexes.
Selected accessors reject without invocation; inherited and unrelated fields
are not read. Nonplain own data and schema-optional undefined behavior remain
supported. Relationship-only context extraction follows the same rule.
Python checks badge discriminators and null/absent-container contradictions
when their witnesses share a page; a discriminator on another page is not
required or assumed. These checks do not evaluate formulas or effective state.

This selector is PF2e-specific, audited against PF2e **8.6.1** revision
`28d9d156f252d084371d994dc359509b49eadf18`, with the integration target
Foundry **14.369**. Source evidence:
[effect/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/effect/data.ts),
[abstract-effect/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/data.ts), and
[duration units](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/values.ts).
Both schema files were read in full, including the context and badge schema
constructors. `prepareBaseData` changes badge values/labels and expiry: these
prepared results are deliberately excluded from this persisted-source selector.
This document establishes the source contract; it does not establish remaining
duration, expiration, rule applicability, or an effective effect state.

`effectFields(source)` returns `null` for non-`effect` Items. Each selected
field is `{path,present,value?,concept,limitations}`. All limitations currently
contain `persisted_source_not_effective_or_expiration_state`. Missing fields
emit `present:false` without `value`; no initial/default values are invented.
All numeric leaves must be finite. No nonempty object is emitted. An array
emits one primitive leaf per index, or a single `[]` marker when empty.
Array order, duplicate values and blank strings are retained. Nullable arrays
can emit `null`. Schema-optional own undefined values are treated as missing only for badge
labels/loop/evaluate, value-badge reevaluate.initial, context, origin token/item/
spellcasting, spellcasting tradition, target, target token and roll degreeOfSuccess.
Other own undefined values fail validation; absent properties are missing. Unknown badge discriminators fail with an actionable
TypeError asking the caller to verify the pinned schema.

Paths below are relative to `/system/`. `?null` means an explicit null is
accepted; every leaf can also be absent. Codes and UUID text are preserved,
without reference resolution or inferred relationships.

| Path | Concept | Value contract |
| --- | --- | --- |
| level/value | effect_level | integer |
| duration/value | effect_duration_value | number >= -1 |
| duration/unit | effect_duration_unit | rounds, minutes, hours, days, unlimited, encounter |
| duration/expiry | effect_duration_expiry | turn-start, turn-end, round-end, ?null |
| duration/sustained | effect_sustained | boolean |
| start/value | effect_start_time | number |
| start/initiative | effect_start_initiative | number, ?null |
| tokenIcon/show | effect_token_icon_show | boolean |
| unidentified | effect_unidentified | boolean |
| fromSpell | effect_from_spell | boolean |
| traits/value[/index] | effect_trait_code | string array |
| traits/otherTags[/index] | effect_other_tag_code | string array |
| slug | source_slug | string, ?null |
| publication/title, authors, license | publication_title, publication_authors, publication_license | string |
| publication/remaster | publication_remaster | boolean |

## Discriminated badge

`badge` itself emits `effect_badge` only when missing or null. A populated badge
must have `type` equal to counter, value or formula. Only children in the
selected branch are emitted; unknown extra properties are not traversed.

| Path | Concept | Branch / value contract |
| --- | --- | --- |
| badge/type | effect_badge_type | all: discriminator string |
| badge/labels[/index] | effect_badge_label | all: string array, ?null |
| badge/value | effect_badge_value | counter/value: number; formula: exact string |
| badge/min | effect_badge_min | counter: integer, ?null |
| badge/max | effect_badge_max | counter: integer, ?null |
| badge/loop | effect_badge_loop | counter: boolean |
| badge/evaluate | effect_badge_evaluate | formula: boolean |
| badge/reevaluate | effect_badge_reevaluate_event | formula: event string, ?null |
| badge/reevaluate | effect_badge_reevaluate | value: missing/null container marker only |
| badge/reevaluate/event | effect_badge_reevaluate_event | value: event string |
| badge/reevaluate/formula | effect_badge_reevaluate_formula | value: exact string |
| badge/reevaluate/initial | effect_badge_reevaluate_initial | value: number |

Event strings are initiative-roll, turn-start or turn-end. Formula text is never
evaluated. Counter values are not clamped; labels are not indexed into a derived
current label. Source min/max null are not replaced with preparation defaults.

## Context

The nullable containers `context`, `context/origin/spellcasting`,
`context/target`, and `context/roll` emit only missing/null markers, with concepts
`effect_context`, `effect_origin_spellcasting`, `effect_target`, and
`effect_context_roll` respectively. Populated containers emit selected leaves.

| Path | Concept | Value contract |
| --- | --- | --- |
| context/origin/actor | effect_origin_actor_uuid | string |
| context/origin/token | effect_origin_token_uuid | string, ?null |
| context/origin/item | effect_origin_item_uuid | string, ?null |
| context/origin/rollOptions[/index] | effect_origin_roll_option | string array |
| context/origin/spellcasting/attribute/type | effect_origin_spellcasting_attribute | str, dex, con, int, wis, cha |
| context/origin/spellcasting/attribute/mod | effect_origin_spellcasting_modifier | number |
| context/origin/spellcasting/tradition | effect_origin_spellcasting_tradition | string, ?null |
| context/target/actor | effect_target_actor_uuid | string |
| context/target/token | effect_target_token_uuid | string, ?null |
| context/roll/total | effect_context_roll_total | number |
| context/roll/degreeOfSuccess | effect_context_roll_degree | 0, 1, 2, 3, ?null |

Context roll totals describe stored historical context, not the effect's current
check modifier or a newly rolled result. UUIDs can be stale or inaccessible;
this selector makes no resolved/denied claim. Tradition is preserved as text
because the schema constructor declares a StringField without choices.
Flags/aura metadata, description, rule elements and prepared `expired` are
excluded. Separate description and relationship contracts remain necessary.

## Verification

`tests/js/actor-effect.test.js` verifies all three badge branches, zero/null/
missing/empty distinctions, exact formula preservation, context leaves,
malformed selected values, mutation avoidance, exclusion of unknown properties
and guards against reading prepared `expired` or rules getters. Integration,
Python DTO validation, live verification and rulebook comparison are separate
story evidence; this helper alone does not complete ITEM-effect.

## Explicit immediate context references

`relationships` resolves five roles: origin_actor, origin_token, origin_item,
target_actor and target_token. Each record preserves all five claimed source
UUID fields and their presence/null distinctions with mapping
`pf2e.effect.context-reference.v1`. Resolved values return canonical target_uuid,
document_name, bounded name/name_truncated and token_uuid when required for
linked/synthetic context. Use read_actor with actor_uuid for ordinary Actors or
token_uuid for token-context Actors/Tokens; use read_item with item_uuid and
returned token_uuid for Items. Standalone compendium Items resolve independently
of any contextual token. The reader never merges duplicate roles or origins.

Absent/null/empty references report missing. Denied, unsupported and unverified
references retain raw claimed source but return null target_uuid and no resolved
target metadata. Denied: grant target/owner/pack/scene access. Unsupported: inspect
canonical UUID and supported type. Unverified: retry resolution or inspect stored
Actor/token mismatch; no base Actor is substituted. Missing: rediscover the target.
Only immediate identities are resolved; target source is not read and no recursive
provenance, learned-spell aggregation, roll, import or effect application occurs.
Target identity/permission changes invalidate relationship continuations.
