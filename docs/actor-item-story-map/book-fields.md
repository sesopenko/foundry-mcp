# Book source field audit

`bookFields` selects detached `Item.toObject(true)` source for `type: book`, audited against PF2e **8.6.1** [book/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts). The [book document implementation](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/document.ts) supplies no book-specific effective contents or preparation contract. This selector establishes persisted source coverage; relationship resolution, MCP validation and live behavior require separate evidence.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["source_only_no_book_ownership_or_preparation"]`. Integration uses mapping `pf2e.book.source.v1`. Missing paths have no `value`; explicit undefined and malformed selected values reject. Unknown string codes, array order, repeated references and nullable slug remain unchanged. Populated source objects are never returned.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `category` | `book_category_code`: string. Current categories are `formula` and `spell`; unknown strings remain source codes. |
| `capacity` | `book_capacity`: finite number, preserved without rounding, filling a default or computing current use. |
| `contents/{i}` | `book_content_uuid`: ordered string claims. Duplicates remain separate indexed entries. Empty arrays retain the parent path with `[]`; missing arrays retain an absent parent marker. Invalid UUID strings remain source claims rather than becoming fabricated document identities. |
| `traits/value/{i}`, `traits/otherTags/{i}` | `book_trait_code`, `book_other_tag_code`: ordered strings, with empty/absent parent markers. |
| `traits/rarity` | `book_rarity_code`: string. |
| `slug` | `book_source_slug`: nullable string, without inferred fallback. |
| `publication/{title,authors,license,remaster}` | `book_publication_title`, `_authors`, `_license`: strings; `_remaster`: boolean. |

Shared `physicalFields` supplies quantity, price denominations and price-per basis, container ID, carry state, material, HP, hardness and other common stored physical fields without duplicate paths. A contents UUID is a reference to a definition, not an actual owned Item in the Actor's inventory. The helper never hydrates references, copies their source, imports their Items, infers formula knowledge, adds spellcasting entries, prepares spells or evaluates castability. Capacity and content count do not establish an eligibility check. The source schema excludes `subitems`; no serialized attachment or prepared runtime contents getter is inspected. Authored descriptions remain a separate exact, bounded prose section.

`tests/js/actor-book.test.js` verifies duplicate and ordered references, unknown categories and source claims, finite numeric capacity, missing/empty/null distinctions, malformed selected leaves, immutability, unique physical-source paths and exclusion of prepared or unrelated getters. These deterministic tests do not establish live populated-book fixtures or rulebook ownership/preparation behavior.


## Explicit immediate relationships

An explicit `relationships` request resolves up to200 content claims; larger
collections fail `ReadFailed` with source-first/selected-UUID recovery. Source
reading remains available without content hydration. Each original index has
key `relationships:book:contents:<index>`, concept `book_content_reference`,
source donor the book UUID and `/system/contents/<index>`. Duplicates preserve
separate records while one snapshot caches each identical lookup once.

Map `pf2e.book.content-reference.v1` uses limitation
`stored_book_contents_not_ownership_or_preparation`. Resolved values contain
`status`, `target_uuid`, `document_name:'Item'`, `type`, `name`,
`name_truncated`, plus `token_uuid` for a synthetic target. Labels are bounded
actual document display names. Canonical targets may be world, compendium or
owned Items on supported Actor types; affliction Items remain unsupported.
They do not acquire the book owner's inventory/preparation context.
Missing, denied, unsupported and unverified targets have only `status` and
`target_uuid:null`; denied identities are withheld. Invalid UUID claims remain
raw strings with unsupported resolution, without name search or inference.

Empty/absent arrays produce key `relationships:book:contents` and the exact
parent source marker, with status `empty`/`missing` respectively and null target.
No target source, descriptions, nested book contents or casting state is read.
Shared snapshots recheck permissions, target identity/display name and source
claims after awaits and on continuations. Changed data requires restarting.
These deterministic contracts do not close the representative live-book gate.
