# Kit source field audit

`kitFields` selects detached `Item.toObject(true)` source for `type: kit`, audited against PF2e **8.6.1** [kit/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/kit/data.ts), [base model](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts) and [PriceField](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/schema.ts). Kits are not PhysicalSystemSource: their component definitions and own price do not establish inventory possession, carrying state or quantity of an owned stack.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["bundle_definition_not_owned_inventory"]`. Integration uses mapping `pf2e.kit.source.v1`. Missing paths have no `value`. Explicit undefined rejects except optional `price.sizeSensitive`, whose schema initial undefined is normalized to absence. Null, empty and missing selected source markers remain distinct. Populated objects are flattened to allowlisted leaves; unrelated source fields are ignored without inspecting their values.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `items` | `kit_items`: missing or empty `{}` marker. Populated keyed entry maps recurse; null root rejects. |
| `items/{key}/{uuid,img,quantity,name,isContainer}` and equivalent nested paths | `kit_component_uuid`, `_image`, `_quantity`, `_name`, `_is_container`: source string/string/positive integer/string/boolean. UUID strings remain authored claims; no fabricated document UUID represents a serialized component. Quantity is not multiplied across levels. |
| Each component's `items` | `kit_component_items`: absent, explicit null or empty `{}` marker; populated maps recurse. The actual recursive constructor permits entries at levels 0 through 3 because it recurses while constructor depth is `<= 2`. Level-3 entries have a NullField child: further objects, including `{}`, reject. |
| `price/value/{pp,gp,sp,cp}` | `kit_price_pp`, `_gp`, `_sp`, `_cp`: nonnegative finite integers, preserving each missing denomination independently. |
| `price/per`, `price/sizeSensitive` | `kit_price_per`: positive finite integer; `kit_price_size_sensitive`: optional boolean. No source defaults, denomination conversion, stack value or sale calculation. |
| `traits/value/{i}`, `traits/otherTags/{i}` | `kit_trait_code`, `kit_other_tag_code`: ordered string codes, preserving duplicates and empty/absent parent markers. Kit schema does not declare rarity. |
| `slug` | `kit_source_slug`: nullable string. |
| `publication/{title,authors,license,remaster}` | `kit_publication_title`, `_authors`, `_license`: strings; `_remaster`: boolean. |

Map keys retain original spelling through JSON Pointer escaping (`~` → `~0`, `/` → `~1`). Empty keys and malformed map/entry values reject. At most 12000 component entries are accepted; exceeding this limit rejects rather than silently omitting contributors. Missing required leaves remain explicit absent markers rather than receiving inferred defaults. Descriptions are handled separately as bounded exact prose. No prepared kit getters, quantity/container state from PhysicalSystemSource, component hydration, import, recursive document expansion or actor inventory mutation occurs.

`tests/js/actor-kit.test.js` covers keyed nesting and escaped provenance, the actual depth boundary, missing/empty/null markers, price basis, zero denominations, absent optional size flag, invalid numbers and types, entry bounds, immutability and ignored unrelated getters. These deterministic source checks do not independently establish live kit fixtures, relationship permissions or rulebook interpretation.


## Explicit component links

`relationships` selects each component UUID descriptor (including absent UUID
markers) and any empty/absent root items marker. Keys are
`relationships:kit:<exact source path>`; source keys and repeated UUIDs never
become fabricated owned Item identities. Mapping is
`pf2e.kit.component-reference.v1`, concept `kit_component_reference`, limitation
`bundle_definition_not_owned_inventory`.

Resolved values contain `status:'resolved'`, canonical `target_uuid`,
`document_name:'Item'`, `type`, bounded display `name`, `name_truncated`, and
`token_uuid` for synthetic target Items. Follow `read_item` with those returned
selectors. Targets retain their actual world/pack/owner/token context rather
than inheriting the kit's owner. Missing/denied/unsupported/unverified targets
contain only status and null target UUID; unreadable identities are withheld.
An empty/absent root map returns empty/missing respectively. Individual absent
UUID leaves return missing while preserving source presence.

At most200 serialized reference occurrences are resolved per explicit request.
Source reading accepts up to12000 entry definitions independently of that limit.
Oversized resolution fails ReadFailed with source-first/selected-UUID recovery.
Duplicate occurrences retain distinct source paths while caching target lookup
within each snapshot. No target source or recursively referenced kit contents
are read. Source, target name/identity and permission changes invalidate cursors.
Book and kit references share the audited immediate Item identity resolver;
book contracts remain unchanged and their regression tests pass.
