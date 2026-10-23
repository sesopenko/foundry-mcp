# Class source field audit

`classFields` selects detached `Item.toObject(true)` source for `type: class`, audited against PF2e **8.6.1** [class/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/class/data.ts), [rank/publication schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/model.ts), [ABC entries](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts) and [shared Item schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts). Descriptors use mapping `pf2e.class.source.v1` and limitation `class_source_not_effective_character`. Pure selector tests establish deterministic extraction, separately from live compatibility evidence.

| Paths under `/system` | Concepts and exact selected source types |
| --- | --- |
| `keyAbility/value/{i}`, `keyAbility/selected` | `class_key_attribute_offer_code` strings versus nullable `class_key_attribute_selected_code`. A singleton offer does not imply selection. |
| `hp` | `class_hp_contribution`, finite number 4–12, with no integer restriction in the source schema. This is not actor HP. |
| `perception`, `savingThrows/{fortitude,reflex,will}` | `class_starting_perception_rank`, `class_starting_{save}_rank`. |
| `attacks/{simple,martial,advanced,unarmed}`, `attacks/other/{name,rank}` | `class_starting_{category}_attack_rank`; optional nonnullable string `class_other_attack_name`; `class_starting_other_attack_rank`. |
| `defenses/{unarmored,light,medium,heavy}`, `spellcasting` | `class_starting_{category}_defense_rank`, `class_starting_spellcasting_rank`. Spellcasting is the starting rank for spell attack rolls and DCs. |
| `trainedSkills/value/{i}`, `trainedSkills/additional` | `class_trained_skill_code` exact strings; `class_additional_trained_skills` nonnegative integer. No acquired training or Intelligence adjustment is calculated. |
| `{ancestryFeatLevels,classFeatLevels,generalFeatLevels,skillFeatLevels,skillIncreaseLevels}/value/{i}` | `class_ancestry_feat_levels`, `class_class_feat_levels`, `class_general_feat_levels`, `class_skill_feat_levels`, `class_skill_increase_levels`. Finite numbers at least 1; pinned schema specifies no integer flag. Entries remain definition progression, not advancement performed or features acquired. |
| `items/{key}/{uuid,img,name,level}` | `class_feature_uuid`, `class_feature_image`, `class_feature_name` strings; `class_feature_level` nonnegative integer. Configured target name/UUID remain source facts, with no hydration or acquired-feature assertion. Empty/missing records use `class_feature_entries`. |
| `traits/otherTags/{i}`, `traits/rarity`, `slug` | `class_other_tag_code`, `class_rarity_code` strings; nullable string `class_source_slug`. Class has **no `traits.value` field** in this schema. |
| `publication/{title,authors,license,remaster}` | `class_publication_title`, `_authors`, `_license` strings; `_remaster` boolean. |

Every rank retains raw integer 0–4 and adds `mapped_value: {rank, label}` with labels `Untrained`, `Trained`, `Expert`, `Master`, `Legendary`. These are starting source proficiencies, not bonuses, current effective ranks, check totals or derived DCs. Unknown attribute/skill/tag/rarity codes remain exact strings rather than being guessed from localization or names.

Arrays retain order and use explicit parent-path empty-array markers. Keyed `items` maps retain escaped JSON Pointer keys (`~` → `~0`, `/` → `~1`) and explicit empty-object markers. Missing descriptors omit `value`; explicit nullable values remain present. Each array/map admits at most 12,000 entries and rejects malformed/oversized data. No defaults are reconstructed. Shared reading supplies document identity, source provenance, permissions and bounded descriptions; the helper reads no description, rules, prepared actor fields or unrelated metadata.

The source package performs no character advancement, HP arithmetic, proficiency bonus calculation, rule execution, import, roll, chat, write or UUID resolution. Named feature references do not prove ownership. Effective character statistics and joins with acquired documents need separate evidence and contracts. PF2e 8.6.1 is the audited schema boundary; future PF2e versions and live v13 behavior remain unverified.

`tests/js/actor-class.test.js` covers offers versus selection, rank labels/raw values, source HP, all five progression lists, fractional progression permitted by the schema, named future references, escaped keys, metadata, null/empty/missing distinctions, unknown codes, inherited/unrelated-field exclusion, immutability and malformed/12,000-entry bounds.

The PF2e class schema uses an unconfigured `StringField` for `attacks.other.name`. A core14 public field-constructor probe confirmed `required: false`, `nullable: false`, `initial: undefined`; existing Fighter/Rogue/Wizard detached sources contained their own empty-string name. Only this optional leaf treats an explicit `undefined` as absent; null rejects. The production selector depends on the source schema, not field construction or runtime preparation.


## Explicit progression-feature definition links

Explicit relationships return `class_feature_reference` per configured UUID
under key `relationships:class:<exact source path>`, map
`pf2e.class.feature-reference.v1`, limitation
`definition_reference_not_acquired_feature`. Repeated UUIDs retain independent
source occurrences while lookup is cached within each snapshot. Empty/absent
root feature maps return empty/missing; absent UUID leaves stay missing.

Resolved results contain canonical target_uuid, document_name Item, type,
bounded display name/name_truncated and token_uuid for a synthetic target.
Follow read_item with those selectors. Missing/denied/unsupported/unverified
results disclose no resolved identity. At most200 references resolve per explicit
read; source arrays/maps independently admit12000 entries. There is no target
source read, recursive feature expansion, advancement, HP recomputation or
acquired-feature claim. Source feature levels and progression lists remain
separate definition contributions. Source, resolved name/identity and permission
changes invalidate continuations.
