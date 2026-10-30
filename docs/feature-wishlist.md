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

## WISH-006 — Paginated chat message reading

- **Status:** Wishlist
- **Requested:** 2026-10-29
- **Scope:** Read-only access to Foundry chat messages through MCP.

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

- **Status:** Wishlist
- **Requested:** 2026-10-29
- **Scope:** A chat-sending MCP tool and a separate read-only writing-style-guide
  tool. Images, message deletion and clearing the chat log are excluded.

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
  lists, plus supported PF2e inline formatting from WISH-008. Images are out of
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

- **Status:** Wishlist
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
