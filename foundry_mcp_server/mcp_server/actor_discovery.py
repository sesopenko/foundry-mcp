"""PF2e-specific world discovery for character/npc/familiar Actor identities.

Uses core document/folder relationships only; no derived PF2e statistics or role
inference. Contract/version boundary: docs/actor-tools.md, core14.369/PF2e8.6.1.
https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.FolderData.html
"""
import asyncio
import json
from typing import Annotated, Any, Literal

from pydantic import Field

from foundry_mcp_server.ws.connection import RpcError
from .actors import (Identifier, Cursor, Limit, ByteLimit, _error, _identifier,
                     _identity, _pagination, _primitive, _runtime, _strings, _tool)

ActorType = Literal['character', 'npc', 'familiar']
ActorTypes = Annotated[list[ActorType], Field(min_length=1, max_length=3)]
Depth = Annotated[int, Field(ge=1, le=5, strict=True)]
StrictBool = Annotated[bool, Field(strict=True)]
SearchQuery = Annotated[str, Field(min_length=1, max_length=200, strict=True)]


def _bounds(folder_uuid, limit, max_bytes, cursor):
    _identifier(folder_uuid, 'folder_uuid')
    if type(limit) is not int or not 1 <= limit <= 100 or type(max_bytes) is not int or not 8000 <= max_bytes <= 48000:
        raise _error('InvalidRequest', 'limit must be integer 1–100 and max_bytes integer 8000–48000.', 'Use published bounds; booleans are invalid.')
    if cursor is not None and (type(cursor) is not str or not 1 <= len(cursor) <= 4096 or not cursor.isascii()):
        raise _error('InvalidRequest', 'cursor must be 1–4096 ASCII characters.', 'Return the provided next_cursor unchanged or restart without cursor.')


def _scope(scope):
    return (type(scope) is dict and set(scope) == {'id', 'status', 'reason'} and
            type(scope['id']) is str and scope['status'] in ('searched','failed','incomplete','denied') and
            (scope['reason'] is None or type(scope['reason']) is str))


def _named_folder(folder):
    return (type(folder) is dict and set(folder) == {'id','uuid','name','name_truncated'} and
            all(type(folder[key]) is str for key in ('id','uuid','name')) and
            1 <= len(folder['uuid']) <= 512 and type(folder['name_truncated']) is bool)


def _node(node, tree):
    if type(node) is not dict or node.get('kind') not in ('actor','folder'):
        return False
    if node['kind'] == 'folder':
        keys = {'kind','id','uuid','name','name_truncated','parent_uuid','depth','children_complete','expand'}
        if not tree or set(node) != keys or not _named_folder({key:node[key] for key in ('id','uuid','name','name_truncated')}):
            return False
        expand=node['expand']
        if type(node['children_complete']) is not bool or (expand is not None and (type(expand) is not dict or set(expand) != {'folder_uuid'} or expand['folder_uuid'] != node['uuid'])):
            return False
        if node['children_complete'] != (expand is None):
            return False
    else:
        keys = {'kind','identity','parent_uuid','depth','folder_path','next_call'}
        if set(node) != keys or not _identity(node['identity']):
            return False
        identity=node['identity']
        if identity['document_name'] != 'Actor' or identity['source_kind'] != 'world' or identity['type'] not in ('character','npc','familiar') or identity['pack'] is not None or identity['instance'] is not None:
            return False
        if type(node['folder_path']) is not list or not all(_named_folder(folder) for folder in node['folder_path']):
            return False
        if node['next_call'] != dict(tool='read_actor',arguments=dict(actor_uuid=identity['uuid'])):
            return False
    return ((node['parent_uuid'] is None or type(node['parent_uuid']) is str and 1 <= len(node['parent_uuid']) <= 512) and
            type(node['depth']) is int and node['depth'] >= 0)


def _validate(result, *, tree, limit, max_bytes, scenes=False):
    valid=False
    try:
        keys={'contract_version','runtime','revision','nodes','scopes','pagination','limitations'} | ({'tree_complete'} if tree else set()) | ({'unsupported_count'} if scenes else set())
        valid=(type(result) is dict and set(result) == keys and _primitive(result) and
               len(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')) <= max_bytes and
               type(result['contract_version']) is int and result['contract_version'] == 1 and
               _runtime(result['runtime']) and result['runtime'] == dict(core_version='14.369',system_id='pf2e',system_version='8.6.1') and
               type(result['revision']) is str and bool(result['revision']) and _strings(result['limitations']) and
               type(result['nodes']) is list and all(_scene_node(node) if scenes else _node(node,tree) for node in result['nodes']) and
               type(result['scopes']) is list and (scenes or bool(result['scopes'])) and all(_scope(scope) for scope in result['scopes']) and
               _pagination(result['pagination'],len(result['nodes']),limit))
        if valid:
            identifiers=[node['identity']['uuid'] if node['kind']=='actor' else node['uuid'] for node in result['nodes']]
            valid=len(set(identifiers)) == len(identifiers)
        if valid and scenes:
            valid=type(result['unsupported_count']) is int and result['unsupported_count'] >= 0
        if valid and tree:
            valid=type(result['tree_complete']) is bool and (not result['tree_complete'] or result['pagination']['complete'] and all(node.get('children_complete',True) for node in result['nodes']) and all(scope['status']=='searched' for scope in result['scopes']))
    except (KeyError,TypeError,ValueError,UnicodeError,RecursionError):
        valid=False
    if not valid:
        raise _error('InvalidFoundryResponse','Malformed or oversized world Actor discovery response.','Check browser/server compatibility; do not interpret malformed results as empty scope.')


async def _call(method,params,tree,scenes=False):
    from . import tools
    try:
        result=await tools._foundry_manager.call('gm',method,params,timeout=15.0)
    except RpcError as exc:
        error=exc.error if type(exc.error) is dict else {}
        raise _error(error.get('code',error.get('type','ReadFailed')),error.get('message','Actor discovery failed.'),error.get('recovery','Inspect get_actor_types and retry the original scope.')) from exc
    except asyncio.TimeoutError as exc:
        raise _error('ReadFailed','Actor discovery timed out.','Wait for the existing GM browser to respond and retry.') from exc
    except (ConnectionError,RuntimeError) as exc:
        raise _error('BridgeUnavailable','No responsive authenticated GM browser.','Reconnect the existing ready GM browser and retry.') from exc
    _validate(result,tree=tree,limit=params['limit'],max_bytes=params['max_bytes'],scenes=scenes)
    if tree and any(node['depth'] > params['depth'] for node in result['nodes']):
        raise _error('InvalidFoundryResponse','Actor tree exceeded requested depth.','Retry the original scope; expand returned branches separately.')
    if scenes:
        scene_uuid=params.get('scene_uuid')
        if any(node['kind'] != ('token' if scene_uuid else 'scene') or (scene_uuid and node['parent_uuid'] != scene_uuid) for node in result['nodes']) or (scene_uuid is None and result['unsupported_count'] != 0):
            raise _error('InvalidFoundryResponse','Scene discovery returned a different scope.','Relist scenes and use the exact returned scene_uuid.')
    return result


@_tool
async def get_actor_tree(folder_uuid: Identifier | None = None, depth: Depth = 2,
                         limit: Limit = 50, max_bytes: ByteLimit = 48000,
                         cursor: Cursor | None = None) -> dict[str,Any]:
    """PF2e-specific: navigate world character/npc/familiar folders and Actor identities.

    Requires ready authenticated GM browser on core14.369/PF2e8.6.1 and document
    OBSERVER rights; excludes compendium/token Actors and unsupported Actor types.
    Start with no folder_uuid at directory root, including empty folders/unfiled
    Actors. To expand, copy a returned folder's expand.folder_uuid (canonical
    Folder.<id>, 1–512 characters); names/paths/local IDs are invalid. depth defaults
    2 (strict integer 1–5), measured from the selected root at depth 0. Uses public
    document parent relationships, never sidebar UI state. Cycles/inaccessible
    ancestry are explicit limitations; partial results are not a full directory.

    Returns contract_version/runtime/revision/nodes/scopes/pagination/limitations
    plus tree_complete. Flat preorder kind=folder nodes retain id/uuid/name,
    parent_uuid/depth/children_complete/expand. kind=actor nodes retain identity,
    parent_uuid/depth/folder_path/next_call; duplicate names retain distinct UUIDs.
    Names may be clipped with name_truncated; UUIDs remain intact. Order is folders
    first, case-insensitive name then UUID. Copy next_call into read_actor, then
    list_actor_items/read_item for details. Scoped depth-limited folders return
    expand={folder_uuid}; expand in a NEW call without cursor.

    limit defaults 50 (strict integer 1–100 nodes); max_bytes defaults 48000
    (8000–48000 UTF-8 JSON bytes). pagination.complete covers this scope's node
    pages; tree_complete also requires descendants expanded and no incomplete
    scopes. Pass pagination.next_cursor unchanged (1–4096 ASCII characters) with
    ALL original inputs until null. ContentChanged: discard accumulated pages and
    restart; InvalidCursor/CursorMismatch: restart without cursor. Missing folder:
    rediscover root; PermissionDenied: GM access needed; UnsupportedSystem/Version:
    inspect get_actor_types; BridgeUnavailable: reconnect. No writes/imports/rolls.
    """
    _bounds(folder_uuid,limit,max_bytes,cursor)
    if type(depth) is not int or not 1 <= depth <= 5:
        raise _error('InvalidRequest','depth must be an integer 1–5.','Use expand.folder_uuid to open deeper branches.')
    return await _call('getActorTree',dict(folder_uuid=folder_uuid,depth=depth,limit=limit,max_bytes=max_bytes,cursor=cursor),True)


@_tool
async def search_actors(query: SearchQuery, types: ActorTypes | None = None,
                        folder_uuid: Identifier | None = None, recursive: StrictBool = True,
                        limit: Limit = 50, max_bytes: ByteLimit = 48000,
                        cursor: Cursor | None = None) -> dict[str,Any]:
    """PF2e-specific: find world character/npc/familiar Actors by literal name substring.

    Requires ready authenticated GM browser on core14.369/PF2e8.6.1 and explicit
    document rights. query is nonblank 1–200 code points after trim, compared using
    locale-independent lowercase literal substring; no fuzzy/regex/biography search.
    Optional types is 1–3 unique character/npc/familiar values; omit for all three.
    Excluded/unknown Actor types are invalid filters. Optional folder_uuid is a
    canonical Folder.<id> UUID (1–512 characters) from get_actor_tree, never name,
    path or local ID. recursive defaults true and includes descendant folders;
    false checks the selected folder only. Omitted folder_uuid searches the world.

    Returns contract_version/runtime/revision/nodes/scopes/pagination/limitations.
    kind=actor nodes have full identity, parent_uuid/depth/folder_path and next_call
    {tool:read_actor,arguments:{actor_uuid:identity.uuid}}. Names may be clipped
    with name_truncated; duplicates remain distinct candidates with folder context.
    Order is case-insensitive Actor name then UUID. Follow next_call with read_actor,
    then list_actor_items/read_item. Search candidates do not establish content read.
    Empty results mean no literal match in completed selected scopes, never global
    absence; failed/incomplete/denied scopes prevent exhaustive absence claims.

    limit defaults 50 (strict integer 1–100 nodes), max_bytes 48000 (8000–48000
    UTF-8 JSON bytes). Return pagination.next_cursor unchanged (1–4096 ASCII chars)
    with ALL original inputs until complete/null. ContentChanged: discard pages,
    restart without cursor; InvalidCursor/CursorMismatch: restart. Missing folder:
    refresh get_actor_tree; PermissionDenied: GM access needed; unsupported runtime:
    inspect get_actor_types; BridgeUnavailable: reconnect. No writes/imports/rolls.
    """
    _bounds(folder_uuid,limit,max_bytes,cursor)
    if type(query) is not str or not query.strip() or len(query.strip()) > 200:
        raise _error('InvalidRequest','query must contain 1–200 characters after trim.','Try a literal nonblank Actor-name substring.')
    if type(recursive) is not bool:
        raise _error('InvalidRequest','recursive must be a boolean.','Use true or false, not a string or integer.')
    if types is not None and (type(types) is not list or not 1 <= len(types) <= 3 or any(type(value) is not str or value not in ('character','npc','familiar') for value in types) or len(set(types)) != len(types)):
        raise _error('InvalidRequest','types must be 1–3 unique in-scope Actor types.','Inspect get_actor_types or omit types for all supported types.')
    return await _call('searchActors',dict(query=query,types=types,folder_uuid=folder_uuid,recursive=recursive,limit=limit,max_bytes=max_bytes,cursor=cursor),False)


def _scene_node(node):
    common={'kind','id','uuid','name','name_truncated','parent_uuid','next_call'}
    if type(node) is not dict or node.get('kind') not in ('scene','token'):
        return False
    fields=common | ({'identity','actor_link','base_actor','limitations'} if node['kind']=='token' else set())
    if set(node) != fields or not _named_folder({key:node[key] for key in ('id','uuid','name','name_truncated')}):
        return False
    if node['kind']=='scene':
        return node['parent_uuid'] is None and node['next_call']==dict(tool='list_scene_actors',arguments=dict(scene_uuid=node['uuid']))
    if type(node['parent_uuid']) is not str or type(node['actor_link']) is not bool or not _strings(node['limitations']):
        return False
    base=node['base_actor']
    if base is not None and (type(base) is not dict or not {'uuid','name'} <= set(base) or not set(base) <= {'uuid','name','name_truncated'} or type(base['uuid']) is not str or type(base['name']) is not str or ('name_truncated' in base and type(base['name_truncated']) is not bool)):
        return False
    identity=node['identity']
    if identity is None:
        return node['next_call'] is None and bool(node['limitations'])
    return (_identity(identity) and identity['document_name']=='Actor' and identity['type'] in ('character','npc','familiar') and
            identity['source_kind']=='token' and identity['instance']['token_uuid']==node['uuid'] and
            identity['instance']['scene_uuid']==node['parent_uuid'] and identity['instance']['actor_link']==node['actor_link'] and
            identity['instance']['base_actor']==base and node['next_call']==dict(tool='read_actor',arguments=dict(token_uuid=node['uuid'])))


@_tool
async def list_scene_actors(scene_uuid: Identifier | None = None, query: SearchQuery | None = None,
                            types: ActorTypes | None = None, limit: Limit = 50,
                            max_bytes: ByteLimit = 48000, cursor: Cursor | None = None) -> dict[str,Any]:
    """PF2e-specific: discover readable scenes, then placed character/npc/familiar tokens.

    Requires ready authenticated GM browser on core14.369/PF2e8.6.1 with Scene,
    Token and Actor OBSERVER permissions; independent of active canvas/scene.
    Omit scene_uuid to list scenes. Then copy a scene next_call to list its placed
    tokens using scene_uuid Scene.<id> (canonical UUID, 1–512 characters, never
    name/path/local ID). query/types require scene_uuid. query is a nonblank
    1–200 character case-insensitive literal substring of token OR Actor name.
    types is 1–3 unique character/npc/familiar values; omit for all in-scope types.
    Excludes other Actor types/prototype tokens; hidden placed tokens are GM data.

    Returns contract_version/runtime/revision/nodes/scopes/pagination/limitations
    and unsupported_count (excluded Actor types, separate from caller filtering;
    zero when listing scenes). Scene nodes retain id/uuid/name/name_truncated/parent_uuid and next_call for
    list_scene_actors(scene_uuid=...). Token nodes additionally include identity,
    actor_link, base_actor, limitations and next_call for read_actor(token_uuid=...).
    identity describes actual token.actor current linked/synthetic state; base_actor
    is separate and never substituted. Missing current Actor returns identity=null,
    next_call=null and ActorUnavailable limitation, distinct from no tokens. Names
    are clipped with name_truncated; stable UUIDs remain intact. Order is lowercase
    token/scene name then UUID. Next read_actor using returned next_call, then
    list_actor_items/read_item while retaining token_uuid for instance context.

    limit defaults 50 (strict integer 1–100 nodes); max_bytes 48000 (8000–48000
    UTF-8 JSON bytes). Scope status searched/failed/incomplete/denied distinguishes
    unreadable data from empty scenes. pagination.complete covers selected scopes
    only; it cannot make incomplete/denied scope evidence exhaustive. Pass returned
    pagination.next_cursor unchanged (1–4096 ASCII chars) with ALL original inputs
    until complete/null. ContentChanged: discard pages/restart; InvalidCursor or
    CursorMismatch: restart without cursor. DocumentNotFound: relist scenes;
    PermissionDenied: GM access needed; UnsupportedSystem/Version: get_actor_types;
    BridgeUnavailable: reconnect existing GM browser. No imports/writes/rolls.
    """
    _bounds(None,limit,max_bytes,cursor)
    _identifier(scene_uuid,'scene_uuid')
    if scene_uuid is None and (query is not None or types is not None):
        raise _error('InvalidRequest','query/types require scene_uuid.','List scenes first, then use a returned scene_uuid.')
    if query is not None and (type(query) is not str or not query.strip() or len(query.strip()) > 200):
        raise _error('InvalidRequest','query must contain 1–200 characters after trim.','Use a literal nonblank token or Actor-name substring.')
    if types is not None and (type(types) is not list or not 1 <= len(types) <= 3 or any(type(value) is not str or value not in ('character','npc','familiar') for value in types) or len(set(types)) != len(types)):
        raise _error('InvalidRequest','types must be 1–3 unique in-scope Actor types.','Inspect get_actor_types or omit types.')
    return await _call('listSceneActors',dict(scene_uuid=scene_uuid,query=query,types=types,limit=limit,max_bytes=max_bytes,cursor=cursor),False,scenes=True)
