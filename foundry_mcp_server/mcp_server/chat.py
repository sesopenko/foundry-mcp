"""Bounded core14 chat tools; no system-specific interpretation or deletion."""
import inspect
import json
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool, ToolResult
from mcp.types import ToolAnnotations
from .selective import rpc
from .server import mcp

ChatMode = Literal['Public as User', 'private to game masters', 'blind to game masters', 'self only', 'public as character']


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Author(Model):
    id: str | None
    name: str | None


class Speaker(Model):
    actor: str | None
    alias: str | None
    scene: str | None
    token: str | None


class Message(Model):
    id: str = Field(min_length=1, max_length=64)
    timestamp: int = Field(ge=0)
    author: Author
    speaker: Speaker
    whisper: list[str]
    blind: bool
    names_truncated: bool = Field(description='Author name or speaker alias exceeded 128 Unicode characters and was clipped; IDs remain exact.')


class ReadMessage(Message):
    content: str | None
    content_available_separately: bool

    @model_validator(mode='after')
    def content_status(self):
        if (self.content is None) != self.content_available_separately:
            raise ValueError('Oversized content must be null and available separately')
        return self


class ReadResult(Model):
    messages: list[ReadMessage] = Field(max_length=100)
    cursor: str = Field(min_length=1, max_length=1000)
    has_more: bool
    scope: Literal['loaded_visible_history']


class ContentResult(Model):
    message_id: str
    content: str
    revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    next_offset: int | None = Field(ge=0)


class SendResult(Message):
    mode: ChatMode
    request_id: str

STYLE_GUIDE = """Throughout this rulebook, you will see formatting standards that might look a bit unusual at first. Specifically, the game’s rules are set apart in this text using specialized capitalization and italicization. These standards are in place to make the rules elements in this book easier to recognize.

The names of specific statistics, skills, feats, actions, and some other mechanical elements in Pathfinder are capitalized. This way, when you see the statement “a Strike targets Armor Class,” you know that both Strike and Armor Class are referring to rules.

If a word or a phrase is italicized, it is describing a spell or a magic item. This way, when you see the statement “the door is sealed by lock,” you know that in this case the word denotes the lock spell, rather than a physical item.

Pathfinder also uses many terms that are typically expressed as abbreviations, like AC for Armor Class, DC for Difficulty Class, and HP for Hit Points. If you’re ever confused about a game term or an abbreviation, you can always turn to the Glossary and Index, beginning on page 628, and look it up!"""


class GuideResult(Model):
    text: str
    attribution_status: Literal['user_supplied_publication_unverified']


async def get_pathfinder_writing_style_guide() -> GuideResult:
    """Retrieve the exact user-supplied Paizo writing-conventions passage on demand.

    No inputs or Foundry connection. Returns text and attribution_status; publication
    attribution is unverified. The passage's page628 reference applies only to its
    original book. This is prose capitalization/italicization guidance, separate
    from PF2e wiki inline syntax; use create_pf2e_inline_check/roll/embed for syntax.
    """
    return {'text': STYLE_GUIDE, 'attribution_status': 'user_supplied_publication_unverified'}


class ChatRead(Model):
    after_id: str | None = Field(None, min_length=1, max_length=64, description='Exclusive message ID from read_chat_messages or send_chat_message; missing anchors error. Not a UUID/name.')
    cursor: str | None = Field(None, min_length=1, max_length=1000, description='Pass returned cursor unchanged, including after has_more=false to poll later. Bound to browser session, world and GM; reload makes it stale. Mutually exclusive with after_id.')
    limit: int = Field(10, ge=1, le=100)
    max_bytes: int = Field(8000, ge=2000, le=48000)

    @model_validator(mode='after')
    def combinations(self):
        if self.after_id and self.cursor:
            raise ValueError('Use after_id or cursor, not both')
        return self


async def read_chat_messages(request: ChatRead) -> ReadResult:
    """Read loaded visible chat history through the connected core14 GM, all systems.

    Returns messages (id,timestamp,author{id,name},speaker{actor,alias,scene,token},
    whisper recipient IDs,blind,content,content_available_separately,names_truncated),
    cursor,has_more,scope. First observed batch sorts timestamp then lexical ID;
    later observed batches append in that order, including backdated/equal timestamps.
    Copy cursor unchanged into request.cursor for next page or polling. Boundary
    is exclusive. Edits are not replayed; content is current at each read. Deleted
    cursor anchors remain usable; browser reload/world/GM change invalidates cursors:
    restart history or use an existing after_id. Deleted after_id errors: restart
    or use saved cursor. Empty means no newer
    visible loaded messages, not proof of complete archived history. Hidden content
    is excluded. Oversized content=null/content_available_separately=true: use
    read_chat_message_content. Ten entries/8000 compact JSON bytes default; count
    max100/bytes max48000. At most50000 observed IDs per browser session; excess
    errors, never truncates. Names clipped at128 characters, IDs exact. No rendering
    or roll evaluation. Connect GM on BridgeUnavailable/NotReady; restart on
    InvalidCursor; raise max_bytes on ResponseTooLarge. Example {"request":{"limit":10}}.
    """
    return ReadResult.model_validate(await rpc('readChatMessages', request.model_dump(exclude_none=True)))


async def read_chat_message_content(message_id: str, offset: int = Field(0, ge=0), revision: str | None = None) -> ContentResult:
    """Read exact stored HTML in at most 1000 UTF-16 units from a visible message.

    Use id from read_chat_messages. Returns message_id,content,revision,next_offset
    (null when complete). Pass returned next_offset and revision; concatenate fragments
    unchanged. StaleContent means edited: restart offset=0 without revision.
    DocumentNotFound means missing/invisible. Requires ready core14 GM, all systems.
    """
    return ContentResult.model_validate(await rpc('readChatMessageContent', dict(message_id=message_id, offset=offset, revision=revision)))


class ChatSend(Model):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9-]{16,64}$', description='Unique send key. Reuse only identical input. Concurrent attempts coalesce; stored flags detect an existing loaded message across reload. Deleted/archived messages cannot deduplicate; reconcile uncertain outcomes before retrying.')
    mode: ChatMode
    content: str = Field(min_length=1, max_length=16000, description='At most 16000 UTF-8 bytes; basic HTML text, headings, lists, tables and text styles. Images, links, event attributes and immediate inline rolls rejected. Deferred inline rolls/checks/embeds from the PF2e builders are accepted as source; no roll is requested by this tool.')
    actor_id: str | None = Field(None, max_length=64, description='World character Actor ID from search_actors, required only for public as character. Never UUID/name.')

    @model_validator(mode='after')
    def combinations(self):
        if not self.content.strip() or len(self.content.encode('utf-8')) > 16000:
            raise ValueError('content must contain non-whitespace text within 16000 UTF-8 bytes')
        if (self.mode == 'public as character') != bool(self.actor_id):
            raise ValueError('actor_id required only for public as character')
        return self


async def send_chat_message(request: ChatSend) -> SendResult:
    """Create one HTML chat message as the connected core14 GM; all systems.

    Author always connected GM. Public as User: public, GM alias; private to game
    masters: GM recipients, GM alias; blind to game masters: same recipients with
    blind flag (a GM author can still see it); self only: connected GM recipient;
    public as character: public, selected owned character speaker, GM author.
    No audience/speaker substitution. Returns id,timestamp,author,speaker,whisper,
    blind,mode,request_id,names_truncated; id can anchor read_chat_messages. Names
    clipped at128 characters; IDs exact. Only world Actors with type character
    can speak as characters; other types error UnsupportedCharacterType. Other
    chat modes use core APIs without PF2e semantics; Actor discovery currently
    requires PF2e. No deletion/clearing. Core HTMLField
    sanitizes persisted HTML; returned content must be checked via chat reading
    if exact formatting matters. Supports heading/block/inline/list/table tags;
    style permits text-align,font-size,font-family,font-weight,font-style,
    text-decoration,color,background-color; table colspan/rowspan 1–100 only.
    Unknown tags/attributes (including images/links/events) are rejected before
    creation; parser normalizes basic HTML. No arbitrary editor HTML guarantee.
    InvalidHTML/InvalidRequest: correct input. Missing/denied character: rediscover
    with search_actors. Any transport timeout/disconnect can mean it was sent:
    inspect read_chat_messages before retrying; retain request_id. Deduplication
    retains1000 attempts/browser session; stored flags also detect loaded messages
    after reload. Deleted/archived messages cannot deduplicate. RequestConflict:
    inspect the original send, never change input under the same request_id.
    PF2e inline builders supply source; enrichment varies by destination/system.
    """
    try:
        return SendResult.model_validate(await rpc('sendChatMessage', request.model_dump(exclude_none=True)))
    except ToolError as exc:
        raise ToolError(f'{exc} Send may have completed; reconcile chat before retrying, especially after reload.') from None


class ReadArguments(Model):
    request: ChatRead = Field(default_factory=ChatRead)


class SendArguments(Model):
    request: ChatSend


class ContentArguments(Model):
    message_id: str = Field(min_length=1, max_length=64, description='Message id from read_chat_messages; not UUID/name.')
    offset: int = Field(0, ge=0, description='UTF-16 offset; use returned next_offset.')
    revision: str | None = Field(None, pattern=r'^[0-9a-f]{64}$', description='Required with nonzero offset; use returned SHA-256 revision unchanged.')

    @model_validator(mode='after')
    def continuation(self):
        if self.offset and not self.revision:
            raise ValueError('Nonzero offset requires returned revision')
        return self


class ChatTool(Tool):
    """Explicit Pydantic input/output validation with compact, secret-free errors."""
    request_model: Any
    response_model: Any
    handler: Any

    async def run(self, arguments):
        try:
            request = self.request_model.model_validate(arguments)
        except ValidationError as exc:
            fields = [dict(field='.'.join(map(str, e['loc'])), type=e['type']) for e in exc.errors()]
            raise ToolError('InvalidRequest: correct fields against published schema: ' + json.dumps(fields)) from None
        try:
            value = await self.handler(**{name: getattr(request, name) for name in type(request).model_fields})
            result = self.response_model.model_validate(value).model_dump(mode='json')
        except ValidationError:
            raise ToolError('InvalidFoundryResponse: update server/module together; for sending, reconcile chat before any retry.') from None
        max_bytes = request.request.max_bytes if isinstance(request, ReadArguments) else 8000
        if isinstance(request, ReadArguments) and (len(result['messages']) > request.request.limit or len({m['id'] for m in result['messages']}) != len(result['messages'])):
            raise ToolError('InvalidFoundryResponse: chat page exceeds count or repeats IDs; update server/module together.')
        if isinstance(request, SendArguments) and (result['mode'] != request.request.mode or result['request_id'] != request.request.request_id):
            raise ToolError('InvalidFoundryResponse: send identity mismatch; reconcile chat before retrying.')
        if len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) > max_bytes:
            raise ToolError('ResponseTooLarge: raise max_bytes up to48000; for sending, reconcile chat before retrying.')
        return ToolResult(content=result, structured_content=result)


for name, request_model, response_model, handler, read_only in (
    ('read_chat_messages', ReadArguments, ReadResult, read_chat_messages, True),
    ('read_chat_message_content', ContentArguments, ContentResult, read_chat_message_content, True),
    ('send_chat_message', SendArguments, SendResult, send_chat_message, False),
    ('get_pathfinder_writing_style_guide', Model, GuideResult, get_pathfinder_writing_style_guide, True),
):
    mcp.add_tool(ChatTool(name=name, description=inspect.cleandoc(handler.__doc__),
                          parameters=request_model.model_json_schema(), output_schema=response_model.model_json_schema(),
                          request_model=request_model, response_model=response_model, handler=handler,
                          annotations=ToolAnnotations(readOnlyHint=read_only, destructiveHint=False,
                                                      idempotentHint=read_only, openWorldHint=False)))
