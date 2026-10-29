# Token-instance acceptance evidence

Baseline: Foundry 14.369 / PF2e 8.6.1. CORE-token is Complete after the approved
marked-fixture verification below. The earlier existing-data census and blocker
remain historical evidence; the user explicitly authorized the test-world setup
exception. Reader acceptance and read-only behavior were preserved.

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

## Existing-data recheck — October 28, 2026

`actor-tools.sh token-live` repeated only the bounded read-only selection check:
two MCP calls, 50 Scenes and 778 tokens. It found six readable supported linked
and 559 unlinked Actors, 564 with readable Items, and 117 eligible unlinked base
groups. **Zero groups had distinct current HP.** One candidate lacked readable
Items; none were excluded for nonfinite HP or invalid owned membership/UUIDs.
The only reported coverage gap remains the required same-base unlinked pair.
No reader pages or writes followed the unmet selection gate.

The original story explicitly prohibits synthetic creation/document updates.
Using a marked temporary fixture would require an explicit user exception;
the other character/familiar fixture permissions do not silently override it.

## Authorized fixture and completion — October 28, 2026

The user subsequently authorized creating state in the existing test world.
`actor-tools.sh token-fixture-live` created one marked NPC with one inert action,
one inactive non-navigation Scene and three tokens. Two unlinked same-base
instances retained source/current HP **7/19**, distinct action source names/prose
and distinct actual owned Item UUIDs. The linked control retained the base Actor
and Item. Only the new fixture's synthetic owned Items were configured; the base
Item and pre-existing game documents stayed unchanged.

The full run passed **62 requested/completed MCP calls**, including 58 nested
reader-check calls, **48 bounded pages**, **48 independent Item source/prose
witnesses**, and **three canonical Item follow-ups**. The shared verifier selected
only the exact marked Scene, requiring two unlinked instances and the linked
control from that scope. Public source/transformed HP, disjoint owned identities,
actual Item membership, inactive Scene navigation and rejected cross-token Item
selectors all passed. Exhausting pages did not imply complete effective state.

Complete source fingerprints matched before/after all reader calls. The enclosing
fixture fingerprint also matched. Exact UUID/type/run-marker cleanup deleted the
Scene before its base Actor and confirmed **pending=0, actors=0, scenes=0** and
unchanged active Scene. No new instance/world, Scene activation, combat, time,
settings, import, roll or preparation calls were used.

### Supported setup boundary and deterministic evidence

Grounded Docs verified the public v14 Actor `getTokenDocument(data, options)`,
Document create/update embedded operations and deletion, plus public
[TokenData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.TokenData.html)
`actorId`/`actorLink`/`delta`,
[ActorDeltaData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorDeltaData.html)
`system`/`items`, and
[SceneData](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneData.html)
`active`/`navigation`. The fixture uses normal document construction and actual
synthetic Actor `updateEmbeddedDocuments`, never manual ActorDelta merging or
private fields. NPC HP and inert action inputs use pinned PF2e8.6.1 schemas.

Eleven shared verifier tests include a fail-first Scene-scope case that formerly
borrowed an unrelated pair and now refuses it. Another actual-JavaScript test
proved that schema-permitted own `undefined` source leaves must compare as absent
after canonical source serialization; the old comparator rejected them, while a
forged absence for a present actionType still rejects after correction. Production
readers were correct and unchanged. Eight additional fixture tests execute actual
setup/cleanup JavaScript against guarded mock Documents: late Actor/Scene creation,
Scene-before-Actor cleanup, wrong UUID/type/marker, ambiguity, foreign tokens,
failed/lost responses, incomplete proofs, deadlines and precise safe call counts.

CORE-token is Complete for the original supported reading scope under the
approved setup exception. Existing-data absence is still a true historical fact;
the passing evidence is the genuine temporary fixture, not a fabricated census.
