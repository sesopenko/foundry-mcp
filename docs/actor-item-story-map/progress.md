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
```

The fixed runner accepts only those commands. `refresh` reloads only the existing dedicated development tab; it does not change game documents. `live` exercises the existing development MCP server using its caller credential from `.env.mcp`, with read-only selectors and no secret/document-ID output. `browser` inspects readiness and console-error counts in the dedicated development profile; neither command creates worlds or changes game documents. It uses installed Python/Node dependencies, performs no network setup or release, and can be approved by its script prefix for unattended checks. The full runner uses the existing repository test script. PDF subprocess tests need host execution when sandboxed child-process waiting stalls; do not repeatedly run them in the known-failing sandbox environment.

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
