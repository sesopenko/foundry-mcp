# Familiar selected-source and master identity verification

Evidence date: October 23, 2026. Runtime: Foundry14.369 / PF2e8.6.1.
This delivers the ACT-familiar source checkpoint, not its integrated milestone.
The [field audit](familiar-fields.md) links pinned schemas and canonical complete
rulebook reads. No compatibility with other system versions is inferred.

Selected source preserves nullable master ID/attribute, stored HP and temporary
HP/source claim. Creature prose requires explicit description and uses shared
6,000 UTF-16-unit fragments. Missing values remain absent. No source defaults,
independent attributes, master-derived maxima, saves or skills are invented.

Identity resolves only the recorded world Character Actor through public
`game.actors.get` and the existing permission-aware canonical resolver. It never
uses the PF2e master getter, which can mutate runtime associations. Resolved
records include a canonical `read_actor` follow-up. Missing, unassociated,
denied, unsupported and unverified master states retain the stored claim and
make identity partial without disclosing unavailable target metadata.

Explicit abilities lists actual owned action Items with exact source traits and
canonical identities. `ability_kind` is always `unclassified`: pinned action
schema/configuration has no verified familiar/master discriminator. Category,
names and custom trait strings do not establish benefit scope or activation.
Follow `read_item` for original prose. Empty references do not establish an
exhaustive active-ability list. Current statistics remain explicitly unsupported.

Deterministic tests cover source/null/unknown-code validation, all master states,
permission secrecy, action-only filtering, canonical world/pack/token identity,
exact Unicode fragments, changed master/action continuations and strict Python
validation of actual paginated JavaScript responses. No getter or transformed
serialization is used for familiar source. Tests reject forged provenance and
follow-ups and retain supported non-PF2e admission boundaries.

`scripts/actor-familiar-live-check.py --world-id test` checked actual MCP discovery
and created one marked temporary character, one familiar and two inert actions
in the existing development world. Selected identity/source/description/abilities
returned **11 records over six pages**; action source/prose used **16 pages**.
Canonical master follow-up, both distinct Item identities, exact descriptions,
default prose exclusion and unsupported statistics passed. A nullable master
update produced explicit unassociated identity. Actor source fingerprints were
unchanged by reads. Both exact marked Actors were removed; cleanup confirmed.

After module refresh the existing browser was GM-ready. Its only console error
was the previously identified minimum-window-size notification. Full offline
suites passed: **347 Python tests (one skipped), 460 JavaScript tests**.
Pack/token and denied/deleted-master variants have deterministic coverage;
the live fixture establishes the world source path. At that checkpoint,
master-derived current statistics remained unverified. The subsequent
`--statistics` run now verifies 127 present declared public model fields, correct
omission after master unassignment, and cleanup in 108 MCP calls. See the
[current contract](familiar-current-contract.md#representative-world-verification--october-25)
for exact scope and independent comparisons. Compendium/token current fixtures
and integrated casting/state remain open. ACT-familiar stays Source implemented;
these checkpoints do not increase the completed-story percentage.
