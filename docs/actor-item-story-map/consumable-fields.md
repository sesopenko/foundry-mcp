# Consumable source checkpoint

PF2e-specific, audited against PF2e 8.6.1 revision `28d9d156f252d084371d994dc359509b49eadf18`, with the existing Foundry 14.369 document boundary. This is a source checkpoint; ITEM-consumable remains incomplete until the dependent spell reader and remaining story acceptance checks are delivered.

Schema contracts: [ConsumableSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/consumable/data.ts), [SpellSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts). The selector reads detached `Item.toObject(true)` source and uses `pf2e.consumable.source.v1`. Every descriptor has limitation `source_only_no_consumable_use_or_spell_application`.

| Source path under `/system` | Mapped concept | Meaning |
| --- | --- | --- |
| `category` | `consumable_category_code` | Exact stored category code. |
| `uses/value`, `uses/max`, `uses/autoDestroy` | `consumable_uses_value`, `consumable_uses_max`, `consumable_uses_auto_destroy` | Stored uses and deletion preference, independent of stack quantity. No consumption or deletion occurs. |
| `damage` | `consumable_damage_healing` | Explicit null or absent structured roll source. |
| `damage/formula`, `damage/type`, `damage/kind` | `consumable_damage_formula`, `consumable_damage_type_code`, `consumable_damage_kind_code` | Authored formula and codes; healing/damage kind is retained, never inferred or rolled. |
| `spell` | `consumable_contained_spell` | Explicit null or absent contained SpellSource. |
| `spell/_id`, `spell/name`, `spell/type`, `spell/system/level/value` | `consumable_contained_spell_id`, `consumable_contained_spell_name`, `consumable_contained_spell_type`, `consumable_contained_spell_base_rank` | Selected embedded source identity and authored base spell rank. Local `_id` is not a document UUID, navigation selector or inferred cast rank. |
| `traits/value`, `traits/otherTags` | `consumable_trait_code`, `consumable_other_tag_code` | Empty/missing markers or ordered indexed string codes, including unfamiliar codes. |
| `traits/rarity`, `slug` | `consumable_rarity_code`, `consumable_source_slug` | Stored rarity and nullable source slug. |
| `publication/title`, `authors`, `license`, `remaster` | `consumable_publication_*` | Exact authored publication metadata. |

Shared physical extraction supplies quantity, usage and other physical fields without duplication. Missing fields remain absent; null markers stay explicit. Malformed selected values fail without coercion; finite numbers remain unchanged. The selector does not expose an arbitrary contained spell object or read its rules, damage, heightening, location, prose or prepared state. Full contained-spell mechanics require the spell reader. Source data does not establish activation eligibility, remaining usable castings, applied healing/damage, active benefits or actor statistics.
