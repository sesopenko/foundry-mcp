# Token-instance acceptance evidence

Baseline: Foundry 14.369 / PF2e 8.6.1. CORE-token remains In progress.

The read-only `scripts/actor-token-live-check.py --world-id test` check scanned
50 existing Scenes and 778 placed tokens on October 25. It found linked and
inactive-scene controls, but no eligible existing character/NPC same-base
unlinked pair with different stored/current HP and meaningful Item source state.
The result was an explicit coverage gap after two MCP calls. It is not a passing
two-token reader test. No document was created or changed to manufacture one.

Candidate Item differences compare persisted name/type/system data, excluding
UUID prefixes, local IDs, bookkeeping and flags. Distinct synthetic UUIDs alone
cannot establish different Item state. The scan uses public Scene tokens and
TokenDocument actor/baseActor/isLinked, without canvas access or Scene activation.
Its bounds are 200 Scenes, 2,000 tokens and 12,000 owned Items per candidate.
Familiar current data is excluded from this scan because its separately verified
master permission boundary must remain intact.

Eight offline harness tests exercise actual JavaScript selection for character
and NPC pairs, meaningful versus cosmetic differences, linked/inactive controls,
runtime guards, complete paginated reader orchestration, cross-token rejection,
empty independent-check responses and changed fingerprints. Existing
`tests/js/actor-token-readers.test.js` additionally covers actual integrated
JavaScript readers, missing/deleted/base/readiness conditions and familiar master
dependencies. These tests preserve the original acceptance criteria; they do not
replace the missing representative live pair.

When an eligible existing pair is available, the harness will consume Scene
discovery and selected token pages, source/current Actor pages, owned Item
navigation and selected Item source/prose pages. It compares public serialization
independently, retains actual canonical Actor/Item UUIDs and token selectors,
rejects cross-token Item reads and verifies unchanged complete source fingerprints.
Until then, previous live evidence covers individual synthetic NPC reads and
Scene navigation only. The remaining gate is an existing qualifying pair, with
no synthetic creation or document updates allowed by the story.
