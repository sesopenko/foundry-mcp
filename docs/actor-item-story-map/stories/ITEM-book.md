# ITEM-book: Formula and spell books

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | In progress |
| Prerequisites | [CORE-physical](CORE-physical.md) |
| Dependency reason | Uses common physical source rules and identity/bounds. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `book` Item as **formula and spell books**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 288, 194 distinguishes formula collections and spellbook contents from spells prepared today. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `category` (formula/spell), `capacity`, `contents` (Item UUID array).
- Mapping and relationships: Present source book category, capacity and named referenced content. This physical type is unrelated to the private PDF library. Formula ownership and spell preparation are separate facts.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [x] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [x] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [x] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [ ] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- A formula book and spell book preserve distinct categories.
- Book contents never prove that an actor has prepared or can cast those spells.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Pinned source/template establishes fields; representative live book Items and content-resolution behavior remain unverified. Formula-specific interpretation beyond the read passages stays partial.

No live type-reader MCP implementation has been verified. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.


Selected source and explicit immediate named-content links are implemented and
deterministically verified; see [fields](../book-fields.md) and
[verification](../book-verification.md). Duplicate indexes, canonical/token
identity, exact descriptions, permissions and stale continuations are covered.
The original representative live-book gate remains open: the existing world,
all inspected Actor instances and26 Item compendiums contain no book Items.
Standard blank books remain equipment. No fixture is fabricated or retyped and
no live source/relationship support is claimed. Story completion awaits the
specified evidence; formula ownership/preparation interpretation stays partial.
