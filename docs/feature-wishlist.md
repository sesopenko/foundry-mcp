# Feature wishlist

Feature ideas and requests with work still to do. Wishlist status does not mean
implemented or scheduled. Completed requests are in
[the finished wishlist](feature-wishlist-finished.md).

## How to maintain this wishlist

- When asked to “add to the wishlist” or record a feature idea, add it here.
  Recording a request does not authorize implementation.
- Read both wishlist files before adding an entry. Extend an existing request
  when the idea overlaps; otherwise append a new `## WISH-### — Title` entry.
  Use one more than the highest ID across both files (currently `WISH-012`);
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

## WISH-010 — Journal writing with GM-controlled guidance

- **Status:** Requested; not implemented
- **Requested:** 2026-10-31
- **Scope:** GM-only world-journal creation/editing, journal folder management,
  ownership changes and a unified writing-guidance tool. Initially text pages
  only; image browsing and embedding are WISH-011 and WISH-012.

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

- **Status:** Requested; not implemented
- **Requested:** 2026-10-31
- **Scope:** GM-only, read-only discovery of existing image files accessible
  through Foundry's file browsing API, for journal display and later embedding.

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

- **Status:** Requested; not implemented
- **Requested:** 2026-10-31
- **Scope:** Add image embedding to journal text authoring.
- **Depends on:** WISH-010 (journal writing) and WISH-011 (image browsing).

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
