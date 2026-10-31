"""Typed, read-only compendium interfaces; the browser owns all game data."""
import asyncio
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, model_validator

from . import selective_models as M


class Page(M.PageRequest):
    """Small default metadata pages with continuation and byte bounds."""
    pass


class PacksRequest(Page):
    document_type: Literal['Actor', 'Item', 'JournalEntry'] | None = Field(default=None, description='Omit to discover all three supported pack families.')
    query: Annotated[str, Field(min_length=1, max_length=200)] | None = Field(default=None, description='Literal case-insensitive pack title/collection substring.')


class Pack(M.Model):
    id: str
    title: str
    title_truncated: bool
    document_type: Literal['Actor', 'Item', 'JournalEntry']


class PackNode(Pack):
    searchable_fields: list[Literal['name', 'entry_name', 'page_name', 'text']]
    next_tool: Literal['search_compendium_journals', 'search_compendium_actors']
    folder_id: str | None
    folder_name: str | None


class PacksResult(M.Model):
    foundry_version: str
    revision: str
    nodes: list[PackNode]
    pagination: M.Pagination
    denied_packs: Annotated[int, Field(ge=0)]


class SearchSelect(M.Model):
    excerpts: bool = Field(default=False, description='One bounded derived excerpt per match; exact source requires read_compendium_journal_page.')


class SearchRequest(Page):
    pack_id: M.Identifier = Field(description='Collection ID from list_compendiums, not title or UUID; exactly one JournalEntry pack.')
    journal_id: M.Identifier | None = Field(default=None, description='Optional entry ID from this pack search; omit for pack-wide page-title discovery.')
    query: Annotated[str, Field(min_length=1, max_length=200)]
    field: Literal['entry_name', 'page_name', 'text'] = Field(default='page_name', description='Case-insensitive literal substring. entry_name uses only index; page_name/text load bounded entries. text scans derived HTML text or stored Markdown, excluding media.')
    max_entries: Annotated[int, Field(ge=1, le=10)] = Field(default=10, description='At most this many complete entries loaded per call, including repeated loads for match continuations. Entry includes all embedded pages; no network byte bound.')
    select: SearchSelect = Field(default_factory=SearchSelect)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.query.strip():
            raise ValueError('query must be nonblank')
        return self


class Match(M.Model):
    journal_id: str
    journal_uuid: str
    journal_name: str
    journal_name_truncated: bool
    page_id: str | None
    page_uuid: str | None
    page_name: str | None
    page_name_truncated: bool
    matched_field: Literal['entry_name', 'page_name', 'text']
    excerpt: str | None = None
    excerpt_derived: bool | None = None


class Failure(M.Model):
    journal_id: str
    status: str


class SearchResult(M.Model):
    foundry_version: str
    pack: Pack
    revision: str
    matches: list[Match]
    searched_field: Literal['entry_name', 'page_name', 'text']
    scanned_entries: Annotated[int, Field(ge=0)]
    scanned_text_pages: Annotated[int, Field(ge=0)]
    unsupported_pages: Annotated[int, Field(ge=0)]
    failures: list[Failure]
    unsearched_entries: Annotated[int, Field(ge=0)]
    batch_match_count: Annotated[int, Field(ge=0)]
    complete: bool
    coverage_complete: bool
    next_cursor: str | None
    limitations: list[str]

    @model_validator(mode='after')
    def continuation(self):
        if self.complete != (self.next_cursor is None):
            raise ValueError('completion and cursor disagree')
        if self.coverage_complete and (not self.complete or self.failures or self.unsupported_pages):
            raise ValueError('unsupported/failed scopes cannot be complete coverage')
        return self


class ContentsRequest(M.ContentsRequest):
    pack_id: M.Identifier = Field(description='JournalEntry collection ID from list_compendiums.')
    journal_id: M.Identifier = Field(description='Entry ID from search_compendium_journals in this pack, not UUID/name.')


class ContentsResult(M.JournalContentsResult):
    pack: Pack


class PageRequest(M.JournalPageRequest):
    pack_id: M.Identifier = Field(description='JournalEntry collection ID returned by list_compendiums.')
    page_uuid: M.Identifier = Field(description='Full Compendium.<pack>.JournalEntry.<entry>.JournalEntryPage.<page> UUID returned by compendium search/contents, without heading anchor.')


class PageResult(M.JournalPageResult):
    pack: Pack


class ReferenceRequest(M.Model):
    pack_id: M.Identifier
    page_uuid: M.Identifier = Field(description='Origin compendium page UUID returned by search/contents/read.')
    target: M.Identifier = Field(description='Exact stored @UUID[target] contents, including optional #anchor; no plain-name guesses.')
    source: Literal['html', 'markdown'] = 'html'

    @property
    def max_bytes(self):
        return 8000


class ReferenceResult(M.Model):
    foundry_version: str
    page_uuid: str
    source: Literal['html', 'markdown']
    target: str
    anchor: str | None
    status: Literal['resolved', 'missing', 'denied', 'unsupported', 'outside_scope', 'unverified']
    identity: dict[str, M.JsonValue] | None
    next_call: dict[str, M.JsonValue] | None


async def call(request, method, response):
    """Validate both RPC directions at the existing typed FastMCP boundary."""
    from . import tools
    from .selective import size
    from foundry_mcp_server.ws.connection import RpcError
    params = request.model_dump(mode='json')
    try:
        result = await tools._foundry_manager.call('gm', method, params, timeout=30.0)
    except RpcError as exc:
        raise ToolError(f"{exc.error.get('type')}: {exc.error.get('message')}") from exc
    except (asyncio.TimeoutError, ConnectionError, RuntimeError) as exc:
        raise ToolError('BridgeUnavailable: reconnect the existing ready GM browser and retry.') from exc
    try:
        validated = response.model_validate(result)
        if size(result) > getattr(request, 'max_bytes', 8000):
            raise ValueError('response exceeds requested UTF-8 JSON budget')
        if hasattr(validated, 'pack') and validated.pack.id != request.pack_id:
            raise ValueError('wrong pack')
        if isinstance(request, SearchRequest):
            if validated.searched_field != request.field:
                raise ValueError('wrong search field')
            for match in validated.matches:
                entry_uuid = f'Compendium.{request.pack_id}.JournalEntry.{match.journal_id}'
                if match.journal_uuid != entry_uuid or match.matched_field != request.field:
                    raise ValueError('wrong entry identity')
                if request.journal_id is not None and match.journal_id != request.journal_id:
                    raise ValueError('wrong entry scope')
                if match.page_uuid != (f'{entry_uuid}.JournalEntryPage.{match.page_id}' if match.page_id else None):
                    raise ValueError('wrong page identity')
                if not request.select.excerpts and match.excerpt is not None:
                    raise ValueError('unrequested excerpt')
        if isinstance(request, ContentsRequest):
            if validated.journal_id != request.journal_id or validated.journal_uuid != f'Compendium.{request.pack_id}.JournalEntry.{request.journal_id}':
                raise ValueError('wrong entry')
            for page in validated.pages or []:
                if page.get('page_uuid') != f"{validated.journal_uuid}.JournalEntryPage.{page.get('page_id')}":
                    raise ValueError('wrong page identity')
        if isinstance(request, PageRequest):
            if validated.page_uuid != request.page_uuid or validated.source != request.source:
                raise ValueError('wrong page/source')
            if len(validated.content.encode('utf-16-le')) // 2 != validated.end_offset - validated.offset:
                raise ValueError('invalid source offsets')
            if not 0 <= validated.offset <= validated.end_offset <= validated.total_chars:
                raise ValueError('invalid source bounds')
            if validated.complete != (validated.next_cursor is None):
                raise ValueError('invalid continuation')
        if isinstance(request, ReferenceRequest):
            if (validated.page_uuid != request.page_uuid or validated.target != request.target
                    or validated.source != request.source or validated.anchor != (request.target.partition('#')[2] or None)):
                raise ValueError('wrong reference origin')
            if validated.status != 'resolved':
                if validated.identity is not None or validated.next_call is not None:
                    raise ValueError('unresolved reference metadata')
            else:
                identity, next_call = validated.identity, validated.next_call
                if not identity or not next_call or set(next_call) != {'tool', 'arguments'}:
                    raise ValueError('missing reference follow-up')
                kind = identity.get('document_name')
                if kind in ('Actor', 'Item'):
                    from .actors import _identity
                    if not _identity(identity):
                        raise ValueError('invalid Actor/Item identity')
                    token = (identity.get('instance') or {}).get('token_uuid')
                    expected = ({'token_uuid': token} if token else {'actor_uuid': identity['uuid']}) if kind == 'Actor' else {'item_uuid': identity['uuid'], **({'token_uuid': token} if token else {})}
                    tool = 'read_actor' if kind == 'Actor' else 'read_item'
                elif kind in ('JournalEntry', 'JournalEntryPage'):
                    pack = identity.get('pack')
                    tool = 'read_journal_page' if kind == 'JournalEntryPage' else 'get_journal_contents'
                    expected = {'page_uuid': identity['uuid']} if kind == 'JournalEntryPage' else {'journal_id': identity['uuid'].split('.')[-1]}
                    if pack:
                        expected['pack_id'] = pack['id']
                        tool = 'read_compendium_journal_page' if kind == 'JournalEntryPage' else 'get_compendium_journal_contents'
                else:
                    raise ValueError('unsupported reference kind')
                if next_call != {'tool': tool, 'arguments': expected}:
                    raise ValueError('wrong reference follow-up')
    except (ValueError, TypeError, AttributeError) as exc:
        raise ToolError('InvalidFoundryResponse: compendium contract validation failed.') from exc
    return result


COMMON = """ Read-only; requires ready GM, Foundry14 (tested14.369), pack/document/page
OBSERVER permission. No imports, writes, rolls, chat, pack configuration or Python
cache. Locked/unlocked packs have identical read-only operations. IDs come from
returned navigation, never names/paths. Metadata names are clipped at256 with
truncation flags; IDs/source remain exact. Count limit defaults10; max_bytes
defaults8000 (8000..48000 compact UTF-8 JSON bytes). Pass next_cursor unchanged
with ALL original selectors, selections and bounds until complete; never invent
offsets. ContentChanged: discard pages/restart without cursor. CursorMismatch or
InvalidCursor: restore inputs/restart. PackNotFound/JournalNotFound/PageNotFound:
rediscover. PermissionDenied: GM must check access. UnsupportedDocument/PageType:
select JournalEntry/text. BridgeUnavailable/NotReady: reconnect/wait, retry.
"""

PACKS_DOC = """Discover Item, Actor and JournalEntry compendium packs and searchable fields.
Omit document_type for all three, or filter; query matches pack title/collection
only. Returns nodes{id,title,document_type,searchable_fields,next_tool,folder_id,
folder_name}, revision, denied_packs (aggregate), pagination{complete,next_cursor,
returned}. This lists immediate directory folder context; no internal pack tree.
Journal packs: search_compendium_journals(pack_id=node.id,query='DCs by Level')
finds embedded titles without knowing entries. Item/Actor packs: use
search_compendium_actors(pack_ids=[node.id],document_type=node.document_type,
query=...). These existing readers require PF2e8.6.1 and supported types; journal
tools do not require PF2e. Empty nodes exclude denied packs, not proof of absence.
""" + COMMON

SEARCH_DOC = """Search one explicitly selected JournalEntry compendium pack.
Use list_compendiums first. Default field=page_name is case-insensitive literal
partial-title matching across entries, not parent-name search; e.g. query='DCs by
Level'. field=entry_name searches index names without document loading. field=text
scans derived HTML text/link labels or original Markdown; no attributes, UUID IDs,
media, regex, fuzzy or semantic search. Use alternate wording or selected entry
contents/outlines for empty matches. Never automatically scans other packs.
Returns named pack, matches{journal_id,journal_uuid,journal_name,page_id,page_uuid,
page_name,matched_field}, revision, scanned_entries/scanned_text_pages,
unsupported_pages, failures{journal_id,status}, unsearched_entries,
batch_match_count, complete, coverage_complete, next_cursor, limitations.
select.excerpts opts into bounded derived context, never source evidence.
max_entries defaults10 (1..10) complete entry loads per call; each includes ALL
pages. At most10000 pages processed per entry, otherwise WorkLimit. Network bytes
and individual load latency are not bounded by Foundry; transport timeout30s.
Result pagination can repeat current-batch loads. Counts describe THIS batch,
not cumulative totals. complete means traversal exhausted; coverage_complete also
requires no failures/media in this batch. Retain gaps from every prior response.
Index/current-batch revisions detect changes; exhausted earlier batches are NOT
revalidated. Restart full scan after edits for a new consistent investigation.
Read a match's page_uuid with read_compendium_journal_page(pack_id=pack.id,...).
For entry matches, get_compendium_journal_contents(pack_id, journal_id) lists
pages/headings. Name matches never establish journal-body evidence.
""" + COMMON

CONTENTS_DOC = """Navigate selected compendium JournalEntry pages/categories/headings.
Use pack_id/journal_id from search_compendium_journals. Returns pack plus
journal_id/journal_uuid/name, mode, total, revision, complete, next_cursor.
Default mode=pages returns compact pages{page_id,page_uuid,name,type,readable} in
category/sort order. Nontext pages are listed unreadable. select.headings opts
into20 headings per page; page_id selects a complete paginated heading_outline.
select.categories/presentation/folder_path opt into extra context. categories_only
lists category groups; conflicts with page_id. Follow-up metadata's journal_id
and page_id remain within the SAME pack: call this tool with pack_id retained.
Read exact source via read_compendium_journal_page with a returned page_uuid.
An empty entry differs from missing/denied. Continuations bind entry content and
selections. Limit1..50. No source bodies returned.
""" + COMMON

PAGE_DOC = """Read exact compendium journal page HTML (default) or stored Markdown.
Use pack_id/page_uuid from search_compendium_journals or
get_compendium_journal_contents, without #anchor. Returns named pack/entry/page,
revision, source, content, source_present, offset/end_offset/total_chars,
offset_units='UTF-16 code units', fragment, complete, next_cursor. Concatenate
content until complete to reconstruct exact tables/headers/units/footnotes/link
notation. max_chars defaults2000 (1..20000); surrogate pairs stay intact, so a
one-unit request may return two. Fragments may split HTML elements or notation.
select.source_metadata adds stored_format/available_sources. Missing HTML returns
source_present=false; absent Markdown raises SourceUnavailable (select html).
select.references adds up to20 fragment-local UUID links, not hydrated evidence.
Use resolve_compendium_journal_reference for one selected exact target; it returns
canonical next-tool arguments. Source notation always remains intact.
No enrichment, rendering or inline evaluation. Cite pack.title/journal_name/
page_name with page_uuid. Identity/excerpts alone are not complete rules evidence.
""" + COMMON

REFERENCE_DOC = """Resolve one exact stored UUID link from a compendium text page lazily.
Use after read_compendium_journal_page; copy pack_id/page_uuid and exact target
from @UUID[target] or select.references. source=html by default; Markdown must
be stored. Relative links resolve against this source page. Origin must still
contain target verbatim or ReferenceChanged requires rereading source.
Returns foundry_version/page_uuid/source/target/anchor/status/identity/next_call.
resolved includes named canonical destination and next_call{tool,arguments} for
world/pack journal entry/page or PF2e Actor/Item readers; copy arguments unchanged.
Anchor is retained separately, never part of a reader selector. PF2e-specific
Actor/Item admission requires supported types/core14.369/PF2e8.6.1; other systems
return unsupported for those targets. Journal destinations are system-neutral.
missing/denied/unsupported/outside_scope/unverified return null identity and
next_call; none disproves the source claim. No recursive expansion or target
source reading. At most8000 output bytes; no pagination. Only origin and one
selected target may load; no pack search or content writes.
""" + COMMON


def install(server):
    from .selective import SelectiveTool
    specs = [('list_compendiums', PacksRequest, PacksResult, 'listCompendiums', PACKS_DOC),
             ('search_compendium_journals', SearchRequest, SearchResult, 'searchCompendiumJournals', SEARCH_DOC),
             ('get_compendium_journal_contents', ContentsRequest, ContentsResult, 'getCompendiumJournalContents', CONTENTS_DOC),
             ('read_compendium_journal_page', PageRequest, PageResult, 'readCompendiumJournalPage', PAGE_DOC),
             ('resolve_compendium_journal_reference', ReferenceRequest, ReferenceResult, 'resolveCompendiumJournalReference', REFERENCE_DOC)]
    for name, request, response, method, description in specs:
        async def handler(value, method=method, response=response):
            return await call(value, method, response)
        server.add_tool(SelectiveTool(name=name, description=description, parameters=request.model_json_schema(),
            output_schema=response.model_json_schema(), request_model=request, response_model=response,
            handler=handler, annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)))
