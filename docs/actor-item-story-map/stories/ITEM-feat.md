# ITEM-feat: Feats and acquired features

[Story-map index](../index.md) · [Evidence ledger](../evidence.md)

| Tracking | Value |
| --- | --- |
| Stage | 2 |
| Planning readiness | Source ready; advanced gated |
| Implementation status | In progress |
| Prerequisites | [CORE-extract](CORE-extract.md) |
| Dependency reason | Uses shared selected-source extraction; referenced types can remain unresolved until their readers are available. |

## User outcome and evidence

As a GM-trusted LLM, I can read a `feat` Item as **feats and acquired features**, retain its original identity and selected source, and follow named contributors without triggering gameplay.

| Evidence | Verified representation or requirement |
| --- | --- |
| Rules | Player Core pp. 249, 253 distinguishes general/skill feats and demonstrates prose requirements; pp. 41, 91 distinguishes ancestry/class benefits. |
| Schema | [PF2e 8.6.1 definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts); [shared evidence and compatibility](../evidence.md#pf2e-schema-baseline). |
| Foundry API | [Public document extraction and embedded identity](../evidence.md#public-foundry-api). Core APIs do not supply PF2e interpretation. |

## Source and mapped contract

Field paths below are relative to `system`. They are a **proposed allowlist**, checked against the pinned source, to finalize in CORE-contract before implementation. Also retain bounded `description.value`, publication metadata where present, document type/name/UUID, local ID, and actual parent/pack/token context. Missing fields stay missing; prepared data must never be relabelled source.

- Selected fields: `category`, `level.value`, `level.taken`, `actionType.value`, `actions.value`, `prerequisites.value`, `location`, `frequency`, selected `subfeatures`.
- Mapping and relationships: Separate feat category from feature category, nominal level from acquired level, and offered progression from owned documents. Preserve prerequisites as text and grants as evidence-backed links; do not implement eligibility.
- Preserve each contributor's canonical identity; unresolved links remain named references with an explicit reason. Nested source objects without document identity use source-path provenance, never fabricated UUIDs.

## Implementation checklist

- [ ] Baseline: add source fixtures and implement selected raw extraction plus the deterministic mappings above, using CORE-contract's response/continuation contract.
- [ ] Integration: expose named references to CORE joins and actor views; keep source-only reading usable before those joins exist. Referenced types are data relationships, not mandatory recursive reader dependencies.
- [ ] Document `PF2e-specific` dependencies and source/effective assumptions at implementation boundaries; test non-PF2e rejection and publish self-contained tool descriptions.
- [ ] Resolve the evidence gates below before advertising the corresponding advanced capability; retain explicit unsupported/partial sections until then.

## Acceptance scenarios

- Class/ancestry feature categories are not labelled chosen feats.
- Battle Medicine retains toolkit/Treat Wounds/immunity prose alongside structured action/prerequisites.
- Future grants and unselected choices are not reported as acquired.
- Read a selected embedded, world, or compendium Item without importing, activation, rolling, enrichment execution, chat, or writes; verify parent/pack/instance identity and bounded descriptions.
- Missing, unsupported, denied, stale, empty and incomplete results remain distinguishable under the shared contract.

## Evidence gates and exclusions

Persisted grant/selection relationships require a separately documented allowlist before use; arbitrary flags and rule-element execution are excluded.

Selected source reads have now been live verified; persisted grant/selection joins remain pending. PF2e 8.6.1 is the schema baseline; v13 system compatibility and future releases are unverified. See the [evidence ledger](../evidence.md) for dates, book revisions and inherited live gaps.

## Source checkpoint in progress — October 22, 2026

The source reader is implemented independently from acquired-document
joins. The [persisted grant audit](../feat-grant-contract.md) records the selected
flag schema and a proposed resolution contract; it does not advertise implemented
or live-verified grants. Preserve source-only usefulness while completing the
original grant/selection evidence gates. The story remains In progress.

The [field audit](../feat-fields.md) and [verification](../feat-verification.md)
record four actual definitions,19 pages and124 source/description/identity records,
with exact prose and unchanged source fingerprints. Optional undefined source
fields remain absent and explicit null stays distinct. Regression suites pass:
307 Python tests (one skipped),377 JavaScript tests. Relationships remain
unsupported pending the original persisted-grant and selection evidence gates.

## Persisted reference checkpoint

The audited grant fields are now selected source. Explicit relationships resolve
actual same-owner IDs and immediate self-effect/suppressed-feature UUIDs, with
missing/null/empty/unowned and inaccessible targets kept distinct. No reciprocal
causality, suppression or active benefit is inferred. Deterministic tests cover
owned/synthetic contexts and identity/permission staleness. The earlier source
checkpoint's unsupported relationships statement is superseded by this limited
reference implementation. Selection and acquired multi-contributor joins remain
unfinished; the story remains In progress.
