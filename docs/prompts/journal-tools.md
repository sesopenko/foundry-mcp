# Journal tools design questions

The first feature should let you ask the LLM questions and have it work through
Foundry journal entries to answer them. These questions will guide the initial
tool design.

## 1. Which journals should the LLM be able to read?

Choose one, or describe another scope:

- All world journals, including GM-only content (recommended).
- Only selected folders or entries.
- World journals and compendium journals.

Answer: All world journals, including GM only content

## 2. What questions do you most want answered?

Please give a few example questions you would ask during game preparation.
Examples might include finding an NPC's history, connecting clues across
chapters, or identifying material needed for the next session.

Answer:

Some examples:

"Tell me Ripnugget's involvement in the campaign from chapter to chapter, build a narrative that's likely to develop as the players go through the campaign"

"What's in area E1?"

"Which encounters/events in chapter 2 happen for level 4 characters and below?"

"What's the expected character level for chatper 7?"

"Summarize chapter 3. Which NPCs from chapter 2 and earlier are relevant in chapter 3?  Which npcs in chapter 3 return in later chapters?"

## 3. How should answers refer back to the journals?

Choose one, or describe another format:

- Entry and page names with clickable Foundry links (recommended).
- Entry and page names only.
- Links plus short supporting excerpts.

Answer: Are foundry links even possible?  That'd likely open new tabs and foundry's not really meant to be ran in multiple tabs.

It could be possible that an mcp tool opens a particular journal page in the game tab.

## Confirmed scope

- Read all world journals through the connected GM browser, including GM-only
  text. Compendium journals are outside the first version.
- Support text pages, including HTML and Markdown. Do not read images, maps,
  PDFs, or video. Report omitted non-text pages so absence of text is explicit.
- Preserve stored page HTML exactly when reading. The LLM interprets its
  markup directly; do not substitute a plain-text or Markdown conversion.
- Answer questions using journal evidence and cite entry and page names.
- Do not assume a particular adventure's folder layout, naming, chapter
  organization, area codes, or HTML classes.
- Give the LLM the user's navigation model: a directory tree of folders,
  subfolders, and entries, followed by an entry's table of contents and page
  text. Names and paths provide context; IDs/UUIDs remain stable references
  for subsequent calls.
- Use only documented, externally callable Foundry public APIs and supported
  document schema fields for Foundry integration. Runtime discoveries are
  research evidence, not permission to depend on undocumented functionality.
  Standard JavaScript/browser APIs may process the retrieved data.

## Exploration findings

Explored the `test` world on Foundry 14.369 through the existing development
RPC. No world documents were created or changed.

### Foundry relationships to preserve

- `game.folders` contains Folder documents. Journal folders have
  `type === "JournalEntry"`. A folder's source `folder` value is its containing
  folder ID; its live `folder` property resolves to that Folder document.
- `game.journal` contains world JournalEntry documents. Each entry has an
  optional containing folder, and can instead live at the directory root.
- `entry.pages` is an EmbeddedCollection of JournalEntryPage documents.
  `page.parent` is the entry. This differs from folder containment: a world
  entry's `parent` is null even when it belongs to a folder.
- Entries do not embed other entries in the core model. Foundry v14 also
  supports embedded categories and optional page membership in a category.
  No categories were present in this sample world; category UI behavior has
  not been verified.
- Page IDs are scoped to their entry. Use full page UUIDs when exposing a
  page reference: `JournalEntry.<entry-id>.JournalEntryPage.<page-id>`.
- Collection iteration order is not necessarily reading order. Sort pages
  by their `sort` values within category groups where present, with a
  deterministic ID tie-breaker. Respect folder alphabetical/manual sorting
  when browsing the directory.
- `title.level` and `title.show` describe presentation. Neither implies that
  a page embeds another page.

### Observations specific to this world

The A/B examples demonstrate nested folders and mixed text/image pages. An
unfiled test entry demonstrates that a containing folder is optional.

The published adventure uses one folder containing chapter entries, a
gazetteer, reference material, and handouts. This is an example, not a tool
requirement. There are 323 text pages in the whole world, totaling about
1.15 million HTML characters. The largest page has about 54,000 characters.
Of those pages, 315 contain headings, two contain tables, and 247 contain
Foundry UUID links. Both HTML and Markdown text formats are present.

Area E1 is in a page named "The Devil's Doorstep". Its area code and encounter
rating occur in an HTML heading. Names alone cannot support content search.
Some Chapter 2 event levels are image badges; image filenames are not an
authoritative generic source of character-level information. Under the
text-only scope, answers must state when the retrieved text is insufficient.

Journal links can refer to an entry, a page, or a heading inside a page.
Relative links also occur. The runtime successfully resolved a relative
page UUID with `foundry.utils.fromUuidSync(uuid, {relative: sourcePage})`
after separating the heading anchor. Other links target actors, compendiums,
playlists, and macros. Preserve those references without invoking them or
expanding their documents.

### Directory and journal navigation

The live `game.journal.tree` exposes directory nodes with `folder`, `children`,
`entries`, `depth`, and visibility information. Its ordering matched the
adventure's folder and chapter sequence. This is an exploration observation,
not an approved implementation dependency: external public API status has not
been established. Construct the tool's tree from documented folder/entry
relationships and sorting fields unless an equivalent documented public tree
API is verified for the supported version. The LLM still receives a nested
view; reconstruction happens in the module through supported APIs.

Inspection of installed core journal sheet source showed that its sidebar
uses a table of contents. When categories exist, it groups pages under ordered
categories and places remaining pages in an uncategorized group. Pages within
groups are sorted by `sort`. Without categories, pages are ordered directly.
The public `page.toc` exposes headings and anchors within a text page.

Private sheet methods and their intermediate objects must not be called,
copied as an integration contract, or used to retrieve the contents view.
Build that view from documented page/category relationships, ordering fields,
and public heading APIs. Verify each dependency's public annotations before
implementation; documentation that lists an internal method is insufficient.

These are two navigation layers: the directory locates an entry, while that
entry's contents locate pages and sections. Heading nesting and page title
levels describe presentation rather than embedded-document containment.

This adventure uses `MetaMorphicJournalEntrySheet`, which extends the core
sheet and customizes page numbering and styling. Core structure can be
represented generically; exact numbering, tabs, and custom sheet behavior
must not be promised for every module. The tools should not invoke private
sheet preparation methods or depend on which journal window is open.

Official v14 references:

- [Folder data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html)
- [Journal entry data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryData.html)
- [Journal page data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageData.html)
- [Page text data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageTextData.html)
- [Relative UUID resolution](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuidSync.html)

## Proposed first-version tools

The initial implementation now follows these proposals. See
[the implemented contracts and API dependency record](../journal-tools.md)
and the actual MCP descriptions for finalized inputs, continuations, category
and heading enumeration, limits, and source-reading behavior.

These sections record the design rationale. All operations run in
Foundry's browser runtime through explicit RPC handlers. Python validates
inputs and responses and handles transport errors; it does not mirror world
data or maintain a separate journal index.

The Foundry integration must comply with the public API requirement in
`AGENTS.md`. Keep a documentation reference and supported version for the
Foundry members used by each handler. If reproducing part of a custom sheet's
view requires unsupported internals, return the supported core hierarchy and
state that presentation limitation rather than adding a fragile dependency.

### 1. `get_journal_tree`

Get a hierarchical directory view from the root or a selected folder. Inputs:
optional `folder_id`, a depth bound, and continuation information when needed.
An omitted folder means the root, including unfiled entries.

Return nested folder nodes containing child folders and entry summaries in
directory order. Each node includes its kind, name, ID, containing folder ID,
and ordering information. Entry nodes also include UUIDs and text/non-text
page counts. Include the selected root's path as IDs and names. Empty folders
remain visible when present in the GM directory tree.

Provide enough depth by default to show folders, subfolders, and their entries
together when the response fits. A depth/size boundary must distinguish an
unexpanded folder from an empty folder and include a way to retrieve its
remaining children. Preserve ancestry in every partial response. Do not
silently omit branches or flatten them into a disconnected ID list.

For example, the A/B test data should be understandable as:

```text
Journal directory
├── A/
│   ├── B/
│   │   └── entry in B
│   └── entry in A
├── Seven Dooms for Sandpoint/
│   ├── Frontmatter
│   ├── Ch 1: Bones and Ashes
│   └── …
└── This is a test entry
```

This tool follows actual containment. It does not invent chapters or group
entries based on their names. Search provides access across all folders
without requiring the LLM to enumerate the complete tree first.

### 2. `get_journal_contents`

Inputs: `journal_id`, plus pagination.

Return the entry's name, UUID, folder path, and a table of contents resembling
the journal sidebar. Include ordered category groups where available and
uncategorized pages; without categories, return the ordered pages directly.
Each page node contains ID, UUID, name, type, sort value, title level, title
visibility, and optional category ID.

Include bounded heading trees beneath text pages, with heading text, level,
and anchor from `page.toc`. Headings are section references within that page,
not new journal documents. Page-title levels remain explicit presentation
metadata rather than fabricated parent-page relationships. The response must
retain group/page ancestry and state where its contents are incomplete.

Include non-text pages with `readable: false`. Text pages have
`readable: true`. Do not return page bodies here. The LLM uses this contents
view to choose a page, then reads its text with `read_journal_page`.

### 3. `search_journals`

Inputs: a nonempty literal `query`, optional `folder_id` or `journal_id`
scope, and pagination. With no scope, search all world journals. Folder scope
includes descendants. Reject conflicting folder and entry scopes.

Search text page names and extracted readable text case-insensitively, with
consistent whitespace normalization. This is text retrieval, not semantic
question answering. Do not require regular expressions, an embedding service,
or adventure-specific fields.

Return one result per matching page, with entry/page names and IDs, page UUID,
folder path, matching fields, match count, and bounded context excerpts.
Use stable document ordering rather than claiming semantic relevance.
Separate total matching pages from the number returned. Multiple appearances
within a long page must not hide matches in other pages.

Search may derive normalized text from HTML solely for matching and bounded
excerpts. Label excerpts as derived search context, not source content.
Do not match arbitrary HTML attributes, UUID IDs, or image filenames as if
they were narrative text. Search visible link labels while retaining their
targets for later reading. Results must state whether more matching pages
or excerpts remain. Search normalization must not alter page-reading output
or supply offsets into that output; return page UUIDs for source retrieval.

### 4. `read_journal_page`

Inputs: a world journal page UUID and an optional continuation position.
Return entry/page names and IDs, folder path, stored text format, and the
unmodified `page.text.content` HTML. For a Markdown-format page, also expose
the original `page.text.markdown` source when present, with explicit field and
format labels. Do not reconstruct HTML from Markdown or replace stored HTML
with another representation. References may be provided separately, while
the original inline notation and markup remain unchanged in the content.

Long pages must be returned in bounded chunks. Return the actual range,
total source length, and the next position, or null when complete. Each chunk
is an exact source substring; concatenating all chunks must reproduce the
stored source exactly. Prefer existing structural boundaries where practical,
but do not parse and reserialize, insert closing tags, wrap fragments, normalize
whitespace, decode entities, or drop source characters. A chunk may be an
incomplete HTML fragment; identify it as such. Keep Unicode boundaries intact.
The LLM follows returned positions rather than calculating offsets itself.
If HTML and Markdown both require chunking, give each source its own explicit
continuation so they cannot be confused.

Include a content revision value. Subsequent chunks should supply the
expected revision; if the page changed, return a clear error asking the
caller to restart reading. Reading and searching must not silently truncate
content or present a partial page as a complete one.

Reject non-page UUIDs, compendium UUIDs, and non-text pages with distinct
errors. A missing document differs from a text page with an empty body.

## Discoverability for a fresh LLM session

The MCP discovery surface must teach this workflow without requiring this
document or any previous conversation:

1. For orientation, call `get_journal_tree()` to see the folder hierarchy and
   entry names. Expand incomplete branches using the selectors/continuations
   in the response. Obtain a `journal_id` from an entry node.
2. Call `get_journal_contents(journal_id=...)` to inspect that entry's ordered
   pages and headings. Obtain a `page_uuid` from a page node.
3. Call `read_journal_page(page_uuid=...)` for the text, following its returned
   continuation until the relevant material has been read.
4. For a known name, phrase, or area code, start with `search_journals(query=...)`
   instead. Search works across the world without prior tree enumeration.
   Read candidate pages using their returned UUIDs and broaden the query or
   scope if needed. Literal search cannot answer a semantic question directly.
5. Cite entry/page names, retain identifiers for follow-up calls, and distinguish
   missing evidence from incomplete retrieval.

### Tool description requirements

Follow the project-wide
[self-documenting MCP tool requirements](../../AGENTS.md#self-documenting-mcp-tools).
For these journal tools, explain the world-journal/GM/text-only scope, metadata
for unreadable media, and the navigation sequence above. Clarify that a page
UUID identifies both its containing entry and the page. The drafts below
apply the shared requirements to this feature; they do not replace them.

### Draft tool descriptions

The following drafts capture the information each tool must communicate.
Replace references to a "returned continuation" with the exact response and
input fields once the contracts are implemented.

**`get_journal_tree`**

> Discover world journals as a directory of folders, subfolders, and entries
> in the connected GM world. Call without a folder ID to start at the root,
> including unfiled entries. Use folder IDs returned in folder nodes to inspect
> a subtree; names and paths are descriptive, not selectors. Results contain
> entry names, journal IDs, UUIDs, and text/media page counts, without bodies.
> Unexpanded branches are marked explicitly and provide continuation
> information. Use an entry's journal ID with `get_journal_contents` to inspect
> its pages. For a known name or phrase, `search_journals` can search the whole
> world immediately. Compendium journals are outside this tool's scope.

**`get_journal_contents`**

> Inspect a world journal's table of contents without reading page bodies.
> Supply the journal ID returned by `get_journal_tree` or `search_journals`.
> Results include the entry's folder path, ordered pages, category groups
> where present, and bounded heading outlines. Page nodes contain names and
> full page UUIDs for `read_journal_page`. Headings belong to their page;
> they are not separate documents. Media pages are listed but marked unreadable
> by the text tool. Follow returned continuation information when the contents
> are incomplete. A journal can have no readable pages; that is different
> from a missing journal.

**`search_journals`**

> Find text pages containing a literal, case-insensitive phrase in their name
> or readable text. With no scope, search all world journals across folders,
> including GM-only text. Use a folder ID to include its descendants or a
> journal ID to search one entry; do not supply both. Obtain those IDs from
> journal navigation results. Search link labels and readable headings, not
> HTML attributes or image contents. Results identify matching entry/page
> names, folder paths, journal IDs, page UUIDs, and bounded excerpts. Read
> full context with `read_journal_page`; excerpts are not complete pages.
> Follow continuations to see all matching pages. No matches means this
> literal query found no matching text in the selected scope; try alternate
> wording or broader scope before concluding the information is absent.
> Use names or distinctive phrases rather than a whole natural-language
> question. For example, search `Ripnugget` or `E1`.

**`read_journal_page`**

> Read a text page from a world journal in the connected GM world. Supply
> the full page UUID returned by `get_journal_contents` or `search_journals`,
> not a bare page ID, entry UUID, name, or folder path. Results include source
> names/path and the exact stored HTML, preserving markup and inline Foundry
> notation. Markdown-format pages also expose original Markdown when present,
> with separate format labels. No HTML-to-text conversion is performed for
> reading. Long source content arrives in bounded chunks: follow the returned
> continuation and revision information until complete, without calculating
> positions yourself.
> Chunks are exact source fragments and may contain incomplete HTML elements;
> concatenating all chunks reproduces the source without inserted markup.
> If content changes during reading, restart the page using the reported
> recovery instructions.
> Images, maps, PDFs, video, and compendium pages are unsupported. An empty
> text page returns empty content; missing or unsupported pages return distinct
> errors. References do not execute macros, open sheets, or fetch other
> documents. Cite entry and page names when using this evidence in an answer.

### Response and error guidance

Responses should make the next valid call clear through typed node kinds,
stable selectors, readable names/path context, completeness indicators, and
continuation data. Avoid ambiguous fields such as an unlabeled `id` when the
response contains folders, entries, pages, and headings together.

Errors should explain recovery using the tool contract, without exposing
Foundry internals or making the caller reverse-engineer an exception. For
example: an invalid page selector points to the tool that supplies page UUIDs;
a deleted entry directs the caller to refresh navigation/search results;
unsupported media explains the text-only boundary; changed content explains
how to restart reading. Do not silently substitute similarly named documents.

## Text and reference handling

- Return stored HTML unchanged, including headings, paragraphs, lists, tables,
  emphasis, classes, attributes, entities, whitespace, and inline Foundry
  notation. Preserve image tags within text-page HTML without fetching images.
  The LLM interprets the source; do not strip or rewrite markup.
- Derived search excerpts and heading labels are navigation aids, not a
  replacement for source HTML. Search extraction should preserve readable
  boundaries between blocks and heading spans without splitting words that
  contain inline formatting. Do not depend on publisher-specific CSS classes.
- Keep source HTML separate from any resolved reference metadata. Resolving
  a link must not rewrite its target or label in returned source content.
- Preserve GM text and read-aloud text. Do not filter by player visibility;
  this feature is for preparation in the connected GM browser.
- Preserve Foundry link labels and expose raw targets, resolved world-journal
  UUIDs when possible, and heading anchors. Keep unresolved references
  explicit. Relative resolution must use the source page as context.
- Keep check, roll, and other Foundry inline notation as inert text. Do not
  enrich content in a way that executes macros, rolls dice, fetches embeds,
  or opens sheets.
- Do not fetch image URLs or infer facts from image filenames. Image-only
  content remains outside the feature's scope.
- Bound all output, including names, paths, excerpts, and references, by the
  serialized UTF-8 response size. Pagination must account for the existing
  bridge's message limits, not just a record count. Any metadata clipping
  must be explicit, and stable IDs must remain intact.
- Require a ready GM runtime. Missing browser, deleted document, unsupported
  page type, changed content, and invalid parameters need actionable errors.

## How the example questions would be investigated

- **Ripnugget's campaign role:** search the entire world for the name, page
  through every matching result, read relevant pages, and follow journal
  references. Distinguish written developments from a proposed narrative.
- **Area E1:** search text and headings, read candidate pages, and distinguish
  the area's description from pages that merely refer to it. If several
  locations use the same code, use context or ask for the intended scope.
- **Chapter 2 events for level 4 and below:** identify the intended entry,
  inspect its contents, and read its introductory guidance and relevant events.
  Do not assume a chapter number determines level or that every event has
  a structured level field. Report missing textual evidence.
- **Expected level for Chapter 7:** inspect chapter introductions and campaign
  guidance; search for advancement information. Do not assume the answer is
  inside the chapter entry or that chapter and character levels coincide.
- **Chapter 3 summary and recurring NPCs:** read the relevant entry in order,
  then search earlier/later material for the identified names. Label the
  search coverage and uncertainty; a limited result page does not prove
  that a character never appears elsewhere.

## Validation for implementation

Establish the current bridge behavior with existing tests before extending
it. Add focused tests for the new behavior as it is implemented, covering:

- Nested, empty, and root-level folders; unfiled entries; duplicate names.
- Directory tree order, bounded subtrees, and explicit unexpanded branches.
- Journal contents grouped by category, ordered pages, heading trees, and
  section anchors, independent of open windows and custom sheet styling.
- Arbitrary entry/page names and documents that do not represent chapters.
- Page ordering that differs from collection order, including equal sort values.
- HTML and Markdown, empty text, mixed text/media pages, and v14 categories.
- Headings, nested inline formatting, lists, tables, and adjacent spans.
- Literal query punctuation, Unicode, multiple occurrences, folder descendants,
  and search completion across multiple result pages.
- Absolute/relative UUIDs, heading anchors, broken links, and non-journal links.
- Large text and metadata, byte limits, chunk continuity, and content changes.
- Exact source preservation and chunk reassembly for HTML and original Markdown,
  including entities, whitespace, inline notation, attributes, tables, and
  Unicode. Verify derived search text never replaces the source response.
- Invalid selectors, wrong document types, missing documents, and RPC failures.
- Review Foundry dependencies against official documentation and public API
  annotations, including deprecations. Runtime existence or a passing mock is
  not sufficient compatibility evidence.
- Inspect the actual MCP tool discovery output for useful descriptions,
  parameter constraints, defaults, and identifier/continuation guidance.
- Exercise orientation, scoped search, page reading, and continuation from a
  fresh client using only discovered contracts and returned data. Verify this
  also works with arbitrary document names and duplicate names.

Use local JavaScript/Python tests plus live checks in the development world.
Do not alter campaign data to produce test fixtures. The A/B examples and
published adventure provide live verification samples; synthetic fixtures
must cover layouts that this adventure does not use.

Opening a cited page in the existing game tab remains a possible follow-up.
It is independent of reading/searching and is not required for the initial
question-answering feature.
