# Character Actor acceptance

Audited October 28, 2026 for Foundry **14.369 / PF2e 8.6.1**. This closes
[ACT-character and M-PC](stories/ACT-character.md) for their declared
supported/partial reading views. It does not claim full current statistics,
complete action legality, CORE-token or CORE-acceptance completion.

## Original requirements and evidence

| Original requirement | Evidence and scope | Result |
| --- | --- | --- |
| Identity, selected raw source, original prose and actual owned Item follow-ups | [Character fields](character-fields.md), [source verification](character-verification.md), shared Actor/Item readers and strict Python boundaries. Existing marked-character source run retained null attributes, rank/resource distinctions and default prose privacy. | Verified source checkpoint; no zero attributes are invented. |
| Identity/build and acquired contributors | [Build contract](build-contract.md) and [verification](build-verification.md) preserve actual build Items, stored selections and reciprocal owner-local claims; future definitions do not become acquired Items. | Verified joined source, without rebuilding advancement or executing grants. |
| AC/HP/saves, Perception, senses, languages, movement and skills including Lore | [Current statistics](current-statistics-contract.md), [creature supplements](creature-current-contract.md) and [Skills](skills-current-contract.md); the new marked-character run below verifies character serialization and a real owner-local Lore join. | Verified selected current fields with independent source/current provenance; remaining applicability is explicit. |
| Strikes, including generated basic unarmed without Item UUID | [Strike contract and runtime proof](strike-current-contract.md): marked character with zero owned Items, generated unarmed origin, present attack modifier and explicit getter-backed MAP capabilities. | Verified bounded current navigation; no invented Item UUID, getter calls, roll or final damage. |
| Activated/passive abilities and features | [Ability contract/runtime evidence](character-abilities-contract.md): actual action, feat and feature references, exact source/prose follow-ups, duplicate names and denied-Item privacy. | Verified acquired-document navigation; classification follows Item source/prose, not inferred activation or active benefits. |
| Spellcasting groups/options/resources, equipment/valuables and supported condition/effect state | Completed scoped [casting acceptance](casting-acceptance.md), [inventory verification](inventory-verification.md) and [state acceptance](state-acceptance.md). | Integrated readers retain each section's source/current distinctions and explicit limitations. Dedicated affliction Items are approved Deferred scope, not a completed capability. |
| Combined views with canonical identity, provenance and bounded continuations | [Combined integration evidence](actor-integration-acceptance.md), `actor-integrated-readers.test.js` and `test_actor_integrated.py` consume actual production JS pages through Python across all advertised sections. | Verified composition, including source/current separation, unique keys, canonical owned references and stale revisions. Mocks do not replace the section-specific runtime proofs. |
| World/compendium/token identity and journal versus direct resolution | Shared discovery/reference adapters and character/token deterministic reader tests retain actual context, reject substitutions and preserve source provenance. | Adapters verified at their recorded scopes. Full live end-to-end context workflow belongs to CORE-acceptance; the original story explicitly says it does not block basic world reading. |
| Invalid systems/types, missing/denied documents and no gameplay side effects | Focused JS/Python guards, immutable reader fixtures and actual authenticated MCP checks. | Reader remains read-only; temporary verification setup/cleanup is separate and narrowly marked. |

## Closing character current-data evidence

`scripts/actor-character-current-live-check.py --world-id test` reused the
existing localhost development world. It created exactly one run-marked
character and one inert Lore Item (`proficient.value: 1`, empty rules), with
the source language code `common` and an authored language qualification.
No existing Actor/Item was changed. The same MCP client supplied this character
to the existing Skills verifier alongside one existing NPC.

The complete run passed **78 requested/completed MCP calls**, with exact cleanup
confirmed. Character statistics consumed **eight pages**, independently checking
**47 core current records and six creature-supplement records** against public
`toObject(false)` own data. A real present language code and explicit empty
collection markers were required; matching absent fields alone could not pass.
Supplement coverage establishes this character's language and empty-collection
configuration, not populated character custom senses/IWR.

The nested Skills check passed **42 pages and 408 current records**, with
**two independent owned-Lore source references and two resolved owner-local
itemId joins**, across character and NPC in **64 calls** included in the total.
Ordinary current skills and numeric fields were required. Recorded proficiency
is kept separate from current modifiers and DCs; source Lore listing remains
independent when prepared keys collide. No Lore relationship was invented from
a name or slug.

Source/current fingerprints remained unchanged throughout the read phase.
Exact UUID/type/run-marker cleanup confirmed zero pending creation and no
remaining fixture. Offline harness tests cover lost/late creation, self-cleanup
after probe closure, wrong identity/type cleanup rejection, missing representative
data, changed fingerprints and getter rejection without invocation. The reader
does not create fixtures, prepare data or apply benefits.

## Preserved advanced limits

- Current values are selected system-recorded fields, not target-context roll
  results or complete character statistics. Conditional modifiers and all rule
  interactions are not reconstructed.
- Senses do not establish detection/visibility. Languages retain qualifications.
  IWR declarations, exceptions, doubleVs and bounded predicates do not calculate
  damage application. Populated character-specific custom configurations remain
  live-unverified; existing populated NPC evidence is separately labelled.
- Strikes do not evaluate damage, critical damage, target legality or non-Strike
  attack kinds. Accessor-backed fields remain explicit unsupported capabilities.
  Alternative-usage, pack and token live configurations retain their recorded gaps.
- Ability navigation is actual owned action/feat/feature references, not every
  basic/generated/prose-only action or proof of active/passive benefit application.
  Build/source acquisition claims remain distinct from eligibility and execution.
- Casting preserves configured ranks, signatures, preparations and resources.
  Computed signature alternatives, specialized modes and complete current
  availability remain explicitly unevaluated; no new casting engine is implied.
- Stored conditions/effects and selected current expiry do not establish all
  activity, suppression or application. Dedicated affliction functionality is
  incomplete upstream and outside approved delivery scope; original future
  acceptance remains Deferred, with no reader or selectable filter.
- Live character pack/token configurations, the qualifying CORE-token pair and
  full journal/world/pack/token workflow acceptance are not fabricated by this
  world-character proof. Foundry v13/future PF2e versions are not certified.

The original M-PC statement allows each book section to be supported with
provenance **or explicitly partial/unsupported**. Its full-current-statistics
claim remains conditional. Delivered sections now have deterministic composition,
representative runtime evidence and visible advanced limits; closure does not
relabel any unsupported capability as verified or reduce the original criteria.
