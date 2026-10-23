# Background source field audit

`backgroundFields` selects detached `Item.toObject(true)` source for `type: background`, audited against PF2e **8.6.1** [background/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/background/data.ts), [ABC feature schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts), [shared Item schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts) and [static template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json). Descriptors use mapping `pf2e.background.source.v1`, exact source paths/presence/value and limitation `background_source_not_effective_character`. The pure selector does not establish live runtime or future-version compatibility.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `boosts/{key}/value/{i}` | `background_boost_offer_code`: ordered string offers. Empty arrays retain the parent path. |
| `boosts/{key}/selected` | `background_boost_selected_code`: nullable string selection, distinct from offers. Missing/empty maps retain parent marker `background_boost_slots`. No singleton-selection inference. |
| `trainedSkills/value/{i}` | `background_trained_skill_code`: ordered skill code strings. Empty list retains its parent path. |
| `trainedSkills/lore/{i}` | `background_lore`: ordered exact Lore strings, including empty strings. No Lore Item creation or acquired-training assertion. |
| `items/{key}/{uuid,img,name,level}` | `background_feature_uuid`, `background_feature_image`, `background_feature_name` strings; `background_feature_level` nonnegative integer. Empty/missing maps retain parent marker `background_feature_entries`. Configured definition references do not prove an Actor acquired the referenced feature. |
| `traits/value/{i}`, `/otherTags/{i}`, `/rarity`, `slug` | `background_trait_code`, `background_other_tag_code`, `background_rarity_code` strings; `background_source_slug` nullable string. Unknown codes remain exact source strings. |
| `publication/{title,authors,license,remaster}` | `background_publication_title`, `_authors`, `_license` strings; `_remaster` boolean. |

Arbitrary persisted slot and feature keys are JSON Pointer escaped (`~` → `~0`, `/` → `~1`). Each keyed map and array is bounded to 12,000 entries; malformed or oversized selected values reject rather than silently dropping entries. Missing descriptors omit `value`. Explicit null is accepted only for nullable selections and slug; empty arrays/maps and missing values remain distinct. No template defaults are reconstructed, even where the static template supplies an empty list or boost slot.

This source package does not calculate effective attributes, training ranks, duplicate-training substitutions, skill-feat acquisition, Lore acquisition or Actor totals. It does not execute rules, hydrate UUIDs, enrich descriptions or inspect prepared fields. Description extraction and identity/permissions belong to the shared reader. Reference resolution and actor joins require their own contract and evidence; source configuration alone supplies no acquired-document claim.

`tests/js/actor-background.test.js` covers offered versus selected boosts, null/empty/missing distinction, named references, escaped keys, metadata, immutability, unknown codes, inherited/unrelated fields, malformed leaves and 12,000-entry boundaries. This deterministic coverage is separate from live Foundry verification.


## Explicit definition links and current coverage

Explicit `relationships` returns `background_feature_reference` for each stored
feature UUID descriptor under its exact escaped source path. Mapping is
`pf2e.background.feature-reference.v1`; limitation is
`definition_reference_not_acquired_feature`. Keys are
`relationships:background:<source path>`. Empty/absent root feature maps return
empty/missing; absent UUID leaves retain missing source markers. Repeated
UUIDs remain distinct source occurrences, with lookup cached within a snapshot.

Resolved results contain canonical target_uuid, document_name Item, type,
bounded name/name_truncated and token_uuid for a synthetic target. Follow
read_item with those selectors. Missing/denied/unsupported/unverified results
contain only status and null UUID; denied metadata is withheld. At most200
immediate references resolve; source maps/lists independently admit12000 entries.
No target source, recursive feature expansion, acquisition or grant is evaluated.
Source, target identity/name and permission changes invalidate continuations.

Empty structured Lore/training or configured features do not prove no benefit.
Animal Whisperer has descriptive terrain Lore choices despite an empty source
Lore array; rare Amnesiac is a real exception to the ordinary package. Read
exact description for those choices and exceptions. Lore strings are labels,
never invented Item UUIDs. Combining background claims with actual acquired
Lore/feat Items and merging multiple contributors belongs to CORE-build; that
acceptance remains open and this Item story is In progress.
