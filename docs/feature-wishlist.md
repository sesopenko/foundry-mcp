# Feature wishlist

Feature ideas and requests with work still to do. Wishlist status does not mean
implemented or scheduled. Completed requests are in
[the finished wishlist](feature-wishlist-finished.md).

## How to maintain this wishlist

- When asked to “add to the wishlist” or record a feature idea, add it here.
  Recording a request does not authorize implementation.
- Read both wishlist files before adding an entry. Extend an existing request
  when the idea overlaps; otherwise append a new `## WISH-### — Title` entry.
  Use one more than the highest ID across both files (currently `WISH-008`);
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

## WISH-005 — On-demand explanation lookup

- **Status:** Wishlist
- **Requested:** 2026-10-28
- **Scope:** A new read-only MCP tool for retrieving explanations currently
  repeated in tool responses.

### User need

Repeated requests repeatedly consume context and tokens with the same explanatory
paragraphs. Let the LLM look up an explanation when needed instead of receiving
it on every data read.

### Desired behavior

- Move reusable disclaimers, interpretation guidance, calculation semantics,
  source-versus-current explanations, capability limitations and verification
  background into a shared explanation catalog exposed through a new MCP tool.
  Audit all tool families, including Actor/Item reads, inventory, wealth/Bulk,
  navigation and capability discovery.
- Replace repeated prose in ordinary responses with compact, stable explanation
  identifiers relevant to the requested data. Avoid returning references for
  unrequested details.
- Provide bulk lookup as the normal interface: accept an array of explanation
  IDs and return their explanations together in one tool call. Looking up
  8–15 explanations must not require 8–15 calls. Publish an example such as
  `{"ids":["<explanation-id-1>","<explanation-id-2>"]}` and document batch
  bounds large enough for at least 15 IDs. Associate every result with its ID;
  an unknown ID must not discard successful lookups for the rest of the batch.
- Make lookup discoverable from MCP tool descriptions and response schemas.
  A fresh LLM must know which tool accepts the returned identifiers, when a
  lookup is useful and how to request it without prior repository context.
- Return each explanation's identifier, text, revision and applicable runtime,
  system or feature scope. Define revision/cache semantics so an LLM can reuse
  an explanation within a conversation and recognize when it has changed.
- Keep lookup selective and bounded; do not return the entire catalog by
  default or embed its full prose in MCP discovery schemas. Handle unknown or
  obsolete identifiers with actionable errors and documented recovery.
- Retain compact result-specific facts inline: units, availability, missing or
  denied fields, partial/unsupported status, scope and continuation information.
  Their longer explanations belong in lookup. Omitting explanatory prose must
  not make incomplete data appear complete or turn unknown values into zero.

### Acceptance direction

- Publish typed requests and responses through the existing FastMCP boundary;
  validate actual discovery, invocation and identifier/revision behavior.
- Test that ordinary data responses omit catalog prose and reference only
  explanations relevant to selected data, while preserving result semantics.
- Verify a fresh client can follow returned references and retrieve the needed
  explanations, including unknown/changed identifiers. Verify actual MCP calls
  resolve batches of 8 and 15 valid IDs in one call each, with no per-ID calls;
  test mixed valid/unknown IDs and documented batch bounds.
- Measure catalog/discovery size, response bytes and call counts before and
  after for repeated reads, both with and without an initial explanation lookup.
  Include the lookup cost rather than claiming savings from smaller data reads
  alone; report provider token usage only when actually measured.

### Design decision for implementation

Choose the tool name, identifier format, catalog organization and versioning
contract during implementation. Keep explanations centralized so tool behavior,
lookup text and any concise discovery guidance remain consistent. This wishlist
entry does not implement the endpoint or change existing response contracts.
