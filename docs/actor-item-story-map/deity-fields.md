# Deity source field audit

`deityFields` selects detached `Item.toObject(true)` source for `type: deity`, audited against PF2e **8.6.1** [deity/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/deity/data.ts), [shared Item schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts) and [static template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json). Descriptors use mapping `pf2e.deity.source.v1`, exact source paths/presence/value and limitation `deity_options_not_active_benefits`. Pure selector tests establish neither live runtime nor future-version compatibility.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `category` | `deity_category_code`: exact string, including deity, pantheon, covenant, philosophy and unknown codes. No conversion to a creature. |
| `sanctification` | `deity_sanctification`: missing or explicit null root marker. For an object, select `modal` as string `deity_sanctification_modal_code` and ordered `what/{i}` strings as `deity_sanctification_what_code`; retain empty/missing `what` parent marker. |
| `domains/primary/{i}`, `domains/alternate/{i}` | `deity_primary_domain_code`, `deity_alternate_domain_code`: ordered exact string codes. |
| `font/{i}`, `attribute/{i}`, `skill/{i}`, `weapons/{i}` | `deity_font_code`, `deity_attribute_code`, `deity_skill_code`, `deity_weapon_code`: ordered exact strings. Skill additionally accepts explicit null at its root. These are offered options, not active benefits or owned weapons. |
| `spells/{key}` | `deity_spell_uuid`: stored UUID string. Keys are opaque source keys, preserved without cast-rank inference. Missing/empty maps retain root `deity_spell_entries` markers. UUIDs do not establish learned, prepared or repertoire spells. |
| `traits/otherTags/{i}`, `slug` | `deity_other_tag_code` string; `deity_source_slug` nullable string. Deity traits are OtherTagsOnly; `traits.value` and `traits.rarity` are excluded. |
| `publication/{title,authors,license,remaster}` | `deity_publication_title`, `_authors`, `_license` strings; `_remaster` boolean. |

Arrays preserve order and empty strings; unknown codes remain exact source strings. Empty arrays retain their parent path. Missing descriptors omit `value`; null is accepted only for sanctification, skill and slug. Arbitrary persisted spell keys use JSON Pointer escaping (`~` → `~0`, `/` → `~1`). Every selected array and spell map is bounded to 12,000 entries. Malformed or oversized selected leaves reject without silently dropping entries. Missing template defaults are never reconstructed.

The source package does not infer worship, active cleric/devotee benefits, ownership, selected attributes, skill training, granted domains, learned spells or casting rank. It does not hydrate UUIDs, execute rules, enrich text or inspect prepared state. Shared reading owns description extraction, identity and permissions. Source references remain unresolved configuration until a separately authorized relationship reader resolves them; resolution itself cannot prove acquisition.

`tests/js/actor-deity.test.js` covers categories including unknown codes, nullable sanctification/skill, option arrays, opaque escaped spell keys, metadata, absent/empty/null distinctions, ignored fields, immutability, malformed leaves and 12,000-entry boundaries. Deterministic tests are separate from live Foundry verification.
