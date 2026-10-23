# Ancestry source field audit

`ancestryFields` selects detached `Item.toObject(true)` source for `type: ancestry`, audited against PF2e **8.6.1** [ancestry/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ancestry/data.ts) and [ABCFeatureEntryField](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts). Descriptors use mapping `pf2e.ancestry.source.v1`, exact source paths/presence/value and limitation `ancestry_source_not_effective_character`. This pure selector does not resolve references or establish runtime verification.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `boosts/{key}/value/{i}`, `flaws/{key}/value/{i}` | `ancestry_boost_offer_code`, `ancestry_flaw_offer_code`: ordered string offers, distinct from selections. Empty arrays retain their parent path. |
| `boosts/{key}/selected`, `flaws/{key}/selected` | `ancestry_boost_selected_code`, `ancestry_flaw_selected_code`: nullable string selections, never filled from an offer list. Empty/missing keyed maps retain parent markers `ancestry_boost_slots` / `ancestry_flaw_slots`. |
| `alternateAncestryBoosts` or `/{i}` | `ancestry_alternate_boost_code`: explicit null, empty array, or ordered strings; null and empty remain distinct from absent. No application to default boosts/flaws. |
| `voluntary/legacy`, `/boost`, `/flaws/{i}` | `ancestry_voluntary_legacy` boolean, `ancestry_voluntary_boost_code` nullable string, `ancestry_voluntary_flaw_code` ordered strings. Preserve modern and legacy configurations without granting a boost or applying flaws. |
| `hp`, `size`, `speed`, `hands`, `reach`, `vision` | `ancestry_hp_contribution` finite number, `ancestry_size_code` string, `ancestry_base_speed`, `ancestry_hands`, `ancestry_reach` finite numbers, `ancestry_vision_code` string. These source contributions are not final character statistics. |
| `languages/value/{i}`, `/custom` | `ancestry_language_code` ordered strings and `ancestry_language_custom` exact string. |
| `additionalLanguages/count`, `/value/{i}`, `/custom` | `ancestry_additional_language_count` finite number, `ancestry_additional_language_code` ordered strings, `ancestry_additional_language_custom` exact string. No Intelligence allowance or learned-language inference. |
| `items/{key}/{uuid,img,name,level}` | `ancestry_feature_uuid`, `ancestry_feature_image`, `ancestry_feature_name` strings; `ancestry_feature_level` nonnegative integer. Empty/missing map parent marker `ancestry_feature_entries`. References are configured future/granted definitions, never proof that an Actor acquired the target. |
| `traits/value/{i}`, `/otherTags/{i}`, `/rarity`, `slug` | `ancestry_trait_code`, `ancestry_other_tag_code`, `ancestry_rarity_code` strings; `ancestry_source_slug` nullable string. |
| `publication/{title,authors,license,remaster}` | `ancestry_publication_title`, `_authors`, `_license` strings; `_remaster` boolean. |

`hands` and `reach` extend the story's proposed allowlist because both are explicit fields in the pinned ancestry schema. Their inclusion closes source coverage without depending on prepared creature getters. Numeric values retain their source values without schema-default reconstruction or downstream character calculations. Unknown string codes remain source strings, not translated labels.

Arbitrary keyed slot and feature names are escaped as JSON Pointer segments (`~` to `~0`, `/` to `~1`), retaining their original provenance. Each keyed map and array is bounded to 12,000 entries; oversized or malformed selected structures reject instead of silently dropping entries. Missing descriptors omit `value`; explicit null is permitted only by the relevant nullable schema leaves. Populated object dumps, inherited properties, prepared getters, description parsing, rule execution, UUID hydration, feature acquisition, HP totals and automatic application are excluded.

`tests/js/actor-ancestry.test.js` covers offered/selected separation, nullable alternate and voluntary choices, empty/missing markers, escaped feature/slot keys, numeric contributions, malformed/oversized inputs, source immutability and exclusion of prepared/unrelated data. Integration, permission/context identity, reference resolution and live verification require separate evidence.


## Explicit feature definition links

An explicit `relationships` read returns one `ancestry_feature_reference` per
configured feature UUID descriptor. Keys are `relationships:ancestry:<source
path>`, with mapping `pf2e.ancestry.feature-reference.v1` and limitation
`definition_reference_not_acquired_feature`. Duplicate UUIDs keep distinct
keyed occurrences; each snapshot caches repeated target lookup. Root empty/
absent feature maps return empty/missing respectively. Missing UUID leaves
retain absent source markers and a missing result.

Resolved results contain canonical `target_uuid`, `document_name:'Item'`,
`type`, bounded document display `name`, `name_truncated`, and `token_uuid`
for synthetic targets. Follow `read_item` with the returned selectors.
Missing/denied/unsupported/unverified targets have only status and null UUID;
unreadable identities stay hidden. At most200 immediate references resolve;
larger selections fail ReadFailed with source-first/selected-UUID recovery.
There is no target-source read, recursive feature expansion, automatic grant or
acquired-feature claim. Source feature levels remain separate configuration.
Source changes, target names/identities and permissions invalidate cursors.

PF2e prepares singleton selections from offered values, but actual persisted
selections can remain null. This reader preserves those nulls without labelling
fixed benefits unused. Alternate null versus empty arrays and modern voluntary
flaws versus legacy boost mode remain explicit source facts. Ancestry HP,
Speed, language count, hands and reach are contributions, not Actor totals.
