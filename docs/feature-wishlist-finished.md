# Finished feature wishlist

Completed requests moved from the [active feature wishlist](feature-wishlist.md).
Original request details below preserve implementation history; current behavior
and verification are documented in each entry's linked implementation guide.
Follow the active wishlist's maintenance instructions when moving entries here.

## WISH-001 — Official party members and party stash

- **Status:** Membership released in v2.1.0; stash implemented after v2.5.0,
  unreleased, verified 2026-10-31
- **Requested:** 2026-10-28
- **Scope:** Read-only party discovery and stash access, initially for PF2e.

`get_party_members` supplies bounded official world-party discovery and
membership, with canonical character follow-ups. `get_party_stash` adds actual
party-owned physical Item identities, stored quantities and optional container
claims; its `read_item` follow-ups preserve the party owner. Generic party Actor
reads remain unsupported. See [party contracts and verification](party-tools.md).

### User need

Answer “Who's in the party?” using official party membership and read the
shared party stash through MCP tools.

The user identifies the UI entry point as the special **“The Party”** group.
Its button opens the party sheet, which lists party members and provides access
to the party stash. This is the requested UI correspondence; the original
request required verification of the underlying supported API/schema.

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

### Original implementation direction and delivered decision

The original request left tool names/schemas undecided and called for reusing
existing Actor/Item readers where suitable, verifying supported PF2e party and
inventory contracts before implementation. Prior generic Actor/Item delivery
excluded party Actors; it did not establish stash support.

The delivered separate typed stash interface selects compact source values
before count/byte pagination and reuses `read_item` for optional source/prose/
evidence. World-party physical Item admission is deliberately narrower than
generic party Actor or campaign reading. Shared party selection and page
validation preserve membership behavior while removing duplicate policy logic.

### Verification

Focused JavaScript and actual typed MCP tests cover source values, missing/zero
quantities, denied/empty/multiple parties, canonical ownership, unsupported
systems, selection, UTF-8 budgets, complete pagination and stale continuations.
The existing Foundry14.369/PF2e8.6.1 test world passed the bounded fixture workflow
in 21 tool calls plus discovery: roster/stash reading, Item detail/prose/evidence
follow-ups, unchanged read-time source, and stale cursor rejection. Exact-marker
cleanup left zero fixtures and no pending creations; the browser reported zero
console errors. Measurements and the public API/schema evidence are recorded in
[the stash verification](party-tools.md#stash-verification--2026-10-31).
This completes the request in source without a release or version bump.

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

## WISH-006 — Paginated chat message reading

- **Status:** Implemented in v2.4.0. See [chat contracts and verification](chat-tools.md).
- **Requested:** 2026-10-29
- **Scope:** Read-only access to Foundry chat messages through MCP.

Implemented contracts and acceptance evidence are in [chat tools](chat-tools.md).
The original request below preserves its planning language; the implementation
guide defines the finalized names, ordering and continuation behavior.

### User need

Let the LLM read chat messages and subsequently ask “give me the messages after
this one” without retrieving the full history again, keeping context consumption
down.

### Desired behavior

- Read chat messages in bounded pages with deterministic ordering and stable
  message identifiers, useful author/speaker context and message content.
- Return continuation data for paging through existing history and a reusable
  message identifier or cursor for requesting only messages after a previously
  read point. The boundary is exclusive: do not repeat the anchor message.
- Allow incremental reads after reaching the end of the current history, so
  later calls retrieve newly added messages without replaying earlier pages.
- Keep default responses compact with explicit count and byte limits; provide
  bounded follow-up access when a single message exceeds the response budget.
- Respect message visibility, including whispers and blind messages. Distinguish
  no newer visible messages from incomplete results or unavailable history.
- Document ordering, continuation and recovery behavior for missing/deleted
  anchors, edited messages and messages arriving between calls. A fresh LLM
  should be able to use returned selectors without constructing cursors.

### Acceptance direction

Verify complete pagination and repeated incremental reads without duplicate or
skipped messages under the documented ordering contract. Cover equal timestamps,
new arrivals, empty results, deleted anchors, visibility and oversized content.
Measure response bytes and call counts for initial history retrieval and later
“after this message” reads, demonstrating that incremental reads omit previously
read history. Tool names and exact cursor/schema design remain undecided.

## WISH-007 — Send HTML chat messages and retrieve the writing style guide

- **Status:** Implemented in v2.4.0. See [chat contracts and verification](chat-tools.md).
- **Requested:** 2026-10-29
- **Scope:** A chat-sending MCP tool and a separate read-only writing-style-guide
  tool. Images, message deletion and clearing the chat log are excluded.

Implemented contracts and acceptance evidence are in [chat tools](chat-tools.md).
The original requirements and supplied guide below are preserved; the linked
contract defines the finalized HTML subset, schemas and retry behavior.

### User need

Let the LLM compose and send chat messages using the same terminology as the
Foundry UI, including HTML formatting, and retrieve Paizo's writing conventions
when drafting Pathfinder text.

### Desired behavior

- Expose these UI choices in the sending tool's published contract:
  **Public as User**, **private to game masters**, **blind to game masters**,
  **self only**, and **public as character**. Keep the user-facing terminology
  even when the underlying API uses different names or represents audience and
  speaker separately; translate internally.
- Document each choice's audience, author and speaker semantics. Make character
  selection discoverable through named canonical identifiers, with explicit
  permission and missing-character errors. Do not silently substitute a different
  audience or speaker.
- Accept HTML message content matching the editor's supported basic formatting:
  headings, block and inline elements, alignment, tables, font, size, format and
  lists, plus supported PF2e inline formatting from
  [WISH-008](feature-wishlist-finished.md#wish-008--pf2e-inline-formatting-assistance). Images are out of
  scope. Establish the actual supported HTML subset and sanitization behavior
  during implementation; these categories are user-observed editor features,
  not a verified tag/style allowlist or a promise of arbitrary HTML support.
- Return a compact send result with the created message's stable identifier,
  audience and named author/speaker context, usable with WISH-006 reading.
- Provide a separate tool to retrieve the exact Paizo passage below on demand.
  Keep the passage out of routine send responses and discovery descriptions.
  Distinguish this writing guide from the PF2e wiki's inline-syntax guidance.
- **Do not expose any message-deletion functionality or “Clear chat log” to
  the LLM**, including through alternate operations on the sending tool.

### Writing-style-guide payload

The user supplied the following as official Paizo text. Preserve it verbatim
as the requested guide payload; publication/page attribution remains to be
verified during implementation. The page 628 reference belongs to this passage
and must not be presented as a universal page reference for other books.

```text
Throughout this rulebook, you will see formatting standards that might look a bit unusual at first. Specifically, the game’s rules are set apart in this text using specialized capitalization and italicization. These standards are in place to make the rules elements in this book easier to recognize.

The names of specific statistics, skills, feats, actions, and some other mechanical elements in Pathfinder are capitalized. This way, when you see the statement “a Strike targets Armor Class,” you know that both Strike and Armor Class are referring to rules.

If a word or a phrase is italicized, it is describing a spell or a magic item. This way, when you see the statement “the door is sealed by lock,” you know that in this case the word denotes the lock spell, rather than a physical item.

Pathfinder also uses many terms that are typically expressed as abbreviations, like AC for Armor Class, DC for Difficulty Class, and HP for Hit Points. If you’re ever confused about a game term or an abbreviation, you can always turn to the Glossary and Index, beginning on page 628, and look it up!
```

### Acceptance direction

Verify actual MCP discovery and invocation for all five UI choices, checking
audience visibility and author/speaker identity separately. Test HTML handling,
invalid choices, denied or missing characters and exact style-guide retrieval.
Confirm discovery exposes neither deletion nor clearing operations. Measure
discovery and representative response sizes, including an explicit guide lookup.
Before implementation, verify documented public Foundry APIs and supported
runtime behavior; finalize names, schemas, content bounds and send-failure/retry
semantics so an uncertain send outcome does not invite duplicate messages.

This request is separate from WISH-006's read-only chat scope. Recording it does
not authorize sending messages to an existing game session.

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

## WISH-009 — Read-only compendium search and reading

- **Status:** Implemented in v2.5.0 (2026-10-30)
- **Requested:** 2026-10-30
- **Scope:** Discover, search and read compendium Items, supported Actor types
  and JournalEntries/pages, initially for PF2e. Compendium mutation is prohibited.

Implementation contracts, bounds, compatibility and verification are in
[the compendium guide](compendium-tools.md). Five typed read-only tools add pack
capability discovery, page-title/body search, ordered contents, exact source
reading and lazy canonical reference follow-ups. Existing PF2e Actor/Item
readers supply complete selected definitions with published rules-reference
guidance. Offline, live deterministic and two bounded fresh-context lookup
checks passed. The requirements
and pre-implementation evidence below are retained as historical context.

### User need

Use the established Item, Actor and journal reading capabilities to look up
compendium content: search for spells, actions and monsters, and read core PF2e
game rules stored in compendium journal entries.

### Desired behavior

- Discover relevant packs and search document names in explicitly selected pack
  indexes, with supported type filters. Return compact named results with pack
  context, document type and canonical identifiers for follow-up reads. State
  which packs and fields were searched; name matches do not establish matches
  in descriptions, embedded abilities or journal page bodies.
- Read selected spell and action Items, monster Actors and other supported
  Actor/Item types using the established readers where suitable. Extend journal
  navigation and reading to compendium JournalEntries and their pages, including
  core PF2e rules text. Reuse internal journal processing while preserving a
  separate compendium interface, as in the existing
  [compendium journal plan](prompts/read-compendium-packs.md).
- Support page-title search across entries in an explicitly selected journal
  pack, without requiring the caller to know the parent entry. Load entries
  within declared work bounds and return continuations when needed. Also offer
  page-name navigation within a selected entry. Any
  broader description or journal-body search must have verified field coverage
  and explicit loading/work bounds. A literal text scan of selected loaded
  journals is feasible; an automatic full-content scan of every pack is not
  required. Report unsearched content and partial scans explicitly.
- Preserve pack/document/page identity and distinguish duplicate names, empty
  results, inaccessible packs, unsupported content and incomplete searches.
  Provide bounded selective responses and continuations for complete retrieval.
- Enforce a strictly read-only compendium boundary: the agent must never be
  allowed to create, write, update or delete compendium content, or change pack
  configuration or permissions to enable such changes. Expose no mutation
  operation through these tools, even for unlocked packs or GM callers.
- Make the discover-search-read workflow usable by a fresh LLM through published
  tool contracts and returned selectors without guessed IDs or prior pack knowledge.

### Acceptance criteria — gameplay and session preparation

Acceptance concerns the GM's completed task, not merely a successful search.
A fresh agent must use published MCP contracts and returned selectors, without
repository access, arbitrary JavaScript, UI inspection, memorized pack IDs or
user knowledge of Foundry's storage layout. The agent supplies explanations;
the tools supply discoverable, bounded source evidence, not model-generated
rules summaries. Do not send chat or execute the retrieved inline notation.

| GM task | Required outcome |
| --- | --- |
| “Explain Treat Wounds to my players.” | Find the action and read its complete rules. Explain equipment/proficiency requirements where supported, treatment time, eligible targets, check/DC choices, degree-of-success outcomes, immunity/repeat timing, extended treatment and wounded removal. Distinguish unsupported or unstated facts from explicit source. A GM-screen summary table alone is insufficient for the full explanation. |
| “Look up Fireball during play.” | Return a concise sourced reference covering rank, traditions/traits, casting time, range, area/targets, defense, damage and heightening. Obtain structured fields as well as description; identify genuinely absent/not-applicable fields. Do not infer a caster's DC, available slots or castability from a compendium definition. |
| “Find DCs by level; what's the DC for level 5?” | Discover the embedded page without being told “GM Screen”; answer 20 from its level/DC table and retain the named pack/entry/page reference. Keep the spell-rank table distinct from the level table; retain footnotes when relevant. A follow-up about hard difficulty must retrieve the separate DC Adjustments evidence rather than invent an adjustment. |
| “Prepare references for next session: Treat Wounds, level-based DCs and difficulty adjustments.” | Produce a concise reading list with canonical references and supported key points. Read the relevant action/page content, preserve caveats and table relationships, and reuse discovered identities without repeatedly enumerating unrelated packs or returning entire journals. This authorizes drafting an answer, not writing Foundry documents. |

- **Discovery:** expose Item, Actor and JournalEntry pack capabilities and
  searchable fields. Page-title search must find “DCs by Level” within a selected
  journal pack even though no top-level entry has that name. Case-insensitive
  partial-title matching and returned parent context should support refinement;
  document literal semantics and recovery for no matches. Semantic/fuzzy search
  is not required. Unknown terminology can be investigated through compact page
  lists/outlines and an explicitly scoped literal body search with continuations.
- **Reading:** provide an obvious rules-reference selection for Items, or
  published guidance identifying all needed field groups. Identity-only reads
  must not be presented as enough to explain an action/spell. Preserve exact
  description/HTML and table headers, rows, units, footnotes and source notation;
  support complete reconstruction across fragments. Return named canonical
  citations and supported follow-ups to related Items/journal pages without
  automatic recursive expansion. Surface ambiguity and source differences.
- **Gameplay efficiency:** target at most eight MCP calls and two minutes for
  each standalone named lookup from fresh discovery in this existing fixture.
  Measure cold and reused-discovery paths separately; do not hide setup calls.
  These are acceptance targets, not measured current performance or universal
  latency guarantees. A small lookup must not require all-pack body loading or
  copying every page into the model context.
- **Preparation completeness:** test bounded multi-page reading and a related
  source follow-up, with a declared cap (initial target 20 calls/five minutes).
  Support continuation after count/byte/work limits; distinguish exhausted
  matches from unsearched scopes. Verify stale selection/revision handling,
  duplicate names, denied/missing packs and unsupported page/document types.
- **Measurement and safety:** validate actual discovery and invocation, source
  coverage and exact reconstruction with deterministic tests before budgeted
  fresh-agent evaluation under [the evaluation process](mcp-tool-evaluation.md).
  Record actual calls, compact JSON bytes, completion and elapsed time; bytes
  are not tokens. Retain monster search/read coverage from the original scope.
  Confirm no imports, document writes/deletes, rolls, chat sends or permission/
  pack configuration changes. Pack locks must not be the only protection.

Existing Actor/Item compendium index search is a starting point, not evidence
that this complete workflow is implemented. Audit current reader coverage and
public Foundry/PF2e contracts before deciding which tools need extensions;
tool names and schemas remain undecided. Recording this request authorizes
neither implementation nor compendium changes.

### API feasibility review — 2026-10-30

Checked the official v14 documentation through Grounded Docs and fresh official
page fetches. The local v14 index was completed on 2026-10-12; matching the
documented development major version does not establish build-specific behavior.
This review adds documentation evidence, not a new live runtime verification.

- **Direct public API support:**
  [CompendiumCollection](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html)
  provides pack identity/type, `testUserPermission`, `getIndex({fields})` and
  `getDocument(id)`. Name/type filtering can operate on the returned index;
  selected document loading requires no import. Existing `actorPacks.js`
  already implements scoped Actor/Item name search with these index APIs.
- **Search coverage needs verification:** the same public API documents
  `search({query, filters, exclude})` over names and indexed HTML fields, plus
  `getSearchableFields(documentName, type)`. This is evidence of a search API,
  not a guarantee that every PF2e description or embedded journal page body is
  indexed. Verify relevant fields and loading behavior before adopting it.
- **Journal reading is supported:**
  [JournalEntry](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntry.html)
  defines embedded pages, and the
  [page schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageData.html)
  provides names, ordering and text sources. Loading an entry can load many
  pages; bounded MCP output alone does not bound that underlying load.
- **Application work remains:** MCP pagination, byte budgets, scan continuations
  and stale-result handling are application contracts; `getIndex` does not
  document server-side offset/limit pagination. Avoid promising cheap full-pack
  text searches or snapshot guarantees the API has not established. Preserve
  the existing journal plan's unresolved internal-folder and cache boundaries.
- **Read-only is enforced by this project:** Foundry also exposes mutation
  APIs and a GM can have write permission. Pack locks are not an agent security
  boundary. Keep mutation operations out of this interface and require any
  future document-writing interface to reject compendium targets.

### Exploratory live lookups — 2026-10-30

Read-only checks used the existing `test` world, ready GM, Foundry 14.369 and
PF2e 8.6.1. These are assisted exploratory observations, not a fresh-agent pass
or a measured performance baseline. Existing Item discovery/search/read tools
were used; journal discovery and selected reads required development JavaScript
because compendium journal tools are absent. No mutation operations were invoked.

- Actions pack name search found **Treat Wounds**; `read_item` returned the
  complete 1,798-unit description in two contiguous fragments, plus publication
  identity. Its stored activation mapping says `passive_ability`, while the
  prose specifies ten minutes: that label alone cannot explain gameplay timing.
  The GM Screen also contains a Treat Wounds table with trained/expert/master/
  legendary DCs, but lacks the full action procedure.
- Spells pack name search found **Fireball**. Selected casting/damage/description
  reads supplied rank 3, two-action source time, 20-foot burst, basic Reflex,
  6d6 fire and +2d6 per heightened rank; a traits/publication read supplied
  traditions and Player Core provenance. Those selections did not expose range;
  a selected source-document check confirmed `system.range.value` is “500 feet”.
  Range retrieval through the production selective interface remains a coverage
  question for implementation, not an established fix or absence of source data.
- PF2e Journals' index contains seven entry names, including **GM Screen** but
  no **DCs by Level**. Loading that one entry exposed 61 embedded pages and
  located **DCs by Level**, **DC Adjustments** and **Treat Wounds** by page title.
  This proves entry-name-only search cannot satisfy the requested rules lookup.
- The complete **DCs by Level** HTML was read in three bounded contiguous
  fragments totaling 1,645 UTF-16 units. It contains both level/DC and spell-rank/
  DC tables, a rarity footnote and GM Core p. 53 attribution. Level 5 maps to
  DC 20. The separate **DC Adjustments** page specifies hard as +2. Preserve
  table structure and the distinction between these sources in future reads.

The lookups establish that the requested content can be obtained through
selected public index/document/page reads. They do not establish native
full-text index coverage, complete journal-search tooling, uniform source
quality or current satisfaction of the acceptance criteria above.

## WISH-010 — Journal writing with GM-controlled guidance

- **Status:** Implemented after v2.5.0, unreleased; verified 2026-10-31
- **Requested:** 2026-10-31
- **Scope:** GM-only world-journal creation/editing, journal folder management,
  ownership changes and a unified writing-guidance tool. Initially text pages
  only; image browsing and embedding are WISH-011 and WISH-012.

The implemented contract and offline/live verification are recorded in
[journal authoring](journal-writing.md). The GM's text tabs are embedded pages;
v14 category authoring remains outside this text-page workflow.

### User need and GM workflows

Let the GM ask the LLM to prepare session notes, add a player handout, revise a
selected page, organize journals or share a handout with particular players.
The GM must be able to supply persistent instructions such as “The journals
under this Adventure Path folder are official source material; do not change
them without my explicit permission. Put our session notes in this other folder.”
Respect those instructions before selecting targets or writing content.

### Persistent writing guidance

- Add a GM-only configuration entry on the module's Foundry settings page,
  preferably opening an HTML WYSIWYG editor. Save the GM-authored HTML and its
  save timestamp together in world-scoped module settings. Restrict editing,
  the configuration UI and MCP retrieval to the GM, like other GM settings.
  World settings are not a confidential secret store; do not promise that
  hiding a settings UI makes its stored value unreadable by player clients.
- Merge this retrieval with `get_pathfinder_writing_style_guide` into one
  writing-guidance tool. Clearly separate and label **GM-authored instructions**
  from **Pathfinder/Paizo style guidance**; the GM section is guidance *for* the
  LLM, not text authored by the LLM. Explicitly tell the LLM that following the
  GM instructions is critically important, including restrictions on official
  adventure material and requirements to obtain permission before overwriting.
- Return the GM copy as HTML and its save timestamp. A caller may supply the
  previously returned timestamp: if changed, return changed status, the new
  timestamp and new guidance; otherwise return an explicit “no change since
  last time” result without repeating the copy. Distinguish never configured,
  deliberately empty and unavailable guidance. Define timestamp precision and
  collision handling so successive saves cannot be mistaken for no change.
  Include the bundled style guide's revision in change detection as well, so
  updating that section cannot silently leave the LLM with stale guidance.
- Preserve the existing style passage and its attribution caveat from
  [the chat guide](chat-tools.md#writing-guide): its exact publication attribution
  is unverified. Do not relabel it as verified official copy or confuse it with
  the PF2e system wiki's authoring conventions. Define migration for existing
  guide callers and update chat and journal tool references consistently.
- Journal-writing tools' published descriptions/docstrings must recommend
  reading the unified guidance tool first, by its final tool name. Explain
  follow-up change checks without placing the full guide in every description
  or write response. Free-form prose guides LLM decisions; do not claim it is
  an automatically enforceable Foundry access-control rule. Define and verify
  the explicit-GM-permission workflow for protected-source edits.

### Read-to-write correspondence and content

- Reuse the hierarchy, terminology and canonical selectors of
  [the journal readers](journal-tools.md): folders contain JournalEntries,
  entries contain embedded JournalEntryPages, with named parent context. Accept
  selectors returned by reading/discovery and return created/updated identities
  usable directly by those readers. Duplicate names must not select a target
  implicitly. Compendium content remains strictly read-only.
- Create and rename entries; create and edit named text pages and their text.
  Map the GM's “tabs” terminology to the reader's documented pages/categories
  model rather than inventing a second hierarchy. Explain whether a requested
  tab means a page or a v14 category and verify any category operation before
  exposing it. Use an extensible type enum initially accepting only `text`, so
  future page types can be added without changing the request structure.
- Accept supported basic HTML: ordinary blocks/inline elements, headings,
  simple tables, font family, font colour, bullet and numbered lists, horizontal
  dividers and links. Offer small, normal, large, huge and custom size choices;
  custom uses a positive bounded point (`pt`) size. Publish their precise HTML/
  CSS mapping and supported subset after verification, not arbitrary HTML/CSS.
  Discover loaded font families through the public font API when available.
  Preserve unrelated content and distinguish replacing text from appending it.
- Define bounded typed requests/responses, clear update semantics, stale-read
  handling and retry outcomes. A timeout must not lead to duplicate entries or
  pages. Return compact mutation receipts and reader follow-ups; do not echo
  entire journals or silently truncate text being written.

### Folders and ownership

- Create and rename JournalEntry folders, choose parent folders, set folder
  colour using an HTML hex colour such as `#254c84`, and select alphabetical or
  manual sorting. Make ordering behavior discoverable, including how to place
  new entries/pages when the GM requests a particular order.
- Set/change ownership using the GM's terms: **No Change**, **None**,
  **Limited**, **Observer**, **Owner**, with **All Players** plus individual
  player overrides. No Change means preserve the existing value, not an ownership
  level and not the embedded-document INHERIT sentinel. Explain the relationship
  between the default ownership value and per-player overrides, and the real
  visibility/access provided by Limited for journals.
- Add narrowly scoped ownership-recipient discovery returning non-GM player
  names and canonical User IDs, including offline users. Limit it to what is
  needed for journal/folder ownership; expose no broader user administration.
- Foundry folders have no persisted ownership field. “Folder permissions” must
  explicitly mean a bounded ownership operation on contained journals, with a
  stated direct-only or recursive scope, affected-target preview/counts and
  per-document results for partial failures. Do not invent inherited folder ACLs
  or imply future entries automatically receive an earlier batch change.
- Never expose “Show GM Users” or accept GM users as ownership targets. Preserve
  all GMs' effective access; reject any operation that could hide an entry/page
  from the GM. Verify page ownership and parent interaction instead of assuming
  entry ownership alone establishes the final audience. Ownership changes must
  not bypass the GM's protected-content guidance.

### Acceptance direction

Test the GM workflows above through actual MCP discovery and invocation:
read guidance, discover a destination, create a handout with two text pages,
read it back, rename/reorganize it, share with one discovered player while
preserving other overrides, and change a folder's contained-journal ownership.
Verify that official-source editing requires the permission called for by GM
instructions. Cover unchanged/changed/empty guidance, duplicate names, invalid
HTML/type/colour/size/ownership, denied and compendium targets, stale edits,
retry ambiguity, partial batch changes and retained GM access. Measure discovery
and response sizes under [the evaluation process](mcp-tool-evaluation.md).
Use offline tests first and safe marked fixtures in the existing development
world for eventual live checks; this request authorizes no implementation or
changes to existing game documents.

### API feasibility review — 2026-10-31

Grounded Docs matched `foundry-vtt@14`; official pages and indexed results were
reviewed against the project's documented Foundry 14.369/PF2e 8.6.1 development
baseline. This is documentation evidence, not new live verification: the healthy
bridge had no connected Foundry client. Verify declared version compatibility,
HTML persistence/rendering and permission behavior during implementation.

- Public document `create`, `update`, `createEmbeddedDocuments` and
  `updateEmbeddedDocuments` support world entries and embedded pages:
  [JournalEntry](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntry.html).
  [Entry data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryData.html)
  supplies `folder`, `ownership`, `pages`, `categories`, `name` and `sort`;
  [page data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageData.html)
  supplies `type`, `name`, `category`, `ownership` and `text`.
  [Text data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageTextData.html)
  stores `content` and `format`. These schemas establish storage, not a promise
  that every editor style survives sanitization or renders identically.
- [Folder data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html)
  supports `name`, `folder`, `color`, `type`, `sort` and `sorting` (`a`/`m`),
  but no ownership. Use public JournalEntry document updates for the explicitly
  scoped ownership batch, not protected ownership-dialog submit handlers.
  [Ownership constants](https://foundryvtt.com/api/v14/variables/CONST.DOCUMENT_OWNERSHIP_LEVELS.html)
  define None/Limited/Observer/Owner and INHERIT; No Change is application logic.
- [ClientSettings](https://foundryvtt.com/api/v14/classes/foundry.helpers.ClientSettings.html)
  documents `register`, `get`, `set` and `registerMenu` with `restricted: true`.
  A custom submenu can use the public
  [HTMLProseMirrorElement](https://foundryvtt.com/api/v14/classes/foundry.applications.elements.HTMLProseMirrorElement.html)
  editor. The module must implement save timestamps/change detection.
- [FontConfig.getAvailableFonts](https://foundryvtt.com/api/v14/classes/foundry.applications.settings.menus.FontConfig.html#getavailablefonts)
  is public and returns loaded font families. This supports discovery, not
  installing fonts or guaranteeing identical fonts on every client.
- These journal/settings operations use core Foundry APIs and need no PF2e
  private interfaces. The upstream
  [PF2e Style Guide](https://github.com/foundryvtt/pf2e/wiki/Style-Guide), searched
  through `pf2e-wiki`, documents authoring conventions; it is rolling system
  guidance, not a Paizo publication or a separate journal-write API. Reuse the
  [verified PF2e inline builders](pf2e-inline-builders.md) where requested;
  keep system-specific syntax conditional and verify journal rendering.

## WISH-011 — Browse Foundry images for content selection

- **Status:** Implemented after v2.5.0, unreleased; verified 2026-10-31
- **Requested:** 2026-10-31
- **Scope:** GM-only, read-only discovery of existing image files accessible
  through Foundry's file browsing API, for journal display and later embedding.

The implemented contract and offline/live evidence are recorded in
[image browsing](journal-images.md). Local verification covers data/public;
configured S3 browsing remains unverified.

Let the GM ask the LLM to find an existing illustration in a selected Foundry
directory and choose its canonical source path without guessing filenames.
Return bounded directory/image listings with names, source location, paths and
follow-up selectors. Distinguish server file directories from JournalEntry
folders. Document supported sources, extension filtering, empty/denied/missing
locations and completion; avoid automatic recursive scans of the whole server.
No uploads, file writes/deletes or arbitrary host filesystem access are included.
Do not promise semantic image search or visual inspection from filenames alone.

### API feasibility and acceptance direction — 2026-10-31

The official v14
[FilePicker](https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html#browse-2)
documents public static `browse(source, target, {bucket, extensions, wildcard})`
returning directory/file results. Use the configured public implementation and
respect Foundry permissions/source availability. This is core Foundry behavior;
PF2e-specific filesystem internals are unnecessary. It does not establish native
server-side pagination or semantic search. Define bounded loading/output and
continuation behavior, verifying exact result fields and permitted sources in
the existing runtime before implementation. This review establishes documented
feasibility only; no new live file browsing was performed.

Verify a fresh LLM can navigate directories, select an image and pass its
returned source to WISH-012 without path reconstruction. Cover duplicate names,
spaces/Unicode, inaccessible sources, large directories and changed listings.
Measure actual discovery/response sizes; never equate a filtered or partial
listing with all images on the server.

## WISH-012 — Embed images in journal text

- **Status:** Implemented after v2.5.0, unreleased; verified 2026-10-31
- **Requested:** 2026-10-31
- **Scope:** Add image embedding to journal text authoring.
- **Depends on:** WISH-010 (journal writing) and WISH-011 (image browsing).

The implemented action, bounds and offline/live acceptance are documented in
[image embedding](journal-images.md#embedding-in-a-text-page).

Let the GM select an existing Foundry image and ask the LLM to insert it at a
specified location in a journal text page, with **source**, **alt description**,
**width** and **height**. Reuse the browser's canonical image source and the
journal reader/writer's page identity; preserve surrounding text and GM writing
constraints. Publish dimension units, defaults/aspect-ratio behavior, bounds and
escaping/source validation. Report unsupported or inaccessible sources explicitly.
This extends text-page HTML; standalone image-type journal pages, uploads and
image generation are not required by this item.

### API feasibility and acceptance direction — 2026-10-31

The documented core [page text schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageTextData.html)
can store HTML content through the public document updates identified in WISH-010.
Standard HTML `img` provides `src`, `alt`, `width` and `height`; these are HTML
attributes, not invented JournalEntry schema fields. No PF2e-specific mutation
API is needed. Actual Foundry sanitization, attribute retention, rendering and
player asset access remain implementation/live-verification gates; do not claim
that a GM-visible file automatically becomes player-accessible through ownership.

Verify browse → select → embed → read back and render using safe marked fixtures
in the existing test world after offline tests. Check alt text, dimensions,
escaping, inaccessible files, stale pages and unchanged surrounding content.
Apply WISH-010's GM-access, guidance, retry and response-budget requirements.

