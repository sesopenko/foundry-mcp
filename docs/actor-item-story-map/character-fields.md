# Character selected-source field audit

This is the PF2e-specific ACT-character **source checkpoint** contract, audited
against PF2e **8.6.1**, research checkout HEAD
`28d9d156f252d084371d994dc359509b49eadf18`. Implementation and live acceptance
remain separate evidence. Select detached `Actor.toObject(true)` source; do not
read prepared `actor.system` properties or sheet data to fill source omissions.

Authoritative pinned sources:
[character source and prepared interfaces](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts),
[shared creature source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts),
[base Actor source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/base.ts),
[base model](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/model.ts),
and [template defaults](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json).
There is no character-specific field-model schema in this pinned source: the
character contract combines interfaces and legacy static template. A numeric
TypeScript declaration is not proof of integer, positive or bounded validation.

## Exact selected allowlist

Paths below are relative to `/system`. Preserve own source presence, exact
values and paths. Optional means omission is allowed, not a default value. JSON
cannot carry own-undefined; deterministic handling must not turn it into null.
Malformed admitted source fields return actionable `ReadFailed` rather than
fabricated absent/empty values. Unknown string codes stay readable without
invented labels. Selected maps/lists admit at most 12,000 entries each.

| Paths | Source types and meaning | Pinned template defaults / bounds |
| --- | --- | --- |
| `abilities` or `abilities/{str,dex,con,int,wis,cha}/mod` | Entire record is explicitly nullable; otherwise six attribute objects with numeric `mod`. Source/manual modifiers, not prepared attributes. | Whole `abilities: null`; no numeric bounds declared. Do not replace null with six zeroes. |
| `details/level/value` | Number; recorded level, not advancement calculation. | 1; no field-schema integer/range constraint established. |
| `details/{age,height,weight,gender,ethnicity,nationality}/value` | Strings retaining authored identity, including units as text. | Empty strings. |
| `details/keyability/value` | Attribute code; selected stored key attribute, not an offered class option or computed check. | `str`; retain unknown strings without claiming known attribute meaning. |
| `details/languages/value`, `details/languages/details` | Ordered language-code array and authored string details. Source selection is not a complete effective/granted language calculation. | Empty array and empty string. |
| `details/biography/{appearance,backstory,campaignNotes,allies,enemies,organizations}` | HTML strings; bounded exact original prose through description continuation. No enrichment or execution. | Empty strings; these six paths appear in `Actor.htmlFields`. |
| `details/biography/{birthPlace,attitude,beliefs,likes,dislikes,catchphrases}` | Plain strings; preserve original text. | Empty strings. |
| `details/biography/{edicts,anathema}` | Ordered string arrays. | Empty arrays. |
| `details/biography/visibility/{appearance,backstory,personality,campaign}` | Booleans recording limited-ownership biography visibility configuration. They do not grant caller permission. | Appearance true; other three false. GM-only tool authorization remains independent. |
| `details/xp/{value,min,max}` | Numeric recorded XP fields. | 0,0,1000. No declared numeric bounds. Exclude `pct`: interface calls it COMPUTED and template does not store it. |
| `attributes/hp/{value,temp}` | Numeric current HP and temporary HP source. | Both 0; no declared numeric bounds. |
| `attributes/hp/tempSource` | Optional string claiming the owner-local Item ID that supplied temporary HP. | Absent. Retain as unresolved source claim; no automatic Item hydration. |
| `attributes/hp/sp/value` | Optional numeric stamina source for the stamina variant. | Absent. No stamina maximum is source here. |
| `skills/<skill>/rank` | Partial standard-skill record of ranks `0..4`; label only valid integers as untrained/trained/expert/master/legendary. | Empty skills record; no omitted rank becomes zero. Rank is not a check total. Lore comes from owned Lore Items. |
| `resources/heroPoints/{value,max}` | Numeric stored current/maximum hero-point fields. | 1 and 3; template defaults are not schema bounds. |
| `resources/focus/value` | Optional numeric stored current focus. | Absent. Character source explicitly forbids `focus.max`; exclude `max` and `cap` even if encountered. |
| `resources/crafting/infusedReagents/value` | Optional nested numeric source resource. | Absent. No source maximum; no crafting availability claim. |
| `resources/resolve/value` | Optional numeric resolve source for stamina variant. | Absent. No source maximum. |
| `build/attributes/manual` | Optional containing build/attributes records; boolean when this leaf exists. | Build absent. Do not infer manual false from absence or nullable abilities. |
| `build/attributes/boosts/{1,5,10,15,20}` | Each level key optional; ordered arrays of attribute codes. Recorded choices only. | Build absent. Preserve duplicate and unknown codes; do not perform boost arithmetic or infer eligibility. |
| `build/attributes/apex` | Optional attribute code or explicit null, for Automatic Bonus Progression apex increase. | Absent. Null and absent remain different. |

All biography prose/string arrays and `details/languages/details` belong to the
explicitly requested bounded description section. Biography visibility booleans
may remain in default source records. Do not accidentally emit unbounded
biography strings via a containing-object descriptor. Shared extraction
owns canonical Actor/token/pack identity, ownership/assignment, version and
embedded Item summary/navigation context; these do not belong to character
`system` field mapping.

## Deliberate exclusions and source/prepared discrepancies

`CharacterSystemSource` explicitly declares `traits?: never`, `perception?:
never` and `saves?: never`. There is no character publication schema. Do not
reuse NPC or Item trait/publication selectors, even if unexpected properties are
present in a fixture. Character traits, size, rarity, senses, AC, saves, movement,
IWR totals, effective attributes, class DCs, Strikes and other effective sections
remain separately gated. Inherited optional IWR source fields are outside this
selected checkpoint allowlist; their omission is not proof that IWR is absent.

Character HP narrows the inherited HP shape: `max` is not declared in
`CharacterAttributesSource.hp`. Exclude source `hp.max`, recovery statistics and
prepared stamina maxima. Character `resources` similarly replaces the broad
creature resource shape: investiture, mythic points, resource maxima other than
hero points, and focus capacity are prepared data, not selected source fields.

Prepared build additions include ancestry/background/class boosts, keyOptions,
allowedBoosts, flaws and granted-language data. Prepared identity convenience
fields include ancestry/heritage/class/deities; acquire their actual owned Item
identities through Build rather than treating these prepared properties as
persisted character identity. Selected attack proficiencies, initiative, formula
records, PFS organizational details and template-only exploration assignments
are outside this checkpoint; their exclusion must not be represented as zero or
an exhaustive absence claim.

## Reused complete rulebook reads

Use existing canonical private-book reads instead of charging for duplicate
reads. All refer to Player Core Remaster immutable revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`:

- [Class verification](class-verification.md) records complete printed p.19
  (physical20), separating boosts and recorded choices; it also preserves the
  unresolved p.19/p.91 boost-wording discrepancy. Do not implement arithmetic
  from that discrepancy.
- [Weapon verification](weapon-verification.md) records complete printed275
  and418 (physical276 and419), separating stored weapon source from effective
  Strike attack/damage and the Strike action.
- [Casting-entry verification](spellcasting-entry-verification.md) records
  complete printed297–299 (physical298–300), separating slots, individual
  preparations, focus pools and innate frequencies from castability.

These ledger entries record `next_offset: null`; extracted reading order and
table associations remain unverified. None establishes a public prepared-stat
runtime interface. M-PC joins and all effective-interface gates remain open.
