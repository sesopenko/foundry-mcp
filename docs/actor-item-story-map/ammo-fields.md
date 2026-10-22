# Ammunition source field audit

`ammoFields` selects detached `Item.toObject(true)` source for `type: ammo`, audited against PF2e **8.6.1** [ammo/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ammo/data.ts). This pure selector establishes source fields; reader integration and live checks establish their own evidence.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["source_only_no_ammunition_consumption_or_compatibility"]`. Finite numeric source values remain unchanged; string codes retain unknown values and order. Missing leaves have no `value`; explicit undefined on these required schema fields rejects. Arrays emit indexed string leaves or an exact empty-array marker. Null is accepted only for `craftableAs` and `slug`.

| Paths under `/system` | Concepts and meaning |
| --- | --- |
| `uses/value`, `uses/max`, `uses/autoDestroy` | `ammo_uses_value`, `ammo_uses_max` finite numbers; `ammo_auto_destroy` boolean. Stored uses are distinct from physical stack quantity. The source policy does not prove the Item will be consumed or deleted. |
| `craftableAs` or `craftableAs/{i}` | `ammo_craftable_as_code`. Null means a selected base category is required; an empty array means any non-magazine category; populated strings list authored category codes. Missing remains unknown. No weapon compatibility check is performed. |
| `traits/value/{i}`, `traits/otherTags/{i}`, `traits/rarity` | `ammo_trait_code`, `ammo_other_tag_code`, `ammo_rarity_code`; source code strings. Empty arrays retain their parent path. |
| `slug` | Nullable `ammo_source_slug`, without name-derived fallback. |
| `publication/{title,authors,license,remaster}` | `ammo_publication_title`, `_authors`, `_license` strings and `_remaster` boolean. |

The shared physical selector supplies `baseItem`, quantity, level, Bulk, HP, price, identification, carrying state and other shared fields. This selector never duplicates those paths. The ammo schema forbids `subitems` and apex properties; no additional ammo descriptors expose them. Descriptions and rule elements are separate explicit reader sections. Prepared properties, private fields, consumption, damage/effect execution and inferred loaded ammunition are excluded.

`tests/js/actor-ammo.test.js` verifies zero/false/null, distinct craftableAs meanings, missing versus empty source, malformed selected types, unknown codes, immutability and shared-path uniqueness. Throwing prepared/unrelated getters establish they are not read. These tests do not prove effective ammunition compatibility, consumption or runtime Item hydration.
