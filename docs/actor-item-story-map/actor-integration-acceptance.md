# Combined Actor integration acceptance

Target: Foundry 14.369 / PF2e 8.6.1. This checkpoint checks composition of the
delivered readers; it does not turn deterministic mocks into runtime evidence.

`tests/js/actor-integrated-readers.test.js` uses production `readActor` with all
sections advertised by `getActorTypes`, consuming every bounded page for
character, NPC and familiar Actors. It checks stable revision and identity,
unique record keys, exact contributor paths, distinct source/current HP,
owned ability and Lore references, casting preparations, inventory and state.
Familiar master identity and action references coexist with current statistics;
ordinary familiar Strikes remain unsupported. Token cases preserve actual
instance ownership without substituting base-Actor witnesses. Changes to current
values, owned source or permissions invalidate combined continuations.

`tests/test_actor_integrated.py` passes actual production JavaScript pages
through Python `read_actor`, including returned cursors, selected sections and
count/byte limits. It rejects a forged foreign current-value contributor.
The shared fixture fingerprints source, current and owned Item data before and
after reads and makes mutation, preparation and roll entry points throw.

These checks complement the section-specific tests and existing runtime
verification. They do not establish every possible combination of game rules,
complete action legality, target-dependent statistics or active application.
Effective sections remain unsupported and state application remains unknown.
Dedicated affliction Items remain Deferred, with no reader or selectable type.

## Evidence gaps identified before Actor closure

The combined-test audit found two concrete gaps that mocks could not close:

- Character/NPC current Skills has discovery and deterministic coverage but
  lacks representative live comparisons of current values and owner-local Lore
  `itemId` joins. Source Lore reads and recorded proficiency ranks do not prove
  this separate current-data boundary. See the [Skills contract](skills-current-contract.md).
- Character senses, languages and IWR supplements lack representative live
  serialization verification. The extended current-statistics probe verified
  NPC samples; earlier character checks covered the core numeric subset.
  See the [creature supplement contract](creature-current-contract.md).

Subsequent October 28 verification closed both representative boundaries using
the existing world: one marked character/Lore and an existing NPC passed 408
current Skills records and two owner-local Lore joins over 42 pages; character
statistics supplied 47 core and six supplement records over eight pages. The
78-call run confirmed unchanged fingerprints and exact cleanup. Character
supplements covered language code/qualification and empty sense/IWR collections;
populated configurations remain unverified live. See the updated contracts above.
Familiar selected current values already have independent
[master-linked runtime evidence](familiar-current-contract.md); repeating that
fixture solely to obtain more passing examples is unnecessary.

The combined-test increment left Actor stories open. A subsequent
[familiar audit](familiar-acceptance.md) closes that Actor's declared views using
its existing runtime proof. Character/NPC closure is audited in their
[character](character-acceptance.md) and [NPC](npc-acceptance.md) matrices using
the additional runtime evidence, without claiming complete mechanics.
Full world/pack/token and journal
workflow acceptance belongs to CORE-acceptance. CORE-token separately retains
the missing existing same-base unlinked pair with distinct current HP; neither
combined mocks nor the affliction deferral changes that requirement.
