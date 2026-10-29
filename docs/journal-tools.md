# Journal preparation tools

Version 2.0.0's [version-two selective reads](selective-reads.md) change
get_journal_contents, search_journals and read_journal_page to compact defaults.
Outlines, excerpts and references now require explicit `select` fields. Existing
source, search and resolution semantics below still apply.

Five read-only MCP tools let a fresh LLM navigate and investigate world journals
through the connected GM browser. They include GM-only text. Compendium journals
and reading images, maps, PDFs, or video are outside this version's scope.

| Tool | Start here when | Next step |
| --- | --- | --- |
| `get_journal_tree` | You need orientation in folders and entries | Expand folder nodes or inspect a returned journal ID |
| `get_journal_contents` | You want an entry's pages and heading outline | Read a text page's returned UUID |
| `search_journals` | You have a name, phrase, or area code | Read candidate pages in full context |
| `read_journal_page` | You have a page UUID | Continue source chunks, then cite entry/page names |
| `resolve_journal_reference` | You want one Actor/Item reference | Follow its returned reader call |

Tool descriptions and input schemas provide the precise parameters, defaults,
response fields, and recovery instructions. They are available in ordinary MCP
discovery, independently of the development-only JavaScript console.

## Selected Actor and Item references

Complete, untruncated Actor/Item-capable UUID references supply `resolve_next_call`
with originating `page_uuid`, exact `target` including anchor, and selected
`source`. Ordinary fragment reads never eagerly hydrate Actor/Item references.
Legacy journal fields and source/revision/continuation behavior remain unchanged.

Resolution verifies current source membership, then uses public asynchronous
`fromUuid(uuid,{relative:page})`. Results contain `foundry_version`, `page_uuid`,
`source`, `target`, `anchor`, `status`, `identity` and `next_call`. Resolved named
canonical identities supply complete `read_actor` or `read_item` arguments;
synthetic targets retain actual token context. Anchors are not reader selectors.
Names/labels are never implicitly resolved; search yields bounded candidates.

Missing, denied, unsupported, outside-scope and unverified outcomes withhold
identity and selectors. `ReferenceChanged` requires rereading source. Reference
failures stay local. No target source, imports, writes, rolls, enrichment or
recursive expansion occurs. PF2e-specific target admission is verified on
Foundry14.369/PF2e8.6.1; ordinary journals remain available on other systems.

Metadata completeness remains fragment-scoped, with at most20 references.
Reconstruct adjacent source fragments before following split notation; truncated
targets have no resolver call. Resolution is one selected reference, no pagination,
bounded to48000 UTF-8 JSON bytes. Source membership and permissions are rechecked
after awaits. See the tool description for exact errors and recovery.

## Navigation and completion

The directory response is nested and includes unfiled entries and empty folders.
Names longer than 256 UTF-16 units are clipped with explicit truncation flags;
stable document identifiers are preserved. Folder nodes that exceed depth or
expansion limits contain an `expand` selector. Use it in a new call without a
cursor. Root ordering is alphabetical; folder contents follow the documented
alphabetical/manual sorting field, with folders before entries. This represents
core document organization, without custom sheet styling or UI filter state.

`complete` concerns the current response's pagination, not every descendant.
The tree additionally reports `tree_complete`. Journal contents additionally
reports `headings_complete` per page and `groups_complete` for categories.
Follow `headings_next_call` or `categories_next_call` in a new call to enumerate
those outlines. Category groups reference the page UUIDs in the current response;
pages carry their own category names and IDs. Heading outlines include parent
anchors and ancestor anchors, so indentation survives pagination. Page title
levels are presentation metadata, not parent-page relationships.

Every paginated response supplies `next_cursor`, or null when complete. Pass
it back unchanged with the same scope inputs. Cursors encode positions and a
data revision; changed data returns `ContentChanged` and requires restarting
without a cursor. Cursors are continuation hints, not authorization tokens.
The browser remains the source of truth; there is no server-side journal cache.

Responses are bounded to 48,000 UTF-8 JSON bytes before RPC framing. Count and
depth limits also apply. An oversized individual metadata record produces an
explicit `ResponseTooLarge` error instead of silently omitting it.

## Reading source and searching

`read_journal_page` returns exact stored HTML from `page.text.content`. It does
not strip tags, normalize whitespace, decode entities, enrich text, run inline
commands, or fetch embedded images. `source="markdown"` returns original
`page.text.markdown` when stored. The editor's `stored_format` and the selected
source are separate fields. Missing HTML is reported explicitly as an absent
source with empty content, rather than treated as a missing page.

Long source content is sliced into exact fragments with UTF-16 positions.
Unicode surrogate pairs remain intact. Fragments may split HTML elements; the
tool adds no wrapper or repair tags. Concatenating all fragments reproduces the
source. HTML and Markdown use separate continuations. A page revision covers
both stored sources, so edits during reading cannot silently mix revisions.

Bounded reference metadata resolves complete world-journal UUID notation within
each fragment, including relative links against the source page. Heading anchors
remain separate from page UUIDs. Non-journal/compendium references are not fetched;
broken references remain unresolved. Reference metadata can be incomplete or
clipped independently of the unchanged source, with explicit flags. Notation
split across chunks remains available in the reassembled source.

Search is a case-insensitive literal substring search over page names and
derived HTML text, using normalized whitespace. When HTML is absent, original
Markdown is searched as text. Search skips script/style content, searches UUID
link labels rather than targets, and excludes arbitrary HTML attributes and
image filenames. Excerpts are derived context, not source offsets. Read the
stored HTML to interpret formatting, table structure, and full evidence.

Results contain one match per page, up to three excerpts, and explicit matching
page/occurrence counts. They are ordered by entry name and page ordering rather
than semantic relevance. An empty result only establishes absence of the literal
query in the selected scope; try alternate wording or broader scope as needed.
Facts such as character levels and narrative relationships are interpreted by
the LLM, not inferred from naming conventions or publisher-specific markup.

## Foundry public API dependencies

The module builds hierarchy from documented relationships. It does not read
`game.journal.tree`, private/protected sheet methods, cached sheet state, UI DOM,
or publisher flags. Standard browser APIs handle hashing, HTML search parsing,
and JSON size measurement. Web Crypto is used where available, with a nonsecure
HTTP-compatible change-marker fallback; neither makes cursors credentials.

The following official v14 references support the dependencies. Their v13
counterparts were checked for the declared minimum version; indexed v13 docs
can differ from older builds. Live verification was performed on v14.369 only.

| Dependency | Public documentation |
| --- | --- |
| `game.ready`, `game.version`, `game.user`, `game.folders`, `game.journal` | [Game](https://foundryvtt.com/api/v14/classes/foundry.Game.html) |
| Collection `contents`, `size`, `get` | [Collection](https://foundryvtt.com/api/v14/classes/foundry.utils.Collection.html) |
| Folder `type`, `folder`, `name`, `sorting`, `sort` | [Folder schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html) |
| Entry `folder`, `pages`, `categories`, `name`, `sort` | [JournalEntry schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryData.html) |
| Page `name`, `type`, `category`, `title`, `sort`, `text` | [JournalEntryPage schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageData.html) |
| Category `name`, `sort` | [JournalEntryCategory schema](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryCategoryData.html) |
| Document `id`, `uuid`, `parent`, `documentName`, `inCompendium` | [Document](https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html), [JournalEntryPage](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntryPage.html) |
| Page `toc` and heading order/children/anchors | [JournalEntryPage](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntryPage.html#toc), [heading schema](https://foundryvtt.com/api/v14/interfaces/foundry.types.JournalEntryPageHeading.html) |
| Relative world document resolution | [fromUuidSync](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuidSync.html) |

## Validation

Focused tests cover hierarchy, duplicate names, ordering, categories, heading
ancestry, literal scoped search, source reassembly, byte limits, references,
changed-data continuations, errors, RPC dispatch, and MCP discovery schemas.
Live checks used the A/B fixtures and published adventure without modifying
world documents. They verified all 21 entries, Chapter 2's 27 ordered pages,
24 Ripnugget matching pages across six entries, area E1, original Markdown,
and SHA-256 equality after reconstructing a 53,806-unit HTML page.

After installation or tool registration changes, reconnect your MCP client.
For this repository, resume through `./scripts/codex-dev.sh resume --last` for
development or `./scripts/codex.sh resume --last` for ordinary tool use.
