# Character selected-source verification

Evidence date: October 23, 2026. Tested Foundry 14.369 / PF2e 8.6.1. This is the
ACT-character source checkpoint, not completion of the integrated/current views.
The [field audit](character-fields.md) records pinned upstream source and reused
canonical rulebook readings. The [current-statistics proposal](current-statistics-contract.md)
has a separately verified partial implementation; see
[current-statistics verification](current-statistics-verification.md).

`characterFields` admits selected detached `toObject(true)` leaves with mapping
`pf2e.character.source.v1` and limitation
`character_source_not_effective_statistics`, plus per-field qualifications.
Null/absent `abilities` remains a root marker, never six zeroes. Selected manual
modifiers are not effective attributes. Stored skill ranks map to `{rank,label}`
using Untrained/Trained/Expert/Master/Legendary; they are not check totals.
HP/focus maxima, prepared traits/saves/Perception/movement, XP percentage and
prepared build additions are excluded. Unknown codes/escaped skill keys remain
source without claiming effective support. Selected maps/lists are bounded to
12,000 entries each; malformed admitted fields return `ReadFailed`.

Explicit description uses `pf2e.character.notes.v1`: exact biography and language
details, indexed edict/anathema strings and distinct empty/absent root markers.
Strings use shared 6,000-UTF-16-unit fragments and record/UTF-8-byte pagination.
Default source contains visibility configuration, not biography prose. Visibility
flags do not replace GM/document permission checks. No enrichment executes.

Deterministic coverage comprises seven helper tests, six reader tests and four
Python tests. Actual JavaScript DTOs cross the Python boundary, including
multi-page Unicode prose, null/undefined/empty distinctions, strict rank labels,
boolean-versus-number rejection, forged mappings/provenance, excluded paths,
world/pack/synthetic identity, stale source/biography/permission/identity checks
and count/byte bounds. Existing NPC and foundation regression tests pass.

Actual MCP discovery checked the published description, input schema, read-only
annotation and character source/mapped/effective capability flags. The fixed
`scripts/actor-build-live-check.py --world-id test` check reused the existing
development world, created one uniquely marked temporary character and seven
inert build Items, and removed only that run's UUID/marker afterward. The fixture
stored null attributes, a Nature rank, identity/language notes, resources,
unselected choices, biography prose, an edict and empty anathema.

Authenticated `read_actor` returned **51 source/description records over eight
pages** at limit 7 / max_bytes 8,000. Raw values matched actual post-hook stored
source; null attributes, labelled rank, resource maxima exclusions and exact
description/list markers passed. A separate complete default read confirmed no
biography prose leak. Existing Build and embedded background/feature checks also
passed. Full Actor source fingerprints before and after all reads matched, and
cleanup was confirmed. The browser stayed GM-ready; its only console notification
was Foundry's already identified minimum-window-dimensions message.

Full suites passed: **335 Python tests (one skipped), 425 JavaScript tests**.
World/pack/token variants, malformed source and stale/denied behavior have
deterministic coverage; this populated live fixture verifies the world source
path. It does not establish v13/future PF2e compatibility or full current
statistics. ACT-character remains Source implemented and counts as incomplete.
