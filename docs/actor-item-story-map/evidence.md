# Actor/Item story-map evidence ledger

[Story-map index](index.md) · [Original research](../pf2e-actor-item-reference.md) · [Implementation handoff](../prompts/actor-reading-plan.md)

Audit date: **October 20, 2026** (America/Denver). This ledger records source reads and planning judgments, not implemented tool behavior. Labels retain the original distinction: **API**, **Schema**, **Rules**, **Observed**, **Proposed**, **Open**.

## Compatibility and availability

| Source | Checked fact | What it does not establish |
| --- | --- | --- |
| Project `/health` | Healthy MCP server; `foundry_clients` empty during audit | No live Actor/Item behavior was tested |
| Installed `foundry-data/Data/systems/pf2e/system.json` | PF2e 8.6.1; minimum core 14.361, verified 14.369, maximum 14 | Installed metadata is not a running browser version check |
| Pinned upstream release manifest | Same PF2e release and compatibility declaration | Future PF2e/core compatibility |
| Existing root Compose service check | Foundry service was not running during this audit | No new instance or world was provisioned; live gates remain open |
| Existing reference | Earlier live research examined Foundry 14.369 / PF2e 8.6.1 | Those October 19 probes are historical evidence, not new passing checks |
| Module manifest | Module minimum core remains 13 | PF2e 8.6.1 cannot be used as the v13 test pairing |

**Decision for this backlog:** use PF2e 8.6.1/core 14 as the documentary baseline. CORE-contract must publish the supported version/section matrix before implementation. Retain v13 as a compatibility gate: establish a compatible pinned system and verify behavior, or explicitly make new PF2e reading capabilities unavailable on that pairing. Do not silently widen minimum compatibility or claim v13 support from API similarity.

## Public Foundry API

Grounded Docs `foundry-vtt` indexes for **13** and **14** were found. Searches were followed by fresh `fetch_url` reads of relevant official pages; index crawl age was not exposed by `find_version`. Therefore the evidence is the fetched public page on this audit date, not a claim that the entire index is current or complete.

| Contract | Official evidence actually inspected | Disposition |
| --- | --- | --- |
| Public/private boundary | [v14 API guidance](https://foundryvtt.com/api/v14/) | Adopt only externally callable methods/schema fields; generated documentation alone does not qualify protected/internal members |
| Actor source extraction | [Actor v14](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject), [Actor v13](https://foundryvtt.com/api/v13/classes/foundry.documents.Actor.html#toobject) | `toObject(source=true)` returns source by default; false selects transformed values, not guaranteed complete effective sheet state |
| Embedded lookup | [Actor v14 getEmbeddedDocument](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#getembeddeddocument), [v13](https://foundryvtt.com/api/v13/classes/foundry.documents.Actor.html#getembeddeddocument) | `embeddedName`, child ID and optional invalid/strict options; preserve actual parent identity |
| Embedded grouping | [Actor v14 itemTypes](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#itemtypes), [v13](https://foundryvtt.com/api/v13/classes/foundry.documents.Actor.html#itemtypes) | Public grouping of owned Item instances; not proof of all possible abilities |
| Roll data | [Actor v14 getRollData](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#getrolldata), [v13](https://foundryvtt.com/api/v13/classes/foundry.documents.Actor.html#getrolldata) | System-defined roll context; reject a universal normalized-sheet interpretation |
| Permission checks | [Actor v14 testUserPermission](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#testuserpermission), [v13](https://foundryvtt.com/api/v13/classes/foundry.documents.Actor.html#testuserpermission) | Check authenticated browser user's document rights explicitly; never use caller role strings as authority |
| Pack read/navigation | [CompendiumCollection v14](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html), [v13](https://foundryvtt.com/api/v13/classes/foundry.documents.collections.CompendiumCollection.html) | `getIndex({fields})`, `getDocument(id)`, `testUserPermission(user, permission, {exact})`; loaded document cache is not an exhaustive pack |
| Relative/full UUID resolution | [fromUuid v14](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html), [v13](https://foundryvtt.com/api/v13/functions/foundry.utils.fromUuid.html) | Async full document or null; `relative` is an originating Document, not a name or ID |
| Scene instance | [TokenDocument v14](https://foundryvtt.com/api/v14/classes/foundry.documents.TokenDocument.html#actor), [v13](https://foundryvtt.com/api/v13/classes/foundry.documents.TokenDocument.html#actor) | `actor` selects linked world/synthetic state; `baseActor` remains separate; `isLinked` is public. v14 notes synthetic readiness after document initialization |
| Core Actor/Item schemas | [ActorData v14](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorData.html), [Item v14](https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html) | Actor `items`, `folder`, `system`, `type` establish generic storage; system semantics need PF2e evidence |

Specific folder traversal APIs, revision strategy and effective PF2e statistic interfaces remain implementation gates. Build from supported relationships; do not adopt UI trees, preparation methods, sheet data or DOM. No production dependency on an internal member is proposed here.

## PF2e schema baseline

Release **pf2e-8.6.1**, commit **`28d9d156f252d084371d994dc359509b49eadf18`**. [Pinned upstream manifest](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/system.pf2e.json) and [template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json) supplement each story's linked data definition.

The complete upstream checkout is available locally at ignored `.local/pf2e-research`, detached at that commit. Read/search locally for low-latency source research; retain immutable public URLs in committed evidence. The checkout contains no private PDFs and is not part of the project deliverable. Do not index its entire compendium corpus into Foundry API documentation.

Grounded Docs also successfully indexed the pinned NPC attack schema as **`pf2e-schema@8.6.1`**. A search for `subjectToMAP damageRolls` returned the immutable source and declared fields. This is a **single-file index**, not a complete PF2e schema index. Use local `rg`/source reading for the rest; use `foundry-vtt` Grounded Docs for core contracts. The API endpoint fetch establishing the release commit and the subsequent git checkout agreed.

**Schema evidence establishes version-specific data contracts, not blanket public status for system methods.** Read `*Source` interfaces/defineSchema separately from `*Data`, `declare`, preparation bodies, sheets and community core declarations. Do not invoke preparation/migration methods from readers.

| Area | Audit disposition |
| --- | --- |
| Character/NPC | Source interfaces rechecked; authored NPC fields and nullable PC attributes/ranks are distinct from prepared statistics |
| Familiar | `master.id` is a nullable Character foreign-document relationship; source omits ordinary perception/saves/skills/resources. Derived declarations do not fill this gap automatically |
| Action/feat | Activation/category/level/frequency fields verified; `action` uses the upstream `ability/data.ts` definition. Persistent grant flags still need a supported allowlist |
| NPC attack | Explicit `action` includes strike and other attack modes; only strike records receive the Strike label. Range is structured separately from Item type |
| Casting | Source spell location/signature/uses and casting-entry prepared ID/expended records verified. Character source persists focus value but explicitly excludes focus max; creature source allows an optional value/max record. Pool capacity therefore needs its own supported basis. Template/type naming and historical mixed record shapes require concrete persisted fixtures |
| Lore | Source/template fields `mod.value` and `proficient.value` rechecked; effective PC total remains open |
| Conditions/effects | Stored values, references, persistent damage, duration/start/context/badge fields verified; activity/expiry cannot be certified by stored presence |
| Affliction | Earlier schema gap narrowed: structured save, status, onset, stages, duration/start/context verified. Status stage is one-based; stages array is zero-based. No representative live Item verified |
| Physical types | Common PhysicalSystemSource plus concrete exceptions rechecked. Carry/investment, quantity, price.per, container and serialized subitems need distinct treatment |
| Armor/shield | Source `usage` explicitly absent; runtime usage is derived. Shield schema supports reinforcing runes; no inference of raised state |
| Book | Formula/spell category, capacity, Item-UUID contents established. This is a physical Item and unrelated to PDF retrieval; no representative live Item verified |
| Kit | Own nested bundle schema, not PhysicalSystemSource. Its source components do not establish possessed inventory |
| Treasure | Source price.per and quantity must survive mapping; loot Actor exclusion does not exclude valuables |
| Type discovery | Legacy template lists only character/npc under Actor.types; manifest documentTypes adds familiar and other categories. Template alone is not the complete runtime Actor type list |

## Rulebook source reads

All citations below refer to **source pages actually read with `read_pdf_pages`**, not search snippets. Each listed page returned `next_offset=null`; no continuation remained unread. Page numbers are printed labels. Physical pages were checked in returned metadata. Store paraphrases/citations only; do not commit extracted private book text.

| Book / revision (SHA-256) | Printed labels read in this audit | Physical page mapping |
| --- | --- | --- |
| Player Core Remaster / `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` | 15, 19, 33, 35, 41, 84, 91, 94, 194, 206, 212–213, 240, 249, 253, 259, 267–268, 271, 274–275, 288, 297–299, 303–304, 414, 418, 430, 442, 445 | For these reads only: physical = printed + 1 |
| GM Core Remaster / `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` | 86, 119–120, 123, 128, 219–221, 232 | For these reads only: physical = printed + 1 |
| Player Core 2 / `ecdb10a329949ff9bd13ffb26e60892df7daabbb3cb5e4068ec2050d92f86596` | 89 | Physical 90, label 89 |

Player Core 33/304 were contextual reads without additional mechanics adopted. Page 94 returned sparse text and establishes no class rule. Monster Core PDF was unavailable in this library; do not imply it was consulted. This is targeted coverage of the mapping claims, not a whole-book review or all classes/features audit.

### Player Core

| Labels | Verified concept | Planning consequence |
| --- | --- | --- |
| 15, 414, 418 | Activation categories, basic actions and Strike differ | Null action count is not free action; embedded Items are not all possible actions; spell attacks are not automatically Strikes |
| 19, 41, 84, 91, 194 | Attribute/build contributions, heritage, skill/Lore grants and future class features | Preserve selected versus offered/acquired; do not reconstruct total statistics or advance the character |
| 35 | Religious affiliation does not automatically grant devotee benefits | Deity weapon/spell/domain entries remain options unless acquisition is established |
| 206, 212–213, 259 | Companion/pet/familiar rules differ; familiar uses master-linked rules and selected abilities | Explicit role evidence; no invented familiar attributes or ordinary Strikes |
| 240, 249, 253 | Lore specialties are skills; feat rules include prose requirements | Merge Lore into Skills with Item identity; keep Battle Medicine text and linked mechanics available |
| 267–268, 271, 274–275, 288 | Carry states, equipment packages, armor contributions, shield use, weapons and formula books are distinct | Separate inventory from effective attacks/defenses, definitions from possessed content, book contents from preparation |
| 297–299, 303 | Definition rank, slot rank, heightening, casting mode and spell format differ | Keep distinct values; do not flatten prepared/shared/individual/focus resources or assume membership means castability |
| 430, 442, 445 | Affliction definition/tracked state, suppression and persistent damage require context | Stored presence/status is not proof of complete effective application |

### GM Core and Player Core 2

| Book / labels | Verified concept | Planning consequence |
| --- | --- | --- |
| GM Core 86 | Many curses have one effect; staged afflictions are not universal | Do not fabricate stages for every affliction |
| GM Core 119–120, 128 | Creature/NPC bonuses and damage are authored, with PC-style NPC construction also possible | Narrative role and source subtype remain separate; do not derive authored attacks from carried gear |
| GM Core 123 | Creature focus casting may have explicit construction exceptions | Preserve creature source exceptions; PC focus rules are not a universal validator |
| GM Core 219–221 | Constant benefits, investment, activation and price/type entries are distinct | Preserve descriptions, usage, frequency and price basis; absent structured activation is not evidence of no activation |
| GM Core 232 | Reinforcing runes specifically improve shields | Source rune configuration is legitimate; do not apply weapon/armor rune assumptions to shields |
| Player Core 2 89 | Champion benefits can confer reinforcement rather than require an etched source rune | Character feature and shield source can contribute differently to an effective value |

### Discrepancies and limits

- Player Core p. 91 in this PDF describes a key-attribute boost with an increase of 2, while p. 19 defines ordinary modifier boosts as 1 with partial-boost handling. Retain both citations as a textual discrepancy; no attribute calculation/errata precedence is implemented or inferred.
- Player Core p. 274 broadly says shields cannot have runes; GM Core p. 232 specifies reinforcing runes, with related class support in Player Core 2 p. 89 and PF2e's schema. Preserve the broader text and specific additional rule; do not use the former to erase legitimate source data.
- GM Core p. 123's creature focus exceptions differ from ordinary PC use on Player Core pp. 298–299. Scope rules by actor/source context rather than enforce one universal casting model.
- All reads warn that reading order/table structure is unverified. No numeric table relationship was inferred solely from text adjacency. Sparse extraction is not proof of an empty source page. If a future feature needs precise tables or uncertain text, verify the rendered original/errata before adoption.
- System/adventure/PDF publication versions may differ. A matching name or remaster marker does not authorize replacing a custom ability with a book/compendium definition.

## Existing capability and research-claim disposition

Source inspection and Code Graph overview identified the existing world-journal readers, Python validation and RPC dispatch. Current journal references resolve world journals only, with a 20-reference fragment cap and 48,000-byte serialized response ceiling. These are reuse evidence, not defaults automatically assigned to new tools. Existing tests include `tests/test_journals.py` and `tests/js/journals.test.js`. No Actor/Item readers were found in the current tool modules; the handoff's names remain candidates.

| Original reference claims/proposals | Disposition in this map |
| --- | --- |
| Architecture/public entry points | Core extraction, embedded lookup, UUID, permission, pack and token contracts rechecked above; folder API and effective-stat gaps remain explicit |
| Actor audit | All three types have individual stories; source models rechecked, rules reread; role and unsupported-type boundaries retained |
| Ability/attack/casting/state Item audit | One story per type with pinned schema and book mappings; affliction source gap narrowed; effective availability/state gates retained |
| Identity/progression Item audit | All five source models rechecked with ancestry/background/class/deity readings; grant-link interpretation still gated |
| Physical/bundle audit | All ten types mapped with concrete source exceptions; book source gap narrowed; kit excluded from generic physical assumptions |
| Remaining declared types | campaignFeature, generic base and unknown/module types explicitly unsupported; excluded Actor types remain outside initial discovery |
| Cross-cutting translations | Attribute/rank/code/activation/resource/damage/source/reference distinctions assigned to CORE-contract and type stories; complete target-dependent math excluded |
| Identity/raw/mapped examples | Still proposed illustrations, not finalized schemas; CORE-contract owns exact defaults/continuation/error design before code |
| Recommended views | Allocated to actor checkpoints and casting/build/inventory/state joins without forcing recursive expansion |
| Recorded live observations | Preserved as October 19 observations; not converted into current API contracts, comprehensive fixtures or new passing tests |
| Verification gaps | Carried into named gates below; no source-only fallback silently closes an effective capability |
| Technical pointers | Story-specific immutable PF2e release URLs replace development-branch assumptions for new adoption; official Foundry URLs retained |

## Open verification gates

| Gate | Responsible stories | Evidence needed / safe baseline |
| --- | --- | --- |
| G-VERSION | CORE-contract, CORE-acceptance | Supported core/system matrix; v13-compatible PF2e pairing if claimed. Baseline documentary pairing is core14/PF2e8.6.1 |
| G-PC | ACT-character, CORE-build | Populated existing PC and supported effective-stat/Strike interfaces. Safe baseline: selected source/build contributions with explicit effective gaps |
| G-FAMILIAR | ACT-familiar | Existing familiar/master pair, supported derivation and missing-master behavior. Safe baseline: master link, stored HP, selected abilities |
| G-CAST | CORE-casting, ITEM-spellcastingEntry | Mode-specific persisted/live preparation, expenditure and derived pool-capacity contracts. Safe baseline: source records and unambiguous joins |
| G-STATE | CORE-state and its Item stories | Supported activity/suppression/expiry/origin behavior. Safe baseline: labelled stored records and tracked status |
| G-SPECIAL | ITEM-book, ITEM-affliction, specialized casting | Representative live data; optional formula/ritual/item/flexible interpretation remains partial. Safe baseline: verified selected source |
| G-LINKS | CORE-build, CORE-inventory, CORE-packs | Proven persisted grants/attachments/folder relationships and stale-read behavior. Safe baseline: explicit named unresolved references |
| G-WORKFLOW | CORE-acceptance | Real MCP discovery plus existing-world journal/pack/token workflows. Unit mocks alone cannot close deployment/runtime claims |

No newly tested live Actor/Item support is claimed. Do not request another installation/world/reset to close these gaps. Continue independent source work, keep partial sections visible, and close each gate only with its stated evidence.

Subsequent Build verification (October 23, 2026): the source/acquired-document
portion of G-PC and persisted grant-join portion of G-LINKS are verified for
CORE-build, ITEM-background and ITEM-feat. A marked temporary character in the
existing development world supplied populated source, selections and shared
grant claims, followed by confirmed cleanup. See
[Build verification](build-verification.md). Effective PC statistics/Strikes and
other gates above remain separate; this does not claim ACT-character complete.

## Documentation validation

October 25 familiar model gate: public ActorData.system plus the pinned
FamiliarSystemData declarations permit selected own derived data after the
existing master guard. The marked-world fixture run passed 108 MCP calls,
127 present fields (zero missing), 128 statistics records over 64 pages, six
Actor pages and 16 Item pages. Independent public-model comparisons, source
fingerprints within each phase, no derived rows after master unassignment and
exact fixture cleanup passed. Expanding this to compendium/token current fixtures
and integrated casting/state remains open; ACT-familiar is not Complete. See
[familiar current verification](familiar-current-contract.md#representative-world-verification--october-25).

October 25 declared effect-model correction: official public core ItemData.system
and pinned `EffectSystemData.expired: boolean` permit selection of the own model
data property even when `toObject(false)` omits it. New regressions fail under
the old serializer-only boundary, then pass with strict getter-free model reads.
The same existing NPC check now verifies one present false expiry flag (zero
absent), 56 records and 76 raw witnesses across 54 MCP calls, with unchanged
complete source fingerprints. This does not establish active application or
condition suppression; see [state contract](state-contract.md).

October 25 token and casting follow-up: the read-only token check scanned 50
Scenes and 778 tokens without a qualifying existing character/NPC same-base
pair with distinct HP and meaningful Item state. CORE-token remains open; see
[token verification](token-verification.md). Two existing NPC current-resource
checks passed across prepared/spontaneous/innate/focus modes: 171 retained
spellcasting pages, 1,052 records and 57 current records, plus 46 source/default
pages. Independent public serialization and unchanged complete fingerprints
passed. One documented byte-limit restart discarded 101 smaller-budget pages;
323 calls were requested and 322 completed. See
[resource verification](casting-current-contract.md#existing-npc-resource-verification--october-25).
The NPC creature supplement check also passed with 14/10 supplemental records
for world/synthetic samples. Final cast ranks, signature alternatives, complete
availability and representative character/familiar resource checks remain open.

October 25 runtime gates: genuine temporary world formula and spell books passed
40 MCP calls, 26 pages, 82 raw source witnesses, six content relationships and 48
exact description fragments. Source fingerprints and exact-marker cleanup were
confirmed. ITEM-book is Complete; total progress is 31/39 (79.5%). See
[book verification](book-verification.md) for scope and remaining effective
ownership/preparation exclusions.

Two existing NPC state views also passed 54 MCP calls, 10 state pages, 56 records,
76 raw witnesses and two resolved relationships with unchanged complete source
fingerprints. The sampled effect omitted serialized expiry (zero present, one
absent), so no current expiry value is live-verified. The verifier's source-name
versus display-name correction has a failing-then-passing offline regression.
CORE-state remains open; see [state contract](state-contract.md).

October 25 state expiry checkpoint: explicit Actor `state` reads now select an
owned effect's declared `EffectSystemData.expired` from public
`Item.toObject(false)`, with transformed provenance separate from stored duration
and timing. Deterministic tests cover false/true, absent data without source
fallback, accessors and invalid values, denied Items, strict Python DTOs and
stale continuations after transformed-only changes. Condition activity and
effect application remain unknown; the serialized expiry flag does not establish
either. Existing-world runtime verification is still pending. CORE-state and
its affliction dependency remain open; story progress remains 30/39.

October 25 casting evidence: actual complete canonical Player Core Remaster
reads added printed 99 (physical 100, 5095 characters) and reread printed
297–299 (physical 298–300, respectively 5261/5706/5273 characters), revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
Each returned `next_offset=null`. Printed 99 verifies Bard signature entitlement,
including lower-rank versions when learned above minimum; printed 298 verifies
higher-slot expenditure without higher cast rank. A persisted signature flag
alone does not establish that class feature's acquisition or legality. See
[casting verification](casting-verification.md#canonical-contextual-rank-reads--october-25-2026)
and the [proposed option contract](casting-options-contract.md). These are
rulebook reads, not new implementation or live availability evidence.

The October 20 checks passed for all 39 story files and both navigation/evidence documents, plus links from the two updated research/handoff documents:

- Exactly three Actor stories and 24 Item stories, matching the pinned declared Item types after excluding campaignFeature; 12 shared tasks.
- All local Markdown links/anchors and all cited immutable PF2e source paths resolve. Story headers, dependency tables and Mermaid agree on 42 nodes and 80 direct edges; topological traversal finds no cycle or backward stage dependency.
- Mermaid **11.12.0** parsed and rendered the complete chart in an isolated headless Chromium process; rendered output contained all 42 nodes and 80 edges. The left-to-right layout was visually inspected. Temporary renderer dependencies/artifacts stayed under `/tmp`; project dependencies were unchanged.
- Targeted Markdown whitespace checks and `git diff --check` passed. No application behavior changed, so application regression suites and live game setup were not required for this documentation change.

When editing dependencies later, compare the story prerequisite rows and integrated checkpoint lists against the index table, parse the fenced Mermaid block, check identical edge/node sets and run a cycle check before rendering. Optional relationships are not solid-arrow dependencies. Revalidate the exact three-Actor/24-Item inventory if scope changes; do not count actor integration checkpoints as new stories.
