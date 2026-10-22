# Treasure source field audit

`treasureFields` selects detached `Item.toObject(true)` source for `type: treasure`, audited against PF2e **8.6.1** [treasure/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/treasure/data.ts) and [category codes](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/treasure/values.ts). Treasure defines its own model schema, rather than inheriting the physical source interface unchanged. This selector establishes source coverage; integration, public MCP validation and live behavior require separate evidence.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["source_only_no_treasure_valuation_or_sale"]`. Missing paths have no `value`; explicit undefined and malformed selected values reject. Unknown string codes, array order and exact nullable source values remain unchanged. Populated source objects are never returned.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `category` | `treasure_category_code`: nullable string. Current schema choices are `art-object`, `coin`, `gem`, `material`, `credstick`; unknown strings remain explicit source codes. Null does not become a guessed category. |
| `traits/value/{i}`, `traits/otherTags/{i}` | `treasure_trait_code`, `treasure_other_tag_code`: ordered strings. Empty arrays retain their parent path; missing arrays retain an absent parent marker. |
| `traits/rarity` | `treasure_rarity_code`: string. |
| `slug` | `treasure_source_slug`: nullable string, without inferred fallback. |
| `publication/{title,authors,license,remaster}` | `treasure_publication_title`, `_authors`, `_license`: strings; `_remaster`: boolean. |

Shared `physicalFields` supplies exact quantity, separate price denominations, `price.per`, container ID, carry state, material, HP, hardness and other common stored physical fields without duplicate paths. Quantity and price-per basis remain independent source values: this selector performs no multiplication, currency conversion, stack valuation, sale calculation or actor wealth calculation. It does not label an unknown/null category as coin, gem or art, or infer resale terms from a name or description.

Treasure's `stackGroup` is a computed getter, and its usage is prepared rather than persisted. Investment, subitems, stack-group migration behavior, prepared coin value and size-sensitive adjustments are not treasure source dependencies. Separate bounded description reading retains authored price or exchange prose without executing or parsing it into valuation rules.

`tests/js/actor-treasure.test.js` verifies source values, nullable and unknown categories, missing/null/empty distinctions, malformed selected leaves, immutability, distinct quantity and price-per fields, unique shared paths, and exclusion of prepared or unrelated getters. These pure tests do not establish live pack hydration, effective values or populated actor inventory views.
