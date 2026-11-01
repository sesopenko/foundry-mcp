# Journal authoring and GM writing guidance

WISH-010 adds GM-guided world journal authoring after v2.5.0, unreleased.
The tools use the existing readers' canonical folder/entry IDs and page UUIDs,
with bounded text writes and explicit ownership previews. Compendiums remain
read-only. [Image browsing and embedding](journal-images.md) extend this workflow
in the same unreleased source tree.

## Authoring workflow

1. Read `get_writing_guidance`, follow its GM section and obtain any permission
   it requires before changing protected official material. A GM instruction to
   create session notes does not imply permission to rewrite an official book.
2. Discover the destination with `get_journal_tree` and pages with
   `get_journal_contents`. Read existing prose with `read_journal_page`.
3. Get `get_journal_write_context({target: ...})`. A target is exactly
   `{kind:"folder",folder_id}`, `{kind:"journal",journal_id}` or
   `{kind:"page",page_uuid}`. Names never select documents.
4. Call `write_journal` with a unique `request_id`, `gm_authorized:true`, the
   complete `guidance_timestamp` from step 1 and one typed `action`. The assertion
   confirms the actual GM instruction and any additional permission required by
   the guide; it cannot infer permission from the prose. The current exact guide
   is checked again in the browser before mutation.
5. Follow the compact receipt's `read_next_call` and verify the result. Get a new
   context before a subsequent edit. `ContentChanged` requires rereading and
   reconsidering; `GuidanceChanged` requires fresh guidance and reconsideration.

All authoring/context/options calls require a ready GM browser on Foundry14.
They use core documents and have no PF2e-specific interpretation. The shipped
module's overall compatibility declaration still applies. The live baseline is
Foundry14.369/PF2e8.6.1; this is not a promise about other core builds.

## Writing actions and receipts

`write_journal` exposes a discriminated `action.operation` enum:

| Operation | Required selectors/content | Optional changes |
| --- | --- | --- |
| `create_folder` | `name` | `parent_folder_id`, `parent_revision`, `color`, `sorting`, `sort` |
| `update_folder` | `folder_id`, `expected_revision` | `name`, `parent_folder_id`, `parent_revision`, `color`, `sorting`, `sort` |
| `create_journal` | `name` | `folder_id`, `parent_revision`, `sort` |
| `update_journal` | `journal_id`, `expected_revision` | `name`, `folder_id`, `parent_revision`, `sort` |
| `create_page` | `journal_id`, `parent_revision`, `name`, `content` | `type:"text"`, `sort`, `format` |
| `update_page` | `page_uuid`, `expected_revision` | `name`, `content`, `mode`, `sort`, `format` |
| `embed_image` | `page_uuid`, `expected_revision`, browsed `image`, `alt` | `width`, `height`, `position`, `anchor` |
| `set_ownership` | scope and `expected_revision` from ownership preview | `all_players`, individual `players` |

Omit update fields to preserve them. Null parent/folder moves to root; a non-null
destination requires its context revision as `parent_revision`. Colour is
`#RRGGBB` or null. Folder sorting is `alphabetical`/`manual` (stored `a`/`m`).
Manual `sort` is a signed32 integer; lower values come first, and equal values
retain Foundry's tie ordering. New entries/pages default to sort0. Read stored
sorts before placing an item; no automatic renumbering of siblings occurs.
Names contain 1–256 nonblank Unicode characters. Cycles/deep folder ancestry
are rejected. Creation does not import compendium documents.

The GM's text “tab” maps to an embedded `JournalEntryPage`, not a separate
writer-only hierarchy. Foundry14 categories are distinct reader grouping nodes;
these actions do not create/rename categories. Page `type` is an extensible enum
initially accepting only `text`. Non-text pages can be identified in context,
but their content cannot be edited here.

Each supplied `content` fragment is limited to 16,000 UTF-8 bytes, with a resulting
page limit of 1,000,000 UTF-16 units. `mode` defaults to replace; `append` preserves
existing HTML and appends only the new fragment. Appending to Markdown is
rejected. Explicit replacement sets HTML format and clears the old Markdown
source; omitted content preserves it. Sibling pages remain unchanged.

The HTML subset includes paragraphs/divs/spans, headings 1–6, line breaks,
emphasis/underline/strike/sub/sup, blockquotes/pre/code, unordered/ordered lists,
horizontal dividers, simple tables and safe links. Table colspan/rowspan is 1–100.
Links allow HTTP, HTTPS, mailto, relative paths and anchors, with no controls or
whitespace in URLs; href is bounded to 2,048 characters, title to 512. No event,
class/data attributes, scripts, iframes, images or arbitrary CSS declarations.
Raw image markup is rejected; use `embed_image` with a browsed source instead.
Immediate inline rolls are rejected. Deferred PF2e notation should come from the
verified PF2e builders when that system is active; these APIs do not roll dice.

Limited CSS properties are text-align, font-size, font-family, font-weight,
font-style, text-decoration, color and background-color. Raw journal font sizes
must be 1–200pt; other CSS dimensions/units are rejected. Optional `format` wraps
only the supplied fragment in a styled div. `font_size` small/normal/large/huge
maps to 10/12/18/24pt; custom requires `custom_size_pt` in 1–200. `font_color` uses
`#RRGGBB`. `font_family` must be a loaded family from
`get_journal_authoring_options({kind:"fonts"})` and fit the supported letters,
numbers, spaces, underscores and hyphens CSS subset. Unsupported unusual font
names return `UnsupportedFont`; omit that choice. Discovery loads no fonts and
does not promise equal availability on every player's browser.

Regular writes return `request_id`, `status` (created/updated/already_applied),
named canonical `identity`, `revision` and `read_next_call`. Contexts return
identity/revision, stored `sort`, `ownership_default` and the same reader
follow-up. Names over 256 codepoints are clipped with `name_truncated:true` in
responses; selectors remain exact. No response repeats the page prose. Inputs
and outputs are validated at actual MCP discovery/invocation boundaries;
unknown fields and invalid combinations fail before reads/writes.

## Ownership and player discovery

`get_journal_authoring_options({kind:"players"})` returns non-GM `user_id,name`
records, including offline users. It exposes no broader user administration or
Show GM Users. Both player and font discovery default to 10 entries (1–100),
8,000 JSON bytes (maximum48,000). Responses contain kind/world_id/revision,
entries/total/complete/next_cursor. Return the exact next_cursor with the same
kind; changed lists/worlds require restarting. Continuation binds the list
revision, not the count/byte bound. Discovery stops at 10,000 options.

Before changing ownership, call `get_journal_ownership_context` with one named
canonical `target`. Folder targets mean existing directly contained journals;
`recursive:true` includes descendants. A `journal_ids` subset can narrow a folder.
No folder ownership field, inherited folder ACL or future-entry policy is created.
Default `limit:10` is a hard target bound (maximum100); an oversized scope reports
its count and requires a smaller subset or raised bound. There is no silently
truncated preview. World enumeration is bounded to10,000 journals/folders;
larger worlds can select individual journal targets.

Optional `user_ids` (maximum 100) selects stored player overrides and current
OBSERVER checks. Default[] avoids repeating the whole user roster. Preview
returns named target/revision/count/recursive, entries and limitations. Each
entry includes identity, `ownership_default:{present,value?}` and selected
`players:[{user_id,present,value?,can_observe,parent_can_observe}]`. Absent differs
from explicit None=0 and inherited=-1. `parent_can_observe` is null except for
pages, where it checks the containing journal. These are current public permission
checks, not a guarantee of final rendered audience. Limited is not full text
access; Observer is the reading level and Owner permits editing.

Copy the preview's revision to `set_ownership.expected_revision` and repeat
identical target/recursive/journal_ids/user_ids/limit. `all_players` changes only
the default. `players:[{user_id,level}]` changes selected overrides. Levels
`no_change`, `none`, `limited`, `observer`, `owner` mean preserve/0/1/2/3. No Change
is an operation instruction, not INHERIT=-1. Other overrides remain intact, so
All Players does not erase individual choices. GM IDs are rejected as targets;
entry/page writes explicitly retain OWNER for every GM. Newly created journals
default to player-private, and text pages default to inherited ownership.

An ownership batch returns request_id/status/count/entries, with per-document
identity/status and error on failure. It stops at the first failure: earlier
results remain updated, that result is failed (possibly uncertain), and later
results are not_attempted. Batch status is complete or partial. Inspect the
documents, get a fresh preview and explicitly select remaining targets before a
new operation. Do not blindly redo completed targets under a new request ID.
The full receipt's byte budget is checked before any batch mutation.

## Concurrency, retries and limits

`request_id` is 16–64 letters/digits/hyphens and identifies one exact operation.
Concurrent identical requests coalesce. Stable create IDs plus persisted module
receipt flags prevent duplicate creation/repeated appends after module reload.
Reusing a request ID with different input is `RequestConflict`. A timeout is
`WriteOutcomeUnknown`: read/reconcile first, then reuse identical input if
appropriate. A changed guide still requires reconsideration; never treat retry
identity as permission to ignore new GM instructions.

Receipts are retained up to 1,000 requests per document and per browser session.
`WriteHistoryFull`/`WriteLedgerFull` requires GM reconciliation, not automatic
flag deletion. Same-session batch retry returns its original outcome. After
reconnect a wholly completed batch can be recognized by flags; a partly changed
scope requires reconciliation and a new explicit preview of remaining targets.

All response budgets default to 8,000 compact UTF-8 JSON bytes, maximum 48,000.
No content is silently truncated. Context/ownership preview revisions bind
relevant source, hierarchy and (for ownership) user roster, but provide no
distributed lock or transaction across GM clients. Stale observations are
rejected; a simultaneous GM update can still race a write under core Foundry
persistence semantics. Deletion and arbitrary document patches are excluded.

## GM configuration

The module's world settings include **Edit writing guidance**, restricted to
GMs. It opens a native Foundry rich-text editor for persistent HTML instructions,
such as which adventure folders are official source and must not be edited
without explicit GM permission. Save writes the HTML and UTC save time together
under the world-scoped `foundry-mcp.writingGuidance` setting. The guide is limited
to 12,000 UTF-8 HTML bytes. Saving it does not reconnect the browser bridge.

Configuration, rendering and saving check GM access. A stale editor snapshot is
rejected rather than silently replacing a newer guide. Saves in one browser are
serialized and advance the timestamp even when the clock has not advanced.
Foundry settings do not provide distributed compare-and-swap; simultaneous GM
clients retain core world-setting persistence semantics. World settings are not
a confidential secret store; hiding configuration from players does not make
the stored value unreadable to player clients.

## Unified retrieval

`get_writing_guidance({})` requires a ready authenticated GM browser on core14.
It returns two separately labelled sources: exact **GM-authored instructions**
and HTML paragraphs containing the original user-supplied **Pathfinder/Paizo
writing conventions**. The latter retains
`attribution_status: "user_supplied_publication_unverified"`; it is not the PF2e
wiki Style Guide, and neither returned section is LLM-authored. GM guidance is
critically important and must be followed, including obtaining the permission
it requires before altering protected official material. Free-form prose is not
an automatically enforced folder ACL.

Full/changed results contain `world_id`, `changed: true`, `timestamp`,
`gm_status`, `message`, `gm_guidance` and `pathfinder_guidance`. The GM section
contains `source`, exact `html` and `importance: "critical"`. The Pathfinder
section contains `source`, `html` and the attribution status.

Copy the complete `timestamp` object into `since` on a later call. Its
`saved_at` is the GM's UTC save time and its `revision` binds the world, exact
HTML/time and bundled style copy. A save date alone cannot detect a change in
the bundled guide. Matching stamps return `changed: false`, the message
“No change since supplied timestamp,” and omit both guidance sections.
Changing only the bundled style or selected world still returns changed copy.

`gm_status` distinguishes `not_configured` (null HTML/save time), `empty`
(saved empty HTML string) and `configured`. A browser/permission/source error
is not an empty guide. Reads are observations, not locks; recheck before later
mutations. The LLM cannot write this configuration through MCP.

The default `max_bytes` is 8,000 compact UTF-8 JSON bytes; the maximum is 48,000.
An oversized guide returns `ResponseTooLarge`; increase the budget explicitly.
The copy is never truncated. Unknown inputs, malformed timestamp records and
invalid bounds fail before RPC. Invalid stored HTML/time is
`InvalidFoundryResponse`; the GM should inspect settings and component versions.

## Migration

The old `get_pathfinder_writing_style_guide` discovery tool is replaced by
`get_writing_guidance`. Refresh client discovery. The original passage is
preserved as HTML paragraphs in `pathfinder_guidance.html`, alongside its
unchanged attribution caveat. Retrieval now requires the GM browser because it
must also read that world's instructions. Chat sending recommends reading the
combined guide before authoring content.

## API evidence

The official v14 public
[ClientSettings](https://foundryvtt.com/api/v14/classes/foundry.helpers.ClientSettings.html)
documents `register`, `get`, `set` and restricted `registerMenu`.
[DialogV2](https://foundryvtt.com/api/v14/classes/foundry.applications.api.DialogV2.html)
hosts the module's own content; no Foundry UI DOM is inspected.
[HTMLProseMirrorElement](https://foundryvtt.com/api/v14/classes/foundry.applications.elements.HTMLProseMirrorElement.html)
provides public `create`, `save` and `value`. Grounded Docs v14 documentation was
checked on 2026-10-31 before implementation. Core settings require no PF2e schema
or private system API.

Journal mutations use public
[Document](https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html)
`toObject(true)`, `testUserPermission`, `getFlag`, `create`, `update` and
`createEmbeddedDocuments`, with documented
[keepId](https://foundryvtt.com/api/v14/interfaces/foundry.abstract.types.DatabaseCreateOperation.html)
creation options. Identity/source fields come from
[JournalEntry data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryData.html),
[page data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.JournalEntryPageData.html)
and [Folder data](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html).
The public
[FontConfig](https://foundryvtt.com/api/v14/classes/foundry.applications.settings.menus.FontConfig.html#getavailablefonts)
loaded-family API was checked in Grounded Docs14 and the live baseline. No sheet
preparation state, internal methods or publisher implementation details are used.

## Guide verification — 2026-10-31

The full host suite passed 632 Python tests (one existing skip) and 657
JavaScript tests. Four subsequent focused verifier-safety tests establish
wrong-world rejection, exact original-setting restoration, refusal to overwrite
unrelated GM changes and marker validation before live execution.

`scripts/writing-guidance-live-check.py` completed 12 tool calls plus discovery
in the existing core14.369/PF2e8.6.1 test world. It opened the registered restricted
menu, verified a native `PROSE-MIRROR` element, saved through the actual UI, checked
that its timestamp advanced and read the result through MCP. Changed/unchanged
and saved-empty guidance were distinguished. A long guide failed the default byte
budget and was retrieved exactly with an explicit larger budget. The original
setting was restored exactly; no other settings or game documents were changed.
Browser console errors were zero before and after the check.

| Guidance-stage scenario | Calls | Compact UTF-8 JSON bytes | Complete |
| --- | ---: | ---: | --- |
| Default short GM guide plus Pathfinder copy | 1 | 1,758 | Yes |
| Matching timestamp, no repeated copy | 1 | 238 | Yes |
| Explicit long guide, `max_bytes: 48000` | 1 | 12,941 | Yes |

The same probe measured 36 tools/190,380 catalog bytes and a 6,220-byte guide
description/schema record at this stage. Before the unified guide, the catalog
contained 36 tools/185,158 bytes. Replacing the style-only tool adds GM guidance,
change checks and typed output; it is not equal-content compression. Counts and
bytes will be remeasured for the completed journal-writing interface. Bytes are
not billed tokens, and no provider token usage was measured.

## Authoring verification — 2026-10-31

The final full host suites passed 653 Python tests (one existing skip) and 676
JavaScript tests.

`scripts/journal-authoring-live-check.py` passed 41 calls plus discovery in the
same existing test world. It created two temporary folders, one handout and two
text pages; read back exact reader identities/HTML; appended once across a retry;
rejected a stale edit; renamed/reorganized the entry and folder; and applied
recursive contained-journal ownership with player follow-up checks. A loaded
font was selected through the public font API. A page's explicit None override
removed its player's OBSERVER access while its parent remained observable. Public
permission checks retained every GM's OWNER access. Basic links, tables, lists
and dividers persisted and rendered in an owned DOM element. Existing journal,
folder and user source fingerprints were unchanged; all marked fixtures were
removed. Offline fixtures reject wrong-world operations and refuse cleanup when
an unrelated document appears inside a marked folder.

| Authoring scenario | Calls | Compact UTF-8 JSON bytes | Complete |
| --- | ---: | ---: | --- |
| Player discovery default | 1 | 216 | Yes |
| Loaded font discovery default | 1 | 393 | Yes |
| All 8 loaded fonts, one per page | 8 | 2,185 | Yes |
| Journal creation receipt | 1 | 460 | Yes |
| Exact authored page readback | 1 | 938 | Yes |
| Selected ownership preview | 1 | 965 | Yes |

The catalog now contains 40 tools/233,894 compact JSON bytes. Records for context,
write, options and ownership-preview tools measured 7,856/22,743/3,885/8,954 bytes.
The expansion supplies actual typed authoring contracts, not equal-content
savings. Optional user selection keeps ownership previews small; a bounded heavy
Unicode-name test proves oversized receipts fail before mutation. A long guide's
explicit expansion is measured above. No provider token counts were measured.

Focused regressions first demonstrated two implementation defects: raw HTML
could bypass the custom point-size bounds, and an empty ownership batch's
vacuously true replay check could bypass stale-preview rejection. Each same
failing test passed after its root cause was corrected; chat's existing HTML
profile remains unchanged. Ownership tests also cover no-change preservation,
GM rejection, partial failures, parent ownership changes, retries after reload,
byte bounds and folder cycles. Category authoring, images and distributed
transactions are not claimed by this implementation.
