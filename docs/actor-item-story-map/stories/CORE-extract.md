# CORE-extract: Bounded Actor and Item source extraction

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | Not started |
| Prerequisites | [CORE-contract](CORE-contract.md) |
| Dependency reason | Uses agreed selectors, permissions, response bounds and error semantics. |

## User outcome and implementation

As a reader, I receive a selected document snapshot with the correct identity, exact bounded descriptions and an honest extraction basis.

- Add browser handlers and Python RPC validation following existing journal architecture. Preserve ready-GM/disconnected/timeout behavior. Browser owns public API access; Python validates/maps bounded primitives without a persistent world cache.
- Resolve a selected world Actor/Item or embedded Item through documented APIs. Pack and token resolution are later adapters, not reasons to block world source extraction.
- Apply type-specific allowlists over documented `toObject(true)` source fields. Exclude secrets, arbitrary flags, migration records, unrelated account/organized-play identifiers and internal/preparation state. Keep source HTML exact and bounded; derive readable text without executing enrichment, inline rolls or macros. Enumerate embedded IDs/types/names without recursively reading them.
- Return version/source/owner context, revision and explicit missing/incomplete/unsupported sections. Track query/source/revision in continuations; never represent a multipage/join read as an atomic snapshot unless established.
- Establish baseline tests using journal/RPC behavior before extending shared helpers. Do not silently refactor existing journal contracts.

Acceptance: correct world/embedded identity, exact Unicode-safe description continuation, byte/count separation, stale continuation rejection, missing child, non-PF2e boundary and no write/roll/import calls. Verify `toObject(false)` is never labelled source and `getRollData` is never advertised as a complete sheet.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.
