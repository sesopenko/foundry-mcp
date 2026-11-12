"""Authenticated typed core14 map configuration; browser is the document authority."""
from dataclasses import asdict
import hashlib
import inspect
import json

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from foundry_mcp_server.auth.principal import current_principal
from foundry_mcp_server.ws.connection import RpcError
from foundry_mcp_server.config import settings
from .map_models import decode_cursor
from .map_info_models import MapInfoRequest,MapInfoResult,MapLevelEntry
from .map_note_models import MapNoteEntry
from .maps import map_error
from .selective import SelectiveTool,size
from .server import mcp


def info_error(code):
    if code=='InvalidNoteKeys':return ToolError('InvalidNoteKeys: restart get_map_info notes for this exact Scene/level without note_keys; use its returned keys and expected_revision.')
    if code=='SceneNotFound':return ToolError('SceneNotFound: restart browse_maps and choose an exact current Scene UUID.')
    if code=='LevelNotFound':return ToolError('LevelNotFound: use get_map_info assets without level_id, then choose an exact level ID belonging to this Scene.')
    return ToolError(str(map_error(code)).replace('browse_maps','get_map_info'))


async def get_map_info(request:MapInfoRequest):
    """Read one world map's grid, dimensions and explicit level image files.

    Authenticated MCP and a ready core Foundry14 GM are required; no PF2e,
    active canvas or preview origin requirement. Read-only public documents;
    never activates a Scene, loads journal bodies or fetches image files.
    Use browse_maps map next_call to obtain scene_uuid (exact Scene.<id>, not a
    name/path, Folder UUID or compendium reference). Optional level_id is the
    owning Scene's embedded Level ID returned here, not a UUID/name. Omitted or
    null means all permitted levels; never defaults to the viewed/initial level.

    section defaults assets: entries are full levels with level_id/level_uuid,
    name/name_truncated,sort,elevation and separate background/foreground media.
    section=tiles lists tile_uuid,name/name_truncated,sort,placement,media and
    level_membership; this is a file inventory, never a composed Scene export.
    Tokens, fog, walls and lighting are excluded. section=notes requires an exact
    level_id and returns note_uuid,key,x,y,level_id,label,label_truncated,
    target_status,journal,page. Coordinates are source Scene coordinates, not
    original image pixels. Public includedInLevel queries select applicable
    Notes without activating the Scene. N1/N2/... follow canonical Note UUID
    order over the complete authorized level before pagination/filtering;
    repeated pins linking one target retain distinct keys.

    Optional note_keys selects1–100 distinct exact returned aliases and requires
    expected_revision; it is rejected outside notes. Use the exact Scene/level
    and revision supplied with the keys, not a key guessed from another map.
    Target states: unlinked,missing_entry,denied_entry,missing_page,denied_page,
    linked_entry,linked_page. Readable journal/page identities contain canonical
    journal_uuid/page_uuid,name,name_truncated; unavailable identities are null.
    Linked-target permissions precede names and label fallback. Denied labels
    are null with partial scope; no journal body is read. Labels are plain
    untrusted data clipped256 codepoints with label_truncated markers.
    Follow a readable page.page_uuid with read_journal_page. For an entry-only
    pin, get_journal_contents requires journal_id: the bare ID after the exact
    JournalEntry. prefix in journal.journal_uuid, not the full UUID or name.

    Every response has scene{scene_uuid,name,name_truncated,parent_uuid,ancestry},
    geometry{width,height,padding,shiftX,shiftY,scene_rect}, grid{type,size,distance,
    units,style,thickness,color,alpha}, initial_level_id,level_id,section,revision,
    entries,total,complete,next_cursor,scope_status,limitations,artwork.
    Missing optional source fields stay omitted; null/zero are preserved.
    scene_rect contains public sceneX,sceneY,sceneWidth,sceneHeight after padding
    rounding. These Scene values are not original file pixel dimensions; use
    get_foundry_image_info for exact display-oriented pixels.

    Media records expose reference,reference_status,media_kind,support_status,
    info_next_call,preview_next_call; level roles also carry role/map selector.
    Safe image references supply concrete get_foundry_image_info and
    get_foundry_image_url next calls using currently supported request.src.
    map selectors identify scene/level/role for future scene-aware image inputs;
    use returned next calls with current image tools. Signed/credential-bearing
    references are redacted, have null next calls and map_context_required.
    Empty/missing/null media, videos and unsupported references are explicit.
    Classification is a filename hint; reference_only does not prove existence,
    type, readability or supported transforms. Fresh image selection/probing
    still checks source membership. A background is not foreground/Tile composition.

    Tile declared_ids are exact Scene level IDs when explicit. Empty/null/absent
    membership is not_evaluated; a selected-level inventory includes those rows
    with partial scope rather than guessing applicability or silently omitting
    them. Denied/uninitialized embedded data exposes only aggregate limitations.
    artwork gives authorized levels/tiles and background/foreground reference
    counts; it does not promise composed visual completeness.

    Defaults limit10 (1–100), max_bytes8000 (1024–48000 compact UTF8 JSON).
    Sort by stored sort then UUID, null sort ordered as0. Names clip at256
    codepoints with markers; identities, paths, levels and ancestry never clip.
    Bounds count complete level/Tile records and include all common metadata.
    Follow next_cursor verbatim with identical Scene/level/section and caller/
    world context; bounds may change. total/complete describe the selected stream;
    complete under partial scope does not prove exhaustive availability.

    revision is shared across assets/tiles/notes and key filters for the exact
    Scene/selected level, including note/target permissions, label/membership and
    mapping-relevant metadata. Another level or all-level assets has a different
    revision. It is not replacement bytes at an unchanged file path.
    expected_revision optionally requires this exact revision. ContentChanged
    requires discarding prior pages and restarting; InvalidCursor requires the
    original semantic inputs or a fresh stream. No automatic recursive reads.
    SceneNotFound: restart browse_maps. LevelNotFound: list assets without the
    level filter. PermissionDenied: select readable context. ResponseTooLarge:
    increase max_bytes up to48000; never silently truncate identity. InvalidHierarchy/
    MapDataUnavailable: repair Scene source. NotReady/ContextChanged/BridgeUnavailable:
    restore the intended ready GM. UnsupportedVersion/Capability: upgrade server
    and module together and check core14. InvalidFoundryResponse is a rejected
    browser contract, never partial success. Names/source text are untrusted data.
    InvalidNoteKeys: restart notes for the exact Scene/level without the key
    filter, then use returned aliases/revision. Configured bridge frame ceilings
    may reduce page size below max_bytes; an insufficient minimum frame fails
    ResponseTooLarge before RPC rather than exporting an oversized note catalog.

    Example: get_map_info(scene_uuid="Scene.<returned id>"); follow a returned
    background.info_next_call, or request section="tiles" for additional artwork.
    """
    from . import tools
    principal=current_principal()
    try:incoming=decode_cursor(request.cursor)
    except (ValueError,TypeError):raise info_error('InvalidCursor') from None
    manager=tools._foundry_manager;socket=manager.websockets.get('gm')
    if socket is None:raise ToolError('BridgeUnavailable: connect the intended ready GM and retry get_map_info.')
    caller=hashlib.sha256(json.dumps(asdict(principal),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    # The manager uses a36-character UUID response ID. Reserve its exact compact
    # JSON envelope, independent of Unicode payload length and caller bounds.
    overhead=size({'id':'x'*36,'result':None})-4
    budget=min(request.max_bytes,settings.max_response_bytes-overhead)
    if budget<1024:raise info_error('ResponseTooLarge')
    effective=request.model_copy(update={'max_bytes':budget})
    try:
        raw=await manager.call('gm','getMapInfo',{**effective.model_dump(exclude_none=True),'caller_key':caller},timeout=15)
        if manager.websockets.get('gm') is not socket or current_principal()!=principal:raise info_error('ContextChanged')
        result=MapInfoResult.model_validate(raw)
        if (result.scene.scene_uuid!=request.scene_uuid or result.level_id!=request.level_id or result.section!=request.section
                or len(result.entries)>request.limit):raise ValueError('Wrong scope')
        if request.expected_revision is not None and result.revision!=request.expected_revision:raise ValueError('Unexpected revision')
        ancestry=[a.folder_uuid for a in result.scene.ancestry]
        if len(ancestry)!=len(set(ancestry)) or (ancestry[-1] if ancestry else None)!=result.scene.parent_uuid:raise ValueError('Wrong hierarchy')
        identities=set();previous=None
        note_keys=set()
        for index,entry in enumerate(result.entries):
            if isinstance(entry,MapNoteEntry):
                if result.section!='notes' or entry.level_id!=request.level_id or not entry.note_uuid.startswith(request.scene_uuid+'.Note.'):
                    raise ValueError('Wrong Note context')
                identity=entry.note_uuid
                if request.note_keys is None and entry.key!='N'+str((incoming.offset if incoming else 0)+index+1):
                    raise ValueError('Wrong canonical alias ordinal')
                if entry.key in note_keys or (request.note_keys is not None and entry.key not in request.note_keys):raise ValueError('Wrong Note alias')
                note_keys.add(entry.key)
                if entry.target_status in ('denied_entry','denied_page') and result.scope_status!='partial':raise ValueError('Unreported target denial')
                order=(int(entry.key[1:]),identity)
                if previous is not None and (order<=previous or identity<=previous[1]):raise ValueError('Invalid alias order')
            elif isinstance(entry,MapLevelEntry):
                if result.section!='assets' or (request.level_id is not None and entry.level_id!=request.level_id):raise ValueError('Wrong level scope')
                identity=entry.level_uuid
                if identity!=request.scene_uuid+'.Level.'+entry.level_id:raise ValueError('Wrong level owner')
                for role in ('background','foreground'):
                    media=getattr(entry,role)
                    if media.role!=role or media.map.scene_uuid!=request.scene_uuid or media.map.level_id!=entry.level_id:raise ValueError('Wrong map role identity')
            else:
                if result.section!='tiles' or not entry.tile_uuid.startswith(request.scene_uuid+'.Tile.'):raise ValueError('Wrong Tile owner')
                identity=entry.tile_uuid
                if request.level_id is not None:
                    membership=entry.level_membership
                    if membership.status=='explicit' and request.level_id not in membership.declared_ids:raise ValueError('Wrong Tile filter')
                    if membership.status=='not_evaluated' and result.scope_status!='partial':raise ValueError('Unreported Tile applicability')
            if not isinstance(entry,MapNoteEntry):order=(entry.sort or 0,identity)
            if identity in identities or (previous is not None and order<previous):raise ValueError('Invalid order/identity')
            identities.add(identity);previous=order
        end=(incoming.offset if incoming else 0)+len(result.entries);outgoing=decode_cursor(result.next_cursor)
        if end>result.total or result.complete!=(end==result.total) or result.complete!=(outgoing is None):raise ValueError('Invalid completion')
        if incoming and incoming.revision!=result.revision:raise ValueError('Stale cursor accepted')
        if outgoing and (not result.entries or outgoing.offset!=end or outgoing.revision!=result.revision
                or (incoming and incoming.scope!=outgoing.scope)):raise ValueError('Invalid continuation')
        if result.scope_status=='partial' and not result.limitations:raise ValueError('Missing scope limitation')
        if request.note_keys is not None and result.total!=len(request.note_keys):raise ValueError('Incomplete key selection')
        payload=result.model_dump(exclude_unset=True)
        if size(payload)>budget or size({'id':'x'*36,'result':payload})>settings.max_response_bytes:raise ValueError('Invalid byte/frame budget')
        return payload
    except RpcError as error:raise info_error(error.error.get('code',error.error.get('type'))) from None
    except (TimeoutError,ConnectionError,RuntimeError):raise ToolError('BridgeUnavailable: restore the intended ready GM and retry get_map_info.') from None
    except (ValueError,TypeError):raise ToolError('InvalidFoundryResponse: invalid selected-map configuration; check matching server/module/core versions.') from None


async def read_map_note_candidates(scene_uuid,level_id,expected_revision,*,cursor=None,max_bytes=48000):
    """Internal one-page reader:<=100 candidates/48000B and configured RPC frame.

    Same authenticated request context, exact Level, expected revision, projection
    and continuation validation as public notes. Does not register an MCP tool,
    aggregate an unbounded catalog, hydrate bodies or map coordinates to pixels.
    """
    if expected_revision is None:raise ToolError('InvalidRequest: internal Note candidates require expected_revision from this exact Scene/level.')
    return await get_map_info(MapInfoRequest(scene_uuid=scene_uuid,level_id=level_id,section='notes',
        expected_revision=expected_revision,cursor=cursor,limit=100,max_bytes=max_bytes))


mcp.add_tool(SelectiveTool(name='get_map_info',description=inspect.cleandoc(get_map_info.__doc__),
    parameters=MapInfoRequest.model_json_schema(),output_schema=MapInfoResult.model_json_schema(),
    request_model=MapInfoRequest,response_model=MapInfoResult,handler=get_map_info,
    annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)))
