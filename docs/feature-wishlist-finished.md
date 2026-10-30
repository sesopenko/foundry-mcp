# Finished feature wishlist

Completed requests moved from the [active feature wishlist](feature-wishlist.md).
Original request details below preserve implementation history; current behavior
and verification are documented in each entry's linked implementation guide.
Follow the active wishlist's maintenance instructions when moving entries here.

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

## WISH-008 — PF2e inline-formatting assistance

- **Status:** Implemented in source after v2.2.0; not yet released
- **Requested:** 2026-10-29
- **Scope:** Three separate MCP tools generating inline roll links, inline check
  links and inline embeds for PF2e content authoring.

### User need

Help the LLM draft PF2e-formatted text for chat messages, journal entries and
other future write/create tools without requiring it to construct inline syntax
from memory.

### Desired behavior

- Provide **one tool per inline type**, each accepting a structured parameter
  object tailored to that type. This supersedes the initial idea of a single
  tool with a block-type selector. Publish distinct typed input/output contracts
  with concise field guidance, defaults, bounds, conflicts and examples.
- Each tool returns a text block containing the insertable inline source text.
  Drafting must not send chat, write journals, execute rolls or apply effects.
  Return source notation rather than rendered HTML or fetched document bodies.
- Keep generated text compact and reusable in WISH-007 and future journal
  writing. Make PF2e requirements and destination/context limitations explicit;
  do not claim that every destination enriches the syntax identically.
- Limit this entry to these three inline families. Inline action macros,
  templates, localization and images are outside scope.

### Evidence and proposed tool boundaries

The upstream [PF2e wiki Style Guide](https://github.com/foundryvtt/pf2e/wiki/Style-Guide)
was searched in Grounded Docs library `pf2e-wiki` and fetched on 2026-10-29.
It is rolling documentation, not a versioned runtime contract. The following
boundaries follow its **Inline Roll Links**, **Inline Check Links** and
**Inline Embeds** sections; exact supported parameters and versions still need
implementation-time verification.

| Separate tool | Proposed parameter coverage | Example returned text |
| --- | --- | --- |
| Inline roll links | Non-damage formula, roll visibility, flavor and optional label; PF2e damage formula/types/categories, roll options and optional label in the same roll-link tool | `[[/r 1d20+17 #Counteract]]` or `@Damage[1d6[fire]]{ouch!}` |
| Inline check links | Check/statistic type, one DC method (`dc`, `against` or `defense`), optional label, basic save, DC visibility/adjustment, roller role, traits and roll options; other documented check flags where verified | `@Check[fortitude|dc:20|basic]` |
| Inline embeds | Compendium Item UUID and optional horizontal-rule suppression; always emit the inline flag | `@Embed[Compendium.pf2e.feats-srd.Item.39CqlOzlHjEhh0E4 inline hr=false]` |

Use the guide's parameter ordering and preferred syntax. Distinguish a roll
link's eventual roll visibility from the audience of the message containing it.
Document where check/damage behavior depends on an owning Actor/Item or target;
do not invent that context when drafting standalone chat text. Embeds require
canonical UUIDs obtained through discovery, not guessed names or IDs; generating
notation does not establish target access or successful rendering.

### Acceptance direction

Verify a fresh client can discover and invoke each tool independently using
only its published schema and examples. Cover valid parameter combinations,
conflicting DC methods, invalid input and delimiter/escaping behavior. Verify
exact insertable output and absence of write/roll side effects. After offline
checks, verify relevant enrichment in the existing development runtime and
record the tested Foundry/PF2e versions and destination-specific limitations.
Measure discovery size and generated-text response bytes. Tool names and exact
schemas remain to be finalized; this entry records proposed work only.

### Implementation and acceptance

The three typed `create_pf2e_inline_roll`, `create_pf2e_inline_check` and
`create_pf2e_inline_embed` tools are implemented and verified on
Foundry14.369/PF2e8.6.1. Advanced expressions and dynamic references are excluded;
roll arithmetic uses structured dice/modifiers. The source tree retains version
2.2.0 pending a separately authorized release. See the
[contract, API evidence, live acceptance and measured payloads](pf2e-inline-builders.md).
The historical proposed boundaries above are preserved; the linked contract
supersedes their undecided schema and verification statements.

