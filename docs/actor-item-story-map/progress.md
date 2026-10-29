# Actor/Item development progress

[Story map](index.md) · [Reviewed contracts](../actor-tools.md)

The 39 stories retain the full agreed scope. Source checkpoints, integrated Actor views and advanced/live evidence gates are separate. Individual story headers are authoritative; regenerate a dependency-aware status report with:

```bash
./scripts/actor-tools.sh status
./scripts/actor-tools.sh check
./scripts/actor-tools.sh focused
./scripts/actor-tools.sh full
./scripts/actor-tools.sh live
./scripts/actor-tools.sh browser
./scripts/actor-tools.sh refresh
./scripts/actor-tools.sh skills-live
./scripts/actor-tools.sh character-current-live
./scripts/actor-tools.sh affliction-interface
```

The fixed runner accepts only those commands and rejects extra arguments.
`skills-live` checks existing NPC current Skills without writes;
`affliction-interface` checks discovery and rejected filters without document
reads. `character-current-live` creates one marked character and inert Lore in
the existing localhost test world, checks character/NPC Skills and character
statistics, and removes only that run's fixture with exact-marker cleanup.
`refresh` reloads only the existing dedicated development tab; it does not change game documents. `live` exercises the existing development MCP server using its caller credential from `.env.mcp`, with read-only selectors and no secret/document-ID output. `browser` inspects readiness and console-error counts in the dedicated development profile; neither command creates worlds or changes game documents. It uses installed Python/Node dependencies, performs no network setup or release, and can be approved by its script prefix for unattended checks. The full runner uses the existing repository test script. PDF subprocess tests need host execution when sandboxed child-process waiting stalls; do not repeatedly run them in the known-failing sandbox environment.

## Verified increments

### 1. Contract and dependency tracking — October 20, 2026

- CORE-contract design reviewed: canonical identities, linked/synthetic token context, explicit source/mapped/effective separation, permissions, limits, continuations, errors and version support.
- The reusable tracker validates all 39 stories, the three integrated checkpoints, direct prerequisite sets and Mermaid edges. It rejects cycles, unknown states, premature dependent completion and closing an Actor story before integration.
- Focused tracker tests cover ready transitions, graph drift, completion ordering and source/integrated status separation. Existing journal baseline passed 4 Python tests and the JavaScript journal suite before extension.
- Live availability probe: ready GM in existing test world, Foundry 14.369/PF2e 8.6.1; 172 NPCs, no character/familiar Actors. No game documents were changed. This establishes availability, not new reader verification.
- Next dependency: CORE-extract; independently delivered world/pack/token navigation and type readers follow after its focused/full checks pass.

### 2. Common source extraction — October 20, 2026

- CORE-extract delivered safe world/pack/token document resolution and permissions, common selected metadata and explicit Item description reads. Type-specific PF2e fields remain pending their stories.
- Four real MCP tools are registered: get_actor_types, read_actor, read_item and list_actor_items. Strict input/schema checks reject unknown arguments; Python validates actual JavaScript DTO fixtures and response byte/count/identity boundaries.
- Focused and full offline suites passed. Live HTTP discovery and two-page NPC, owned Item and token-instance reads passed on the existing test world after refresh/restart. No game documents changed. Independent console audit found no reader-module errors; cached errors were a core window-size warning and reconnect-period socket errors.
- Root cause of the first live attempt was connection timing after refresh/service restart; health later showed GM admission. The fixed live runner now waits for the existing bridge rather than starting another server or requesting another login.
- Next ready tasks are independent world/pack/token discovery, physical source helpers and individual Actor/Item source readers. Complete source checkpoints do not close effective/live gates.

### 3. World, scene and scoped pack discovery — October 20, 2026

- CORE-world and CORE-packs delivered bounded canonical discovery, literal queries, folder expansion and explicit scope failures. Pack search uses selected indexes and public UUIDs; no imports or bulk hydration.
- CORE-token navigation is in progress: linked/synthetic identities and inactive scene navigation work, but distinct HP/Items and relevant master state remain pending type readers.
- Focused cross-language DTO/discovery/schema/RPC tests passed. Live HTTP MCP discovery verified nine tools, world search/tree, selected scene/token follow-up and selected pack Item hydration on Foundry14.369/PF2e8.6.1. No game documents changed. Console audit after refresh found only the existing core window-width warning.
- The live runner now uses protocol structured JSON for version diagnostics; a regression test covers generated client model objects. Native Codex MCP sessions became stale after server restart, so live verification used a fresh authenticated client to the existing service.
- Shared physical-field helper/schema evidence is prepared separately; reader integration and individual Item stories remain pending.

### 4. Shared physical Item source fields — October 20, 2026

- CORE-physical delivered the pinned common allowlist, per-type omissions, price.per, identification source, and nonrecursive serialized attachment metadata. Explicit alternate descriptions use bounded exact text fragments. Concrete Item type completeness and effective values remain pending.
- Focused helper/integration/Python cross-language tests and full suites passed. Live actual MCP reads passed for six available physical types in the supported-owner scope; broader read-only helper audit found no errors after the correction below. Book/nonempty attachment/alternate unidentified runtime fixtures remain unavailable.
- Root cause regression: optional schema PriceField.sizeSensitive may be own undefined. The initial strict check rejected it. A failing test proved the defect; the exact schema-permitted undefined field now reports absent without borrowing prepared false. All other source validation remains strict.

### 5. Action Item selected source and self-effects — October 20, 2026

- ITEM-action delivered activation/count mappings, stored frequency, traits/tags, publication and named self-effect source. Explicit relationships resolve only the immediate supported effect and retain synthetic target token context; source-only reads do not hydrate it.
- Focused pure/browser/Python actual-DTO checks passed, including null-count distinctions, schema-optional undefined values, exact description continuation, permissions/staleness, ordinary and synthetic follow-ups, and unsupported effective sections.
- Live actual MCP passed four activation modes, familiar compendium identity/category, token action reading and self-effect follow-up. Selected persisted sources stayed unchanged. Missing standalone world-action and live synthetic-target fixtures remain named coverage limits.
- A larger selector probe encountered the known 1000-character development string bound; the runner now returns bounded chunks and rejects truncated snapshots, with a regression test. Production reader limits were not changed.

### 6. NPC attack Item source and effect labels — October 20, 2026

- ITEM-melee delivered authored attack modes, source bonus/range/area, keyed damage components, traits and named additional effects. Only strike is called Strike; effect labels never become guessed UUIDs.
- Five existing null-range attacks have thrown traits. Mapping now reports no_explicit_range and retains that limitation, avoiding a false exclusive-melee claim. Non-Strike modes have representative source fixtures; no live non-Strike sample exists.
- Focused source/browser/Python actual-DTO checks and full suites passed. Actual MCP verified explicit ranged, null/thrown, effect-label and compendium-owned attack reads, with unchanged persisted source fingerprints.

### 7. Lore specialties and partial Skills references — October 20, 2026

- ITEM-lore delivered owner-aware authored/stored modifiers and labelled original ranks, exact variants/tags/publication source and bounded descriptions. Actor Skills exposes separate canonical Lore references, including duplicate names and linked/synthetic token context, while remaining explicitly partial.
- Focused pure/browser/Python DTO checks and full suites passed (157 Python tests, one skipped; 134 JavaScript tests). Denied Items do not leak identity or read source; missing, empty, stale and oversized results retain shared contract behavior.
- Actual authenticated MCP verified NPC Lore source and Skills follow-ups with unchanged source fingerprints on Foundry14.369/PF2e8.6.1. Character/familiar/world Lore, variants and duplicate specialties have deterministic coverage; those live fixtures are unavailable. Effective checks remain gated.

### 8. NPC authored source integration checkpoint — October 20, 2026

- NPC source now retains authored attributes, defenses, Perception, skills, movement, senses/languages, IWR and recorded resources with source provenance. No elite/weak or effective arithmetic is applied.
- Focused helper, browser and Python actual-DTO checks passed. Actual MCP consumed all three source pages and verified exact AC/HP with unchanged source fingerprints; previous delivered readers still passed.
- ACT-npc is In progress: explicit bounded biography notes, embedded summary integration and advanced integrated/effective acceptance remain. Completed stories stay 8/39 (20.5%).

### 9. Explicit bounded NPC biography — October 20, 2026

- Actor `description` now selects NPC blurb, public notes and GM-private notes on separate exact source paths. Default source requests disclose none of them; other Actor descriptions remain explicitly unsupported.
- Focused JS/Python tests cover exact Unicode pages, empty/missing, malformed/denied/stale results and cross-language DTOs. Actual MCP reconstructed the selected NPC biography and matched stored-source SHA-256 values without outputting text; persisted source fingerprints remained unchanged.
- ACT-npc remains In progress pending embedded view integration and advanced acceptance. Completed story count remains 8/39 (20.5%).

### 10. NPC attack/action references and source checkpoint — October 20, 2026

- Explicit NPC strikes/abilities now expose actual owned melee/action Items with exact source-name/type provenance, separate duplicate UUIDs and selected token context. They remain partial; unreadable Items disclose no name or selector.
- Focused cross-language tests passed, including world/linked/synthetic contexts, strict ownership and provenance, denied privacy, stale membership and mandatory partial semantics for empty sections. Actual MCP followed three existing references and preserved source fingerprints.
- ACT-npc is Source implemented: source, bounded biography and embedded navigation are delivered. M-NPC integrated casting/inventory/state and verified effective interfaces remain open. Completed stories remain 8/39 (20.5%).

### 11. Effect Item persisted source checkpoint — October 20, 2026

- ITEM-effect now selects duration/start, discriminated counter/value/formula badges, context primitive leaves and identity/publication source. Unlimited/encounter units remain exact; no formulas, expiry or acquisition semantics are evaluated.
- Actual rulebook pages were fully read and pinned schema boundaries recorded. Focused pure/browser/Python actual-DTO checks passed; actual MCP verified six world/owned/compendium samples with unchanged persisted sources.
- ITEM-effect remains In progress pending explicit origin/target relationship traversal and advanced state integration. Completed stories remain 8/39 (20.5%).

### 12. Effect immediate context references — October 20, 2026

- ITEM-effect now resolves five explicit immediate origin/target Actor, Token and Item roles, preserving all claimed source context. Resolved metadata and token follow-ups are permission checked; unresolved statuses expose no resolved target metadata. Source-only calls do not hydrate links.
- Full suites passed: 181 Python tests (one skipped) and 155 JavaScript tests. Deterministic checks cover non-null contexts, linked/synthetic follow-ups, standalone packs, duplicate roles, denied privacy, malformed/mismatched targets and stale target identity/permissions.
- Actual MCP passed six source samples and explicit missing-reference records for their null contexts, with unchanged source fingerprints. Non-null live context is unavailable; effective expiry/current application and recursive provenance remain unsupported advanced gates.
- ITEM-effect Complete for its declared source/immediate-reference scope. Completed stories are 9/39 (23.1%); the full Actor/state integration objective remains open.

### 13. Condition Item persisted source checkpoint — October 20, 2026

- ITEM-condition now preserves valued/unvalued source, persistent-damage formula/type/recovery metadata, local reference IDs and override slugs. Presence is not active state; formulas and dominance are not evaluated.
- Actual rulebook pages and pinned schema contracts were reviewed. Focused JS/Python actual-DTO checks passed; authenticated MCP verified four existing owned/compendium samples with unchanged persisted source.
- Populated persistent/reference fixtures and character/familiar conditions are unavailable live; these retain deterministic coverage. Relationships and advanced active/suppression integration remain open. Completed stories remain 9/39 (23.1%).

### 14. Condition owner-local relationships — October 20, 2026

- ITEM-condition resolves actual owner-local parent/child/override reference IDs without constructing UUIDs. Override slugs remain unverified claims. Duplicate identities and distinct persistent-damage source remain separate; no activity/suppression or dominance is computed.
- Focused JS and actual Python DTO tests cover linked/synthetic follow-up, standalone scope, permissions, stale identity/membership and exact source provenance. Full offline suites and four live source/relationship samples passed; populated reference chains remain a live-fixture gap.
- ITEM-condition Complete for declared persisted-source and owner-local reference scope. Advanced active/suppressed-state/effective duration remain unsupported and recorded. Completed stories are 10/39 (25.6%); integrated state acceptance remains open.

### 15. Affliction schema preparation and verified runtime limit — October 20, 2026

- Actual rulebook pages and the pinned affliction schema were reviewed. Offline pure fixtures preserve stage definitions, one-based tracked stage correspondence, missing/empty arrays and out-of-range values without clamping or advancement.
- Upstream and installed PF2e8.6.1 production code reject affliction construction. No existing affliction was found in world/owned Items, 565 token Actor contexts or 26 Item pack indexes. Actor-pack embeddings were not exhaustively hydrated.
- Runtime admission now reports UnsupportedType before source access; registry support is false, owned navigation continues with unsupported_count, and condition links report unsupported. Focused schema and boundary tests pass. No production guard was bypassed.
- ITEM-affliction remains In progress. Supported runtime access/fixtures are required for its later integration; other independent stories can proceed. Completed stories remain 10/39 (25.6%).

### 16. Weapon definition/configuration source checkpoint — October 20, 2026

- Weapon-specific damage/runes/range/ammunition/alternate-source fields now combine with shared physical source using unique paths and distinct provenance. Carried configuration never becomes a final Strike or recalculated NPC attack.
- Actual rulebook pages and pinned schema fields were verified. Focused pure/browser/Python DTO checks passed; actual MCP consumed six owned/compendium samples with unchanged selected persisted sources.
- ITEM-weapon remains In progress pending selected ammunition relationships. Effective character/alternate-use attack calculations retain explicit gates. Completed stories remain 10/39 (25.6%).

### 17. Stored ammunition references and weapon acceptance — October 22, 2026

- ITEM-weapon now follows explicit stored selectedAmmoId through actual owner membership, preserving linked/synthetic selectors and exact source provenance. Selection remains distinct from loaded/compatible ammunition and effective attacks.
- Deterministic JS/Python DTO checks and full offline suites passed. Actual MCP after reboot verified six weapon sources, missing-selection relationships and delivered-reader regressions without changing persisted data. Populated live selections remain unavailable.
- ITEM-weapon Complete for its declared source/configuration and stored-reference scope. Effective PC Strikes/alternate-use calculations retain their advanced gates. Completed stories: 11/39 (28.2%).

### 18. Ammunition source and explicit-selection acceptance — October 22, 2026

- ITEM-ammo now preserves separate stock/use counts, crafting category distinctions and special source text. Two carried stacks do not both contribute: only the weapon's explicit selected stack is followed, with missing/denied/unverified results retained.
- Actual rulebook/schema evidence, focused JS/Python DTO checks and full suites passed (207 Python tests, one skipped; 197 JavaScript tests). Actual MCP verified five owned/compendium examples and exact crafting categories without source changes.
- ITEM-ammo Complete for declared stored-source and explicit-selection scope. Compatibility, consumption, automatic rule application and effective attacks remain unsupported. Completed stories: 12/39 (30.8%).

### 19. Armor source and wearing-state acceptance — October 22, 2026

- ITEM-armor preserves source defenses/constraints, runes, specific baselines and shared carrying/investment state. Missing/null/zero Strength remain distinct, serialized attachments retain source-path identity, and unworn gear never becomes Actor AC.
- Actual rulebook/schema evidence, focused JS/Python actual-DTO checks and full suites passed (211 Python tests, one skipped; 207 JavaScript tests). Actual MCP verified five owned/compendium examples without source changes.
- ITEM-armor Complete for stored-source/configuration scope. Effective Actor AC/saves/Speed and automatic rune/rule application remain unsupported. Completed stories: 13/39 (33.3%).

### 20. Shield source and durability acceptance — October 22, 2026

- ITEM-shield preserves definition/durability, reinforcing runes, specific baselines, integrated source and publication. Held is not raised; ownership does not grant Shield Block. Persisted HP56/max12 is retained without clamping or effective reinforcement math.
- Three full rulebook pages and pinned schema evidence were verified. Full suites passed (215 Python tests, one skipped; 216 JavaScript tests). Actual MCP verified three distinct compendium shields with unchanged source fingerprints; no world/owned/token shields exist live.
- ITEM-shield Complete for stored-source/configuration scope. Raised/current state, blocking/class benefits and generated attachment attacks remain unsupported. Completed stories: 14/39 (35.9%).

## Open acceptance evidence

Full effective PC/familiar values, mode-specific casting resources, condition suppression/expiry and specialized Item behavior retain their named gates in the [evidence ledger](evidence.md#open-verification-gates). Do not close those gates with source-only fallback or unit mocks. The existing development session can support live NPC checks; missing populated PC/familiar fixtures remain a distinct gap.

Each implementation increment must record focused/full results and a local commit after review. No version bump, release, tag or push is authorized by this development run.

### 21. Equipment source and prose abilities — October 22, 2026

- ITEM-equipment preserves usage, carrying/investment, attachments, traits and publication without applying benefits. Structured activation/frequency is absent from the schema; explicit bounded prose remains authoritative.
- Focused and full suites passed (219 Python, one skipped; 223 JavaScript). Actual MCP source and exact description fingerprints matched one owned NPC and two selected compendium Items; all source fingerprints remained unchanged. Explicit false investment and large Unicode continuation use deterministic fixtures because live investment flags are null.
- ITEM-equipment Complete for selected source/prose scope. Effective benefits, activation/expenditure and rule application remain unsupported. Completed stories: 15/39 (38.5%).

### 22. Consumable stock, uses and contained-source checkpoint — October 22, 2026

- ITEM-consumable now reads category, independent stock/uses, healing versus damage formulas, traits/publication and selected contained-spell source metadata. Nested source keeps consumable provenance without fabricated UUIDs; base rank is not heightened casting rank.
- Full suites passed (223 Python, one skipped; 232 JavaScript). Five actual MCP source cases matched persisted values and retained source fingerprints, including an empty scroll template whose index omitted spell but hydrated source contained explicit null. No consumption, rolls or casting occurred.
- ITEM-consumable remains In progress: complete contained-spell mechanics/prose mapping depends on ITEM-spell. Source explicitly stays partial; activation/castability/expenditure are unsupported. Completed stories remain 15/39 (38.5%). Next: implement ITEM-spell and return to the contained-spell mapping.

### 23. Spell definitions and immediate casting-entry references — October 22, 2026

- ITEM-spell preserves base rank, textual casting time, spell format, healing/damage components, location configuration and bounded recursive fixed-heightening/overlay source. Explicit root/nested prose is kept separate without merging or executing variants.
- Immediate owner-local casting-entry references resolve actual identities without target source; missing, denied, unsupported and unverified remain explicit, including linked/synthetic token context. Stored configuration never proves cast rank, slot resources or castability.
- Focused source/browser/Python tests and full suites passed (228 Python, one skipped; 245 JavaScript). Nine live source/prose cases matched persisted data and retained source fingerprints, with assigned/unassigned entry follow-up. Effective casting remains unsupported.
- ITEM-spell Complete for definition/source scope. Completed stories: 16/39 (41.0%). Next: integrate its source/prose mapping into consumable contained spells, then casting-entry reading.

### 24. Complete contained-spell source and prose integration — October 22, 2026

- ITEM-consumable now reuses the spell field/prose selectors under the consumable source path. Existing metadata/base rank stays unique; additional definitions and exact nested prose retain spell concepts and the actual consumable UUID. Nested location IDs never become owner-entry links.
- Source completes after pagination. Null/absent templates, separate stock/uses, damage/healing kinds, base/configured ranks, partial variants and source identity remain explicit. Activation, castability, expenditure and effective benefits remain unsupported.
- Focused and full suites passed (231 Python, one skipped; 251 JavaScript). Actual MCP source reads matched five persisted cases; contained wand prose matched its SHA256 and every source fingerprint was unchanged. No console errors after refresh.
- ITEM-consumable Complete for source/definition scope. Completed stories: 17/39 (43.6%).

### 25. Spellcasting-entry source and mode-specific resources — October 22, 2026

- ITEM-spellcastingEntry preserves casting mode/configuration, authored attack/DC and per-slot values/preparations. Repeated spell IDs retain indexes, absent expenditure stays absent, and zero slot counters do not establish exhaustion. Official template slot11 is retained without 11th-rank semantics despite the interface union ending at10.
- Malformed/legacy preparation portions remain explicit partial source with safe sibling records retained and exact issue paths; no object-to-array coercion or fabricated source defaults occurs. Actor spell joins, focus/innate resources, effective statistics and usable cast availability remain CORE-casting work.
- Focused/full suites passed (235 Python, one skipped; 262 JavaScript). Actual MCP read four modes plus a token-context entry, matching source fields/absence and unchanged source fingerprints. Discovery contracts match limits and unsupported sections.
- ITEM-spellcastingEntry Complete for selected resource-source scope. Completed stories: 18/39 (46.2%).

### 26. Actor casting source joins and focus provenance — October 22, 2026

- CORE-casting now joins actual owned spell/group identities, per-index preparations and selected mode-specific resource source in the explicit Actor spellcasting section. Same-owner, denied, missing, unsupported and mismatched claims remain distinct, with canonical linked/synthetic follow-up selectors.
- Character persisted focus value excludes derived maximum; creature optional source value/max is retained. Source base/configured/slot ranks and signature/cantrip flags remain independent; no availability or effective option is inferred.
- Focused/full checks and live source reads verify four Actor contexts covering all four common modes plus a scene token. Exact references, preparations, focus source and unchanged fingerprints passed. Full regression testing caught an accidentally removed pre-existing effect-name bound; the exact guard was restored and its regression test passed before further verification.
- CORE-casting remains In progress: availability, effective contextual options and specialized casting semantics are unverified. Completed stories remain 18/39 (46.2%).

### 27. Container source and stored containment graphs — October 22, 2026

- ITEM-backpack reads stored stowing, Bulk configuration, traits and publication alongside common physical source. Explicit relationships return actual owner-local parent/descendant claims, each readable descendant once, with depth, canonical parent IDs and token context. Cycles, missing/wrong-type parents, denied potential contents and unowned scope remain distinct; no Bulk totals are calculated.
- Focused/full tests cover nested/cyclic/synthetic graphs, denied source privacy, no source-only inventory scan, stale changes and strict cross-language contracts. Actual MCP reads passed two compendium sources and exact prose fingerprints; relationships correctly stayed unverified for unowned scope.
- Corrected the live inventory audit: its three owned containers are on excluded loot Actors, not supported NPCs. Owned/nested/cyclic graphs have deterministic coverage only; the runtime gap remains explicit. Casting eligibility audit also confirms canCast does not establish resource availability, with no new production API dependency.
- ITEM-backpack Complete for source/containment scope. Completed stories: 19/39 (48.7%). CORE-casting remains In progress; its original conditional availability gate is preserved without adding an unconditional execution requirement.

### 28. Treasure source and independent price basis — October 22, 2026

- ITEM-treasure preserves nullable category, traits/publication and independent shared quantity, denominations and price.per, without using asset value, stackGroup, sale or conversion math. No usage/investment state is synthesized. Supported Actor valuables remain readable while loot Actors remain unsupported.
- Focused/full suites passed (251 Python, one skipped; 291 JavaScript). Six actual MCP reads cover NPC-owned, synthetic-token and four pack categories, with exact source/description fingerprints unchanged. Character/familiar and non-unit basis cases have deterministic coverage.
- Corrected an over-broad private-data test marker whose ordinary word collided with legitimate capability documentation; the unique fake source marker keeps exposure detection intact. No production behavior was weakened to satisfy the assertion.
- ITEM-treasure Complete for valuables/source scope. Completed stories: 20/39 (51.3%). The Item prerequisites for CORE-inventory are now delivered.


### 29. Actor inventory source graph — October22,2026

- CORE-inventory lists actual owned physical possessions once, joins explicit container/ammunition claims and preserves source quantity, denomination price/per, carrying/investment and serialized attachment metadata. Kit definitions remain separate; book/kit specialty expansion is optional and explicitly partial.
- Nested/rootless cycles, orphan/denied/wrong-type parents, multiple ammunition stacks, duplicate serialized/actual/kit references, token context and stale continuation cases have deterministic coverage. Live reads cover three Actor contexts and six physical types with unchanged source fingerprints; unavailable owned container/book/kit/attachment/selected-ammunition fixtures remain named gaps.
- Actual runtime naming differences exposed mixed source/prepared provenance. A failing regression established the cause; inventory now uses cached persisted names consistently without weakening validation. Full suites pass:259 Python tests (one skipped),305 JavaScript tests.
- CORE-inventory Complete for its declared source graph scope. Completed stories:21/39 (53.8%). Effective Actor integration and the remaining stories remain open.


### 30. Formula/spell book source and immediate content checkpoint — October 22, 2026

- ITEM-book now preserves category, capacity, ordered duplicate UUID claims and metadata alongside shared physical source and exact prose. Explicit relationships name immediate world/pack/owned/token targets without target-source or recursive content expansion; ownership/preparation/castability remain separate.
- Deterministic helper, paginated reader and actual Python DTO tests cover empty/missing/denied/unsupported/stale states and resolution bounds. Full suites pass:264 Python tests (one skipped),314 JavaScript tests. Actual MCP discovery/regression checks retain book live verification as not_run.
- The existing world,894 distinct Actor instances and26 Item compendiums contain no book Items. Standard blank formula/spell books are equipment and remain that type. ITEM-book stays In progress at its original representative-live-fixture gate; completed stories remain21/39 (53.8%).


### 31. Kit bundle source and immediate component references — October 22, 2026

- ITEM-kit preserves keyed nested UUID/name/quantity/container definitions and its own price, separate from physical owned stock. Escaped paths and duplicate target occurrences retain identity without quantity multiplication or generated possession UUIDs.
- Explicit component links share the audited book Item resolver, preserving canonical owner/token context and denied privacy without reading target source or recursively expanding kits. Source-only reads remain independent of resolution bounds.
- Focused/full tests pass:270 Python tests (one skipped),323 JavaScript tests. Actual MCP source/prose and all14 immediate references passed on both existing compendium kits with unchanged source fingerprints. World/owned/token/max-depth cases retain deterministic coverage; no game writes occurred.
- ITEM-kit Complete. Completed stories:22/39 (56.4%). Book and advanced Actor/casting/state gates remain open.


### 32. Ancestry choices, contributions and feature definitions — October 22, 2026

- ITEM-ancestry separates offered/selected/default/alternate and modern/legacy voluntary configuration, preserving source HP, size, movement, vision, language and schema-defined hands/reach contributions. Persisted null singleton selections are never replaced by prepared choices.
- Explicit immediate feature definitions retain keyed provenance, future levels and canonical/token follow-ups without acquisition, target-source hydration, grants or character totals. Missing/denied/unsupported/stale cases remain explicit.
- Focused/full suites pass:275 Python tests (one skipped),332 JavaScript tests. Actual MCP consumed three ancestry definitions and exact prose, followed two feat identities and preserved complete source fingerprints. Owned/token/alternate/voluntary cases have deterministic coverage.
- ITEM-ancestry Complete. Completed stories:23/39 (59.0%). Remaining build Item stories still gate CORE-build and integrated character support.


### 33. Background source and definition checkpoint — October 22, 2026

- ITEM-background preserves offered/null/absent boost choices, skill codes, Lore labels and keyed feature definitions. Empty structured fields do not prove no benefit; exact prose retains terrain-Lore choices and rare-background exceptions.
- Explicit immediate feat definitions retain source occurrence identity without acquired claims, Lore construction, grant execution or duplicate-training replacement. Actual MCP passed three background sources/prose and two feat follow-ups with unchanged source fingerprints.
- Focused/full suites pass:281 Python tests (one skipped),341 JavaScript tests. Actual paginated JavaScript DTOs cross strict Python validation; world/pack/token, malformed/denied/stale/bounded cases have deterministic coverage.
- ITEM-background remains In progress for its acquired same-Lore/feat multi-contributor acceptance in CORE-build. Completed stories remain23/39 (59.0%). Independent remaining build readers can proceed before this integration closes.


### 34. Heritage selections and nullable ancestry links — October 22, 2026

- ITEM-heritage preserves independent heritage identity, nullable ancestry association and metadata. Explicit ancestry links resolve only actual ancestry Items and do not establish owner membership, exclusivity, eligibility or effective benefits.
- Focused/full suites pass:288 Python tests (one skipped),351 JavaScript tests. Actual MCP consumed three heritage definitions and exact prose, verified one Elf identity follow-up and two unassociated results, and preserved source fingerprints. World/pack/token, independent synthetic target, denied/stale and non-PF2e boundaries have deterministic coverage.
- Corrected stale generic limitation text on delivered definition readers; regression coverage verifies accurate source limitations while retaining pending effective/acquisition capabilities.
- ITEM-heritage Complete. Completed stories:24/39 (61.5%). Background acquired-item integration and remaining class/deity/feat readers still gate the character Build view.


### 35. Class definitions, labelled starting ranks and progression — October 22, 2026

- ITEM-class preserves key-attribute offers/null selections, HP contribution, labelled raw starting proficiency ranks, training and all five progression lists. Named features retain source levels and keyed occurrence identity without advancement or acquisition.
- Focused/full suites pass:294 Python tests (one skipped),360 JavaScript tests. Actual MCP consumed Fighter/Rogue/Wizard, exact prose and51 immediate feature links with unchanged source fingerprints. World/pack/token and malformed/denied/stale cases have deterministic coverage.
- Optional other-attack name handling follows audited public field semantics; no private defaults or prepared values are used. The original Player Core boost discrepancy remains documented with no arithmetic from it.
- ITEM-class Complete. Completed stories:25/39 (64.1%). Deity/feat readers and acquired background integration remain before character Build completion.

### Deity source implementation checkpoint — October 22, 2026

Deity source options and explicit spell identity links are wired into selected Item
reading, with strict Python validation of actual paginated JavaScript output.
The story remains In progress pending rulebook/live verification and integration
review. Completed progress remains 25/39 (64.1%).

### Deity source and spell references complete — October 22, 2026

ITEM-deity is Complete: rulebook prose, pinned schema, deterministic contexts
and fresh authenticated MCP reads establish offered options and immediate spell
identity references. Three actual definitions and nine spell targets passed exact
source/prose comparisons and unchanged source fingerprints. No acquisition or
active benefits are inferred. Completed progress is26/39 (66.7%).

### Feat source checkpoint — October 22, 2026

ITEM-feat remains In progress. Typed source extraction and strict Python
validation distinguish feat/feature categories, nominal/taken levels and
subfeature options without applying them. Four actual compendium definitions
passed source/prose/fingerprint verification across19 pages and124 records.
A separate persisted grant schema audit establishes a proposed narrow allowlist;
acquired grant/selection joins remain to implement. Progress remains26/39 (66.7%).

### Feat persisted reference checkpoint — October 22, 2026

Implemented selected persisted grant flags and explicit same-owner grant-ID,
self-effect and suppressed-feature references. Deterministic coverage includes
synthetic ownership, exact target identity, permission/staleness and bounded
continuations. Live reads verify actual missing/empty states on four definitions,
21 source pages and132 records. Populated runtime grants, selections and integrated
acquired-document joins remain open. ITEM-feat stays In progress;26/39 complete.

### Recorded feat selection checkpoint

Added a narrow recorded-selection source allowlist: exact strings and finite
numbers, distinct absent/empty maps, no UUID or acquisition inference. Unsupported
values are withheld and make source partial. Acquired joins and populated owned
runtime verification remain open; ITEM-feat stays In progress,26/39 complete.

### Journal Actor/Item references complete — October 22, 2026

CORE-journal delivers lazy selected-reference resolution with canonical named
identities and complete reader selectors, including synthetic token context.
Existing-world live checks follow journal → Actor → owned Item and a compendium
Item while preserving journal source/revision. Deterministic tests cover relative
links, anchors, duplicates, bounds, permissions and asynchronous source changes.
Completed progress is27/39 (69.2%).

### Shared grant-source dependency for build joins

The common PF2e Item grant selector now accepts build contributors without
pretending they are feats. The feat-only wrapper preserves its existing output.
Focused source and paginated cross-language regression tests pass. CORE-build is
In progress; its integrated view and donor-validation contract remain unfinished.
Completed progress remains27/39 (69.2%).

### Character Build joins complete — October 23, 2026

CORE-build, ITEM-background and ITEM-feat now meet their original selected-source,
reference and acquired-document integration acceptance. The character Build
section lists each actual owned Item once while preserving separate persisted
contributor claims and reciprocal source evidence. Options, future definitions,
null choices and deity spell options never establish acquisitions.

Actual MCP verified seven owned Items, shared Lore/feature claims, scalar
selections and unchanged source fingerprints over 217 Build records / 32 pages
plus eight embedded source/description pages. The marked temporary character in
the existing development world was removed. Initial console inspection found zero
errors; final refresh showed only the core minimum-window-dimensions notification.
Actual discovery checks passed. The [verification record](build-verification.md)
states the runtime, fixture boundaries and deterministic cases.

A reproduced donor-type inconsistency regression was fixed before completion.
Full suites pass:331 Python tests (one skipped),412 JavaScript tests. The story
graph remains acyclic and consistent. Completed progress is30/39 (76.9%);
effective character views, casting, state and remaining live gates stay open.

### Character source checkpoint — October 23, 2026

Selected persisted character fields and explicit bounded biography are delivered.
Null manual attributes remain null, ranks remain distinct from check modifiers,
and source HP/focus maxima and prepared fields are excluded. Actual MCP verified
51 source/description records over eight pages, default prose privacy and
unchanged source fingerprints with confirmed marked-fixture cleanup. Full suites
pass:335 Python tests (one skipped),425 JavaScript tests. See
[verification](character-verification.md).

ACT-character is Source implemented, not Complete. Its integrated/current views
remain open; the public transformed-document candidate is recorded separately.
Completed progress remains30/39 (76.9%).

### Selected transformed statistics — October 23, 2026

Character/NPC statistics now reads bounded declared current document-data fields
through public `toObject(false)`, retaining transformed basis separately from
source. The section remains partial; missing serialized leaves stay unavailable.
Actual MCP verified an elite world NPC, synthetic NPC and marked character:
129 statistics records across 20 pages in total, exact independent serializer
matches and unchanged source snapshots. The character fixture was removed.

A failing live HP-container case was reproduced and fixed with a regression:
nonplain serialized containers are accepted for own declared data fields, while
inherited fields/getters remain excluded. Full suites pass:341 Python tests
(one skipped),440 JavaScript tests. See
[verification](current-statistics-verification.md).

ACT-character and ACT-npc remain Source implemented; the original full integrated
acceptance is preserved. Completed progress remains30/39 (76.9%).

## Familiar source and master identity checkpoint

ACT-familiar is Source implemented. Selected stored master/HP and explicit
creature prose retain raw provenance; identity resolves the world-character
master without the PF2e master getter. Owned action Items retain identities and
exact traits, always unclassified until their descriptions are read. Integrated
casting/state and master-derived statistics remain open.

Actual MCP verified 11 familiar records over six pages and 16 owned action
source/prose pages, canonical master follow-up, nullable unassociated master,
default prose privacy and unchanged source fingerprints. Both marked temporary
Actors were removed. See [verification](familiar-verification.md).
Full suites:347 Python tests (one skipped),460 JavaScript tests. Completed
progress remains30/39 (76.9%); source checkpoints do not close Actor stories.

## Casting current-resource contract preparation — October 25, 2026

Audited official public serialization and pinned transformed focus/cost schema
contracts; [integration contract](casting-current-contract.md) separates current
pool value/maximum/capacity and spell cost from persisted source and availability.
A pure detached-data helper has seven focused passing tests. It is not yet
connected to published readers or packaged runtime; no new live capability or
completed story is claimed. Contextual option/rank and signature rulebook
verification remain the next casting work. After the machine restart the
services/browser were restored; live checks await the existing test-world GM
connection. Completed progress remains30/39 (76.9%).

## Casting current-resource integration — October 25, 2026

Explicit spellcasting now includes separately labelled transformed character/NPC
focus value/max/cap and readable owned-spell focus costs. Source records are
unchanged. Strict Python validation accepts actual paginated JavaScript DTOs,
rejects wrong ownership/type/provenance, and requires missing-current diagnostics.
Current-only Actor or spell changes invalidate continuations. Source/default
reads do not request transformed serialization; familiar Actor pools stay excluded.

The [contract](casting-current-contract.md) and registry explicitly retain a
current-resource live-verification gap. A bounded read-only
`scripts/actor-casting-current-live-check.py` is prepared for the existing GM
connection; it has not been run. No runtime compatibility or complete casting
availability is inferred from deterministic tests. Contextual options/signature
rank rules remain unfinished. Completed progress remains30/39 (76.9%).

## Casting contextual configuration options — October 25, 2026

Explicit spellcasting now groups actual readable spells with preparation or
repertoire/innate/focus contexts, preserving repeated preparation positions,
expenditure flags, base/configured/slot ranks, independent auto-heightening
configuration and signature flags. Cast rank stays null and availability stays
not_evaluated. Unresolved preparation references retain their separate rows;
unsupported modes preserve identities without inventing execution semantics.

Canonical complete Player Core reads now include the Bard signature feature
and the higher-slot-without-heightening distinction. See
[verification](casting-verification.md) and [option contract](casting-options-contract.md).
Strict Python validation reconstructs mapped values from source witnesses and
checks actual paginated JavaScript responses. Preparation indexing is shared
per entry, with explicit aggregate bounds. Live verification remains pending
the existing GM connection; evaluated ranks, signature eligibility/alternatives
and full current availability remain open. Completed progress stays30/39 (76.9%).
Full suites passed:359 Python tests (one skipped),484 JavaScript tests. Actual
authenticated discovery passed without a browser; it explicitly did not check
runtime behavior.

## Remaining acceptance-gap audit — October 25, 2026

Five token workflow regressions now cover two unlinked shared-base Actors with
distinct source/current HP and owned Items, inactive scenes, linked controls,
stale snapshots and token-selected familiar master differences. Existing live
evidence covers one synthetic NPC; the two-token read-only comparison remains
pending GM connectivity. No world documents changed. CORE-token stays In progress.

The book constructor audit also corrects a potential false blocker: hidden UI
creation is not production constructor rejection. A genuine marked temporary
book is a candidate for the existing development world's live acceptance;
actual support remains unverified. Affliction's explicit production guard is
different and remains unresolved. Completed progress stays30/39 (76.9%).

## Condition/effect boundary regression fixes — October 25, 2026

Failing regressions exposed selected getter execution, an affliction-parent
validation mismatch, impossible missing-reference statuses and same-page badge
contradictions. Source and relationship selectors now require own detached data
without invoking accessors; subtype dispatch validates condition/effect type
before reading it. Python matches the existing browser's disabled-affliction
and absent/null/empty-reference behavior and checks available page-local badge
discriminators without requiring off-page witnesses. Actual JavaScript DTO
regressions retain valid pagination and token context. No new API dependency,
world write or effective-state claim was introduced. CORE-state integration
remains next; completed progress stays30/39 (76.9%).

## Integrated Actor state source view — October 25, 2026

Explicit `read_actor` state now joins actual condition/effect identities,
typed stored source and immediate local/external references. Overlapping Items
remain separate, application stays unknown and unsupported affliction reading
is explicit even in an empty result. Snapshot limits preflight owned Items,
selected rows and nonempty external claims before resolution. Default/source
reads do not inspect state Items; continuations track owned and external changes.

Focused JavaScript and strict Python tests consume actual paginated reader
responses, preserving token context and raw provenance while rejecting forged
owners, activity claims and contradictory page witnesses. See the
[contract](state-contract.md). CORE-state is In progress; affliction stages,
effective suppression/expiry/application and live state-view verification retain
their original gates. Completed progress remains30/39 (76.9%).

## Current skill and Lore integration — October 25, 2026

Explicit skills now adds selected transformed character/NPC skill fields,
character proficiency labels, NPC qualification notes and actual itemId-based
Lore contributor joins. Owned Lore source rows remain independent, including
duplicate names and prepared-map collisions. Denied Lore skills withhold their
keys, labels and totals; current-only and target-identity changes invalidate
continuations. Missing fields never fall back to source or runtime getters.

Deterministic helper/reader/Python tests cover world, pack and token contexts,
raw provenance, bounds, rank/modifier/DC distinctions and permission privacy.
Authenticated discovery passed without game data. See the
[contract](skills-current-contract.md). NPC conditional variants, familiar
skills and current-skill live verification remain open; this checkpoint does
not close the full Actor stories. Completed progress stays30/39 (76.9%).

## Permission-checked current familiar statistics — October 25, 2026

Explicit statistics now resolves and rechecks the recorded world-character
master before familiar transformed serialization. Source ID/ability remain
separate witnesses; current defenses, movement and ordinary skills retain
transformed provenance without local formulas. Unavailable master returns no
transformed rows. Reassignment and permission-loss races are guarded before
serialization; Item-linked skills are withheld without key/label disclosure.

Deterministic world/pack/token and paginated Python boundary checks pass.
Authenticated discovery passed with runtime_checked false. The existing fixture
runner has an optional statistics mode reusing its marked pair and cleanup;
it has not been run. Representative live values and original integrated gates
remain open; see the [contract](familiar-current-contract.md). A separate tiny
skills-boundary regression also aligns empty-key rejection with the documented
1–256-codepoint bound. Completed progress remains30/39 (76.9%).

## Current senses, languages and conditional defenses — October 25, 2026

Character/NPC statistics now includes selected current senses, language codes
and qualifications, and IWR declarations with exceptions/doubleVs. Positive
Infinity sense range retains exact tagged JSON encoding, never silent null.
Custom predicates are bounded typed data without evaluation; omitted custom
definitions stay explicit gaps. The same public serializer output supplies
core and supplemental fields, with a combined snapshot bound and unchanged
source/default behavior.

World/pack/token, paginated Python DTO, getter-safety, conditional-data and
current-only stale-read tests pass. Authenticated discovery passed without
world access. The existing read-only current probe now compares supplemental
values independently; it has not run against the GM world. See the
[contract](creature-current-contract.md). Target detection, conditional damage
application and representative live serialization remain unverified. Completed
progress remains30/39 (76.9%).

## Genuine books and existing NPC state — October 25, 2026

ITEM-book is Complete after public creation and reading of two genuine marked
world books (formula/spell), populated compendium links, duplicate/missing
references, exact long Unicode prose and confirmed cleanup. The live harness
verified 26 pages, 82 source witnesses, six relationships and 48 description
fragments in 40 MCP calls with unchanged source fingerprints. Offline
harness tests include deferred-creation cleanup and the actual exploration
serializer budget regression. See [book verification](book-verification.md).

The independent state verifier now distinguishes persisted Item names from
prepared display labels, proven by a failing-then-passing offline regression.
Two existing NPCs passed 54 MCP calls: 10 state pages, 56 records, 76 raw witnesses
and two resolved relationships, with unchanged source fingerprints. The sampled
effect omitted serialized expiry, so no current expiry value is live-verified.
Character/familiar/token state, application and affliction gates remain open.

Completed progress is **31/39 (79.5%)**. CORE-state remains In progress; its
original acceptance criteria and dependencies are unchanged.

## Token coverage and casting boundary verification — October 25, 2026

The new read-only token harness scanned 50 Scenes and 778 placed tokens across
eligible character/NPC instances. Linked and inactive controls exist, but the
required same-base pair with distinct HP and meaningful Item state was absent.
Eight offline tests prove selection and paginated reader orchestration without
writes. CORE-token remains In progress under its original acceptance criteria;
see [token verification](token-verification.md).

Casting source identity and contextual-option names now match their persisted
name witnesses, while immediate relationship labels retain display names.
Failing-then-passing actual JavaScript/Python regressions cover this distinction,
Unicode clipping and stable same-page identity joins, retaining forged-target
rejection.

The existing NPC current-resource run passed after bounded byte-limit recovery:
171 retained casting pages, 1,052 records, 57 current records and 46 source pages.
All four ordinary modes were represented. Complete fingerprints were unchanged;
323 requested / 322 completed calls include one documented `ResponseTooLarge`
restart that discarded 101 smaller-budget pages. A separate current-statistics
run verified 14/10 supplemental records for world/synthetic NPCs, respectively.
Neither run evaluates final rank, signature alternatives or complete castability.
Completed progress remains **31/39 (79.5%)**.

## Declared public effect expiry — October 25, 2026

The earlier serializer-only reader omitted expiry because `toObject(false)`
does not include every declared current system field. Official public core
`ItemData.system`, pinned PF2e `EffectPF2e.system: EffectSystemData`, and its
`expired: boolean` declaration establish the supported model boundary. The
reader now selects that own data property with transformed provenance, without
getters, preparation, time arithmetic or source/serialization fallback.

Failing-then-passing JavaScript/Python tests preserve false, reject accessors and
invalid values, protect denied Items, and stale continuations on model-only
changes. An independent Node-backed verifier reproduces serializer omission.
The existing NPC run now verifies one present false expiry flag, zero absent
flags, 56 records and 76 raw witnesses in 54 MCP calls with unchanged source.
Expired-true, other Actor/token state, condition suppression, application and
affliction gates remain open. CORE-state remains In progress; completed progress
stays **31/39 (79.5%)**. See [state contract](state-contract.md).

## Guarded public familiar model verification — October 25, 2026

Familiar current reads now select declared own `Actor.system` data after the
existing master/role/source/context permission checks. Schema-based serialization
is not a fallback. Failing-then-passing tests cover omitted serialized fields,
unresolved and raced master access, own-data getter rejection, model-only stale
continuations and strict Python discovery/DTO contracts.

The hardened fixture runner passed in the existing test world: 127 present
current fields, zero missing, 128 statistics records across 64 pages, plus six
Actor pages and 16 Item pages. Representative numeric AC, saves, ordinary skills
and land Speed are required. Master unassignment returned only one source-context
page with no derived rows; the verifier independently preserves the system's
normalized nullable ability. Per-phase source fingerprints were unchanged and
the exact marked familiar/character pair was removed, with no pending creations.
The run made 108 MCP calls. Nine offline harness tests cover timeouts, lost
responses, late-creation cleanup, real model witnesses and nullable source
normalization.

World familiar current values now have runtime evidence. Compendium/token
current fixtures and integrated casting/state remain open, so ACT-familiar and
M-FAMILIAR stay incomplete. Progress remains **31/39 (79.5%)**. See the
[familiar current contract](familiar-current-contract.md).

## Declared current Strike view — October 25, 2026

Character/NPC Strikes now selects closed public `Actor.system.actions` own data,
separately retaining authored NPC melee references. Response-local Actor paths
cover generated attacks and alternatives without invented Item UUIDs. Actual
permitted owned object membership is required for canonical origin links;
denied and unverified origins protect labels and totals. Getter-backed PC MAP
fields are explicit unsupported capabilities, not missing values or recomputed
penalties. Long text fragments are exact and bounded.

Live world/synthetic NPC plus marked-character verification passed 29 pages,
214 records and 220 raw witnesses across 78 MCP calls. Four origins were owned
Items; one was generated unarmed on a character with zero owned Items. Six
accessors were confirmed without invocation. Source fingerprints and exact
fixture cleanup passed. Unit regressions cover all contexts, privacy, stale
current/source state, text, bounds, source-name precision, packaging and detached
array markers that cannot retain model serialization callbacks.

Damage, target eligibility, other attack modes and remaining Actor integration
dependencies remain open. Completed progress stays **31/39 (79.5%)**. See the
[Strike contract](strike-current-contract.md) for exact delivered scope.

## Casting reading acceptance — October 25, 2026

CORE-casting now passes its original reading contract: source joins, independent
rank/resource contexts, selected current resource fields and explicit limitations.
The acceptance audit maps every original requirement to implementation/tests and
actual runtime evidence; no casting engine or complete-availability claim was added.

Independent MCP verification matched all 58 options and 663 unique source
witnesses across prepared, spontaneous, innate and focus modes on two existing
NPCs. Source/current fingerprints remained unchanged. Repeated preparations,
zero generic counters, cantrips, absent innate uses and unresolved entries were
observed. Signature true, innate cantrips and explicit expenditure booleans retain
deterministic coverage only. New regressions also prove shared Actor focus across
two entries and prevent higher spontaneous slot capacity from becoming a cast
rank or signature entitlement.

The run retained 171 casting pages/1,052 records/57 current records and 46
source/default pages. Its 341 requested/340 completed calls include one legitimate
ResponseTooLarge recovery at 48,000 bytes after discarding 101 earlier pages.
The verifier now checks option key-set completeness, all selected source paths
and mapped meanings rather than treating transformed-resource comparisons as
proof of source-based options.

CORE-casting is Complete; **32/39 stories (82.1%)**. Actor integrated checkpoints
still require CORE-state. Final rank/availability, specialized casting and
character/familiar current casting resources remain explicit advanced limitations.
Full regression checks passed: 467 Python tests (one skipped) and 575 JavaScript
tests. See the [acceptance audit](casting-acceptance.md).

## Character state and expired-true verification — October 25, 2026

The explicit opt-in state fixture now verifies a genuine character with three
effects, three conditions and two inert origin actions in the existing test world.
Actual MCP passed 27 state pages/173 records, 238 raw witnesses and 12 resolved
relationships across 40 calls. True and false own-model expiry flags, distinct
origins for same-name effects, an unevaluated encounter formula badge and
valued/unvalued/persistent-damage condition source all matched independent reads.
Read fingerprints and exact cleanup passed.

The default runner remains read-only. Optional setup creates only the marked
character and owned Items, updates only its timed effect's start and cleans up
through exact UUID/type/run checks. Nine independent safety regressions cover
delayed creation, lost responses, cancellation, bounded deadlines and cleanup;
the state reader regression retains stored override claims without reading
condition activity or claiming suppression.

CORE-state remains In progress: genuine affliction reading and effective
suppression/application are still open, as are familiar/token state fixtures.
Progress remains **32/39 (82.1%)**. See the
[state verification record](state-contract.md#marked-character-state-verification--october-25).
Full suites passed: 478 Python tests (one skipped) and 576 JavaScript tests.
Fresh-client discovery also passed; the refreshed GM browser showed only the
previously known window-size notification.

## Existing token-state proof and acceptance blocker audit — October 25, 2026

The read-only state adapter now verifies existing unlinked token instances:
two samples, 10 state pages/51 records, 71 raw witnesses and two owned Item
follow-ups in 67 MCP calls. It checks each page's actual Actor/Scene/token/base
identity, exact source/current provenance, origin token context and unchanged
source/current fingerprints. No documents were created or modified. The sample
covers conditions/effects and a present false expiry flag; full effective state
and token expired-true remain unverified.

The CORE-token probe incorrectly required both stored/current HP differences
and different Item definition contents. These extra requirements have been
removed, with fail-first regressions retaining actual owned membership and
canonical document separation even when definitions match. The corrected live
census still cannot satisfy the original distinct-current-HP pair: 50 Scenes,
778 tokens, 559 readable supported unlinked Actors and 117 eligible base groups
contain zero groups with distinct current HP. No ownership/UUID invalidity or
nonfinite HP caused the gap.

CORE-token is now explicitly Blocked on existing fixture configuration.
ITEM-affliction is Blocked on PF2e8.6.1's production constructor. Their original
acceptance criteria and the prerequisite graph remain intact; no unsupported
capability has been counted Complete. A capability decision was requested for
afflictions while independent work continued; no answer or reduction is assumed.
Completed progress remains **32/39 (82.1%)**. See
[token verification](token-verification.md) and
[state verification](state-contract.md#existing-unlinked-token-state-verification--october-25).
Full regression checks passed: 484 Python tests (one skipped), 576 JavaScript
tests, dependency/diagram validation and fresh-client discovery. The refreshed
GM browser retained only its known window-size notification.

## Approved affliction deferral and honest delivery scope — October 25, 2026

The user explicitly classified dedicated Affliction Items as incomplete upstream
and outside delivery of this story set, to be revisited after PF2e maintainers
complete them. ITEM-affliction is Deferred, with its original acceptance retained
for that follow-up. It is not Complete and earns no completion credit.

Current delivery therefore contains **38 stories; 32 are Complete (84.2%)**.
The recorded backlog still contains 39 stories, including the one deferred type.
The percentage change from 82.1% reflects the approved denominator change, not
another implemented story. CORE-state no longer depends on ITEM-affliction;
its condition/effect acceptance remains unchanged. The separate token-pair
fixture blocker is unchanged.

Readable-type input schemas must omit affliction. Registry entries must report
in_scope/source/mapped/effective false, and tool descriptions/errors must clearly
identify upstream-incomplete, deferred functionality without suggesting a
source-only or stage/timer fallback. Existing unsupported state markers and
reading poison/disease/curse descriptions through supported Item types remain.

Fresh-client verification of the running interface passed four MCP calls across
22 published tools: no affliction input enum/const or dedicated reader is offered,
the registry is out-of-scope/unsupported, and two invalid filters reject before
document access. Zero documents were read or changed. The
[interface record](affliction-verification.md#approved-deferral-and-actual-interface-verification--october-25-2026)
and seven offline checker tests preserve this caller-facing boundary.
Full regression checks passed: 497 Python tests (one skipped) and 578 JavaScript
tests. Dependency/diagram validation passed for 38 delivery stories, 39 retained
stories, 42 nodes and 79 edges. One stale error-wording assertion was updated to
check the InvalidRequest code and readable-type guidance after its failing run.

## Condition/effect reading acceptance — October 25, 2026

CORE-state is Complete under its original supported-portions contract and the
approved dedicated-affliction deferral. The [acceptance audit](state-acceptance.md)
maps every current requirement to implementation/tests and the existing NPC,
marked character and existing unlinked-token runtime evidence. No additional
fixture collection or unsupported activity interface was needed.

Stored override claims preserve both conditions with unknown application;
overlapping effects and distinct origins remain separate; typed duration/badge
source and both supported expiry flags retain exact provenance. Full condition
suppression/general application remain explicitly unsupported. Familiar live
state and token expired-true remain unverified advanced configurations.

Progress is **33/38 delivery stories (86.8%)**, plus one Deferred affliction
story outside delivery. Actor integrated checkpoints are now dependency-ready;
their own combined-section acceptance and character ability-navigation gap still
require work. CORE-token's missing existing distinct-HP pair remains Blocked.
Full regression checks passed: 497 Python tests (one skipped) and 578 JavaScript
tests. Dependency/diagram and whitespace checks also passed.

## Character owned ability navigation — October 25, 2026

Character abilities now lists permitted actual owned action and feat/feature
Items with exact name/type source provenance, bounded named identities and
canonical Item follow-ups. Permission and exact parent/membership checks precede
source/identity extraction; denial is an aggregate with no name/ID disclosure.
The list remains partial for basic/generated/prose-only capabilities and active
benefits. Defaults/source-only reads never select owned abilities.

Actual MCP verified a genuine marked character's action, feat and class feature:
three references, one Actor page, 13 source/prose Item pages and 75 independent
source checks in 24 requested/completed calls. Exact prose and full fingerprints
matched; cleanup confirmed zero pending creations and remaining marked Actors.
Two diagnostic runs also cleaned up. Their verifier mismatch was reproduced
with optional own undefined source properties and fixed using canonical source
serialization; 14 absences were independently confirmed. Production reading
did not require a correction for that mismatch.

This closes the missing character ability-navigation implementation. ACT-character
and its M-PC checkpoint remain open for combined-section integration acceptance.
Progress remains **33/38 (86.8%)**; dedicated affliction functionality stays Deferred.
Full suites passed: 511 Python tests (one skipped) and 589 JavaScript tests.
Fresh-client discovery and the refreshed GM browser checks passed. M-PC is now
tracked In progress; no full Actor story completion is claimed by this unit.

## Combined Actor integration checks — October 28, 2026

Production JavaScript readers now have combined, fully paginated acceptance
fixtures for character, NPC and familiar Actors, including all advertised
sections. Actual pages also pass through Python's strict tool boundary.
The checks retain exact contributor identity, distinct source/current values,
owned Lore joins and Item follow-ups, individual spell preparations, inventory,
state and explicit unsupported sections. Token cases retain instance ownership;
changed current values, source or permissions invalidate continuations.

The [integration audit](actor-integration-acceptance.md) records two remaining
runtime evidence gaps: character/NPC current Skills and character creature
supplements. These are distinct from already verified source ranks, Lore source
and NPC supplements. Actor stories remain open; progress stays **33/38 (86.8%)**.
Dedicated affliction functionality remains Deferred and unavailable in readable
type filters. The existing local Docker stack and test-world GM bridge were
restored without creating another instance or changing game documents.
Focused checks passed (four Python and three JavaScript); full suites passed
515 Python tests (one skipped) and 592 JavaScript tests. Dependency/Mermaid and
whitespace checks passed. These tests prove composition, not the pending live
interfaces.

## Familiar integrated acceptance — October 28, 2026

The [familiar closure matrix](familiar-acceptance.md) audits every original
ACT-familiar requirement against the delivered readers, combined-section
JavaScript/Python acceptance and existing master-linked runtime evidence.
The latter verifies 127 present current fields, exact action prose and master
follow-ups, omission of current rows after master unassignment, unchanged read
fingerprints and confirmed fixture cleanup. No additional fixture was created.

ACT-familiar and M-FAMILIAR are Complete for their declared supported/partial
views. Full mechanics, Item-linked familiar skills, ordinary Strikes, automatic
ability classification, casting availability and state application remain
unsupported or unverified. Broader contextual end-to-end acceptance stays in
CORE-acceptance; the distinct-current-HP token pair remains CORE-token's blocker.
Character/NPC current Skills and character supplements still need live evidence.
Progress is **34/38 delivery stories (89.5%)**; affliction remains separately
Deferred and unavailable in readable interfaces.

## Unattended verifier commands — October 28, 2026

The fixed runner now includes `skills-live`, `character-current-live` and
`affliction-interface`. Reviewed project rules allow those exact command names;
the runner rejects unknown commands and extra arguments. AGENTS.md records
authorization for the scoped localhost test-world checks, including bounded
marked-fixture setup/cleanup. No global sandbox or approval policy was relaxed.

The new Skills verifier passed on an existing NPC: 221 current records over
23 pages, one actual source Lore identity and current owner-local join, unchanged
source/current fingerprints, 36 requested/completed calls. Census found 172
readable NPCs with current skills and 12 with resolved Lore. This verifies that
sample's current-data boundary, not character Skills or target-context rolls.
The same-client character/Lore verifier is prepared and has offline safety
coverage; its character runtime checks remain pending. The interrupted direct
invocation supplied no runtime evidence and is not counted as a passing check.

Full suites passed: 526 Python tests (one skipped), 592 JavaScript tests.
Rule decisions were checked with `codex execpolicy check`; arbitrary Python
does not match. Current delivery progress remains **34/38 (89.5%)**.

## Character/NPC integrated acceptance — October 28, 2026

The approved fixed character verifier passed **78 requested/completed calls**
with exact marked-fixture cleanup. Its single character/Lore and an existing
NPC supplied **408 current Skills records over 42 pages**, two independent source
Lore identities and two actual owner-local current joins (64 nested calls,
included in the total). Character statistics supplied **47 core and six
supplement records over eight pages**. Independent public serialization matched
every selected witness; source/current fingerprints stayed unchanged.
Supplement coverage is language code/qualification and empty sense/IWR
collections, not populated character custom configurations.

The [character](character-acceptance.md) and [NPC](npc-acceptance.md) closure
matrices audit every original requirement against the delivered readers,
combined-section JavaScript/Python acceptance and scoped live evidence.
ACT-character/M-PC and ACT-npc/M-NPC are Complete for their declared
supported/partial views. Discovery now records current Skills/statistics proof
and explicitly preserves advanced exclusions and unverified configurations.
The discovery regression failed against stale `not_run` metadata before the
update and passes with the scoped evidence and unchanged affliction boundary.

Progress is **36/38 delivery stories (94.7%)**. CORE-token and CORE-acceptance
remain open; the former lacks an existing same-base unlinked pair with distinct
current HP. No existing tokens were changed and no original acceptance gate was
weakened. Affliction remains Deferred outside delivery.
Focused checks and full regression suites passed: 526 Python tests (one skipped)
and 593 JavaScript tests. Dependency/Mermaid and whitespace checks passed.
After refresh the native MCP registry returned the new scoped evidence; the
only browser console category was the existing core window-size notification.

## Final interface reconciliation — October 28, 2026

CORE-acceptance is In progress. Actual MCP discovery and response regression
checks first reproduced stale delivery claims, then passed after correction.
Book source/links now advertise their verified marked-world fixtures; inventory
points to the concrete book reader; Actor sections describe delivered scoped
views and the actual direct-model expiry boundary. The token-owned Item mismatch
documents its implemented DocumentNotFound recovery. Actor contracts, README
and Docker overview were reconciled with completed story evidence.

The discovery checker now selects read_actor or read_item explicitly, with
bounded connection/request/session deadlines and sanitized requested/completed
counts. Three fresh one-call checks passed against the restarted service, covering
the corrected Item and Actor descriptions. Initial attempts during the still
running restart failed before discovery; they provide no runtime evidence.
After a post-recovery refresh the GM bridge is ready and only the existing core
window-size console category remains.

Progress remains **36/38 (94.7%)**. A typed journal→Actor→ability/spell proof still
needs to be made explicit, alongside the unchanged existing token-pair gap.
Neither an unspecified Item follow-up nor source-only coverage closes those
requirements. Affliction remains Deferred, not readable or counted Complete.
Focused discovery/response tests, dependency/Mermaid checks, whitespace checks
and the full Python/JavaScript suites passed before commit.
