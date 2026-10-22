# Equipment source field audit

`equipmentFields` selects detached `Item.toObject(true)` source for `type: equipment`, audited against PF2e **8.6.1** [equipment/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/equipment/data.ts), [physical/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts) and [base source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts). This pure selector establishes source coverage; production integration, bounded prose continuation and live behavior require separate evidence.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["source_only_no_equipment_benefit_application"]`. Strings retain exact source values, unknown codes and array order. Missing paths have no `value`; explicit undefined rejects. Empty arrays retain their parent paths. No populated object is returned. Only `slug` accepts null.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `traits/value/{i}` or parent marker | `equipment_trait_code`: ordered strings; missing or empty-array parent marker. |
| `traits/otherTags/{i}` or parent marker | `equipment_other_tag_code`: ordered strings; missing or empty-array parent marker. |
| `traits/rarity` | `equipment_rarity_code`: string. |
| `slug` | `equipment_source_slug`: nullable string, without inferred fallback. |
| `publication/{title,authors,license,remaster}` | `equipment_publication_title`, `_authors`, `_license`: strings; `_remaster`: boolean. |

Shared `physicalFields` supplies usage, equipped carry/investment state, quantity, material, HP, price, identification and bounded attachment identity metadata. These paths are not duplicated by `equipmentFields`. Attachment identities use source paths rather than fabricated UUIDs; their full systems are not recursively selected. The inherited optional `apex` source structure is outside this selected allowlist and is not interpreted as an active attribute bonus.

`EquipmentSystemSource` adds no structured activation or frequency fields. Descriptions remain available through the explicit bounded description section without parsing, enrichment or execution. Their absence from this source selector does not mean the Item lacks abilities. A stored invested flag does not establish which magical benefits currently apply, and an uninvested flag does not erase mundane benefits. Trait codes alone do not assert active effects. Rule elements, effective statistics, target calculations and benefit application remain outside this selector.

`tests/js/actor-equipment.test.js` covers exact source metadata, unknown codes, missing/null/empty distinctions, malformed leaves, immutability, uniqueness alongside common physical fields, uninvested state preservation and throwing getters on excluded prose, activation, rule and apex fields. Pure tests do not establish live ownership, description continuation or runtime provenance validation.
