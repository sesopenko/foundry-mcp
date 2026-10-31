# Read-only compendium references (WISH-009)

Implemented in version 2.5.0. Update both the
server and browser module, then reconnect clients to discover the new tools.
Verified on the existing `test` world, Foundry 14.369 / PF2e 8.6.1.
Journal handlers require core14 and do not interpret system mechanics; the
installed module still declares PF2e, and live use on other systems is untested.
Existing Actor/Item readers remain PF2e-specific and version-gated.

## Discover, search, read

| Tool | Inputs and useful next step |
| --- | --- |
| `list_compendiums` | Discover Actor, Item and JournalEntry packs together, or filter `document_type`. Optional `query` matches literal pack title/collection. Copy a returned `id`, never a title. |
| `search_compendium_actors` | Existing Actor/Item index search: `pack_ids`, `document_type`, literal `query`, optional supported `types`. Follow named canonical `next_call` to `read_actor` / `read_item`. |
| `search_compendium_journals` | One `pack_id`, literal `query`. Default `field="page_name"` searches embedded text-page titles across entries; no parent ID needed. `entry_name` searches index names only. `text` scans derived page text in that selected pack or optional `journal_id`. |
| `get_compendium_journal_contents` | `pack_id` plus returned `journal_id`: ordered page names, types and UUIDs. Optional `page_id` lists headings; `categories_only` lists categories. |
| `read_compendium_journal_page` | `pack_id`, returned `page_uuid`: exact stored HTML, or original `source="markdown"`. Continue fragments before interpreting complete rules. |
| `resolve_compendium_journal_reference` | `pack_id`, origin `page_uuid`, exact stored `target` from `@UUID[target]`, and `source`: lazily resolve one link to a named journal/Actor/Item and canonical `next_call`. No target source expansion. |

For “DCs by Level,” discover JournalEntry packs, choose a relevant named pack,
then search `field="page_name"`. Entry-name search alone cannot find a page
inside “GM Screen.” For uncertain terminology, inspect compact page names and
selected outlines, or explicitly scan `field="text"` within a selected entry.
Matching is case-insensitive literal substring, not fuzzy/semantic search.
Queries accept 1–200 nonblank characters; empty results say only that this
literal phrase was absent from searched fields in completed scopes.

For action/spell definitions, use the existing `read_item` selection
`{"details":["source","description"]}` and follow `pagination.next_cursor`.
This includes available requirements, activation, rank, time, range, targets,
area, defense, damage, heightening, traditions/traits and publication, together
with complete prose. `limit=100,max_bytes=48000` is an explicit larger request
for a single rules reference; defaults remain compact. Narrow selections must
include `source.attack` for spell range, alongside `source.casting`,
`source.damage`, `source.defenses`, `source.traits`, `source.publication` and
`description` as needed. Identity alone cannot explain rules. Missing/null
fields remain distinct; a definition establishes neither a caster's DC/slots
nor current castability. Treat Wounds' stored passive activation label does not
replace its ten-minute procedure in prose.

## Response and continuation contracts

Requests and responses use Pydantic through the existing typed FastMCP boundary,
with unknown fields rejected and strict primitive types. New tools publish
read-only, nondestructive annotations. No model call performs validation.
Default metadata count is 10; `limit` accepts 1–100, except contents (1–50).
Default `max_bytes=8000`, maximum 48000 compact UTF-8 JSON bytes. These bytes do
not measure billed tokens. Page source defaults to 2000 UTF-16 units, with
`max_chars` 1–20000; a surrogate pair may require two units at a one-unit limit.
Counts, source units, underlying loading and response bytes are separate.

`list_compendiums` returns `foundry_version`, `revision`, `nodes`,
`denied_packs` and `pagination {complete,next_cursor,returned}`. Nodes contain
`id,title,title_truncated,document_type,searchable_fields,next_tool,folder_id,
folder_name`. Immediate public directory-folder context is retained; no
publisher browser, internal pack-folder tree or sheet hierarchy is claimed.
Unreadable packs are omitted and counted. Discovery never loads pack indexes
or documents. Actor/Item `name` means indexed document names only.

Journal search returns `foundry_version,pack,revision,matches,searched_field,
scanned_entries,scanned_text_pages,unsupported_pages,failures,unsearched_entries,
batch_match_count,complete,coverage_complete,next_cursor,limitations`.
`pack` is `{id,title,title_truncated,document_type}`. Matches retain
`journal_id,journal_uuid,journal_name,journal_name_truncated,page_id,page_uuid,
page_name,page_name_truncated,matched_field`; entry-only matches have null page
fields. `select.excerpts=true` adds one bounded `excerpt` and
`excerpt_derived=true`. HTML text traversal excludes script/style/template,
attributes and UUID IDs, preserving link labels; Markdown uses its stored text.
Search excerpts are derived context, never exact source or source offsets.
Names are capped at 256 characters with truncation flags (shared journal
summaries count UTF-16 units); identifiers are preserved. Duplicate names remain
separate canonical references.

Page-title and body scans load at most `max_entries=10` (1–10) complete entries
per call, including on match continuations. They process at most 10000 pages per
entry or fail `WorkLimit`. Foundry loads **all embedded pages of each entry**;
these limits do not cap a single document's network bytes or load latency.
Calls have a 30-second RPC timeout. Index retrieval has no public server offset
bound. Entry-name mode does not load documents. No automatic all-pack body scan
exists. Media pages are counted unsupported, and denied pages are not named or
searched. Entry failures have `{journal_id,status}`; scans continue with gaps.

`scanned_*`, failures, unsupported counts and `batch_match_count` describe the
current batch, not cumulative totals. `unsearched_entries` counts later entries;
matches remaining in the current batch also require continuation. `complete`
means traversal exhausted, even with gaps. `coverage_complete` additionally
requires no failed or unsupported content **in this batch**. Keep gaps from
every response; final-batch success does not erase earlier gaps.

Copy search `next_cursor` unchanged with all original selectors, selection,
count/byte/work bounds. It binds the pack index, current batch revision, match
position and next batch offset. Source/permission changes while a batch loads
abort it. Changes to the current batch/index invalidate its continuation.
Previously exhausted batches are not reloaded or revalidated: restart a full
scan after edits for a new investigation. This is not a whole-pack snapshot.
Failed entries are reported; restart a scan to retry them.

Contents and exact-page responses reuse [world journal processing](journal-tools.md)
with a named `pack` added inside the byte budget. Contents returns
`journal_id,journal_uuid,name,name_truncated,mode,total,revision,complete,
next_cursor` and `pages`, `heading_outline` or `groups`. Default pages retain
`kind,page_id,page_uuid,name,name_truncated,type,readable`; media is unreadable.
`select.headings/categories/presentation/folder_path` adds the corresponding
world-journal metadata. Heading previews stop at 20; retain `pack_id` when
passing returned heading/category selectors to this compendium tool.

Page responses retain `journal_id,journal_name,page_id,page_uuid,page_name`,
name truncation flags, `source,content,source_present,offset,end_offset,
total_chars,offset_units,fragment,revision,complete,next_cursor`. Offset units
are UTF-16 code units. Concatenate `content` in contiguous offset order to
reconstruct exact stored tables, headers, footnotes, entities and notation;
fragments can split HTML tags. Missing HTML is explicit `source_present=false`;
missing original Markdown raises `SourceUnavailable`. `select.source_metadata`
adds format/available sources; `select.references` adds at most 20 complete
fragment-local UUID notations and lazy resolver calls. Split notation remains
in exact source; reference metadata is not exhaustive across split fragments.

The resolver checks that the selected source still contains the exact target,
resolves relative UUIDs through public async `fromUuid`, retains the anchor
separately, and rechecks origin/target access. It returns
`foundry_version,page_uuid,source,target,anchor,status,identity,next_call`.
Only `resolved` includes identity and reader arguments; `missing,denied,
unsupported,outside_scope,unverified` withhold both. World and pack journal
destinations have their appropriate reader; supported PF2e Actor/Item targets
reuse existing canonical/token-context admission. No recursive reading occurs.

Contents/page continuations bind selected entry/page source revisions, names,
pack identity, selections and bounds. Cursor formats are opaque and may change
between builds; restart any older continuation. `ContentChanged` requires
discarding accumulated fragments and restarting. `InvalidCursor/CursorMismatch`
means restore original inputs or restart. Missing pack/entry/page requires
rediscovery; permission errors require an authorized GM; unsupported documents
require selecting JournalEntry/text. Nothing changes permissions to make a
read succeed. Reconnect the existing ready GM for bridge failures.

## API and safety boundary

Core14 documentation was checked through Grounded Docs (`foundry-vtt`, version
14, existing index from October 12), matching runtime major14. Official APIs:
[CompendiumCollection](https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html)
(`collection,title,documentName,folder,testUserPermission,getIndex,getDocument,
getUuid`), [JournalEntry](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntry.html)
(`pages,categories`), [JournalEntryPage](https://foundryvtt.com/api/v14/classes/foundry.documents.JournalEntryPage.html)
(`text,title,sort,category,toc,parent`) and public
[fromUuid](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html).
The schema/permission boundaries match the existing reader implementations;
the documentation index alone does not prove build-specific behavior.

The server remains a validating proxy. No persistent Python content cache was
added; Foundry's documented browser cache may serve `getDocument`. Every call
requires the connected authorized browser. System version alone cannot
invalidate arbitrary world/module pack edits, so it is not used as a cache key.

Only fixed read RPCs are exposed. No imports, document create/update/delete,
pack configuration/permission changes, rolls, enrichment or chat occur. Pack
locking is irrelevant to this protection; unlocked packs receive the same
read-only interface. Future writing tools must independently reject compendium
targets. Arbitrary development execution remains separately opt-in and is not
part of these production tools.

## Verification — October 30, 2026

Deterministic checks cover real JS packets through actual FastMCP discovery and
invocation, strict typed input/output validation, source reconstruction with
Unicode/tables/notation, duplicate names, work/count/byte pagination, default
omissions/explicit expansion, denied/missing/unsupported scope, stale selection
and revision handling, permission changes during loading and mutation rejection.
The module packager includes the new runtime script; container smoke discovery
expects all five new tools. Existing world-journal tests remain applicable.
The full `./scripts/test.sh` run passed, followed by the complete JavaScript
suite after the final Markdown-search correction. The regression first proved
that raw Markdown incorrectly matched UUID target IDs; sharing the established
label/whitespace normalizer made it pass without changing exact source reads.
Module ZIP packaging passed. The final refreshed development browser reported
zero console errors; an earlier restart/refresh overlap had logged socket
reconnect errors that did not recur after the completed restart.

The bounded localhost harness is `scripts/compendium-live-check.py candidate`:
60 calls / 300 seconds maximum; it prints aggregate sizes/checks, never bulk game
data. It verifies Treat Wounds, Fireball, Goblin Warrior, title discovery without
parent IDs, complete fragmented DC source, separate hard-adjustment evidence,
entry navigation and selected body search. Public document/message counts stay
unchanged; mutation-trapping mocks check forbidden API paths separately.
Two early harness assumptions were corrected: the pack title is not simply
“Journals,” and the rarity footnote says “uncommon or rare,” not “rarity.” These
were verifier assumptions, not reader defects; exact source was preserved.

| Scenario | Calls after catalog discovery | Compact result bytes |
| --- | ---: | ---: |
| Treat Wounds pack/search/identity/full rules | 4 | 688 + 1099 + 882 + 5109 |
| Fireball pack/search/identity/full rules | 4 | 529 + 1014 + 985 + 5653 |
| Goblin Warrior pack/search/identity/current statistics and abilities | 4 | 694 + 1156 + 1037 + 7635 |
| DC page pack discovery/title search/exact read | 3 | 449 + 1243 + 2360 |
| Same known DC page in three 600-unit fragments | 3 | 1758 + 1765 + 1150 |
| Known entry: DC Adjustments search/read | 2 | 1244 + 1300 |
| Entry contents first page, default / explicit expanded | 1 each | 3110 / 6862 |
| Complete 61-page entry navigation, default metadata | 7 | 19376 total |
| DC page default / references and source metadata | 1 each | 2360 / 2522 |
| Selected-entry body search with excerpt | 1 | 3255 |
| Fireball range with explicit source evidence | 1 | 1732 |

The final deterministic audit completed 34 operations (including catalog and
two setup/count checks) in 1.044 seconds with all checks passing. This is a
warm-browser scripted measurement, excluding model deliberation. A preparation
workflow reusing discovered Item/page identities needs one full Treat Wounds
read, three DC source fragments and adjustment search/read: six tool calls;
the separate cold lookups above include discovery/search and unnecessary
identity-only samples for comparison. No full pack scan is required.

The original baseline catalog had 30 tools / 138262 compact bytes. The candidate
has 35 / 174131 bytes, an increase of 35869 including improved existing reader
guidance. Existing Item/Actor responses were unchanged in the same scenarios.
These are added capabilities, not claimed equal-content savings. Metadata
expansion is opt-in. Combined text-plus-structured MCP payloads are larger than
the compact DTOs (for example, the DC read is 4919 bytes combined). Raw game
responses stay outside tracked files. Tokens are unmeasured.

Two independent fresh-context runs used only the fallback client's actual
published catalog, descriptions/schemas and returned selectors for the single
task “Find DCs by level; what's the DC for level 5?” Both answered **20**, named
PF2e Journals → GM Screen → DCs by Level / GM Core p.53, and distinguished the
spell-rank table. Each needed three tool calls plus four discovery/description
operations, within the eight-operation/120-second cap: 15.253 and 18.194 seconds
through the last source response. Each received 33359 compact bytes across the
catalog preview, three descriptions and three results. Exact per-operation
metrics are in ignored `.eval-runs/wish009-agent1.json` and `wish009-agent2.json`.

Both runs used the same catalog hash
`c03ceca111073e83dd26634efba57a0edc268fcd57a590bc2b79fa809dddd856`
on the uncommitted working tree based on `566cbec633bbbf164c918f2966d453767697fa05`.
Isolation was instruction-only, with one fresh Python MCP connection per
operation; model/reasoning settings and billed tokens were unavailable.
This is a narrow exploratory usability pass, not GM-reviewed answer grading
for every acceptance question, a statistical reliability claim or a cold
Foundry-cache latency guarantee. Reused identities avoid discovery/search;
browser cache was not flushed. No additional benchmark runs are warranted.
