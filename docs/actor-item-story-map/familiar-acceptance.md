# Familiar Actor acceptance

Audited October 28, 2026 for Foundry **14.369 / PF2e 8.6.1**. This closes
[ACT-familiar and M-FAMILIAR](stories/ACT-familiar.md) for the declared
supported/partial views. It does not certify every familiar mechanic or close
CORE-token/CORE-acceptance.

## Original requirements and evidence

| Requirement | Implementation and authoritative evidence | Result |
| --- | --- | --- |
| Canonical familiar identity, selected source, original creature prose and owned Item follow-ups | `actorFamiliar.js`, `actorFamiliarRelationships.js`, production Actor/Item readers; `actor-familiar-readers.test.js` and `test_actor_familiar.py`; [source verification](familiar-verification.md) | Verified source checkpoint; no independent attributes are fabricated. |
| Resolve the recorded world-character master with permissions | Master identity/statistics relationship rows preserve separate source ID/ability witnesses. `actor-familiar-current-readers.test.js` covers master identity, permissions, reassignment and missing/null/absent/denied/unsupported guards. | Verified; no private master getter or same-name/token substitution. |
| Read familiar and master-benefit action Items without losing identities or exact descriptions | Familiar owned action references remain `unclassified`; `read_item` returns their source/prose. The existing marked pair supplied two actions describing different benefit scopes, with exact Item follow-ups. | Verified navigation and prose. No unsupported machine-readable classification or active-benefit inference. |
| Preserve source HP while selecting supported master-linked values | Source fields retain source basis; current defenses/HP/Perception/movement/ordinary skills use the declared public model only after a resolved master guard. [Current contract and runtime proof](familiar-current-contract.md) | Verified selected current values, not local recalculation or full statistics. |
| Missing/deleted/denied/unassociated master yields partial data without invented statistics | Deterministic current reader tests prevent model reads for every unresolved status, including permission loss during resolution. The live fixture's master unassignment returned only exact source context and no current rows. | Verified; source HP survives independently. |
| Optional casting and condition/effect data compose with familiar identity and abilities | `actor-integrated-readers.test.js` exercises production `readActor` with every advertised section; familiar assertions include master identity, action Item, repeated preparations, inventory and two state Items with unknown application. | Verified composition. Availability/application remain explicitly unevaluated. |
| Raw and mapped fields, contributors, bounds, continuation and completeness remain coherent | `test_actor_integrated.py` feeds actual production JS pages through strict Python validation. Stable revisions, unique keys, source/current separation, owner provenance and returned cursors/count/byte limits are checked. | Verified combined boundary at commit `a87a830`. |
| World/compendium/token identities do not substitute for one another | Familiar source/current reader tests cover those contexts and master guards; combined world/token tests preserve actual instance witnesses and canonical owned selectors. CORE-journal already verifies lazy canonical Actor/Item follow-ups. | Deterministic adapter support verified. Full contextual live workflow remains CORE-acceptance's separate requirement. |
| Non-PF2e, missing, denied and unsupported types remain actionable; reads have no gameplay side effects | Shared Actor document boundary plus familiar reader/Python tests; combined fixture makes mutation, roll and preparation entry points throw and fingerprints source/current/owned data. | Verified read-only contract. Test fixture setup/cleanup is distinct from reader behavior. |

## Existing runtime proof, reused without another fixture

The completed `actor-familiar-live-check.py --world-id test --statistics` run
verified **127 present current fields and zero missing**, with 128 statistics
records across 64 pages in **108 MCP calls**. Independent public own-property
reads checked every selected field, requiring present finite AC, saves, ordinary
skills and land Speed. Source/master context, action descriptions, master
identity follow-up and unassociated-master suppression of current rows also
passed. Source fingerprints matched within each read phase. Exact marked
familiar-before-master cleanup and zero pending creation were confirmed.

That proof establishes the familiar-specific public model boundary. Shared
casting, inventory and condition/effect readers have their own completed scoped
acceptance; combined mocks establish their composition without representing a
new live casting or condition-application experiment. This familiar-specific
model proof does not certify character/NPC current Skills or creature supplements.

## Preserved limits

- Current familiar statistics remain partial. Missing fields are unavailable;
  no source/master fallback, independent attributes, rank inference or normal
  Strikes are generated. Item-linked/Lore skill traces are withheld before
  exposing their keys or totals.
- Familiar/master benefit scope requires reading the exact action descriptions.
  Ownership, name and animal traits do not establish ordinary pet, animal
  companion or other special roles. Active benefits are not calculated.
- Casting records preserve definitions/configuration and supported resources;
  familiar current focus semantics, final cast rank and current availability
  are not certified. State records retain unknown application; effect expiry
  booleans do not establish condition activity or effective suppression.
- Dedicated affliction functionality is Deferred outside current delivery by
  the user's explicit decision. Responses continue declaring it unsupported.
- Live compendium/token familiar-current coverage, the existing same-base token
  pair, full journal/discovery workflows and compatibility beyond the tested
  pair remain separately gated. The original Actor story explicitly assigns
  contextual end-to-end acceptance to CORE-acceptance rather than blocking
  basic world reading on it.

These limitations remain visible in discovery and responses. Story completion
does not change an unsupported effective capability into verified support.
