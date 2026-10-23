# Feat selected-source fields

The `pf2e.feat.source.v1` mapping reads detached `Item.toObject(true)` source for
`feat` Items. Its schema baseline is [PF2e 8.6.1 feat/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts),
with [frequency](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts),
[trait toggle](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/trait-toggles.ts)
and shared Item metadata from the same revision. Core14 is the development
boundary; future PF2e versions and live v13 support are unverified.

Every selected descriptor carries `feat_source_not_effective_benefit`. Missing
fields remain absent; null remains null only for nullable fields. No source
default, frequency maximum, infinite numeric value or effective actor benefit
is reconstructed. Every list/map has a 12,000-entry bound, independently of
reader pagination and byte bounds. List order is preserved. Empty lists/maps
have root markers; opaque map keys use JSON Pointer `~0`/`~1` escaping.

All concepts below have the `feat_` prefix; paths are relative to `/system`.

| Source paths | Concept suffix and meaning |
| --- | --- |
| `category` | `category_code`; mapped `{code,kind}` keeps the raw code and distinguishes `feature`, `feat`, `unknown`. Feature codes: ancestryfeature, calling, classfeature, curse, deityboon, pfsboon. Feat codes: ancestry, bonus, class, general, skill. |
| `level/value`, `level/taken` | `nominal_level`, `taken_level`; separate integers 1–30, taken nullable. No ownership or acquisition is inferred. |
| `actionType/value`, `actions/value` | `activation_kind` raw code and `action_count` nullable integer 1–3. Null count does not mean free action. |
| `onlyLevel1`, `maxTakable`, `location` | `only_level_one` boolean, `maximum_takable` nullable positive integer, `location` nullable source string. Location does not verify a grant or slot relationship. |
| `prerequisites/value/{i}/value` | `prerequisite_text` ordered prose; root absent/empty marker `prerequisite_entries`. No eligibility evaluation. |
| `frequency` | Absent/null `frequency_source`; otherwise `value` → `recorded_frequency_remaining` nonnegative integer, `max` → `frequency_maximum` positive integer, `per` → `frequency_interval_code`. Missing remaining uses are not initialized. |
| `traits/value/{i}`, `traits/otherTags/{i}`, `traits/rarity` | `trait_code`, `other_tag_code`, `rarity_code`; exact source codes. |
| `traits/toggles`, `traits/toggles/mindshift`, `traits/toggles/mindshift/selected` | `trait_toggles`, nullable `mindshift_toggle`, boolean `mindshift_selected`; no damage alteration or prepared tag inference. |
| `subfeatures/keyOptions/{i}` | `key_option_code`; offered attributes, no inferred selection. |
| `subfeatures/languages` | Absent `language_options`; `slots` → nonnegative integer `language_slots`, `granted/{i}` → `granted_language_code`. Source contributions, not effective actor languages. |
| `subfeatures/proficiencies/{opaque}` | Empty/absent `proficiency_entries`; `rank` → integer 1–4 `proficiency_rank`, `attribute` → nullable `proficiency_attribute_code`. No effective rank or bonus. |
| `subfeatures/senses/{opaque}` | Empty/absent `sense_entries`; `acuity` → `sense_acuity_code`, `range` → nullable finite 5–300 `sense_range`. The schema has no integer flag for range. |
| `subfeatures/senses/{opaque}/special` | Absent `sense_special`; otherwise boolean `ancestry`, `llv`, `second` → `sense_special_ancestry`, `sense_special_llv`, `sense_special_second`. Conditions are preserved, never evaluated. |
| `subfeatures/suppressedFeatures/{i}` | `suppressed_feature_uuid`; source suppression intent, not established effective suppression. |
| `selfEffect` | Absent/null `self_effect_source`; otherwise `uuid`/`name` → `self_effect_uuid`/`self_effect_name`. Neither target identity nor application is verified by source selection. |
| `slug`, `publication/{title,authors,license,remaster}` | Nullable `source_slug`, `publication_title`, `publication_authors`, `publication_license`, boolean `publication_remaster`. |

Own undefined normalizes to absent only for explicit `required:false`,
`initial:undefined` fields: `level/taken`, `frequency`, `selfEffect`,
`traits/toggles`, `traits/toggles/mindshift`, `subfeatures/keyOptions`,
`subfeatures/languages`, each sense `acuity` and `special`, and `frequency/value`.
Explicit null remains accepted only for nullable fields; required undefined fails.
Unknown string codes remain unchanged; invalid scalar types,
nonfinite numbers, integer/range violations and malformed containers fail.

Descriptions are handled by the shared bounded description reader. Arbitrary
flags, rules, preparation methods, sheet state, future grants and selection
history are excluded. The selector makes no Foundry runtime calls and performs
no import, hydration, roll, activation, update or rule execution. System-ID
checking belongs to the shared reader. Deterministic tests cover the selector;
live identity, description continuation and runtime bridge checks belong to the
integrated reader verification and must be recorded separately.
