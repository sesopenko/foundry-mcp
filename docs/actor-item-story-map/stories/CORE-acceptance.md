# CORE-acceptance: Integrated discovery, contracts and compatibility acceptance

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 4 |
| Planning readiness | Planned |
| Implementation status | Not started |
| Prerequisites | [CORE-world](CORE-world.md), [CORE-packs](CORE-packs.md), [CORE-token](CORE-token.md), [CORE-journal](CORE-journal.md), [ITEM-book](ITEM-book.md), [ITEM-kit](ITEM-kit.md); M-NPC, M-PC, M-FAMILIAR |
| Dependency reason | Checks every type baseline, actor integration checkpoint and source/navigation adapter. |

## User outcome and implementation

Approved delivery boundary (October 25, 2026): dedicated affliction Items are
incomplete upstream and deferred until PF2e maintainers complete them. Exclude
ITEM-affliction from delivery progress and current hard dependencies; retain its
original story for follow-up. Actual discovery must identify the type as outside
scope and unreadable, and readable-type input schemas must not offer it. This
decision grants no source/stage/application support and does not change the
remaining token-instance or condition/effect acceptance criteria.

As a fresh GM-trusted client, I can discover the right entity, read supported source/book views, follow contributors and accurately recognize gaps.

- Validate actual MCP discovery descriptions and input schemas against implemented behavior, including type/system restrictions, names plus IDs, bounds, exact continuations and actionable recovery.
- Run deterministic Python/JS scenarios across world, pack and token contexts and supported types; assert no imports, creation/updates, casting/activation, rolls, chat or enrichment side effects.
- Verify journal → actor → ability/spell, pack-versus-world identity, linked/unlinked token state, and available character/familiar fixtures in the existing development world. Record unavailable live checks rather than fabricate coverage or provision another instance.
- Before any implementation commit run `./scripts/test.sh`. Update user-facing tool docs, README and Docker overview only when behavior changes. Release/version/publication is a separate authorization.
- If fresh-agent evaluation is justified, follow the repository budget: one task, two independent runs, measured calls; a third requires a concrete unresolved issue. Deterministic discovery/fixture checks are the default.

The actor integration prerequisites transitively include the other 22 Item readers; book and kit are explicit because ordinary inventory does not require their optional expansion.

Acceptance: every baseline story and integrated actor milestone meets its declared contract, or an explicit approved capability reduction remains visible in discovery and docs. Do not close an advanced capability solely because source-only fallback passes. Compatibility claims match tested core/system pairs.

## Evidence and completion

Use the [evidence ledger](../evidence.md), [original research](../../pf2e-actor-item-reference.md), and [shared story-map conventions](../index.md#working-conventions). Each implementation checklist item needs deterministic evidence; runtime-dependent claims also need the specified live check. No current Actor/Item implementation is implied.
