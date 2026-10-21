# NPC attack Item selected source fields

ITEM-melee source and named-reference reader evidence, October 20, 2026. Delivered through `read_item` on Foundry14.369/PF2e8.6.1.

`meleeFields(source)` accepts detached `Item.toObject(true)` data and returns
null for non-`melee` Items. Descriptors contain `path`, `present`, `value` when
present, `concept`, `limitations`, and optional `mapped_value`. Paths are JSON
Pointers, preserving record keys with `~` → `~0` and `/` → `~1` escaping.

## Schema and rulebook evidence

Read the pinned PF2e **8.6.1**
[MeleeSystemSource/defineSchema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/melee/data.ts),
[attack-action codes](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/melee/values.ts),
and shared [ItemSystemSchema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts).
Source schema establishes the contract; preparation code explains exclusions.
In particular, preparation may supply a non-Strike area or rewrite bleed's
category; the selector performs neither operation. Prepared material/runes are
excluded. There are no new Foundry API calls in this pure helper.

Actual source-page rereads used a fresh authenticated local MCP session after
the existing session became stale following a server restart. Every page
returned `next_offset=null`:

| Book | Printed / physical pages | Revision |
| --- | --- | --- |
| GM Core Remaster | 119–120 / 120–121 | `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` |
| Player Core Remaster | 418 / 419; 303 / 304 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |

GM Core's prose establishes independently authored creature Strike attack
bonuses and damage expressions. These are not merely attribute modifiers or
carried weapon damage. Player Core distinguishes weapon/unarmed Strikes from
other attacks, including spell attacks. No numeric table relationship was
inferred from extracted adjacency; reading order/table warnings remain.

## Allowlist and interpretation

All paths below begin `/system/`.

| Path | Concept and source interpretation |
| --- | --- |
| `action` | `attack_action`: strike → Strike; area-fire → Area Fire; auto-fire → Auto Fire; unknown code retained, never labelled Strike |
| `bonus/value` | `authored_attack_bonus`; not an attribute modifier, final elite/weak attack or recomputed PC total |
| `subjectToMAP` | `subject_to_multiple_attack_penalty`; flag only, no penalty calculation |
| `area/type`, `area/value` | `area_shape_code`, `area_size_feet`; no generated area or target selection |
| `range` when null | `attack_range_kind` with raw null, mapped `no_explicit_range`; no exclusive melee/ranged inference |
| `range/increment`, `range/max` | `ranged_increment_feet`, `ranged_maximum_feet`; preserve nulls, never infer maximum from increment |
| `damageRolls/<key>/damage` | `damage_formula`; exact component expression, never evaluated |
| `damageRolls/<key>/damageType` | `damage_type_code`; retain unknown codes |
| `damageRolls/<key>/category` | `damage_category_code`; preserve null, persistent/splash or custom source value; no bleed-category rewriting |
| `traits/value/<index>`, `traits/otherTags/<index>` | `npc_attack_trait_code`, `npc_attack_other_tag_code`; exact ordered codes |
| `attackEffects/value/<index>` | `additional_effect_label`; named source label, not necessarily UUID or complete effect definition |
| `slug` | `source_slug`, including explicit null |
| `publication/title`, `publication/authors`, `publication/license`, `publication/remaster` | Corresponding `publication_*` source metadata; no book/errata precedence inferred |

Missing fields emit absent records, explicit null stays null, and zero stays
zero. Null/absent area and range emit container markers; non-null objects emit
only selected primitive leaves. Explicit empty arrays/maps use `[]`/`{}`
markers; nonempty damage maps emit three primitive fields per original key.
Malformed selected shapes fail instead of exposing arbitrary source objects.
Source metadata is exact; reader pagination owns byte/count bounds and can reject
indivisible oversized metadata explicitly.

The document type `melee` does not determine range. Non-null source range fields
carry explicit ranged concepts/limitations, while absent range remains unknown.
No matching carried weapon replaces these authored attacks. Weapon linkage
flags, trait configuration, prepared material/runes, implicit rules and
descriptions are outside this allowlist. Exact descriptions remain available
through the existing explicitly requested section.

## Deterministic acceptance evidence

Seven focused tests cover ranged records stored as `melee`, all three declared
attack modes plus unknown codes, mixed damage/category components, escaped map
keys, non-UUID effect labels, absent/null/empty/zero distinctions, no preparation
defaults, no source mutation, malformed-data rejection, null-range thrown attacks and hostile map keys. Reader integration separately verifies explicit indivisible metadata byte-budget failures.

Reader integration applies descriptor mappings with `pf2e.melee.source.v1`
provenance and includes selected fields in revisions, count/byte pagination and
post-read permission checks. `relationships` preserves each stored additional
label as an unverified reference with null target_uuid; even UUID-looking labels
are never treated as selectors. Missing/empty arrays emit distinct raw markers.
Relationships-only reads select only those labels, so malformed unrequested
bonus/damage fields cannot block them. Exact descriptions and unsupported
effective sections remain independently usable.

Four browser reader tests and four Python boundary tests cover actual cross-
language DTOs, bounded text, indivisible metadata errors, stale changes, carried-
weapon independence, no effect resolution and non-PF2e rejection. Live actual
MCP checked three existing contexts (explicit range, null/thrown and effect
labels), plus an embedded attack on a selected compendium NPC. Persisted source
fingerprints stayed unchanged. No full PC Strikes, target-dependent math,
complete elite/weak values or unsampled non-Strike live variants are certified.

## Existing-runtime source audit

Read-only checks through a fresh authenticated FastMCP client on October 20,
2026 used core14.369/PF2e8.6.1 and the existing development world. All 202
available `melee` Items from world Items and supported world Actors passed the
pure source selector. Serialized source snapshots matched before/after every
selection; no names, UUIDs, document writes, rolls, or imports were involved.

All 202 source actions were `strike`; 175 had null source range and 27 had a
non-null range object. **Five null-range sources also had a thrown trait.**
Therefore null-range maps to `no_explicit_range` with `source_null_range_does_not_exclude_trait_derived_ranged_attacks`; it cannot
establish exclusive melee capability or replace the separately retained trait
codes. Inspection of pinned preparation code explains that thrown traits can
supply prepared range; this is exclusion evidence, not permission to call that
preparation or reproduce its calculation. `area-fire` and `auto-fire` remain
schema/deterministic coverage without a representative live fixture.

Across 242 selected damage components, category was null on 225, splash on
five, and persistent on 12. Sixty-three attacks had at least one additional
source effect label. These are labels, not verified document identities or
resolved rule definitions. No mechanical inference follows from these counts.

One attack on an existing Monster Core compendium NPC also passed selection.
Its owner was an NPC in the selected pack; owner and Item OBSERVER permissions
passed and source snapshots remained unchanged. This verifies hydrated source
reading without importing. It does not certify every pack record, authored
attack variant, effective bonus, computed maximum range, or target calculation.
No helper source-type mismatch was observed, and the selected melee schema
fields do not share the optional-undefined defaults found on action Items.
