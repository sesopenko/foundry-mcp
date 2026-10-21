# Condition persisted-source contract

This PF2e-specific selector was audited against PF2e **8.6.1**, revision
`28d9d156f252d084371d994dc359509b49eadf18`; the integration target is Foundry
**14.369**. Evidence is the complete pinned
[condition schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/condition/data.ts)
and the inherited
[Item source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts).
The condition model's `prepareBaseData` assigns duration: that duration is
prepared data and is excluded. Persistent damage `damage` and `expectedValue`
are additional prepared properties, also excluded. Reading these declarations
establishes the persisted contract, not a public effective-state API.

`conditionFields(source)` accepts detached persisted Item source and returns
`null` for other Item types. Descriptors are
`{path,present,value?,concept,limitations}` with limitation
`persisted_source_not_effective_condition_state`. Missing properties emit
`present:false` without `value`. Only schema-optional `persistent` treats an own
`undefined` as missing; other selected own undefined primitive values fail.
No schema initial value is fabricated. Numeric leaves must be finite. String
codes, slugs and formulas are preserved exactly without evaluation or localized
label inference. Arrays emit indexed primitive leaves or one `[]` marker; null
arrays fail. No populated object escapes the selector. Unknown extra fields
are ignored, so rules, descriptions, flags and prepared getters are untouched.

Paths below are relative to `/system/`. All leaves may be absent; `?null`
indicates explicit null is accepted.

| Path | Concept | Value contract |
| --- | --- | --- |
| value/isValued | condition_is_valued | boolean |
| value/value | condition_stored_value | finite number, ?null |
| persistent | condition_persistent_damage | missing or null marker only |
| persistent/formula | condition_persistent_formula | string |
| persistent/damageType | condition_persistent_damage_type | source code string |
| persistent/dc | condition_persistent_recovery_dc | finite number |
| persistent/criticalHit | condition_persistent_critical_hit | boolean |
| references/parent | condition_parent_reference | missing or null marker only |
| references/parent/id | condition_parent_item_id | local Item ID string |
| references/children[/index] | condition_child_reference | missing or empty array marker |
| references/children/index/id | condition_child_item_id | local Item ID string |
| references/children/index/type | condition_child_item_type | literal condition |
| references/overrides[/index] | condition_override_reference | missing or empty array marker |
| references/overrides/index/id | condition_override_item_id | local Item ID string |
| references/overrides/index/type | condition_override_item_type | literal condition |
| references/overriddenBy[/index] | condition_overridden_by_reference | missing or empty array marker |
| references/overriddenBy/index/id | condition_overridden_by_item_id | local Item ID string |
| references/overriddenBy/index/type | condition_overridden_by_item_type | literal condition |
| overrides[/index] | condition_override_slug | string array of source slugs |
| fromSpell | condition_from_spell | boolean |
| group | condition_group | string, ?null |
| traits/value[/index] | condition_trait_code | string array |
| traits/otherTags[/index] | condition_other_tag_code | string array |
| slug | source_slug | string, ?null |
| publication/title, authors, license | publication_title, publication_authors, publication_license | string |
| publication/remaster | publication_remaster | boolean |

The nullable `persistent` and `references/parent` containers emit only their
marker when missing/null; populated objects emit selected children. A populated
reference array emits only each entry's `id` and `type` fields. The selector
preserves duplicate slugs and reference ordering. Missing children remain
explicitly absent, rather than filling IDs or types from defaults.

A condition's stored value is a source claim. It is not a computed effective
value or proof the condition is currently active. The selector does not enforce
a derived correlation between `isValued` and `value`, synthesize totals, decide
suppression or apply condition rules. `persistent/criticalHit` records source
metadata; neither damage multipliers nor formula results are calculated.
Top-level `overrides` contains **condition slugs**; it is not interchangeable
with local Item IDs in `references/overrides`. Resolving either relationship
requires a separate permission-aware document traversal; this selector makes
no resolution or validity claim.

Focused verification: `node --test tests/js/actor-condition.test.js` covers
valued/unvalued source, zero/null/false, exact formula preservation, all local
reference categories, duplicate override slugs, null/missing/empty markers,
malformed primitive/container values, optional undefined, exclusion of prepared
getters and no source mutation. These deterministic checks alone do not prove
live Foundry integration or complete ITEM-condition acceptance criteria.

## Explicit owner-local relationships

`relationships` returns one record per parent reference, list entry or override
slug, including absent/null/empty markers. Mapping is
`pf2e.condition.reference.v1`; keys are `relationships:condition:<source path>`.
Indexed references retain both id/type source contributors. Parent references
may resolve any supported owned Item; child/override/overriddenBy lists resolve
only condition Items. Actual owner membership supplies canonical UUIDs; no UUID
is manufactured from a local ID. Duplicate local references and same-name Items
remain separate source records.

Resolved mapped values contain status resolved, target_uuid, document_name Item,
actual type, bounded name/name_truncated and token_uuid for selected linked or
synthetic context. Follow read_item with item_uuid and returned token_uuid.
Denied targets return null target_uuid and no resolved metadata; missing targets
stay missing. Unsupported types remain unsupported. Without an Actor owner a
local ID stays unverified; top-level override slugs always stay unverified named
claims. Source UUIDs/IDs remain raw claims, not evidence of activity/suppression.
Source-only reads never inspect related Items. No target source, rolls, writes,
recursive provenance or suppression calculation occurs. Target identity,
permission and membership changes invalidate relationship cursors.
