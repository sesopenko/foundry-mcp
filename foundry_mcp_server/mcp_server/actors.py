"""Read-only Actor/Item adapters; source state and permissions remain in Foundry.

PF2e-specific: the browser registry describes delivered source readers for
character/npc/familiar and PF2e Item types. The pinned schema/API evidence and
source-versus-effective gates live in docs/actor-tools.md (core 14.369/PF2e 8.6.1).
No Python calculation substitutes for a supported PF2e effective interface.
PF2e source boundary: https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts
"""
import asyncio
import json
import math
import re
from typing import Annotated, Any, Literal

from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import FunctionTool
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from .server import mcp
from foundry_mcp_server.ws.connection import RpcError

Identifier = Annotated[str, Field(min_length=1, max_length=512, strict=True)]
Cursor = Annotated[str, Field(min_length=1, max_length=4096, pattern=r"^[\x00-\x7f]+$", strict=True)]
Limit = Annotated[int, Field(ge=1, le=100, strict=True)]
ByteLimit = Annotated[int, Field(ge=8000, le=48000, strict=True)]
ActorSection = Literal['identity', 'source', 'build', 'statistics', 'skills', 'strikes', 'abilities', 'spellcasting', 'inventory', 'state', 'effective']
ItemSection = Literal['identity', 'source', 'description', 'rules', 'relationships', 'effective']
ActorSections = Annotated[list[ActorSection], Field(min_length=1, max_length=11)]
ItemSections = Annotated[list[ItemSection], Field(min_length=1, max_length=6)]
ItemType = Literal['melee', 'action', 'feat', 'spell', 'spellcastingEntry', 'lore', 'condition', 'effect', 'affliction', 'ancestry', 'heritage', 'background', 'class', 'deity', 'weapon', 'armor', 'shield', 'equipment', 'consumable', 'ammo', 'backpack', 'book', 'kit', 'treasure']
ItemTypes = Annotated[list[ItemType], Field(min_length=1, max_length=24)]
Query = Annotated[str, Field(min_length=1, max_length=200, strict=True)]
ACTOR_SECTIONS = {'identity', 'source', 'build', 'statistics', 'skills', 'strikes', 'abilities', 'spellcasting', 'inventory', 'state', 'effective'}
ITEM_SECTIONS = {'identity', 'source', 'description', 'rules', 'relationships', 'effective'}
ITEM_TYPES = set(ItemType.__args__)
SOURCE_PATHS = {'/name', '/type', '/system/description/value'}
# PF2e-specific PhysicalSystemSource 8.6.1 primitive paths. No prepared values.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts
PHYSICAL_TYPES = {'weapon','armor','shield','equipment','consumable','ammo','backpack','book','treasure'}
ATTACHMENT_TYPES = {'weapon','armor','shield','equipment'}
PHYSICAL_PATHS = {'/system/' + path for path in (
    'level/value','quantity','baseItem','size','bulk/value','hp/value','hp/max','hardness',
    'price/value/pp','price/value/gp','price/value/sp','price/value/cp','price/per','price/sizeSensitive',
    'equipped/carryType','equipped/inSlot','equipped/handsHeld','equipped/invested','containerId',
    'material/type','material/grade','identification/status','identification/unidentified/name',
    'identification/unidentified/img','identification/unidentified/data/description/value','temporary','usage/value')}
UNIDENTIFIED_DESCRIPTION = '/system/identification/unidentified/data/description/value'
# PF2e-specific AbilitySystemSource8.6.1: no prepared actionCost/frequency getters.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts
ACTION_PATHS = {'/system/' + path for path in (
    'actionType/value','actions/value','category','deathNote','slug','traits/value','traits/otherTags',
    'frequency','frequency/value','frequency/max','frequency/per','selfEffect','selfEffect/uuid','selfEffect/name',
    'publication/title','publication/authors','publication/license','publication/remaster')}
ACTIVATION_LABELS = {'action':'action_or_activity','reaction':'reaction','free':'free_action','passive':'passive_ability'}


def _empty_source_array(path: str, identity: dict[str, Any]) -> bool:
    """PF2e-specific source markers for empty attachment/ability-trait arrays only."""
    return (identity['type'] in ATTACHMENT_TYPES and path == '/system/subitems' or
            identity['type'] == 'action' and path in {'/system/traits/value','/system/traits/otherTags'})


def _action_value(raw: dict[str, Any]) -> bool:
    """PF2e-specific AbilitySystemSource8.6.1 primitive types; absent is not default.

    Frequency values are recorded source, not initialized/max/current availability;
    null action count is not activation type. Publication and traits stay source.
    """
    if not raw['present']:
        return True
    path=raw['path']; value=raw['value']
    if path in {'/system/traits/value','/system/traits/otherTags'}:
        return value == []
    if path in {'/system/frequency','/system/selfEffect'}:
        return value is None
    if path in {'/system/category','/system/slug'} and value is None:
        return True
    if path in {'/system/actions/value','/system/frequency/value','/system/frequency/max'}:
        return value is None and path == '/system/actions/value' or type(value) in (int,float)
    if path in {'/system/deathNote','/system/publication/remaster'}:
        return type(value) is bool
    return type(value) is str



def _action_record(row: dict[str, Any], identity: dict[str, Any]) -> bool:
    """PF2e-specific action8.6.1 source/activation and immediate selfEffect boundary.

    Only explicit relationships may resolve a canonical effect UUID; source
    frequency/presence is never castability, activation or a prepared statistic.
    Raw/provenance remain action source paths, including absent/null references.
    Schema: pinned ability/data.ts referenced by ACTION_PATHS above.
    """
    if any(raw['document_uuid'] != identity['uuid'] or not _action_value(raw) for raw in row['raw']):
        return False
    if any(value['document_uuid'] != identity['uuid'] for value in row['provenance']['contributors']):
        return False
    mapped=row['mapped']
    if row['kind']=='relationship':
        if row['section']!='relationships' or row['key']!='relationships:selfEffect' or [raw['path'] for raw in row['raw']] != ['/system/selfEffect/uuid','/system/selfEffect/name']:
            return False
        value=mapped['value']
        if mapped['concept']!='self_effect' or mapped['unit'] is not None or type(value) is not dict or not {'target_uuid','status'} <= set(value) or not set(value) <= {'target_uuid','status','token_uuid'} or value['status'] not in ('unverified','resolved','missing','denied','unsupported'):
            return False
        target=value['target_uuid']
        if value['status']=='resolved':
            if type(target) is not str or not 1 <= len(target) <= 512 or re.match(r'^(Item|Actor|Compendium|Scene)\.',target) is None or '#' in target:
                return False
        elif target is not None:
            return False
        if value['status']=='resolved' and target.startswith('Scene.'):
            token=value.get('token_uuid')
            if type(token) is not str or not 1 <= len(token) <= 512 or re.fullmatch(r'Scene\.[^.]+\.Token\.[^.]+',token) is None or not target.startswith(token+'.Actor.') or '.Item.' not in target:
                return False
        elif 'token_uuid' in value:
            return False
        return row['provenance']['mapping']=='pf2e.action.self_effect.v1' and [c['path'] for c in row['provenance']['contributors']]==['/system/selfEffect/uuid','/system/selfEffect/name']
    if len(row['raw'])!=1:
        return False
    raw=row['raw'][0]
    if raw['path'] not in SOURCE_PATHS and (row['section']!='source' or row['kind']!='field'):
        return False
    expected=raw.get('value')
    if raw['path']=='/system/actionType/value' and raw['present']:
        expected=ACTIVATION_LABELS.get(raw['value'],raw['value'])
    if row['kind']=='text':
        expected=None
    return type(mapped['value']) is type(expected) and mapped['value']==expected


def _source_path(path: Any, identity: dict[str, Any] | None = None) -> bool:
    """PF2e-specific: admit pinned physical and AbilitySystemSource8.6.1 paths.

    Armor/shield/treasure source overrides exclude usage; treasure excludes
    investment/slot/hands. Serialized attachment identities are source paths,
    never independent Item UUIDs. No effective Bulk/value/statistic is inferred.
    """
    if type(path) is not str:
        return False
    if path in SOURCE_PATHS:
        return True
    if identity is None or identity['document_name'] != 'Item':
        return False
    # PF2e-specific action paths exclude toggles, rule elements and prepared data.
    if identity['type'] == 'action':
        return path in ACTION_PATHS or re.fullmatch(r'/system/traits/(value|otherTags)/(0|[1-9][0-9]*)',path) is not None
    if identity['type'] not in PHYSICAL_TYPES:
        return False
    item_type = identity['type']
    if path == '/system/usage/value' and item_type in {'armor','shield','treasure'}:
        return False
    if path in {'/system/equipped/invested','/system/equipped/inSlot','/system/equipped/handsHeld'} and item_type == 'treasure':
        return False
    if path in PHYSICAL_PATHS:
        return True
    return item_type in ATTACHMENT_TYPES and (path == '/system/subitems' or re.fullmatch(r'/system/subitems/(0|[1-9][0-9]*)/(_id|name|type)', path) is not None)



def _error(code: str, message: str, recovery: str) -> ToolError:
    return ToolError(json.dumps(dict(code=code, message=message, recovery=recovery), ensure_ascii=True))


def _identifier(value: Any, name: str, optional: bool = True) -> None:
    if value is None and optional:
        return
    if type(value) is not str or not 1 <= len(value) <= 512:
        raise _error('InvalidRequest', f'{name} must be a 1–512 character UUID.', 'Use a canonical UUID returned by discovery.')


def _inputs(actor_uuid=None, token_uuid=None, *, item_uuid=None, sections=None,
            allowed=None, limit=50, max_bytes=48000, cursor=None) -> None:
    for name, value in [('actor_uuid', actor_uuid), ('token_uuid', token_uuid)]:
        _identifier(value, name)
    if item_uuid is None:
        if (actor_uuid is None) == (token_uuid is None):
            raise _error('InvalidRequest', 'Provide exactly one actor_uuid or token_uuid.', 'Use read_actor(actor_uuid=...) or read_actor(token_uuid=...).')
    else:
        _identifier(item_uuid, 'item_uuid', optional=False)
    if type(limit) is not int or not 1 <= limit <= 100 or type(max_bytes) is not int or not 8000 <= max_bytes <= 48000:
        raise _error('InvalidRequest', 'limit must be integer 1–100; max_bytes integer 8000–48000.', 'Use the documented bounds; booleans are not integers here.')
    if cursor is not None and (type(cursor) is not str or not 1 <= len(cursor) <= 4096 or not cursor.isascii()):
        raise _error('InvalidRequest', 'cursor must be 1–4096 ASCII characters.', 'Return next_cursor unchanged or restart without cursor.')
    if sections is not None and (type(sections) is not list or not sections or
                               any(type(x) is not str or x not in allowed for x in sections) or len(set(sections)) != len(sections)):
        raise _error('InvalidRequest', 'sections must contain unique known section names.', 'Inspect get_actor_types for section support.')


def _primitive(value: Any) -> bool:
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_primitive(x) for x in value)
    if type(value) is dict:
        return all(type(k) is str and _primitive(v) for k, v in value.items())
    return False


def _strings(value: Any) -> bool:
    return type(value) is list and all(type(v) is str for v in value)


def _runtime(value: Any) -> bool:
    return type(value) is dict and set(value) == {'core_version', 'system_id', 'system_version'} and all(type(v) is str for v in value.values())


def _identity(value: Any) -> bool:
    if type(value) is not dict:
        return False
    required = {'document_name', 'id', 'uuid', 'name', 'type', 'source_kind', 'folder', 'pack', 'actor', 'instance'}
    if not required <= set(value) or not set(value) <= required | {'name_truncated'}:
        return False
    if not all(type(value[k]) is str for k in ('document_name', 'id', 'uuid', 'name', 'type', 'source_kind')):
        return False
    if value['document_name'] not in ('Actor', 'Item') or value['source_kind'] not in ('world', 'compendium', 'token') or not value['uuid'] or len(value['uuid']) > 512:
        return False
    if 'name_truncated' in value and type(value['name_truncated']) is not bool:
        return False
    for key, keys in [('folder', {'id', 'uuid', 'name'}), ('pack', {'id', 'title'}), ('actor', {'uuid', 'name'})]:
        row = value[key]
        if row is not None and (type(row) is not dict or not keys <= set(row) or not set(row) <= keys | {'name_truncated'} or not all(type(row[k]) is str for k in keys) or ('name_truncated' in row and type(row['name_truncated']) is not bool)):
            return False
    instance = value['instance']
    if value['source_kind'] == 'token':
        if type(instance) is not dict or set(instance) != {'scene_uuid', 'scene_name', 'token_uuid', 'token_name', 'actor_link', 'base_actor'}:
            return False
        if type(instance['actor_link']) is not bool or not all(type(instance[k]) is str for k in ('scene_uuid', 'scene_name', 'token_uuid', 'token_name')):
            return False
        base = instance['base_actor']
        if base is not None and (type(base) is not dict or not {'uuid', 'name'} <= set(base) or not set(base) <= {'uuid', 'name', 'name_truncated'} or not all(type(base[k]) is str for k in ('uuid', 'name')) or ('name_truncated' in base and type(base['name_truncated']) is not bool)):
            return False
    elif instance is not None:
        return False
    return True


def _contributor(value: Any, identity: dict[str, Any] | None = None) -> bool:
    """Validate source provenance; PF2e-specific physical paths use _source_path."""
    return type(value) is dict and set(value) == {'document_uuid', 'path', 'basis'} and type(value['document_uuid']) is str and 1 <= len(value['document_uuid']) <= 512 and _source_path(value['path'], identity) and value['basis'] == 'source'


def _record(row: Any, sections: list[str], identity: dict[str, Any]) -> bool:
    """Validate records including PF2e-specific persisted physical source fields.

    PhysicalSystemSource 8.6.1 permits only primitive selected values and the
    explicit empty serialized-subitems marker; no derived values or child UUIDs.
    The pinned schema/type overrides are enforced by _source_path.
    """
    required = {'key', 'section', 'kind', 'raw', 'mapped', 'provenance'}
    if type(row) is not dict or not required <= set(row) or not set(row) <= required | {'text'}:
        return False
    if type(row['key']) is not str or row['section'] not in sections or row['kind'] not in ('field', 'relationship', 'text') or type(row['raw']) is not list:
        return False
    for raw in row['raw']:
        if type(raw) is not dict or not {'document_uuid', 'path', 'present', 'basis'} <= set(raw) or not set(raw) <= {'document_uuid', 'path', 'present', 'basis', 'value'}:
            return False
        if not _contributor({k: raw[k] for k in ('document_uuid', 'path', 'basis')}, identity) or type(raw['present']) is not bool or raw['present'] != ('value' in raw) or (raw['present'] and raw['value'] is not None and type(raw['value']) not in (str, bool, int, float) and not (_empty_source_array(raw['path'], identity) and raw['value'] == [])):
            return False
        # PF2e-specific alternate description is source text, explicitly selected.
        if raw['path'] == UNIDENTIFIED_DESCRIPTION and (row['section'] != 'description' or raw['present'] and row['kind'] != 'text'):
            return False
        if raw['path'] == '/system/subitems' and raw['present'] and raw['value'] != []:
            return False
    mapped = row['mapped']
    provenance = row['provenance']
    if identity['type'] in PHYSICAL_TYPES and any(raw['path'] not in SOURCE_PATHS for raw in row['raw']):
        # PF2e-specific physical source descriptors cannot smuggle nested mapped data
        # or relabel serialized attachments as separate contributor documents.
        if any(raw['document_uuid'] != identity['uuid'] for raw in row['raw']):
            return False
        if type(mapped) is dict and isinstance(mapped.get('value'), (dict, list)) and not (mapped.get('value') == [] and all(_empty_source_array(raw['path'], identity) for raw in row['raw'])):
            return False
    if type(mapped) is not dict or set(mapped) != {'concept', 'value', 'unit'} or type(mapped['concept']) is not str or (mapped['unit'] is not None and type(mapped['unit']) is not str):
        return False
    if type(provenance) is not dict or set(provenance) != {'contributors', 'mapping', 'limitations'} or type(provenance['mapping']) is not str or not _strings(provenance['limitations']) or type(provenance['contributors']) is not list or not all(_contributor(x, identity) for x in provenance['contributors']):
        return False
    # PF2e-specific action source and named self-effect semantics stay type-scoped.
    if identity['document_name'] == 'Item' and identity['type'] == 'action' and not _action_record(row, identity):
        return False
    if row['kind'] == 'text':
        text = row.get('text')
        if type(text) is not dict or set(text) != {'path', 'start', 'end', 'total', 'complete'}:
            return False
        if type(text['path']) is not str or any(type(text[k]) is not int for k in ('start', 'end', 'total')) or type(text['complete']) is not bool or not 0 <= text['start'] <= text['end'] <= text['total'] or text['complete'] != (text['end'] == text['total']):
            return False
        if len(row['raw']) != 1 or type(row['raw'][0].get('value')) is not str:
            return False
        units = len(row['raw'][0]['value'].encode('utf-16-le')) // 2
        if units != text['end'] - text['start'] or units > 6000 or row['raw'][0]['path'] != text['path']:
            return False
    elif 'text' in row:
        return False
    return True


def _pagination(value: Any, count: int, limit: int) -> bool:
    if type(value) is not dict or set(value) != {'complete', 'next_cursor', 'returned'} or type(value['complete']) is not bool or type(value['returned']) is not int or value['returned'] != count or count > limit:
        return False
    cursor = value['next_cursor']
    return value['complete'] == (cursor is None) and (cursor is None or type(cursor) is str and 1 <= len(cursor) <= 4096 and cursor.isascii())


def _validate(result: Any, mode: str, *, limit=50, max_bytes=48000, sections=None) -> None:
    valid = type(result) is dict
    try:
        valid = valid and _primitive(result)
        valid = valid and len(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')) <= max_bytes
        valid = valid and type(result.get('contract_version')) is int and result['contract_version'] == 1 and _runtime(result.get('runtime')) and _strings(result.get('limitations'))
        if valid and mode == 'types':
            valid = _registry(result)
        elif valid:
            valid = type(result.get('revision')) is str and bool(result['revision'])
            if mode == 'read':
                valid = valid and set(result) == {'contract_version', 'runtime', 'identity', 'revision', 'sections', 'records', 'pagination', 'limitations'} and _identity(result.get('identity')) and type(result.get('records')) is list and type(result.get('sections')) is list
                if valid:
                    rows = result['sections']
                    valid = [row.get('name') for row in rows if type(row) is dict] == sections and all(set(row) == {'name', 'status', 'reasons'} and row['status'] in ('complete', 'partial', 'unsupported', 'not_applicable') and _strings(row['reasons']) for row in rows)
                    valid = valid and all(_record(row, sections, result['identity']) for row in result['records']) and len({row['key'] for row in result['records']}) == len(result['records']) and _pagination(result.get('pagination'), len(result['records']), limit)
            else:
                valid = valid and _item_list(result, limit)
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
        valid = False
    if not valid:
        raise _error('InvalidFoundryResponse', 'Malformed or oversized Actor/Item response.', 'Check browser/server compatibility and retry; do not interpret this response as empty data.')


def _registry(result: dict[str, Any]) -> bool:
    # The browser is authoritative for its delivered per-type registry.
    required = {'contract_version', 'runtime', 'availability', 'actor_types', 'item_types', 'actor_sections', 'item_sections', 'limits', 'limitations'}
    if set(result) != required or type(result['availability']) is not dict or set(result['availability']) != {'supported', 'reason'} or type(result['availability']['supported']) is not bool or (result['availability']['reason'] is not None and type(result['availability']['reason']) is not str) or type(result['limits']) is not dict:
        return False
    for key in ('actor_types', 'item_types', 'actor_sections', 'item_sections'):
        if type(result[key]) is not list:
            return False
        identifiers = []
        for row in result[key]:
            fields = {'name', 'allowed', 'in_scope', 'source_supported', 'mapped_supported', 'effective_supported', 'limitations', 'verification'}
            if key.endswith('types'):
                fields.add('type')
            if type(row) is not dict or set(row) != fields or type(row.get('name')) is not str or ('type' in fields and type(row.get('type')) is not str) or not all(type(row.get(flag)) is bool for flag in ('allowed', 'in_scope', 'source_supported', 'mapped_supported', 'effective_supported')) or not _strings(row.get('limitations')):
                return False
            identifiers.append(row.get('type', row['name']))
            verification = row.get('verification')
            if type(verification) is not dict or set(verification) != {'deterministic', 'live'}:
                return False
            for evidence in verification.values():
                if type(evidence) is not dict or set(evidence) != {'status', 'evidence'} or evidence['status'] not in ('not_run', 'passed', 'failed', 'not_required') or not _strings(evidence['evidence']):
                    return False
        if len(set(identifiers)) != len(identifiers):
            return False
    return result['limits'] == dict(default_limit=50, max_records=100, min_bytes=8000, max_bytes=48000, max_text_units=6000, max_cursor_characters=4096, max_selector_characters=512) and all(type(v) is int for v in result['limits'].values())


def _item_list(result: dict[str, Any], limit: int) -> bool:
    if set(result) != {'contract_version', 'runtime', 'revision', 'nodes', 'scopes', 'pagination', 'limitations', 'unsupported_count'} or type(result['nodes']) is not list or type(result['scopes']) is not list:
        return False
    for scope in result['scopes']:
        if type(scope) is not dict or set(scope) != {'id', 'status', 'reason'} or type(scope['id']) is not str or scope['status'] not in ('searched', 'failed', 'incomplete', 'denied') or (scope['reason'] is not None and type(scope['reason']) is not str):
            return False
    for node in result['nodes']:
        if type(node) is not dict or not {'kind','identity','next_call'} <= set(node) or not set(node) <= {'kind','identity','next_call','parent_uuid','relationships','limitations'} or node.get('kind') != 'item' or not _identity(node.get('identity')) or node['identity']['document_name'] != 'Item':
            return False
        call = node.get('next_call')
        if call is None:
            if not _strings(node.get('limitations')) or not node['limitations']:
                return False
        if call is not None and (type(call) is not dict or set(call) != {'tool', 'arguments'} or call['tool'] != 'read_item' or type(call['arguments']) is not dict or call['arguments'].get('item_uuid') != node['identity']['uuid'] or not set(call['arguments']) <= {'item_uuid', 'token_uuid'}):
            return False
        if call is not None:
            instance = node['identity']['instance']
            arguments = call['arguments']
            if instance is not None and arguments.get('token_uuid') != instance['token_uuid']:
                return False
            if instance is None and 'token_uuid' in arguments:
                return False
        if 'parent_uuid' in node and (type(node['parent_uuid']) is not str or not 1 <= len(node['parent_uuid']) <= 512):
            return False
        if 'relationships' in node and type(node['relationships']) is not list:
            return False
    if type(result.get('unsupported_count')) is not int or result['unsupported_count'] < 0:
        return False
    return _pagination(result['pagination'], len(result['nodes']), limit)


async def _call(method: str, params: dict[str, Any], mode: str) -> dict[str, Any]:
    from . import tools
    try:
        result = await tools._foundry_manager.call('gm', method, params, timeout=15.0)
    except RpcError as exc:
        error = exc.error if isinstance(exc.error, dict) else {}
        raise _error(error.get('code', error.get('type', 'ReadFailed')), error.get('message', 'Foundry read failed.'), error.get('recovery', 'Inspect get_actor_types and retry using returned selectors.')) from exc
    except asyncio.TimeoutError as exc:
        raise _error('ReadFailed', 'Foundry read timed out.', 'Wait for a responsive GM browser and retry.') from exc
    except (ConnectionError, RuntimeError) as exc:
        raise _error('BridgeUnavailable', 'No responsive authenticated GM bridge.', 'Reconnect the existing ready GM browser and retry.') from exc
    _validate(result, mode, limit=params.get('limit', 50), max_bytes=params.get('max_bytes', 48000), sections=params.get('sections'))
    if mode != 'types' and result['runtime'] != dict(core_version='14.369', system_id='pf2e', system_version='8.6.1'):
        raise _error('InvalidFoundryResponse', 'Reader returned unsupported runtime semantics.', 'Inspect get_actor_types; use the supported Foundry/PF2e pairing.')
    if mode == 'read' and result['identity']['document_name'] != ('Actor' if method == 'readActor' else 'Item'):
        raise _error('InvalidFoundryResponse', 'Reader returned the wrong document kind.', 'Rediscover the canonical selector and check browser/server compatibility.')
    if mode == 'read':
        identity = result['identity']
        selector = params.get('actor_uuid') if method == 'readActor' else params.get('item_uuid')
        if selector is not None and identity['uuid'] != selector:
            raise _error('InvalidFoundryResponse', 'Reader returned a different document identity.', 'Rediscover the canonical selector; do not substitute another document.')
        token_uuid = params.get('token_uuid')
        if token_uuid is not None and (identity['instance'] is None or identity['instance']['token_uuid'] != token_uuid):
            raise _error('InvalidFoundryResponse', 'Reader lost the selected token context.', 'Retry using the original token_uuid; never substitute its base Actor.')
        if token_uuid is None and identity['instance'] is not None:
            raise _error('InvalidFoundryResponse', 'Reader returned unexpected token context.', 'Use the explicit token_uuid selector for token instances.')
    return result


class _ActorTool(FunctionTool):
    async def run(self, arguments):
        try:
            return await super().run(arguments)
        except ValidationError as exc:
            raise _error('InvalidRequest', 'Inputs do not match the Actor/Item tool schema.', 'Check the published input schema; reject unknown inputs and use documented bounds.') from exc


def _tool(fn):
    tool = _ActorTool.from_function(fn, annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    tool.parameters['additionalProperties'] = False
    return mcp.add_tool(tool)


@_tool
async def get_actor_types() -> dict[str, Any]:
    """PF2e-specific: discover delivered Actor/Item source readers and compatibility before reading.

    Requires a ready authenticated GM browser. Returns contract_version, runtime
    (core_version/system_id/system_version), availability, actor_types, item_types,
    actor_sections, item_sections, limits and limitations. allowed/in_scope differ
    from source_supported/mapped_supported/effective_supported; each registry entry
    includes deterministic/live verification status and evidence. No support for
    complete effective statistics is implied by an allowed type. PF2e 8.6.1/core
    14.369 is the verified baseline; other systems/versions report unavailable.
    Next use read_actor with a canonical Actor UUID, read_item with an Item UUID,
    or list_actor_items with an actor/token selector. No writes, rolls or imports.
    BridgeUnavailable: reconnect the ready GM browser. Unknown inputs are invalid.
    """
    return await _call('getActorTypes', {}, 'types')


@_tool
async def read_actor(actor_uuid: Identifier | None = None, token_uuid: Identifier | None = None,
                     sections: ActorSections = ['identity', 'source'], limit: Limit = 50,
                     max_bytes: ByteLimit = 48000, cursor: Cursor | None = None) -> dict[str, Any]:
    """PF2e-specific: read an Actor's selected source and delivered book-oriented sections as GM.

    Requires ready authenticated GM browser and explicit document permissions.
    Provide exactly one canonical actor_uuid (world Actor.<id> or full compendium
    Actor UUID) OR placed token_uuid Scene.<id>.Token.<id>, each 1–512 characters;
    names/paths/local IDs are invalid. Copy UUIDs from discovery/reference identity
    records. A token reads token.actor current state, never silently its base.
    Synthetic actor UUIDs require token_uuid instead. Default sections identity,
    source expose common selected metadata; type-specific full mapping is staged.
    Known sections build/statistics/skills/strikes/abilities/spellcasting/inventory/
    state/effective can be unsupported; get_actor_types reports delivered support.
    Sections must be unique/nonempty (at most 11). PF2e character/npc/familiar only;
    other systems/versions/types give UnsupportedSystem/Version/Type errors.

    Returns contract_version/runtime/identity/revision/sections/records/pagination/
    limitations. Records retain selected raw fields, mapped concepts and provenance;
    sections distinguish partial/unsupported/not_applicable from complete. Missing
    fields differ from null/zero; source is not complete effective statistics.
    limit defaults 50 (integer 1–100 records); max_bytes defaults 48000 (8000–48000
    UTF-8 JSON bytes). Exact text fragments use UTF-16 text.start/end/total offsets,
    at most 6000 units; concatenate same-path/revision raw values without enrichment.
    pagination.next_cursor is null when complete; otherwise return it unchanged
    (1–4096 ASCII chars) with ALL original inputs. ContentChanged: discard prior
    pages/restart without cursor; InvalidCursor/CursorMismatch: restart. Permissions
    rechecked per page. DocumentNotFound: rediscover; PermissionDenied: GM access
    needed; BridgeUnavailable: reconnect. Next list_actor_items for owned identities
    then read_item; local record keys/mapped fields are never document selectors.
    """
    _inputs(actor_uuid, token_uuid, sections=sections, allowed=ACTOR_SECTIONS, limit=limit, max_bytes=max_bytes, cursor=cursor)
    return await _call('readActor', dict(actor_uuid=actor_uuid, token_uuid=token_uuid, sections=sections, limit=limit, max_bytes=max_bytes, cursor=cursor), 'read')


@_tool
async def read_item(item_uuid: Identifier, token_uuid: Identifier | None = None,
                    sections: ItemSections = ['identity', 'source'], limit: Limit = 50,
                    max_bytes: ByteLimit = 48000, cursor: Cursor | None = None) -> dict[str, Any]:
    """PF2e-specific: read selected Item source with canonical owner/pack/token identity as GM.

    Requires ready authenticated GM browser and explicit document/owner/pack rights.
    item_uuid (1–512 characters) is the full world Item.<id>, Actor.<id>.Item.<id>,
    or full compendium/embedded UUID returned by discovery or list_actor_items;
    names/local IDs/paths are invalid. token_uuid Scene.<id>.Token.<id> is required
    for synthetic-owned Items and permitted for linked-token Items only when the
    Item belongs to that token.actor. No template substitution. Default unique
    sections identity/source expose common metadata and shared physical source
    fields for weapon/armor/shield/equipment/consumable/ammo/backpack/book/treasure:
    quantity, level, Bulk, denomination prices and price.per, carrying/investment,
    container local ID, material, identification, HP/Hardness and permitted usage.
    Missing paths have present=false without value; null/zero/false remain distinct.
    Serialized attachments expose local _id/name/type paths, never their own UUIDs.
    Armor/shield/treasure omit persisted usage; kit is not a physical source type.
    Source remains partial until its concrete type story is delivered;
    action Items have complete selected source mappings for activation kind/count,
    category, frequency, traits/tags, publication and named self-effect references.
    Null action counts never imply free actions. Explicit relationships resolve
    only the immediate self-effect without applying it: mapped.value contains
    target_uuid/status, plus token_uuid for resolved synthetic targets. Follow a
    resolved target with read_item(item_uuid=target_uuid, token_uuid=token_uuid
    if present). Missing/denied/unsupported/unverified targets retain named raw
    references with null target_uuid. Source alone performs no effect hydration;
    optional description/rules/relationships/effective are delivered or explicitly
    unsupported as get_actor_types reports. At most 6 unique nonempty section names.
    PF2e-only; UnsupportedSystem/Version/Type explains excluded targets.

    Returns contract_version/runtime/identity/revision/sections/records/pagination/
    limitations; records carry raw selected paths, mapped concepts and provenance.
    Source is not castability, active effect or effective statistics. Exact stored
    description text (including physical unidentified alternate text only when
    explicitly requested) is never enriched/executed; text.start/end/total are UTF-16
    offsets (6000 units per fragment); concatenate matching path/revision fragments.
    limit 50 by default (strict integer 1–100 records); max_bytes 48000 by default
    (strict integer 8000–48000 UTF-8 JSON bytes). Pass pagination.next_cursor unchanged
    with all original inputs until null/complete; cursor 1–4096 ASCII characters.
    ContentChanged: discard prior pages/restart. InvalidCursor/CursorMismatch:
    restart without cursor. DocumentNotFound: rediscover; PermissionDenied: GM rights
    needed; BridgeUnavailable: reconnect. Next follow named relationships through
    read_item/read_actor; local record keys are not UUIDs. No writes/rolls/imports.
    """
    _inputs(token_uuid=token_uuid, item_uuid=item_uuid, sections=sections, allowed=ITEM_SECTIONS, limit=limit, max_bytes=max_bytes, cursor=cursor)
    return await _call('readItem', dict(item_uuid=item_uuid, token_uuid=token_uuid, sections=sections, limit=limit, max_bytes=max_bytes, cursor=cursor), 'read')


@_tool
async def list_actor_items(actor_uuid: Identifier | None = None, token_uuid: Identifier | None = None,
                           types: ItemTypes | None = None, query: Query | None = None,
                           limit: Limit = 50, max_bytes: ByteLimit = 48000,
                           cursor: Cursor | None = None) -> dict[str, Any]:
    """PF2e-specific: enumerate an Actor's embedded Item identities, not all possible abilities.

    Requires a ready authenticated GM browser and explicit document permissions.
    Exactly one actor_uuid (canonical world/compendium Actor UUID) or token_uuid
    (Scene.<id>.Token.<id>) is required, 1–512 characters, from discovery/reference
    identity; names/paths/local IDs are invalid. Token reads current token.actor.
    Optional types is 1–24 unique in-scope PF2e Item types; omit for all in-scope
    types, inspect get_actor_types first. Unknown/excluded types invalid. query is
    a trimmed 1–200 character case-insensitive literal Item-name substring, not
    regex/semantic/full-description search. Duplicate names remain distinct UUIDs.

    Returns contract_version/runtime/revision/nodes/scopes/pagination/limitations
    and unsupported_count. kind=item nodes include identity, parent_uuid, next_call
    and supported named relationships; call next_call.tool with next_call.arguments
    (normally read_item(item_uuid=node.identity.uuid), retaining token_uuid).
    Scope statuses searched/failed/incomplete/denied distinguish incomplete results;
    unsupported_count counts excluded Items. Empty only means no literal matches
    in completed scope, never no possible actions. limit defaults 50 (integer
    1–100 nodes), max_bytes 48000 (8000–48000 UTF-8 JSON bytes). Follow returned
    pagination.next_cursor unchanged with ALL original inputs until complete/null;
    cursor is 1–4096 ASCII chars. ContentChanged: discard pages/restart; invalid or
    mismatched cursor: restart without cursor. UnsupportedSystem/Version/Type:
    inspect registry. Missing targets: rediscover; denied: GM access needed;
    BridgeUnavailable: reconnect existing GM browser. No imports, writes or rolls.
    """
    _inputs(actor_uuid, token_uuid, limit=limit, max_bytes=max_bytes, cursor=cursor)
    if types is not None and (type(types) is not list or not types or len(types) > 24 or any(type(x) is not str or x not in ITEM_TYPES for x in types) or len(set(types)) != len(types)):
        raise _error('InvalidRequest', 'types must be 1–24 unique in-scope Item types.', 'Inspect get_actor_types for valid types.')
    if query is not None and (type(query) is not str or not query.strip() or len(query.strip()) > 200):
        raise _error('InvalidRequest', 'query must be 1–200 characters after trim.', 'Use a literal nonblank Item name substring.')
    return await _call('listActorItems', dict(actor_uuid=actor_uuid, token_uuid=token_uuid, types=types, query=query, limit=limit, max_bytes=max_bytes, cursor=cursor), 'list')
