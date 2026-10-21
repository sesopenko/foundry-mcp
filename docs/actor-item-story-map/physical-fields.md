# Shared physical source fields

`CORE-physical` selects persisted fields from `Item.toObject(true)` for PF2e
8.6.1 (commit `28d9d156f252d084371d994dc359509b49eadf18`) on Foundry
14.369. It does not call PF2e preparation, sheet, activation, or calculation APIs.

The pure `physicalFields(source)` helper returns `null` for nonphysical types,
including `kit`, and detached field descriptors for `weapon`, `armor`, `shield`,
`equipment`, `consumable`, `ammo`, `backpack`, `book`, and `treasure`.
Descriptors contain JSON Pointer `path`, `present`, optional exact primitive
`value`, `concept`, and `limitations`. Empty supported `subitems` has exact
`value: []`. The caller supplies canonical document identity, source provenance,
text fragmentation, response bounds, revisions, and continuation handling.
This helper alone is not a published MCP tool or a complete physical Item reader.

## Evidence and allowlist

The immutable [PhysicalSystemSource and related source interfaces](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts)
and [physical and concrete templates](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json)
establish these persisted paths under `/system`:

| Source paths | Presentation and limitations |
| --- | --- |
| `level/value`, `quantity`, `baseItem`, `size` | Item level, stack quantity, base-item code, size code; retain unknown codes. |
| `bulk/value` | Persisted Bulk; no effective, carried, or container total is calculated. |
| `hp/value`, `hp/max`, `hardness` | Source item HP and Hardness; zeros may be template placeholders, not evidence of applicability or usability. |
| `price/value/pp`, `gp`, `sp`, `cp`; `price/per`, `price/sizeSensitive` | Exact denomination amounts and source per-quantity basis; missing denomination or per value stays missing. No multiplication, currency conversion, size adjustment, or resale calculation. |
| `equipped/carryType`, `inSlot`, `handsHeld`, `invested` | Source carrying/slot/hands/investment state; null investment is distinct from false. Possession does not establish active benefits. |
| `containerId` | Local parent-container ID, not a UUID or attachment ID. Resolution and containment validation belong to later joins. |
| `material/type`, `material/grade` | Source material codes; no resistance, damage, or durability calculation. |
| `identification/status`; `identification/unidentified/name`, `img`, `data/description/value` | GM-source identification and optional alternate presentation. Does not substitute unidentified text for canonical identity or suppress original source. No image is fetched or description executed. |
| `temporary` | Optional source temporary flag; absence is not false. |
| `usage/value` | Exact source usage code where permitted below; no inferred hands, investment, or activations. |

A descriptor with `present:false` has no `value`; present `null`, `0`, `false`,
and empty strings remain exact values. Missing children of a null/absent parent
are absent selected paths, not a claim that the parent is an empty object.
Malformed nonprimitive selected leaves fail extraction instead of exposing an
unrestricted object. Unselected flags, migration records, rule elements, derived
Bulk fields, broken thresholds, material effects, and type-specific statistics
are omitted.

Source `description.value` remains the existing separately selected and bounded
`description` section; this helper does not duplicate it. Unidentified alternate
description strings require the same bounded text handling at integration.

## Concrete overrides and attachments

[Armor](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/armor/data.ts)
and [shield](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/shield/data.ts)
source explicitly prohibit `usage`; their prepared worn/held usage is excluded
even if an input supplies it. [Treasure](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/treasure/data.ts)
also prohibits source usage and investment; its equipped schema selects only
`carryType`, so `handsHeld` and `inSlot` are excluded.

Weapon, armor, shield, and equipment sources declare `subitems`; select only
`/system/subitems/N/_id`, `/name`, and `/type` for direct serialized attachments.
Each is marked `serialized_source_not_document` and
`attachment_interpretation_pending`. No attachment UUID, canonical document
identity, recursive expansion, activation, or effective modifier is invented.
An empty array and an absent array remain distinct. Actual Item document
relationships must come from the caller's resolved Foundry documents.

[Ammo](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ammo/data.ts),
[consumable](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/consumable/data.ts),
[book](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts),
[container/backpack](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/container/data.ts),
and treasure prohibit `subitems`; no attachment paths are selected for them.
Backpack capacity/ignored Bulk/stowing and book contents remain type-story work.
Kit is a bundle schema and is outside this helper entirely.

## Verification

`node --test tests/js/actor-physical.test.js` covers exact zeros/false/null,
missing source leaves, custom codes, unidentified GM source, stack prices with
`price.per`, concrete omissions, serialized attachment identity restrictions,
no recursive/unselected object exposure, and malformed selected fields.
These deterministic source-selector tests do not establish effective mechanics
or complete runtime coverage for every Item type. Live public extraction is
validated independently by the reader integration.

### Existing-runtime source-shape check, October 20, 2026

A read-only authenticated bridge probe on Foundry14.369/PF2e8.6.1 enumerated
existing world Items and all world Actors' embedded Items, then inspected one
`toObject(true)` source per available physical type. No documents were created
or changed; no names, identifiers, or item statistics were recorded.

| Type | Documents in sampled world/embedded scope | Sample usage.value | Sample price.per | Sample subitems |
| --- | ---: | --- | --- | --- |
| weapon | 95 | string | absent | empty array |
| armor | 24 | absent | absent | empty array |
| shield | 5 | absent | absent | empty array |
| equipment | 100 | string | absent | empty array |
| consumable | 91 | string | absent | absent |
| ammo | 11 | absent | number | absent |
| backpack | 3 | string | absent | absent |
| book | 0 | unverified | unverified | unverified |
| treasure | 57 | absent | number | absent |

Counts cover this explicit world/embedded scope, including Actors outside the
three reader-supported types; they are not global library or compendium counts.
One source per available type establishes only those observed shapes. No live
nonempty attachment, book, unidentified alternate-description, or effective
mechanics claim follows from this probe; those remain deterministic/schema
coverage or later representative-fixture work. An initial larger probe was
truncated by development serialization and was replaced by the bounded summary
above. Numeric, boolean, string, and nullable selected leaves are validated
against their source types; malformed attachment elements also fail extraction.

### Optional PriceField source correction

The live integration exposed an own `price.sizeSensitive` property whose source
value was `undefined` on treasure. The pinned
[PriceField schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/schema.ts)
explicitly defines this optional BooleanField with `initial: undefined`; its
`initialize` method separately assigns prepared `false`. The selector treats
only this exact undefined source path as absent (`present:false`, no value),
retaining strict boolean validation for actual values. It does not copy the
prepared false or relax required source-field checks. A regression test failed
before this correction and passed afterward. A cache-busted, read-only helper
probe then returned no extraction errors across existing world physical Items
and physical Items on supported world Actors. This verifies extraction shapes,
not complete mechanics or missing representative book/attachment fixtures.
