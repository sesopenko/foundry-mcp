# CORE-inventory: Inventory containment and source configuration joins

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 3 |
| Planning readiness | Planned |
| Implementation status | Complete |
| Prerequisites | [ITEM-weapon](ITEM-weapon.md), [ITEM-armor](ITEM-armor.md), [ITEM-shield](ITEM-shield.md), [ITEM-equipment](ITEM-equipment.md), [ITEM-consumable](ITEM-consumable.md), [ITEM-ammo](ITEM-ammo.md), [ITEM-backpack](ITEM-backpack.md), [ITEM-treasure](ITEM-treasure.md) |
| Dependency reason | Needs common possession/container/ammunition readers; book/kit expansion stays optional. |

## User outcome and implementation

As a reader, I can navigate carried possessions, containers and selected equipment relationships without double-counting.

- Join physical Items via `containerId` within the resolved actor/token. Preserve missing parents/cycles, carry state, quantities and identity. Treat attachments and kit definitions separately from owned Item collections.
- Connect weapon selected ammunition only with explicit same-owner ID evidence. Join weapon/shield attachments only through supported persisted relationships; do not guess effective attack math.
- Keep generic item activations in source prose. Optional book-content/kit component expansion becomes available after ITEM-book/ITEM-kit without blocking ordinary inventory delivery.
- Preserve price-per basis and source denomination values; no inferred sale price, total encumbrance engine or activation eligibility engine.

Acceptance: nested containers, cycles, orphaned contents, multiple ammo stacks, coin quantities and duplicate kit/generated-content references retain distinct treatment. No recursive all-document hydration or inventory mutation. Baseline source inventory can ship while optional specialty interpretation remains partial.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.


Delivered owner-wide source inventory uses each actual owned physical Item once,
including nested, disconnected and cyclic components. Persisted container and
selected-ammunition links retain same-owner/token identities and explicit
missing/denied/unsupported outcomes. Serialized attachments and actual kit
references remain distinct from possessions; optional book/kit expansion stays
partial. Independent quantity/price-per/carry/investment source never becomes
effective benefits or valuation. See [field contract](../inventory-fields.md)
and [verification](../inventory-verification.md).

Deterministic helper, paginated reader and strict Python DTO tests cover the
acceptance scenarios, source/membership/relationship/permission staleness,
non-PF2e rejection and denied privacy. Actual MCP checks cover three world/token
Actor contexts and six physical types with unchanged source fingerprints.
The existing world lacks supported owned containers, books/kits, selected ammo
and serialized attachments; these have deterministic coverage, not live claims.
Full suites passed:259 Python tests (one skipped),305 JavaScript tests.
