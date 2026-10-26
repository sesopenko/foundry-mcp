"""PF2e-specific Actor/Item compendium discovery, index-first and read-only.

Only character/npc/familiar and the documented 23 readable Item types are interpreted;
source identity never establishes effective statistics or rules completeness.
Core14.369/PF2e8.6.1 baseline and field evidence: docs/actor-tools.md.
https://foundryvtt.com/api/v14/classes/foundry.documents.collections.CompendiumCollection.html
"""
import asyncio
import json
from typing import Annotated, Any, Literal

from pydantic import Field

from foundry_mcp_server.ws.connection import RpcError
from .actors import (Identifier, Cursor, Limit, ByteLimit, ReadableItemType, READABLE_ITEM_TYPES,
                     _error, _identity, _pagination, _primitive, _runtime, _strings, _tool)
from .actor_discovery import ActorType, SearchQuery, _bounds, _scope

DocumentType = Literal['Actor', 'Item']
PackId = Annotated[str, Field(min_length=1, max_length=256, strict=True)]
PackIds = Annotated[list[PackId], Field(min_length=1, max_length=10)]
TypeFilter = Annotated[list[ActorType | ReadableItemType], Field(min_length=1, max_length=23)]


def _filters(document_type, query=None, *, required=False, types=None):
    if document_type not in ('Actor','Item') or type(document_type) is not str:
        raise _error('InvalidRequest','document_type must be Actor or Item.','Use list_actor_compendiums to discover pack document types.')
    if query is not None and (type(query) is not str or not query.strip() or len(query.strip()) > 200) or required and query is None:
        raise _error('InvalidRequest','query must contain 1–200 characters after trim.','Supply a literal name/title substring, not a semantic question.')
    allowed={'character','npc','familiar'} if document_type=='Actor' else READABLE_ITEM_TYPES
    if types is not None and (type(types) is not list or not types or len(types)>len(allowed) or any(type(value) is not str or value not in allowed for value in types) or len(set(types)) != len(types)):
        raise _error('InvalidRequest','types must be unique in-scope types for the selected document_type.','Inspect get_actor_types; omit types for all in-scope types.')


def _pack_node(node, document_type):
    keys={'kind','id','title','title_truncated','document_type','visible','folder','parent_uuid','next_call','search_scope','limitations'}
    return (type(node) is dict and set(node)==keys and node['kind']=='pack' and
            type(node['id']) is str and 1 <= len(node['id']) <= 256 and type(node['title']) is str and len(node['title']) <= 256 and
            type(node['title_truncated']) is bool and node['document_type']==document_type and type(node['visible']) is bool and
            node['folder'] is None and node['parent_uuid'] is None and node['next_call'] is None and
            node['search_scope']==dict(pack_ids=[node['id']],document_type=document_type) and
            _strings(node['limitations']) and bool(node['limitations']))


def _document_node(node, document_type):
    if type(node) is not dict or set(node) != {'kind','identity','parent_uuid','next_call'}:
        return False
    identity=node['identity']
    if not _identity(identity) or identity['document_name'] != document_type or node['kind'] != document_type.lower() or identity['source_kind'] != 'compendium' or identity['folder'] is not None or not identity['uuid'].startswith('Compendium.') or identity['pack'] is None or identity['actor'] is not None or identity['instance'] is not None or node['parent_uuid'] is not None:
        return False
    allowed={'character','npc','familiar'} if document_type=='Actor' else READABLE_ITEM_TYPES
    selector='actor_uuid' if document_type=='Actor' else 'item_uuid'
    return identity['type'] in allowed and node['next_call']==dict(tool='read_actor' if document_type=='Actor' else 'read_item',arguments={selector:identity['uuid']})


def _validate(result, *, search, params):
    valid=False
    try:
        valid=(type(result) is dict and set(result)=={'contract_version','runtime','revision','nodes','scopes','pagination','limitations'} and
               _primitive(result) and len(json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')) <= params['max_bytes'] and
               type(result['contract_version']) is int and result['contract_version']==1 and _runtime(result['runtime']) and
               result['runtime']==dict(core_version='14.369',system_id='pf2e',system_version='8.6.1') and type(result['revision']) is str and bool(result['revision']) and
               type(result['nodes']) is list and type(result['scopes']) is list and _strings(result['limitations']) and
               _pagination(result['pagination'],len(result['nodes']),params['limit']))
        if valid:
            valid=all(_scope(scope) for scope in result['scopes'])
        if valid and search:
            valid=all(_document_node(node,params['document_type']) for node in result['nodes']) and sorted(scope['id'] for scope in result['scopes'])==sorted(params['pack_ids'])
            if valid:
                valid=all(node['identity']['pack']['id'] in params['pack_ids'] and (params['types'] is None or node['identity']['type'] in params['types']) for node in result['nodes'])
        elif valid:
            valid=all(_pack_node(node,params['document_type']) for node in result['nodes']) and len(result['scopes'])==1 and result['scopes'][0]['id']=='packs'
        if valid:
            selectors=[node['identity']['uuid'] if search else node['id'] for node in result['nodes']]
            valid=len(set(selectors))==len(selectors)
    except (KeyError,TypeError,ValueError,UnicodeError,RecursionError):
        valid=False
    if not valid:
        raise _error('InvalidFoundryResponse','Malformed or oversized compendium discovery response.','Check browser/server compatibility; incomplete scopes never prove absent content.')


async def _call(method,params,search):
    from . import tools
    try:
        result=await tools._foundry_manager.call('gm',method,params,timeout=15.0)
    except RpcError as exc:
        error=exc.error if type(exc.error) is dict else {}
        raise _error(error.get('code',error.get('type','ReadFailed')),error.get('message','Compendium discovery failed.'),error.get('recovery','Relist packs and retry the original scope.')) from exc
    except asyncio.TimeoutError as exc:
        raise _error('ReadFailed','Compendium discovery timed out.','Wait for the existing GM browser and retry the selected packs.') from exc
    except (ConnectionError,RuntimeError) as exc:
        raise _error('BridgeUnavailable','No responsive authenticated GM browser.','Reconnect the existing ready GM browser and retry.') from exc
    _validate(result,search=search,params=params)
    return result


@_tool
async def list_actor_compendiums(document_type: DocumentType = 'Actor', query: SearchQuery | None = None,
                                 limit: Limit = 50, max_bytes: ByteLimit = 48000,
                                 cursor: Cursor | None = None) -> dict[str,Any]:
    """PF2e-specific: discover readable Actor or Item packs without loading documents.

    Requires ready authenticated GM browser on core14.369/PF2e8.6.1 and pack
    OBSERVER permissions. document_type defaults Actor; Item explicitly selects
    Item packs. query optionally matches lowercase literal pack title/collection
    substring, 1–200 nonblank characters after trim; no regex/fuzzy/content search.
    Pack editing lock does not imply read prohibition. Uses pack collection IDs,
    not titles/paths. No getDocuments, imports or bulk document hydration.

    Returns contract_version/runtime/revision/nodes/scopes/pagination/limitations.
    kind=pack nodes retain id/title/document_type/visible, truncation flags and
    explicit flat folder context (null when public hierarchy is unverified).
    next_call is null because a caller query is required; copy search_scope
    {pack_ids:[id],document_type}, add a literal query and call search_compendium_actors.
    limitations explains this next step; no fabricated query is supplied.
    Select returned pack IDs with search_compendium_actors; supply your desired
    literal document-name query. A title is never a unique document selector.
    Scope statuses searched/failed/incomplete/denied distinguish access gaps;
    empty nodes establish no matching readable packs in completed scope only.

    limit defaults 50 (strict integer 1–100 nodes); max_bytes defaults 48000
    (8000–48000 UTF-8 JSON bytes). Pass pagination.next_cursor unchanged (1–4096
    ASCII chars) with ALL original inputs until complete/null. ContentChanged:
    discard pages/restart; InvalidCursor/CursorMismatch: restart without cursor.
    PermissionDenied: GM access needed; UnsupportedSystem/Version: get_actor_types;
    BridgeUnavailable: reconnect existing GM browser. No writes, imports or rolls.
    """
    _bounds(None,limit,max_bytes,cursor);_filters(document_type,query)
    return await _call('listActorCompendiums',dict(document_type=document_type,query=query,limit=limit,max_bytes=max_bytes,cursor=cursor),False)


@_tool
async def search_compendium_actors(pack_ids: PackIds, query: SearchQuery,
                                   types: TypeFilter | None = None, document_type: DocumentType = 'Actor',
                                   limit: Limit = 50, max_bytes: ByteLimit = 48000,
                                   cursor: Cursor | None = None) -> dict[str,Any]:
    """PF2e-specific: search selected Actor/Item pack indexes by literal document name.

    Requires ready authenticated GM browser on core14.369/PF2e8.6.1 and explicit
    pack OBSERVER permission. pack_ids is 1–10 unique collection IDs (1–256 chars
    each) returned by list_actor_compendiums, never pack titles or document UUIDs.
    document_type defaults Actor; Item selects Item packs. query is a nonblank
    1–200 character lowercase literal name substring after trim, not regex/fuzzy/
    semantic/full-description search. Optional types are unique in-scope types:
    character/npc/familiar for Actor (at most 3), 23 readable types for Item;
    omit for all in-scope types. Unknown/excluded/mismatched types are invalid.
    Dedicated affliction Items have no reader and are excluded from filters and
    results pending upstream support. Empty results never establish no affliction
    or related state; inspect original descriptions on actual supported Items.
    No implicit all-pack search, full-pack getDocuments/imports or bulk hydration.

    Returns contract_version/runtime/revision/nodes/scopes/pagination/limitations.
    Indexed kind=actor/item nodes preserve identity (full canonical UUID, name,
    type, pack ID/title) and next_call for read_actor/read_item; use that complete
    selector to lazily read one full document. Indexed candidates are not content
    already read. One scope per requested pack reports searched/failed/denied/
    incomplete; missing index type remains incomplete, never coerced into a type.
    Empty matches prove only literal absence in fully searched selected indexes;
    partial failures do not prove no content. Order is pack ID/name/UUID.

    limit defaults 50 (strict integer 1–100 nodes); max_bytes 48000 (8000–48000
    UTF-8 JSON bytes). Return pagination.next_cursor unchanged (1–4096 ASCII chars)
    with ALL original inputs until complete/null. ContentChanged: discard prior
    pages/restart; InvalidCursor/CursorMismatch: restart without cursor. Relist
    missing packs; grant GM access for denied scopes; UnsupportedSystem/Version:
    get_actor_types; BridgeUnavailable: reconnect existing GM browser. Read-only.
    """
    _bounds(None,limit,max_bytes,cursor);_filters(document_type,query,required=True,types=types)
    if type(pack_ids) is not list or not 1 <= len(pack_ids) <= 10 or any(type(value) is not str or not value.strip() or not 1 <= len(value) <= 256 for value in pack_ids) or len(set(pack_ids)) != len(pack_ids):
        raise _error('InvalidRequest','pack_ids must be 1–10 unique collection IDs of 1–256 characters.','Reuse pack IDs from list_actor_compendiums.')
    return await _call('searchCompendiumActors',dict(pack_ids=pack_ids,query=query,types=types,document_type=document_type,limit=limit,max_bytes=max_bytes,cursor=cursor),True)
