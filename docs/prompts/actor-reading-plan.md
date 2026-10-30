# PF2e character and creature reading: implementation handoff

**Archived October 28, 2026.** Historical planning context for the
[archived Actor/Item tracker](../actor-item-story-map/index.md), not active work
in progress. The proposal and sequencing statements below reflect their original
date; consult [Actor/Item contracts](../actor-tools.md) for delivered behavior.

Updated October 19, 2026. **Status: proposed functionality; not implemented.**
This handoff preserves the direction for a future build task. The current work
only records research; it does not authorize implementing or releasing tools.

Read the [detailed Actor/Item reference](../pf2e-actor-item-reference.md) first.
It is the source of truth for the type-by-type audit, technical/rulebook
references, dated observations, transformation requirements and verification gaps.
Follow AGENTS.md and its required readings before implementation.

The [archived development story map](../actor-item-story-map/index.md) supplies the historical
staged backlog, individual Actor/Item stories and authoritative dependency graph.
Use its [October 20 evidence ledger](../actor-item-story-map/evidence.md) for
release-pinned schema checks, actual additional rulebook reads, corrections and
remaining evidence gates. This handoff preserves overall intent; the story map
records the former task sequencing and tracking. Neither artifact defines active work.

## Goal and agreed scope

Later delivery note (October 28): [character wealth/Bulk](../character-inventory-metrics.md)
uses a user-authorized exception to the API-evidence requirement with guarded
runtime reads and explicit potentially missing fields. Earlier gates below
remain historical research, not a prohibition on that scoped implementation.

Enable a fresh GM-trusted MCP client to follow actor references in journals,
find characters/creatures in world folders or compendiums, and read their
statistics, abilities, equipment, spells and supported current encounter state.
Responses should use PF2e book concepts while retaining source data and canonical
identifiers so future tools can resolve the same entities.

- Target PF2e directly. Supported system APIs and document schemas are allowed;
  a multi-system abstraction framework is not required first. The companion
  manifest now declares the PF2e system restriction in the working tree; that
  edit is not evidence of a published release or installed module update.
- Initial Actor subtypes: **`character`, `npc`, `familiar`**. Monsters, ordinary
  NPCs and animals commonly use `npc`. Player assignment is a separate fact.
  Pet/animal-companion roles require explicit evidence, not ownership/name alone.
- Exclude **hazard, vehicle, loot, party and army Actors**, plus generic/unknown
  types without supported character semantics. Exclude them from scoped actor
  search results; direct references must explain the unsupported type.
- Include relevant embedded Items and dependencies: attacks, actions, feats,
  equipment, spells, casting entries, ancestry/heritage/background/class/deity,
  Lore and supported conditions/effects. Character valuables remain relevant:
  excluding loot Actors does not exclude treasure Items.
- `campaignFeature` specialized semantics are outside the initial interpretation.
  The declared `book`/`affliction` types and specialized casting modes need further
  evidence; describe partial/unsupported interpretation explicitly.
- Keep initial tools read-only: no imports, activation, rolls, chat messages,
  character advancement, document creation/updates or combat automation.

## Architecture and identity

Use the existing Python MCP → authenticated GM WebSocket → ready Foundry browser
architecture. Foundry remains authoritative. Browser handlers extract supported
fields/relationships and perform only supported runtime calculations; Python
validates, joins bounded snapshots and translates presentation. Do not create a
second PF2e combat engine or persistent world-state cache. Browser-backed reads
must report disconnection; existing Python-local PDF retrieval is independent.

Preserve three distinct sources: world Actor, compendium Actor and scene-token
Actor. Use public `token.actor` for current linked/synthetic state and retain
base actor identity separately. Never silently substitute a template or bestiary
record for a requested encounter instance. Discover packs through indexes and
hydrate selected documents without importing or loading all packs.

Journal readers already return bounded UUID references but currently resolve
only world-journal targets. Extend typed Actor/Item follow-up information while
preserving exact source and existing continuation behavior. Resolve relative
references against the originating document and use async UUID resolution for
full compendium documents. Plain-name mentions return candidates with context;
never pick the first duplicate as established identity.

Use existing GM-trusted MCP authorization and explicit document/pack permission
checks. Hidden creature statistics and private biography are GM data. Client role
claims are not authorization. Do not expose these views through player routes.

## Proposed discovery and reading interfaces

The names below are design candidates, not registered tools or finalized schemas.
Keep world and compendium discovery explicit, consistent with the separate
[compendium-journal plan](read-compendium-packs.md). Its older journal-only scope
is not an actor implementation or a ban on this future actor work.

| Candidate tool | Responsibility |
| --- | --- |
| `get_actor_types` | Core/system versions, allowed versus supported types, supported sections and limitations |
| `get_actor_tree` | Actor folders, unfiled entries, empty folders, names/types and canonical selectors |
| `search_actors` | Bounded world name/type/folder search with duplicate-name candidates |
| `list_actor_compendiums` | Actor pack identities/titles, supported directory context and accessibility |
| `search_compendium_actors` | Explicitly scoped index search with searched, failed and incomplete scopes |
| `read_actor` | Selected identity/statistics/abilities/equipment/spellcasting/state views for a canonical actor selector |
| `list_actor_items` | Bounded embedded Item identities/types and useful named relationships |
| `read_item` | Selected world/compendium/embedded Item source and mapped interpretation |
| `list_scene_actors` | Scene/token discovery and linked/synthetic/base-actor relationships |

A selected token must have an explicit current-actor reading path. Whether this
uses `read_actor` with typed selectors or a dedicated reader remains a schema
choice to finalize before implementation. Item-pack lookup should share internal
pack plumbing while keeping source/type scope visible to the caller.

Book-oriented detail views should cover identity/build; attributes/defenses;
Perception/senses/movement/skills; Strikes; activated/passive abilities and
feats/features; spellcasting groups/options/resources; equipment/valuables;
and supported conditions/current effects. Each view retains underlying entities.
Embedded Item enumeration alone cannot claim all possible actions are covered.

## Raw and mapped response direction

Provide complementary **identity, selected raw fields, mapped data and
provenance/completeness**, following the examples in the detailed reference.
The intent is to make both representations available; exact view defaults and
response schemas are still to be finalized.

- Retain canonical UUIDs, local IDs, document/subtype names, owning actors,
  pack/scene/token/base-actor relationships and runtime/source context.
- Raw means explicitly selected source paths/primitive values with an extraction
  basis, not unrestricted document/flag/internal-state dumps. Distinguish source
  fields from supported effective values; include original descriptive source.
- Mapped entries use book terminology, preserve original codes where useful and
  link to contributing documents/fields. Joined concepts can have several
  contributors and may have no persisted document identity of their own.
- Never invent a Foundry UUID for a generated Strike/spell option/statistic.
  Labels, mapped field paths and local response keys are not write selectors.
- Future mutation tools must re-resolve canonical targets, check current
  authorization/state and distinguish world/compendium/token contexts. This
  task does not define or authorize mutation tools or arbitrary raw patches.
- Bound response counts, UTF-8 bytes and source expansions separately. Use
  returned continuations tied to query/source/revision, and explain stale reads,
  partial/unsupported sections and missing relationships. Do not invent default
  zeroes or claim unsupported calculations are complete.

Finalize exact selectors, default sections/views, bounds, field names,
continuations, revision semantics and tool descriptions before coding. These are
open interface decisions, not facts discovered from the runtime.

## Implementation sequence for a later authorized build

1. Finalize contracts from the research; audit each adopted API/schema field for
   the supported Foundry/PF2e versions. Add `PF2e-specific` docstrings/JSDoc and
   inline annotations recording dependencies, assumptions and version evidence.
2. Establish baseline tests, then implement world discovery, selected Actor/Item
   reading, identity preservation and journal reference integration.
3. Add scoped Actor/Item compendium discovery and lazy hydration. Verify folder
   API support rather than using internal trees or publisher browsers.
4. Implement book-oriented PF2e sections and their joins. Keep authored NPC
   attacks separate from equipment; distinguish features from feats and source
   spells from casting options. Verify public effective-stat interfaces before
   claiming complete PC Strikes or calculated current statistics.
5. Add scene/token-current reading with instance-correct embedded selectors.
   Verify master-linked familiar behavior and supported companion-role evidence.
6. Validate actual MCP discovery descriptions and schemas with a fresh client.
   Add user-facing contract/architecture documentation and update README/Docker
   Hub overview when functionality actually changes. A later release needs
   separate authorization and the repository release workflow.

## Verification and acceptance

Use focused Python/JS tests for identity/provenance, duplicate names, unsupported
Actors/Items/systems, permissions, disconnects, UUID kinds, missing relationships,
source-versus-mapped values, bounded reads, stale continuations and partial pack
failures. Cover every implemented translation using representative fixtures.

Mechanics-specific cases must include passive versus free/reaction activation;
NPC ranged attacks stored as `melee`; class/ancestry features stored as `feat`;
Lore in the Skills view; base versus cast spell rank; mode-specific resources;
source weapons versus effective Strikes; inventory containment; and condition
presence versus supported active/suppressed state. Assert no imports, rolls,
activation or writes occur.

Use small live checks in the existing development instance for journal → actor →
ability/spell, compendium versus world identity, and linked/unlinked token state.
Do not provision another instance or reset worlds. No populated PC/familiar was
live-verified during research; use existing suitable fixtures or record the gap.
Live v13 compatibility, complete resource expenditure and some effective-state
APIs remain unverified, as detailed in the reference.

For a later code change, run focused tests during development and the full
`./scripts/test.sh` before committing. Commits containing only staged `.md`
paths need link/example/consistency and whitespace checks, without local tests
or confirmation; both rename paths must qualify. Unstaged files do not affect
the exception. See [the commit hook policy](../../README.md#unit-tests-and-commit-hook).

Success is a fresh LLM discovering the correct entity, reading supported source
and mapped concepts, following dependencies and retaining canonical identities,
while distinguishing verified mechanics/current state from partial evidence.
