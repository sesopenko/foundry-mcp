# CORE-physical: Shared physical source fields and attachments

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Applies common physical fields after safe document extraction. |

## User outcome and implementation

As an inventory reader, I can understand common physical fields without losing per-type exceptions.

- Establish selected quantity/level/Bulk/price/price.per, carry/hands/investment, container, material, identification, HP/hardness and description contracts from pinned PhysicalSystemSource/template and concrete type overrides.
- A property absent from a concrete source remains absent. Source usage is intentionally absent for armor/shield; derived usage must not be relabelled persisted source. Preserve unknown codes.
- Separate child containment (`containerId`) from serialized `subitems` attachments. A nested source object is not automatically a Foundry embedded Item and must not receive a manufactured UUID. Unsupported attachment interpretation remains named source-path content.
- Exclude kit from the physical helper: its schema is a bundle with its own items/price. Handle raw `price.per` before any value normalization.

Acceptance: identified/unidentified GM source, missing/placeholder fields, zero-versus-inapplicable quantities, price-per stacks, serialized attachments and type-specific omissions are covered. Do not calculate effective Bulk, bonuses or market resale in this helper.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

## Delivery evidence — October 20, 2026

The [physical field registry](../physical-fields.md) finalizes the allowlist and concrete omissions. Shared fields now flow through read_item with source provenance, byte/count pagination, stale checks and explicit descriptions. Pure/helper, integration and Python cross-language tests cover null/zero/absent values, price.per, type omissions, serialized attachments, long alternate text and malformed/private field rejection.

Live MCP source reads passed for six available physical types on supported owners; a separate source-shape/helper audit covered the broader existing world/embedded scope. No book, nonempty attachment or unidentified alternate-text runtime fixture was available; their deterministic/schema coverage does not claim full specialized behavior. A live treasure mismatch was traced to schema-permitted undefined price.sizeSensitive, proved with a failing regression and corrected narrowly to absent source. Individual Item stories and effective mechanics remain open.
