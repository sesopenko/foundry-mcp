# Actor inventory source graph

`actorInventoryRecords(target)` is PF2e-specific, verified for Foundry14.369 /
PF2e8.6.1. It reads actual Items from the selected Actor instance using public
`Actor.items`, permission checks, identities and `Item.toObject(true)`. Its source
contracts are pinned to commit
[`28d9d156f252d084371d994dc359509b49eadf18`](https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item):
`physical/data.ts`, `container/data.ts`, `weapon/data.ts` and `kit/data.ts`.
No prepared inventory/contents getters, recursive document hydration, imports,
source mutations or mechanical calculations are used.

## Record contract

All records use section `inventory`; selected source donors are actual owned
Item UUIDs. Owner scope is the selected world/pack/token Actor, including its
synthetic instance. A selected token selector remains in resolved references.
Results sort readable physical Items and kit references by UUID within each group
and contain no duplicate
keys. Limits are 12000 owner Items and 24000 selected records; exceeding either
fails extraction. The shared reader supplies paging, byte limits, revisions,
revalidation and bounded text. Keys are record identities, not document selectors.

| Key and concept | Raw source | Mapped result |
| --- | --- | --- |
| `inventory:item:<uuid>` / `inventory_item` | Actual Item `/name` and `/type` | One identity for every readable physical possession: weapon, armor, shield, equipment, consumable, ammo, backpack, book or treasure. |
| `inventory:source:<type>:<uuid>:<path>` / existing physical concept | One exact source path from [the common physical allowlist](physical-fields.md) | Original primitive/null/empty-array value, or null for absent with `present:false`; map `pf2e.physical.source.v1` and original field limitations. The unidentified alternate description is omitted and belongs to explicit `read_item` prose. |
| `inventory:container:<uuid>` / `inventory_container` | Actual possession `/system/containerId`, preserving absent/null/empty | Same-owner backpack identity when resolved; otherwise `missing`, `denied` or `unsupported`. Includes `cycle` boolean. |
| `inventory:ammunition:<uuid>` / `inventory_selected_ammunition` | Actual weapon `/system/selectedAmmoId`, preserving absent/null/empty | Same-owner ammo/weapon identity when resolved; otherwise `missing`, `denied` or `unsupported`. |
| `inventory:kit:<uuid>` / `inventory_kit_definition` | Actual owned kit `/name` and `/type` | Separate definition identity. No physical-possession row, containment edge or component expansion. |
| `inventory:scope` / `inventory_scope` | Empty raw/contributor arrays | `{status:'denied',target_uuid:null}` if any potential physical Item or kit is unreadable; otherwise `{status:'empty',target_uuid:null}` only if no readable physical Items or kit definitions exist. |

Join/reference records use mapping `pf2e.actor.inventory-source.v1`, kind
`relationship`, and limitation `stored_inventory_not_effective_benefits`.
Resolved values contain `status:'resolved'`, actual `target_uuid`,
`document_name:'Item'`, `type`, bounded `name`, `name_truncated`, and optional
selected `token_uuid`. Display names are clipped from each Item's cached persisted
`/name` source (256 Unicode code points), including resolved parent and ammunition
references. Prepared display names can include magical adjustments and are not
substituted for these source labels. No extra source read is performed.
Unresolved values contain only status and
`target_uuid:null`; container values additionally contain `cycle`. Denied
references expose no target name, type or UUID, and no denied source is read.

The graph spans every readable possession, including disconnected components,
orphan contents and cycles without a root. Each possession appears once.
`cycle:true` means following readable physical parent claims reaches a cycle,
including a tail entering that cycle. Unsupported physical parent types can
participate in source-claim cycles while remaining invalid container targets.
Missing/denied parents terminate the readable graph; `cycle:false` does not prove
unreadable data is acyclic. The algorithm memoizes ancestry without recursion.

Absent, null and empty parent/ammo selections map to `missing` without a missing
claim diagnostic; raw descriptors distinguish those states. Nonempty unresolved
claims add `container_parent_missing`, `container_parent_denied`,
`container_parent_unsupported`, `selected_ammunition_missing`,
`selected_ammunition_denied`, or `selected_ammunition_unsupported`.
Additional partial reasons are `containment_cycle`, `inventory_items_denied`,
`book_interpretation_pending` and `kit_interpretation_pending`. Books retain
common possession facts; kit and book specialty expansion remains optional.

## Rules presentation boundaries

Stack quantity, price denomination amounts and `price.per` remain separate
stored facts. There is no currency conversion, asset total, sale price or Bulk
engine. Carry state, hands, slot and nullable investment are source claims;
none establishes effective benefits, activation eligibility or an attack bonus.
Generic activations remain original Item description prose.

Explicit selected ammunition never merges multiple carried stacks, guesses a
selection from availability, or proves reload/compatibility/consumption.
Serialized attachment `_id`, name and type remain paths on the containing
Item with the original serialized-source limitations. They never acquire
fabricated document UUIDs. An actual owned Item with the same local ID is still
a separate actual possession. Kit definitions and generated owned contents also
remain separate; component references are never treated as extra possessions.

## Deterministic verification

`tests/js/actor-inventory.test.js` checks nested containers, rootless cycles,
incoming tails, unsupported-parent cycles, orphans, denied parents, explicit
ammunition and multiple stacks, exact coin quantity and nonunit price basis,
serialized/actual/kit duplicate references, optional books, source immutability,
one source read per relevant readable Item, no nonphysical hydration,
character/NPC/familiar and synthetic token identities, empty versus denied
scope, malformed selected fields, description exclusion, and stable ordering.
Shared-reader and Python-boundary tests establish continuation, response limits,
revalidation and validated external DTOs; this helper alone does not establish
live runtime coverage or effective mechanics.
