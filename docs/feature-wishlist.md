# Feature wishlist

Requests collected for future work. Wishlist status does not mean implemented
or scheduled. Append subsequent requests with stable `WISH-###` identifiers.

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

## WISH-002 — Character carried Bulk and encumbrance

- **Status:** Implemented in v2.2.0
- **Requested:** 2026-10-28
- **Scope:** Read-only character Bulk and encumbrance, initially for PF2e.

The user authorized a scoped API-evidence exception on October 28, requiring
defensive getter access and explicit potentially missing fields. See the
[implemented contract and verification](character-inventory-metrics.md).

### User need

Answer “How much Bulk is this character carrying, and where are they relative
to their encumbrance threshold?” through MCP tools.

### Desired behavior

- Report the character's total carried Bulk with clear units, including light
  Bulk where applicable.
- Report the character's encumbrance threshold and maximum carrying limit,
  and clearly describe their current position relative to those limits,
  including whether the encumbrance threshold has been crossed.
- Preserve character identity and provide useful follow-up access to inventory
  and contributing items when the LLM needs to explain the load.
- Account for supported system handling of quantities, containers and character
  adjustments. Do not present a naive sum of item Bulk as an authoritative
  character total. Distinguish unavailable or partial results from zero Bulk.

### Design decision for implementation

Choose an existing Actor/inventory tool extension, a new tool, or a combination
based on clear LLM discovery and efficient answers to carrying-capacity questions.
Tool names and schemas remain undecided.

Existing inventory source reading does not establish current total Bulk or
encumbrance support. Verify the supported PF2e interfaces and precise threshold
semantics before implementation; document source versus derived values and
relevant version constraints.

## WISH-003 — À la carte detail requests with typed contracts

- **Status:** Implemented in version 2.0.0
- **Requested:** 2026-10-28
- **Scope:** Reduce LLM context consumption for heavy read-only MCP responses,
  including Actor/Item details, capability/compendium discovery, journals and PDF search.

Implementation, migration, exact selections and measured live results are in
[the selective-read guide](selective-reads.md). Typed requests and responses are
limited to the nine à la carte interfaces. Defaults return minimal responses.

### User need

Let the LLM request exactly the game information needed, such as a character's
AC or prepared spells, without retrieving broad sections and paging through
unrelated fields. Use **Pydantic with the existing FastMCP boundary** so input
shape and constraint validation happens at the tool boundary rather than through
large handwritten validation blocks inside tool function bodies.

### Evidence motivating the request

The shared LibreChat conversation examined on October 28 contained 53 tool calls
with 583,395 bytes of stored outputs. These are payload measurements, not billed
tokens or a measurement of provider TPM accounting.

| Heavy workflow/tool | Observed output | Desired selective access |
| --- | --- | --- |
| `read_actor` statistics for five PCs' AC | 10 reads, 75,238 bytes; AC was record 13, beyond the requested 10-record first page | AC value, breakdown and exception notes together |
| Prepared-spell lookup using `read_actor`, `list_actor_items` and `read_item` | 5 calls, 190,648 bytes; enumeration included 107 spells and two casting entries | Prepared slots with entry, rank, spell name/UUID and recorded expenditure |
| Inventory lookup using Actor search, `read_actor` and `list_actor_items` | 3 calls, 63,069 bytes | Item names, quantities and containment, with optional selected properties |
| `get_actor_types` compatibility/capability lookup | 2 calls, 51,432 bytes | Concise runtime compatibility plus requested types/sections |
| `read_actor` Strikes and `read_item` attack source | One Strike response was 23,692 bytes; the same attack Item was read twice at 16,595 bytes each | Named attacks and selected bonus, damage, traits or description details |

An offline projection retaining only the three AC records per PC, with existing
metadata and provenance, reduced the AC payload to 18,266 bytes (75.7% smaller).
This is a design baseline, not an implemented optimization or token-saving claim.
The advertised local `read_actor` and `read_item` descriptions also totaled about
60,000 characters; request/schema discovery overhead needs attention alongside
response size. Avoid retaining private character data in tracked fixtures.

### Desired behavior

- Offer discoverable, named detail selections such as armor class, hit points,
  saves, prepared spells, inventory summary and Strike summary. Support combining
  compatible selections without requiring internal Foundry/PF2e field paths.
- Apply selection before pagination. Page collections by meaningful entries
  where possible, keeping related values and their necessary caveats together.
  Retain count/byte bounds and revision-bound continuations; smaller pages alone
  must not force retrieval of unrelated records to reach a requested field.
- Make `read_item` selective for heavy source definitions, especially casting
  entries and attack Items. Allow exact descriptions and detailed evidence to
  be requested independently of unrelated source fields.
- Filter `list_actor_items` to the needed types/subset and return compact named
  identities. A prepared-spell view should join the actual recorded preparations
  to their spell identities without requiring a full spell inventory listing.
- Allow concise compatibility and selected type/section capability requests
  through `get_actor_types`, retaining an explicit full-detail option.
- Provide compact results with shared identity/provenance context and optional
  detailed evidence, reducing repeated UUIDs, paths and limitation strings.
  Preserve canonical selectors, source-versus-current basis, missing/null/zero
  distinctions, permissions, unsupported/partial status and actionable errors.
  Recorded preparation/expenditure must not imply verified castability.
- Keep essential tool contracts self-contained and concise. Expose exhaustive
  type-specific details on demand without replacing response bloat with an
  equally large selector schema or discovery response.

### Typed boundary design

Use Pydantic models and FastMCP's published input/output schema interface
for detail selections, selector variants, bounded limits and output contracts.
Use enums/literals, constrained fields, discriminated unions and model validators
for invalid combinations and cross-field constraints. Reject unknown inputs and
return useful validation feedback before executing the read. Keep function bodies
focused on orchestration and extraction rather than duplicating these checks.

The final implementation uses Pydantic 2.12.5 and the existing FastMCP server.
Every incoming selective call validates against its request model; every result
validates against its response model. PydanticAI and additional model calls are
not used. This supersedes the original framework request.

Typed input validation does not replace runtime document permission checks,
supported-version/schema checks, source validation or stale-continuation checks.
Keep those checks at their appropriate trust boundaries. The compact Actor/Item
projection is independently checked against validated private browser witnesses.

### Acceptance direction

- Validate actual MCP discovery schemas and reject invalid selections, bounds,
  unknown fields and conflicting selectors before document reads.
- Compare selective results with the equivalent existing detailed records,
  including provenance, exceptional notes and unsupported/missing data.
- Measure response bytes, catalog size and call counts for the AC, preparation,
  inventory, attack and compatibility workflows. Record actual model usage only
  when supplied by the client/provider; do not equate bytes with tokens.
- Verify pagination completeness and stale-result behavior after filtering.
  Reuse the existing test world and bounded synthetic PCs if needed; no production
  character mutations or new Foundry instance are required by this wishlist.

The live comparison covered all nine selected interfaces, including journal and
PDF payloads beyond the original AC example. The marked temporary character
check verified two repeated prepared positions, current AC, unchanged read-time
state and exact-marker cleanup. No production characters were modified.

## WISH-004 — Compute character wealth

- **Status:** Implemented in v2.2.0
- **Requested:** 2026-10-28
- **Scope:** Read-only character wealth calculation, initially for PF2e.

Agreed totals: **Total Currency** is currency only; **Total Wealth** is currency
plus full current item value, matching PF2e's GM-visible calculations. Optional
item details should explain the totals. No resale estimates or shared stash.

The same scoped exception as WISH-002 permits guarded PF2e current valuations.
See the [implemented contract and verification](character-inventory-metrics.md).

### User need

Answer “How much wealth does this character have?” through MCP tools.

### Desired behavior

- Report total wealth with explicit currency units and a breakdown of coins,
  other treasure and equipment value. State the valuation basis; inventory
  value and expected sale proceeds are distinct concepts.
- Account for quantities, price-per units and currency conversion without
  double-counting coins, contained items or attachments.
- Preserve character identity and offer optional contributing-item details
  with canonical identifiers for follow-up reads.
- Keep personal wealth separate from the shared party stash. Distinguish
  missing prices, inaccessible items and partial totals from zero wealth.

### Design decision for implementation

Choose an existing Actor/inventory tool extension, a new tool, or a combination
based on clear LLM discovery and compact answers. Tool names and schemas remain
undecided.

Existing inventory and treasure source readers do not establish computed wealth
support. Verify supported PF2e valuation interfaces and schema semantics before
implementation, documenting source versus derived values, inclusion rules and
relevant version constraints.

### Group-question acceptance (WISH-002 and WISH-004)

Use character members of the selected official party, not all character Actors
or player ownership. Required examples:

- “What's each PC worth?” — Total Currency and Total Wealth for each PC.
- “Who has the most wealth?” — highest Total Wealth, preserving ties.
- “Who's close to being encumbered?” — already-encumbered PCs first, then rank
  by additional Bulk needed to become encumbered, with exact boundary semantics.
- “What's the spread of wealth among the PCs?” — sorted totals, minimum,
  maximum, range, mean and median.

Use compact per-character summaries, preserve duplicate-name identities, and
state incomplete roster/value coverage. Group reads are sequential observations;
recheck party membership revision before claiming complete-party comparisons.

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
