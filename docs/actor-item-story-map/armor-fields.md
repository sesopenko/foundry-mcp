# Armor source field audit

`armorFields` selects detached `Item.toObject(true)` source for `type: armor`, audited against PF2e **8.6.1** [armor/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/armor/data.ts) and its [physical material schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts). This pure selector establishes source coverage; production reader integration and live behavior require their own evidence.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["source_only_no_actor_armor_calculation"]`. Selected finite numbers remain unchanged; unknown code strings and array order are preserved. Missing paths have no `value`. Explicit undefined rejects because all selected fields are required in this schema. Empty objects and arrays retain their parent paths as exact markers. Null is accepted only at schema-nullable boundaries listed below. No effective defenses or adjustment arithmetic is performed.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `category`, `group`, `grade` | `armor_category_code` string; nullable `armor_group_code` and `armor_grade_code` strings. |
| `acBonus`, `strength`, `dexCap`, `checkPenalty`, `speedPenalty` | Finite numbers with concepts `armor_ac_bonus`, `armor_strength_requirement`, `armor_dex_cap`, `armor_check_penalty`, `armor_speed_penalty`. Only strength is nullable. Zero and negative values remain exact. |
| `runes` | `armor_runes`: missing or empty-object marker, otherwise selected leaves. Null rejects. |
| `runes/potency`, `runes/resilient` | `armor_rune_potency`, `armor_rune_resilient` finite numbers; source values rather than calculated bonuses. |
| `runes/property` or `runes/property/{i}` | `armor_property_rune_code` empty-array marker or ordered string codes. |
| `specific` | `armor_specific_baseline`: missing, null or empty-object marker, otherwise baseline material and rune leaves. |
| `specific/material` | `armor_specific_material`: missing or empty-object marker; null rejects. |
| `specific/material/type`, `specific/material/grade` | `armor_specific_material_type_code`, `armor_specific_material_grade_code` nullable strings. |
| `specific/runes` and its `potency`, `resilient`, `property` leaves | Same marker, concepts and source types as current `runes`. Baseline values remain separate from current runes and are never added together. |
| `traits/value/{i}`, `traits/otherTags/{i}`, `traits/rarity` | `armor_trait_code`, `armor_other_tag_code`, `armor_rarity_code` strings. Empty arrays retain their parent paths. |
| `slug` | Nullable `armor_source_slug` string, without inferred fallback. |
| `publication/{title,authors,license,remaster}` | `armor_publication_title`, `_authors`, `_license` strings; `_remaster` boolean. |

Shared `physicalFields` supplies `baseItem`, material, carrying/equipped state, quantity, level, Bulk, HP, price, identification and attachment source fields. The armor selector does not duplicate these paths. Armor's schema explicitly excludes stored usage, so no usage descriptor or getter is read. The selector does not infer whether armor is worn, invested or contributing to actor AC, saving throws or Speed. Prepared `runes.effects` and `traits.config`, private members, rule execution and formula evaluation are excluded. Descriptions and rule elements remain separate explicit sections.

`tests/js/actor-armor.test.js` covers distinct null/missing/zero/empty states, specific baseline versus current runes, negative penalties, unknown codes, malformed source types, immutability and shared-path uniqueness. Throwing getters verify prepared and unrelated fields are untouched. These pure tests do not establish live hydration, actor defense totals or reader provenance validation.
