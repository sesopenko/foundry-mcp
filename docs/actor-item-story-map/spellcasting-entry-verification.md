# Spellcasting-entry book and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. These are complete rulebook reads and persisted-source observations. They do not prove current usable resources, effective statistics or casting legality.

## Complete rulebook reads

Read complete canonical text through `read_pdf_pages`, using the following immutable revisions. Every page returned `next_offset=null`; reading order and table structure remain unverified. The conclusions below use prose rather than inferred table associations.

| Book | Printed / physical page | Characters | Revision |
| --- | --- | --- | --- |
| Player Core Remaster | 297 / 298 | 5261 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` |
| Player Core Remaster | 298 / 299 | 5706 | same |
| Player Core Remaster | 299 / 300 | 5273 | same |
| GM Core Remaster | 123 / 124 | 5761 | `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` |

Prepared spells are individual preparations: casting one expends that preparation, so multiple castings normally require multiple preparations of the same spell. Cantrips are an explicit exception. Spontaneous spells instead draw on slots at the time of casting; repertoire membership is distinct from expenditure. Heightening has separate requirements, including knowing the desired rank for ordinary spontaneous casting. A higher slot alone does not establish heightened benefits.

Focus spells normally use a shared focus pool rather than ordinary slots. Multiple granting sources retain their traditions and attributes while sharing that pool. Innate spells instead have frequencies and traditions supplied by their granting abilities; ordinary slots cannot normally pay for innate spells. None of these resource meanings can be collapsed into a single remaining-slot count.

GM Core allows a creature-specific exception permitting focus spells to use spell slots. Therefore a reader must preserve the creature's authored context rather than apply PC resource rules as universal validation. Reading a source entry does not trigger preparation, expenditure, Refocus, casting, rolling or chat.

## Pinned source contract and discrepancy

The [PF2e 8.6.1 source interface](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts) declares the entry mode/tradition/ability, source attack/DC numbers, proficiency, automatic-heightening setting and slots. Slot preparations are arrays containing `id` and `expended`. The array position identifies an individual preparation; repeated IDs must not be deduplicated. IDs are owner-local claims, not independently valid document UUIDs. Selected source fields retain absence rather than fabricate defaults.

There is a real upstream discrepancy: `SlotKey` in that interface covers `slot0` through `slot10`, but the pinned official [template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json#L571) explicitly supplies **slot0 through slot11**. The installed runtime's source matches the template. Retain slot11's selected source leaves if present, with a documented unknown game meaning; do not invent an eleventh spell rank or label it malformed solely because the TypeScript union omits it.

The upstream [migration 921](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/migration/migrations/921-spell-slot-arrays.ts) restores preparations to arrays from object values. This documents the historical shape change, but does not authorize a reader to run migrations or silently coerce object-shaped preparations. Current observed preparations omit `expended`; preserve that absence rather than assume false or claim availability. Source attack/DC numbers are not established effective PC statistics. Display configuration such as `showSlotlessLevels` is not a resource.

## Existing read-only runtime

Inspected public world and scene collections, actual token Actors and Item `toObject(true)`. Indexed all 26 available Item packs by type without importing or hydrating unrelated documents. No document writes, slot expenditure, activation, preparation methods, rolls, chat or enrichment occurred.

| Scope | Observed entries / shapes |
| --- | --- |
| Standalone world Items | 0 spellcasting entries |
| Supported world Actor-owned Items | 85 entries, all NPC-owned |
| World entry modes | 14 prepared, 11 spontaneous, 49 innate, 11 focus |
| World slot records | 1020; all preparations arrays, all entries contain slot0–slot11 |
| World preparations | 285 individual records; all 285 omit expended; 2 have id null |
| Zero-value nonempty preparation groups | 78 slot records with value 0 and at least one nonempty id |
| Repeated-ID preparation groups | 9 slot records with repeated nonempty ids |
| Scene-token occurrences | 338: 33 prepared, 54 spontaneous, 230 innate, 21 focus |
| Scene-token slot records | 4056; all arrays, all 12 slot keys present |
| Available standalone Item-pack indexes | 0 spellcasting-entry rows across 26 packs |

Token occurrences can repeat linked documents; these are occurrence counts, not distinct Item counts. Actor-pack embedded entries were not exhaustively indexed. Character, familiar and standalone world/Item-pack fixtures remain unavailable live. No object-shaped preparations, expended true/false records, flexible entries or item-casting mode were established by this inspection; deterministic tests must cover those cases without manufacturing world data.

The selected prepared entry has slot value zero with populated preparations at several ranks; slot4 contains the same spell ID four times plus two other preparations, maximum 6. None of those preparations has an expended field. The spontaneous sample retains positive stored value/max counts separately. Focus and innate samples retain their mode with empty slot arrays; that does not establish a zero focus pool or zero innate uses.

Four selected entries, one per observed mode, had identical complete serialized source before and after inspection, with SHA256 calculated through the standard browser crypto API. The ignored reproducible selector `.local/spellcasting-entry-selector.js` chooses these modes plus zero-value and repeated-ID cases, returns actual canonical Item/Actor identity, exact selected slot source and fingerprints in bounded string chunks. Do not treat pack index absence as evidence about Actor-pack embedded Items.

## Acceptance still to verify

Actual authenticated `read_item` reads must consume all source pages, verify exact raw/mapped/provenance and unchanged source fingerprints, preserve repeated preparations and zero counts, and keep effective resources unsupported. Missing/null/empty and absent expended must remain distinct. Cover legacy object shapes, malformed values, permissions, stale continuations, other systems, token identity and unavailable ownership contexts deterministically. Immediate owner-local spell relationships may resolve actual identity without reading target source or merging resource counts; CORE-casting owns the full join and availability semantics.

## Actual entry-reader acceptance

Authenticated MCP consumed all source pages for five existing entries: prepared,
spontaneous, innate, focus and a selected scene-token context. Exact mode,
tradition, source attack/DC, slot values/maxima and individual prepared IDs matched
persisted source. Missing expenditure flags stayed absent. Every source path was
unique and all complete source fingerprints were unchanged after reads. The final
source page was complete; effective remained unsupported. Actual MCP discovery
explains mode-specific limits, template slot11, absent flags and malformed partial
source. No spell or casting-entry target was hydrated by this source reader.

Focused deterministic tests verify zero slot value alongside repeated preparations,
independent true/false expenditure flags, null and absent IDs/flags, legacy object
preparations, malformed members and unsupported slot keys. Invalid portions are
omitted with partial reasons and source paths; no fake empty/absent data replaces
invalid source. Tests additionally cover exact Unicode prose continuation,
permissions, non-PF2e rejection and stale changed preparations. Full suites passed:
235 Python tests (one skipped), 262 JavaScript tests. No casting, consumption,
preparation, expenditure, imports, rolls, chat or document writes occurred.

This closes the Item definition/resource-source story. CORE-casting still must
join actual spells and represent supported contextual resources. Effective PC
statistics, usable casting resources, focus/innate pool interpretation and actual
expenditure remain unverified advanced capabilities. Live character/familiar and
standalone world/pack entry fixtures remain unavailable.
