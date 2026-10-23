# Character Build join verification

Evidence date: October 23, 2026. Supported/tested pairing: Foundry 14.369 /
PF2e 8.6.1. This verifies selected persisted build data and owned-document
relationships, not effective benefits, eligibility or advancement. See the
[implemented contract](build-contract.md).

## Rules and schema basis

The existing canonical rulebook readings remain authoritative:
[ancestry](ancestry-verification.md), [background](background-verification.md),
[class](class-verification.md), [deity](deity-verification.md) and
[feat](feat-verification.md). Player Core pp. 19, 41, 84, 91 and 194 distinguish
offered/selected choices, training contributions, features and future progression.
Duplicate training does not authorize this reader to choose a replacement skill.
The class verification preserves the unresolved boost wording discrepancy.

PF2e 8.6.1 revision `28d9d156f252d084371d994dc359509b49eadf18`
[ItemSourceFlagsPF2e](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts)
defines stored `itemGrants`, `grantedBy` and `rulesSelections`. The
[grant audit](feat-grant-contract.md) and
[selection audit](feat-selection-contract.md) constrain the allowlist. Matching
stored claims establish agreement, not historical causality or active benefits.
Actual owner membership alone establishes an acquired document; definition UUIDs,
names, labels and selected scalar values do not.

The official public
[Actor documentation](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html)
was fetched through Grounded Docs before adopting fixture creation APIs. Its
public `implementation.create`, `createEmbeddedDocuments`,
`updateEmbeddedDocuments`, `getFlag` and `delete` signatures were checked.
Production reads use the existing public document identity, permission,
`Actor.items` and `toObject(true)` boundary. Fixture writes are test setup only.

## Deterministic acceptance

`tests/js/actor-build.test.js`, `tests/js/actor-build-readers.test.js` and
`tests/test_actor_build.py` cover:

- One actual owned Lore and feature with multiple contributor claims; versatile
  heritage, duplicate skill codes, class-feature category, level-19 future
  definition, unselected boost and deity spell option remain distinct.
- Exact local IDs and actual synthetic owners; no base-Actor substitution,
  name matching, importing, progression or rule execution.
- Agreeing, disagreeing, absent and unevaluated reciprocal evidence, including
  exact inverse source witnesses and withheld denied/unsupported target identity.
- Missing/empty/null source, unsupported selections, malformed typed fields,
  unsupported systems and NPC/familiar Build rejection.
- Deterministic ordering, independent single-record pages, source/name/permission/
  membership/inverse-evidence changes invalidating continuations, and separate
  12,000-Item / 24,000-record bounds.
- Strict per-row donor type/mapping/path/concept validation. A reproduced failing
  regression exposed conflicting same-page donor types; the fix also rejects
  conflicting target identities and repeated raw/inverse witnesses. Valid rows
  remain independently pageable; browser snapshot revalidation supplies
  cross-page consistency.

## Actual MCP verification

The pre-existing development world had no populated character fixture. The
fixed `scripts/actor-build-live-check.py --world-id test` check created one
unpredictably marked temporary character in that world, using public APIs and
seven inert owned Items: ancestry, heritage, background, class, deity, feat and
Lore. It did not provision another world or Foundry instance. Only that exact
run's UUID and marker authorize cleanup.

Background and class each stored claims to the same Lore and feature. The inverse
claims named background, deliberately producing agreement for one contributor
and disagreement for the other. The fixture retained null heritage ancestry and
boost selection, duplicate Nature training, a class-feature category, a recorded
scalar selection, a future level-19 definition and a deity spell option. The
future feat and spell were selected through existing pack indexes, never imported.

Actual authenticated `read_actor` returned **217 Build records across 32 pages**
at limit 7 / max_bytes 8,000. All seven owned identities appeared exactly once;
all four outgoing contributor claims retained their separate provenance and
expected reciprocity. No future feature or deity spell became an owned Item.
Actual `read_item` consumed **eight source/description pages** for the background
and feature, preserving canonical owner identities and original prose.

Complete Actor source fingerprints before and after these reads matched, with
seven Items throughout. Cleanup confirmed removal of the temporary character.
The dedicated GM browser remained ready with **zero console errors** after the
first run. After loading the final validator and registry metadata, the repeat
passed the same 217 records in 31 pages, plus eight Item pages, with discovery,
unchanged fingerprints and cleanup confirmed. Page count varies with generated
Item UUID ordering and byte packing. That refreshed browser reported one core
notification requiring a window at least 1,024 pixels wide; its current width
was 960 pixels. The notification is unrelated to the reader; no module exception
was observed. The browser helper now reports bounded code locations/categories
without printing console arguments.
The separate `--discovery-only` mode passed actual MCP discovery description,
input-schema, read-only annotation and `get_actor_types` source/mapped/effective
flag checks without creating game documents.

World/compendium feat and background source checks remain recorded in their
earlier verification files. Synthetic ownership, permission failures, stale
continuations and malformed data have deterministic coverage; this live fixture
does not claim those runtime cases, effective character views, another Foundry
build or another PF2e version.

CORE-build, ITEM-background and ITEM-feat meet their original selected-source,
explicit-reference and acquired-document integration acceptance. Character
effective views, casting and encounter state remain separate unfinished stories.
