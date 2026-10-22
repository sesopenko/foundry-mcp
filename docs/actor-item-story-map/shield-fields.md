# Shield source field audit

`shieldFields` selects detached `Item.toObject(true)` source for `type: shield`, audited against PF2e **8.6.1** [shield/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/shield/data.ts), [weapon rune source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/weapon/data.ts) and [physical material schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts). This pure selector establishes source coverage; production reader integration and live behavior require separate evidence.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["source_only_no_actor_shield_calculation"]`. Selected numbers must be finite and remain exact. Unknown string codes and array order remain unchanged. Missing paths have no `value`; explicit undefined rejects. Empty objects and arrays retain their parent paths as exact markers; no populated source object is returned. Null is accepted only at nullable boundaries below.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `acBonus`, `speedPenalty` | `shield_ac_bonus`, `shield_speed_penalty`: finite numbers, retaining zero and negative penalties. |
| `grade` | `shield_grade_code`: nullable string. |
| `runes` | `shield_runes`: missing or empty-object marker, otherwise reinforcing leaf. Null rejects. |
| `runes/reinforcing` | `shield_rune_reinforcing`: finite authored number. |
| `specific` | `shield_specific_baseline`: missing, null or empty-object marker, otherwise baseline material, runes and integrated weapon leaves. |
| `specific/material` | `shield_specific_material`: missing or empty-object marker; null rejects. |
| `specific/material/type`, `specific/material/grade` | `shield_specific_material_type_code`, `shield_specific_material_grade_code`: nullable strings. |
| `specific/runes`, `specific/runes/reinforcing` | Same marker and concept rules as current shield runes. Baseline values remain separate. |
| `specific/integrated` | `shield_specific_integrated_weapon`: missing, null or empty-object marker, otherwise baseline integrated rune leaves. |
| `traits/integrated` | `shield_integrated_weapon`: missing, null or empty-object marker, otherwise current integrated rune and versatile leaves. |
| `{specific/integrated,traits/integrated}/runes` | `shield_integrated_weapon_runes`: missing or empty-object marker; null rejects. |
| `{specific/integrated,traits/integrated}/runes/{potency,striking}` | `shield_integrated_weapon_rune_potency`, `shield_integrated_weapon_rune_striking`: finite source numbers. |
| `{specific/integrated,traits/integrated}/runes/property` or its indexed leaves | `shield_integrated_weapon_property_rune_code`: empty-array marker or ordered string codes. |
| `traits/integrated/versatile` | `shield_integrated_weapon_versatile`: missing, null or empty-object marker. |
| `traits/integrated/versatile/selected` | `shield_integrated_weapon_versatile_selected_damage_code`: string. |
| `traits/value/{i}`, `traits/otherTags/{i}`, `traits/rarity` | `shield_trait_code`, `shield_other_tag_code`, `shield_rarity_code`: strings. Empty arrays retain their parent paths. |
| `slug` | `shield_source_slug`: nullable string, without inferred fallback. |
| `publication/{title,authors,license,remaster}` | `shield_publication_title`, `_authors`, `_license`: strings; `_remaster`: boolean. |

Shared `physicalFields` supplies HP, hardness, base item, equipped state, material and attachment metadata without duplicate paths. Shield usage is prepared rather than stored. Integrated `damageType`, versatile `options`, rune `effects`, raised or broken state, Shield Block, class reinforcement, effective defenses and attacks are excluded. Descriptions and rule elements require their separate sections. Specific baseline runes and material are never added to current source values. Persisted HP value can exceed persisted maximum when reinforcement changes prepared limits; source values are neither clamped nor used to infer broken state or a broken threshold.

`tests/js/actor-shield.test.js` verifies source values, unknown codes, integrated versus specific baselines, missing/null/empty distinctions, malformed selected leaves, immutability, unique shared paths and populated-object exclusion. Throwing getters verify prepared and unrelated fields stay untouched. Pure tests do not prove live actor defense totals, pack hydration or provenance validation.
