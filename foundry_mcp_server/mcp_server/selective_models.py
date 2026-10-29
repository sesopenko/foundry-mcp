"""Version-two selective MCP contracts. Models are limited to à la carte tools.

PF2e-specific selections refer to existing core14.369/PF2e8.6.1 source and
transformed contracts in docs/actor-tools.md, not new system calculations.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=512)]
Cursor = Annotated[str, Field(min_length=1, max_length=4096, pattern=r'^[\x00-\x7f]+$')]
Count = Annotated[int, Field(ge=1, le=100)]
Budget = Annotated[int, Field(ge=8000, le=48000)]
ActorDetail = Literal['identity', 'source', 'description', 'build', 'statistics',
    'statistics.attributes', 'statistics.armor_class', 'statistics.hit_points',
    'statistics.saves', 'statistics.perception', 'statistics.movement',
    'statistics.senses', 'statistics.languages', 'statistics.iwr', 'skills',
    'strikes', 'abilities', 'spellcasting', 'spellcasting.prepared',
    'spellcasting.options', 'inventory', 'inventory.summary', 'state', 'effective', 'wealth', 'wealth.items', 'bulk', 'bulk.items']
ItemDetail = Literal['identity', 'source', 'source.definition', 'source.activation',
    'source.attack', 'source.damage', 'source.defenses', 'source.casting',
    'source.preparations', 'source.physical', 'source.traits', 'source.publication',
    'description', 'rules', 'relationships', 'effective']


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class UniqueSelections(Model):
    """Request lists are sets of choices; response arrays retain source order/repeats."""

    @model_validator(mode='after')
    def unique_lists(self):
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, list) and all(isinstance(v, str) for v in value) and len(value) != len(set(value)):
                raise ValueError(f'{name} must not contain duplicate selections')
        return self


class ActorSelect(UniqueSelections):
    details: list[ActorDetail] = Field(default_factory=list, max_length=33, description='Empty means identity only. wealth/bulk select guarded character summaries. wealth.items/bulk.items select separately paginated physical Item details. Missing runtime values report potentially_missing. Other dots narrow sections; inventory.summary selects identities, quantities and containers.')
    item_uuids: list[Identifier] = Field(default_factory=list, max_length=100, description='Optional actual owned Item UUIDs from list_actor_items narrowing inventory, abilities, build and wealth.items/bulk.items, never wealth/Bulk summary totals; diagnostics remain visible.')
    entry_uuids: list[Identifier] = Field(default_factory=list, max_length=100, description='Optional owned spellcasting-entry UUIDs narrowing spellcasting, including preparation witnesses.')
    skill_names: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=100, description='Exact serialized skill keys, such as stealth; narrows current Skills. Lore identity diagnostics remain visible.')
    evidence: bool = Field(default=False, description='Include validated raw fields, contributor paths and mapping evidence. Off by default; basis and essential limitations remain.')


class ItemSelect(UniqueSelections):
    details: list[ItemDetail] = Field(default_factory=list, max_length=16, description='Empty means identity only. source selects all supported source fields; dot selections choose named groups. description returns exact stored text, independently of source.')
    evidence: bool = Field(default=False, description='Include raw fields and provenance for selected values.')


class PageRequest(UniqueSelections):
    limit: Count = Field(default=10, description='Maximum selected semantic entries, not primitive source fields.')
    max_bytes: Budget = Field(default=8000, description='Maximum compact UTF-8 JSON result bytes. Increase explicitly for larger selected units.')
    cursor: Cursor | None = Field(default=None, description='Copy returned continuation unchanged, with every original selector, selection and bound.')


class ActorRequest(PageRequest):
    actor_uuid: Identifier | None = Field(default=None, description='World/compendium Actor UUID from discovery; mutually exclusive with token_uuid.')
    token_uuid: Identifier | None = Field(default=None, description='Placed Scene.<id>.Token.<id>; reads current token Actor, never substitutes base.')
    select: ActorSelect | None = Field(default=None, description='À la carte selection; omitted means identity only.')
    sections: list[Literal['identity','source','description','build','statistics','skills','strikes','abilities','spellcasting','inventory','state','effective','wealth','bulk']] | None = Field(default=None, min_length=1, max_length=14, description='Explicit coarse shorthand for select.details; cannot combine with select. wealth/bulk select character summaries only.')

    @model_validator(mode='after')
    def selector_and_selection(self):
        if (self.actor_uuid is None) == (self.token_uuid is None):
            raise ValueError('Provide exactly one actor_uuid or token_uuid')
        if self.sections is not None and self.select is not None:
            raise ValueError('Choose select or sections, not both')
        return self


class ItemRequest(PageRequest):
    item_uuid: Identifier = Field(description='Canonical world, compendium or owned Item UUID from discovery.')
    token_uuid: Identifier | None = Field(default=None, description='Required for an Item in a synthetic token Actor context.')
    select: ItemSelect | None = None
    sections: list[Literal['identity','source','description','rules','relationships','effective']] | None = Field(default=None, min_length=1, max_length=6, description='Coarse shorthand; cannot combine with select.')

    @model_validator(mode='after')
    def selection(self):
        if self.sections is not None and self.select is not None:
            raise ValueError('Choose select or sections, not both')
        return self


class ListSelect(Model):
    context: bool = Field(default=False, description='Include full owner/folder/pack context instead of compact identities.')
    relationships: bool = Field(default=False, description='Include returned relationship metadata; does not expand targets.')
    follow_up: bool = Field(default=False, description='Include explicit next_call arguments; canonical identifiers are always present.')
    limitations: bool = Field(default=False, description='Include repeated per-entry explanatory limitations; scope failures are always present.')


ReadableType = Literal['melee','action','feat','spell','spellcastingEntry','lore','condition','effect','ancestry','heritage','background','class','deity','weapon','armor','shield','equipment','consumable','ammo','backpack','book','kit','treasure']
class ItemsRequest(PageRequest):
    actor_uuid: Identifier | None = None
    token_uuid: Identifier | None = None
    types: list[ReadableType] | None = Field(default=None, min_length=1, max_length=23)
    query: Annotated[str, Field(min_length=1,max_length=200)] | None = Field(default=None, description='Literal case-insensitive Item-name substring.')
    select: ListSelect = Field(default_factory=ListSelect)

    @model_validator(mode='after')
    def owner(self):
        if (self.actor_uuid is None) == (self.token_uuid is None):
            raise ValueError('Provide exactly one actor_uuid or token_uuid')
        return self


class PacksRequest(PageRequest):
    document_type: Literal['Actor','Item'] = 'Actor'
    query: Annotated[str, Field(min_length=1,max_length=200)] | None = Field(default=None, description='Literal case-insensitive title/pack-ID substring.')
    select: ListSelect = Field(default_factory=ListSelect)


class CapabilitySelect(UniqueSelections):
    actor_types: list[str] = Field(default_factory=list, max_length=30, description='Exact type codes; empty omits Actor registry entries.')
    item_types: list[str] = Field(default_factory=list, max_length=40, description='Exact type codes; empty omits Item registry entries.')
    actor_sections: list[str] = Field(default_factory=list, max_length=14, description='Exact section names; empty omits section registry entries.')
    item_sections: list[str] = Field(default_factory=list, max_length=6)
    all: bool = Field(default=False, description='Explicitly select all registry entries; may require a larger byte budget.')
    evidence: bool = Field(default=False, description='Include verification evidence and detailed limitations.')
    limits: bool = Field(default=False, description='Include reader limits.')


class CapabilityRequest(Model):
    select: CapabilitySelect = Field(default_factory=CapabilitySelect)
    max_bytes: Budget = 8000


class JournalContentsSelect(Model):
    headings: bool = Field(default=False, description='Include up to 20 heading outlines per page and explicit heading continuation calls.')
    categories: bool = Field(default=False, description='Include category groups and category follow-up metadata.')
    presentation: bool = Field(default=False, description='Include stored sort/title/category presentation fields.')
    folder_path: bool = False


class ContentsRequest(PageRequest):
    journal_id: Identifier = Field(description='Opaque world Journal ID, not UUID, from get_journal_tree or search_journals.')
    page_id: Identifier | None = Field(default=None, description='Select one page to enumerate its headings.')
    categories_only: bool = Field(default=False, description='Enumerate categories; cannot combine with page_id.')
    limit: Annotated[int,Field(ge=1,le=50)] = 10
    select: JournalContentsSelect = Field(default_factory=JournalContentsSelect)

    @model_validator(mode='after')
    def mode(self):
        if self.page_id and self.categories_only: raise ValueError('page_id conflicts with categories_only')
        return self


class JournalSearchSelect(Model):
    excerpts: bool = Field(default=False, description='Include up to three derived excerpts per match; not exact source.')
    counts: bool = Field(default=False, description='Include text occurrence counts.')
    folder_path: bool = False


class JournalSearchRequest(PageRequest):
    query: Annotated[str,Field(min_length=1,max_length=512)] = Field(description='Literal case-insensitive phrase, not a semantic question.')
    folder_id: Identifier | None = None
    journal_id: Identifier | None = None
    limit: Annotated[int,Field(ge=1,le=50)] = 10
    select: JournalSearchSelect = Field(default_factory=JournalSearchSelect)

    @model_validator(mode='after')
    def scope(self):
        if self.folder_id and self.journal_id: raise ValueError('Choose folder_id or journal_id')
        if not self.query.strip(): raise ValueError('query must not be blank')
        return self


class JournalPageSelect(Model):
    references: bool = Field(default=False, description='Extract bounded UUID references in this fragment with resolve_journal_reference follow-ups.')
    source_metadata: bool = Field(default=False, description='Include stored format and available original sources.')
    folder_path: bool = False


class JournalPageRequest(Model):
    page_uuid: Identifier = Field(description='Full world JournalEntry.<id>.JournalEntryPage.<id> UUID, without anchor.')
    source: Literal['html','markdown'] = 'html'
    max_chars: Annotated[int,Field(ge=1,le=20000)] = Field(default=2000, description='Maximum UTF-16 source units; exact fragments may also stop at the byte budget.')
    max_bytes: Budget = 8000
    cursor: Cursor | None = None
    select: JournalPageSelect = Field(default_factory=JournalPageSelect)


class PdfSearchSelect(Model):
    snippet: bool = Field(default=False, description='Include the derived lexical-match snippet.')
    entries: bool = Field(default=False, description='Include candidate heading titles and provenance; not proof of a rule definition.')
    context: bool = Field(default=False, description='Include entry ancestor context and optional-variant evidence; requires entries.')

    @model_validator(mode='after')
    def entry_context(self):
        if self.context and not self.entries: raise ValueError('context requires entries')
        return self


class PdfSearchRequest(Model):
    query: Annotated[str,Field(min_length=1,max_length=300)]
    document_id: Annotated[str,Field(pattern=r'^[a-f0-9]{32}$')] | None = None
    offset: Annotated[int,Field(ge=0,le=100000)] = 0
    limit: Annotated[int,Field(ge=1,le=20)] = 10
    max_bytes: Budget = 8000
    select: PdfSearchSelect = Field(default_factory=PdfSearchSelect)


class Pagination(Model):
    complete: bool
    next_cursor: str | None
    returned: int


class Runtime(Model):
    core_version: str
    system_id: str
    system_version: str


class Identity(Model):
    document_name: Literal['Actor','Item']
    id: str
    uuid: str
    name: str
    name_truncated: bool
    type: str
    source_kind: str
    folder: dict[str,JsonValue] | None
    pack: dict[str,JsonValue] | None
    actor: dict[str,JsonValue] | None
    instance: dict[str,JsonValue] | None


class Section(Model):
    name: str
    status: Literal['complete','partial','unsupported','not_applicable']
    reasons: list[str]


class Witness(Model):
    document_uuid: str
    path: str
    basis: Literal['source','transformed']
    present: bool
    value: JsonValue = None


class TextFragment(Model):
    path: str
    start: int
    end: int
    total: int
    complete: bool


class Evidence(Model):
    key: str
    section: str
    kind: Literal['field','relationship','text']
    raw: list[Witness]
    mapped: dict[str,JsonValue]
    provenance: dict[str,JsonValue]
    text: TextFragment | None = None


class Value(Model):
    concept: str = Field(description='Book-oriented concept from the selected supported reader.')
    value: JsonValue = Field(description='Selected value; null is distinct from absent source (present=false). Text is exact source.')
    basis: Literal['source','transformed','mixed','none','runtime']
    availability: Literal['available','potentially_missing'] | None = Field(default=None, description='Runtime wealth/Bulk fields: available preserves zero/false; potentially_missing has null value and a reason. Never count missing as zero.')
    reason: Literal['missing_api','invalid_value','getter_failed','items_denied','item_limit','dependency_unavailable','inconsistent_value'] | None = None
    present: bool | None = Field(default=None, description='Present on single-field values. Omitted for multi-contributor relationships.')
    unit: str | None = None
    text: TextFragment | None = None
    evidence: Evidence | None = None

    @model_validator(mode='after')
    def runtime_availability(self):
        if self.basis == 'runtime':
            if self.availability == 'available' and self.value is not None and self.reason is None:
                return self
            if self.availability == 'potentially_missing' and self.value is None and self.reason is not None:
                return self
            raise ValueError('Runtime fields require explicit availability and consistent value/reason')
        if self.availability is not None or self.reason is not None:
            raise ValueError('Availability is reserved for runtime metrics')
        return self


class Entry(Model):
    section: str
    key: str = Field(description='Response-local semantic group key, never a document UUID selector.')
    values: list[Value]


class ReadResult(Model):
    contract_version: Literal[2]
    runtime: Runtime
    identity: Identity
    revision: str
    sections: list[Section]
    entries: list[Entry]
    pagination: Pagination
    limitations: list[str]


class CompactIdentity(Model):
    uuid: Identifier
    name: str
    name_truncated: bool
    type: ReadableType
    token_uuid: Identifier | None = None


class Scope(Model):
    id: str
    status: Literal['searched','failed','incomplete','denied']
    reason: str | None


class MetadataNode(Model):
    kind: Literal['item','pack']
    identity: CompactIdentity | Identity | None = None
    id: str | None = None
    title: str | None = None
    title_truncated: bool | None = None
    document_type: Literal['Actor','Item'] | None = None
    searchable: bool | None = None
    visible: bool | None = None
    folder: JsonValue = None
    parent_uuid: str | None = None
    relationships: list[dict[str,JsonValue]] | None = None
    next_call: dict[str,JsonValue] | None = None
    search_scope: dict[str,JsonValue] | None = None
    limitations: list[str] | None = None


class ListResult(Model):
    contract_version: Literal[2]
    runtime: Runtime
    revision: str
    scopes: list[Scope]
    limitations: list[str]
    pagination: Pagination
    nodes: list[MetadataNode]
    unsupported_count: int | None = None


class CapabilityResult(Model):
    contract_version: Literal[2]
    runtime: Runtime
    availability: dict[str,JsonValue]
    actor_types: list[dict[str,JsonValue]] | None = None
    item_types: list[dict[str,JsonValue]] | None = None
    actor_sections: list[dict[str,JsonValue]] | None = None
    item_sections: list[dict[str,JsonValue]] | None = None
    limits: dict[str,int] | None = None
    limitations: list[str] | None = None


class JournalResult(Model):
    contract_version: Literal[2]
    foundry_version: str
    revision: str
    complete: bool
    next_cursor: str | None
    journal_id: str | None = None
    journal_uuid: str | None = None
    journal_name: str | None = None
    journal_name_truncated: bool | None = None
    name: str | None = None
    name_truncated: bool | None = None
    page_id: str | None = None
    page_uuid: str | None = None
    page_name: str | None = None
    page_name_truncated: bool | None = None
    folder_path: list[dict[str,JsonValue]] | None = None
    mode: Literal['pages','headings','categories'] | None = None
    total: int | None = None
    pages: list[dict[str,JsonValue]] | None = None
    groups: list[dict[str,JsonValue]] | None = None
    heading_outline: list[dict[str,JsonValue]] | None = None
    category_count: int | None = None
    groups_complete: bool | None = None
    categories_next_call: dict[str,JsonValue] | None = None
    scope: dict[str,JsonValue] | None = None
    searched_text_pages: int | None = None
    matches: list[dict[str,JsonValue]] | None = None
    source: Literal['html','markdown'] | None = None
    stored_format: int | None = None
    available_sources: list[str] | None = None
    content: str | None = None
    source_present: bool | None = None
    offset: int | None = None
    end_offset: int | None = None
    total_chars: int | None = None
    offset_units: str | None = None
    fragment: bool | None = None
    references: list[dict[str,JsonValue]] | None = None
    references_complete: bool | None = None
    references_scope: str | None = None


class PdfCandidate(Model):
    document_id: str
    name: str
    revision: str
    physical_page: int
    page_label: str
    warnings: list[str]
    snippet: str | None = None
    entries: list[dict[str,JsonValue]] | None = None
    exact_heading_candidate: bool | None = None


class JournalContentsResult(JournalResult):
    journal_id: str
    journal_uuid: str
    name: str
    name_truncated: bool
    mode: Literal['pages','headings','categories']
    total: int


class JournalSearchResult(JournalResult):
    scope: dict[str,JsonValue]
    searched_text_pages: int
    matches: list[dict[str,JsonValue]]
    total: int


class JournalPageResult(JournalResult):
    journal_id: str
    page_uuid: str
    source: Literal['html','markdown']
    content: str
    source_present: bool
    offset: int
    end_offset: int
    total_chars: int
    offset_units: str
    fragment: bool


class PdfResult(Model):
    contract_version: Literal[2]
    candidates: list[PdfCandidate]
    next_offset: int | None
    candidate_cap_reached: bool
    message: str
