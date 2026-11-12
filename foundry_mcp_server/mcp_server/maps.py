"""Typed authenticated core map browsing; browser remains the document authority."""
from dataclasses import asdict
import hashlib
import inspect
import json

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from .map_models import BrowseMapsRequest,BrowseMapsResult,decode_cursor,MapFolderNode
from .selective import SelectiveTool,size
from .server import mcp
from foundry_mcp_server.auth.principal import current_principal
from foundry_mcp_server.ws.connection import RpcError

ERRORS={
    'InvalidRequest':'Use the published browse_maps fields and bounds.',
    'InvalidCursor':'Return next_cursor unchanged with identical folder/filter, or restart without cursor.',
    'ContentChanged':'Discard prior pages and restart browse_maps without cursor; metadata or permissions changed.',
    'ContextChanged':'Reconnect the intended ready GM and restart browse_maps.',
    'FolderNotFound':'Selected folder is missing; restart browse_maps at root.',
    'InvalidFolder':'Choose a Scene Folder UUID from browse_maps, not another document type.',
    'PermissionDenied':'Selected map scope is unavailable; use a readable parent and the ready authorized GM.',
    'InvalidHierarchy':'Repair missing/cyclic Scene-folder relationships in Foundry, then restart browse_maps.',
    'ResponseTooLarge':'Increase max_bytes up to48000 or choose a shallower folder; complete identities are never silently truncated.',
    'NotReady':'Wait for the intended GM world to become ready, then retry.',
    'UnsupportedVersion':'Map browsing requires matching module/server on Foundry14.',
    'UnsupportedCapability':'Required public document APIs are unavailable; check module/core compatibility.',
    'MapDataUnavailable':'Public map metadata is malformed or unsupported; repair world data and retry.',
}


def map_error(code):
    if code not in ERRORS:return ToolError('MapReadFailed: map browsing failed; check matching module/server/core versions and reconnect the ready GM.')
    return ToolError(code+': '+ERRORS[code])


async def browse_maps(request:BrowseMapsRequest):
    """Browse world Scene folders and named maps without activating a Scene.

    Authenticated MCP and a ready Foundry14 GM are required; no PF2e or active
    canvas requirement, and no public image origin needed. Read-only world Scenes
    and Scene folders, including imported adventures; excludes unimported
    compendium catalogs, image-content search and composed Scene rendering.
    Names are untrusted data. Permission-denied names/paths are never returned.

    Start with {} (folder_uuid=null/root), or pass a folder entry's next_call.
    folder_uuid is an exact Folder.<id> UUID from this tool, not a name/path or
    Scene UUID. Map entries carry Scene.<id> UUIDs and get_map_info next calls;
    use that tool to inspect grid/level assets, then get_foundry_image_info and
    get_foundry_image_url for a selected file. image_status=not_checked includes
    Scenes without usable media; browsing never promises an image exists.

    name_contains defaults empty, literal case-insensitive substring of full
    immediate-child names only (<=256 characters). It is not recursive or
    semantic search. Folders precede maps. Root sorts alphabetically; inside a
    folder its saved sorting a/m controls alphabetical/manual order, with UUID
    as the final tie-break. Missing sort is null, ordered as zero. The browser's
    reported locale participates in revision. Duplicate names remain separate.

    Defaults limit10 (1–100), max_bytes8000 (1024–48000 compact UTF8 JSON).
    Returns location{folder_uuid,name,name_truncated,ancestry,sorting,locale},
    revision,entries,total,complete,next_cursor,scope_status,limitations.
    Each entry has kind,parent_uuid,name,name_truncated,ancestry,sort,next_call;
    folders add folder_uuid/sorting, maps add scene_uuid/image_status.
    Named ancestry runs root to parent, excluding the object itself. Names over
    256 codepoints are clipped with markers; UUIDs/ancestry are never silently
    clipped. Empty folders remain navigable. total counts authorized local
    matches; a complete empty page under partial scope is not exhaustive absence.

    Follow next_cursor verbatim with identical folder/name_contains and caller/
    world context; limit/max_bytes may change. Complete means this selected
    stream, not all world maps. ContentChanged requires discarding previous
    pages and restarting. Revision tracks catalog metadata/permissions, not file
    replacement bytes or get_map_info's separate selected-map revision.
    Loaded world metadata is scanned before output pagination; no upstream
    server search or automatic folder recursion is performed.

    FolderNotFound: restart at root. InvalidFolder: choose a returned Scene-folder
    UUID. PermissionDenied/NotReady/ContextChanged: restore intended ready GM or
    readable parent. InvalidHierarchy/MapDataUnavailable: repair source metadata.
    InvalidCursor: restart or reuse original semantic inputs. ResponseTooLarge:
    raise max_bytes or use shallower scope; no partial identity is returned.
    UnsupportedVersion/Capability/MapReadFailed: check matching core/module/server.
    """
    from . import tools
    principal=current_principal()
    try:incoming=decode_cursor(request.cursor)
    except (ValueError,TypeError):raise map_error('InvalidCursor') from None
    manager=tools._foundry_manager
    socket=manager.websockets.get('gm')
    if socket is None:raise ToolError('BridgeUnavailable: connect the existing ready authorized GM and retry browse_maps.')
    caller_key=hashlib.sha256(json.dumps(asdict(principal),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    try:
        raw=await manager.call('gm','browseMaps',{**request.model_dump(exclude_none=True),'caller_key':caller_key},timeout=15)
        if manager.websockets.get('gm') is not socket or current_principal()!=principal:raise map_error('ContextChanged')
        result=BrowseMapsResult.model_validate(raw)
        if result.location.folder_uuid!=request.folder_uuid or len(result.entries)>request.limit:raise ValueError('Wrong scope')
        if request.folder_uuid is None and (result.location.name!='World Scenes' or result.location.ancestry or result.location.sorting!='a'):
            raise ValueError('Wrong root identity')
        ancestors=result.location.ancestry
        ids=[a.folder_uuid for a in ancestors]
        if len(ids)!=len(set(ids)) or request.folder_uuid in ids:raise ValueError('Invalid ancestry')
        expected=ancestors+([] if request.folder_uuid is None else [dict(folder_uuid=request.folder_uuid,
            name=result.location.name,name_truncated=result.location.name_truncated)])
        expected=[v.model_dump() if hasattr(v,'model_dump') else v for v in expected]
        seen=set();maps_started=False
        for entry in result.entries:
            identity=entry.folder_uuid if isinstance(entry,MapFolderNode) else entry.scene_uuid
            if identity in seen or entry.parent_uuid!=request.folder_uuid or [a.model_dump() for a in entry.ancestry]!=expected:
                raise ValueError('Invalid entry identity/context')
            seen.add(identity)
            if isinstance(entry,MapFolderNode):
                if maps_started or entry.next_call.arguments.folder_uuid!=identity:raise ValueError('Invalid folder followup/order')
            else:
                maps_started=True
                if entry.next_call.arguments.scene_uuid!=identity:raise ValueError('Invalid map followup')
        offset=incoming.offset if incoming else 0
        end=offset+len(result.entries)
        outgoing=decode_cursor(result.next_cursor)
        if end>result.total or result.complete!=(end==result.total) or result.complete!=(outgoing is None):raise ValueError('Invalid completion')
        if incoming and incoming.revision!=result.revision:raise ValueError('Stale cursor accepted')
        if outgoing and (not result.entries or outgoing.offset!=end or outgoing.revision!=result.revision
                or (incoming and outgoing.scope!=incoming.scope)):raise ValueError('Invalid continuation')
        if result.scope_status=='partial' and not result.limitations:raise ValueError('Missing scope limitation')
        payload=result.model_dump(exclude_unset=True)
        if size(payload)>request.max_bytes:raise ValueError('Oversize response')
        return payload
    except RpcError as error:
        raise map_error(error.error.get('code',error.error.get('type'))) from None
    except (TimeoutError,ConnectionError,RuntimeError):
        raise ToolError('BridgeUnavailable: reconnect the existing ready GM and retry browse_maps.') from None
    except (ValueError,TypeError):
        raise ToolError('InvalidFoundryResponse: invalid map listing or identity; check matching module/server/core versions.') from None


mcp.add_tool(SelectiveTool(name='browse_maps',description=inspect.cleandoc(browse_maps.__doc__),
    parameters=BrowseMapsRequest.model_json_schema(),output_schema=BrowseMapsResult.model_json_schema(),
    request_model=BrowseMapsRequest,response_model=BrowseMapsResult,handler=browse_maps,
    annotations=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)))
