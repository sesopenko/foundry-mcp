# ITEM-affliction: Affliction definitions and tracked stage

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | In progress |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `affliction` Item as **affliction definitions and tracked stage**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core p. 430 defines onset, saves, stage intervals and maximum duration; GM Core p. 86 notes many curses have a single effect rather than staged progression. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/affliction/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `save.type`, `save.value`, `status.onset`, `status.stage`, `status.progress`, `onset`, `stages`, `duration`, `start`, `context`, `fromSpell`.
- Mapping and relationships: Expose persisted tracked status separately from stage definitions. `status.stage` is one-based while `stages` is zero-based; resolve only in range, retaining malformed source explicitly. Preserve stage condition/effect links without applying them.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Current runtime limit

PF2e8.6.1's production constructor explicitly rejects affliction Items. The
current reader returns UnsupportedType before source extraction; discovery marks
affliction source/mapped/effective support false. See [runtime and rulebook
evidence](../affliction-verification.md). A pure offline selector and stage-mapping
fixtures are prepared in [the schema audit](../affliction-fields.md), but no live
reader or story completion is claimed. Do not bypass the upstream guard or
construct speculative fixtures. Original poison/disease/curse descriptions remain
readable through their actual supported Item types. Resume runtime integration
only after a supported system version and representative existing fixtures are
available and audited.

## Implementation checklist

- [ ] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [ ] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [ ] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [ ] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Stage 1 maps to stages[0]; an out-of-range stage is partial rather than silently clamped by the reader.
- Single-effect curses do not acquire fabricated stages.
- Source status is labelled tracked, not proof that all resulting effects are active.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

The 8.6.1 schema is now verified; representative live afflictions and current timer/effect-application semantics are still missing. Source-stage interpretation can proceed; automatic advancement, recovery rolls and expiry calculation are excluded.

No live type-reader MCP implementation has been verified. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.
