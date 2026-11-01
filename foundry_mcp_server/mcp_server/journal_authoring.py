"""Typed core14 journal edit contexts using the readers' canonical selectors."""
import hashlib
import inspect
import json
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, RootModel, model_validator

from .selective import SelectiveTool, rpc
from .selective_models import Model
from .server import mcp
from .writing import GuidanceSource, GuidanceTimestamp, guidance_revision
from .journal_image_models import ImageSelector

LocalId = Annotated[str, Field(pattern=r'^[^.\s#]{1,64}$')]
PageUuid = Annotated[str, Field(pattern=r'^JournalEntry\.[^.\s#]+\.JournalEntryPage\.[^.\s#]+$', max_length=512)]
ChangeMarker = Annotated[str, Field(min_length=1, max_length=128)]


class FolderTarget(Model):
    kind: Literal['folder']
    folder_id: LocalId


class JournalTarget(Model):
    kind: Literal['journal']
    journal_id: LocalId


class PageTarget(Model):
    kind: Literal['page']
    page_uuid: PageUuid


Target = Annotated[FolderTarget | JournalTarget | PageTarget, Field(discriminator='kind')]


class ContextRequest(Model):
    target: Target = Field(description='World-only selector from get_journal_tree/get_journal_contents; names and compendium UUIDs are not accepted.')
    max_bytes: int = Field(default=8000, ge=8000, le=48000)


class NamedIdentity(Model):
    uuid: str
    name: str = Field(max_length=256)
    name_truncated: bool


class FolderIdentity(NamedIdentity, FolderTarget):
    parent_folder_id: LocalId | None


class JournalIdentity(NamedIdentity, JournalTarget):
    folder_id: LocalId | None


class PageIdentity(NamedIdentity, PageTarget):
    page_id: LocalId
    journal_id: LocalId
    type: str


Identity = Annotated[FolderIdentity | JournalIdentity | PageIdentity, Field(discriminator='kind')]


class OwnershipDefault(Model):
    present: bool
    value: Literal[-1, 0, 1, 2, 3] | None = None


class TreeFollow(Model):
    tool: Literal['get_journal_tree']
    arguments: dict[Literal['folder_id'], LocalId]


class JournalFollow(Model):
    tool: Literal['get_journal_contents']
    arguments: dict[Literal['journal_id'], LocalId]


class PageFollow(Model):
    tool: Literal['read_journal_page']
    arguments: dict[Literal['page_uuid'], PageUuid]


Follow = Annotated[TreeFollow | JournalFollow | PageFollow, Field(discriminator='tool')]


class ContextResult(Model):
    identity: Identity
    revision: ChangeMarker
    sort: int | None
    ownership_default: OwnershipDefault | None
    read_next_call: Follow


def validate_identity(identity, follow=None):
    """Validate the same canonical identity and reader follow-up for all receipts."""
    selector = {'folder': 'folder_id', 'journal': 'journal_id', 'page': 'page_uuid'}[identity.kind]
    value = getattr(identity, selector)
    expected_uuid = {'folder': 'Folder.', 'journal': 'JournalEntry.', 'page': ''}[identity.kind] + value
    tool = {'folder': 'get_journal_tree', 'journal': 'get_journal_contents', 'page': 'read_journal_page'}[identity.kind]
    if identity.uuid != expected_uuid or (follow is not None and follow.model_dump() != {'tool': tool, 'arguments': {selector: value}}):
        raise ToolError('InvalidFoundryResponse: inconsistent journal identity or reader follow-up.')
    if isinstance(identity, PageIdentity) and identity.page_uuid != f'JournalEntry.{identity.journal_id}.JournalEntryPage.{identity.page_id}':
        raise ToolError('InvalidFoundryResponse: inconsistent page identity.')


async def get_journal_write_context(request: ContextRequest):
    """Get one named world journal/folder/page revision before an authorized edit.

    First read get_writing_guidance: GM guidance is critically important to
    follow, including permission requirements protecting official adventures.
    Find folder_id/journal_id with get_journal_tree, or page_uuid with
    get_journal_contents. Pass target.kind=folder/journal/page with exactly its
    corresponding selector. IDs are local document IDs; page_uuid is the full
    world JournalEntry.<id>.JournalEntryPage.<id> UUID. Names are not selectors.

    Ready GM and Foundry14 required; system independent, no PF2e interpretation.
    Compendiums are read-only and excluded. Non-text pages may be identified
    but text writing supports only text pages. No mutations or content reads
    are returned here. Use read_next_call to read actual prose before editing.

    Returns identity with name/name_truncated, uuid, kind and canonical IDs;
    revision is an opaque change marker for editable source and containing
    context, not permission or a lock. sort is stored manual ordering or null.
    ownership_default=null for folders (folders have no ownership); otherwise
    present distinguishes an absent default from explicit inherited -1 or
    None=0/Limited=1/Observer=2/Owner=3. No GM user selectors are exposed.
    read_next_call contains the reader tool and exact arguments.

    max_bytes defaults8000, range8000–48000 compact UTF-8 JSON bytes. One
    context only; no pagination. ContentChanged: reread and obtain a new context.
    DocumentNotFound: rediscover selectors. PermissionDenied/NotReady: connect
    the existing ready GM. UnsupportedVersion: use Foundry14. InvalidRequest:
    inspect the published schema; unknown fields are rejected before reads.
    """
    packet = await rpc('getJournalWriteContext', request.model_dump())
    try:
        result = ContextResult.model_validate(packet)
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: invalid journal edit context; check server/module compatibility.') from None
    identity = result.identity
    target = request.target
    selector = {'folder': 'folder_id', 'journal': 'journal_id', 'page': 'page_uuid'}[target.kind]
    value = getattr(target, selector)
    validate_identity(identity, result.read_next_call)
    if identity.kind != target.kind or getattr(identity, selector) != value:
        raise ToolError('InvalidFoundryResponse: journal identity or reader follow-up differs from the requested target.')
    default = result.ownership_default
    if (target.kind == 'folder') != (default is None) or (default is not None and default.present != ('value' in default.model_fields_set)):
        raise ToolError('InvalidFoundryResponse: inconsistent stored ownership default.')
    return result.model_dump(exclude_unset=True)


Name = Annotated[str, Field(min_length=1, max_length=256)]
Sort = Annotated[int, Field(ge=-2147483648, le=2147483647)]
Color = Annotated[str, Field(pattern=r'^#[0-9a-fA-F]{6}$')]


class Action(Model):
    @model_validator(mode='after')
    def fields_are_meaningful(self):
        if 'name' in self.model_fields_set and (self.name is None or not self.name.strip()):
            raise ValueError('name must contain non-whitespace characters')
        for key in self.model_fields_set:
            if getattr(self, key) is None and key not in ('folder_id', 'parent_folder_id', 'color'):
                raise ValueError(f'{key} cannot be null; omit unchanged fields')
        if self.operation.startswith('update_') and not self.model_fields_set - {
                'operation', 'folder_id' if self.operation == 'update_folder' else 'journal_id' if self.operation == 'update_journal' else 'page_uuid',
                'expected_revision', 'parent_revision', 'mode'}:
            raise ValueError('an update needs at least one changed field')
        destination = 'parent_folder_id' if 'folder' in self.operation else 'folder_id'
        if getattr(self, destination, None) is not None and getattr(self, 'parent_revision', None) is None:
            raise ValueError('a selected destination requires parent_revision')
        if getattr(self, 'mode', None) is not None and 'content' not in self.model_fields_set:
            raise ValueError('mode requires content')
        if getattr(self, 'format', None) is not None and 'content' not in self.model_fields_set:
            raise ValueError('format requires content')
        content = getattr(self, 'content', None)
        if content is not None and len(content.encode('utf-8')) > 16000:
            raise ValueError('content exceeds 16000 UTF-8 bytes; split into append operations')
        return self


class TextFormat(Model):
    font_family: str | None = Field(default=None, min_length=1, max_length=256, description='Exact loaded family from get_journal_authoring_options(kind=fonts).')
    font_size: Literal['small', 'normal', 'large', 'huge', 'custom'] | None = Field(default=None, description='10/12/18/24pt respectively, or custom_size_pt.')
    custom_size_pt: float | None = Field(default=None, ge=1, le=200, description='Positive point size for font_size=custom only.')
    font_color: Color | None = None

    @model_validator(mode='after')
    def valid_format(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('omit unchanged format fields rather than null')
        if (self.font_size == 'custom') != (self.custom_size_pt is not None):
            raise ValueError('custom requires custom_size_pt; other sizes forbid it')
        return self


class CreateFolder(Action):
    operation: Literal['create_folder']
    name: Name
    parent_folder_id: LocalId | None = None
    parent_revision: ChangeMarker | None = None
    color: Color | None = None
    sorting: Literal['alphabetical', 'manual'] = 'alphabetical'
    sort: Sort = 0


class UpdateFolder(Action):
    operation: Literal['update_folder']
    folder_id: LocalId
    expected_revision: ChangeMarker
    name: Name | None = None
    parent_folder_id: LocalId | None = None
    parent_revision: ChangeMarker | None = None
    color: Color | None = None
    sorting: Literal['alphabetical', 'manual'] | None = None
    sort: Sort | None = None


class CreateJournal(Action):
    operation: Literal['create_journal']
    name: Name
    folder_id: LocalId | None = None
    parent_revision: ChangeMarker | None = None
    sort: Sort = 0


class UpdateJournal(Action):
    operation: Literal['update_journal']
    journal_id: LocalId
    expected_revision: ChangeMarker
    name: Name | None = None
    folder_id: LocalId | None = None
    parent_revision: ChangeMarker | None = None
    sort: Sort | None = None


class CreatePage(Action):
    operation: Literal['create_page']
    journal_id: LocalId
    parent_revision: ChangeMarker
    name: Name
    type: Literal['text'] = Field(default='text', description='Extensible page type enum; currently only text.')
    content: str = Field(max_length=16000, description='Supported HTML within 16000 UTF-8 bytes; never truncated.')
    sort: Sort = 0
    format: TextFormat | None = None


class UpdatePage(Action):
    operation: Literal['update_page']
    page_uuid: PageUuid
    expected_revision: ChangeMarker
    name: Name | None = None
    content: str | None = Field(default=None, max_length=16000)
    mode: Literal['replace', 'append'] | None = None
    sort: Sort | None = None
    format: TextFormat | None = None


class ImageAnchor(Model):
    tag: Literal['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'ul', 'ol', 'li', 'table']
    text: str = Field(min_length=1, max_length=2000, description='Exact decoded textContent of one block; duplicate matches are rejected. Read the page first.')


class EmbedImage(Model):
    operation: Literal['embed_image']
    page_uuid: PageUuid
    expected_revision: ChangeMarker
    image: ImageSelector = Field(description='Copy the complete image record returned by browse_journal_images or upload_image. No extra image discovery is required after upload. Membership and GM loading are checked again before writing.')
    alt: str = Field(max_length=1000, description='Required alt description, HTML escaped. Empty string allowed for decorative images.')
    width: int | None = Field(default=None, ge=1, le=8192, description='Optional HTML width in CSS pixels; omit to retain natural size/aspect ratio.')
    height: int | None = Field(default=None, ge=1, le=8192, description='Optional HTML height in CSS pixels. One dimension preserves natural aspect ratio; both explicitly specify it.')
    position: Literal['append', 'prepend', 'before', 'after'] = 'append'
    anchor: ImageAnchor | None = None

    @model_validator(mode='after')
    def valid_insertion(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('omit optional image fields rather than null')
        if (self.position in ('before', 'after')) != (self.anchor is not None):
            raise ValueError('before/after requires anchor; append/prepend forbids it')
        if any((ord(char) < 32 and char not in '\t\n\r') or ord(char) == 127 for char in self.alt):
            raise ValueError('alt cannot contain control characters')
        return self


Level = Literal['no_change', 'none', 'limited', 'observer', 'owner']


class OwnershipScope(Model):
    target: Target
    recursive: bool = Field(default=False, description='Folder only: include descendants. False selects directly contained journals.')
    journal_ids: list[LocalId] | None = Field(default=None, min_length=1, max_length=100, description='Folder only: explicit subset of discovered contained journals; omit to preview all within limit.')
    user_ids: list[LocalId] = Field(default_factory=list, max_length=100, description='Non-GM players whose stored overrides/current OBSERVER checks to include in preview.')
    limit: int = Field(default=10, ge=1, le=100, description='Hard bound on targets; larger scopes fail before writing. Choose a subset rather than receiving a truncated preview.')

    @model_validator(mode='after')
    def valid_scope(self):
        if self.target.kind != 'folder' and (self.recursive or self.journal_ids is not None):
            raise ValueError('recursive/journal_ids apply only to a folder')
        for values in (self.journal_ids, self.user_ids):
            if values is not None and len(set(values)) != len(values):
                raise ValueError('scope IDs must be unique')
        return self


class OwnershipRequest(OwnershipScope):
    max_bytes: int = Field(default=8000, ge=8000, le=48000)


class PlayerOwnership(OwnershipDefault):
    user_id: LocalId
    can_observe: bool
    parent_can_observe: bool | None


class OwnershipEntry(Model):
    identity: Identity
    ownership_default: OwnershipDefault
    players: list[PlayerOwnership] = Field(max_length=100)


class OwnershipContextResult(Model):
    target: Identity
    revision: ChangeMarker
    count: int = Field(ge=0, le=100)
    recursive: bool
    entries: list[OwnershipEntry] = Field(max_length=100)
    limitations: list[str]


class PlayerChange(Model):
    user_id: LocalId
    level: Level


class SetOwnership(OwnershipScope):
    operation: Literal['set_ownership']
    expected_revision: ChangeMarker = Field(description='Revision from get_journal_ownership_context with identical scope/user_ids/limit.')
    all_players: Level = Field(default='no_change', description='Changes default ownership only; existing per-player overrides remain intact. No Change preserves default.')
    players: list[PlayerChange] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def actual_change(self):
        ids = [player.user_id for player in self.players]
        if len(set(ids)) != len(ids):
            raise ValueError('player IDs must be unique')
        if self.all_players == 'no_change' and all(player.level == 'no_change' for player in self.players):
            raise ValueError('select at least one actual ownership change')
        return self


WriteAction = Annotated[CreateFolder | UpdateFolder | CreateJournal | UpdateJournal | CreatePage | UpdatePage | SetOwnership | EmbedImage, Field(discriminator='operation')]


class WriteRequest(Model):
    request_id: str = Field(pattern=r'^[A-Za-z0-9-]{16,64}$', description='Unique operation ID. Reuse only with identical input after reconciling uncertain outcomes.')
    gm_authorized: Literal[True] = Field(description='True only when the GM explicitly requested this edit and supplied any permission required by the GM writing guidance.')
    guidance_timestamp: GuidanceTimestamp = Field(description='Complete timestamp record from get_writing_guidance, checked again immediately before writing.')
    action: WriteAction
    max_bytes: int = Field(default=8000, ge=8000, le=48000)


class WriteResult(Model):
    request_id: str
    status: Literal['created', 'updated', 'already_applied']
    identity: Identity
    revision: ChangeMarker
    read_next_call: Follow


class OwnershipReceiptEntry(Model):
    identity: Identity
    status: Literal['updated', 'already_applied', 'failed', 'not_attempted']
    error: str | None = None


class OwnershipWriteResult(Model):
    request_id: str
    status: Literal['complete', 'partial']
    count: int = Field(ge=0, le=100)
    entries: list[OwnershipReceiptEntry] = Field(max_length=100)


class MutationResult(RootModel[WriteResult | OwnershipWriteResult]):
    pass


async def write_journal(request: WriteRequest):
    """Create/rename/reorganize world journals/folders or create/edit text pages.

    Read get_writing_guidance FIRST (recommended before planning every edit).
    GM instructions are critically important; obtain explicit GM permission for
    protected official material. Set gm_authorized=true only for the GM's actual
    instruction and required permission. This assertion is not an automatic
    interpretation of prose or a new ACL. Pass its complete guidance_timestamp;
    GuidanceChanged means reread guidance and reconsider the edit before retry.
    Requires ready GM, Foundry14; system independent, no PF2e interpretation.
    World documents only; compendiums and non-text content are read-only.

    Select one action.operation. create_folder/create_journal require name;
    optionally choose parent_folder_id/folder_id and its parent_revision from
    get_journal_write_context. Null destination means root. update_folder and
    update_journal use folder_id/journal_id and expected_revision from that
    context; omit fields to preserve them. To move, pass destination and its
    parent_revision. Folder color is #RRGGBB or null; sorting alphabetical/manual
    controls folder child ordering. sort is a signed32 integer: lower first in
    manual order (read stored sort from context); equal sorts use Foundry order.
    Folder cycles are rejected. Names are 1–256 Unicode characters, nonblank.

    create_page requires journal_id,parent_revision,name,content; type enum is
    currently text. A GM's text 'tab' normally means this embedded page, not a
    v14 category. Category changes are not supported by these operations.
    update_page takes page_uuid,expected_revision and name/content/sort. content
    replaces by default; mode=append appends HTML, requiring an existing HTML
    page. Replacement sets HTML format and clears the old Markdown source.
    Use IDs returned by get_journal_tree/get_journal_contents and read_journal_page
    before editing; names never select targets. Omitted fields and siblings
    remain unchanged. Each content fragment is <=16000 UTF-8 bytes; resulting
    text <=1000000 UTF-16 units. Long prose can use sequential appends with fresh
    context. Supported HTML includes blocks/headings/emphasis/lists/tables/hr,
    safe links, semantic sections/asides/figures, CSS class lists (<=1024 chars),
    id (<=256), title (<=512), data-split-here (<=256), and passive IMG markup.
    Images accept relative or HTTP(S) src <=2048 chars (spaces allowed),
    alt <=1000 chars and width/height1–8192; raw HTML does not verify asset
    existence/membership. Use browse_journal_images/embed_image for verified
    image selection. Publisher appearance requires installed styles.
    Font CSS and bounded layout syntax support position/dimensions/margins/
    padding/float/display/borders/opacity/object-fit/text-indent/line-height,
    numeric scale transforms and shape-outside:url(safe image URL).
    Scripts/events/iframes/forms/active embeds, unsafe URL schemes, srcset,
    other data attributes and arbitrary CSS functions/declarations are rejected.
    Optional format wraps only the supplied fragment in a styled div: font_family
    comes from get_journal_authoring_options(kind=fonts), font_color is #RRGGBB,
    font_size small/normal/large/huge maps to10/12/18/24pt; custom requires
    custom_size_pt in1–200. Omit format properties to preserve inherited styles.

    embed_image inserts a browsed image into an existing HTML text page. Requires
    page_uuid,expected_revision,image,alt. Copy image{source,directory,bucket?,src}
    from browse_journal_images or upload_image, never guess a URL. Current directory membership
    and successful GM-browser image loading (5s deadline) are checked before
    writing; private/missing/broken assets fail ImageNotFound/BrowseFailed/
    ImageUnavailable. This does not prove player asset access. Read guidance and
    confirm GM authorization as above; retries use the same request identity.
    alt is required, <=1000 Unicode characters, HTML escaped; empty decorative
    alt is allowed. Optional width/height are integers1–8192 CSS pixels, not pt.
    Omit both for natural size; one dimension retains intrinsic aspect ratio;
    both explicitly set width/height and can distort it (page CSS still applies).
    position defaults append; prepend inserts first. before/after requires
    anchor{tag,text}, exact decoded textContent of one supported block. Match is
    case/whitespace sensitive, no fuzzy search; find the text in read_journal_page.
    AnchorNotFound/AmbiguousAnchor: reread and choose a unique tag/text or append.
    Append/prepend preserves existing source bytes; anchored insertion serializes
    a detached standard DOM, preserving content while normalizing HTML markup.
    No enrichment/roll evaluation. Markdown/non-text pages are unsupported.
    Result is the normal updated/already_applied page receipt. The resulting
    page still has the1,000,000 UTF-16 limit. Raw img in content remains rejected;
    use embed_image so source validation cannot be bypassed.
    Use verified PF2e inline builders only on PF2e; immediate rolls are rejected.

    One write per call. max_bytes defaults8000 (8000–48000 compact JSON bytes).
    Returns request_id,status, named canonical identity,revision,read_next_call;
    no full prose. Newly created journals are player-private; GM ownership is
    retained for entries/pages. Folders have no ownership field. Use ownership
    tooling separately for players. No deletions, imports or arbitrary patches.

    set_ownership first requires get_journal_ownership_context: copy its revision
    to expected_revision and repeat identical target/recursive/journal_ids/user_ids/
    limit. target can be one journal/page, or a folder's existing journals only.
    Folders have no ACL and future entries do not inherit this batch. Default
    direct-only; recursive=true includes descendant folders. limit10 default,
    max100; ScopeTooLarge requires a smaller journal_ids subset or raised limit.
    all_players sets default; players[{user_id,level}] sets individual overrides.
    Levels no_change/none/limited/observer/owner map preserve/0/1/2/3. No Change
    preserves stored values; it is not embedded INHERIT=-1. Existing unrelated
    overrides are preserved, so All Players does not erase per-player choices.
    Discover non-GM user IDs via get_journal_authoring_options(kind=players).
    GM IDs are rejected; all GMs retain OWNER. Limited is not full text access;
    use Observer for reading, Owner for editing. Page access also depends on
    its parent; preview current can_observe/parent_can_observe and verify audience.
    Batch result is request_id,status=complete|partial,count,entries with named
    identity,status=updated|already_applied|failed|not_attempted,error on failure.
    Batches are not atomic: stop on first failure. Reconcile partial results,
    obtain a new preview and explicitly select remaining targets for a new
    request; do not repeat completed targets with a new ID. Same-session retry
    returns the original outcome; after reconnect completed flags prevent repeats
    and a partially changed scope requires a new preview. No silent truncation.

    request_id is 16–64 letters/digits/hyphens, unique per operation. Concurrent
    identical retries coalesce; persisted flags and stable create IDs prevent
    repeat appends/duplicate creation after reconnect. Reuse EXACT input after
    reading the target to reconcile a timeout. RequestConflict means the ID was
    reused differently; do not blindly select a new ID. WriteOutcomeUnknown or
    BridgeUnavailable may mean the mutation completed: inspect via readers first.
    Receipts are bounded to1000 requests per document and per browser session;
    WriteHistoryFull/WriteLedgerFull requires GM reconciliation, not flag removal.
    Revisions are optimistic observations, not distributed locks. ContentChanged:
    reread content/context and reconsider; changes from another GM can race a
    write. Missing/denied targets: rediscover/connect the authorized ready GM.
    InvalidRequest/UnsupportedType/UnsupportedFormat: inspect schema or choose a
    text/HTML target. InvalidFoundryResponse after dispatch requires reconciliation.
    """
    try:
        source = GuidanceSource.model_validate(await rpc('getWritingGuidance', {}))
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: invalid writing guidance; inspect module settings.') from None
    current = GuidanceTimestamp(saved_at=source.saved_at, revision=guidance_revision(source))
    if current != request.guidance_timestamp:
        raise ToolError('GuidanceChanged: call get_writing_guidance and reconsider the edit before writing.')
    public = request.model_dump(mode='json', exclude_unset=True)
    digest = hashlib.sha256(json.dumps(public, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()).hexdigest()
    params = request.model_dump(mode='json', exclude={'guidance_timestamp'}, exclude_unset=True)
    params.update(expected_guidance=source.model_dump(), request_digest=digest)
    if len(json.dumps(params, ensure_ascii=False, separators=(',', ':')).encode()) > 60000:
        raise ToolError('InvalidRequest: combined guidance and write exceed the RPC budget; split the content.')
    try:
        packet = await rpc('writeJournal', params)
    except ToolError as exc:
        if 'BridgeUnavailable' in str(exc):
            raise ToolError('WriteOutcomeUnknown: bridge did not confirm; read the target to reconcile, then reuse identical request_id/input. Do not blindly create a new request.') from None
        raise
    try:
        if isinstance(request.action, SetOwnership):
            result = OwnershipWriteResult.model_validate(packet)
            if result.request_id != request.request_id or result.count != len(result.entries) or result.count > request.action.limit:
                raise ValueError('invalid ownership receipt counts')
            seen = set()
            for entry in result.entries:
                validate_identity(entry.identity)
                if entry.identity.uuid in seen or (entry.status == 'failed') != ('error' in entry.model_fields_set):
                    raise ValueError('invalid ownership target/error')
                seen.add(entry.identity.uuid)
                target = request.action.target
                if target.kind != 'folder' and entry.identity.uuid != (target.page_uuid if target.kind == 'page' else 'JournalEntry.' + target.journal_id):
                    raise ValueError('wrong ownership target')
                if target.kind == 'folder' and (entry.identity.kind != 'journal' or (request.action.journal_ids is not None and entry.identity.journal_id not in request.action.journal_ids)):
                    raise ValueError('wrong folder batch target')
            if (result.status == 'partial') != any(entry.status in ('failed', 'not_attempted') for entry in result.entries):
                raise ValueError('inconsistent partial status')
            return result.model_dump(exclude_unset=True)
        result = WriteResult.model_validate(packet)
        validate_identity(result.identity, result.read_next_call)
        operation = request.action.operation
        kind = 'page' if operation == 'embed_image' else operation.split('_', 1)[1]
        if result.request_id != request.request_id or result.identity.kind != kind:
            raise ValueError('wrong receipt')
        if kind == 'page' and result.identity.type != 'text':
            raise ValueError('text mutation returned a non-text page')
        if operation.startswith('update_') or operation == 'embed_image':
            selector = {'folder': 'folder_id', 'journal': 'journal_id', 'page': 'page_uuid'}[kind]
            if getattr(result.identity, selector) != getattr(request.action, selector) or result.status == 'created':
                raise ValueError('wrong update target')
        elif result.status == 'updated':
            raise ValueError('wrong create status')
        if kind == 'page' and operation == 'create_page' and result.identity.journal_id != request.action.journal_id:
            raise ValueError('wrong page parent')
        return result.model_dump(exclude_unset=True)
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: invalid write receipt; reconcile the target before retrying.') from None


async def get_journal_ownership_context(request: OwnershipRequest):
    """Preview bounded journal ownership targets before set_ownership writes.

    Read get_writing_guidance first; GM instructions are critically important.
    Ready GM and Foundry14 required; core/system independent, world only, no
    compendiums. Use journal/folder IDs from get_journal_tree or page_uuid from
    get_journal_contents. target.kind selects folder/journal/page. Folder means
    ownership of existing contained journals, never a persisted/inherited folder
    ACL. recursive=false default is direct-only; true includes descendants.
    journal_ids optionally narrows a folder to1–100 known contained journal IDs.
    Individual journal/page targets do not accept these folder options.

    Default limit10 (1–100) is a hard target bound: ScopeTooLarge reports count
    and requires raising limit or a smaller discovered journal_ids subset. No
    truncated preview/pagination. max_bytes8000 default (8000–48000 compact UTF-8
    JSON bytes); ResponseTooLarge: raise budget or select fewer targets/users.
    user_ids defaults[]; choose up to100 non-GM IDs from
    get_journal_authoring_options(kind=players), including offline players.

    Returns named target,revision,count,recursive,entries,limitations. Each entry
    has canonical identity,ownership_default{present,value?},players[{user_id,
    present,value?,can_observe,parent_can_observe}]. Values -1/0/1/2/3 mean
    inherit/None/Limited/Observer/Owner; absent differs from explicit zero/inherit.
    can_observe is current public OBSERVER permission check, not proof of final
    rendered audience. parent_can_observe is null except for embedded pages.
    Limited is not full text read access. No GM selectors or Show GM Users.

    Pass revision as write_journal action.set_ownership.expected_revision with
    identical target/recursive/journal_ids/user_ids/limit and desired player
    changes. Revision covers scope, source and user roster; it is not a lock.
    ContentChanged: reread preview. Empty complete folder means zero current
    journals in that scope; no effect on future entries. PermissionDenied/
    NotReady: connect ready GM. Missing target: rediscover. InvalidRequest:
    restore valid scoped selectors. No mutations or broader user administration.
    """
    try:
        result = OwnershipContextResult.model_validate(await rpc('getJournalOwnershipContext', request.model_dump(exclude_none=True)))
        validate_identity(result.target)
        target = request.target
        selector = {'folder': 'folder_id', 'journal': 'journal_id', 'page': 'page_uuid'}[target.kind]
        if result.target.kind != target.kind or getattr(result.target, selector) != getattr(target, selector) or result.recursive != request.recursive:
            raise ValueError('wrong scope')
        if result.count != len(result.entries) or result.count > request.limit:
            raise ValueError('wrong count')
        seen = set()
        for entry in result.entries:
            validate_identity(entry.identity)
            if entry.identity.uuid in seen or [p.user_id for p in entry.players] != request.user_ids:
                raise ValueError('wrong preview IDs')
            seen.add(entry.identity.uuid)
            if target.kind != 'folder' and entry.identity.uuid != result.target.uuid:
                raise ValueError('wrong document')
            if target.kind == 'folder' and (entry.identity.kind != 'journal' or (request.journal_ids is not None and entry.identity.journal_id not in request.journal_ids)):
                raise ValueError('wrong contained journal')
            for stored in [entry.ownership_default, *entry.players]:
                if stored.present != ('value' in stored.model_fields_set) or (stored.present and stored.value is None):
                    raise ValueError('invalid stored ownership')
        return result.model_dump(exclude_unset=True)
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: invalid ownership preview; check server/module compatibility.') from None


class OptionsCursor(Model):
    offset: int = Field(ge=0, le=10000)
    revision: ChangeMarker


class OptionsRequest(Model):
    kind: Literal['players', 'fonts']
    limit: int = Field(default=10, ge=1, le=100)
    cursor: OptionsCursor | None = None
    max_bytes: int = Field(default=8000, ge=8000, le=48000)


class PlayerOption(Model):
    user_id: LocalId
    name: str


class FontOption(Model):
    font_family: str = Field(min_length=1, max_length=256)


class OptionsResult(Model):
    kind: Literal['players', 'fonts']
    world_id: str
    revision: ChangeMarker
    entries: list[PlayerOption | FontOption] = Field(max_length=100)
    total: int = Field(ge=0, le=10000)
    complete: bool
    next_cursor: OptionsCursor | None


async def get_journal_authoring_options(request: OptionsRequest):
    """Discover player User IDs for journal ownership or loaded font families.

    GM-only ready Foundry14, core/system independent. kind=players returns only
    non-GM users including offline players, with user_id,name. This is narrowly
    scoped to journal/folder-contained-journal ownership, not user administration.
    No Show GM Users option exists. kind=fonts returns font_family from public
    FontConfig.getAvailableFonts; discovery does not install fonts or guarantee
    the same fonts on other clients. UnsupportedCapability: omit font selection.
    Pass returned IDs to journal ownership and font_family to write_journal.format.
    Read get_writing_guidance before writing; GM instructions are critical.

    Returns kind,world_id,revision,entries,total,complete,next_cursor. Default
    limit10 (1–100), max_bytes8000 (8000–48000 compact UTF-8 JSON bytes). Either
    count or byte budget may shorten a page. Return next_cursor unchanged with
    identical kind; never construct it. Continuation binds world/list revision,
    not limit/bytes. ContentChanged: discard earlier pages and restart. Empty
    complete list means no non-GM users/no loaded fonts in this world, not that
    permissions or fonts are supported on every client. Up to10000 options.
    PermissionDenied/NotReady: connect existing ready GM. InvalidRequest: inspect
    schema; InvalidCursor: restart. No user changes, document writes or font loads.
    """
    try:
        result = OptionsResult.model_validate(await rpc('getJournalAuthoringOptions', request.model_dump(exclude_none=True)))
        if result.kind != request.kind or len(result.entries) > request.limit or result.complete != (result.next_cursor is None):
            raise ValueError('inconsistent options page')
        wanted = PlayerOption if request.kind == 'players' else FontOption
        if any(not isinstance(entry, wanted) for entry in result.entries):
            raise ValueError('wrong option kind')
        offset = request.cursor.offset if request.cursor else 0
        end = offset + len(result.entries)
        if end > result.total or result.complete != (end == result.total):
            raise ValueError('invalid counts')
        if result.next_cursor and (result.next_cursor.offset != end or result.next_cursor.revision != result.revision or not result.entries):
            raise ValueError('invalid continuation')
        if request.cursor and request.cursor.revision != result.revision:
            raise ValueError('stale continuation accepted')
        return result.model_dump(exclude_unset=True)
    except (ValueError, TypeError):
        raise ToolError('InvalidFoundryResponse: invalid authoring option page; check server/module compatibility.') from None


mcp.add_tool(SelectiveTool(name='get_journal_write_context', description=inspect.cleandoc(get_journal_write_context.__doc__),
    parameters=ContextRequest.model_json_schema(), output_schema=ContextResult.model_json_schema(),
    request_model=ContextRequest, response_model=ContextResult, handler=get_journal_write_context,
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)))

mcp.add_tool(SelectiveTool(name='write_journal', description=inspect.cleandoc(write_journal.__doc__),
    parameters=WriteRequest.model_json_schema(), output_schema=MutationResult.model_json_schema(),
    request_model=WriteRequest, response_model=MutationResult, handler=write_journal,
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)))

mcp.add_tool(SelectiveTool(name='get_journal_authoring_options', description=inspect.cleandoc(get_journal_authoring_options.__doc__),
    parameters=OptionsRequest.model_json_schema(), output_schema=OptionsResult.model_json_schema(),
    request_model=OptionsRequest, response_model=OptionsResult, handler=get_journal_authoring_options,
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)))

mcp.add_tool(SelectiveTool(name='get_journal_ownership_context', description=inspect.cleandoc(get_journal_ownership_context.__doc__),
    parameters=OwnershipRequest.model_json_schema(), output_schema=OwnershipContextResult.model_json_schema(),
    request_model=OwnershipRequest, response_model=OwnershipContextResult, handler=get_journal_ownership_context,
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)))
