# Token-instance acceptance evidence

Baseline: Foundry 14.369 / PF2e 8.6.1. CORE-token is Blocked on an unavailable
existing distinct-HP pair. Its original acceptance criteria remain unchanged.

The read-only `scripts/actor-token-live-check.py --world-id test` check scanned
50 existing Scenes and 778 placed tokens on October 25. It found linked and
inactive-scene controls, but no eligible existing character/NPC same-base
unlinked pair with different stored/current HP and meaningful Item source state.
The result was an explicit coverage gap after two MCP calls. It is not a passing
two-token reader test. No document was created or changed to manufacture one.

The first probe imposed extra conditions: unequal stored and current HP plus
different hashes of Item name/type/system contents. These are historical probe
requirements, not original acceptance requirements; the corrected check below
removes them. The scan uses public Scene tokens and
TokenDocument actor/baseActor/isLinked, without canvas access or Scene activation.
Its bounds are 200 Scenes, 2,000 tokens and 12,000 owned Items per candidate.
Familiar current data is excluded from this scan because its separately verified
master permission boundary must remain intact.

Ten offline harness tests exercise actual JavaScript selection for character
and NPC pairs, identical definitions with distinct actual owned documents, linked/inactive controls,
runtime guards, complete paginated reader orchestration, cross-token rejection,
empty independent-check responses and changed fingerprints. Existing
`tests/js/actor-token-readers.test.js` additionally covers actual integrated
JavaScript readers, missing/deleted/base/readiness conditions and familiar master
dependencies. These tests preserve the original acceptance criteria; they do not
replace the missing representative live pair.

## Original-criteria correction and aggregate census — October 25

Distinct actual owned Item documents can share definitions. The corrected probe
requires actual owner membership, canonical UUIDs and disjoint token-owned Item
identities; source/prose follow-ups and cross-token rejection remain required.
Item-content and stored-HP differences are reported as coverage facts, rather
than completion gates. Different current HP remains necessary for the pair.
Fail-first Node regressions now accept identical definitions and equal stored
HP with distinct current HP; invalid ownership/UUIDs and equal current HP fail.

The corrected scan again visited 50 Scenes and 778 tokens in two MCP calls:

| Aggregate | Count |
| --- | ---: |
| Readable supported linked / unlinked Actors | 6 / 559 |
| Candidates with readable supported Items | 564 |
| Excluded for no readable Items | 1 |
| Excluded for nonfinite HP | 0 |
| Excluded for invalid owned membership / UUID | 0 / 0 |
| Eligible unlinked base-Actor groups | 117 |
| Groups with distinct current HP | **0** |

Linked and inactive-Scene controls exist. The missing pair is caused by existing
HP configuration, rather than Item-content equality or invalid ownership. No
token, synthetic Actor or other document was created or updated.

When an eligible existing pair is available, the harness will consume Scene
discovery and selected token pages, source/current Actor pages, owned Item
navigation and selected Item source/prose pages. It compares public serialization
independently, retains actual canonical Actor/Item UUIDs and token selectors,
rejects cross-token Item reads and verifies unchanged complete source fingerprints.
Until then, previous live evidence covers individual synthetic NPC reads and
Scene navigation only. The remaining gate is an existing qualifying pair, with
no synthetic creation or document updates allowed by the story.

## Independent existing-token state checkpoint

The separate read-only state check passed two existing unlinked instances:
10 state pages, 51 records, 71 raw witnesses and two canonical owned Item
follow-ups in 67 MCP calls. Condition/effect source, a false model expiry flag,
token/base identities and origin token context matched public documents.
Source/current fingerprints remained unchanged. See the
[state evidence](state-contract.md#existing-unlinked-token-state-verification--october-25).
This establishes those selected instance reads, not the unavailable same-base
distinct-HP pair or complete effective state. CORE-token remains Blocked.
