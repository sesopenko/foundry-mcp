# CORE-journal: Journal references to Actors and Items

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 1 |
| Planning readiness | Planned |
| Implementation status | Complete |
| Prerequisites | [CORE-world](CORE-world.md), [CORE-packs](CORE-packs.md) |
| Dependency reason | World and pack discovery/read paths supply valid follow-up targets. |

## User outcome and implementation

As a journal reader, I can follow a returned Actor/Item reference to the correct supported target.

- Extend typed follow-up reference metadata while preserving exact journal source and existing cursor/revision behavior. Read current `journals.js` and Python contracts before changing shared helpers.
- Use asynchronous `fromUuid(uuid, {relative: originatingDocument})` for selected full documents, including compendiums. Separate anchors from target selection and preserve original notation.
- Add named/type/source context and next-reader guidance for Actor/Item targets; keep broken, denied, unsupported and outside-scope references explicit. Token-backed references become navigable when CORE-token is available.
- Plain-name mentions lead to bounded candidates, never automatic first-name resolution. Fragment reference completeness stays fragment-scoped.

Acceptance: relative/absolute/compendium/embedded references, duplicates, broken targets, anchors and bounded source fragments preserve prior journal behavior. No eager hydration of every reference; pack failures remain local. Test both existing journal contracts and added metadata.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.

Delivered selected-reference resolution and lazy follow-up metadata preserve
legacy world-journal fields, exact source and continuation semantics. See
[verification](../journal-reference-verification.md) for deterministic relative,
absolute, compendium, embedded and token cases, strict MCP discovery/DTO checks,
and existing-world journal → Actor → owned Item plus compendium Item follow-up.
No eager target hydration or implicit name resolution occurs. Ordinary journal
reading remains available outside the pinned PF2e target-reader pairing.
