# CORE-packs: Scoped Actor and Item compendium discovery

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | Complete |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Adds index/hydration resolution to the shared extraction pipeline. |

## User outcome and implementation

As a client, I can find a pack document and read it without importing it or loading every pack.

- Share internal pack plumbing for Actor and Item scopes, while publishing explicit document-type and pack scope. Preserve titles/collection IDs and accessible hierarchy from public folder relationships only.
- Check pack permission, call `getIndex({fields})` for the selected scope, then `getDocument(id)` for a selected document. Cache contents/get are not an exhaustive index; an editing lock is not a read prohibition.
- Return searched, failed, inaccessible and incomplete scopes with continuation/revision context. Do not equate one inaccessible pack with no matching content.
- Recheck identity/type/permission after hydration. Keep compendium and imported/world UUIDs distinct.

Acceptance: unloaded/cached packs yield consistent discovery; partial pack failures, stale indexes and lazy hydration are explicit; unsupported actor types are filtered; no bulk getDocuments/import is invoked. Verify folder API availability before advertising nested pack navigation; use explicit flat pack context if unavailable.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

## Delivery evidence — October 20, 2026

Implemented explicit Actor/Item pack listing and selected index search, partial failed/denied/incomplete scopes, unknown index type handling, canonical public getUuid selectors and stale-result checks. Flat folder context is explicitly limited; pack editing locks do not prevent reads. Tests: `tests/js/actor-packs.test.js`, `tests/js/actor-dispatch.test.js`, `tests/test_actor_compendiums.py`. Live selected pack search followed its returned Item UUID through the full reader without import on Foundry14.369/PF2e8.6.1.
