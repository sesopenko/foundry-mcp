# Current delivery acceptance audit

October 28, 2026: Foundry14.369/PF2e8.6.1 only. Final acceptance is complete:
38/38 delivery stories Complete (100%), including CORE-token and CORE-acceptance.
All three Actor integrated checkpoints are Complete. Dedicated affliction Items
remain separately Deferred, outside delivery and unreadable through tool inputs.

| Original CORE-acceptance requirement | Evidence and current result |
| --- | --- |
| Actual discovery descriptions/schemas, identifiers, scope, bounds and recovery | Actual MCP discovery tests in `test_actor_interface_contract.py`, `test_actor_discovery_check.py`, `test_journals.py` and `actor-integration-discovery.test.js`; reconciled [tool contracts](../actor-tools.md); fresh SDK discovery and the typed journal live check. Verified scoped contracts, including explicit unsupported sections. |
| Deterministic supported types and world/pack/token boundaries without gameplay side effects | The 23 Item stories retain their individual helper/reader/Python tests. `actor-documents.test.js`, `actor-packs.test.js`, `actor-token-readers.test.js` and actual production JS pages through `test_actor_integrated.py` cover shared identity, permissions, pagination and no-write boundaries. No new type-by-context fixture matrix is required. |
| Journal → Actor → ability/spell | [Typed journal verification](journal-reference-verification.md): an actual owned action, complete selected source/prose, exact hashes and unchanged journal/document fingerprints in 21 calls. Verified ability path; no new live spell claim. |
| World/pack identity and available character/familiar runtime fixtures | Existing journal world/compendium proof, individual type-pack checks and [character](character-acceptance.md), [NPC](npc-acceptance.md), [familiar](familiar-acceptance.md) matrices. Scoped public current-data values were independently checked; marked-fixture cleanup was confirmed. |
| Linked/unlinked token state and inactive Scene behavior | [Approved fixture verification](token-verification.md) passed 62 calls: same-base unlinked HP7/19 and different Item content/identities, linked control, inactive Scene, cross-token rejection, unchanged fingerprints and exact cleanup. CORE-token is Complete; the earlier existing-data absence is retained as historical evidence. |
| Required regressions, current documentation and separate publication authorization | Full offline suites and local commit hook pass per verified unit. README, Docker overview and contracts match delivered scope. No version bump, tag, release or push is authorized by acceptance work. |
| Budgeted fresh-agent evaluation when justified | Optional; deterministic discovery/reader/workflow checks suffice here. No behavioral benchmark or additional live fixture matrix was run. |

The final review checked each delivery story's stated acceptance and the three
Actor matrices. The typed journal proof and approved token pair now close the
last identified evidence gaps. CORE-acceptance is Complete. Full offline
verification passed 545 Python tests (one skipped) and 594 JavaScript tests;
the dependency tracker validates all 42 nodes and 79 edges without cycles.
Full current mechanics, target-context calculations,
casting legality/availability and condition application/suppression retain their
explicit unsupported/unevaluated boundaries. Populated character senses/IWR,
some live pack/token configurations and other versions remain unverified.

## Approved testing exception for the last fixture

The existing-data restriction prevented the required live comparison. On October
28 the user explicitly authorized creating test state in the existing world.
The approved bounded fixture creates one marked NPC with one inert action,
one marked **inactive** Scene, and three tokens in that Scene: two unlinked copies
with distinct HP and fixture-only Item source differences, plus a linked control.
All setup would be confined to newly
created fixture documents in the existing localhost `test` world. The check
would preserve actual owner/Item identities, reject cross-token Item selectors,
read the inactive Scene without canvas access and compare fingerprints before
and after reading. Exact run-marker/UUID cleanup would remove the new Scene
before its base Actor; no existing game document, active Scene, world settings,
time or combat would be changed. No new Foundry instance/world is proposed.

The original no-new-instance and read-only reader requirements remain in force.
The exception permits only the described test-world setup/cleanup; it does not
itself establish live proof or authorize game-session/production mutations.
The actual comparison and exact cleanup subsequently passed as recorded above.
