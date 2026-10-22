# Container source field audit

`containerFields` selects detached `Item.toObject(true)` source for `type: backpack` against PF2e **8.6.1** [container/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/container/data.ts). The type means a container and need not represent a literal backpack. This pure selector establishes source coverage; production integration, relationship resolution and runtime behavior require separate evidence.

Descriptors contain `path`, `present`, optional exact `value`, `concept` and `limitations: ["source_only_no_container_bulk_calculation"]`. Missing paths omit `value`. Numbers must be finite and remain exact; booleans are not coerced. Unknown string codes and array order remain unchanged. Null is accepted only for `slug`. Empty trait arrays retain their parent path; populated arrays emit indexed primitive leaves.

| Paths under `/system` | Concepts and source types |
| --- | --- |
| `stowing` | `container_stowing`: boolean source configuration. |
| `bulk/heldOrStowed` | `container_bulk_held_or_stowed`: finite number; stored configuration, not effective current Bulk. |
| `bulk/capacity` | `container_bulk_capacity`: finite number; capacity is not current contents Bulk. |
| `bulk/ignored` | `container_bulk_ignored`: finite number; a source parameter, not an unconditional Bulk subtraction. |
| `traits/value/{i}`, `traits/otherTags/{i}` | `container_trait_code`, `container_other_tag_code`: string codes, or empty-array markers at parent paths. |
| `traits/rarity` | `container_rarity_code`: string. |
| `slug` | `container_source_slug`: nullable string, without fallback inference. |
| `publication/{title,authors,license,remaster}` | `container_publication_title`, `_authors`, `_license`: strings; `_remaster`: boolean. |

Shared `physicalFields` supplies `bulk.value`, `usage.value`, `containerId`, equipped state and other common physical source without duplicate paths. Containment relationships must join actual Items within the same actor instance separately; this helper neither resolves nor recursively embeds contents. Container `subitems` are not part of the pinned source contract. `collapsed` is presentation state and is excluded. No current contents Bulk, total Bulk, capacity enforcement, ignored-Bulk application, accessibility, prepared getter, rule evaluation or writes occur. Descriptions remain a separate explicit bounded section.

`tests/js/actor-container.test.js` verifies exact configuration, absent versus empty values, malformed selected leaves, finite numbers, zero and false retention, unknown codes, immutability, unique shared paths and excluded getters. Pure tests do not establish live containment, actor totals or provenance validation.

## Explicit stored containment relationships

`actorContainerRelationships.js` reads actual owner Items through public document
APIs and only selects physical `containerId` claims. It never reads prepared
contents or calculates Bulk. Source-only requests do not scan inventory. Owner
scope is capped at 12,000 Items with ReadFailed, separately from response paging.

Records use `pf2e.container.contents.v1` and limitation
`stored_containment_not_effective_bulk`. `container_parent` contributes the
selected container's `/system/containerId`. Resolved values include actual
backpack target_uuid/document_name/type/name/name_truncated, a cycle boolean and
selected token_uuid when applicable. Missing/denied/unsupported/unverified retain
null target_uuid and cycle:false, which does not establish an acyclic unknown scope.

Each `container_content` contributes the actual child's containerId and appears
once under key `relationships:container:content:<actual UUID>`. Resolved child
metadata includes parent_uuid, parent_status (resolved or unsupported) and depth
1–12,000. Depth1 means the selected root is the parent. An invalid non-container
parent stays an explicit claim, never silently promoted into a valid container.
Root is never repeated as a descendant; ancestor/descendant cycles remain partial.
`container_contents` scope markers have no raw identity and distinguish verified
empty, denied potential contents and unverified unowned scope. Unreadable Item
source/name/identity is not exposed; it prevents an exhaustive empty claim.

Relationships complete after paging when the selected graph is fully readable;
otherwise reasons are container_scope_unverified, containment_cycle,
container_parent_missing, container_parent_denied, container_parent_unsupported or
container_contents_denied. Missing unrelated containers are outside this selected
subtree; CORE-inventory owns the Actor-wide graph. No document UUID is invented.
