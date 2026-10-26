# PF2e Actor and Item reading reference

Research date: **October 19, 2026**. Runtime examined: **Foundry 14.369,
PF2e 8.6.1**. This is a research reference and proposed presentation design,
not documentation of implemented Actor/Item MCP tools.

The **October 20, 2026 follow-up audit** is recorded in the
[story-map evidence ledger](actor-item-story-map/evidence.md). The
[development story map](actor-item-story-map/index.md) provides one story per
in-scope Actor/Item type, shared tasks, stages and a Mermaid dependency graph.
Its release-pinned schema checks narrow the book/affliction gaps below without
claiming new live verification. The October 19 observations remain historical.

The [implementation handoff](prompts/actor-reading-plan.md) records the current
scope and future build sequence. Read this reference before designing Actor,
Item or encounter-state tools. PF2e is the primary target; a multi-system
framework is not a prerequisite.

## Evidence and its limits

Use these labels when extending this document:

- **API:** documented, externally callable Foundry public API or core schema.
- **Schema:** PF2e's shipped document definitions, checked for the examined
  version. A system-specific data contract, not an assertion of cross-version
  stability for arbitrary system methods.
- **Observed:** a read-only check against the development runtime. Observation
  alone does not establish supported public API status.
- **Rules:** a passage actually read through the private PDF MCP tools.
- **Proposed:** a future MCP design requirement, not existing functionality.
- **Open:** insufficient evidence or an interface that still needs verification.

The investigation read official Foundry v14 documentation and compared key
Actor/compendium interfaces with v13 documentation. It inspected PF2e's shipped
`system.json`, `template.json` and selected schema/implementation definitions in
the installed system. Implementation inspection explained behavior; it does
not authorize adopting private members, sheet preparation, DOM structure or
undocumented prepared properties in production.

Live probes used the existing authorized development GM browser. They read
world documents, loaded selected compendium indexes/documents and compared a
token actor with its world base actor. No documents were created, imported,
modified or deleted. Compendium reads populated Foundry's browser cache only.
The probes were exploratory, not an end-to-end test of future MCP tools.

### Rulebook evidence

Page numbers here are **printed labels**, not physical PDF pages. For the
listed Player Core and GM Core passages, the observed physical page is the
printed page plus one. Rediscover document IDs with `list_pdf_documents` and
check returned labels/revisions rather than assuming that offset for other
files. Search candidates are not evidence until their pages have been read.

| Book | Pages actually read relevant to this research | Topics |
| --- | --- | --- |
| Player Core | 15, 19 | Rules notation, actions, attribute modifiers and boosts |
| Player Core | 206, 212–213, 259 | Animal companions, familiar/master abilities and pets |
| Player Core | 240, 249, 253 | Lore, general/skill feats and Battle Medicine |
| Player Core | 267, 274 | Possessions, carrying/wielding and shields |
| Player Core | 297–298, 303 | Prepared/spontaneous casting, heightening, focus/innate spells and spell format |
| Player Core | 414, 418 | Action economy, activation distinctions and Strike |
| Player Core | 430, 442 | Afflictions, condition values and overriding conditions |
| GM Core | 86, 119–120, 123, 128 | Afflictions, creature Strikes/abilities and NPC construction |
| GM Core | 219–221 | Constant benefits, investment, activation and item stat-block format |

Player Core 2 was confirmed indexed and ready but was **not read for the
October 19 Actor/Item audit**. The October 20 follow-up read its printed p. 89;
see the ledger for that limited reading and additional Player Core/GM Core pages.
Monster Core compendium documents were inspected; a Monster
Core PDF was not used. Do not attribute conclusions to unconsulted passages.
The table records relevant readings rather than claiming whole-book review.
PDF extraction has unverified reading order and table structure; numeric table
relationships were not inferred from adjacency. Store paraphrases and page
references here, not private book contents or copies of the PDFs.

## Architecture and public entry points

**API:** Foundry supplies generic Actor/Item documents. Their `type` selects a
system/module data model under `system`; core Foundry does not define one
universal monster, character sheet or spell schema.

| Concern | Public entry points | Interpretation |
| --- | --- | --- |
| World actors | `game.actors`, document `id`, `uuid`, `type`, `folder` | Actors-directory documents, including world-specific edits |
| Embedded Items | `actor.items`, `actor.itemTypes`, `getEmbeddedDocument("Item", id)` | Parent identity matters; local Item IDs are not global selectors |
| Allowed types | `Actor.TYPES`, `Item.TYPES` | Runtime discovery; allowed does not mean populated or fully supported |
| Selected source | `toObject()` | Source values by default; select allowed fields instead of returning the entire document |
| Transformed data | `toObject(false)` | Transformed serialization; not a promise to expose all effective sheet statistics or getters |
| Declared PF2e current model data | Public `Actor.system` / `Item.system` plus pinned document-data contracts | Select only specifically declared, version-verified own data fields; serialization omission does not make those fields private. Never substitute undocumented members, selected getters or sheet preparation state. See the [effect expiry boundary](actor-item-story-map/state-contract.md#source-unknown-and-unsupported-state). |
| Roll context | `getRollData()` | System-defined roll data, not a complete normalized sheet |
| Permissions | Document/pack `testUserPermission` | Explicit checks; `getUserLevel` alone does not account for all role privileges |
| Compendiums | `game.packs`, `documentName`, `collection`, `title`, `visible`, `getIndex`, `getDocument` | Index-first discovery, then hydrate selected documents without importing |
| UUID resolution | Async `foundry.utils.fromUuid`, optional originating document as `relative` | Obtain a full document; synchronous compendium resolution returns an index entry |
| Scene instances | `scene.tokens`, `token.actor`, `token.baseActor`, `actorLink`/`isLinked` | Linked world actor versus unlinked synthetic actor; do not merge deltas manually |

**Proposed:** keep Foundry API access and supported runtime calculations in the
browser. Python validates requests, joins bounded extracted records and maps
them into book terminology. It must not reproduce PF2e's combat engine or keep
a second authoritative world-state database. Unlike these browser-backed reads,
the existing private PDF tools work without a connected Foundry browser.

Compendium `contents`/`get(id)` are loaded cache contents, not proof of the full
pack. A pack editing lock is not a read prohibition. Avoid unbounded
`getDocuments()` calls. Full internal pack-folder navigation still needs its
own public API check; do not adopt an internal tree helper or publisher browser.

### Document identity and journal references

Distinguish world actor, compendium actor and scene-token actor even when names
match. An unlinked token can have different HP, Items and effects from its base.
A prototype token is not a placed token. A compendium actor is not automatically
the authoritative version of a modified adventure/world actor.

Existing `read_journal_page` extracts bounded `@UUID[...]` references, labels
and anchors but resolves only world-journal destinations. Actor/Item resolution
is proposed. Preserve source notation; resolve requested supported types, check
permissions and report broken/unsupported targets. Plain names require bounded
candidate searches, not picking the first duplicate. Relative references need
the originating document. Complete references in one returned fragment do not
establish completeness across unread fragments or other link syntaxes.

## Actor audit

Actor subtype and narrative role are separate. A `character` can represent an
NPC; an `npc` can be player-controlled. Use explicit user-character assignments
and permissions for control relationships, never the subtype alone. If user
assignment is exposed, select only the supported relationship, not whole User
documents or personal account data.

| Type | Storage versus book concept | Proposed transformation and cautions |
| --- | --- | --- |
| `character` | PC-style build model; class/ancestry/heritage/background, feats, Items, choices and rules contribute to statistics | Join current embedded documents into identity/build, attributes, proficiencies, skills, defenses, Strikes, abilities and resources. Separate available build choices/progression from choices already acquired. Source Actor fields alone are incomplete. No populated PC was live-verified. |
| `npc` | Monsters, NPCs and ordinary animals; many statistics are authored directly rather than calculated by PC construction rules | Present a creature stat block with Perception, senses, languages, skills, attributes, defenses, Speeds, Strikes, abilities and spellcasting. Preserve special notes. Do not rebuild an NPC as a PC or derive its authored attacks from equipment. Base and elite/weak/current values may differ; verify supported extraction before promising effective values. |
| `familiar` | Master-linked model; important statistics derive from the master and selected abilities rather than independent PC attributes | Preserve master identity and selected familiar/master abilities. Explain derived values and missing-master limitations. Do not fabricate attributes or ordinary Strikes. Schema and source were inspected, but no populated familiar was live-verified. |
| `hazard`, `vehicle`, `loot`, `party`, `army` | Other PF2e Actor subtypes | Explicitly excluded from initial discovery results and detail semantics. A direct reference returns an unsupported-type result rather than coercion into a creature. Historical observations of these types are not implementation scope. |
| `base` | Also appeared in the allowed type list | No supported character interpretation. Do not advertise it as a populated PF2e creature category. |

**Rules:** NPCs may be built using creature guidelines or PC-style rules; their
narrative role does not determine a single build method (GM Core p. 128).
Familiars use the pet rules with specified differences, including master-linked
statistics and daily familiar/master ability selection (Player Core pp. 212–213,
259). Animal companions have different progression, attacks, support benefits
and maneuvers (p. 206).

**Proposed:** ordinary animal, pet, familiar and animal-companion roles need
explicit evidence. The examined core type list contains no separate
`animalCompanion` type. An animal trait, ownership or creature name does not prove
companion status. No active companion/familiar-specific add-on was observed;
do not silently depend on one. Missing role evidence should remain unknown.

## Item audit: abilities, attacks, casting and state

The following field paths are relative to an Item's `system` unless stated
otherwise. They are extraction candidates for the examined version, not a
finished cross-version MCP schema. A book heading and a Foundry type are not
necessarily one-to-one. Never invoke activation, roll, casting or grant/import
methods just to read an Item.

| Type | Schema/observed representation | Book-oriented transformation |
| --- | --- | --- |
| `melee` | NPC attack record: `bonus.value`, `damageRolls`, `traits.value`, `range`, `attackEffects.value`; examined schema also defines `action`, `area`, `subjectToMAP` | Label qualifying attack-mode records **Strikes**, with melee/ranged distinguished from the type name. Retain each damage component, damage type/category, range information, traits and additional effects. Not every declared attack mode has been sampled. Additional-effect strings are not necessarily UUIDs or full definitions. Never reconstruct authored NPC attack math from carried weapons. |
| `action` | `actionType.value`, `actions.value`, category, description, optional frequency and `selfEffect` | Present abilities as action/activity, reaction, free action or passive. Null action count is not proof of a free action. Familiar abilities also use this type. Preserve trigger, requirements, frequency and exceptions from descriptions; structured fields are not complete rules. Link a self-effect without activating it. |
| `feat` | Category, `level.value`, optional `level.taken`, prerequisites, activation fields, description, rules, subfeatures, grants/selection relationships | Distinguish actual feats, ancestry features, class features and other categories. Feat level differs from acquired-at level. Present selected benefits and linked abilities without treating every feature as a chosen feat or every future grant as acquired. Prerequisite strings are evidence, not an implemented eligibility checker. |
| `spell` | `level.value`, `traits.traditions`, `time.value`, range/target/area, defense, duration, damage, description, heightening/overlays; actor context in `location` | Translate spell level to **rank** only in this context. Separate base definition from casting options/ranks/variants. Preserve variable casting times, save versus spell-attack mechanics, damage versus healing, sustained duration and heightened text. A spell record alone does not prove castability or current resources. |
| `spellcastingEntry` | Tradition, `prepared.value` casting mode, ability/proficiency, `spelldc`, rank-keyed slots, optional heightening configuration | Present a **spellcasting group**, not an unexplained inventory Item. Join spells through `spell.location.value` to the owning entry ID. Interpret prepared, spontaneous, innate, focus and other supported modes separately. Prepared uses, shared slots, individual uses and focus resources cannot be flattened into one remaining-spells counter. |
| `lore` | Separate Item with proficiency or modifier data; source inspection distinguishes PC `proficient.value` from NPC `mod.value` contributions | Merge into Skills while retaining the Item identity. Display the specialty separately and distinguish proficiency from final modifier. Do not assume a PC Lore source value is a complete check modifier. |
| `condition` | Valued/unvalued state, persistent damage, parent/child references and override relationships | Present named condition and value, with supported active/suppressed state and origin. Persistent damage needs formula/type/recovery details. Stored presence does not establish active application. Suppressed is not removed; duration can continue while suppressed. Complete effective-state extraction remains open. |
| `effect` | Description/rules, duration, start time, badge, context, unidentified flag and optional spell origin | Present current benefits/penalties or tracking effects with origins. A badge can have several meanings; do not automatically call it a condition value or remaining uses. Preserve duration unit, expiry timing and sustained state. Do not count an automation effect as another learned ability. |
| `affliction` | October 20 pinned 8.6.1 schema check established `save`, `status`, `onset`, `stages`, `duration`, `start` and `context`; no representative live record verified | Separate recorded status from stage definitions: `status.stage` is one-based and `stages` is zero-based. Expose selected source without inventing recovery, expiry or complete current application. See [affliction story](actor-item-story-map/stories/ITEM-affliction.md). |

**Rules:** actions and activities can be granted through feats, spells and magic
items, not only action Items (Player Core pp. 15, 414). Strike is distinct from
other attacks (p. 418). NPC attack bonuses and damage are authored under creature
guidelines (GM Core pp. 119–120). Conditions can override others without removing
them (Player Core p. 442); afflictions have onset/stage/duration semantics (p. 430).

### Casting joins and resource interpretation

Observed spell `location` keys included `value`, `heightenedLevel` and `uses`.
The first joins to an embedded spellcasting entry; it is not a global UUID.
Prepared slot records can reference an embedded spell ID. Resolve these within
the same actor/token context and retain unresolved relationships explicitly.

| Book concept | Proposed presentation requirement |
| --- | --- |
| Prepared casting | Separate known/listed spells from actual prepared uses by rank; repeated preparations can reference the same spell. Read expenditure through a verified current contract, not the generic slot counter alone. |
| Spontaneous casting | Repertoire and remaining shared slots are separate. Heightened-rank access and signature-spell exceptions need evidence. |
| Innate casting | Preserve individual uses and special at-will/constant restrictions where established; no universal slot interpretation. |
| Focus casting | Link focus spells to the actor's focus pool and casting group. Pool capacity is not a per-spell daily use count. |
| Cantrips | Distinguish unlimited slot-free casting from absence of a resource field; automatic heightening does not change the stored base definition. |
| Slot rank versus casting rank | Player Core p. 298 permits a spontaneous caster to spend a higher-rank slot without heightening a spell. Preserve base rank, slot rank and casting rank separately; never infer heightening from slot rank alone. |
| Rituals, item casting and flexible preparation | Preserve the identified mode and source; complete specialized handling has not been verified. Do not force these into ordinary prepared/spontaneous behavior. |

Player Core pp. 297–298 distinguish preparations, repertoires, heightening,
cantrips, focus and innate casting; p. 303 explains spell stat-block fields and
spell attacks. GM Core p. 123 gives creature-specific guidance and can differ
from ordinary PC construction. Keep creature exceptions attached to their source.

A live prepared entry had a generic slot `value` of zero while containing
prepared spells. Another probe encountered mixed object/string preparation
values; the investigation's initial assumption that every value was an object
failed. This is evidence of a parsing/legacy-data concern, not a validated
expended-slot contract. Report unknown/partial availability rather than treating
these values as exhausted or rewriting game data to make them uniform.

### Ability completeness and automation

Basic actions are generally available by the rules and need not be embedded on
every actor. Equipment activations can exist only in prose. Features can grant
abilities, and rule elements can affect statistics or create runtime options.
An embedded Item list is therefore not an exhaustive list of usable actions.

Battle Medicine illustrated the split: prerequisites and one-action cost were
structured, while toolkit requirements, Treat Wounds references and target
immunity were in descriptive HTML. Preserve both representations and dependencies
(Player Core p. 253). Never derive completeness from missing structured fields.

## Item audit: identity, faith and progression

| Type | Schema/observed representation | Book-oriented transformation |
| --- | --- | --- |
| `ancestry` | Boost/flaw choices, HP, size, Speed, senses, languages and feature references in `items` | Present ancestry identity, choices and benefits together. Distinguish offered choices, selected values and actual embedded grants. An ancestry HP contribution is not actor maximum HP. |
| `heritage` | Description/rules/traits and optional ancestry association | Present alongside ancestry as a separate selection. Do not assume every heritage is ancestry-exclusive or coerce a versatile heritage into one ancestry. |
| `background` | Boost choices, `trainedSkills`, Lore and feature references | Present the background benefit package and selected choices. Join its skill feat/Lore where supported without double-counting granted documents. |
| `class` | Key attribute, HP contribution, proficiency/skill definitions, advancement schedules and level-gated feature references | Separate class definition/progression from this actor's acquired features and effective statistics. Future class grants are not currently owned abilities. Class HP is not total HP. |
| `deity` | Faith-related domains, font, attributes/skills, favored weapons, spells, sanctification and description | Present religious affiliation and granted options, not a deity creature stat block. Associated spells are not necessarily known or prepared; associations do not prove a particular class benefit is active. |

Player Core p. 19 distinguishes ancestry/background/class contributions from
final attributes. These Items are reading dependencies even if creating or
advancing characters remains outside scope. The inspected class-feature pack
also contained non-Player-Core categories, so pack membership is not proof of a
specific book, role or edition.

## Item audit: physical possessions and bundles

Common physical data in the examined version includes quantity, level, Bulk,
price, equipped/carrying state, container, material, identification, HP and
description/rules. Fields can be placeholders or inapplicable. Do not interpret
every zero-valued field as a confirmed usable object statistic.

| Type | Schema/observed representation | Book-oriented transformation |
| --- | --- | --- |
| `weapon` | Category/group, base damage, traits, runes, material, hands, range/reload and equipment state | Present weapon definition and instance configuration, with supported Strike links separately. Base damage is not final PC Strike damage. NPC authored attacks remain separate even when a matching weapon is carried. |
| `armor` | AC contribution, category, Dexterity cap, Strength requirement, penalties, runes and worn/invested state | Present armor properties separately from final actor AC/saves/Speed. Requirement and penalty interpretation must preserve the actor's context. |
| `shield` | AC bonus, HP, Hardness, runes and physical state | Distinguish held, raised, damaged/broken and ability to Shield Block. Possession is not an active AC bonus. Link shield attacks/attachments separately where supported. |
| `equipment` | General physical gear and magical items; usage/benefits/activation can be in prose | Present mundane usage, constant benefits, investment and activation requirements. Absence of structured activation data does not prove no activation exists. |
| `consumable` | Category, quantity, uses, damage, usage and optional contained spell data | Preserve category-specific behavior for potions, poisons, scrolls and others. Quantity, per-object uses and frequency are different. A generic scroll template can have no specific spell attached; report that instead of inventing one. |
| `ammo` | Separate physical type with quantity, uses and special effects | Present ammunition, consumption and special rules. Selected ammunition/weapon relationships need explicit evidence. Do not automatically append every carried ammunition effect to every ranged attack. |
| `backpack` | Container data, capacity, ignored/held-or-stowed Bulk, stowing and usage | Present containers and contents using parent relationships, not the literal word backpack. Avoid duplicate contents or naive total-Bulk calculations that ignore container rules. |
| `book` | October 20 pinned 8.6.1 definition verifies formula/spell category, capacity and Item-UUID contents | Present supported book contents without interpreting them as prepared/known spells. This is not the private PDF library. No representative live Item was verified; see [book story](actor-item-story-map/stories/ITEM-book.md). |
| `kit` | Bundle definition with nested component UUIDs, quantities and container relationships | Present a bundle definition, not one ordinary possession. Reading must not import/expand it into inventory. Do not count both a kit and its generated contents as owned equipment. |
| `treasure` | Coins, gems, art objects/materials and associated quantity/value data | Include character valuables despite excluding loot Actors. Preserve unit/stack value semantics and denominations; normalize only when that basis is established. Do not multiply a value twice or silently infer a sale price. |

**Rules:** carrying, holding, wearing, stowing and wielding are distinct (Player
Core p. 267). Shield AC benefits require the relevant action/state, not merely
ownership (p. 274). Constant benefits, investment and activation are distinct
(GM Core pp. 219–220); item level, usage, activation, variants and crafting
requirements have separate meanings (p. 221). An item above the actor's level
is not automatically unusable. Preserve book-specific exceptions.

### Remaining declared types

`campaignFeature` described Kingmaker campaign features in the inspected
schema, including campaign activities/features rather than ordinary character
feats. Exclude its specialized interpretation from the initial tools and report
it explicitly if encountered. `base` is a generic allowed Item type without an
established book interpretation. Unknown future/module-defined types must remain
explicitly unsupported rather than being silently classified as equipment.

## Cross-cutting translation requirements

| Raw concept | Proposed mapped presentation | Safeguard |
| --- | --- | --- |
| `abilities`/`str`/`dex` and related keys | Named attribute modifiers | Do not reconstruct obsolete attribute scores or assume every creature uses independent attributes |
| Numeric proficiency rank | Untrained/trained/expert/master/legendary | Keep rank separate from the total check modifier and level contribution |
| Spell `level` | Spell rank | Do not relabel actor, feat or item level as rank |
| Action type/count | Action/activity, reaction, free action or passive | Preserve variable/long casting times and requirements; null is not zero |
| Trait slugs, abbreviated sizes and other codes | Readable labels plus original codes | Preserve unknown/custom values and use a verified label source; do not drop unrecognized traits |
| Generic `value`, `max`, badge and frequency fields | Meaningful, mode-specific resources | Absent, untracked, inapplicable and exhausted are distinct states |
| Damage data | Components with formula, type, category and damage/healing meaning | No universal flattening or unsupported target-dependent total |
| Source and transformed values | Base/source versus effective/current | State the extraction basis; serialization alone does not establish complete calculation support |
| Document references | Named, typed links with canonical selectors | Parent/pack/token context must survive every join |
| Source HTML and inline notation | Exact bounded source plus optional derived readable text/references | Never execute rolls, enrichers, macros or activation to render a read response |
| Publication/older terminology | Source/edition metadata and searchable aliases where justified | Do not silently rewrite mechanics to match the uploaded PDF or newest system |

Conditions, equipment, feats and rule elements can alter statistics conditionally.
The same source can participate in several mapped views: a feat grants an
ability, an effect tracks its use, and another rule modifies a statistic. Keep
those relationships rather than duplicating them as unrelated powers.

The installed system, imported adventure documents and PDFs can reflect
different errata or editions. A `remaster` marker or publication title is useful
provenance, not proof of precedence or complete agreement. Never use a matching
name alone to replace an actor's custom ability with a compendium/book version.

## Proposed response design: identity, raw and mapped data

The LLM needs readable game concepts **and** canonical entity selectors for
future tools. Retain both instead of replacing source identities with labels.
The following is a design direction; exact tool schemas, view defaults, bounds,
continuations and mutation interfaces are not finalized.

1. **Identity:** document name/subtype, local ID, UUID, owner/parent, source
   kind and relevant pack/scene/token/base-actor selectors. Include core/system
   versions and enough instance/world context to avoid cross-session confusion.
2. **Raw:** explicitly selected primitive fields under their original paths,
   with an extraction basis such as source or transformed serialization. This
   is not an unrestricted `toObject` dump. Exclude secrets, unrelated flags,
   migration records and internal state. State omitted/partial sections.
3. **Mapped:** book-oriented sections and terminology, with references to
   contributing document UUIDs and raw paths. Preserve original codes alongside
   display labels. Joins/derived concepts may have multiple contributors.
4. **Provenance/completeness:** distinguish direct fields, deterministic
   translation, joined relationships and supported calculated values. Explain
   missing data, unknown semantics, stale reads and unsupported calculations.

A mapped Strike, spellcasting option or combined statistic may not be a
persisted document. Do not invent a Foundry UUID for it. Any local response key
is only a response identifier and must be labelled as such. Distinguish graph
references from executable write selectors.

### Illustrative spell and casting relationship

All identifiers/numbers below are fictional placeholders. These snippets are
illustrations, not implemented response schemas or complete document exports.

```json
{
  "identity": {
    "uuid": "Actor.AAAAAAAAAAAAAAAA.Item.BBBBBBBBBBBBBBBB",
    "id": "BBBBBBBBBBBBBBBB",
    "document_name": "Item",
    "type": "spell",
    "parent_uuid": "Actor.AAAAAAAAAAAAAAAA",
    "source_kind": "world"
  },
  "raw": {
    "basis": "source",
    "fields": {
      "system.level.value": 3,
      "system.location.value": "CCCCCCCCCCCCCCCC"
    }
  },
  "mapped": {
    "base_rank": 3,
    "spellcasting_entry_uuid": "Actor.AAAAAAAAAAAAAAAA.Item.CCCCCCCCCCCCCCCC",
    "casting_rank": null,
    "availability": "not_evaluated"
  },
  "mapping": [
    {"output": "mapped.base_rank", "source": "system.level.value", "operation": "spell_level_to_rank"},
    {"output": "mapped.spellcasting_entry_uuid", "source": "system.location.value", "operation": "resolve_embedded_entry_in_same_actor"}
  ]
}
```

The entry UUID is returned only after verifying the referenced Item exists and
has the expected type. An unresolved reference remains explicit. Casting rank
and availability require additional contextual evidence; a base rank is not an
assertion that this actor can currently cast the spell at that rank.

### Illustrative embedded ability

```json
{
  "identity": {
    "uuid": "Actor.AAAAAAAAAAAAAAAA.Item.DDDDDDDDDDDDDDDD",
    "type": "action",
    "parent_uuid": "Actor.AAAAAAAAAAAAAAAA"
  },
  "raw": {
    "basis": "source",
    "fields": {
      "system.actionType.value": "reaction",
      "system.actions.value": null
    }
  },
  "mapped": {
    "activation": {"kind": "reaction", "action_count": null},
    "trigger": {"status": "requires_description_read"}
  }
}
```

The null count does not mean a free action, and trigger absence in the selected
fields does not mean no trigger. Source HTML and its continuation must remain
available to read the complete ability.

### Illustrative token-specific identity

```json
{
  "identity": {
    "source_kind": "token",
    "scene_uuid": "Scene.EEEEEEEEEEEEEEEE",
    "token_uuid": "Scene.EEEEEEEEEEEEEEEE.Token.FFFFFFFFFFFFFFFF",
    "actor_uuid": "Scene.EEEEEEEEEEEEEEEE.Token.FFFFFFFFFFFFFFFF.Actor.AAAAAAAAAAAAAAAA",
    "base_actor_uuid": "Actor.AAAAAAAAAAAAAAAA",
    "linked": false
  },
  "raw": {"basis": "source", "fields": {"system.attributes.hp.value": 7}},
  "mapped": {"hit_points": {"current": 7}}
}
```

Here the selected field belongs to the resolved token actor. It must not be
silently relabelled as base-actor data. An Item on this actor must likewise keep
its actual instance UUID rather than assuming a world-parent UUID.

### Future mutation compatibility

Future write tools should accept canonical supported selectors, re-resolve the
target, check current permissions and validate current state/revision. They
must distinguish world, compendium and token targets and reject unsupported
writes. Read-derived labels, response keys and mapped paths are not writable
Foundry paths, and raw snapshots must not become unrestricted patch requests.
Document IDs are valid in their current context, not permanent identities across
deletion, recreation, import or world changes. Mutation design is future work;
this reference does not authorize or define write operations.

## Recommended book-oriented reading views

Keep discovery recognizable from Foundry: world folders, named actors, packs
and scene tokens. Detail responses should organize around the game:

- Identity/build and character or creature overview.
- Attributes, defenses, Perception/senses, movement and skills including Lore.
- Strikes, with source weapons/attacks and calculation limitations.
- Actions, reactions, free actions, passive abilities, feats and features.
- Spellcasting groups, spell definitions/options and mode-specific resources.
- Equipment, valuables, containment and use/investment state.
- Conditions/current effects with supported origins, suppression and duration.

Each mapped entry retains its contributing entity references. Avoid unlimited
recursive expansion. Return next useful readers and named references, supported
sections, count/byte limits and continuations. Search matches are candidates,
not evidence that full ability text was read. Keep unsupported versus empty
versus incomplete distinct. These are proposed views, not new MCP tool names.

## Recorded live observations

These are a dated development snapshot, not fixture expectations or public
campaign exports. No private actor names/IDs or book filesystem paths are needed.

- 280 world actors: 172 NPCs, 89 loot, 18 hazards and one party. No populated
  character/familiar was available for live completeness checks.
- Allowed Actor types: `base`, `army`, `familiar`, `hazard`, `loot`, `party`,
  `vehicle`, `character`, `npc`.
- 68 Actor compendiums. Monster Core's requested index had 492 entries and
  fields `_id`, `img`, `name`, `type`, `uuid`. One hydrated NPC exposed 15 spells,
  one casting entry, three attack Items, 12 actions and two Lore Items. Async
  UUID resolution returned the same hydrated actor without importing it.
- World journal source contained 246 explicit world-Actor UUID references and
  other compendium references. Not every compendium reference was classified.
- A sampled unlinked token had a synthetic actor distinct from its base. Both
  linked and unlinked tokens existed.
- On in-scope world actors: 202 `melee` Items, including 27 ranged records;
  557 action Items (320 passive, 197 action, 34 reaction, six free); 791 spells;
  85 casting entries; 61 weapons; 29 equipment Items; and other physical/state
  Items. No embedded feat Items occurred in this sampled actor population.
- Of those spells, 771 linked to existing casting entries and 20 had no assigned
  entry; no nonempty missing-entry reference was found in that probe. This does
  not establish castability for any of them.
- Prepared, spontaneous, innate and focus entries were observed. Complete
  expenditure interpretation was not established.
- Selected packs showed 117 familiar abilities as `action:familiar`, 55 ancestry
  features as `feat:ancestryfeature`, and 862 class-feature entries as
  `feat:classfeature`; the class-feature pack also included 18 `feat:calling`
  entries and an equipment entry. Pack title is not a type/content guarantee.
- A kit referenced nested physical components. A generic sixth-rank scroll
  template had no contained spell. No book Item occurred in the sampled
  equipment index. These are sample findings, not global absence claims.

## Verification gaps and follow-up

| Open area | Required evidence before claiming full support |
| --- | --- |
| PC statistics and Strikes | Existing populated character fixture plus public/supported effective-stat interfaces; source weapons alone are insufficient |
| Familiar statistics/abilities | Existing populated familiar/master pair; verify dependencies and missing-master behavior without adopting preparation internals |
| Animal companion/pet role | Explicit supported relationship/content evidence; no inference from name, animal trait or ownership |
| Casting resources | Current supported prepared-use, innate/focus/spontaneous contracts and legacy-data handling; no generic slot-counter fallback |
| Conditions/effects | Supported activity/suppression/expiry interfaces, overlapping origins and duration semantics |
| Specialized Items | Representative book/affliction data and specialized ritual/item-casting support where implemented |
| Core compatibility | Key APIs were checked in v13 docs, but live research was v14 only; do not claim live v13 coverage |
| API status | Pin source/schema references to the implemented version; generated docs, upstream development branches and runtime exploration alone do not prove stability/public visibility |
| Pack hierarchy/freshness | Verify public folder access and scoped revision/continuation behavior; do not substitute cache contents for complete discovery |
| Full workflow | Future journal → actor → ability/spell MCP discovery and reads, including bounds/errors and mutation-safe identity preservation |

Prefer focused deterministic tests and small live checks using existing
instances. Do not create a new Foundry world/instance for convenience. These
gaps are not reasons to hide safe source data, but responses must not present
partial interpretations as complete effective game state.

## Primary technical references

For new implementation dependencies, prefer the immutable PF2e 8.6.1 sources
and fresh official API reads in the [follow-up evidence ledger](actor-item-story-map/evidence.md).
That audit also records the core14/PF2e8.6.1 compatibility boundary, source versus
derived field distinctions, shield reinforcing-rune context and book-text
discrepancies. It does not close the live verification gaps above.

- [Foundry public/private API guidance](https://foundryvtt.com/api/v14/)
- [Actor v14](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html),
  [Actor v13](https://foundryvtt.com/api/v13/classes/foundry.documents.Actor.html)
- [Actor schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorData.html)
- [Item API](https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html),
  [Item schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ItemData.html)
- [Scene schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.SceneData.html),
  [Folder schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html),
  [User schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.UserData.html)
- [TokenDocument](https://foundryvtt.com/api/v14/classes/foundry.documents.TokenDocument.html)
- [CompendiumCollection v14](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html),
  [v13](https://foundryvtt.com/api/v13/classes/foundry.documents.collections.CompendiumCollection.html)
- [fromUuid](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html),
  [fromUuidSync](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuidSync.html)
- [Foundry system data models](https://foundryvtt.com/article/system-data-models/)
- [PF2e upstream](https://github.com/foundryvtt/pf2e),
  [rule-element documentation](https://github.com/foundryvtt/pf2e/wiki/Quickstart-guide-for-rule-elements)
- [PF2e 8.6.1 feat schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts),
  [NPC attack schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/melee/data.ts),
  [casting-entry data](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts)
  pin the release-specific schema evidence; they do not establish future
  compatibility or authorize private/prepared system interfaces.

Keep book citations independent of these technical references. The rules explain
mechanics; the API/schema evidence explains how the installed system represents
them. Neither proves the other's exact current implementation.
