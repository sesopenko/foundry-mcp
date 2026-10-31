# Feature wishlist

Feature ideas and requests with work still to do. Wishlist status does not mean
implemented or scheduled. Completed requests are in
[the finished wishlist](feature-wishlist-finished.md).

## How to maintain this wishlist

- When asked to “add to the wishlist” or record a feature idea, add it here.
  Recording a request does not authorize implementation.
- Read both wishlist files before adding an entry. Extend an existing request
  when the idea overlaps; otherwise append a new `## WISH-### — Title` entry.
  Use one more than the highest ID across both files (currently `WISH-009`);
  never renumber or reuse IDs, including after moving entries.
- Include **Status**, **Requested** (the request date as `YYYY-MM-DD`) and
  **Scope**, followed by the user need and desired behavior. Add acceptance
  direction, evidence or design decisions when useful. Preserve the user's
  intent and distinguish proposed behavior from verified implementation.
- Keep unfinished and partially implemented requests here. For partial work,
  state what shipped, link its contract/verification and identify what remains.
- Once the whole request is implemented and verified, record the implemented
  version and link its contract/verification, then move the complete entry to
  `feature-wishlist-finished.md` in ID order. Preserve its ID, request date,
  requirements and evidence; remove it from this file and update any links to
  its old location. Keep relative links valid in both files.
- Reopened requests return here under their existing ID, with the remaining
  work and prior implementation history explained. Keep one entry per ID across
  the two files.

## WISH-001 — Official party members and party stash

- **Status:** Partially implemented in v2.1.0: party membership; stash remains wishlist
- **Requested:** 2026-10-28
- **Scope:** Read-only party discovery and stash access, initially for PF2e.

`get_party_members` supplies bounded official world-party discovery and
membership, with canonical character follow-ups. See [party contracts and
verification](party-tools.md). Generic party Actor reads and stash access remain
unsupported.

### User need

Answer “Who's in the party?” using official party membership and read the
shared party stash through MCP tools.

The user identifies the UI entry point as the special **“The Party”** group.
Its button opens the party sheet, which lists party members and provides access
to the party stash. This is the requested UI correspondence; the underlying
supported API/schema still needs verification.

### Desired behavior

- Discover the official party and list its members with names and canonical
  Actor identifiers for follow-up reads. Membership must come from the party
  relationship, not guesses based on player ownership, logged-in users, folders,
  or scene tokens.
- Discover and read the party stash, including item names, quantities and
  identifiers for follow-up item details. Preserve stash ownership/context so
  shared possessions are distinguishable from members' personal inventories.
- Make missing parties, empty membership/stashes, inaccessible data and partial
  results distinguishable. Handle multiple parties explicitly if supported by
  the system.
- Let a fresh LLM discover the workflow from tool descriptions and returned
  follow-up selectors without opening the UI or knowing document IDs beforehand.

### Design decision for implementation

Choose existing tool extensions, new tools, or a combination based on clear LLM
discovery and efficient follow-up reading. Reuse existing Actor/Item readers
where suitable; tool names and schemas are intentionally undecided.

The previous Actor/Item delivery excluded party Actors. This request adds a new
wishlist scope; it does not imply that existing readers already support parties
or their stash. Verify supported PF2e party relationships and inventory schemas
before implementation, following the repository's public API requirements.

## WISH-009 — Read-only compendium search and reading

- **Status:** Requested; existing Actor/Item compendium index search provides a starting point
- **Requested:** 2026-10-30
- **Scope:** Discover, search and read compendium Items, supported Actor types
  and JournalEntries/pages, initially for PF2e. Compendium mutation is prohibited.

### User need

Use the established Item, Actor and journal reading capabilities to look up
compendium content: search for spells, actions and monsters, and read core PF2e
game rules stored in compendium journal entries.

### Desired behavior

- Discover relevant packs and search their supported content, returning compact
  named results with pack context, document type and canonical identifiers for
  follow-up reads. Make search scope and matching semantics explicit.
- Read selected spell and action Items, monster Actors and other supported
  Actor/Item types using the established readers where suitable. Extend journal
  navigation, search and reading to compendium JournalEntries and their pages,
  including core PF2e rules text.
- Preserve pack/document/page identity and distinguish duplicate names, empty
  results, inaccessible packs, unsupported content and incomplete searches.
  Provide bounded selective responses and continuations for complete retrieval.
- Enforce a strictly read-only compendium boundary: the agent must never be
  allowed to create, write, update or delete compendium content, or change pack
  configuration or permissions to enable such changes. Expose no mutation
  operation through these tools, even for unlocked packs or GM callers.
- Make the discover-search-read workflow usable by a fresh LLM through published
  tool contracts and returned selectors without guessed IDs or prior pack knowledge.

### Acceptance direction

Verify actual MCP discovery and end-to-end searches and reads for spells,
actions, monsters and PF2e rules journals in the existing development runtime.
Check permission boundaries, duplicate names, unsupported types, bounded
pagination and exact journal text reconstruction. Measure discovery/response
sizes and call counts under the selective-read guidance. Confirm that the
workflow leaves compendium content unchanged and exposes no compendium write
or delete capability.

Existing Actor/Item compendium index search is a starting point, not evidence
that this complete workflow is implemented. Audit current reader coverage and
public Foundry/PF2e contracts before deciding which tools need extensions;
tool names and schemas remain undecided. Recording this request authorizes
neither implementation nor compendium changes.
