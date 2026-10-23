# Selected transformed-statistics verification

Evidence date: October 23, 2026. Tested Foundry 14.369 / PF2e 8.6.1. The
[contract](current-statistics-contract.md) supplies the official public API,
pinned document-data definitions, exact fields and remaining candidates.
This verifies selected current values, not complete Actor stories.

Grounded Docs confirmed public `Actor.toObject(false)` selects transformed
values. Official PF2e document-data contracts establish field meaning separately
from sheet classes and private preparation methods. Production selects own
declared primitive data properties only, never runtime getters, system methods,
source fallback or local statistic arithmetic. Raw and provenance basis are
explicitly `transformed`; persisted source at the same path remains separate.

## Regression evidence

Eight helper tests, seven actual-reader tests and six Python tests cover book
concepts, strict types/rank labels, missing versus null, movement literals,
source/current differences, exact provenance, world/pack/synthetic identities,
permission/runtime boundaries, count/byte limits, and current-value changes
invalidating cursors while source remains unchanged. Source-only reads never
request transformed serialization. Familiar statistics returns no fabricated
values and the explicit master-contract reason.

The first actual NPC call failed because the helper required plain prototypes.
One bounded diagnosis located the HP container: it had a custom prototype but
own numeric `value`, `max` and `temp` data properties. A regression reproduced
the failure before the fix. The corrected helper admits those own declared
properties while leaving inherited fields absent and rejecting getters without
invoking them. No HP prototype or private key becomes a dependency.

Python also rejects malformed mappings/types/bases, foreign owners, extra record
fields, conflicting null movement parents/present descendants, and unsupported
familiar section reasons. Different source and transformed values remain valid.

## Actual MCP checks

The read-only `scripts/actor-current-probe.py --verify` check exhausted statistics
pages for two pre-existing NPCs, without game writes:

| Sample | Pages | Records | Verified distinction |
| --- | --- | --- | --- |
| Elite world NPC | 6 | 38 | Source AC 22 → current 24; source maximum HP 65 → current 85; saves increase by 2 through Foundry's transformed data |
| Unlinked synthetic NPC | 7 | 44 | Actual token Actor/UUID context, including fly/swim versus null movement modes |

Every raw path, presence and value matched independently selected public
serialization. Exact world/token identities, transformed contributors, partial
reasons, actual discovery/schema/registry flags and unchanged before/after source
hashes and selected current snapshots passed. Optional NPC Perception rank was
unavailable and explicitly diagnosed. The earlier failure and diagnostic are
recorded separately in the contract rather than counted as passing verification.

`scripts/actor-build-live-check.py --world-id test --statistics` then verified
one uniquely marked temporary character in the existing development world.
Seven inert build Items provided populated source without importing definitions
or executing rules. **47 statistics records over seven pages** matched independent
own-data-property expectations, including character attribute bases, labelled
save/Perception ranks, HP and movement. Existing source/biography/Build/embedded
Item checks passed; full source fingerprints stayed unchanged and cleanup
confirmed removal of only that marked fixture. No new world or instance was made.

The dedicated GM browser remained ready. Its only console notification was the
already identified core minimum-window-dimensions message. Capability flags and
standalone descriptions state that selected effective data is available while
the statistics section remains partial. Full suites pass: **341 Python tests
(one skipped), 440 JavaScript tests**.

## Remaining gates

Familiar/master-derived values, skills/Lore totals and joins, senses/languages,
IWR, generated Strikes, conditions/effects and complete target-dependent results
remain unfinished. Non-null movement source strings have deterministic coverage;
additional conditional-effect configurations remain unverified.
No v13 or future-version compatibility is established. ACT-character and
ACT-npc remain Source implemented; this unit does not add completed stories.
