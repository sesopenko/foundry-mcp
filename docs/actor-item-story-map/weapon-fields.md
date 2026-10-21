# Weapon source field audit

The pure `weaponFields` selector accepts detached `Item.toObject(true)` source for `type: weapon`, audited against PF2e **8.6.1** at [weapon/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/weapon/data.ts). This document establishes source selection, not effective Strike support. Reader integration and live verification must establish their own evidence.

All descriptors contain `path`, `present`, optional exact `value`, `concept`, and `limitations: ["source_only_no_effective_strike_calculation"]`. Numbers must be finite; codes remain original strings, including unknown codes. Schema source values are not defaulted, localized or converted into attack/damage totals. Missing leaves have no `value`; explicit nullable fields retain null. Selected object containers emit a missing/null/empty-object marker or their selected child leaves. Code arrays emit indexed string leaves or an exact empty-array marker.

| Paths under `/system` | Concepts and meaning |
| --- | --- |
| `category`, `group` | `weapon_category_code`, `weapon_group_code`; nullable group. Shared physical selection supplies `baseItem` separately. |
| `damage/{dice,die,damageType,modifier}` | `weapon_damage_dice`, `weapon_damage_die_code`, `weapon_damage_type_code`, `weapon_damage_modifier`; die is nullable. No damage formula construction. |
| `damage/persistent` or its `{number,faces,type}` | Container `weapon_persistent_damage`; child `weapon_persistent_damage_number`, `weapon_persistent_damage_faces`, `weapon_persistent_damage_type_code`. Faces null means stored constant; number remains unchanged. |
| `range`, `maxRange`, `reload/value`, `expend` | `weapon_range_feet`, `weapon_max_range_feet`, `weapon_reload_code`, `weapon_expend`; all nullable. Do not derive maximum range or reload action costs. |
| `ammo` or `{builtIn,baseType,capacity}` | Container `weapon_ammunition`; child `weapon_ammo_built_in`, `weapon_ammo_base_type_code`, `weapon_ammo_capacity`. Base type and capacity nullable. |
| `selectedAmmoId` | `weapon_selected_ammo_local_id`; nullable local identifier, without existence, ownership or hydration inference. |
| `runes/{potency,striking,property/{i}}` | `weapon_rune_potency`, `weapon_rune_striking`, `weapon_property_rune_code`. Container `weapon_runes`. Prepared `runes.effects` excluded. |
| `bonus/value`, `splashDamage/value` | `weapon_bonus`, `weapon_splash_damage`; stored source numbers without bonus stacking or splash calculation. |
| `attribute`, `grade`, `graspingAppendage`, `usage/canBeAmmo` | `weapon_attribute_code`, `weapon_grade_code` (nullable strings); `weapon_grasping_appendage`, `weapon_can_be_ammo` (booleans). |
| `meleeUsage/{damage/{type,die},group,traits/{i}}` | Container `weapon_melee_usage`; `weapon_melee_damage_type_code`, `weapon_melee_damage_die_code`, `weapon_melee_group_code`, `weapon_melee_trait_code`; combination-weapon source mode only. |
| `meleeUsage/traitToggles/{modular,versatile}` | Container `weapon_melee_trait_toggles`; `weapon_melee_modular_selected` nullable number and `weapon_melee_versatile_selected_code` nullable string. |
| `traits/toggles/{doubleBarrel,modular,versatile}/selected` | Container `weapon_trait_toggles`, child-container concepts `weapon_double_barrel_toggle`, `weapon_modular_toggle`, `weapon_versatile_toggle`; selected concepts `weapon_double_barrel_selected` boolean, `weapon_modular_selected` nullable number, `weapon_versatile_selected_code` nullable string. Modular container itself can be null. |
| `specific/material/{type,grade}`, `specific/runes/{potency,striking,property/{i}}` | Nullable container `weapon_specific_baseline`; material container `weapon_specific_material` and nullable `weapon_specific_material_type_code` / `weapon_specific_material_grade_code`. Baseline runes reuse rune concepts, with distinct exact paths. No baseline reconciliation. |
| `traits/{value/{i},otherTags/{i},rarity}`, `slug` | `weapon_trait_code`, `weapon_other_tag_code`, `weapon_rarity_code`, nullable `weapon_source_slug`; source-only codes. |
| `publication/{title,authors,license,remaster}` | `weapon_publication_title`, `_authors`, `_license` strings and `_remaster` boolean. |

Explicit undefined is missing only where the schema marks a field optional: `maxRange`, `expend`, `attribute`, `graspingAppendage`, `usage/canBeAmmo`, `meleeUsage`, `meleeUsage/traits`, `meleeUsage/traitToggles`, `traits/toggles`, and each named toggle container. Undefined on a required selected leaf fails validation. Null is accepted only where the source type permits it.

Shared physical source already supplies quantity, equipped hands/carry/investment, source material, base item, usage code, source Bulk/HP/price, and serialized attachments. No weapon descriptor duplicates those paths. Flags, sheet state, prepared traits, rune effects, reload labels, final Strikes, rule elements and descriptions are excluded. Selecting a mode or toggle never changes the source or executes a rule.

`tests/js/actor-weapon.test.js` covers exact damage/ammunition/runes, zero/false/null, unknown code preservation, optional undefined, missing versus empty markers, malformed selected types, source immutability, forbidden prepared getters and uniqueness alongside shared physical paths. These pure tests establish neither effective weapon totals nor successful ammunition relationship resolution.

## Explicit stored ammunition selection

`relationships` reads only `/system/selectedAmmoId`, returning one record with
key `relationships:weapon:selectedAmmoId`, concept
`stored_selected_ammunition_reference` and mapping
`pf2e.weapon.selected-ammo.v1`. It looks up that local ID only in the actual
owning Actor's Item collection. Only ammo/weapon targets resolve; no UUID is
constructed and no target source is read. Resolved metadata includes target_uuid,
document_name Item, type, bounded name/name_truncated and selected token_uuid
for linked/synthetic context. Follow read_item with those selectors.

Absent/null/empty selection is missing; an absent owned target is missing;
unreadable targets are denied, other types unsupported, and a standalone local ID
unverified. Unresolved values have null target_uuid and no resolved metadata.
Source-only reading never inspects related Items. Identity/permission/membership
changes are included in relationship snapshot checks.

The stored selection is not the PF2e prepared ammo getter. That getter also uses
reload/repeating logic and loaded serialized subitems; its implementation is not
adopted as an external API. No loaded/compatible ammunition, quantity, usability,
consumption, roll or final Strike is inferred by this reference reader.
