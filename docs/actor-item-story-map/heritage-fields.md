# Heritage source field audit

`heritageFields` selects detached `Item.toObject(true)` source for `type: heritage`, audited against PF2e **8.6.1** [heritage/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/heritage/data.ts) and shared [base/data/model.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts). The local evidence checkout `.local/pf2e-research` was checked at that exact revision. Descriptors use mapping `pf2e.heritage.source.v1`, exact source paths/presence/value and limitation `heritage_source_not_effective_character`. The pure selector does not resolve references or establish runtime verification.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `ancestry` | `heritage_ancestry_association`: absent marker or explicit null only. Null preserves a source association fact; it does not infer ancestry exclusivity, owner ancestry, acquired benefits or effective eligibility. |
| `ancestry/{name,slug,uuid}` | `heritage_ancestry_name`, `heritage_ancestry_slug`, `heritage_ancestry_uuid`: nonnullable strings from a populated association object. Only these leaves are selected; no populated object dump or fabricated document identity. UUID is a configured reference, not proof the owner has that ancestry. |
| `traits/value/{i}`, `/otherTags/{i}`, `/rarity` | `heritage_trait_code`, `heritage_other_tag_code`, `heritage_rarity_code`: source strings. Ordered duplicates and unknown codes remain exact. Missing/empty lists retain parent markers. |
| `slug` | `heritage_source_slug`: nullable source string. |
| `publication/{title,authors,license,remaster}` | `heritage_publication_title`, `_authors`, `_license`: strings; `_remaster`: boolean. |

Missing descriptors omit `value`; explicit null is permitted only at the ancestry association root and shared slug. A populated ancestry object emits all three leaf descriptors with exact presence, including missing leaves, and no parent descriptor. An empty association object is therefore distinct from a null association. Primitive association roots, arrays, explicit undefined leaves, nonstring ancestry leaves and malformed code lists reject without coercion or default reconstruction. Each list is bounded to 12,000 entries; oversized lists reject without truncation. Shared `read_item` byte/count pagination applies separately.

Heritage is nonphysical: quantity, price, bulk, equipment state, level, rule elements and arbitrary flags are not selected by this helper. Description handling belongs to the bounded shared source reader. No getter-based preparation, rule execution, UUID hydration, ancestry substitution, grants, automatic application or effective Actor calculation occurs. The caller checks `game.system.id` before applying PF2e semantics; this detached helper dispatches only on Item type.

`tests/js/actor-heritage.test.js` covers populated and null ancestry association, missing roots/leaves, empty strings/lists, ordered duplicates, unknown codes, exact metadata, malformed/oversized inputs, 12,000-entry acceptance, source immutability and exclusion of unrelated/inherited/prepared data. Integration, permission/context identity, named-reference resolution and live verification require separate evidence; these tests establish source selection only. PF2e 8.6.1 is the schema baseline; live v13 and future system releases remain unverified.


## Explicit ancestry association link

`relationships` returns one record, key `relationships:heritage:ancestry`, concept
`heritage_ancestry_reference`, map `pf2e.heritage.ancestry-reference.v1`, limitation
`ancestry_association_not_owner_membership`. The raw contributor is the exact
`/system/ancestry` absent/null marker or `/system/ancestry/uuid` leaf.
A null association returns `{status:'unassociated',target_uuid:null}`. Missing
association/UUID returns missing; malformed UUID claims stay source and resolve
unsupported without name/slug inference.

Resolved values contain canonical target_uuid, document_name Item, type ancestry,
bounded display name/name_truncated and token_uuid for a synthetic target.
Follow read_item with those returned selectors. Actual target type must be
ancestry; another supported Item type remains unsupported. Missing/denied/
unsupported/unverified targets disclose no resolved identity. Target context is
independent of the heritage owner's world/pack/token context.

The link is a definition association, not proof the owner currently has that
ancestry, ancestry exclusivity or an eligibility decision. No target source,
features, effective benefits or grants are read. Source, resolved name/identity
and permission changes invalidate continuations. Null-association versatile
heritages remain readable alongside ancestry-specific definitions; no universal
one-heritage limit is enforced by this reader.
