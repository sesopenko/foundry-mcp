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
from typing import Annotated, Any, Literal, get_args

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
ActorSection = Literal['identity', 'source', 'description', 'build', 'statistics', 'skills', 'strikes', 'abilities', 'spellcasting', 'inventory', 'state', 'effective']
ItemSection = Literal['identity', 'source', 'description', 'rules', 'relationships', 'effective']
ActorSections = Annotated[list[ActorSection], Field(min_length=1, max_length=12)]
ItemSections = Annotated[list[ItemSection], Field(min_length=1, max_length=6)]
ItemType = Literal['melee', 'action', 'feat', 'spell', 'spellcastingEntry', 'lore', 'condition', 'effect', 'affliction', 'ancestry', 'heritage', 'background', 'class', 'deity', 'weapon', 'armor', 'shield', 'equipment', 'consumable', 'ammo', 'backpack', 'book', 'kit', 'treasure']
ItemTypes = Annotated[list[ItemType], Field(min_length=1, max_length=24)]
Query = Annotated[str, Field(min_length=1, max_length=200, strict=True)]
ACTOR_SECTIONS = {'identity', 'source', 'description', 'build', 'statistics', 'skills', 'strikes', 'abilities', 'spellcasting', 'inventory', 'state', 'effective'}
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
# PF2e-specific MeleeSystemSource8.6.1: authored NPC attack records, not gear maths.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/melee/data.ts
MELEE_PATHS = {'/system/' + path for path in (
    'action','bonus/value','subjectToMAP','slug','area','area/type','area/value','range','range/increment','range/max',
    'damageRolls','traits/value','traits/otherTags','attackEffects/value','publication/title','publication/authors','publication/license','publication/remaster')}
MELEE_MODES = {'strike':'Strike','area-fire':'Area Fire','auto-fire':'Auto Fire'}
DAMAGE_LEAF = re.compile(r'/system/damageRolls/(?:[^~/]|~[01])*/(damage|damageType|category)')
MELEE_ARRAY_INDEX = re.compile(r'/system/(?:traits/(?:value|otherTags)|attackEffects/value)/(0|[1-9][0-9]*)')


# PF2e-specific LoreSystemSource8.6.1; exact persisted fields, no skill total.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/lore.ts
LORE_PATHS = {'/system/'+p for p in ('mod/value','proficient/value','variants','traits/otherTags','slug','publication/title','publication/authors','publication/license','publication/remaster')}
LORE_VARIANT = re.compile(r'/system/variants/(?:[^~/]|~[01])*/(label|options)')
LORE_RANKS = ['Untrained','Trained','Expert','Master','Legendary']


# PF2e-specific EffectSystemSource8.6.1; selected persisted leaves only.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/effect/data.ts
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/data.ts
EFFECT_SOURCE = {}
EFFECT_EVENTS = ('initiative-roll','turn-start','turn-end')
EFFECT_ARRAYS = {'/system/'+p:c for p,c in [('traits/value','effect_trait_code'),('traits/otherTags','effect_other_tag_code'),('badge/labels','effect_badge_label'),('context/origin/rollOptions','effect_origin_roll_option')]}


def _effect_specs():
    """PF2e-specific effect8.6.1 source path/concept/type/null/choices contract."""
    for path,concept,kind,nullable,choices in [
        ('level/value','effect_level','integer',False,None),('duration/value','effect_duration_value','duration',False,None),
        ('duration/unit','effect_duration_unit','string',False,('rounds','minutes','hours','days','unlimited','encounter')),
        ('duration/expiry','effect_duration_expiry','string',True,('turn-start','turn-end','round-end')),
        ('duration/sustained','effect_sustained','boolean',False,None),('start/value','effect_start_time','number',False,None),
        ('start/initiative','effect_start_initiative','number',True,None),('tokenIcon/show','effect_token_icon_show','boolean',False,None),
        ('unidentified','effect_unidentified','boolean',False,None),('fromSpell','effect_from_spell','boolean',False,None),('slug','source_slug','string',True,None),
        ('badge','effect_badge','null',True,None),('badge/type','effect_badge_type','string',False,('counter','value','formula')),
        ('badge/value','effect_badge_value','badge',False,None),('badge/min','effect_badge_min','integer',True,None),('badge/max','effect_badge_max','integer',True,None),
        ('badge/loop','effect_badge_loop','boolean',False,None),('badge/evaluate','effect_badge_evaluate','boolean',False,None),
        ('badge/reevaluate/event','effect_badge_reevaluate_event','string',False,EFFECT_EVENTS),('badge/reevaluate/formula','effect_badge_reevaluate_formula','string',False,None),('badge/reevaluate/initial','effect_badge_reevaluate_initial','number',False,None),
        ('context','effect_context','null',True,None),('context/origin/actor','effect_origin_actor_uuid','string',False,None),
        ('context/origin/token','effect_origin_token_uuid','string',True,None),('context/origin/item','effect_origin_item_uuid','string',True,None),
        ('context/origin/spellcasting','effect_origin_spellcasting','null',True,None),
        ('context/origin/spellcasting/attribute/type','effect_origin_spellcasting_attribute','string',False,('str','dex','con','int','wis','cha')),
        ('context/origin/spellcasting/attribute/mod','effect_origin_spellcasting_modifier','number',False,None),
        ('context/origin/spellcasting/tradition','effect_origin_spellcasting_tradition','string',True,None),
        ('context/target','effect_target','null',True,None),('context/target/actor','effect_target_actor_uuid','string',False,None),('context/target/token','effect_target_token_uuid','string',True,None),
        ('context/roll','effect_context_roll','null',True,None),('context/roll/total','effect_context_roll_total','number',False,None),('context/roll/degreeOfSuccess','effect_context_roll_degree','number',True,(0,1,2,3)),
    ]:EFFECT_SOURCE['/system/'+path]=(concept,kind,nullable,choices)
    for key in ('title','authors','license','remaster'):
        EFFECT_SOURCE['/system/publication/'+key]=('publication_'+key,'boolean' if key=='remaster' else 'string',False,None)
_effect_specs()


def _effect_spec(path):
    """PF2e-specific effect8.6.1 selected arrays and badge union leaf alternatives.

    Records paginate independently, so badge discriminator/value consistency is
    enforced in the browser selector; this boundary admits only each union leaf.
    """
    if path in EFFECT_SOURCE:return [EFFECT_SOURCE[path]]
    if path=='/system/badge/reevaluate':
        return [('effect_badge_reevaluate','null',True,None),('effect_badge_reevaluate_event','string',True,EFFECT_EVENTS)]
    for base,concept in EFFECT_ARRAYS.items():
        if path==base:return [(concept,'array',base=='/system/badge/labels',None)]
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path):return [(concept,'string',False,None)]
    return []



# PF2e-specific ConditionSystemSource8.6.1; persisted leaves, no prepared activity.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/condition/data.ts
CONDITION_SOURCE = {
    '/system/'+path:(concept,kind,nullable) for path,concept,kind,nullable in (
        ('value/isValued','condition_is_valued','boolean',False),
        ('value/value','condition_stored_value','number',True),
        ('persistent','condition_persistent_damage','null',True),
        ('persistent/formula','condition_persistent_formula','string',False),
        ('persistent/damageType','condition_persistent_damage_type','string',False),
        ('persistent/dc','condition_persistent_recovery_dc','number',False),
        ('persistent/criticalHit','condition_persistent_critical_hit','boolean',False),
        ('references/parent','condition_parent_reference','null',True),
        ('references/parent/id','condition_parent_item_id','string',False),
        ('fromSpell','condition_from_spell','boolean',False),
        ('group','condition_group','string',True),('slug','source_slug','string',True),
        *((f'publication/{key}','publication_'+key,'boolean' if key=='remaster' else 'string',False)
          for key in ('title','authors','license','remaster')),
    )
}
CONDITION_ARRAYS = {'/system/'+path:concept for path,concept in (
    ('traits/value','condition_trait_code'),('traits/otherTags','condition_other_tag_code'),
    ('overrides','condition_override_slug'),('references/children','condition_child_reference'),
    ('references/overrides','condition_override_reference'),('references/overriddenBy','condition_overridden_by_reference'))}


def _condition_spec(path):
    """PF2e-specific condition8.6.1 primitive source paths, never resolved IDs.

    Source schema link above; lists flatten local Item IDs and condition type.
    Damage formulas and recovery DCs remain authored, never rolled or evaluated.
    """
    if path in CONDITION_SOURCE:return CONDITION_SOURCE[path]
    if path in CONDITION_ARRAYS:return (CONDITION_ARRAYS[path],'array',False)
    for base,concept in CONDITION_ARRAYS.items():
        suffix=path.removeprefix(base+'/')
        if path.startswith(base+'/') and re.fullmatch(r'(0|[1-9][0-9]*)',suffix) and '/references/' not in base:
            return (concept,'string',False)
    match=re.fullmatch(r'/system/references/(children|overrides|overriddenBy)/(0|[1-9][0-9]*)/(id|type)',path)
    if match:
        role={'children':'child','overrides':'override','overriddenBy':'overridden_by'}[match[1]]
        return ('condition_'+role+'_item_'+match[3],'condition_type' if match[3]=='type' else 'string',False)
    return None


def _condition_relationship(row, identity):
    """PF2e-specific condition8.6.1 local Item references and override slugs.

    The pinned condition/data.ts schema above defines local IDs, not UUIDs.
    Only resolved same-owner Items carry canonical selectors; source references
    never establish effective suppression, activity or persistent damage state.
    """
    raw = row['raw']
    if not raw or row['section'] != 'relationships' or row['kind'] != 'relationship': return False
    path = raw[0]['path']
    if row['key'] != 'relationships:condition:' + path: return False
    if any(r['document_uuid'] != identity['uuid'] for r in raw): return False
    role = None
    marker = False
    if path in ('/system/references/parent', '/system/references/parent/id'):
        role = 'parent_reference'
        marker = path.endswith('/parent')
        if len(raw) != 1: return False
    else:
        match = re.fullmatch(r'/system/references/(children|overrides|overriddenBy)(?:/(0|[1-9][0-9]*)/id)?', path)
        if match:
            role = {'children':'child_reference','overrides':'override_reference','overriddenBy':'overridden_by_reference'}[match[1]]
            marker = match[2] is None
            if marker:
                if len(raw) != 1: return False
            elif len(raw) != 2 or raw[1]['path'] != path[:-2] + 'type' or raw[1]['present'] and raw[1].get('value') != 'condition': return False
        elif re.fullmatch(r'/system/overrides(?:/(0|[1-9][0-9]*))?', path):
            role = 'override_slug'
            marker = path == '/system/overrides'
            if len(raw) != 1: return False
        else: return False
    first = raw[0]
    if marker:
        if first['present'] and (first.get('value') is not None if role == 'parent_reference' else first.get('value') != []): return False
    elif first['present'] and type(first.get('value')) is not str: return False
    provenance = row['provenance']
    if provenance['mapping'] != 'pf2e.condition.reference.v1' or not provenance['limitations'] or any(not v for v in provenance['limitations']): return False
    if provenance['contributors'] != [{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]: return False
    mapped = row['mapped']; value = mapped['value']
    if mapped['concept'] != 'condition_' + role or mapped['unit'] is not None or type(value) is not dict: return False
    status = value.get('status')
    local_id = first.get('value') if first['present'] and not marker else None
    if status in ('missing','denied','unsupported','unverified'):
        if set(value) != {'status','target_uuid'} or value['target_uuid'] is not None: return False
        if not local_id: return status == 'missing'
        if role == 'override_slug' or identity['actor'] is None: return status == 'unverified'
        return True
    if status != 'resolved' or role == 'override_slug' or not local_id or identity['actor'] is None: return False
    required = {'status','target_uuid','document_name','type','name','name_truncated'}
    instance = identity['instance']
    if set(value) != required | ({'token_uuid'} if instance is not None else set()): return False
    if not re.fullmatch(r'[^.\s#]+', local_id): return False
    if value['target_uuid'] != identity['actor']['uuid'] + '.Item.' + local_id or value['document_name'] != 'Item': return False
    if value['type'] not in get_args(ItemType) or value['type']=='affliction' or role != 'parent_reference' and value['type'] != 'condition': return False
    if type(value['name']) is not str or len(value['name']) > 256 or type(value['name_truncated']) is not bool: return False
    return instance is None or value['token_uuid'] == instance['token_uuid']


def _condition_record(row,identity):
    """PF2e-specific condition8.6.1 source DTO; no active/suppressed/duration state.

    Persisted local reference IDs and override slugs stay unchanged source text;
    this boundary provides no relationship hydration or effective interpretation.
    """
    if row['section']=='relationships': return _condition_relationship(row,identity)
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];value=raw.get('value')
    if path in SOURCE_PATHS:return row['section'] in ('source','description')
    spec=_condition_spec(path)
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    concept,kind,nullable=spec
    if raw['document_uuid']!=identity['uuid'] or row['provenance']['contributors']!=[{k:raw[k] for k in ('document_uuid','path','basis')}]:return False
    if row['provenance']['mapping']!='pf2e.condition.source.v1' or row['provenance']['limitations']!=['persisted_source_not_effective_condition_state']:return False
    if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):return False
    if not raw['present']:return True
    if value is None and nullable:return True
    return {'string':type(value) is str,'number':type(value) in (int,float) and math.isfinite(value),
            'boolean':type(value) is bool,'null':False,'array':type(value) is list and not value,
            'condition_type':type(value) is str and value=='condition'}[kind]


EFFECT_REFERENCE_ROLES = ('origin_actor','origin_token','origin_item','target_actor','target_token')
EFFECT_REFERENCE_PATHS = ['/system/context/'+role.replace('_','/') for role in EFFECT_REFERENCE_ROLES]


def _effect_reference_uuid(value, kind):
    """PF2e-specific effect context selector shape; canonical supported documents.

    UUIDs are persisted source selectors, never names or inferred relationships.
    Core14.369/PF2e8.6.1 contracts are pinned above; synthetic Actor/Item UUIDs
    retain their explicit Token selector and may not fall back to a base Actor.
    """
    if type(value) is not str or not 1 <= len(value) <= 512:return False
    leaf=r'[^.\s#]+'
    actor=rf'(?:Actor\.{leaf}|Scene\.{leaf}\.Token\.{leaf}\.Actor\.{leaf}|Compendium\.(?:{leaf}\.)+Actor\.{leaf})'
    patterns={'Actor':actor,'Token':rf'Scene\.{leaf}\.Token\.{leaf}',
              'Item':rf'(?:Item\.{leaf}|{actor}\.Item\.{leaf}|Compendium\.(?:{leaf}\.)+Item\.{leaf})'}
    return re.fullmatch(patterns[kind],value) is not None


def _effect_relationship(row,identity):
    """PF2e-specific effect8.6.1 explicit context references with source provenance.

    All five persisted reference leaves are context contributors. Permission or
    unsupported targets expose only status, never resolved names/identifiers.
    Resolution verifies selected Token context in the browser, not by computing
    effective statistics here. Schema: pinned effect/data.ts above.
    """
    role=row['key'].removeprefix('relationships:effect:')
    if role not in EFFECT_REFERENCE_ROLES or row['key']!='relationships:effect:'+role or row['section']!='relationships' or row['kind']!='relationship':return False
    if len(row['raw'])!=5 or [raw['path'] for raw in row['raw']]!=EFFECT_REFERENCE_PATHS:return False
    for raw in row['raw']:
        if raw['document_uuid']!=identity['uuid'] or raw['present'] and raw['value'] is not None and type(raw['value']) is not str:return False
    provenance=row['provenance']
    if provenance['mapping']!='pf2e.effect.context-reference.v1' or not provenance['limitations'] or any(not item for item in provenance['limitations']):return False
    if provenance['contributors']!=[{k:raw[k] for k in ('document_uuid','path','basis')} for raw in row['raw']]:return False
    mapped=row['mapped'];value=mapped['value']
    if mapped['concept']!='effect_'+role+'_reference' or mapped['unit'] is not None or type(value) is not dict:return False
    selected=row['raw'][EFFECT_REFERENCE_ROLES.index(role)]
    if not selected['present'] or selected['value'] is None or selected['value']=='':
        return value==dict(status='missing',target_uuid=None)
    if value.get('status') in ('missing','denied','unsupported','unverified'):
        return set(value)=={'status','target_uuid'} and value['target_uuid'] is None
    if value.get('status')!='resolved' or not {'status','target_uuid','document_name','name','name_truncated'}<=set(value) or not set(value)<={'status','target_uuid','document_name','name','name_truncated','token_uuid'}:return False
    kind={'actor':'Actor','token':'Token','item':'Item'}[role.split('_')[1]]
    target=value['target_uuid'];raw=row['raw'][EFFECT_REFERENCE_ROLES.index(role)]
    if value['document_name']!=kind or not _effect_reference_uuid(target,kind) or not raw['present'] or target!=raw['value']:return False
    if type(value['name']) is not str or len(value['name'])>256 or type(value['name_truncated']) is not bool:return False
    token=value.get('token_uuid')
    if token is not None and not _effect_reference_uuid(token,'Token'):return False
    if 'token_uuid' in value and token is None:return False
    if kind=='Token':return token==target
    if target.startswith('Scene.'):
        if token is None or not target.startswith(token+'.Actor.'):return False
    if kind=='Actor':
        paired=row['raw'][1 if role=='origin_actor' else 4].get('value')
        if paired is not None and token!=paired:return False
        if paired is None and token is not None and not target.startswith(token+'.Actor.'):return False
    elif kind=='Item':
        if token is not None and token!=row['raw'][1].get('value'):return False
        if '.Item.' in target and not target.startswith('Compendium.'):
            owner=target.rsplit('.Item.',1)[0]
            source_actor=row['raw'][0].get('value')
            if type(source_actor) is str and owner!=source_actor:return False
    return True


def _effect_record(row,identity):
    """PF2e-specific persisted effect8.6.1 DTO; never expired/prepared/activity state.

    Source UUID strings remain authored references, not resolved relationships.
    Badge formulas are retained without evaluation. Schema links beside specs.
    """
    if row['section']=='relationships':return _effect_relationship(row,identity)
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];value=raw.get('value')
    if path in SOURCE_PATHS:return row['section'] in ('source','description')
    if row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path or row['provenance']['mapping']!='pf2e.effect.source.v1':return False
    if raw['document_uuid']!=identity['uuid'] or row['provenance']['contributors']!=[{k:raw[k] for k in ('document_uuid','path','basis')}]:return False
    if row['provenance']['limitations']!=['persisted_source_not_effective_or_expiration_state']:return False
    for concept,kind,nullable,choices in _effect_spec(path):
        if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):continue
        if not raw['present']:return True
        if value is None and nullable:return True
        number=type(value) in (int,float) and math.isfinite(value)
        valid={'number':number,'integer':number and int(value)==value,'duration':number and value>=-1,
               'string':type(value) is str,'boolean':type(value) is bool,'null':False,
               'badge':type(value) is str or number,'array':type(value) is list and not value}[kind]
        if valid and (choices is None or value in choices):return True
    return False


def _effect_source_page(records):
    """PF2e-specific8.6.1 same-page effect source union consistency.

    EffectSystemSource's badge discriminator selects string formula versus
    numeric counter/value data. Null/missing containers cannot simultaneously
    supply present descendants. Only witnesses on this page are compared: a
    missing discriminator or parent marker may occur on a different page.
    https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/effect/data.ts
    """
    fields={row['raw'][0]['path']:row['raw'][0] for row in records
            if row['section']=='source' and row['provenance']['mapping']=='pf2e.effect.source.v1'}
    containers=('/system/badge','/system/badge/reevaluate','/system/context',
                '/system/context/origin/spellcasting','/system/context/target','/system/context/roll')
    for path in containers:
        marker=fields.get(path)
        if marker is not None and (not marker['present'] or marker['value'] is None):
            if any(child.startswith(path+'/') and field['present'] for child,field in fields.items()):return False
    badge=fields.get('/system/badge/type');value=fields.get('/system/badge/value')
    if badge is not None and badge['present'] and value is not None and value['present']:
        if badge['value']=='formula':return type(value['value']) is str
        return type(value['value']) in (int,float)
    return True


# PF2e-specific NPCSystemSource8.6.1 selected source fields, never effective math.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/npc/data.ts
NPC_NOTES = {'/system/details/'+key:'creature_'+key+'_source' for key in ('blurb','publicNotes','privateNotes')}
NPC_SOURCE = {}

def _npc_specs():
    """PF2e-specific NPC8.6.1 exact source path/concept/type contract."""
    def add(path,concept,kind,nullable=False):NPC_SOURCE['/system/'+path]=(concept,kind,nullable)
    for path,concept,kind,nullable in [
        ('details/level/value','creature_level','number',False),('details/alliance','recorded_alliance','string',True),
        ('traits/size/value','creature_size_code','string',False),('traits/rarity','creature_rarity_code','string',False),
        ('attributes/adjustment','recorded_creature_adjustment','string',True),('attributes/ac/value','authored_armor_class','number',False),
        ('attributes/ac/details','armor_class_exception_notes','string',False),('attributes/hp/details','hit_point_exception_notes','string',False),
        ('attributes/hp/tempSource','temporary_hit_point_source_item_id','string',False),('attributes/allSaves/value','all_save_exception_notes','string',False),
        ('perception/mod','authored_perception_bonus','number',False),('perception/details','perception_exception_notes','string',False),
        ('perception/vision','recorded_vision','boolean',False),('details/languages/details','language_exception_notes','string',False),
        ('attributes/speed/value','authored_land_speed_feet','number',False),('attributes/speed/details','movement_exception_notes','string',False),
        ('initiative/statistic','initiative_statistic_code','string',False),('spellcasting/rituals/dc','authored_ritual_dc','number',False)]:add(path,concept,kind,nullable)
    for key in ('str','dex','con','int','wis','cha'):add('abilities/'+key+'/mod','attribute_modifier_'+key,'number')
    for key,concept in [('value','recorded_hit_points'),('max','source_maximum_hit_points'),('temp','recorded_temporary_hit_points')]:add('attributes/hp/'+key,concept,'number')
    for key in ('fortitude','reflex','will'):
        add('saves/'+key+'/value','authored_'+key+'_save_bonus','number');add('saves/'+key+'/saveDetail',key+'_save_exception_notes','string')
    for key in ('value','max'):add('resources/focus/'+key,'recorded_focus_'+key,'number')
    for key in ('title','authors','license','remaster'):add('details/publication/'+key,'publication_'+key,'boolean' if key=='remaster' else 'string')
_npc_specs()


def _npc_spec(path):
    """PF2e-specific NPC8.6.1 bounded JSON-pointer leaves and empty markers.

    Arbitrary skill names and predicate keys remain escaped source keys. Predicate
    JSON leaves are preserved without evaluation; maximum depth matches JS32.
    """
    if path in NPC_SOURCE:return NPC_SOURCE[path]
    index=r'(?:0|[1-9][0-9]*)';key=r'(?:[^~/]|~[01])*'
    for base,concept in [('traits/value','creature_trait_code'),('details/languages/value','language_code')]:
        if path=='/system/'+base:return concept,'array',False
        if re.fullmatch('/system/'+base+'/'+index,path):return concept,'string',False
    for base,concept,children in [
        ('perception/senses','creature_senses',{'type':('sense_type_code','string',False),'acuity':('sense_acuity_code','string',False),'range':('sense_range_feet','number',False),'source':('sense_source_label','string',True)}),
        ('attributes/speed/otherSpeeds','other_movement_sources',{'type':('movement_type_code','string',False),'value':('authored_movement_speed_feet','number',False),'label':('movement_source_label','string',False),'source':('movement_source_reference','string',False)})]:
        if path=='/system/'+base:return concept,'array',False
        match=re.fullmatch('/system/'+base+'/'+index+'/([^/]+)',path)
        if match:return children.get(match[1])
    if path=='/system/skills':return 'authored_skill_sources','object',False
    skill='/system/skills/'+key
    for suffix,spec in [('/base',('authored_skill_bonus','number',True)),('/note',('skill_exception_notes','string',False)),('/special',('special_skill_sources','array',False)),('/special/'+index+'/label',('special_skill_label','string',False)),('/special/'+index+'/base',('authored_special_skill_bonus','number',False))]:
        if re.fullmatch(skill+suffix,path):return spec
    predicate_bases=[skill+'/special/'+index+'/predicate']
    for kind in ('immunities','weaknesses','resistances'):
        base='/system/attributes/'+kind
        if path==base:return 'source_'+kind,'array',False
        for suffix,spec in [('/type',(kind+'_type_code','string',False)),('/value',(kind+'_source_value','number',False)),('/applyOnce',('weakness_apply_once_source','boolean',False))]:
            if suffix=='/value' and kind=='immunities' or suffix=='/applyOnce' and kind!='weaknesses':continue
            if re.fullmatch(base+'/'+index+suffix,path):return spec
        for prop in (('exceptions','doubleVs') if kind=='resistances' else ('exceptions',)):
            propbase=base+'/'+index+'/'+prop
            for suffix,spec in [('',(kind+'_'+prop,'array',False)),('/'+index,(kind+'_'+prop+'_code','string',False)),('/'+index+'/label',(kind+'_'+prop+'_label','string',False))]:
                if re.fullmatch(propbase+suffix,path):return spec
            predicate_bases.append(propbase+'/'+index+'/definition')
    for base in predicate_bases:
        match=re.fullmatch('('+base+')(.*)',path)
        if match:
            suffix=match[2]
            if suffix=='':return 'stored_predicate_source','array',False
            if re.fullmatch('/'+index+'(?:/'+key+'){0,31}',suffix):return 'stored_predicate_source','predicate',False
    return None


def _npc_record(row,identity):
    """PF2e-specific NPC8.6.1 exact source DTO; no prepared statistics allowed."""
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path']
    if path in SOURCE_PATHS:return row['section']=='source'
    if path in NPC_NOTES:
        # PF2e-specific NPC biography is opt-in source text, including GM notes.
        if row['section']!='description' or row['provenance']['mapping']!='pf2e.npc.notes.v1':return False
        if raw['document_uuid']!=identity['uuid'] or row['provenance']['contributors']!=[{k:raw[k] for k in ('document_uuid','path','basis')}]:return False
        if row['mapped']!=dict(concept=NPC_NOTES[path],value=None,unit=None):return False
        if raw['present']:
            return row['kind']=='text' and type(raw.get('value')) is str and re.fullmatch(re.escape('description:'+path)+r':(?:0|[1-9][0-9]*)',row['key']) is not None
        return row['kind']=='field' and row['key']=='description:'+path
    spec=_npc_spec(path)
    if spec is None:return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path or row['provenance']['mapping']!='pf2e.npc.source.v1':return False
    if raw['document_uuid']!=identity['uuid'] or row['provenance']['contributors']!=[{k:raw[k] for k in ('document_uuid','path','basis')}]:return False
    if row['mapped']!=dict(concept=concept,value=value,unit=None):return False
    if not raw['present']:return True
    if value is None and nullable:return True
    return {'number':type(value) in (int,float) and math.isfinite(value) if type(value) in (int,float) else False,
            'string':type(value) is str,'boolean':type(value) is bool,
            'array':type(value) is list and not value,'object':type(value) is dict and not value,
            'predicate':value is None or type(value) in (str,bool,int) or type(value) is float and math.isfinite(value) or type(value) in (dict,list) and not value}[kind]


CHARACTER_SOURCE = {}
CHARACTER_NOTES = {'/system/details/languages/details': 'language_exception_notes'}
CHARACTER_LIMIT = ['character_source_not_effective_statistics']


def _character_specs():
    """PF2e-specific CharacterSystemSource8.6.1 allowlist, never prepared totals.

    https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts
    Numeric source declarations impose no bounds except integer skill ranks0..4.
    """
    def add(path, concept, kind, nullable=False, limits=()):
        CHARACTER_SOURCE['/system/'+path] = (concept, kind, nullable, CHARACTER_LIMIT+list(limits))
    add('abilities','recorded_attribute_modifiers','null',True,['null_not_zero_attributes'])
    for key in ('str','dex','con','int','wis','cha'):
        add('abilities/'+key+'/mod','attribute_modifier_'+key,'number',limits=['source_manual_modifier_not_effective_attribute'])
    add('details/level/value','character_level','number')
    for key in ('age','height','weight','gender','ethnicity','nationality'):
        add('details/'+key+'/value','character_'+key+'_source','string')
    add('details/keyability/value','recorded_key_attribute_code','string')
    for key in ('value','min','max'):add('details/xp/'+key,'recorded_experience_'+key,'number')
    for key in ('appearance','backstory','personality','campaign'):
        add('details/biography/visibility/'+key,'biography_'+key+'_visibility_source','boolean',limits=['visibility_not_caller_authorization'])
    add('attributes/hp/value','recorded_hit_points','number')
    add('attributes/hp/temp','recorded_temporary_hit_points','number')
    add('attributes/hp/tempSource','temporary_hit_point_source_item_id','string',limits=['local_item_id_not_verified_uuid'])
    add('attributes/hp/sp/value','recorded_stamina_points','number',limits=['stamina_variant_source_only'])
    add('skills','recorded_skill_ranks','object')
    for key in ('value','max'):add('resources/heroPoints/'+key,'recorded_hero_points_'+key,'number')
    add('resources/focus/value','recorded_focus_value','number',limits=['focus_pool_maximum_not_source'])
    add('resources/crafting/infusedReagents/value','recorded_infused_reagents_value','number',limits=['crafting_availability_not_evaluated'])
    add('resources/resolve/value','recorded_resolve_value','number',limits=['stamina_variant_source_only'])
    add('build/attributes/manual','recorded_manual_attributes','boolean')
    add('build/attributes/apex','recorded_apex_attribute_code','string',True)
    for key in ('appearance','backstory','campaignNotes','allies','enemies','organizations','birthPlace','attitude','beliefs','likes','dislikes','catchphrases','edicts','anathema'):
        CHARACTER_NOTES['/system/details/biography/'+key] = 'character_biography_'+key+'_source'
_character_specs()


def _character_spec(path):
    """PF2e-specific character8.6.1 exact source leaves/empty markers only.

    Nullable abilities are a root marker; standard and unknown stored skill codes
    retain escaped keys and ranks, never arbitrary member fields or check totals.
    """
    if path in CHARACTER_SOURCE:return CHARACTER_SOURCE[path]
    index=r'(?:0|[1-9][0-9]*)'
    arrays={'/system/details/languages/value':'recorded_language_code'}
    arrays.update({'/system/build/attributes/boosts/'+key:'recorded_attribute_boost_code' for key in ('1','5','10','15','20')})
    for base,concept in arrays.items():
        if path==base:return concept,'array',False,CHARACTER_LIMIT
        if re.fullmatch(re.escape(base)+'/'+index,path):return concept,'string',False,CHARACTER_LIMIT
    if re.fullmatch(r'/system/skills/(?:[^~/]|~[01])*/rank',path):
        return 'recorded_skill_proficiency_rank','rank',False,CHARACTER_LIMIT+['rank_not_total_check_modifier']
    return None


def _character_note_spec(path):
    """PF2e-specific character biography/language prose, explicitly requested.

    Ordered edict/anathema strings fragment separately; empty array markers stay
    arrays, not fabricated prose. No enrichment or prepared notes are admitted.
    """
    arrays=('/system/details/biography/edicts','/system/details/biography/anathema')
    if path in CHARACTER_NOTES:return CHARACTER_NOTES[path], 'array' if path in arrays else 'string'
    for base in arrays:
        if re.fullmatch(re.escape(base)+r'/(?:0|[1-9][0-9]*)',path):return CHARACTER_NOTES[base],'string'
    return None


def _character_record(row,identity):
    """PF2e-specific character8.6.1 strict detached source/description DTO.

    Enforces exact concepts, raw primitive types, ranks and source limitations;
    HP/focus maxima and prepared build/statistic properties remain excluded.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];value=raw.get('value')
    if path in ('/name','/type'):return row['section']=='source'
    if raw['document_uuid']!=identity['uuid'] or row['provenance']['contributors']!=[{k:raw[k] for k in ('document_uuid','path','basis')}]:return False
    note=_character_note_spec(path)
    if note is not None:
        concept,kind=note
        if row['section']!='description' or row['provenance']['mapping']!='pf2e.character.notes.v1' or row['provenance']['limitations']!=CHARACTER_LIMIT:return False
        expected=[] if raw['present'] and kind=='array' else None
        if row['mapped']!=dict(concept=concept,value=expected,unit=None):return False
        if not raw['present']:return row['kind']=='field' and row['key']=='description:'+path
        if kind=='array':return row['kind']=='field' and row['key']=='description:'+path and type(value) is list and not value
        return row['kind']=='text' and type(value) is str and re.fullmatch(re.escape('description:'+path)+r':(?:0|[1-9][0-9]*)',row['key']) is not None
    spec=_character_spec(path)
    if spec is None:return False
    concept,kind,nullable,limits=spec
    if row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path or row['provenance']['mapping']!='pf2e.character.source.v1' or row['provenance']['limitations']!=limits:return False
    expected=value
    if raw['present'] and kind=='rank':
        if type(value) is not int or not 0<=value<=4:return False
        expected=dict(rank=value,label=LORE_RANKS[value])
        if type(row['mapped']['value']) is not dict or type(row['mapped']['value'].get('rank')) is not int:return False
    elif type(row['mapped']['value']) is not type(expected):return False
    if row['mapped']!=dict(concept=concept,value=expected,unit=None):return False
    if not raw['present']:return True
    if value is None:return nullable
    if kind in ('number','rank'):return type(value) in (int,float) and math.isfinite(value)
    if kind=='string':return type(value) is str
    if kind=='boolean':return type(value) is bool
    if kind=='array':return type(value) is list and not value
    if kind=='object':return type(value) is dict and not value
    return False


FAMILIAR_LIMIT = ['familiar_source_not_master_derived_statistics']


def _familiar_spec(path):
    """PF2e-specific familiar8.6.1 persisted source, never master-derived totals.

    https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts
    master.id is a nullable Character foreign-document local ID; ability codes
    remain uninterpreted. HP value/temp are nonnegative integer source fields.
    """
    return {
        '/system/master/id': ('recorded_master_character_id','string',True),
        '/system/master/ability': ('recorded_master_attribute_code','string',True),
        '/system/attributes/hp/value': ('recorded_hit_points','integer',False),
        '/system/attributes/hp/temp': ('recorded_temporary_hit_points','integer',False),
        '/system/attributes/hp/tempSource': ('temporary_hit_point_source_item_id','nonblank',False),
    }.get(path)


def _familiar_record(row,identity):
    """PF2e-specific familiar8.6.1 source/explicit creature prose DTO validation.

    Uses the pinned familiar/data.ts schema linked by _familiar_spec, excludes
    all prepared/master statistics and preserves unknown stored ability codes.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];value=raw.get('value')
    if path in ('/name','/type'):return row['section']=='source'
    if raw['document_uuid']!=identity['uuid'] or row['provenance']['contributors']!=[{k:raw[k] for k in ('document_uuid','path','basis')}]:return False
    if row['provenance']['limitations']!=FAMILIAR_LIMIT:return False
    if path=='/system/details/creature/value':
        if row['section']!='description' or row['provenance']['mapping']!='pf2e.familiar.notes.v1' or row['mapped']!=dict(concept='familiar_creature_description_source',value=None,unit=None):return False
        if not raw['present']:return row['kind']=='field' and row['key']=='description:'+path
        return row['kind']=='text' and type(value) is str and re.fullmatch(re.escape('description:'+path)+r':(?:0|[1-9][0-9]*)',row['key']) is not None
    spec=_familiar_spec(path)
    if spec is None:return False
    concept,kind,nullable=spec
    if row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path or row['provenance']['mapping']!='pf2e.familiar.source.v1':return False
    if type(row['mapped']['value']) is not type(value) or row['mapped']!=dict(concept=concept,value=value,unit=None):return False
    if not raw['present']:return True
    if value is None:return nullable
    if kind=='integer':return type(value) in (int,float) and math.isfinite(value) and value>=0 and value==int(value)
    return type(value) is str and (kind!='nonblank' or bool(value.strip()))


def _familiar_relationship(row,identity):
    """PF2e-specific familiar8.6.1 master ID and owned action source evidence.

    Pinned familiar/data.ts and item/ability/data.ts (revision linked above).
    No derived master state or activation is inferred. Action traits are retained
    but have no supported familiar/master classification in this pinned schema.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship':return False
    raw=row['raw'];mapped=row['mapped'];p=row['provenance']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['unit'] is not None:return False
    if type(p) is not dict or set(p)!={'contributors','mapping','limitations'}:return False
    for r in raw:
        if type(r) is not dict or not {'document_uuid','path','present','basis'}<=set(r) or not set(r)<={'document_uuid','path','present','basis','value'} or r['basis']!='source' or type(r['present']) is not bool or r['present']!=('value' in r):return False
    if p['contributors']!=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if row['section']=='identity':
        if row['key']!='identity:familiar_master' or mapped['concept']!='familiar_master' or p['mapping']!='pf2e.familiar.master.v1' or p['limitations']!=['stored_master_reference_not_current_statistics']:return False
        if len(raw)!=1 or raw[0]['document_uuid']!=identity['uuid'] or raw[0]['path']!='/system/master/id':return False
        r=raw[0];claim=r.get('value')
        if r['present'] and claim is not None and type(claim) is not str:return False
        status=value.get('status')
        if status!='resolved':
            if value!={'status':status,'target_uuid':None}:return False
            if not r['present'] or claim=='':return status=='missing'
            if claim is None:return status=='unassociated'
            return status in ('missing','denied','unsupported','unverified')
        uuid='Actor.'+claim if type(claim) is str else None
        return (r['present'] and type(claim) is str and re.fullmatch(r'[^.\s#]+',claim) is not None and len(uuid)<=512 and set(value)=={'status','target_uuid','document_name','type','name','name_truncated','next_call'} and value['target_uuid']==uuid and value['document_name']=='Actor' and value['type']=='character' and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and value['next_call']=={'tool':'read_actor','arguments':{'actor_uuid':uuid}})
    if row['section']!='abilities' or mapped['concept']!='familiar_ability' or p['mapping']!='pf2e.familiar.ability.v1' or p['limitations']!=['owned_action_reference_not_complete_or_active_ability','ability_scope_requires_description']:return False
    if row['key']=='abilities:familiar:denied':return raw==[] and value==dict(status='denied',target_uuid=None)
    if not 3<=len(raw)<=202:return False
    uuid=raw[0]['document_uuid']
    if not _casting_owned(uuid,identity) or row['key']!='abilities:familiar:'+uuid or any(r['document_uuid']!=uuid for r in raw):return False
    if [r['path'] for r in raw[:2]]!=['/name','/type'] or not all(r['present'] for r in raw[:2]) or type(raw[0]['value']) is not str or raw[1]['value']!='action':return False
    traits=raw[2:]
    if len(traits)==1 and traits[0]['path']=='/system/traits/value':
        if traits[0]['present'] and (type(traits[0]['value']) is not list or traits[0]['value']!=[]):return False
    elif any(r['path']!='/system/traits/value/'+str(i) or not r['present'] or type(r['value']) is not str for i,r in enumerate(traits)):return False
    expected=dict(status='resolved',target_uuid=uuid,document_name='Item',type='action',name=raw[0]['value'][:256],name_truncated=len(raw[0]['value'])>256,ability_kind='unclassified')
    if identity['instance'] is not None:expected['token_uuid']=identity['instance']['token_uuid']
    return value==expected and type(value.get('name_truncated')) is bool


def _lore_record(row: dict[str, Any], identity: dict[str, Any]) -> bool:
    """PF2e-specific Lore8.6.1 source semantics depend on actual owner type.

    NPC modifier is authored source; character rank is proficiency, not a total.
    World/unknown owner fields retain stored meaning without assuming character.
    Schema URL and supported version are recorded beside LORE_PATHS.
    """
    if len(row['raw']) != 1 or row['kind'] not in ('field','text'):
        return False
    raw=row['raw'][0];path=raw['path'];value=raw.get('value')
    if raw['document_uuid'] != identity['uuid'] or len(row['provenance']['contributors']) != 1 or any(c['document_uuid'] != identity['uuid'] or c['path'] != path for c in row['provenance']['contributors']):
        return False
    expected=value
    if path not in SOURCE_PATHS:
        if row['section'] != 'source' or row['kind'] != 'field' or row['provenance']['mapping'] != 'pf2e.lore.source.v1':
            return False
        owner=(identity.get('actor') or {}).get('type')
        concept=None
        if path == '/system/mod/value':
            concept='npc_lore_authored_modifier' if owner == 'npc' else 'stored_lore_modifier'
            if raw['present'] and type(value) not in (int,float):return False
        elif path == '/system/proficient/value':
            concept='character_lore_proficiency_rank' if owner == 'character' else 'stored_lore_proficiency_rank'
            if raw['present']:
                if type(value) is not int or not 0 <= value <= 4:return False
                expected=dict(rank=value,label=LORE_RANKS[value])
        elif raw['present']:
            if path == '/system/variants':
                if type(value) is not dict or value != {}:return False
            elif path == '/system/traits/otherTags':
                if type(value) is not list or value != []:return False
            elif path == '/system/publication/remaster':
                if type(value) is not bool:return False
            elif not (value is None and path == '/system/slug') and type(value) is not str:return False
        if concept is not None and row['mapped']['concept'] != concept:return False
    if row['kind'] == 'text':expected=None
    return type(row['mapped']['value']) is type(expected) and row['mapped']['value'] == expected


def _skill_current_spec(path, actor_type):
    """PF2e-specific8.6.1 character/NPC serialized SkillData leaf contracts.

    Source skill ranks and NPC authored variants remain separate. Schema:
    https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor
    creature/character/npc/data.ts and system/statistic/data.ts define these
    transformed primitives; no methods, predicates or target math are evaluated.
    """
    if actor_type not in ('character','npc') or type(path) is not str:return None
    if path=='/system/skills':return ('current_skill_collection','collection')
    match=re.fullmatch(r'/system/skills/((?:[^~/]|~[01])*)/([^/]+)',path)
    if not match:return None
    key=match[1].replace('~1','/').replace('~0','~')
    if not 1<=len(key)<=256:return None
    leaf=match[2]
    kinds=dict(slug='string',label='string',attribute='attribute',value='number',totalModifier='number',dc='number',breakdown='string',lore='boolean',itemId='nullable_string')
    kinds.update(dict(rank='rank',armor='boolean') if actor_type=='character' else dict(base='number',mod='number',visible='boolean',note='string'))
    if leaf not in kinds:return None
    return ('current_skill_'+{'itemId':'item_id','totalModifier':'total_modifier'}.get(leaf,leaf),kinds[leaf])


def _actor_skill_current_record(row, identity):
    """PF2e-specific8.6.1 exact transformed skill fields and owner-local Lore.

    _skill_current_spec pins the document-data schema. Lore claims reference
    actual owned Lore Items; no name/slug join or exhaustive Lore claim is made.
    Familiar master-derived skills remain unsupported by this boundary.
    """
    if identity['type'] not in ('character','npc') or set(row)!={'key','section','kind','raw','mapped','provenance'}:return False
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['unit'] is not None:return False
    if type(provenance) is not dict or set(provenance)!={'contributors','mapping','limitations'}:return False
    for field in raw:
        if type(field) is not dict or not {'document_uuid','path','present','basis'}<=set(field) or not set(field)<={'document_uuid','path','present','basis','value'}:return False
        if field['document_uuid']!=identity['uuid'] or field['basis']!='transformed' or type(field['present']) is not bool or field['present']!=('value' in field):return False
    if provenance['contributors']!=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]:return False
    mapping=provenance['mapping']
    if mapping=='pf2e.actor.skills-current.v1':
        if provenance['limitations']!=['serialized_current_skill_not_target_context']:return False
        if row['key']=='skills:current:denied':return row['kind']=='relationship' and raw==[] and mapped==dict(concept='current_skill_item_reference',value=dict(status='denied',target_uuid=None),unit=None)
        if len(raw)!=1 or row['kind']!='field':return False
        field=raw[0];path=field['path'];spec=_skill_current_spec(path,identity['type'])
        if spec is None or row['key']!='skills:current:'+path:return False
        concept,kind=spec;value=field.get('value')
        if field['present']:
            valid={'number':type(value) in (int,float) and math.isfinite(value),'string':type(value) is str,
                   'attribute':type(value) is str and value in ('str','dex','con','int','wis','cha'),'boolean':type(value) is bool,
                   'rank':type(value) is int and 0<=value<=4,'nullable_string':value is None or type(value) is str,
                   'collection':type(value) is dict and value=={}}
            if not valid[kind]:return False
        expected=None if kind=='collection' else dict(rank=value,label=LORE_RANKS[value]) if kind=='rank' and field['present'] else value
        return json.dumps(mapped,sort_keys=True,allow_nan=False)==json.dumps(dict(concept=concept,value=expected,unit=None),sort_keys=True,allow_nan=False)
    if mapping!='pf2e.actor.skills-lore.v1' or provenance['limitations']!=['serialized_lore_claim_not_exhaustive_owned_lore'] or row['kind']!='relationship' or len(raw)!=2:return False
    path=raw[0]['path'];spec=_skill_current_spec(path,identity['type'])
    if spec!=('current_skill_lore','boolean') or not raw[0]['present'] or raw[0]['value'] is not True or raw[1]['path']!=path[:-4]+'itemId':return False
    item_id=raw[1].get('value')
    if raw[1]['present'] and item_id is not None and type(item_id) is not str:return False
    escaped=path[len('/system/skills/'):-len('/lore')]
    if row['key']!='skills:current-lore:'+escaped or mapped['concept']!='current_skill_lore_reference' or type(mapped['value']) is not dict:return False
    value=mapped['value'];status=value.get('status')
    if status in ('missing','unsupported'):
        return value==dict(status=status,target_uuid=None) and (bool(item_id) or status=='missing')
    if status!='resolved' or not item_id or not _casting_owned(identity['uuid']+'.Item.'+item_id,identity):return False
    expected={'status','target_uuid','document_name','type','name','name_truncated'}|({'token_uuid'} if identity['instance'] is not None else set())
    return (set(value)==expected and value['target_uuid']==identity['uuid']+'.Item.'+item_id and value['document_name']=='Item' and value['type']=='lore'
            and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool
            and (identity['instance'] is None or value['token_uuid']==identity['instance']['token_uuid']))


def _skills_section(records, section, identity):
    """PF2e-specific8.6.1 page-local skill claims, never exhaustive skills."""
    rows=[r for r in records if r['section']=='skills'];current=[r for r in rows if r['provenance']['mapping'] in ('pf2e.actor.skills-current.v1','pf2e.actor.skills-lore.v1')]
    reasons=set(section['reasons'])
    if section['status']!='partial' or 'other_skills_pending' not in reasons:return False
    if not reasons<={'other_skills_pending','related_items_denied','conditional_skill_variants_not_evaluated','current_skill_fields_unavailable','current_skill_items_denied','pagination'}:return False
    if not current:return True
    if identity['type']=='npc' and 'conditional_skill_variants_not_evaluated' not in reasons:return False
    if any(r['key']=='skills:current:denied' for r in current) and 'current_skill_items_denied' not in reasons:return False
    fields={};root=False
    for row in current:
        for field in row['raw']:
            path=field['path']
            if not field['present'] and not (identity['type']=='npc' and path.endswith('/note')) and 'current_skill_fields_unavailable' not in reasons:return False
            if path in fields and json.dumps(fields[path],sort_keys=True)!=json.dumps(field,sort_keys=True):return False
            fields[path]=field
            if path=='/system/skills':root=True
    if root and any(path!='/system/skills' for path in fields):return False
    return True


def _lore_specialty(row: dict[str, Any], identity: dict[str, Any]) -> bool:
    """PF2e-specific Actor skills contain actual owned Lore references only.

    Lore8.6.1 source name/type identify specialty; no effective skill is inferred.
    Source UUID must be an immediate embedded Item of the selected current Actor.
    """
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if row['key'] == 'skills:lore:denied':
        return (row['kind'] == 'relationship' and row['section'] == 'skills' and raw == [] and
                mapped == dict(concept='lore_specialty',value=dict(target_uuid=None,status='denied'),unit=None) and
                provenance['contributors'] == [] and provenance['mapping'] == 'pf2e.lore.specialty.v1' and
                bool(provenance['limitations']) and all(provenance['limitations']))
    if len(raw) != 2 or row['kind'] != 'relationship' or row['section'] != 'skills':return False
    target=raw[0]['document_uuid'];prefix=identity['uuid']+'.Item.'
    if not target.startswith(prefix) or not target[len(prefix):] or '.' in target[len(prefix):]:return False
    if row['key'] != 'skills:lore:'+target or [r['path'] for r in raw] != ['/name','/type']:return False
    if any(r['document_uuid'] != target or not r['present'] for r in raw) or type(raw[0]['value']) is not str or raw[1]['value'] != 'lore':return False
    expected=dict(target_uuid=target,status='resolved')
    instance=identity['instance']
    if instance is not None:expected['token_uuid']=instance['token_uuid']
    return (mapped == dict(concept='lore_specialty',value=expected,unit=None) and
            provenance['mapping'] == 'pf2e.lore.specialty.v1' and bool(provenance['limitations']) and
            all(provenance['limitations']) and provenance['contributors'] == [{k:r[k] for k in ('document_uuid','path','basis')} for r in raw])


def _npc_item_reference(row: dict[str, Any], identity: dict[str, Any]) -> bool:
    """PF2e-specific NPC8.6.1 owned melee/action source references only.

    Persisted Item name/type establish membership, never an effective Strike or
    ability total. Selected token context is preserved for follow-up read_item.
    Schema: https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/npc/data.ts
    """
    section=row['section']
    if identity['type']!='npc' or section not in ('strikes','abilities'):return False
    item_type,concept=('melee','npc_attack_item') if section=='strikes' else ('action','npc_ability_item')
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if row['kind']!='relationship' or provenance['mapping']!='pf2e.npc.item-reference.v1' or not provenance['limitations'] or not all(provenance['limitations']):return False
    if row['key']==section+':items:denied':
        return raw==[] and provenance['contributors']==[] and mapped==dict(concept=concept,value=dict(target_uuid=None,status='denied'),unit=None)
    if len(raw)!=2:return False
    target=raw[0]['document_uuid'];prefix=identity['uuid']+'.Item.'
    if not target.startswith(prefix) or not target[len(prefix):] or '.' in target[len(prefix):]:return False
    if row['key']!=section+':item:'+target or [r['path'] for r in raw]!=['/name','/type']:return False
    if any(r['document_uuid']!=target or not r['present'] for r in raw) or type(raw[0]['value']) is not str or raw[1]['value']!=item_type:return False
    expected=dict(target_uuid=target,status='resolved')
    if identity['instance'] is not None:expected['token_uuid']=identity['instance']['token_uuid']
    return mapped==dict(concept=concept,value=expected,unit=None) and provenance['contributors']==[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]


def _empty_source_object(path: str, identity: dict[str, Any]) -> bool:
    """PF2e-specific empty NPC damageRolls/Lore variants source markers8.6.1; no map dumps."""
    if identity['document_name']=='Actor' and identity['type']=='character':
        return path=='/system/skills'
    return (identity['document_name']=='Actor' and identity['type']=='npc' and _npc_spec(path) is not None and _npc_spec(path)[1] in ('object','predicate')) or identity['document_name']=='Item' and ((identity['type']=='melee' and path=='/system/damageRolls') or (identity['type']=='lore' and path=='/system/variants') or (identity['type']=='weapon' and _weapon_spec(path) is not None and _weapon_spec(path)[1]=='object') or (identity['type']=='armor' and _armor_spec(path) is not None and _armor_spec(path)[1]=='object') or (identity['type']=='shield' and _shield_spec(path) is not None and _shield_spec(path)[1]=='object') or (identity['type']=='spell' and _spell_spec(path) is not None and _spell_spec(path)[1]=='object') or (identity['type']=='ancestry' and _ancestry_spec(path) is not None and _ancestry_spec(path)[1]=='object') or (identity['type']=='background' and _background_spec(path) is not None and _background_spec(path)[1]=='object') or (identity['type']=='feat' and _feat_spec(path) is not None and _feat_spec(path)[1]=='object') or (identity['type']=='deity' and _deity_spec(path) is not None and _deity_spec(path)[1]=='object') or (identity['type']=='class' and _class_spec(path) is not None and _class_spec(path)[1]=='object') or (identity['type']=='kit' and _kit_spec(path) is not None and _kit_spec(path)[1]=='object') or (identity['type']=='consumable' and _contained_spell_spec(path) is not None and _contained_spell_spec(path)[1]=='object'))


def _melee_value(raw: dict[str, Any]) -> bool:
    """PF2e-specific MeleeSystemSource8.6.1 primitive shapes; no prepared math.

    Source range null differs from absent/nullable ranged leaves; damage formula,
    category and type remain separate authored values. Schema boundary above.
    """
    if not raw['present']:
        return True
    path=raw['path'];value=raw['value']
    if path in {'/system/traits/value','/system/traits/otherTags','/system/attackEffects/value'}:
        return value == []
    if path=='/system/damageRolls':
        return value == {}
    if path in {'/system/area','/system/range'}:
        return value is None
    if path in {'/system/subjectToMAP','/system/publication/remaster'}:
        return type(value) is bool
    if path in {'/system/bonus/value','/system/area/value','/system/range/increment','/system/range/max'}:
        return value is None and path in {'/system/range/increment','/system/range/max'} or type(value) in (int,float)
    if value is None and (path=='/system/slug' or DAMAGE_LEAF.fullmatch(path) and path.endswith('/category')):
        return True
    return type(value) is str


def _melee_record(row: dict[str, Any], identity: dict[str, Any]) -> bool:
    """PF2e-specific NPC attack source8.6.1 and additional-effect label boundary.

    Only known action codes translate; null range has no explicit range context.
    Attack-effect strings are unverified labels, never manufactured selectors.
    Damage source keys retain JSON Pointer escaping and origin Item identity.
    """
    if len(row['raw'])!=1 or any(raw['document_uuid']!=identity['uuid'] or not _melee_value(raw) for raw in row['raw']):
        return False
    raw=row['raw'][0];mapped=row['mapped'];provenance=row['provenance']
    if any(c['document_uuid']!=identity['uuid'] or c['path']!=raw['path'] for c in provenance['contributors']):
        return False
    if row['kind']=='relationship':
        match = re.fullmatch(r'/system/attackEffects/value/(0|[1-9][0-9]*)', raw['path'])
        indexed = (match is not None and raw['present'] and type(raw.get('value')) is str and
                   row['key'] == 'relationships:attackEffects:' + match.group(1))
        marker = (raw['path'] == '/system/attackEffects/value' and
                  row['key'] == 'relationships:attackEffects' and
                  (not raw['present'] or raw.get('value') == []))
        return (row['section'] == 'relationships' and (indexed or marker) and
                mapped == dict(concept='additional_effect', value=dict(target_uuid=None, status='unverified' if indexed else 'missing'), unit=None) and
                provenance['mapping'] == 'pf2e.melee.attack_effect.v1' and
                len(provenance['contributors']) == 1 and bool(provenance['limitations']) and
                all(provenance['limitations']))
    if raw['path'] not in SOURCE_PATHS and (row['section']!='source' or row['kind']!='field'):
        return False
    expected=raw.get('value')
    if raw['path']=='/system/action' and raw['present']:
        expected=MELEE_MODES.get(raw['value'],raw['value'])
    if raw['path']=='/system/range' and raw['present'] and raw['value'] is None:
        expected='no_explicit_range'
    if row['kind']=='text':
        expected=None
    return type(mapped['value']) is type(expected) and mapped['value']==expected



def _empty_source_array(path: str, identity: dict[str, Any]) -> bool:
    """PF2e-specific8.6.1 empty attachment, ability/attack traits and Lore tags."""
    if identity['document_name']=='Actor' and identity['type']=='character':
        spec=_character_spec(path);note=_character_note_spec(path)
        return spec is not None and spec[1]=='array' or note is not None and note[1]=='array'
    return (identity['document_name']=='Actor' and identity['type']=='npc' and _npc_spec(path) is not None and _npc_spec(path)[1] in ('array','predicate') or
            identity['type'] in ATTACHMENT_TYPES and path == '/system/subitems' or
            identity['type'] == 'action' and path in {'/system/traits/value','/system/traits/otherTags'} or
            identity['type'] == 'melee' and path in {'/system/traits/value','/system/traits/otherTags','/system/attackEffects/value'} or
            identity['type'] == 'lore' and path == '/system/traits/otherTags' or
            identity['type'] == 'effect' and path in EFFECT_ARRAYS or
            identity['type'] == 'condition' and path in CONDITION_ARRAYS or
            identity['type'] == 'weapon' and path in WEAPON_ARRAYS or
            identity['type'] == 'ammo' and path in AMMO_ARRAYS or
            identity['type'] == 'armor' and path in ARMOR_ARRAYS or
            identity['type'] == 'shield' and path in SHIELD_ARRAYS or
            identity['type'] == 'equipment' and path in EQUIPMENT_ARRAYS or
            identity['type'] == 'book' and path in BOOK_ARRAYS or
            identity['type'] == 'ancestry' and _ancestry_spec(path) is not None and _ancestry_spec(path)[1]=='array' or
            identity['type'] == 'heritage' and path in HERITAGE_ARRAYS or
            identity['type'] == 'background' and _background_spec(path) is not None and _background_spec(path)[1]=='array' or
            identity['type'] == 'feat' and _feat_spec(path) is not None and _feat_spec(path)[1]=='array' or
            identity['type'] == 'deity' and _deity_spec(path) is not None and _deity_spec(path)[1]=='array' or
            identity['type'] == 'class' and _class_spec(path) is not None and _class_spec(path)[1]=='array' or
            identity['type'] == 'kit' and path in KIT_ARRAYS or
            identity['type'] == 'treasure' and path in TREASURE_ARRAYS or
            identity['type'] == 'backpack' and path in CONTAINER_ARRAYS or
            identity['type'] == 'consumable' and (path in CONSUMABLE_ARRAYS or _contained_spell_spec(path) is not None and _contained_spell_spec(path)[1] == 'array') or
            identity['type'] == 'spellcastingEntry' and _casting_entry_spec(path) is not None and _casting_entry_spec(path)[1] == 'array' or
            identity['type'] == 'spell' and _spell_spec(path) is not None and _spell_spec(path)[1] == 'array')


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


# PF2e-specific WeaponSystemSource8.6.1 persisted leaves, never prepared strikes.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/weapon/data.ts
WEAPON_SOURCE = {'/system/'+p:('weapon_'+c,k,n) for p,c,k,n in (
 ('traits/rarity','rarity_code','string',False),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
 ('category','category_code','string',False),('group','group_code','string',True),
 ('damage/dice','damage_dice','number',False),('damage/die','damage_die_code','string',True),('damage/damageType','damage_type_code','string',False),('damage/modifier','damage_modifier','number',False),
 ('range','range_feet','number',True),('maxRange','max_range_feet','number',True),('reload/value','reload_code','string',True),('expend','expend','number',True),('selectedAmmoId','selected_ammo_local_id','string',True),
 ('bonus/value','bonus','number',False),('splashDamage/value','splash_damage','number',False),('attribute','attribute_code','string',True),('grade','grade_code','string',True),('graspingAppendage','grasping_appendage','boolean',False),('usage/canBeAmmo','can_be_ammo','boolean',False),
 ('damage/persistent','persistent_damage','object',True),('damage/persistent/number','persistent_damage_number','number',False),('damage/persistent/faces','persistent_damage_faces','number',True),('damage/persistent/type','persistent_damage_type_code','string',False),
 ('ammo','ammunition','object',True),('ammo/builtIn','ammo_built_in','boolean',False),('ammo/baseType','ammo_base_type_code','string',True),('ammo/capacity','ammo_capacity','number',True),
 ('meleeUsage','melee_usage','object',False),('meleeUsage/damage/type','melee_damage_type_code','string',False),('meleeUsage/damage/die','melee_damage_die_code','string',False),('meleeUsage/group','melee_group_code','string',False),('meleeUsage/traitToggles','melee_trait_toggles','object',False),('meleeUsage/traitToggles/modular','melee_modular_selected','number',True),('meleeUsage/traitToggles/versatile','melee_versatile_selected_code','string',True),
 ('traits/toggles','trait_toggles','object',False),('traits/toggles/doubleBarrel','double_barrel_toggle','object',False),('traits/toggles/doubleBarrel/selected','double_barrel_selected','boolean',False),('traits/toggles/modular','modular_toggle','object',True),('traits/toggles/modular/selected','modular_selected','number',True),('traits/toggles/versatile','versatile_toggle','object',False),('traits/toggles/versatile/selected','versatile_selected_code','string',True),
 ('specific','specific_baseline','object',True),('specific/material','specific_material','object',False),('specific/material/type','specific_material_type_code','string',True),('specific/material/grade','specific_material_grade_code','string',True),
)}
for _prefix in ('runes','specific/runes'):
    WEAPON_SOURCE.update({'/system/'+_prefix+suffix:('weapon_'+concept,kind,False) for suffix,concept,kind in (('', 'runes','object'),('/potency','rune_potency','number'),('/striking','rune_striking','number'))})
WEAPON_ARRAYS = {'/system/'+p:'weapon_'+c for p,c in (('traits/value','trait_code'),('traits/otherTags','other_tag_code'),('runes/property','property_rune_code'),('specific/runes/property','property_rune_code'),('meleeUsage/traits','melee_trait_code'))}


def _weapon_spec(path):
    """PF2e-specific weapon8.6.1 primitive selected source path contract.

    Source schemas at the pinned URL above; selected ammo IDs remain local text,
    runes remain authored, and no prepared strike or wielded state is inferred.
    """
    if path in WEAPON_SOURCE: return WEAPON_SOURCE[path]
    for base, concept in WEAPON_ARRAYS.items():
        if path == base: return (concept, 'array', False)
        if re.fullmatch(re.escape(base) + r'/(0|[1-9][0-9]*)', path): return (concept, 'string', False)
    return None


def _weapon_ammunition_relationship(row, identity):
    """PF2e-specific WeaponSystemSource.selectedAmmoId8.6.1 local reference.

    The pinned weapon/data.ts schema above defines an authored local ID. A
    resolved same-owner selector never establishes loading, compatibility,
    availability, usability or a prepared strike's ammunition.
    """
    if row['section'] != 'relationships' or row['kind'] != 'relationship' or row['key'] != 'relationships:weapon:selectedAmmoId': return False
    if len(row['raw']) != 1: return False
    raw = row['raw'][0]
    if raw['document_uuid'] != identity['uuid'] or raw['path'] != '/system/selectedAmmoId': return False
    local_id = raw.get('value') if raw['present'] else None
    if local_id is not None and type(local_id) is not str: return False
    provenance = row['provenance']
    if provenance['mapping'] != 'pf2e.weapon.selected-ammo.v1' or not provenance['limitations'] or any(not v for v in provenance['limitations']): return False
    if provenance['contributors'] != [{k:raw[k] for k in ('document_uuid','path','basis')}]: return False
    mapped = row['mapped']; value = mapped['value']
    if mapped['concept'] != 'stored_selected_ammunition_reference' or mapped['unit'] is not None or type(value) is not dict: return False
    status = value.get('status')
    if status in ('missing','denied','unsupported','unverified'):
        if set(value) != {'status','target_uuid'} or value['target_uuid'] is not None: return False
        if not local_id: return status == 'missing'
        if identity['actor'] is None: return status == 'unverified'
        return True
    if status != 'resolved' or not local_id or identity['actor'] is None or re.fullmatch(r'[^.\s#]+',local_id) is None: return False
    instance = identity['instance']
    required = {'status','target_uuid','document_name','type','name','name_truncated'} | ({'token_uuid'} if instance is not None else set())
    if set(value) != required or value['target_uuid'] != identity['actor']['uuid'] + '.Item.' + local_id or value['document_name'] != 'Item' or value['type'] not in ('ammo','weapon'): return False
    if type(value['name']) is not str or len(value['name']) > 256 or type(value['name_truncated']) is not bool: return False
    return instance is None or value['token_uuid'] == instance['token_uuid']




# PF2e-specific SpellcastingEntrySystemSource8.6.1 source schema, never computed casting.
# Official template also declares slot11; retain it without invented spell-rank meaning.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts
CASTING_ENTRY_LIMIT = ['source_only_no_castability_or_resource_expenditure','template_slot11_no_spell_rank_semantics']
CASTING_ENTRY_LEAVES = {p:('casting_entry_'+c,k,n) for p,c,k,n in (
 ('tradition/value','tradition_code','string',False),('prepared/value','mode_code','string',False),
 ('prepared/flexible','flexible','boolean',False),('prepared/validItems','valid_items_code','string',True),
 ('ability/value','ability_code','string',False),('proficiency/value','proficiency_rank','number',False),
 ('spelldc/value','spell_attack_source','number',False),('spelldc/dc','spell_dc_source','number',False),
 ('autoHeightenLevel/value','auto_heighten_rank','number',True),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),
 ('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
)}


def _casting_entry_spec(path):
    """PF2e-specific8.6.1 casting entry source paths; indexed preparations keep identity.

    Schema pinned above. slot value/max and each preparation's expended flag remain
    independent authored fields. Legacy object preparations are not array-coerced.
    """
    if not path.startswith('/system/'): return None
    relative=path[len('/system/'):]
    if relative in CASTING_ENTRY_LEAVES: return CASTING_ENTRY_LEAVES[relative]
    if relative == 'traits/otherTags': return ('casting_entry_other_tag_code','array',False)
    if re.fullmatch(r'traits/otherTags/(0|[1-9][0-9]*)',relative): return ('casting_entry_other_tag_code','string',False)
    match=re.fullmatch(r'slots/slot(?:[0-9]|10|11)/(value|max|prepared)(?:/(0|[1-9][0-9]*)/(id|expended))?',relative)
    if match is None: return None
    leaf,index,prepared_leaf=match.groups()
    if index is not None:
        if leaf != 'prepared': return None
        return ('casting_entry_prepared_spell_local_id','string',True) if prepared_leaf == 'id' else ('casting_entry_prepared_expended','boolean',False)
    return ('casting_entry_preparations','array',False) if leaf == 'prepared' else ('casting_entry_slot_'+leaf,'number',False)


def _casting_entry_record(row, identity):
    """PF2e-specific8.6.1 casting entry DTO: exact source, no effective/resource inference."""
    if row['section'] == 'description':
        return len(row['raw']) == 1 and row['raw'][0]['path'] == '/system/description/value' and row['provenance']['mapping'] != 'pf2e.spellcasting-entry.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path']
    if path in ('/name','/type'): return row['provenance']['mapping'] != 'pf2e.spellcasting-entry.source.v1'
    spec=_casting_entry_spec(path)
    if spec is None or raw['document_uuid'] != identity['uuid'] or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.spellcasting-entry.source.v1',limitations=CASTING_ENTRY_LIMIT): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'string':type(value) is str,'boolean':type(value) is bool,'number':type(value) in (int,float) and math.isfinite(value),'array':type(value) is list and not value}[kind]


# PF2e-specific SpellSystemSource8.6.1 primitive schema; no prepared variants.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts
SPELL_LIMIT = ['source_only_no_spell_casting_or_variant_application']
SPELL_LEAVES = {p:('spell_'+c,k,n) for p,c,k,n in (
 ('level/value','base_rank','number',False),('time/value','casting_time_text','string',False),
 ('requirements','requirements_text','string',False),('cost/value','cost_text','string',False),
 ('range/value','range_text','string',False),('target/value','target_text','string',False),
 ('traits/rarity','rarity_code','string',False),('area/type','area_shape_code','string',False),
 ('area/value','area_value','number',False),('area/details','area_details_text','string',False),
 ('duration/value','duration_text','string',False),('duration/sustained','duration_sustained','boolean',False),
 ('defense/passive/statistic','passive_defense_statistic_code','string',False),
 ('defense/save/statistic','save_statistic_code','string',False),('defense/save/basic','save_basic','boolean',False),
 ('counteraction','counteraction','boolean',False),('ritual/primary/check','ritual_primary_check_text','string',False),
 ('ritual/secondary/checks','ritual_secondary_checks_text','string',False),('ritual/secondary/casters','ritual_secondary_casters','number',False),
 ('location/value','casting_entry_local_id','string',True),('location/signature','signature','boolean',False),
 ('location/heightenedLevel','configured_heightened_rank','number',False),('location/autoHeightenLevel','configured_auto_heighten_rank','number',True),
 ('location/uses/value','innate_uses_value','number',False),('location/uses/max','innate_uses_max','number',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
SPELL_CONTAINERS = {p:('spell_'+c,'container',n) for p,c,n in (
 ('level','level',False),('traits','traits',False),('time','time',False),('cost','cost',False),
 ('range','range',False),('target','target',False),('area','area',True),('duration','duration',False),
 ('defense','defense',True),('defense/passive','passive_defense',True),('defense/save','save',True),
 ('ritual','ritual',True),('ritual/primary','ritual_primary',False),('ritual/secondary','ritual_secondary',False),
 ('location','location',False),('location/uses','innate_uses',False),('publication','publication',False),
)}
SPELL_ARRAYS = {p:'spell_'+c for p,c in (('traits/traditions','tradition_code'),('traits/value','trait_code'),('traits/otherTags','other_tag_code'))}
SPELL_DAMAGE = {p:('spell_'+c,k,n) for p,c,k,n in (
 ('formula','damage_formula','string',False),('applyMod','damage_apply_mod','boolean',False),
 ('type','damage_type_code','string',False),('category','damage_category_code','string',True),
)}
SPELL_SEGMENT = r'(?:[^~/]|~[01])*'


def _spell_relative_spec(parts, *, depth=0, overlays=True):
    """PF2e-specific8.6.1 spell schema walk, fixed layers and overlay source only.

    Pinned schema above. Layers retain paths, not document identities; source
    heightening configuration does not calculate a current cast or variant rank.
    JSON Pointer keys preserve escaped slash/tilde and no arbitrary object leaks.
    """
    if depth > 12: return None
    path='/'.join(parts)
    if not path and depth: return ('spell_system_patch','object',False)
    if path in SPELL_LEAVES: return SPELL_LEAVES[path]
    if path in SPELL_CONTAINERS:
        concept,kind,nullable=SPELL_CONTAINERS[path]
        return (concept,'object' if depth else kind,nullable)
    if path == 'description/value': return ('spell_description_text','text',False)
    for base,concept in SPELL_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    if parts and parts[0] == 'damage':
        if len(parts) == 1: return ('spell_damage_components','object',False)
        if re.fullmatch(SPELL_SEGMENT,parts[1]) is None: return None
        if len(parts) == 2: return ('spell_damage_component','object' if depth else 'container',False)
        leaf='/'.join(parts[2:])
        if leaf in SPELL_DAMAGE: return SPELL_DAMAGE[leaf]
        for key,concept in [('kinds','spell_damage_kind_code'),('materials','spell_damage_material_code')]:
            if leaf == key: return (concept,'array',False)
            if re.fullmatch(key+r'/(0|[1-9][0-9]*)',leaf): return (concept,'string',False)
    if parts and parts[0] == 'heightening':
        if len(parts) == 1: return ('spell_heightening','object' if depth else 'absent',False)
        direct={'type':('spell_heightening_type','heightening',False),'interval':('spell_heightening_interval','number',False),'area':('spell_heightening_area_increment','number',False),'damage':('spell_heightening_damage','object',False),'levels':('spell_fixed_heightening_levels','object',False)}
        if len(parts) == 2: return direct.get(parts[1])
        if len(parts) == 3 and parts[1] == 'damage' and re.fullmatch(SPELL_SEGMENT,parts[2]) is not None: return ('spell_heightening_damage_formula','string',False)
        if len(parts) >= 3 and parts[1] == 'levels' and re.fullmatch(r'[1-9]|10',parts[2]): return _spell_relative_spec(parts[3:],depth=depth+1,overlays=overlays)
    if overlays and parts and parts[0] == 'overlays':
        if len(parts) == 1: return ('spell_overlays','object',False)
        if len(parts) < 3 or re.fullmatch(SPELL_SEGMENT,parts[1]) is None: return None
        if len(parts) == 3 and parts[2] == 'system': return ('spell_system_patch','object',False)
        if len(parts) == 3:
            return {'name':('spell_overlay_name','string',False),'overlayType':('spell_overlay_type','string',False),'sort':('spell_overlay_sort','number',False)}.get(parts[2])
        if parts[2] == 'system': return _spell_relative_spec(parts[3:],depth=depth+1,overlays=False)
    return None


def _spell_spec(path):
    """PF2e-specific8.6.1 spell selected paths; prepared cast/effective fields excluded."""
    if not path.startswith('/system/'): return None
    return _spell_relative_spec(path[len('/system/'):].split('/'))


def _spell_record(row, identity):
    """PF2e-specific8.6.1 strict spell source, description and local assignment DTO.

    Schema pinned above. Base rank, configured ranks and exact prose remain source;
    neither overlays nor fixed/interval heightening are applied to an actor's cast.
    """
    if row['section'] == 'relationships': return _spell_entry_relationship(row,identity)
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_spell_spec(path)
    if path in ('/name','/type'): return row['section'] == 'source' and row['provenance']['mapping'] != 'pf2e.spell.source.v1'
    if spec is None or raw['document_uuid'] != identity['uuid']: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.spell.source.v1',limitations=SPELL_LIMIT): return False
    if kind == 'text':
        return row['section'] == 'description' and row['kind'] == ('text' if raw['present'] else 'field') and row['mapped'] == dict(concept=concept,value=None,unit=None) and (not raw['present'] or type(value) is str)
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'string':type(value) is str,'number':type(value) in (int,float) and math.isfinite(value),
            'boolean':type(value) is bool,'array':type(value) is list and not value,
            'object':type(value) is dict and not value,'container':False,'absent':False,
            'heightening':type(value) is str and value in ('interval','fixed')}[kind]

def _spell_entry_relationship(row, identity):
    """PF2e-specific SpellSystemSource.location.value8.6.1 stored local assignment.

    Schema: https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts
    Resolution names the actual owner-local casting entry only; no cast rank,
    resource availability, prepared spell or castability is inferred.
    """
    if row['section'] != 'relationships' or row['kind'] != 'relationship' or row['key'] != 'relationships:spell:location': return False
    if len(row['raw']) != 1: return False
    raw=row['raw'][0]
    if raw['document_uuid'] != identity['uuid'] or raw['path'] != '/system/location/value': return False
    local_id=raw.get('value') if raw['present'] else None
    if local_id is not None and type(local_id) is not str: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.spell.casting-entry.v1',limitations=['stored_assignment_not_castability']): return False
    mapped=row['mapped'];value=mapped['value']
    if mapped['concept'] != 'stored_spellcasting_entry_reference' or mapped['unit'] is not None or type(value) is not dict: return False
    status=value.get('status')
    if status in ('missing','denied','unsupported','unverified'):
        if set(value) != {'status','target_uuid'} or value['target_uuid'] is not None: return False
        if not local_id: return status == 'missing'
        if identity['actor'] is None: return status == 'unverified'
        return True
    if status != 'resolved' or not local_id or identity['actor'] is None or re.fullmatch(r'[^.\s#]+',local_id) is None: return False
    instance=identity['instance']
    required={'status','target_uuid','document_name','type','name','name_truncated'} | ({'token_uuid'} if instance is not None else set())
    if set(value) != required or value['target_uuid'] != identity['actor']['uuid']+'.Item.'+local_id or value['document_name'] != 'Item' or value['type'] != 'spellcastingEntry': return False
    if type(value['name']) is not str or len(value['name']) > 256 or type(value['name_truncated']) is not bool: return False
    return instance is None or value['token_uuid'] == instance['token_uuid']

def _weapon_record(row, identity):
    """PF2e-specific weapon8.6.1 strict source DTO, alongside shared physical fields.

    Each new weapon leaf requires exact mapping/concept/source provenance. Shared
    physical descriptors retain their existing contract; no mapping may cross the
    path scopes. Description behavior remains the existing explicit text reader.
    """
    if len(row['raw']) != 1: return False
    if row['section'] == 'relationships': return _weapon_ammunition_relationship(row,identity)
    raw = row['raw'][0]; path = raw['path']; spec = _weapon_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.weapon.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:' + path: return False
    concept, kind, nullable = spec; value = raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}], mapping='pf2e.weapon.source.v1', limitations=['source_only_no_effective_strike_calculation']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'string':type(value) is str, 'number':type(value) in (int,float) and math.isfinite(value),
            'boolean':type(value) is bool, 'null':False, 'array':type(value) is list and not value,
            'object':type(value) is dict and not value}[kind]


# PF2e-specific AmmoSystemSource8.6.1 authored leaves; no consumption state.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ammo/data.ts
AMMO_SOURCE = {'/system/'+p:('ammo_'+c,k,n) for p,c,k,n in (
 ('uses/value','uses_value','number',False),('uses/max','uses_max','number',False),
 ('uses/autoDestroy','auto_destroy','boolean',False),('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
AMMO_ARRAYS = {'/system/'+p:'ammo_'+c for p,c in (
 ('craftableAs','craftable_as_code'),('traits/value','trait_code'),('traits/otherTags','other_tag_code'))}


def _ammo_spec(path):
    """PF2e-specific ammo8.6.1 source schema above; arrays retain exact codes.

    craftableAs null is distinct from absent/empty; no compatibility is inferred.
    """
    if path in AMMO_SOURCE: return AMMO_SOURCE[path]
    for base,concept in AMMO_ARRAYS.items():
        if path == base: return (concept,'array',base == '/system/craftableAs')
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _ammo_record(row,identity):
    """PF2e-specific ammo8.6.1 strict selected source and physical separation.

    Schema pinned above; uses remain authored, not remaining shots/compatibility.
    Shared physical paths retain their mapping; no reverse weapon search occurs.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_ammo_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.ammo.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.ammo.source.v1',limitations=['source_only_no_ammunition_consumption_or_compatibility']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value}[kind]


# PF2e-specific EquipmentSystemSource8.6.1 authored metadata; no benefit activation state.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/equipment/data.ts
EQUIPMENT_SOURCE = {'/system/'+p:('equipment_'+c,k,n) for p,c,k,n in (
 ('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
EQUIPMENT_ARRAYS = {'/system/'+p:'equipment_'+c for p,c in (
 ('traits/value','trait_code'),('traits/otherTags','other_tag_code'))}


def _equipment_spec(path):
    """PF2e-specific equipment8.6.1 source schema above; arrays retain exact codes.

    No activation structure or effective carried benefits are inferred.
    """
    if path in EQUIPMENT_SOURCE: return EQUIPMENT_SOURCE[path]
    for base,concept in EQUIPMENT_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _equipment_record(row,identity):
    """PF2e-specific equipment8.6.1 strict selected source and physical separation.

    Schema pinned above; traits remain authored, not active benefit calculations.
    Shared physical usage, investment and attachment paths retain their mapping.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_equipment_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.equipment.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.equipment.source.v1',limitations=['source_only_no_equipment_benefit_application']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value}[kind]


# PF2e-specific BookSystemSource8.6.1 authored metadata; no effective ownership or preparation.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts
BOOK_SOURCE = {'/system/'+p:('book_'+c,k,n) for p,c,k,n in (
 ('category','category_code','string',False),('capacity','capacity','number',False),
 ('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
BOOK_ARRAYS = {'/system/'+p:'book_'+c for p,c in (
 ('traits/value','trait_code'),('traits/otherTags','other_tag_code'),('contents','content_uuid'))}


def _book_spec(path):
    """PF2e-specific book8.6.1 source schema above; arrays retain exact codes.

    No Item ownership, preparation, capacity usage or effective access is inferred.
    """
    if path in BOOK_SOURCE: return BOOK_SOURCE[path]
    for base,concept in BOOK_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _book_relationship(row, identity):
    """PF2e-specific BookSystemSource8.6.1 immediate contents UUID claim boundary.

    Pinned book schema above; resolved definitions establish no ownership or
    preparation. Duplicate references retain their original indexed source path.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship':return False
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if len(raw)!=1 or type(raw[0]) is not dict:return False
    r=raw[0]
    if not {'document_uuid','path','present','basis'}<=set(r) or not set(r)<={'document_uuid','path','present','basis','value'}:return False
    if r['document_uuid']!=identity['uuid'] or r['basis']!='source' or type(r['present']) is not bool or r['present']!=('value' in r):return False
    if provenance!=dict(contributors=[{k:r[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.book.content-reference.v1',limitations=['stored_book_contents_not_ownership_or_preparation']):return False
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='book_content_reference' or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if r['path']=='/system/contents':
        return row['key']=='relationships:book:contents' and ((not r['present'] and value==dict(status='missing',target_uuid=None)) or (r['present'] and type(r['value']) is list and r['value']==[] and value==dict(status='empty',target_uuid=None)))
    match=re.fullmatch(r'/system/contents/(0|[1-9][0-9]*)',r['path']) if type(r['path']) is str else None
    if not match or row['key']!='relationships:book:contents:'+match[1] or not r['present'] or type(r['value']) is not str:return False
    if value.get('status')!='resolved':return value in [dict(status=s,target_uuid=None) for s in ('missing','denied','unsupported','unverified')]
    keys={'status','target_uuid','document_name','type','name','name_truncated'}
    synthetic=re.fullmatch(r'Scene\.[^.\s#]+\.Token\.[^.\s#]+\.Actor\.[^.\s#]+\.Item\.[^.\s#]+',r['value'])
    if synthetic:keys.add('token_uuid')
    return (set(value)==keys and value['target_uuid']==r['value'] and _effect_reference_uuid(value['target_uuid'],'Item') and value['document_name']=='Item' and type(value['type']) is str and value['type'] in ITEM_TYPES-{'affliction'} and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(r['value'].split('.')[:4])))


def _book_record(row,identity):
    """PF2e-specific book8.6.1 strict selected source and physical separation.

    Schema pinned above; contents and category remain authored, not owned or prepared.
    Shared physical quantity, price.per and coin values retain their mapping.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_book_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.book.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.book.source.v1',limitations=['source_only_no_book_ownership_or_preparation']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value}[kind]


# PF2e-specific AncestrySystemSchema8.6.1 and ABCFeatureEntryField; source definitions only.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ancestry/data.ts
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts
ANCESTRY_SOURCE={'/system/'+p:('ancestry_'+c,k,n) for p,c,k,n in (
 ('boosts','boost_slots','object',False),('flaws','flaw_slots','object',False),('items','feature_entries','object',False),
 ('hp','hp_contribution','number',False),('size','size_code','string',False),('speed','base_speed','number',False),
 ('hands','hands','number',False),('reach','reach','number',False),('vision','vision_code','string',False),
 ('languages/custom','language_custom','string',False),('additionalLanguages/count','additional_language_count','number',False),
 ('additionalLanguages/custom','additional_language_custom','string',False),
 ('voluntary/legacy','voluntary_legacy','boolean',False),('voluntary/boost','voluntary_boost_code','string',True),
 ('traits/rarity','rarity_code','string',False),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),
 ('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
)}
ANCESTRY_ARRAYS={'/system/'+p:'ancestry_'+c for p,c in (
 ('traits/value','trait_code'),('traits/otherTags','other_tag_code'),('languages/value','language_code'),
 ('additionalLanguages/value','additional_language_code'),('alternateAncestryBoosts','alternate_boost_code'),
 ('voluntary/flaws','voluntary_flaw_code'))}


def _ancestry_spec(path):
    """PF2e-specific pinned ancestry source paths, escaped slot/feature keys.

    Authored boosts, flaws and ABC definitions establish no character acquisition
    or effective ability score, languages, HP, speed or senses.
    """
    if path in ANCESTRY_SOURCE:return ANCESTRY_SOURCE[path]
    for base,concept in ANCESTRY_ARRAYS.items():
        if path==base:return concept,'array',base=='/system/alternateAncestryBoosts'
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path):return concept,'string',False
    match=re.fullmatch(r'/system/(boosts|flaws|items)/([^/]+)/(.*)',path)
    if not match or re.search(r'~(?![01])',match[2]):return None
    group,_,leaf=match.groups()
    if group=='items':
        spec={'uuid':('feature_uuid','string',False),'img':('feature_image','string',False),
              'name':('feature_name','string',False),'level':('feature_level','nonnegative_integer',False)}.get(leaf)
        return ('ancestry_'+spec[0],*spec[1:]) if spec else None
    prefix='ancestry_'+('boost' if group=='boosts' else 'flaw')
    if leaf=='selected':return prefix+'_selected_code','string',True
    if leaf=='value':return prefix+'_offer_code','array',False
    if re.fullmatch(r'value/(0|[1-9][0-9]*)',leaf):return prefix+'_offer_code','string',False
    return None


def _ancestry_record(row,identity):
    """PF2e-specific ancestry8.6.1 exact source DTO; no effective character math.

    Pinned schema above. No physical, level or acquired feature fields admitted.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];spec=_ancestry_spec(path)
    if path in SOURCE_PATHS:return row['provenance']['mapping']!='pf2e.ancestry.source.v1'
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    if raw['document_uuid']!=identity['uuid']:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.ancestry.source.v1',limitations=['ancestry_source_not_effective_character']):return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):return False
    if not raw['present']:return True
    if value is None:return nullable
    return {'string':type(value) is str,'boolean':type(value) is bool,
            'number':type(value) in (int,float) and math.isfinite(value),
            'nonnegative_integer':type(value) in (int,float) and math.isfinite(value) and value%1==0 and value>=0,
            'array':type(value) is list and not value,'object':type(value) is dict and not value}[kind]


def _ancestry_relationship(row,identity):
    """PF2e-specific ancestry8.6.1 immediate ABC feature UUID definition claims.

    Pinned schemas above. Resolution establishes no acquired character feature.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='source' or type(raw['present']) is not bool or raw['present']!=('value'in raw):return False
    path=raw['path']
    if type(path) is not str or row['key']!='relationships:ancestry:'+path:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.ancestry.feature-reference.v1',limitations=['definition_reference_not_acquired_feature']):return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='ancestry_feature_reference' or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if path=='/system/items':return (not raw['present'] and value==dict(status='missing',target_uuid=None)) or (raw['present'] and type(raw['value']) is dict and not raw['value'] and value==dict(status='empty',target_uuid=None))
    spec=_ancestry_spec(path)
    if spec is None or spec[0]!='ancestry_feature_uuid':return False
    if not raw['present']:return value==dict(status='missing',target_uuid=None)
    if type(raw['value']) is not str:return False
    if value.get('status')!='resolved':return value in [dict(status=status,target_uuid=None) for status in ('missing','denied','unsupported','unverified')]
    keys={'status','target_uuid','document_name','type','name','name_truncated'}
    synthetic=re.fullmatch(r'Scene\.[^.\s#]+\.Token\.[^.\s#]+\.Actor\.[^.\s#]+\.Item\.[^.\s#]+',raw['value'])
    if synthetic:keys.add('token_uuid')
    return (set(value)==keys and value['target_uuid']==raw['value'] and _effect_reference_uuid(value['target_uuid'],'Item') and value['document_name']=='Item' and type(value['type']) is str and value['type'] in ITEM_TYPES-{'affliction'} and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(raw['value'].split('.')[:4])))


# PF2e-specific HeritageSystemSchema8.6.1; authored association, never ownership.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/heritage/data.ts
HERITAGE_SOURCE={'/system/'+p:('heritage_'+c,k,n) for p,c,k,n in (
 ('ancestry','ancestry_association','null',True),
 ('ancestry/name','ancestry_name','string',False),('ancestry/slug','ancestry_slug','string',False),
 ('ancestry/uuid','ancestry_uuid','string',False),('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
HERITAGE_ARRAYS={'/system/traits/value':'heritage_trait_code','/system/traits/otherTags':'heritage_other_tag_code'}


def _heritage_spec(path):
    """PF2e-specific heritage8.6.1 source schema above; no effective benefits.

    Nullable ancestry association and authored name/slug/uuid are independent of
    the actual owner's acquired ancestry. Nonphysical Items admit no stock fields.
    """
    if path in HERITAGE_SOURCE:return HERITAGE_SOURCE[path]
    for base,concept in HERITAGE_ARRAYS.items():
        if path==base:return concept,'array',False
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path):return concept,'string',False
    return None


def _heritage_record(row,identity):
    """PF2e-specific heritage8.6.1 exact source DTO; pinned schema above.

    Authored association fields never establish exclusivity or current membership.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];spec=_heritage_spec(path)
    if path in SOURCE_PATHS:return row['provenance']['mapping']!='pf2e.heritage.source.v1'
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    if raw['document_uuid']!=identity['uuid']:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.heritage.source.v1',limitations=['heritage_source_not_effective_character']):return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):return False
    if not raw['present']:return True
    if value is None:return nullable
    return {'null':False,'string':type(value) is str,'boolean':type(value) is bool,'array':type(value) is list and not value}[kind]


def _heritage_relationship(row,identity):
    """PF2e-specific heritage8.6.1 ancestry association; schema pinned above.

    Immediate canonical ancestry Item identity is distinct from owner membership;
    unresolved outcomes contain no target identity or prepared ancestry state.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship' or len(row['raw'])!=1 or row['key']!='relationships:heritage:ancestry':return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='source' or type(raw['present']) is not bool or raw['present']!=('value'in raw):return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.heritage.ancestry-reference.v1',limitations=['ancestry_association_not_owner_membership']):return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='heritage_ancestry_reference' or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if raw['path']=='/system/ancestry':return value==dict(status='missing',target_uuid=None) if not raw['present'] else raw['value'] is None and value==dict(status='unassociated',target_uuid=None)
    if raw['path']!='/system/ancestry/uuid':return False
    if not raw['present']:return value==dict(status='missing',target_uuid=None)
    claim=raw['value']
    if type(claim) is not str:return False
    if not _effect_reference_uuid(claim,'Item'):return value==dict(status='unsupported',target_uuid=None)
    if value.get('status')!='resolved':return value in [dict(status=status,target_uuid=None) for status in ('missing','denied','unsupported','unverified')]
    keys={'status','target_uuid','document_name','type','name','name_truncated'}
    synthetic=claim.startswith('Scene.')
    if synthetic:keys.add('token_uuid')
    return (set(value)==keys and value['target_uuid']==claim and value['document_name']=='Item' and value['type']=='ancestry' and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(claim.split('.')[:4])))


# PF2e-specific BackgroundSystemSchema8.6.1 and ABCFeatureEntryField; source definitions only.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/background/data.ts
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abc/data.ts
BACKGROUND_SOURCE={'/system/'+p:('background_'+c,k,n) for p,c,k,n in (
 ('boosts','boost_slots','object',False),('items','feature_entries','object',False),
 ('traits/rarity','rarity_code','string',False),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),
 ('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
)}
BACKGROUND_ARRAYS={'/system/'+p:'background_'+c for p,c in (
 ('traits/value','trait_code'),('traits/otherTags','other_tag_code'),
 ('trainedSkills/value','trained_skill_code'),('trainedSkills/lore','lore'))}


def _background_spec(path):
    """PF2e-specific BackgroundSystemSchema8.6.1 paths, escaped slot/feature keys.

    Authored boosts, trainedSkills.value/lore and ABC definitions establish no
    character acquisition or effective ability scores, training or skill totals.
    """
    if path in BACKGROUND_SOURCE:return BACKGROUND_SOURCE[path]
    for base,concept in BACKGROUND_ARRAYS.items():
        if path==base:return concept,'array',False
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path):return concept,'string',False
    match=re.fullmatch(r'/system/(boosts|items)/([^/]+)/(.*)',path)
    if not match or re.search(r'~(?![01])',match[2]):return None
    group,_,leaf=match.groups()
    if group=='items':
        spec={'uuid':('feature_uuid','string',False),'img':('feature_image','string',False),
              'name':('feature_name','string',False),'level':('feature_level','nonnegative_integer',False)}.get(leaf)
        return ('background_'+spec[0],*spec[1:]) if spec else None
    prefix='background_boost'
    if leaf=='selected':return prefix+'_selected_code','string',True
    if leaf=='value':return prefix+'_offer_code','array',False
    if re.fullmatch(r'value/(0|[1-9][0-9]*)',leaf):return prefix+'_offer_code','string',False
    return None


def _background_record(row,identity):
    """PF2e-specific background8.6.1 exact source DTO; no effective character math.

    Pinned background/data.ts and abc/data.ts links above establish source-only
    contracts. No physical, character level or acquired feature fields admitted.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];spec=_background_spec(path)
    if path in SOURCE_PATHS:return row['provenance']['mapping']!='pf2e.background.source.v1'
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    if raw['document_uuid']!=identity['uuid']:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.background.source.v1',limitations=['background_source_not_effective_character']):return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):return False
    if not raw['present']:return True
    if value is None:return nullable
    return {'string':type(value) is str,'boolean':type(value) is bool,
            'number':type(value) in (int,float) and math.isfinite(value),
            'nonnegative_integer':type(value) in (int,float) and math.isfinite(value) and value%1==0 and value>=0,
            'array':type(value) is list and not value,'object':type(value) is dict and not value}[kind]


def _background_relationship(row,identity):
    """PF2e-specific background8.6.1 immediate ABC feature UUID definition claims.

    Pinned schemas above. Resolution establishes no acquired character feature.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='source' or type(raw['present']) is not bool or raw['present']!=('value'in raw):return False
    path=raw['path']
    if type(path) is not str or row['key']!='relationships:background:'+path:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.background.feature-reference.v1',limitations=['definition_reference_not_acquired_feature']):return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='background_feature_reference' or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if path=='/system/items':return (not raw['present'] and value==dict(status='missing',target_uuid=None)) or (raw['present'] and type(raw['value']) is dict and not raw['value'] and value==dict(status='empty',target_uuid=None))
    spec=_background_spec(path)
    if spec is None or spec[0]!='background_feature_uuid':return False
    if not raw['present']:return value==dict(status='missing',target_uuid=None)
    if type(raw['value']) is not str:return False
    if value.get('status')!='resolved':return value in [dict(status=status,target_uuid=None) for status in ('missing','denied','unsupported','unverified')]
    keys={'status','target_uuid','document_name','type','name','name_truncated'}
    synthetic=re.fullmatch(r'Scene\.[^.\s#]+\.Token\.[^.\s#]+\.Actor\.[^.\s#]+\.Item\.[^.\s#]+',raw['value'])
    if synthetic:keys.add('token_uuid')
    return (set(value)==keys and value['target_uuid']==raw['value'] and _effect_reference_uuid(value['target_uuid'],'Item') and value['document_name']=='Item' and type(value['type']) is str and value['type'] in ITEM_TYPES-{'affliction'} and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(raw['value'].split('.')[:4])))


# PF2e-specific feat8.6.1 source contract, never effective benefits.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts
# Same revision item/feat/values.ts and item/ability/{data.ts,trait-toggles.ts}.
FEAT_SOURCE={'/system/'+p:('feat_'+c,k,n) for p,c,k,n in (
 ('category','category_code','string',False),('level/value','nominal_level','level',False),
 ('level/taken','taken_level','level',True),('onlyLevel1','only_level_one','boolean',False),
 ('maxTakable','maximum_takable','positive_integer',True),('actionType/value','activation_kind','string',False),
 ('actions/value','action_count','actions',True),('location','location','string',True),
 ('frequency','frequency_source','null',True),('frequency/value','recorded_frequency_remaining','nonnegative_integer',False),
 ('frequency/max','frequency_maximum','positive_integer',False),('frequency/per','frequency_interval_code','string',False),
 ('traits/rarity','rarity_code','string',False),('traits/toggles','trait_toggles','absent',False),
 ('traits/toggles/mindshift','mindshift_toggle','null',True),('traits/toggles/mindshift/selected','mindshift_selected','boolean',False),
 ('subfeatures/languages','language_options','absent',False),('subfeatures/languages/slots','language_slots','nonnegative_integer',False),
 ('subfeatures/proficiencies','proficiency_entries','object',False),('subfeatures/senses','sense_entries','object',False),
 ('selfEffect','self_effect_source','null',True),('selfEffect/uuid','self_effect_uuid','string',False),
 ('selfEffect/name','self_effect_name','string',False),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),
 ('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
)}
FEAT_ARRAYS={'/system/'+p:'feat_'+c for p,c in (
 ('prerequisites/value','prerequisite_entries'),('traits/value','trait_code'),('traits/otherTags','other_tag_code'),
 ('subfeatures/keyOptions','key_option_code'),('subfeatures/languages/granted','granted_language_code'),
 ('subfeatures/suppressedFeatures','suppressed_feature_uuid'))}


def _feat_spec(path):
    """PF2e-specific feat8.6.1 pinned source paths; no effective benefit math.

    Opaque subfeature keys retain escaped source provenance, never document IDs.
    """
    if path=='/flags/pf2e/rulesSelections':return 'feat_selection_entries','object',False
    match=re.fullmatch(r'/flags/pf2e/rulesSelections/([^/]*)',path)
    if match and re.search(r'~(?![01])',match[1]) is None:return 'feat_recorded_selection','selection',False
    if path=='/flags/pf2e/itemGrants':return 'feat_grant_entries','object',False
    if path=='/flags/pf2e/grantedBy':return 'feat_granted_by_source','null',True
    match=re.fullmatch(r'/flags/pf2e/itemGrants/([^/]*)/(id|onDelete|nested)',path)
    if match:
        if re.search(r'~(?![01])',match[1]):return None
        return {'id':('feat_grant_item_id','string',False),'onDelete':('feat_grant_delete_policy','string',False),'nested':('feat_grant_nested','boolean',True)}[match[2]]
    if path=='/flags/pf2e/grantedBy/id':return 'feat_granted_by_item_id','string',False
    if path=='/flags/pf2e/grantedBy/onDelete':return 'feat_granted_by_delete_policy','string',False
    if path in FEAT_SOURCE:return FEAT_SOURCE[path]
    for base,concept in FEAT_ARRAYS.items():
        if path==base:return concept,'array',False
        suffix=r'/(0|[1-9][0-9]*)'+('/value' if base=='/system/prerequisites/value' else '')
        if re.fullmatch(re.escape(base)+suffix,path):return ('feat_prerequisite_text' if base=='/system/prerequisites/value' else concept),'string',False
    match=re.fullmatch(r'/system/subfeatures/(proficiencies|senses)/([^/]+)(?:/(rank|attribute|acuity|range|special(?:/(?:ancestry|llv|second))?))?',path)
    if not match or re.search(r'~(?![01])',match[2]):return None
    group,_,leaf=match.groups()
    if leaf is None:return ('feat_proficiency_entries' if group=='proficiencies' else 'feat_sense_entries'),'absent',False
    if group=='proficiencies':return {'rank':('feat_proficiency_rank','rank',False),'attribute':('feat_proficiency_attribute_code','string',True)}.get(leaf)
    return {'acuity':('feat_sense_acuity_code','string',False),'range':('feat_sense_range','range',True),'special':('feat_sense_special','absent',False),**{'special/'+k:('feat_sense_special_'+k,'boolean',False) for k in ('ancestry','llv','second')}}.get(leaf)


def _feat_record(row,identity):
    """PF2e-specific feat8.6.1 exact source DTO; pinned schema above.

    Category alone maps to {code,kind}; activation codes, proficiency ranks and
    every other source value remain unchanged. No eligibility or effective value.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];spec=_feat_spec(path)
    if path in SOURCE_PATHS:return row['provenance']['mapping']!='pf2e.feat.source.v1'
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    if raw['document_uuid']!=identity['uuid']:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.feat.source.v1',limitations=['feat_source_not_effective_benefit']):return False
    concept,kind,nullable=spec;value=raw.get('value');expected=value
    if path=='/system/category' and raw['present']:
        expected=dict(code=value,kind='feature' if value in ('ancestryfeature','calling','classfeature','curse','deityboon','pfsboon') else 'feat' if value in ('ancestry','bonus','class','general','skill') else 'unknown')
    if row['mapped']!=dict(concept=concept,value=expected,unit=None) or type(row['mapped']['value']) is not type(expected):return False
    if not raw['present']:return True
    if value is None:return nullable
    numeric=type(value) in (int,float) and math.isfinite(value)
    integer=numeric and value%1==0
    return {'null':False,'absent':False,'string':type(value) is str,'boolean':type(value) is bool,
            'level':integer and 1<=value<=30,'actions':integer and 1<=value<=3,
            'rank':integer and 1<=value<=4,'range':numeric and 5<=value<=300,
            'positive_integer':integer and value>=1,'nonnegative_integer':integer and value>=0,
            'selection':type(value) is str or numeric,
            'array':type(value) is list and not value,'object':type(value) is dict and not value}[kind]


def _feat_relationship(row, identity):
    """PF2e-specific feat8.6.1 persisted grants/selfEffect/suppressedFeatures.

    Pinned feat/data.ts and item/base/data/system.ts at revision
    28d9d156f252d084371d994dc359509b49eadf18 define source claims.
    Local grant IDs resolve only within the actual Actor owner; UUID claims
    retain exact identity. Resolution establishes no acquisition or active benefit.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='source' or type(raw['present']) is not bool or raw['present']!=('value'in raw):return False
    path=raw['path']
    if type(path) is not str or row['key']!='relationships:feat:'+path:return False
    local=False;marker=False
    if path=='/flags/pf2e/itemGrants':concept='feat_grant_reference';marker=True;empty={}
    elif re.fullmatch(r'/flags/pf2e/itemGrants/([^/]*)/id',path):
        key=path.split('/')[4]
        if re.search(r'~(?![01])',key):return False
        concept='feat_grant_reference';local=True
    elif path in ('/flags/pf2e/grantedBy','/flags/pf2e/grantedBy/id'):
        concept='feat_granted_by_reference';marker=path.endswith('/grantedBy');empty=None;local=not marker
    elif path in ('/system/selfEffect','/system/selfEffect/uuid'):
        concept='feat_self_effect_reference';marker=path.endswith('/selfEffect');empty=None
    elif re.fullmatch(r'/system/subfeatures/suppressedFeatures(?:/(0|[1-9][0-9]*))?',path):
        concept='feat_suppressed_feature_reference';marker=path=='/system/subfeatures/suppressedFeatures';empty=[]
    else:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.feat.reference.v1',limitations=['persisted_reference_not_active_benefit']):return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!=concept or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if not raw['present']:return value==dict(status='missing',target_uuid=None)
    claim=raw['value']
    if marker:
        if type(claim) is not type(empty) or claim!=empty:return False
        return value==dict(status='unassociated' if empty is None else 'empty',target_uuid=None)
    if type(claim) is not str:return False
    valid_claim=(len(claim)<=512 and re.fullmatch(r'[^.\s/#]+',claim) is not None) if local else _effect_reference_uuid(claim,'Item')
    if not valid_claim:return value==dict(status='unsupported',target_uuid=None)
    owner=identity['actor']
    if local and owner is None:return value==dict(status='unowned',target_uuid=None)
    if value.get('status')!='resolved':return value in [dict(status=status,target_uuid=None) for status in ('missing','denied','unsupported','unverified')]
    if local:
        if re.fullmatch(r'[^.\s#]+',claim) is None:return False
        target=owner['uuid']+'.Item.'+claim
    else:target=claim
    if not _effect_reference_uuid(target,'Item'):return False
    synthetic=re.fullmatch(r'Scene\.[^.\s#]+\.Token\.[^.\s#]+\.Actor\.[^.\s#]+\.Item\.[^.\s#]+',target)
    keys={'status','target_uuid','document_name','type','name','name_truncated'}|({'token_uuid'} if synthetic else set())
    if set(value)!=keys or value['target_uuid']!=target or value['document_name']!='Item' or type(value['type']) is not str or value['type'] not in ITEM_TYPES-{'affliction'}:return False
    if concept=='feat_self_effect_reference' and value['type']!='effect' or concept=='feat_suppressed_feature_reference' and value['type']!='feat':return False
    return type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(target.split('.')[:4]))


# PF2e-specific DeitySystemSchema8.6.1; authored options, no active benefits.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/deity/data.ts
DEITY_SOURCE={'/system/'+p:('deity_'+c,k,n) for p,c,k,n in (
 ('category','category_code','string',False),('sanctification','sanctification','null',True),
 ('sanctification/modal','sanctification_modal_code','string',False),
 ('spells','spell_entries','object',False),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),
 ('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
)}
DEITY_ARRAYS={'/system/'+p:'deity_'+c for p,c in (
 ('sanctification/what','sanctification_what_code'),('domains/primary','primary_domain_code'),
 ('domains/alternate','alternate_domain_code'),('font','font_code'),('attribute','attribute_code'),
 ('skill','skill_code'),('weapons','weapon_code'),('traits/otherTags','other_tag_code'))}


def _deity_spec(path):
    """PF2e-specific deity8.6.1 source paths; pinned schema above.

    Nullable skill and sanctification and listed options are source definitions,
    never learned spells, owned weapons or active devotee benefits.
    """
    if path in DEITY_SOURCE:return DEITY_SOURCE[path]
    for base,concept in DEITY_ARRAYS.items():
        if path==base:return concept,'array',base=='/system/skill'
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path):return concept,'string',False
    match=re.fullmatch(r'/system/spells/([^/]+)',path)
    if match and not re.search(r'~(?![01])',match[1]):return 'deity_spell_uuid','string',False
    return None


def _deity_record(row,identity):
    """PF2e-specific deity8.6.1 exact source DTO; no effective character math.

    Pinned deity/data.ts link above establishes source-only
    contracts. No physical, character level or acquired feature fields admitted.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];spec=_deity_spec(path)
    if path in SOURCE_PATHS:return row['provenance']['mapping']!='pf2e.deity.source.v1'
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    if raw['document_uuid']!=identity['uuid']:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.deity.source.v1',limitations=['deity_options_not_active_benefits']):return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):return False
    if not raw['present']:return True
    if value is None:return nullable
    return {'null':False,'string':type(value) is str,'boolean':type(value) is bool,
            'number':type(value) in (int,float) and math.isfinite(value),
            'nonnegative_integer':type(value) in (int,float) and math.isfinite(value) and value%1==0 and value>=0,
            'array':type(value) is list and not value,'object':type(value) is dict and not value}[kind]


def _deity_relationship(row,identity):
    """PF2e-specific deity8.6.1 immediate listed spell UUID claims.

    Pinned schemas above. Resolution establishes no acquired character feature.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='source' or type(raw['present']) is not bool or raw['present']!=('value'in raw):return False
    path=raw['path']
    if type(path) is not str or row['key']!='relationships:deity:'+path:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.deity.spell-reference.v1',limitations=['listed_spell_not_learned_or_prepared']):return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='deity_spell_reference' or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if path=='/system/spells':return (not raw['present'] and value==dict(status='missing',target_uuid=None)) or (raw['present'] and type(raw['value']) is dict and not raw['value'] and value==dict(status='empty',target_uuid=None))
    spec=_deity_spec(path)
    if spec is None or spec[0]!='deity_spell_uuid':return False
    if not raw['present']:return value==dict(status='missing',target_uuid=None)
    if type(raw['value']) is not str:return False
    if value.get('status')!='resolved':return value in [dict(status=status,target_uuid=None) for status in ('missing','denied','unsupported','unverified')]
    keys={'status','target_uuid','document_name','type','name','name_truncated'}
    synthetic=re.fullmatch(r'Scene\.[^.\s#]+\.Token\.[^.\s#]+\.Actor\.[^.\s#]+\.Item\.[^.\s#]+',raw['value'])
    if synthetic:keys.add('token_uuid')
    return (set(value)==keys and value['target_uuid']==raw['value'] and _effect_reference_uuid(value['target_uuid'],'Item') and value['document_name']=='Item' and value['type']=='spell' and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(raw['value'].split('.')[:4])))


# PF2e-specific ClassSystemSchema8.6.1; definition contributions, not character totals.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/class/data.ts
# Same revision: src/module/model.ts (ranks), src/module/item/abc/data.ts (features).
CLASS_SOURCE={'/system/'+p:('class_'+c,k,n) for p,c,k,n in (
 ('keyAbility/selected','key_attribute_selected_code','string',True),
 ('hp','hp_contribution','hp',False),('attacks/other/name','other_attack_name','string',False),
 ('trainedSkills/additional','additional_trained_skills','nonnegative_integer',False),
 ('items','feature_entries','object',False),('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
 ('perception','starting_perception_rank','rank',False),('spellcasting','starting_spellcasting_rank','rank',False),
 *((f'savingThrows/{n}',f'starting_{n}_rank','rank',False) for n in ('fortitude','reflex','will')),
 *((f'attacks/{n}',f'starting_{n}_attack_rank','rank',False) for n in ('simple','martial','advanced','unarmed')),
 ('attacks/other/rank','starting_other_attack_rank','rank',False),
 *((f'defenses/{n}',f'starting_{n}_defense_rank','rank',False) for n in ('unarmored','light','medium','heavy')),
)}
CLASS_ARRAYS={'/system/'+p:('class_'+c,k) for p,c,k in (
 ('keyAbility/value','key_attribute_offer_code','string'),('trainedSkills/value','trained_skill_code','string'),
 ('traits/otherTags','other_tag_code','string'),
 *((n+'/value',re.sub(r'([A-Z])',lambda m:'_'+m[1].lower(),n),'progression') for n in ('ancestryFeatLevels','classFeatLevels','generalFeatLevels','skillFeatLevels','skillIncreaseLevels')),
)}


def _class_spec(path):
    """PF2e-specific class8.6.1 source paths from pinned schemas above.

    Starting ranks and HP are contributions, progression is definition source;
    no acquired features, effective rank, modifier or total HP is inferred.
    """
    if path in CLASS_SOURCE:return CLASS_SOURCE[path]
    for base,(concept,kind) in CLASS_ARRAYS.items():
        if path==base:return concept,'array',False
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path):return concept,kind,False
    match=re.fullmatch(r'/system/items/([^/]+)/(uuid|img|name|level)',path)
    if not match or re.search(r'~(?![01])',match[1]):return None
    leaf=match[2]
    return 'class_feature_'+('image' if leaf=='img' else leaf),('nonnegative_integer' if leaf=='level' else 'string'),False


def _class_record(row,identity):
    """PF2e-specific class8.6.1 exact source DTO; schemas pinned above.

    Only starting rank leaves map to {rank,label}; all other values preserve
    source exactly. Rank labels are never effective character proficiency.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];spec=_class_spec(path)
    if path in SOURCE_PATHS:return row['provenance']['mapping']!='pf2e.class.source.v1'
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    if raw['document_uuid']!=identity['uuid']:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.class.source.v1',limitations=['class_source_not_effective_character']):return False
    concept,kind,nullable=spec;value=raw.get('value');expected=value
    numeric=type(value) in (int,float) and math.isfinite(value)
    if raw['present'] and kind=='rank':
        if not numeric or value%1 or not 0<=value<=4:return False
        expected=dict(rank=value,label=('Untrained','Trained','Expert','Master','Legendary')[int(value)])
        if type(row['mapped']['value']) is not dict or type(row['mapped']['value'].get('rank')) is not type(value):return False
    elif type(row['mapped']['value']) is not type(value):return False
    if row['mapped']!=dict(concept=concept,value=expected,unit=None):return False
    if not raw['present']:return True
    if value is None:return nullable
    return {'string':type(value) is str,'boolean':type(value) is bool,
            'hp':numeric and 4<=value<=12,'rank':numeric and value%1==0 and 0<=value<=4,
            'progression':numeric and value>=1,
            'nonnegative_integer':numeric and value%1==0 and value>=0,
            'array':type(value) is list and not value,'object':type(value) is dict and not value}[kind]


def _class_relationship(row,identity):
    """PF2e-specific class8.6.1 immediate ABC feature UUID definition claims.

    Pinned schemas above. Resolution establishes no acquired character feature.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='source' or type(raw['present']) is not bool or raw['present']!=('value'in raw):return False
    path=raw['path']
    if type(path) is not str or row['key']!='relationships:class:'+path:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.class.feature-reference.v1',limitations=['definition_reference_not_acquired_feature']):return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='class_feature_reference' or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if path=='/system/items':return (not raw['present'] and value==dict(status='missing',target_uuid=None)) or (raw['present'] and type(raw['value']) is dict and not raw['value'] and value==dict(status='empty',target_uuid=None))
    spec=_class_spec(path)
    if spec is None or spec[0]!='class_feature_uuid':return False
    if not raw['present']:return value==dict(status='missing',target_uuid=None)
    if type(raw['value']) is not str:return False
    if value.get('status')!='resolved':return value in [dict(status=status,target_uuid=None) for status in ('missing','denied','unsupported','unverified')]
    keys={'status','target_uuid','document_name','type','name','name_truncated'}
    synthetic=re.fullmatch(r'Scene\.[^.\s#]+\.Token\.[^.\s#]+\.Actor\.[^.\s#]+\.Item\.[^.\s#]+',raw['value'])
    if synthetic:keys.add('token_uuid')
    return (set(value)==keys and value['target_uuid']==raw['value'] and _effect_reference_uuid(value['target_uuid'],'Item') and value['document_name']=='Item' and type(value['type']) is str and value['type'] in ITEM_TYPES-{'affliction'} and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(raw['value'].split('.')[:4])))


# PF2e-specific KitSystemSchema8.6.1 definitions; never owned inventory.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/kit/data.ts
KIT_SOURCE = {'/system/'+p:('kit_'+c,k,n) for p,c,k,n in (
 ('items','items','object',False),('price/per','price_per','positive_integer',False),
 ('price/sizeSensitive','price_size_sensitive','boolean',False),
 *((f'price/value/{c}',f'price_{c}','nonnegative_integer',False) for c in ('pp','gp','sp','cp')),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
KIT_ARRAYS={'/system/traits/value':'kit_trait_code','/system/traits/otherTags':'kit_other_tag_code'}


def _kit_spec(path):
    """PF2e-specific pinned KitSystemSchema finite source paths and escaped keys.

    KitEntriesField permits four entry levels; last-level items is null only.
    Keys identify bundle definitions, never owned Item IDs or expanded contents.
    """
    if path in KIT_SOURCE:return KIT_SOURCE[path]
    for base,concept in KIT_ARRAYS.items():
        if path==base:return concept,'array',False
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path):return concept,'string',False
    parts=path.split('/')
    if parts[:3]!=['','system','items']:return None
    tail=parts[3:];level=0
    while len(tail)>=2:
        key,leaf=tail[:2]
        if not key or re.search(r'~(?![01])',key):return None
        if len(tail)==2:
            specs={'uuid':('component_uuid','string',False),'img':('component_image','string',False),
                   'quantity':('component_quantity','positive_integer',False),'name':('component_name','string',False),
                   'isContainer':('component_is_container','boolean',False),
                   'items':('component_items','null' if level==3 else 'object',True)}
            spec=specs.get(leaf)
            return ('kit_'+spec[0],*spec[1:]) if spec else None
        if leaf!='items' or level>=3:return None
        level+=1;tail=tail[2:]
    return None


def _kit_relationship(row,identity):
    """PF2e-specific kit8.6.1 explicit component UUID claims, never inventory.

    Pinned KitSystemSchema above. Resolving an immediate definition establishes
    no generated ownership, quantity multiplication or recursive target expansion.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='source' or type(raw['present']) is not bool or raw['present']!=('value'in raw):return False
    path=raw['path']
    if type(path) is not str or row['key']!='relationships:kit:'+path:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.kit.component-reference.v1',limitations=['bundle_definition_not_owned_inventory']):return False
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='kit_component_reference' or mapped['unit'] is not None:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if path=='/system/items':return (not raw['present'] and value==dict(status='missing',target_uuid=None)) or (raw['present'] and type(raw['value']) is dict and not raw['value'] and value==dict(status='empty',target_uuid=None))
    spec=_kit_spec(path)
    if spec is None or spec[0]!='kit_component_uuid':return False
    if not raw['present']:return value==dict(status='missing',target_uuid=None)
    if type(raw['value']) is not str:return False
    if value.get('status')!='resolved':return value in [dict(status=status,target_uuid=None) for status in ('missing','denied','unsupported','unverified')]
    keys={'status','target_uuid','document_name','type','name','name_truncated'}
    synthetic=re.fullmatch(r'Scene\.[^.\s#]+\.Token\.[^.\s#]+\.Actor\.[^.\s#]+\.Item\.[^.\s#]+',raw['value'])
    if synthetic:keys.add('token_uuid')
    return (set(value)==keys and value['target_uuid']==raw['value'] and _effect_reference_uuid(value['target_uuid'],'Item') and value['document_name']=='Item' and type(value['type']) is str and value['type'] in ITEM_TYPES-{'affliction'} and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (not synthetic or value['token_uuid']=='.'.join(raw['value'].split('.')[:4])))


def _kit_record(row,identity):
    """PF2e-specific kit8.6.1 authored bundle validation; no owned expansion.

    Pinned schema above. Kit price is its own schema, never shared physical
    quantity, carry state, container membership or effective valuation.
    """
    if len(row['raw'])!=1:return False
    raw=row['raw'][0];path=raw['path'];spec=_kit_spec(path)
    if path in SOURCE_PATHS:return row['provenance']['mapping']!='pf2e.kit.source.v1'
    if spec is None or row['section']!='source' or row['kind']!='field' or row['key']!='source:'+path:return False
    if raw['document_uuid']!=identity['uuid']:return False
    if row['provenance']!=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.kit.source.v1',limitations=['bundle_definition_not_owned_inventory']):return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):return False
    if not raw['present']:return True
    if value is None:return nullable or kind=='null'
    return {'string':type(value) is str,'boolean':type(value) is bool,
            'positive_integer':type(value) in (int,float) and math.isfinite(value) and value%1==0 and value>0,
            'nonnegative_integer':type(value) in (int,float) and math.isfinite(value) and value%1==0 and value>=0,
            'array':type(value) is list and not value,'object':type(value) is dict and not value,'null':False}[kind]


# PF2e-specific TreasureSystemSchema8.6.1 authored metadata; no derived valuation or sale.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/treasure/data.ts
TREASURE_SOURCE = {'/system/'+p:('treasure_'+c,k,n) for p,c,k,n in (
 ('category','category_code','string',True),
 ('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
TREASURE_ARRAYS = {'/system/'+p:'treasure_'+c for p,c in (
 ('traits/value','trait_code'),('traits/otherTags','other_tag_code'))}


def _treasure_spec(path):
    """PF2e-specific treasure8.6.1 source schema above; arrays retain exact codes.

    No stack group, sale price, total valuation or usage is inferred.
    """
    if path in TREASURE_SOURCE: return TREASURE_SOURCE[path]
    for base,concept in TREASURE_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _treasure_record(row,identity):
    """PF2e-specific treasure8.6.1 strict selected source and physical separation.

    Schema pinned above; traits and category remain authored, not valuation.
    Shared physical quantity, price.per and coin values retain their mapping.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_treasure_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.treasure.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.treasure.source.v1',limitations=['source_only_no_treasure_valuation_or_sale']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value}[kind]


# PF2e-specific ContainerSystemSource8.6.1 authored metadata; no benefit activation state.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/container/data.ts
CONTAINER_SOURCE = {'/system/'+p:('container_'+c,k,n) for p,c,k,n in (
 ('bulk/heldOrStowed','bulk_held_or_stowed','number',False),
 ('bulk/capacity','bulk_capacity','number',False),('bulk/ignored','bulk_ignored','number',False),
 ('stowing','stowing','boolean',False),
 ('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
CONTAINER_ARRAYS = {'/system/'+p:'container_'+c for p,c in (
 ('traits/value','trait_code'),('traits/otherTags','other_tag_code'))}


def _container_spec(path):
    """PF2e-specific backpack8.6.1 source schema above; arrays retain exact codes.

    No derived container Bulk, capacity usage or encumbrance is inferred.
    """
    if path in CONTAINER_SOURCE: return CONTAINER_SOURCE[path]
    for base,concept in CONTAINER_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _container_relationship(row, identity):
    """PF2e-specific8.6.1 persisted containerId owner-local graph boundary.

    Container/physical source schemas linked above define containment claims;
    actual public Item identities supply selectors, never computed Bulk or access.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship':return False
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if type(raw) is not list or type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['unit'] is not None:return False
    if type(provenance) is not dict or set(provenance)!={'contributors','mapping','limitations'} or provenance['mapping']!='pf2e.container.contents.v1' or provenance['limitations']!=['stored_containment_not_effective_bulk']:return False
    for r in raw:
        if type(r) is not dict or not {'document_uuid','path','present','basis'}<=set(r) or not set(r)<={'document_uuid','path','present','basis','value'}:return False
        if r['path']!='/system/containerId' or r['basis']!='source' or type(r['present']) is not bool or r['present']!=('value' in r) or r['present'] and r['value'] is not None and type(r['value']) is not str:return False
    if provenance['contributors']!=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]:return False
    value=mapped['value']
    if type(value) is not dict:return False
    owner=identity['actor'];instance=identity['instance']
    def owned(uuid):
        """PF2e-specific immediate physical Item identity within the actual owner."""
        prefix=owner['uuid']+'.Item.' if owner else ''
        return bool(prefix) and type(uuid) is str and len(uuid)<=512 and uuid.startswith(prefix) and re.fullmatch(r'[^.\s#]+',uuid[len(prefix):]) is not None
    def target(extra):
        """PF2e-specific detached actual containment target, never effective Bulk."""
        expected={'status','target_uuid','document_name','type','name','name_truncated'}|set(extra)
        if instance is not None:expected.add('token_uuid')
        return set(value)==expected and value['status']=='resolved' and owned(value['target_uuid']) and value['document_name']=='Item' and type(value['name']) is str and len(value['name'])<=256 and type(value['name_truncated']) is bool and (instance is None or value['token_uuid']==instance['token_uuid'])
    if row['key']=='relationships:container:scope':
        return raw==[] and mapped['concept']=='container_contents' and value in [dict(status=x,target_uuid=None) for x in ('unverified','empty','denied')] and (value['status'] in ('empty','denied') if owner is not None else value['status']=='unverified')
    if len(raw)!=1:return False
    r=raw[0];local_id=r.get('value')
    if row['key']=='relationships:container:parent':
        if mapped['concept']!='container_parent' or r['document_uuid']!=identity['uuid']:return False
        if value.get('status')!='resolved':
            if value not in [dict(status=x,target_uuid=None,cycle=False) for x in ('missing','denied','unsupported','unverified')] or value['cycle'] is not False:return False
            return value['status']=='missing' if not local_id else value['status']=='unverified' if owner is None else value['status'] in ('missing','denied','unsupported')
        return bool(local_id) and target({'cycle'}) and value['type']=='backpack' and type(value['cycle']) is bool and value['target_uuid']==owner['uuid']+'.Item.'+local_id
    uuid=r['document_uuid']
    if row['key']!='relationships:container:content:'+uuid or mapped['concept']!='container_content' or not owned(uuid) or uuid==identity['uuid'] or not r['present'] or not local_id:return False
    return target({'parent_uuid','parent_status','depth'}) and value['target_uuid']==uuid and value['type'] in PHYSICAL_TYPES and owned(value['parent_uuid']) and value['parent_uuid']==owner['uuid']+'.Item.'+local_id and value['parent_status'] in ('resolved','unsupported') and type(value['depth']) is int and 1<=value['depth']<=12000 and (value['depth']==1)==(value['parent_uuid']==identity['uuid'])


def _container_record(row,identity):
    """PF2e-specific backpack8.6.1 strict selected source and physical separation.

    Schema pinned above; traits remain authored, not active benefit calculations.
    Shared physical usage, investment and base Bulk paths retain their mapping.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_container_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.container.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.container.source.v1',limitations=['source_only_no_container_bulk_calculation']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value}[kind]


# PF2e-specific ConsumableSystemSource8.6.1 authored source; no use/spell application.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/consumable/data.ts
CONSUMABLE_SOURCE = {'/system/'+p:('consumable_'+c,k,n) for p,c,k,n in (
 ('category','category_code','string',False),
 ('uses/value','uses_value','number',False),('uses/max','uses_max','number',False),
 ('uses/autoDestroy','uses_auto_destroy','boolean',False),
 ('damage','damage_healing','null',True),('damage/formula','damage_formula','string',False),
 ('damage/type','damage_type_code','string',False),('damage/kind','damage_kind_code','string',False),
 ('spell','contained_spell','null',True),('spell/_id','contained_spell_id','string',False),
 ('spell/name','contained_spell_name','string',False),('spell/type','contained_spell_type','spell',False),
 ('spell/system/level/value','contained_spell_base_rank','number',False),
 ('traits/rarity','rarity_code','string',False),
 ('slug','source_slug','string',True),('publication/title','publication_title','string',False),
 ('publication/authors','publication_authors','string',False),('publication/license','publication_license','string',False),
 ('publication/remaster','publication_remaster','boolean',False),
)}
CONSUMABLE_ARRAYS = {'/system/'+p:'consumable_'+c for p,c in (
 ('traits/value','trait_code'),('traits/otherTags','other_tag_code'))}


def _consumable_spec(path):
    """PF2e-specific consumable8.6.1 source schema above; arrays retain exact codes.

    Damage formulas and contained spell definitions remain authored source only.
    """
    if path in CONSUMABLE_SOURCE: return CONSUMABLE_SOURCE[path]
    for base,concept in CONSUMABLE_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _contained_spell_spec(path):
    """PF2e-specific8.6.1 contained SpellSystemSource paths; no new identity.

    ConsumableSystemSource.spell embeds the pinned SpellSource schema above.
    Existing consumable local metadata/base-rank paths retain their own mapping.
    Definition and layered prose selection reuse the spell allowlist; local
    casting-entry claims are source data and never relationships to an owner.
    """
    prefix='/system/spell'
    if not path.startswith(prefix+'/system/') or _consumable_spec(path) is not None:
        return None
    return _spell_spec(path[len(prefix):])


def _contained_spell_record(row, identity):
    """PF2e-specific8.6.1 contained spell DTO, preserving consumable provenance.

    Normalize only prefixed field paths for the shared spell schema validator;
    document_uuid remains the actual consumable UUID throughout. Relationships
    are excluded because embedded SpellSource is no independent document.
    """
    if row['section'] == 'relationships' or len(row['raw']) != 1:
        return False
    prefix='/system/spell'
    raw=row['raw'][0]
    if _contained_spell_spec(raw['path']) is None:
        return False
    # Paths are already admitted by _source_path; leave the original DTO intact.
    normalized=dict(row)
    normalized['raw']=[dict(raw,path=raw['path'][len(prefix):])]
    normalized['provenance']=dict(row['provenance'],contributors=[
        dict(c,path=c['path'][len(prefix):]) for c in row['provenance']['contributors']])
    if row['section'] == 'source':
        if row['key'] != 'source:'+raw['path']:
            return False
        normalized['key']='source:'+normalized['raw'][0]['path']
    return _spell_record(normalized,identity)


def _consumable_record(row,identity):
    """PF2e-specific consumable8.6.1 strict selected source and physical separation.

    Schema pinned above; no damage roll or contained-spell application is inferred.
    Shared physical fields retain their mapping; contained spell IDs are local source IDs.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_consumable_spec(path)
    if _contained_spell_spec(path) is not None:
        return _contained_spell_record(row,identity)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.consumable.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.consumable.source.v1',limitations=['source_only_no_consumable_use_or_spell_application']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value,
            'null':False,'spell':type(value) is str and value == 'spell'}[kind]


# PF2e-specific ArmorSystemSource8.6.1 persisted leaves, never Actor defenses.
# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/armor/data.ts
ARMOR_SOURCE = {'/system/'+p:('armor_'+c,k,n) for p,c,k,n in (
 ('category','category_code','string',False),('group','group_code','string',True),
 ('acBonus','ac_bonus','number',False),('strength','strength_requirement','number',True),
 ('dexCap','dex_cap','number',False),('checkPenalty','check_penalty','number',False),
 ('speedPenalty','speed_penalty','number',False),('grade','grade_code','string',True),
 ('specific','specific_baseline','object',True),('specific/material','specific_material','object',False),
 ('specific/material/type','specific_material_type_code','string',True),('specific/material/grade','specific_material_grade_code','string',True),
 ('traits/rarity','rarity_code','string',False),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),
 ('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
)}
for _prefix in ('runes','specific/runes'):
    ARMOR_SOURCE.update({'/system/'+_prefix+suffix:('armor_'+concept,kind,False) for suffix,concept,kind in (('', 'runes','object'),('/potency','rune_potency','number'),('/resilient','rune_resilient','number'))})
ARMOR_ARRAYS = {'/system/'+p:'armor_'+c for p,c in (('traits/value','trait_code'),('traits/otherTags','other_tag_code'),('runes/property','property_rune_code'),('specific/runes/property','property_rune_code'))}


def _armor_spec(path):
    """PF2e-specific armor8.6.1 source schema above; codes stay authored.

    Item acBonus and rune values never establish Actor AC, saves or movement.
    """
    if path in ARMOR_SOURCE: return ARMOR_SOURCE[path]
    for base,concept in ARMOR_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _armor_record(row,identity):
    """PF2e-specific armor8.6.1 exact source DTO and shared physical separation.

    Schema pinned above; source penalties/runes remain authored, not applied.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_armor_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.armor.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.armor.source.v1',limitations=['source_only_no_actor_armor_calculation']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value,'object':type(value) is dict and not value}[kind]


# https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/shield/data.ts
SHIELD_SOURCE = {'/system/'+p:('shield_'+c,k,n) for p,c,k,n in (
 ('acBonus','ac_bonus','number',False),('speedPenalty','speed_penalty','number',False),('grade','grade_code','string',True),
 ('specific','specific_baseline','object',True),('specific/material','specific_material','object',False),
 ('specific/material/type','specific_material_type_code','string',True),('specific/material/grade','specific_material_grade_code','string',True),
 ('traits/integrated','integrated_weapon','object',True),('specific/integrated','specific_integrated_weapon','object',True),
 ('traits/integrated/versatile','integrated_weapon_versatile','object',True),('traits/integrated/versatile/selected','integrated_weapon_versatile_selected_damage_code','string',False),
 ('traits/rarity','rarity_code','string',False),('slug','source_slug','string',True),
 ('publication/title','publication_title','string',False),('publication/authors','publication_authors','string',False),
 ('publication/license','publication_license','string',False),('publication/remaster','publication_remaster','boolean',False),
)}
for _prefix in ('runes','specific/runes'):
    SHIELD_SOURCE.update({'/system/'+_prefix+suffix:('shield_'+concept,kind,False) for suffix,concept,kind in (('', 'runes','object'),('/reinforcing','rune_reinforcing','number'))})
SHIELD_ARRAYS = {'/system/'+p:'shield_'+c for p,c in (('traits/value','trait_code'),('traits/otherTags','other_tag_code'))}
for _prefix in ('traits/integrated/runes','specific/integrated/runes'):
    SHIELD_SOURCE.update({'/system/'+_prefix+suffix:('shield_'+concept,kind,False) for suffix,concept,kind in (('', 'integrated_weapon_runes','object'),('/potency','integrated_weapon_rune_potency','number'),('/striking','integrated_weapon_rune_striking','number'))})
    SHIELD_ARRAYS['/system/'+_prefix+'/property']='shield_integrated_weapon_property_rune_code'


def _shield_spec(path):
    """PF2e-specific shield8.6.1 source schema above; codes stay authored.

    Item acBonus and rune values never establish raised state, Shield Block, Actor AC or effective defenses.
    """
    if path in SHIELD_SOURCE: return SHIELD_SOURCE[path]
    for base,concept in SHIELD_ARRAYS.items():
        if path == base: return (concept,'array',False)
        if re.fullmatch(re.escape(base)+r'/(0|[1-9][0-9]*)',path): return (concept,'string',False)
    return None


def _shield_record(row,identity):
    """PF2e-specific shield8.6.1 exact source DTO and shared physical separation.

    Schema pinned above; source penalties/runes remain authored, not applied.
    """
    if len(row['raw']) != 1: return False
    raw=row['raw'][0];path=raw['path'];spec=_shield_spec(path)
    if spec is None:
        if path in SOURCE_PATHS or path == UNIDENTIFIED_DESCRIPTION:
            return row['provenance']['mapping'] != 'pf2e.shield.source.v1'
        return row['provenance']['mapping'] == 'pf2e.physical.source.v1'
    if row['section'] != 'source' or row['kind'] != 'field' or row['key'] != 'source:'+path: return False
    concept,kind,nullable=spec;value=raw.get('value')
    if raw['document_uuid'] != identity['uuid']: return False
    if row['provenance'] != dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.shield.source.v1',limitations=['source_only_no_actor_shield_calculation']): return False
    if row['mapped'] != dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value): return False
    if not raw['present']: return True
    if value is None and nullable: return True
    return {'number':type(value) in (int,float) and math.isfinite(value),'boolean':type(value) is bool,
            'string':type(value) is str,'array':type(value) is list and not value,'object':type(value) is dict and not value}[kind]


def _source_path(path: Any, identity: dict[str, Any] | None = None) -> bool:
    """PF2e-specific: admit pinned physical/ability/attack/Lore8.6.1 paths.

    Armor/shield/treasure source overrides exclude usage; treasure excludes
    investment/slot/hands. Serialized attachment identities are source paths,
    never independent Item UUIDs. No effective Bulk/value/statistic is inferred.
    """
    if type(path) is not str:
        return False
    if path in SOURCE_PATHS:
        return True
    if identity is not None and identity['document_name']=='Actor' and identity['type']=='familiar':
        return _familiar_spec(path) is not None or path=='/system/details/creature/value'
    if identity is not None and identity['document_name']=='Actor' and identity['type']=='character':
        return _character_spec(path) is not None or _character_note_spec(path) is not None
    if identity is not None and identity['document_name']=='Actor' and identity['type']=='npc':
        return path in NPC_NOTES or _npc_spec(path) is not None
    if identity is None or identity['document_name'] != 'Item':
        return False
    if identity['type'] == 'feat':
        return _feat_spec(path) is not None
    if identity['type'] == 'deity':
        return _deity_spec(path) is not None
    if identity['type'] == 'class':
        return _class_spec(path) is not None
    if identity['type'] == 'heritage':
        return _heritage_spec(path) is not None
    if identity['type'] == 'background':
        return _background_spec(path) is not None
    if identity['type'] == 'ancestry':
        return _ancestry_spec(path) is not None
    if identity['type'] == 'kit':
        return _kit_spec(path) is not None
    if identity['type'] == 'spellcastingEntry':
        return _casting_entry_spec(path) is not None
    if identity['type'] == 'spell':
        return _spell_spec(path) is not None
    if identity['type'] == 'condition':
        return _condition_spec(path) is not None
    if identity['type'] == 'effect':
        return bool(_effect_spec(path))
    if identity['type'] == 'lore':
        return path in LORE_PATHS or LORE_VARIANT.fullmatch(path) is not None or re.fullmatch(r'/system/traits/otherTags/(0|[1-9][0-9]*)',path) is not None
    # PF2e-specific action paths exclude toggles, rule elements and prepared data.
    if identity['type'] == 'action':
        return path in ACTION_PATHS or re.fullmatch(r'/system/traits/(value|otherTags)/(0|[1-9][0-9]*)',path) is not None
    # PF2e-specific NPC attack source excludes gear flags and prepared bonuses.
    if identity['type'] == 'melee':
        return path in MELEE_PATHS or DAMAGE_LEAF.fullmatch(path) is not None or MELEE_ARRAY_INDEX.fullmatch(path) is not None
    if identity['type'] == 'consumable' and (_consumable_spec(path) is not None or _contained_spell_spec(path) is not None):
        return True
    if identity['type'] == 'backpack' and _container_spec(path) is not None:
        return True
    if identity['type'] == 'book' and _book_spec(path) is not None:
        return True
    if identity['type'] == 'treasure' and _treasure_spec(path) is not None:
        return True
    if identity['type'] == 'equipment' and _equipment_spec(path) is not None:
        return True
    if identity['type'] == 'shield' and _shield_spec(path) is not None:
        return True
    if identity['type'] == 'armor' and _armor_spec(path) is not None:
        return True
    if identity['type'] == 'ammo' and _ammo_spec(path) is not None:
        return True
    if identity['type'] == 'weapon' and _weapon_spec(path) is not None:
        return True
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
        if row is not None and (type(row) is not dict or not keys <= set(row) or not set(row) <= keys | {'name_truncated'} | ({'type'} if key == 'actor' else set()) or not all(type(row[k]) is str for k in keys) or ('name_truncated' in row and type(row['name_truncated']) is not bool)):
            return False
    if value['actor'] is not None and 'type' in value['actor'] and value['actor']['type'] not in ('character','npc','familiar'):
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


CASTING_LIMIT = ['source_configuration_only', 'availability_not_evaluated']


def _state_child_identity(uuid, typ, identity):
    """PF2e-specific8.6.1 actual owner context for condition/effect validation."""
    return dict(identity,document_name='Item',uuid=uuid,id=uuid.rsplit('.Item.',1)[1],type=typ,
                actor={key:identity[key] for key in ('uuid','name','type')})


def _actor_state_record(row, identity):
    """PF2e-specific8.6.1 owned condition/effect source and public current expiry.

    Reuses pinned condition/effect schemas and immediate relationship validators
    with the selected Actor/token owner. EffectSystemData.expired from public
    Item.system own data uses transformed provenance; it does not prove full
    application. Missing transformed expiry stays missing. Afflictions unsupported.
    https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
    """
    if identity['type'] not in ('character','npc','familiar') or set(row)!={'key','section','kind','raw','mapped','provenance'}:return False
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['unit'] is not None:return False
    if type(provenance) is not dict or set(provenance)!={'contributors','mapping','limitations'}:return False
    mapping=provenance['mapping']
    for field in raw:
        if type(field) is not dict or not {'document_uuid','path','present','basis'}<=set(field) or not set(field)<={'document_uuid','path','present','basis','value'}:return False
        if field['basis']!=('transformed' if mapping=='pf2e.effect.current.v1' else 'source') or type(field['present']) is not bool or field['present']!=('value' in field):return False
    if provenance['contributors']!=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]:return False
    # PF2e-specific EffectSystemData.expired is derived, never persisted source.
    # 8.6.1 effect/data.ts at the immutable revision linked in this docstring.
    if mapping=='pf2e.effect.current.v1':
        if len(raw)!=1 or row['kind']!='field':return False
        field=raw[0];uuid=field['document_uuid']
        if not _casting_owned(uuid,identity) or field['path']!='/system/expired' or row['key']!='state:current:'+uuid+':/system/expired':return False
        if field['present'] and type(field['value']) is not bool:return False
        return (mapped['concept']=='current_effect_expired' and type(mapped['value']) is (bool if field['present'] else type(None))
                and mapped['value']==(field['value'] if field['present'] else None)
                and provenance['limitations']==['effect_expiry_not_application'])
    if mapping=='pf2e.actor.state-capability.v1':
        return (row['key']=='state:capability:affliction' and row['kind']=='field' and raw==[]
                and mapped==dict(concept='state_affliction_support',value=dict(status='unsupported',reason='pf2e_8_6_1_affliction_disabled'),unit=None)
                and provenance['limitations']==['no_effective_state_inference'])
    if mapping=='pf2e.actor.state-source.v1':
        if row['kind']!='relationship' or mapped['concept']!='state_item' or provenance['limitations']!=['stored_state_not_effective_application']:return False
        if row['key']=='state:denied':return raw==[] and mapped['value']==dict(status='denied',target_uuid=None)
        if len(raw)!=2 or [r['path'] for r in raw]!=['/name','/type'] or not all(r['present'] for r in raw):return False
        uuid=raw[0]['document_uuid'];name=raw[0]['value'];typ=raw[1]['value']
        if not _casting_owned(uuid,identity) or any(r['document_uuid']!=uuid for r in raw) or type(name) is not str or typ not in ('condition','effect'):return False
        expected=dict(status='resolved',target_uuid=uuid,document_name='Item',type=typ,name=name[:256],name_truncated=len(name)>256,application='unknown')
        if identity['instance'] is not None:expected['token_uuid']=identity['instance']['token_uuid']
        return row['key']=='state:item:'+uuid and json.dumps(mapped['value'],sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False)
    types={'pf2e.condition.source.v1':'condition','pf2e.effect.source.v1':'effect','pf2e.condition.reference.v1':'condition','pf2e.effect.context-reference.v1':'effect'}
    typ=types.get(mapping)
    if typ is None or not raw:return False
    uuid=raw[0]['document_uuid']
    if not _casting_owned(uuid,identity) or any(r['document_uuid']!=uuid for r in raw):return False
    child=_state_child_identity(uuid,typ,identity)
    if mapping in ('pf2e.condition.source.v1','pf2e.effect.source.v1'):
        if len(raw)!=1 or (_condition_spec(raw[0]['path']) is None if typ=='condition' else not _effect_spec(raw[0]['path'])):return False
        if row['key']!='state:source:'+uuid+':'+raw[0]['path']:return False
        delegated=dict(row,section='source',key='source:'+raw[0]['path'])
        return _record(delegated,['source'],child)
    prefix='state:'+typ+':'+uuid+':'
    if not row['key'].startswith(prefix):return False
    expected_limit=(['Stored local reference or override slug only; no active/suppressed state or persistent-damage dominance is inferred. Unresolved targets disclose no resolved metadata.'] if typ=='condition' else ['Immediate stored context only; no acquired ability, learned spell, current application or recursive provenance is inferred. Unresolved targets disclose no identity.'])
    if provenance['limitations']!=expected_limit:return False
    suffix=row['key'][len(prefix):]
    delegated=dict(row,section='relationships',key='relationships:'+typ+':'+suffix)
    return _record(delegated,['relationships'],child)


def _state_section(records, section, identity):
    """PF2e-specific8.6.1 same-page state evidence; source is not application."""
    rows=[r for r in records if r['section']=='state']
    reasons=set(section['reasons'])
    if section['status']!='partial' or not {'effective_application_not_evaluated','affliction_reading_unsupported'}<=reasons:return False
    if any(r['key']=='state:denied' for r in rows) and 'state_items_denied' not in reasons:return False
    if not reasons<={'effective_application_not_evaluated','affliction_reading_unsupported','state_items_denied','unresolved_state_references','current_effect_expiry_unavailable','pagination'}:return False
    types={};source={}
    for row in rows:
        mapping=row['provenance']['mapping']
        if mapping=='pf2e.actor.state-source.v1' and row['raw']:
            uuid=row['raw'][0]['document_uuid'];typ=row['raw'][1]['value']
        elif mapping in ('pf2e.condition.source.v1','pf2e.condition.reference.v1'):uuid=row['raw'][0]['document_uuid'];typ='condition'
        elif mapping in ('pf2e.effect.source.v1','pf2e.effect.context-reference.v1','pf2e.effect.current.v1'):uuid=row['raw'][0]['document_uuid'];typ='effect'
        else:continue
        if mapping=='pf2e.effect.current.v1' and not row['raw'][0]['present'] and 'current_effect_expiry_unavailable' not in reasons:return False
        if mapping in ('pf2e.condition.reference.v1','pf2e.effect.context-reference.v1'):
            selected=[row['raw'][0]] if typ=='condition' else [row['raw'][EFFECT_REFERENCE_ROLES.index(row['key'].rsplit(':',1)[1])]]
            if row['mapped']['value']['status']!='resolved' and any(field['present'] and type(field['value']) is str and field['value']!='' for field in selected):
                if 'unresolved_state_references' not in reasons:return False
        if uuid in types and types[uuid]!=typ:return False
        types[uuid]=typ
        if mapping=='pf2e.effect.source.v1':source.setdefault(uuid,[]).append(dict(row,section='source'))
    for row in rows:
        if row['provenance']['mapping']=='pf2e.condition.reference.v1' and row['mapped']['value']['status']=='resolved':
            target=row['mapped']['value']
            if target['target_uuid'] in types and types[target['target_uuid']]!=target['type']:return False
    return all(_effect_source_page(fields) for fields in source.values())


def _casting_owned(uuid, identity):
    """PF2e-specific immediate owned spell/entry UUID; generated UUIDs excluded."""
    prefix=identity['uuid']+'.Item.'
    return type(uuid) is str and len(uuid)<=512 and uuid.startswith(prefix) and re.fullmatch(r'[^.\s#]+',uuid[len(prefix):]) is not None


def _casting_section(records, section):
    """PF2e-specific8.6.1 casting page evidence, not exhaustive Item coverage.

    A same-page /type source witness must agree with transformed SpellCastData;
    missing witnesses can be on another page and do not imply missing Items.
    """
    rows=[row for row in records if row['section']=='spellcasting']
    current=[row for row in rows if row['provenance']['mapping']=='pf2e.actor.casting-current.v1']
    options=[row for row in rows if row['provenance']['mapping']=='pf2e.actor.casting-options.v1']
    for option in options:
        value=option['mapped']['value'];spell_uuid=value['spell']['target_uuid']
        if value['signature'] is True and 'signature_alternatives_not_evaluated' not in section['reasons']:return False
        for witness in rows:
            if witness['key']=='spellcasting:assignment:'+spell_uuid:
                # PF2e-specific assignment display labels and option persisted
                # names have separate row contracts. Join stable identity only;
                # each row's names remain independently validated above.
                stable=('status','target_uuid','type','token_uuid')
                if ({key:field for key,field in witness['mapped']['value'].items() if key in stable}
                        != {key:field for key,field in value['entry'].items() if key in stable}):return False
            for field in witness['raw']:
                if field['path']=='/type' and field['present']:
                    if field['document_uuid']==spell_uuid and field['value']!='spell':return False
                    if field['document_uuid']==value['entry']['target_uuid'] and field['value']!='spellcastingEntry':return False
        if value['context']=='unsupported_mode' and 'unsupported_casting_mode' not in section['reasons']:return False
        if value['preparation_index'] is not None:
            path=f"/system/slots/slot{value['slot_rank']}/prepared/{value['preparation_index']}/expended"
            if not any(field['path']==path for field in option['raw']) and 'malformed_preparation' not in section['reasons']:return False
    if any(not row['raw'][0]['present'] for row in current) and 'current_fields_unavailable' not in section['reasons']:return False
    for row in current:
        raw=row['raw'][0]
        if raw['path']!='/system/cast/focusPoints':continue
        for witness in rows:
            for field in witness['raw']:
                if field['document_uuid']==raw['document_uuid'] and field['path']=='/type' and field['present'] and field['value']!='spell':return False
    return section['status']=='partial' and 'availability_not_evaluated' in section['reasons']


def _actor_casting_option_record(row, identity):
    """PF2e-specific8.6.1 owned spell/entry source contextual options.

    SpellSystemSource location/level/traits, SpellcastingEntrySystemSource
    prepared/slots and character/creature focus source are selected witnesses.
    No rank, entitlement, availability or resource expenditure is calculated.
    https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='relationship':return False
    raw=row['raw'];mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['concept']!='casting_contextual_option' or mapped['unit'] is not None:return False
    if row['provenance']!=dict(contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw],mapping='pf2e.actor.casting-options.v1',limitations=['availability_not_evaluated','configured_rank_not_final_cast_rank']):return False
    for field in raw:
        if type(field) is not dict or not {'document_uuid','path','present','basis'}<=set(field) or not set(field)<={'document_uuid','path','present','basis','value'}:return False
        if field['basis']!='source' or type(field['present']) is not bool or field['present']!=('value' in field):return False
    value=mapped['value']
    if type(value) is not dict or not raw:return False
    position=0
    def take(uuid,path,kind,nullable=False,required=False):
        """PF2e-specific ordered scalar source witnesses; absence never defaults."""
        nonlocal position
        if position>=len(raw):raise ValueError('Missing option witness')
        field=raw[position];position+=1
        if field['document_uuid']!=uuid or field['path']!=path:raise ValueError('Wrong option witness')
        result=field.get('value')
        if required and not field['present']:raise ValueError('Missing required option witness')
        if field['present'] and not (nullable and result is None):
            valid={'string':type(result) is str,'number':type(result) in (int,float) and math.isfinite(result),'boolean':type(result) is bool}
            if not valid.get(kind,False):raise ValueError('Invalid option witness type')
        return result
    def identify(uuid,typ):
        """PF2e-specific owner-local identity derived from exact name/type source."""
        if not _casting_owned(uuid,identity):raise ValueError('Wrong option owner')
        name=take(uuid,'/name','string',required=True)
        if take(uuid,'/type','string',required=True)!=typ:raise ValueError('Wrong option Item type')
        result=dict(status='resolved',target_uuid=uuid,type=typ,name=name[:256],name_truncated=len(name)>256)
        if identity['instance'] is not None:result['token_uuid']=identity['instance']['token_uuid']
        return result
    try:
        spell_uuid=raw[0]['document_uuid'];spell=identify(spell_uuid,'spell')
        assignment=take(spell_uuid,'/system/location/value','string',True)
        ritual=position<len(raw) and raw[position]['path']=='/system/ritual/primary/check'
        if ritual:
            take(spell_uuid,'/system/ritual/primary/check','string',required=True)
            take(spell_uuid,'/system/ritual/secondary/checks','string',required=True)
            take(spell_uuid,'/system/ritual/secondary/casters','number',required=True)
        entry_value=value.get('entry')
        if type(entry_value) is not dict:return False
        if entry_value.get('status')=='resolved':
            entry_uuid=entry_value.get('target_uuid')
            if not assignment or entry_uuid!=identity['uuid']+'.Item.'+assignment:return False
            entry=identify(entry_uuid,'spellcastingEntry')
        else:
            if entry_value not in [dict(status=s,target_uuid=None) for s in ('missing','denied','unsupported')]:return False
            if not assignment and entry_value['status']!='missing':return False
            entry_uuid=None;entry=entry_value
        base=take(spell_uuid,'/system/level/value','number')
        configured=take(spell_uuid,'/system/location/heightenedLevel','number')
        spell_auto=take(spell_uuid,'/system/location/autoHeightenLevel','number',True)
        signature=take(spell_uuid,'/system/location/signature','boolean')
        traits=[];cantrip=None
        if position<len(raw) and raw[position]['path']=='/system/traits/value':
            field=raw[position];position+=1
            if field['document_uuid']!=spell_uuid or field['present'] and (type(field.get('value')) is not list or field['value']!=[]):return False
            if field['present']:cantrip=False
        else:
            while position<len(raw) and raw[position]['path']==f'/system/traits/value/{len(traits)}':traits.append(take(spell_uuid,f'/system/traits/value/{len(traits)}','string',required=True))
            if not traits or len(traits)>200:return False
            cantrip='cantrip' in traits
        mode=flexible=entry_auto=None
        if entry_uuid:
            mode=take(entry_uuid,'/system/prepared/value','string')
            flexible=take(entry_uuid,'/system/prepared/flexible','boolean')
            entry_auto=take(entry_uuid,'/system/autoHeightenLevel/value','number',True)
        rank=value.get('slot_rank');index=value.get('preparation_index');expended=None
        unsupported=ritual or bool(entry_uuid and (flexible is True or mode not in ('prepared','spontaneous','innate','focus')))
        if rank is not None or index is not None:
            if unsupported or mode!='prepared' or type(rank) is not int or not 0<=rank<=10 or type(index) is not int or not 0<=index<6000:return False
            path=f'/system/slots/slot{rank}/prepared/{index}'
            if take(entry_uuid,path+'/id','string',True,True)!=spell_uuid.rsplit('.Item.',1)[1]:return False
            if position<len(raw) and raw[position]['path']==path+'/expended':expended=take(entry_uuid,path+'/expended','boolean')
            take(entry_uuid,f'/system/slots/slot{rank}/value','number');take(entry_uuid,f'/system/slots/slot{rank}/max','number')
        uses=dict(value=take(spell_uuid,'/system/location/uses/value','number'),max=take(spell_uuid,'/system/location/uses/max','number')) if mode=='innate' else None
        context='unsupported_mode' if unsupported else 'prepared_use' if rank is not None else {'spontaneous':'spontaneous_repertoire','innate':'innate_spell','focus':'focus_spell'}.get(mode,'listed_spell')
        scope={'prepared_use':'individual_preparation','spontaneous_repertoire':'shared_entry_slots','innate_spell':'individual_spell_uses','focus_spell':'shared_actor_focus'}.get(context,'not_evaluated')
        if context=='focus_spell' and identity['type']!='familiar':
            take(identity['uuid'],'/system/resources/focus/value','number')
            if identity['type']=='npc':take(identity['uuid'],'/system/resources/focus/max','number')
        expected=dict(spell=spell,entry=entry,mode=mode,context=context,base_rank=base,configured_rank=configured,spell_auto_heighten_rank=spell_auto,entry_auto_heighten_rank=entry_auto,cast_rank=None,slot_rank=rank,preparation_index=index,expended=expended,signature=signature,cantrip=cantrip,uses=uses,resource_scope=scope,availability='not_evaluated')
        key=f"spellcasting:option:{spell_uuid}:{entry_uuid or 'unassigned'}:{rank if rank is not None else 'none'}:{index if index is not None else 'none'}"
        return position==len(raw) and row['key']==key and json.dumps(value,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False)
    except (KeyError,TypeError,ValueError):return False


def _actor_casting_current_record(row, identity):
    """PF2e-specific8.6.1 character/NPC focus and owned SpellCastData leaves.

    Transformed serializer values remain separate from persisted source and do
    not establish availability. Actor focus fields are finite numbers; spell
    cast.focusPoints is an integer 0–3. Familiar derivation is unsupported.
    https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='field' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['basis']!='transformed' or type(raw['present']) is not bool or raw['present']!=('value' in raw):return False
    uuid=raw['document_uuid'];path=raw['path'];value=raw.get('value')
    concepts={'/system/resources/focus/value':'current_focus_points','/system/resources/focus/max':'current_focus_pool_maximum','/system/resources/focus/cap':'current_focus_pool_cap'}
    if identity['type'] in ('character','npc') and uuid==identity['uuid'] and type(path) is str and path in concepts:
        concept=concepts[path]
        valid=type(value) in (int,float) and math.isfinite(value)
    elif _casting_owned(uuid,identity) and path=='/system/cast/focusPoints':
        concept='current_spell_focus_point_cost'
        valid=type(value) is int and 0<=value<=3
    else:return False
    if raw['present'] and not valid:return False
    if row['key']!='spellcasting:current:'+uuid+':'+path:return False
    return (row['mapped']==dict(concept=concept,value=value,unit=None)
            and type(row['mapped'].get('value')) is type(value)
            and row['provenance']==dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.actor.casting-current.v1',limitations=['casting_availability_not_evaluated']))


def _actor_casting_record(row, identity):
    """PF2e-specific8.6.1 Actor source casting joins; no current castability.

    Same-owner spell/entry source fields reuse their strict pinned validators.
    Focus value/max use Actor schemas; character max is derived and excluded.
    https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'}:return False
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['unit'] is not None:return False
    if type(provenance) is not dict or set(provenance)!={'contributors','mapping','limitations'}:return False
    if provenance['mapping']=='pf2e.actor.casting-options.v1':return _actor_casting_option_record(row,identity)
    if provenance['mapping']=='pf2e.actor.casting-current.v1':return _actor_casting_current_record(row,identity)
    for r in raw:
        if type(r) is not dict or not {'document_uuid','path','present','basis'}<=set(r) or not set(r)<={'document_uuid','path','present','basis','value'}:return False
        if r['basis']!='source' or type(r['path']) is not str or type(r['present']) is not bool or r['present']!=('value' in r):return False
    if provenance['contributors']!=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]:return False
    mapping=provenance['mapping']
    if mapping in ('pf2e.spell.source.v1','pf2e.spellcasting-entry.source.v1'):
        if len(raw)!=1 or row['kind']!='field':return False
        r=raw[0];uuid=r['document_uuid'];path=r['path']
        if not _casting_owned(uuid,identity) or row['key']!='spellcasting:source:'+uuid+':'+path:return False
        typ='spell' if mapping=='pf2e.spell.source.v1' else 'spellcastingEntry'
        if typ=='spell' and not (path in ('/system/level','/system/traits','/system/level/value','/system/traits/value','/system/location') or re.fullmatch(r'/system/traits/value/(0|[1-9][0-9]*)',path) or path.startswith('/system/location/')):return False
        return _record(dict(row,section='source',key='source:'+path),['source'],dict(identity,document_name='Item',uuid=uuid,type=typ))
    if mapping!='pf2e.actor.casting-source.v1' or provenance['limitations']!=CASTING_LIMIT:return False
    if row['kind']=='field':
        if len(raw)!=1:return False
        r=raw[0]
        for leaf in ('value','max'):
            if row['key']=='spellcasting:focus:'+leaf:
                value=r.get('value')
                return (leaf!='max' or identity['type'] in ('npc','familiar')) and r['document_uuid']==identity['uuid'] and r['path']=='/system/resources/focus/'+leaf and mapped==dict(concept='casting_focus_'+leaf,value=value,unit=None) and (not r['present'] or type(value) in (int,float) and math.isfinite(value))
        return False
    if row['kind']!='relationship':return False
    if row['key']=='spellcasting:denied':return raw==[] and mapped==dict(concept='casting_item',value=dict(status='denied',target_uuid=None),unit=None)
    concept=mapped['concept'];value=mapped['value']
    if type(value) is not dict:return False
    def target(expected_type, local_id=None):
        """PF2e-specific actual Item join identity; no inferred cast availability."""
        status=value.get('status')
        if status!='resolved':return value==dict(status=status,target_uuid=None) and status in ('missing','denied','unsupported','unverified','mismatched_assignment')
        expected={'status','target_uuid','type','name','name_truncated'}
        if identity['instance'] is not None:expected.add('token_uuid')
        if set(value)!=expected or value['type']!=expected_type or type(value['name']) is not str or len(value['name'])>256 or type(value['name_truncated']) is not bool or not _casting_owned(value['target_uuid'],identity):return False
        if local_id is not None and value['target_uuid']!=identity['uuid']+'.Item.'+local_id:return False
        return identity['instance'] is None or value['token_uuid']==identity['instance']['token_uuid']
    if concept in ('casting_entry','casting_spell'):
        typ='spellcastingEntry' if concept=='casting_entry' else 'spell';label='entry' if typ=='spellcastingEntry' else 'spell'
        if len(raw)!=2 or [r['path'] for r in raw]!=['/name','/type']:return False
        uuid=raw[0]['document_uuid']
        return _casting_owned(uuid,identity) and row['key']=='spellcasting:'+label+':'+uuid and all(r['document_uuid']==uuid and r['present'] for r in raw) and type(raw[0]['value']) is str and raw[1]['value']==typ and value.get('target_uuid')==uuid and value.get('name')==raw[0]['value'][:256] and value.get('name_truncated')==(len(raw[0]['value'])>256) and target(typ)
    if len(raw)!=1:return False
    r=raw[0];uuid=r['document_uuid'];path=r['path'];local_id=r.get('value')
    if not _casting_owned(uuid,identity) or r['present'] and local_id is not None and type(local_id) is not str:return False
    if concept=='casting_spell_assignment':
        if row['key']!='spellcasting:assignment:'+uuid or path!='/system/location/value':return False
        typ='spellcastingEntry'
    elif concept=='casting_preparation':
        match=re.fullmatch(r'/system/slots/(slot(?:[0-9]|10|11))/prepared/(0|[1-9][0-9]*)/id',path)
        if not match or row['key']!='spellcasting:preparation:'+uuid+':'+match[1][4:]+':'+match[2]:return False
        typ='spell'
    else:return False
    if (not r['present'] or not local_id) and value.get('status')!='missing':return False
    return target(typ,local_id if value.get('status')=='resolved' else None)


INVENTORY_LIMIT = ['stored_inventory_not_effective_benefits']
# PF2e-specific PhysicalSystemSource8.6.1 projection, pinned physical schema above.
INVENTORY_PHYSICAL = {'/system/'+p:(c,k,n) for p,c,k,n in (
 ('level/value','item_level','number',False),('quantity','quantity','number',False),
 ('baseItem','base_item_code','string',True),('size','size_code','string',False),
 ('bulk/value','source_bulk','number',False),('hp/value','current_item_hit_points','number',False),
 ('hp/max','source_maximum_item_hit_points','number',False),('hardness','source_hardness','number',False),
 ('price/value/pp','price_platinum','number',False),('price/value/gp','price_gold','number',False),
 ('price/value/sp','price_silver','number',False),('price/value/cp','price_copper','number',False),
 ('price/per','price_per_quantity','number',False),('price/sizeSensitive','price_size_sensitive','boolean',False),
 ('equipped/carryType','carry_type_code','string',False),('equipped/inSlot','in_slot','boolean',False),
 ('equipped/handsHeld','hands_held','number',False),('equipped/invested','investment_state','boolean',True),
 ('containerId','container_local_id','string',True),('material/type','material_type_code','string',True),
 ('material/grade','material_grade_code','string',True),('identification/status','identification_status','string',False),
 ('identification/unidentified/name','unidentified_name','string',False),
 ('identification/unidentified/img','unidentified_image','string',False),('temporary','temporary_item','boolean',False),
 ('usage/value','usage_code','string',False),
)}


def _inventory_physical(row, identity):
    """PF2e-specific8.6.1 inventory shared physical leaves and attachment metadata.

    Enforce exact persisted field projection before reusing Item path validation;
    unidentified prose, effective benefits and serialized document UUIDs excluded.
    Schema: pinned PhysicalSystemSource and concrete overrides linked above.
    """
    raw=row['raw'][0];path=raw['path'];spec=INVENTORY_PHYSICAL.get(path)
    limits=['source_only_no_effective_calculation']
    if path=='/system/usage/value':limits=[]
    if path=='/system/subitems':
        spec=('serialized_attachments','array',False)
        limits=['serialized_sources_not_embedded_documents']
    match=re.fullmatch(r'/system/subitems/(0|[1-9][0-9]*)/(_id|name|type)',path)
    if match:
        spec=({'_id':'attachment_local_id','name':'attachment_name','type':'attachment_type_code'}[match[2]],'string',False)
        limits=['serialized_source_not_document','attachment_interpretation_pending']
    if spec is None or row['provenance']['limitations']!=limits:return False
    concept,kind,nullable=spec;value=raw.get('value')
    if row['mapped']!=dict(concept=concept,value=value,unit=None) or type(row['mapped']['value']) is not type(value):return False
    if raw['present'] and not (value is None and nullable):
        if not {'number':type(value) in (int,float) and math.isfinite(value), 'string':type(value) is str,
                'boolean':type(value) is bool,'array':type(value) is list and not value}[kind]:return False
    return _record(row,['source'],identity)


def _actor_inventory_record(row, identity):
    """PF2e-specific8.6.1 Actor inventory source graph with same-owner identities.

    PhysicalSystemSource containerId and WeaponSystemSource selectedAmmoId are
    persisted claims, not access, equipped effects, Bulk or ammunition eligibility.
    https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'}:return False
    raw=row['raw'];mapped=row['mapped'];provenance=row['provenance']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['unit'] is not None:return False
    if type(provenance) is not dict or set(provenance)!={'contributors','mapping','limitations'}:return False
    for r in raw:
        if type(r) is not dict or not {'document_uuid','path','present','basis'}<=set(r) or not set(r)<={'document_uuid','path','present','basis','value'}:return False
        if r['basis']!='source' or type(r['path']) is not str or type(r['present']) is not bool or r['present']!=('value' in r):return False
    if provenance['contributors']!=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]:return False
    if row['kind']=='field':
        if len(raw)!=1 or provenance['mapping']!='pf2e.physical.source.v1':return False
        r=raw[0];uuid=r['document_uuid'];path=r['path']
        for typ in PHYSICAL_TYPES:
            if row['key']=='inventory:source:'+typ+':'+str(uuid)+':'+path:
                if not _casting_owned(uuid,identity):return False
                return _inventory_physical(dict(row,section='source',key='source:'+path),dict(identity,document_name='Item',uuid=uuid,type=typ))
        return False
    if row['kind']!='relationship' or provenance['mapping']!='pf2e.actor.inventory-source.v1' or provenance['limitations']!=INVENTORY_LIMIT:return False
    value=mapped['value']
    if type(value) is not dict:return False
    if row['key']=='inventory:scope':
        return raw==[] and mapped['concept']=='inventory_scope' and value in [dict(status=x,target_uuid=None) for x in ('empty','denied')]
    def target(types, local_id=None, cycle=False):
        """PF2e-specific detached same-owner physical Item identity, token retained."""
        expected={'status','target_uuid','document_name','type','name','name_truncated'}
        if cycle:expected.add('cycle')
        if identity['instance'] is not None:expected.add('token_uuid')
        if set(value)!=expected or value['status']!='resolved' or value['document_name']!='Item' or value['type'] not in types:return False
        if not _casting_owned(value['target_uuid'],identity) or type(value['name']) is not str or len(value['name'])>256 or type(value['name_truncated']) is not bool:return False
        if cycle and type(value['cycle']) is not bool:return False
        if local_id is not None and value['target_uuid']!=identity['uuid']+'.Item.'+local_id:return False
        return identity['instance'] is None or value['token_uuid']==identity['instance']['token_uuid']
    if mapped['concept'] in ('inventory_item','inventory_kit_definition'):
        kit=mapped['concept']=='inventory_kit_definition'
        types={'kit'} if kit else PHYSICAL_TYPES
        label='kit' if kit else 'item'
        if len(raw)!=2 or [r['path'] for r in raw]!=['/name','/type']:return False
        uuid=raw[0]['document_uuid']
        return _casting_owned(uuid,identity) and row['key']=='inventory:'+label+':'+uuid and all(r['document_uuid']==uuid and r['present'] for r in raw) and type(raw[0]['value']) is str and raw[1]['value'] in types and value.get('target_uuid')==uuid and value.get('type')==raw[1]['value'] and value.get('name')==raw[0]['value'][:256] and value.get('name_truncated')==(len(raw[0]['value'])>256) and target(types)
    if len(raw)!=1:return False
    r=raw[0];uuid=r['document_uuid'];local_id=r.get('value')
    if not _casting_owned(uuid,identity) or r['present'] and local_id is not None and type(local_id) is not str:return False
    container=mapped['concept']=='inventory_container'
    if container:
        if row['key']!='inventory:container:'+uuid or r['path']!='/system/containerId':return False
    elif mapped['concept']=='inventory_selected_ammunition':
        if row['key']!='inventory:ammunition:'+uuid or r['path']!='/system/selectedAmmoId':return False
    else:return False
    if value.get('status')=='resolved':return bool(local_id) and target({'backpack'} if container else {'ammo','weapon'},local_id,container)
    expected={'status','target_uuid'}|({'cycle'} if container else set())
    if set(value)!=expected or value['target_uuid'] is not None or value['status'] not in ('missing','denied','unsupported'):return False
    if container and type(value['cycle']) is not bool:return False
    if container and value['cycle'] and value['status']!='unsupported':return False
    return value['status']=='missing' if not local_id else True



BUILD_TYPES = {'ancestry','heritage','background','class','deity','feat','lore'}


def _actor_build_record(row, identity):
    """PF2e-specific character Build, tested against PF2e8.6.1 persisted Items.

    Reuse pinned typed source contracts above, never prepared benefits. Every
    transferred leaf carries its own persisted donor type for independent pages.
    Grant flags follow item/base/data/system.ts at pinned revision
    28d9d156f252d084371d994dc359509b49eadf18; agreement is stored evidence only.
    """
    if identity['type']!='character' or set(row)!={'key','section','kind','raw','mapped','provenance'}:return False
    raw=row['raw'];mapped=row['mapped'];p=row['provenance']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'} or mapped['unit'] is not None:return False
    if type(p) is not dict or set(p)!={'contributors','mapping','limitations'}:return False
    for r in raw:
        if type(r) is not dict or not {'document_uuid','path','present','basis'}<=set(r) or not set(r)<={'document_uuid','path','present','basis','value'}:return False
        if r['basis']!='source' or type(r['path']) is not str or type(r['present']) is not bool or r['present']!=('value' in r) or not _casting_owned(r['document_uuid'],identity):return False
    contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in raw]
    if p['contributors']!=contributors:return False
    value=mapped['value']
    def target(v, uuid=None):
        fields={'status','target_uuid','document_name','type','name','name_truncated'}
        if identity['instance'] is not None:fields.add('token_uuid')
        return (type(v) is dict and set(v)==fields and v['status']=='resolved' and v['document_name']=='Item'
                and v['type'] in ITEM_TYPES-{'affliction'} and _casting_owned(v['target_uuid'],identity)
                and (uuid is None or v['target_uuid']==uuid) and type(v['name']) is str and len(v['name'])<=256
                and type(v['name_truncated']) is bool and (identity['instance'] is None or v['token_uuid']==identity['instance']['token_uuid']))
    if row['key']=='build:scope':
        return row['kind']=='relationship' and raw==[] and mapped['concept']=='build_scope' and value in [dict(status=s,target_uuid=None) for s in ('empty','denied')] and p['mapping']=='pf2e.build.identity.v1' and p['limitations']==['owned_document_not_effective_benefit']
    if len(raw)<2:return False
    uuid=raw[0]['document_uuid']
    if mapped['concept']=='build_item':
        return (row['kind']=='relationship' and row['key']=='build:item:'+uuid and len(raw)==2
                and [r['path'] for r in raw]==['/name','/type'] and all(r['present'] and r['document_uuid']==uuid for r in raw)
                and type(raw[0]['value']) is str and raw[1]['value'] in ITEM_TYPES-{'affliction'} and target(value,uuid)
                and value['type']==raw[1]['value'] and value['name']==raw[0]['value'][:256] and value['name_truncated']==(len(raw[0]['value'])>256)
                and p['mapping']=='pf2e.build.identity.v1' and p['limitations']==['owned_document_not_effective_benefit'])
    context,r=raw[:2];typ=context.get('value');path=r['path']
    if context['path']!='/type' or not context['present'] or typ not in BUILD_TYPES or r['document_uuid']!=uuid:return False
    donor=dict(identity,document_name='Item',uuid=uuid,type=typ,actor=dict(uuid=identity['uuid'],type='character'))
    if row['kind']=='field':
        if len(raw)!=2 or row['key']!='build:source:'+uuid+':'+path or path in SOURCE_PATHS:return False
        source=dict(row,section='source',key='source:'+path,raw=[r],provenance=dict(p,contributors=contributors[1:]))
        if path.startswith(('/flags/pf2e/itemGrants','/flags/pf2e/grantedBy')):
            if p['mapping']!='pf2e.build.grants.v1' or p['limitations']!=['stored_grant_claim_not_active_benefit'] or not path.startswith(('/flags/pf2e/itemGrants','/flags/pf2e/grantedBy')):return False
            source['mapped']=dict(mapped,concept='feat_'+mapped['concept'])
            source['provenance']=dict(source['provenance'],mapping='pf2e.feat.source.v1',limitations=['feat_source_not_effective_benefit'])
            return _feat_record(source,donor)
        validators={'ancestry':_ancestry_record,'heritage':_heritage_record,'background':_background_record,'class':_class_record,'deity':_deity_record,'feat':_feat_record,'lore':_lore_record}
        return _record(source,['source'],donor) and validators[typ](source,donor)
    if row['kind']!='relationship' or row['key']!='build:claim:'+uuid+':'+path or p['mapping']!='pf2e.build.claim.v1' or p['limitations']!=['persisted_claim_not_causality_or_active_benefit'] or type(value) is not dict:return False
    outgoing=re.fullmatch(r'/flags/pf2e/itemGrants/([^/]*)/id',path)
    incoming=path=='/flags/pf2e/grantedBy/id'
    if not (outgoing and re.search(r'~(?![01])',outgoing[1]) is None or incoming):return False
    if mapped['concept']!=('build_granted_by_claim' if incoming else 'build_grant_claim'):return False
    local=r.get('value')
    if r['present'] and type(local) is not str:return False
    reciprocity=value.get('reciprocity');v={k:v for k,v in value.items() if k!='reciprocity'}
    if v.get('status')!='resolved':
        return len(raw)==2 and reciprocity=='not_evaluated' and v in [dict(status=s,target_uuid=None) for s in ('missing','denied','unsupported','unverified')] and (bool(local) or v['status']=='missing')
    if not local or not target(v,identity['uuid']+'.Item.'+local):return False
    if incoming:return len(raw)==2 and reciprocity=='not_evaluated'
    if len(raw)!=3:return False
    witness=raw[2]
    if witness['document_uuid']!=v['target_uuid']:return False
    if witness['path']=='/flags/pf2e/grantedBy/id':
        if not witness['present']:expected='absent'
        elif type(witness['value']) is str:expected='agree' if witness['value']==uuid.rsplit('.Item.',1)[1] else 'disagree'
        else:return False
    elif witness['path']=='/flags/pf2e/grantedBy' and (not witness['present'] or witness['value'] is None):expected='absent'
    else:return False
    return reciprocity==expected


def _build_section(records, section, identity):
    """PF2e-specific character8.6.1 stored Build diagnostics and page consistency.

    Repeated persisted donor/path witnesses and resolved identity metadata must
    agree within a page. Independently paged donors remain valid; the browser's
    revalidated snapshot revision establishes consistency between pages.
    """
    rows=[r for r in records if r['section']=='build']
    if identity['type']!='character':return not rows and section['status']=='unsupported'
    allowed={'pagination','build_items_denied','unsupported_selection_values'}|{'build_grant_target_'+s for s in ('missing','denied','unsupported','unverified')}
    reasons=set(section['reasons'])
    if not reasons<=allowed or section['status']!=('partial' if reasons else 'complete'):return False
    required=set();witnesses={};identities={}
    def agrees(table, key, value):
        """PF2e-specific Build evidence comparison preserves JSON scalar types."""
        signature=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False)
        if key in table:return table[key]==signature
        table[key]=signature
        return True
    for row in rows:
        concept=row['mapped']['concept'];v=row['mapped']['value']
        for raw in row['raw']:
            uuid=raw['document_uuid'];path=raw['path']
            if not agrees(witnesses,(uuid,path),[raw['present'],raw.get('value')]):return False
            if raw['present'] and path=='/type':
                if not agrees(identities,(uuid,'type'),raw['value']):return False
            if raw['present'] and path=='/name':
                name=raw['value']
                if not agrees(identities,(uuid,'name'),[name[:256],len(name)>256]):return False
        if concept in ('build_item','build_grant_claim','build_granted_by_claim') and v['status']=='resolved':
            uuid=v['target_uuid']
            if not agrees(identities,(uuid,'type'),v['type']):return False
            if not agrees(identities,(uuid,'name'),[v['name'],v['name_truncated']]):return False
        if concept=='build_scope' and v['status']=='denied':required.add('build_items_denied')
        if concept in ('build_grant_claim','build_granted_by_claim') and row['raw'][1].get('value') and v['status']!='resolved':required.add('build_grant_target_'+v['status'])
    return required<=reasons


def _inventory_section(records, section):
    """PF2e-specific8.6.1 inventory diagnostics cannot claim complete benefits.

    Enforce source graph diagnostics on each page; omitted records on other pages
    may explain additional reasons, so only present evidence mandates reasons.
    """
    reasons=section['reasons']
    allowed={'pagination','containment_cycle','inventory_items_denied',
             'book_interpretation_pending','kit_interpretation_pending'}
    allowed.update(prefix+status for prefix in ('container_parent_','selected_ammunition_') for status in ('missing','denied','unsupported'))
    if not set(reasons)<=allowed or section['status']!=('partial' if reasons else 'complete'):return False
    required=set()
    for row in records:
        if row['section']!='inventory':continue
        concept=row['mapped']['concept'];value=row['mapped']['value']
        if concept=='inventory_kit_definition':required.add('kit_interpretation_pending')
        if concept=='inventory_item' and value.get('type')=='book':required.add('book_interpretation_pending')
        if concept=='inventory_scope' and value.get('status')=='denied':required.add('inventory_items_denied')
        if concept in ('inventory_container','inventory_selected_ammunition'):
            if value.get('cycle'):required.add('containment_cycle')
            if row['raw'][0].get('value') and value['status']!='resolved':
                required.add(('container_parent_' if concept=='inventory_container' else 'selected_ammunition_')+value['status'])
    return required<=set(reasons)


def _actor_current_spec(path, actor_type):
    """PF2e-specific character/NPC8.6.1 transformed document-data primitives.

    Uses CreatureSystemData/CharacterSystemData, never sheet/getter state:
    https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts
    Public toObject(false) extraction is distinct from persisted source and
    does not establish target-context modifiers. Tested boundary: core14.369.
    """
    if actor_type not in ('character','npc') or type(path) is not str:return None
    match=re.fullmatch(r'/system/abilities/(str|dex|con|int|wis|cha)/(mod|base)',path)
    if match:return 'number' if match[2]=='mod' or actor_type=='character' else None
    if path in ('/system/attributes/ac/value',*(f'/system/attributes/hp/{key}' for key in ('value','max','temp'))):return 'number'
    if path in ('/system/attributes/ac/breakdown','/system/attributes/ac/details'):return 'string'
    match=re.fullmatch(r'/system/(saves/(fortitude|reflex|will)|perception)/(value|totalModifier|breakdown|rank|vision)',path)
    if match:
        leaf=match[3]
        if leaf=='vision':return 'boolean' if match[1]=='perception' else None
        if leaf=='rank':return 'rank' if match[1]=='perception' or actor_type=='character' else None
        return 'string' if leaf=='breakdown' else 'number'
    match=re.fullmatch(r'/system/movement/speeds/(land|burrow|climb|fly|swim|travel)(?:/(value|base|type|source))?',path)
    if match:
        mode,leaf=match.groups()
        if leaf is None:return 'null' if mode in ('burrow','climb','fly','swim') else None
        return {'value':'number','base':'number','type':mode,'source':'nullable_string'}[leaf]
    return None


def _actor_current_concept(path):
    """PF2e-specific book concepts for _actor_current_spec's transformed leaves."""
    keys=path.removeprefix('/system/').split('/')
    group,key,*rest=keys
    leaf=rest[0] if rest else None
    if group=='abilities':return f"current_attribute_{'base_' if leaf=='base' else ''}modifier_{key}"
    if group=='attributes':
        return ({'value':'current_armor_class','breakdown':'current_armor_class_breakdown','details':'current_armor_class_exception_notes'} if key=='ac' else {'value':'current_hit_points','max':'current_maximum_hit_points','temp':'current_temporary_hit_points'})[leaf]
    if group=='saves':return 'current_'+key+'_save_'+{'value':'modifier','totalModifier':'total_modifier','breakdown':'breakdown','rank':'proficiency_rank'}[leaf]
    if group=='perception':return {'value':'current_perception_modifier','totalModifier':'current_perception_total_modifier','breakdown':'current_perception_breakdown','vision':'current_standard_vision','rank':'current_perception_proficiency_rank'}[key]
    return 'current_'+leaf+'_'+('movement' if len(rest)==1 else {'value':'speed','base':'base_speed','type':'movement_type','source':'movement_source_label'}[rest[1]])


def _creature_predicate(value):
    """PF2e-specific8.6.1 bounded RawPredicate data, never evaluated.

    system/predication.ts declares the closed operator grammar. Root depth0,
    depth8 and 512 total array/object/primitive nodes; text is at most6000 UTF-16
    units. No source execution, arbitrary keys or boolean operands are admitted.
    https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/predication.ts
    """
    nodes=0
    def enter(depth):
        nonlocal nodes
        nodes+=1
        if depth>8 or nodes>512:raise ValueError('Predicate bound')
    def text(v):return type(v) is str and len(v.encode('utf-16-le',errors='surrogatepass'))//2<=6000
    def array(v,depth,visit):
        enter(depth)
        return type(v) is list and len(v)<=512 and all(visit(child,depth+1) for child in v)
    def operand(v,depth):
        enter(depth)
        return text(v) or type(v) in (int,float) and math.isfinite(v)
    def statement(v,depth):
        enter(depth)
        if type(v) is str:return text(v) and bool(v)
        if type(v) is not dict:return False
        if set(v)=={'if','then'}:return statement(v['if'],depth+1) and statement(v['then'],depth+1)
        if len(v)!=1:return False
        key=next(iter(v));child=v[key]
        if key in ('eq','gt','gte','lt','lte'):
            return type(child) is list and len(child)==2 and array(child,depth+1,operand) and type(child[0]) is str
        if key in ('and','or','nand','nor','xor','iff'):return array(child,depth+1,statement)
        return key=='not' and statement(child,depth+1)
    try:return array(value,0,statement)
    except (ValueError,RecursionError):return False


def _creature_current_spec(path):
    """PF2e-specific8.6.1 transformed senses/languages/IWR allowlist.

    CreaturePerceptionData/CreatureLanguagesData and ActorAttributes IWR types:
    https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor
    Only own serialized data is represented; no getters or IWR methods adopted.
    """
    if type(path) is not str:return None
    if path=='/system/perception/senses':return 'current_senses','collection'
    match=re.fullmatch(r'/system/perception/senses/(0|[1-9][0-9]*)/(type|acuity|range|source|label)',path)
    if match and int(match[1])<200:return 'current_sense_'+match[2],{'type':'string','acuity':'acuity','range':'range','source':'nullable_string','label':'nullable_string'}[match[2]]
    if path=='/system/details/languages/value':return 'current_languages','collection'
    if path=='/system/details/languages/details':return 'current_language_details','string'
    match=re.fullmatch(r'/system/details/languages/value/(0|[1-9][0-9]*)',path)
    if match and int(match[1])<200:return 'current_language_code','actual_string'
    match=re.fullmatch(r'/system/attributes/(immunities|weaknesses|resistances)(?:/(0|[1-9][0-9]*)(?:/(.*))?)?',path)
    if not match:return None
    group,index,leaf=match.groups();singular={'immunities':'immunity','weaknesses':'weakness','resistances':'resistance'}[group]
    if index is None:return 'current_'+group,'collection'
    if int(index)>=200:return None
    if leaf in ('type','source','label','definition') or leaf=='value' and group!='immunities':
        return 'current_'+singular+'_'+leaf,{'type':'string','source':'nullable_string','label':'string','definition':'nullable_predicate','value':'number'}[leaf]
    sub=re.fullmatch(r'(exceptions|doubleVs)(?:/(0|[1-9][0-9]*)(?:/(label|definition))?)?',leaf or '')
    if not sub or sub[1]=='doubleVs' and group!='resistances':return None
    which,position,child=sub.groups();prefix='current_'+singular+'_'+('exception' if which=='exceptions' else 'double_vs')
    if position is None:return ('current_'+singular+'_exceptions' if which=='exceptions' else prefix),'collection'
    if int(position)>=200:return None
    return prefix+'_'+(child or 'type'),{'label':'string','definition':'predicate',None:'actual_string'}[child]


def _creature_current_record(row,identity):
    """PF2e-specific8.6.1 exact serialized creature supplements, not targeting."""
    if identity['type'] not in ('character','npc') or set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='field' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='transformed' or type(raw['present']) is not bool or raw['present']!=('value' in raw):return False
    path=raw['path'];spec=_creature_current_spec(path)
    if spec is None or row['key']!='statistics:'+path:return False
    concept,kind=spec;value=raw.get('value')
    if not raw['present'] and kind=='actual_string':return False
    if raw['present']:
        text=type(value) is str and len(value.encode('utf-16-le',errors='surrogatepass'))//2<=6000
        valid={'string':text,'actual_string':text,'nullable_string':value is None or text,
               'acuity':text and value in ('precise','imprecise','vague'),
               'number':type(value) in (int,float) and math.isfinite(value),
               'range':type(value) in (int,float) and math.isfinite(value) or type(value) is dict and value=={'$number':'Infinity'},
               'collection':type(value) is list and value==[],
               'predicate':_creature_predicate(value),'nullable_predicate':value is None or _creature_predicate(value)}
        if not valid[kind]:return False
    expected=dict(concept=concept,value=None if kind=='collection' else value,unit=None)
    if json.dumps(row['mapped'],sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return False
    return row['provenance']==dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.actor.creature-current.v1',limitations=['serialized_creature_details_not_target_context'])


def _creature_current_page(records,section):
    """PF2e-specific8.6.1 same-page collection/discriminator consistency."""
    fields={r['raw'][0]['path']:r['raw'][0] for r in records if r['section']=='statistics' and r['provenance']['mapping']=='pf2e.actor.creature-current.v1'}
    reasons=set(section['reasons'])
    for path,raw in fields.items():
        concept,kind=_creature_current_spec(path)
        if kind in ('collection','actual_string'):
            if any(child.startswith(path+'/') for child in fields):return False
        match=re.match(r'(/system/attributes/(?:immunities|weaknesses|resistances)/(?:0|[1-9][0-9]*))/',path)
        if match:
            if 'conditional_iwr_not_evaluated' not in reasons:return False
            if path==match[1]+'/definition':
                typ=fields.get(match[1]+'/type')
                if typ is not None and (not typ['present'] or typ['value']!='custom'):return False
                if not raw['present'] and 'custom_iwr_definition_unavailable' not in reasons:return False
    return True


def _familiar_current_spec(path):
    """PF2e-specific8.6.1 familiar transformed primitive allowlist.

    FamiliarSystemData declares CreatureAttributes, CreatureSaves, Perception,
    CreatureMovementData and SkillData. Source excludes these derived leaves.
    https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts
    No independent attributes, attacks, resources or proficiency ranks admitted.
    """
    if type(path) is not str:return None
    if path=='/system/skills':return ('current_skill_collection','collection')
    skill=_skill_current_spec(path,'npc')
    if skill is not None and skill[0] in ('current_skill_slug','current_skill_label','current_skill_value','current_skill_total_modifier','current_skill_dc','current_skill_breakdown'):return skill
    if path.startswith('/system/skills/'):return None
    if path.startswith('/system/abilities/') or path.endswith('/rank'):return None
    kind=_actor_current_spec(path,'npc')
    return (_actor_current_concept(path),kind) if kind is not None else None


def _familiar_current_record(row, identity):
    """PF2e-specific8.6.1 familiar values serialized after master admission.

    Exact source master provenance delegates the existing master contract;
    transformed familiar primitives follow _familiar_current_spec, never local
    master-derived arithmetic. Page-level master/reason consistency is separate.
    """
    if row['key']=='statistics:familiar_master':
        if len(row['raw'])!=2 or type(row['provenance']) is not dict or row['provenance'].get('contributors')!=[{k:r[k] for k in ('document_uuid','path','basis')} for r in row['raw']]:return False
        ability=row['raw'][1]
        if type(ability) is not dict or not {'document_uuid','path','present','basis'}<=set(ability) or not set(ability)<={'document_uuid','path','present','basis','value'}:return False
        if ability['document_uuid']!=identity['uuid'] or ability['path']!='/system/master/ability' or ability['basis']!='source' or type(ability['present']) is not bool or ability['present']!=('value' in ability):return False
        if ability['present'] and ability['value'] is not None and type(ability['value']) is not str:return False
        narrowed=dict(row,key='identity:familiar_master',section='identity',raw=row['raw'][:1],provenance=dict(row['provenance'],contributors=row['provenance']['contributors'][:1]))
        return _familiar_relationship(narrowed,identity)
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='field' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='transformed' or type(raw['present']) is not bool or raw['present']!=('value' in raw):return False
    path=raw['path'];spec=_familiar_current_spec(path)
    if spec is None or row['key']!='statistics:'+path:return False
    concept,kind=spec;value=raw.get('value')
    if raw['present']:
        valid={'number':type(value) in (int,float) and math.isfinite(value),'string':type(value) is str,
               'boolean':type(value) is bool,'null':value is None,'nullable_string':value is None or type(value) is str,
               'collection':type(value) is dict and value=={}}
        if not valid.get(kind,type(value) is str and value==kind):return False
    expected=dict(concept=concept,value=None if kind=='collection' else value,unit=None)
    if json.dumps(row['mapped'],sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return False
    return row['provenance']==dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.familiar.current.v1',limitations=['serialized_familiar_value_not_recalculated'])


def _familiar_current_section(records, section):
    """PF2e-specific8.6.1 same-page familiar/master admission diagnostics.

    Master witnesses can be on another page. Explicit unresolved section reasons
    never permit transformed rows, and available source/current master claims
    must agree. No inference is made from an off-page absent discriminator.
    """
    rows=[r for r in records if r['section']=='statistics'];current=[r for r in rows if r['provenance']['mapping']=='pf2e.familiar.current.v1']
    masters=[r for r in records if r['key'] in ('statistics:familiar_master','identity:familiar_master')]
    reasons=set(section['reasons'])
    if section['status']!='partial':return False
    if masters:
        first=masters[0]
        if any(r['raw'][0]!=first['raw'][0] or r['mapped']!=first['mapped'] for r in masters[1:]):return False
        claim=first['raw'][0]
        for row in records:
            for raw in row['raw']:
                if raw['path']=='/system/master/id' and raw['basis']=='source' and raw!=claim:return False
        ability=next((r['raw'][1] for r in masters if r['key']=='statistics:familiar_master'),None)
        if ability is not None:
            for row in records:
                for raw in row['raw']:
                    if raw['path']=='/system/master/ability' and raw['basis']=='source' and raw!=ability:return False
        status=first['mapped']['value']['status']
        if status!='resolved':return not current and reasons-{'pagination'}=={'familiar_master_'+status}
    unresolved=reasons-{'pagination'}
    if any(reason.startswith('familiar_master_') for reason in unresolved):
        allowed={'familiar_master_'+s for s in ('missing','unassociated','denied','unsupported','unverified')}
        return not current and not masters and len(unresolved)==1 and unresolved<=allowed
    if 'other_statistics_pending' not in reasons or not reasons<={'other_statistics_pending','current_fields_unavailable','familiar_item_linked_skills_unsupported','pagination'}:return False
    fields=[r['raw'][0] for r in current]
    if any(not r['present'] for r in fields) and 'current_fields_unavailable' not in reasons:return False
    for mode in ('burrow','climb','fly','swim'):
        path='/system/movement/speeds/'+mode
        if any(r['path']==path and (not r['present'] or r['value'] is None) for r in fields):
            if any(r['path'].startswith(path+'/') and r['present'] for r in fields):return False
    if any(r['path']=='/system/skills' for r in fields) and any(r['path'].startswith('/system/skills/') for r in fields):return False
    return True


def _actor_current_record(row, identity):
    """PF2e-specific current character/NPC leaves; exact transformed provenance.

    Schema/version and source-versus-derived restrictions: _actor_current_spec.
    Familiar master-derived values remain unsupported pending their own contract.
    """
    if set(row)!={'key','section','kind','raw','mapped','provenance'} or row['kind']!='field' or len(row['raw'])!=1:return False
    raw=row['raw'][0]
    if type(raw) is not dict or not {'document_uuid','path','present','basis'}<=set(raw) or not set(raw)<={'document_uuid','path','present','basis','value'}:return False
    if raw['document_uuid']!=identity['uuid'] or raw['basis']!='transformed' or type(raw['present']) is not bool or raw['present']!=('value' in raw):return False
    path=raw['path'];kind=_actor_current_spec(path,identity['type'])
    if kind is None or row['key']!='statistics:'+path:return False
    value=raw.get('value')
    if raw['present']:
        valid={'number':type(value) in (int,float) and math.isfinite(value),
               'string':type(value) is str,'boolean':type(value) is bool,
               'rank':type(value) is int and 0<=value<=4,'null':value is None,
               'nullable_string':value is None or type(value) is str}
        if not valid.get(kind,type(value) is str and value==kind):return False
    expected={'rank':value,'label':LORE_RANKS[value]} if raw['present'] and kind=='rank' else value
    mapped=row['mapped']
    if type(mapped) is not dict or set(mapped)!={'concept','value','unit'}:return False
    if mapped!=dict(concept=_actor_current_concept(path),value=expected,unit=None):return False
    if type(mapped['value']) is not type(expected):return False
    if kind=='rank' and raw['present'] and type(mapped['value']['rank']) is not int:return False
    return row['provenance']==dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.actor.current.v1',limitations=['serialized_current_value_not_target_context'])


def _current_section(records, section, identity):
    """PF2e-specific character/NPC partial current-statistics diagnostics.

    Compare only transformed statistics on the current page: persisted source
    at the same path may legitimately differ. A missing/null movement mode
    cannot simultaneously provide a present descendant in this snapshot.
    """
    rows=[row for row in records if row['section']=='statistics']
    if identity['type']=='familiar':return _familiar_current_section(records,section)
    if identity['type'] not in ('character','npc'):
        return not rows and section['status']=='unsupported' and section['reasons']==['master_current_contract_pending']
    raw=[row['raw'][0] for row in rows]
    for mode in ('burrow','climb','fly','swim'):
        path='/system/movement/speeds/'+mode
        if any(field['path']==path and (not field['present'] or field['value'] is None) for field in raw):
            if any(field['path'].startswith(path+'/') and field['present'] for field in raw):return False
    reasons=set(section['reasons'])
    return (section['status']=='partial' and 'other_statistics_pending' in reasons
            and reasons<={'other_statistics_pending','current_fields_unavailable','conditional_iwr_not_evaluated','custom_iwr_definition_unavailable','pagination'}
            and _creature_current_page(records,section)
            and (not any(not row['raw'][0]['present'] for row in rows) or 'current_fields_unavailable' in reasons))


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
    if identity['document_name']=='Actor' and identity['type']=='familiar' and row['section'] in ('identity','abilities') and row['key']!='identity':
        return _familiar_relationship(row,identity)
    # PF2e-specific transformed statistics are admitted only at this narrow gate.
    if identity['document_name']=='Actor' and row['section']=='statistics':
        if identity['type']=='familiar':return _familiar_current_record(row,identity)
        if type(row['provenance']) is dict and row['provenance'].get('mapping')=='pf2e.actor.creature-current.v1':return _creature_current_record(row,identity)
        return _actor_current_record(row,identity)
    if identity['document_name']=='Item' and identity['type']=='feat' and row['section']=='relationships':
        return _feat_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='deity' and row['section']=='relationships':
        return _deity_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='class' and row['section']=='relationships':
        return _class_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='heritage' and row['section']=='relationships':
        return _heritage_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='background' and row['section']=='relationships':
        return _background_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='ancestry' and row['section']=='relationships':
        return _ancestry_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='kit' and row['section']=='relationships':
        return _kit_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='book' and row['section']=='relationships':
        return _book_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='backpack' and row['section']=='relationships':
        return _container_relationship(row,identity)
    if identity['document_name']=='Actor' and row['section']=='spellcasting':
        return _actor_casting_record(row,identity)
    if identity['document_name']=='Actor' and row['section']=='state':
        return _actor_state_record(row,identity)
    if identity['document_name']=='Actor' and row['section']=='skills' and type(row['provenance']) is dict and row['provenance'].get('mapping') in ('pf2e.actor.skills-current.v1','pf2e.actor.skills-lore.v1'):
        return _actor_skill_current_record(row,identity)
    if identity['document_name']=='Actor' and row['section']=='inventory':
        return _actor_inventory_record(row,identity)
    if identity['document_name']=='Actor' and row['section']=='build':
        return _actor_build_record(row,identity)
    for raw in row['raw']:
        if type(raw) is not dict or not {'document_uuid', 'path', 'present', 'basis'} <= set(raw) or not set(raw) <= {'document_uuid', 'path', 'present', 'basis', 'value'}:
            return False
        if not _contributor({k: raw[k] for k in ('document_uuid', 'path', 'basis')}, identity) or type(raw['present']) is not bool or raw['present'] != ('value' in raw) or (raw['present'] and raw['value'] is not None and type(raw['value']) not in (str, bool, int, float) and not (_empty_source_array(raw['path'], identity) and raw['value'] == []) and not (_empty_source_object(raw['path'], identity) and raw['value'] == {})):
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
        if not (identity['type'] == 'weapon' and row['section'] == 'relationships') and type(mapped) is dict and isinstance(mapped.get('value'), (dict, list)) and not (mapped.get('value') == [] and all(_empty_source_array(raw['path'], identity) for raw in row['raw'])) and not (mapped.get('value') == {} and all(_empty_source_object(raw['path'], identity) for raw in row['raw'])):
            return False
    if type(mapped) is not dict or set(mapped) != {'concept', 'value', 'unit'} or type(mapped['concept']) is not str or (mapped['unit'] is not None and type(mapped['unit']) is not str):
        return False
    if type(provenance) is not dict or set(provenance) != {'contributors', 'mapping', 'limitations'} or type(provenance['mapping']) is not str or not _strings(provenance['limitations']) or type(provenance['contributors']) is not list or not all(_contributor(x, identity) for x in provenance['contributors']):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'spellcastingEntry' and not _casting_entry_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'spell' and not _spell_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'weapon' and not _weapon_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'ammo' and not _ammo_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'armor' and not _armor_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'consumable' and not _consumable_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'backpack' and not _container_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'feat' and not _feat_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'deity' and not _deity_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'class' and not _class_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'heritage' and not _heritage_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'background' and not _background_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'ancestry' and not _ancestry_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'kit' and not _kit_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'book' and not _book_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'treasure' and not _treasure_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'equipment' and not _equipment_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'shield' and not _shield_record(row, identity):
        return False
    # PF2e-specific action source and named self-effect semantics stay type-scoped.
    if identity['document_name'] == 'Item' and identity['type'] == 'action' and not _action_record(row, identity):
        return False
    # PF2e-specific NPC attacks preserve authored formulas and non-UUID labels.
    if identity['document_name'] == 'Item' and identity['type'] == 'melee' and not _melee_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'condition' and not _condition_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'effect' and not _effect_record(row, identity):
        return False
    if identity['document_name'] == 'Item' and identity['type'] == 'lore' and not _lore_record(row, identity):
        return False
    if identity['document_name']=='Actor' and identity['type']=='npc' and row['section'] in ('source','description') and not _npc_record(row,identity):
        return False
    if identity['document_name']=='Actor' and identity['type']=='character' and row['section'] in ('source','description') and not _character_record(row,identity):
        return False
    if identity['document_name']=='Actor' and identity['type']=='familiar' and row['section'] in ('source','description') and not _familiar_record(row,identity):
        return False
    if identity['document_name']=='Actor' and row['section']=='description' and identity['type'] not in ('npc','character','familiar'):
        return False
    if identity['document_name'] == 'Actor' and row['section'] == 'skills' and not _lore_specialty(row, identity):
        return False
    if identity['document_name']=='Actor' and row['section'] in ('strikes','abilities') and not _npc_item_reference(row,identity):
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
                    # PF2e-specific feat recorded selections may omit unsupported values.
                    if result['identity']['document_name']=='Item' and result['identity']['type']=='feat':
                        valid = valid and all(row['name']=='source' and row['status']=='partial' for row in rows if 'unsupported_selection_values' in row['reasons'])
                    # PF2e-specific casting configuration excludes current availability.
                    if result['identity']['document_name']=='Actor':
                        valid = valid and all(row['status']=='partial' and 'availability_not_evaluated' in row['reasons'] for row in rows if row['name']=='spellcasting')
                    # PF2e-specific NPC8.6.1 Item references never claim full sections.
                    if result['identity']['document_name']=='Actor' and result['identity']['type']=='npc':
                        pending={'strikes':'other_attacks_pending','abilities':'other_abilities_pending'}
                        valid = valid and all(row['status']=='partial' and pending[row['name']] in row['reasons'] for row in rows if row['name'] in pending)
                    if result['identity']['document_name']=='Actor' and result['identity']['type']=='familiar':
                        # PF2e-specific source relationships never prove active abilities.
                        for section in rows:
                            relevant=[r for r in result['records'] if r.get('section')==section['name']]
                            if section['name']=='abilities':
                                valid = valid and section['status']=='partial' and 'other_abilities_pending' in section['reasons'] and set(section['reasons'])<={'other_abilities_pending','related_items_denied','pagination'}
                                if any(r.get('key')=='abilities:familiar:denied' for r in relevant):valid = valid and 'related_items_denied' in section['reasons']
                            if section['name']=='identity':
                                reasons=[reason for reason in section['reasons'] if reason!='pagination']
                                valid = valid and (section['status']=='complete' and section['reasons']==[] or section['status']=='partial' and (reasons==[] and 'pagination' in section['reasons'] or len(reasons)==1 and reasons[0] in ['familiar_master_'+s for s in ('missing','unassociated','denied','unsupported','unverified')]))
                                for r in relevant:
                                    if r.get('key')=='identity:familiar_master':
                                        status=r['mapped']['value']['status']
                                        valid = valid and reasons==([] if status=='resolved' else ['familiar_master_'+status])
                    valid = valid and all(_record(row, sections, result['identity']) for row in result['records']) and len({row['key'] for row in result['records']}) == len(result['records']) and _pagination(result.get('pagination'), len(result['records']), limit)
                    if valid and result['identity']['document_name']=='Item' and result['identity']['type']=='effect':
                        valid = _effect_source_page(result['records'])
                    if valid and result['identity']['document_name']=='Actor':
                        valid = valid and all(_skills_section(result['records'], row, result['identity']) for row in rows if row['name']=='skills')
                        valid = valid and all(_state_section(result['records'], row, result['identity']) for row in rows if row['name']=='state')
                        valid = valid and all(_casting_section(result['records'], row) for row in rows if row['name']=='spellcasting')
                        valid = valid and all(_inventory_section(result['records'], row) for row in rows if row['name']=='inventory')
                        valid = valid and all(_build_section(result['records'], row, result['identity']) for row in rows if row['name']=='build')
                        valid = valid and all(_current_section(result['records'], row, result['identity']) for row in rows if row['name']=='statistics')
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
    complete effective statistics is implied by an allowed type. A true effective
    flag can describe a partial delivered section: character/NPC statistics
    selects transformed primitives while other current views remain unfinished.
    Inspect entry limitations and returned section reasons. PF2e 8.6.1/core
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
    source expose common metadata and selected type-specific persisted fields.
    Known sections description/build/statistics/skills/strikes/abilities/spellcasting/inventory/
    effective can be unsupported; get_actor_types reports delivered support.
    Sections must be unique/nonempty (at most 12). PF2e character/npc/familiar only;
    other systems/versions/types give UnsupportedSystem/Version/Type errors.

    Returns contract_version/runtime/identity/revision/sections/records/pagination/
    limitations. Records retain selected raw fields, mapped concepts and provenance;
    sections distinguish partial/unsupported/not_applicable from complete. Missing
    fields differ from null/zero; source is not complete effective statistics.
    NPC source includes authored attributes, AC/saves/Perception/skills, stored HP,
    senses/languages/movement, IWR and publication. Elite/weak arithmetic is not
    applied to source. Explicit statistics reads selected transformed character/NPC
    ability modifiers (character base separately), AC, current/max/temporary HP,
    saves, Perception and six movement modes from public toObject(false).
    Each field has key statistics:<exact /system/... path>, kind field, one own
    Actor raw contributor with basis transformed, mapping pf2e.actor.current.v1,
    and limitations exactly [serialized_current_value_not_target_context].
    Mapped concepts name book concepts with current_ prefix, e.g.
    current_armor_class, current_hit_points, current_fortitude_save_modifier,
    current_perception_proficiency_rank and current_land_speed;
    unit is null and value retains the serialized primitive, except rank maps
    to {rank,label}. Missing raw values have present:false and mapped null;
    nullable movement modes preserve null rather than inventing zero speed.
    Statistics is always partial with other_statistics_pending, plus
    current_fields_unavailable when selected leaves are missing and pagination
    while more records remain. Character/NPC skills use the separate skills
    section. Character/NPC statistics additionally selects transformed senses,
    languages and immunity/weakness/resistance (IWR) details from that same public
    serializer snapshot. These field records retain statistics:<path> keys but
    mapping pf2e.actor.creature-current.v1 and exact limitation
    serialized_creature_details_not_target_context; raw/contributor basis is
    transformed and document_uuid is the selected Actor. Sense paths are
    /system/perception/senses/<index>/{type,acuity,range,source,label}; concepts are
    current_sense_<leaf>, acuity is precise/imprecise/vague, source/label may be
    null, and range is a finite number or the exact JSON object
    {"$number":"Infinity"} for positive Infinity. The same explicit object is
    retained in raw.value and mapped.value. Null never substitutes for Infinity;
    negative Infinity/NaN reject, and this encoding is allowed only for sense
    range. It does not establish unlimited detection, line of sight or targets.
    Language paths /system/details/languages/value/<index> and sibling details
    map current_language_code and current_language_details, preserving codes and
    conditional notes without interpreting communication or comprehension.
    IWR paths /system/attributes/{immunities,weaknesses,resistances}/<index> expose
    type/source/label and weakness/resistance value, with concepts
    current_{immunity,weakness,resistance}_<leaf>. Source is nullable; values are
    finite numbers, independent of damage or active applicability. Exceptions
    and resistance-only doubleVs preserve indexed string codes or custom
    /label and /definition fields. Their concepts use exception_type/label/
    definition or resistance_double_vs_type/label/definition. Main definitions
    are selected only for type custom, as own serialized Predicate data or null;
    an omitted definition adds custom_iwr_definition_unavailable and
    current_fields_unavailable. No getter, source fallback or reconstructed
    predicate fills an omitted definition. A known null remains null.
    Predicate definitions preserve closed RawPredicate JSON arrays: nonempty
    string atoms; eq/gt/gte/lt/lte with [string,string-or-finite-number];
    and/or/xor/nand/nor/iff arrays; not with one statement; or exact if/then
    statements. No operator is evaluated. Root array depth is zero; maximum
    depth8 and 512 array/object/primitive nodes, including operands and containers.
    Every selected text value is at most6000 UTF-16 units. Extra predicate keys,
    malformed operands and unsupported operators return ReadFailed.
    Empty/missing arrays have a root marker mapped to null: current_senses,
    current_languages, current_immunities/current_weaknesses/current_resistances,
    and current_<singular>_exceptions or current_resistance_double_vs. Raw
    present true/value [] differs from absent/no value. An empty predicate []
    remains mapped [], since it is definition data rather than a collection
    marker. Collections admit at most200 entries each, including each entry's
    exceptions/doubleVs, and at most24000 supplement fields. Bounds exceedance
    returns ReadFailed and is separate from page record/byte limits. Missing
    selected fields add current_fields_unavailable. Any IWR entries add
    conditional_iwr_not_evaluated; target predicates, exception applicability,
    doubled resistance and damage are never calculated. Familiar statistics
    retains its separate mapping/allowlist below. Strikes, condition/effect
    application and target-context calculations remain outside statistics.
    Explicit description returns NPC
    stored blurb, publicNotes and privateNotes only, including GM-private biography;
    default source never includes them. Familiar source preserves nullable stored
    master Character local ID/attribute code, integer nonnegative HP/temporary HP
    and optional temporary-HP source ID; these are not master-derived statistics.
    Explicit familiar description returns exact /system/details/creature/value
    text in fragments of at most6000 UTF-16 units, with ordinary absent markers.
    Familiar identity record identity:familiar_master maps concept familiar_master
    with mapping pf2e.familiar.master.v1 and limitation
    stored_master_reference_not_current_statistics. Resolved values contain status,
    target_uuid, document_name Actor, type character, name, name_truncated and
    next_call for read_actor of the actual world Character. Missing, unassociated,
    denied, unsupported and unverified references withhold target_uuid and make
    identity partial with familiar_master_<status>; no master totals are supplied.
    Familiar abilities records abilities:familiar:<owned Item UUID> map concept
    familiar_ability with mapping pf2e.familiar.ability.v1 and limitations
    owned_action_reference_not_complete_or_active_ability and
    ability_scope_requires_description. They list actual owned action Items with bounded
    source trait evidence (at most200 strings), ability_kind unclassified and
    optional token_uuid. Follow target_uuid with read_item for category/prose;
    traits and names do not establish familiar/master scope or active benefits.
    Abilities is always partial with other_abilities_pending; related_items_denied
    adds an anonymous denied marker. Explicit familiar statistics first resolves
    the actual source master ID through the permission-aware world Character
    resolver, even when identity was not requested. statistics:familiar_master
    retains the same familiar_master concept/mapping/value/limitation as identity,
    but has two exact source witnesses: /system/master/id and
    /system/master/ability, with missing/null distinctions. The latter is only
    selected configuration, never an independent attribute or modifier. Identity's
    master record keeps its original single-ID witness. Missing/unassociated/
    denied/unsupported/unverified masters produce a partial statistics section
    with familiar_master_<status>, plus pagination if needed, and no transformed
    familiar fields or serialization fallback. Denied references reveal no
    resolved metadata. Only a resolved permitted master admits public familiar
    toObject(false) values. These field records have key statistics:<exact path>,
    mapping pf2e.familiar.current.v1, one own familiar-Actor transformed
    raw/contributor, and limitation serialized_familiar_value_not_recalculated.
    The allowlist is AC value/breakdown/details; HP value/max/temp; fortitude,
    reflex and will value/totalModifier/breakdown; Perception value/totalModifier/
    breakdown/vision; and movement land/burrow/climb/fly/swim/travel with
    value/base/type/source leaves and explicit null optional mode roots. Concepts
    match the current_* character/NPC names above, without rank or attributes.
    Familiar statistics also includes ordinary SkillData slug/label/value/
    totalModifier/dc/breakdown, mapped to current_skill_<leaf> except total_modifier.
    Skill keys are JSON Pointer escaped; missing or empty /system/skills has
    concept current_skill_collection, mapped null and absent raw versus value {}.
    Skills with lore true or a nonempty itemId are entirely withheld before keys,
    labels or totals, adding familiar_item_linked_skills_unsupported; no Lore
    relationship is inferred. Resolved-master statistics stays partial with
    other_statistics_pending, current_fields_unavailable for missing selected
    leaves, the linked-skill reason when applicable, and pagination. Finite numbers
    and booleans retain serialized values; source is never a current-value fallback.
    Selected master identity/configuration and familiar values participate in
    revision checks; changed permissions/claims/values require restarting a
    stale continuation. Familiar skill maps allow at most512 own keys of1–256
    Unicode code points and at most24000 selected fields; overflow is ReadFailed.
    No master getter, preparation, local derivation, independent attributes,
    proficiency ranks, normal Strikes, attack/resource totals or complete familiar
    mechanics are inferred. Neither empty references nor source HP establishes
    complete current familiar mechanics. Default/source reads do not serialize
    transformed familiar statistics.
    Character source exposes PF2e8.6.1 recorded level, nullable manual attribute
    modifiers, identity/language codes, XP, source HP/temporary HP/stamina, skill
    ranks, selected resources and persisted build choices. Null abilities remain
    one root marker, never six zero modifiers. Skill mapped.value is {rank,label},
    with integer rank0..4 and label Untrained/Trained/Expert/Master/Legendary;
    unknown stored skill codes remain source keys, never effective check totals.
    Character source excludes derived HP maximum and focus maximum/capacity.
    Default source excludes biography prose. Explicit description returns bounded
    exact character biography and language-details text, including ordered edicts
    and anathema; empty arrays stay field markers and absent source stays absent.
    Lists/maps admit at most12000 entries. Malformed admitted source or excessive
    complexity fails ReadFailed; inspect the selected document source in Foundry
    or request identity separately. Excluded prepared properties are ignored.
    These selected-source sections do not establish full current statistics;
    integrated/effective sections remain explicitly partial or unsupported.
    Character build lists actual readable owned ancestry/heritage/background/class/
    deity/feat/Lore Items once as build_item identities, with independently paged
    typed source fields and build_grant_claim/build_granted_by_claim records.
    Each transferred field includes the donor's persisted /type and exact source
    path. Offered options and future feature definitions do not imply acquisition;
    missing linkage stays unknown, with no joins by name. Claims resolve exact
    owner-local IDs only. Resolved values include target_uuid, document_name,
    type, name, name_truncated and token_uuid in token context; follow read_item.
    Reciprocity agree/disagree/absent compares outgoing stored claims with exact
    inverse evidence; incoming and unresolved claims remain not_evaluated. This
    does not establish causality, eligibility or active benefits. Missing/denied/
    unsupported/unverified claim targets withhold target_uuid; build_scope empty
    or denied distinguishes absence from inaccessible Items. Denied Items expose
    no identities. Build is partial for denied Items, unsupported recorded selection
    values or unresolved claims; NPC/familiar Build is unsupported. Build rejects
    over 12000 owned Items or 24000 selected records with ReadFailed; narrow with
    list_actor_items/read_item. Multiple claims retain one owned benefit identity.
    Explicit skills additionally selects character/NPC transformed skill data
    from public serialization; familiar skills retain owned Lore references only
    and never request transformed data. Field keys skills:current:<JSON Pointer>
    use mapping pf2e.actor.skills-current.v1 and limitation
    serialized_current_skill_not_target_context. Each raw/contributor contains
    the selected Actor UUID, /system/skills/<escaped own map key>/<leaf> and basis
    transformed. Keys escape ~ as ~0 and / as ~1; generated keys are not document
    selectors. Common leaves slug/label/attribute/value/totalModifier/dc/breakdown/
    lore/itemId map to current_skill_<leaf>, except itemId becomes item_id and
    totalModifier becomes total_modifier. Strings remain text; attribute is one
    of str/dex/con/int/wis/cha; value/totalModifier/dc are independent finite
    numbers; lore is boolean and itemId is a nullable owner-local Item ID claim.
    Character-only rank is an integer 0–4 mapped to {rank,label} with TEML labels,
    and armor is boolean. NPC-only base/mod are independent finite numbers,
    visible is boolean and optional note is string; absent note alone does not
    add an unavailable reason. No NPC rank or conditional special/predicate
    evaluation is supplied. Absent selected fields have present false, no raw
    value and mapped null, with current_skill_fields_unavailable. An absent or
    empty skill map has /system/skills as its raw path, concept
    current_skill_collection and mapped null; raw present false differs from
    present true/value {}. Missing values never fall back to source or zero.
    A true serialized lore flag adds skills:current-lore:<escaped key>, mapping
    pf2e.actor.skills-lore.v1, concept current_skill_lore_reference and limitation
    serialized_lore_claim_not_exhaustive_owned_lore. Its two exact transformed
    contributors are that Actor's lore and itemId leaves. Resolved values contain
    status/target_uuid/document_name Item/type lore/name/name_truncated and
    token_uuid in token context; follow read_item with returned selectors. Missing
    or wrong-type claims contain only status missing/unsupported and target_uuid
    null. An unreadable linked Item withholds the entire current skill, including
    generated key/labels/totals, before one generic skills:current:denied
    relationship exposes only status denied/target_uuid null and adds
    current_skill_items_denied. This marker has the current-field mapping,
    concept current_skill_item_reference and no raw/contributors.
    Skills always remains partial with other_skills_pending; NPC current reads
    also report conditional_skill_variants_not_evaluated. Target-dependent checks,
    conditional variants, exhaustive skills and familiar/master derivation remain
    unsupported. Current selection bounds are 512 own map keys, 256 Unicode code
    points per key, 12000 owned Items and 24000 records; exceeding them returns
    ReadFailed. Page count/bytes remain independent. Default identity/source reads
    do not request current skills. Existing owned Lore source listings remain
    separate because serialized skill keys may collapse duplicate owned Items.
    Each lore_specialty mapped value has resolved target_uuid
    and token_uuid for token-context ownership; follow with read_item. Duplicate
    specialty names remain separate Items, never merged skill totals.
    NPC strikes/abilities contain actual owned melee/action Item references only:
    npc_attack_item/npc_ability_item values have resolved target_uuid and selected
    token_uuid when applicable; follow with read_item. Both sections remain partial
    with other_attacks_pending/other_abilities_pending. Permission-denied related
    Items produce a generic denied marker with null target_uuid and no selectors;
    related_items_denied is reported without exposing their names or identities.
    Spellcasting exposes owned spell/casting-entry identities, selected stored
    configuration, owner-local assignment/preparation joins and focus resources.
    casting_entry/casting_spell values resolve target_uuid and token_uuid when
    applicable; their names use persisted /name witnesses clipped to 256 Unicode
    codepoints. Immediate assignment/preparation labels use public display names
    and can differ; joins retain canonical identity and token context.
    Follow read_item. casting_spell_assignment/casting_preparation
    statuses resolved/missing/denied/unsupported/unverified/mismatched_assignment
    distinguish stored membership from invalid or inaccessible links. Repeated
    preparations retain independent slot/index keys and expended source fields.
    Contextual option relationships use mapping pf2e.actor.casting-options.v1,
    concept casting_contextual_option and response-local keys
    spellcasting:option:<spell UUID>:<entry UUID or unassigned>:<slot rank or none>:<preparation index or none>.
    mapped.value.spell is the actual resolved owned spell; entry is the same
    canonical resolved/missing/denied/unsupported assignment shape. Resolved
    identities retain target_uuid/type/name/name_truncated and token_uuid in
    token context. These option names use their persisted /name witnesses too.
    Unresolved entry objects contain only status/target_uuid null.
    mode is the stored entry mode or null. context is prepared_use,
    spontaneous_repertoire, innate_spell, focus_spell, listed_spell or
    unsupported_mode. base_rank/configured_rank, spell_auto_heighten_rank and
    entry_auto_heighten_rank preserve independent source configuration or null;
    cast_rank is always null. slot_rank/preparation_index identify each ordinary
    slot0–10 preparation position; slot0 is independent of the cantrip flag,
    and slot11 never establishes a spell rank. expended/signature/cantrip are
    recorded booleans or null. uses is an innate {value,max} pair with independently
    nullable counts, otherwise null. resource_scope is individual_preparation,
    shared_entry_slots, individual_spell_uses, shared_actor_focus or not_evaluated.
    availability is always not_evaluated. Raw witnesses and contributors are
    selected source fields; current-resource records remain separate. Mapping
    limitations are availability_not_evaluated/configured_rank_not_final_cast_rank.
    Signature flags never generate rank alternatives or establish entitlement;
    signature_alternatives_not_evaluated records that boundary. Flexible, ritual,
    item and unknown modes retain unsupported_casting_mode. Malformed preparation
    source stays partial; missing expended is null, and malformed expenditure
    values are omitted with malformed_preparation. Unresolved preparation claims
    remain separate casting_preparation records, without fabricated spell options.
    Options do not infer current availability, automatic heightening or higher-slot
    casting ranks. Familiar options can name owned spells but exclude Actor focus
    source contributors. Selection bounds are 12000 owned Item snapshots, 24000
    total preparation positions/options and 200 traits per spell; exceeding these
    returns ReadFailed. These complexity bounds are separate from page limits.
    Denied markers expose no related identity. The section remains partial with
    availability_not_evaluated: source slots/uses are not current castability,
    generated groups, adjusted ranks or attack/DC totals. Explicit spellcasting
    additionally returns character/NPC transformed focus value/max/cap as
    current_focus_points/current_focus_pool_maximum/current_focus_pool_cap, and
    owned spell /system/cast/focusPoints as current_spell_focus_point_cost.
    These field records use keys spellcasting:current:<document UUID>:<path>,
    mapping pf2e.actor.casting-current.v1, exact transformed raw/contributors,
    and limitation casting_availability_not_evaluated. Actor values are finite
    numbers; spell cost is integer 0–3. Missing fields have present false, no raw
    value, mapped null and current_fields_unavailable. Zero remains a value;
    source is never a fallback. Familiar Actor focus pools, slot expenditure,
    contextual options and castability remain unsupported. Character source
    focus maximum remains excluded. Default identity/source reads do not request
    current resources. Casting selection
    rejects over 12000 owned Items or 24000 selected records with ReadFailed; these
    source-complexity guards are separate from page count/byte limits. Request
    identity or selected Item readers separately if the casting view is too large.
    Explicit state reads list each readable actual owned condition/effect Item
    once, selected typed source and immediate same-owner condition/external effect
    context relationships. state:item:<Item UUID> has mapping
    pf2e.actor.state-source.v1, concept state_item and a resolved value with
    target_uuid/document_name Item/type/name/name_truncated, token_uuid in token
    context, and application unknown. Names use persisted source /name, which may
    differ from prepared display names. Raw /name and /type contributors have
    basis source; limitation is stored_state_not_effective_application.
    state:source:<Item UUID>:<path> retains existing pf2e.condition.source.v1 or
    pf2e.effect.source.v1 fields and limitations. Each readable effect also has
    state:current:<owned Item UUID>:/system/expired, kind field, mapping
    pf2e.effect.current.v1 and concept current_effect_expired. Its single raw
    witness and exact contributor use /system/expired with basis transformed,
    from public Item.system, selecting the own data property declared by
    PF2e8.6.1 EffectSystemData.expired. No getters or toObject(false) fallback
    are used; serialization can omit this declared current flag.
    A present value must be boolean (false is preserved); absent declared data
    has present false, no raw value and mapped null, adding
    current_effect_expiry_unavailable. Limitation is exactly
    effect_expiry_not_application. This does not infer application,
    suppression, remaining seconds or condition activity, and never calculates
    expiry independently. state:condition:<Item UUID>:<path>
    and state:effect:<Item UUID>:<role> reuse read_item relationships, including
    resolved/missing/denied/unsupported/unverified statuses and exact source
    contributors. Resolved targets provide canonical target_uuid and token_uuid
    when needed for read_item/read_actor. Condition local IDs resolve only within
    the actual owner; override slugs stay unverified. Effects resolve immediate
    origin_actor/origin_token/origin_item/target_actor/target_token only, without
    expanding target source. Overlapping effects, equal names, and granted ability
    versus tracking effect remain separate actual Items; no duplicate ability or
    acquired benefit is inferred. Unresolved nonempty claims add
    unresolved_state_references. A generic state:denied marker contains only
    status denied/target_uuid null, no source or identity, and state_items_denied.
    State always remains partial with effective_application_not_evaluated and
    affliction_reading_unsupported, even when supported Item results are empty.
    The state:capability:affliction field (mapping pf2e.actor.state-capability.v1,
    concept state_affliction_support, no raw/contributors) has value
    {status:unsupported,reason:pf2e_8_6_1_affliction_disabled} and limitation
    no_effective_state_inference. This capability is independent of Item presence:
    no affliction stage, stage-range validity or effective affliction state is read.
    Stored condition values, persistent damage, duration units/start/expiry and
    badge formula/counter source never establish activity, suppression, current
    expiry beyond the separately labelled transformed effect boolean, damage
    dominance or complete application. No formulas are evaluated.
    Limits are 12000 owned Items, 24000 selected records and 200 nonempty external
    context claims, checked before relationship resolution and separately from
    page count/bytes. Exceeding these bounds returns ReadFailed; request selected
    read_item source/relationships instead. Default identity/source reads do not
    request state. State requires the supported PF2e character/NPC/familiar
    runtime and GM/document permissions; other systems/types are rejected before
    interpretation. Empty or paginated supported results never prove no conditions,
    effective effects or afflictions. Application interfaces and stage reading
    remain unsupported; state does not change documents, rolls or game execution.
    Inventory exposes actual owned physical inventory_item references once, plus
    persisted-name labels (prepared display names can differ), selected physical
    source fields and same-owner inventory_container and
    inventory_selected_ammunition claims. Resolved values contain target_uuid,
    document_name/type/name/name_truncated and token_uuid in token context; follow
    read_item for full definitions or exact activation prose. Missing/denied/
    unsupported targets retain null target_uuid; container cycle flags diagnose
    stored graph cycles. inventory_scope empty distinguishes no possessions from
    a generic denied scope without identities. Serialized attachments remain
    local source paths, never owned Item UUIDs. Actual owned kit definitions use
    inventory_kit_definition references and remain partial without content
    expansion; books expose common physical fields with specialty pending.
    Quantity, price.per, carrying and investment preserve source values; no total
    Bulk, sale price, effective benefits or activation eligibility is inferred.
    Inventory source-complexity guards reject over 12000 owned Items or 24000
    records with ReadFailed; use list_actor_items and read_item to narrow reads.
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
    weapon Items additionally expose authored damage dice/die/type/modifier and
    persistent damage, category/group, range/reload, ammunition capacity and local
    selectedAmmoId, runes, combination melee usage, trait toggles and specific-magic
    baseline. These are persisted source values, never effective Strike totals,
    wielded state or hydrated ammunition. Explicit weapon relationships return one
    relationship record with raw /system/selectedAmmoId and mapped concept
    stored_selected_ammunition_reference. mapped.value has status and target_uuid;
    missing/denied/unsupported/unverified expose null target_uuid. Resolved ammo or
    weapon Items include document_name, type, name, name_truncated and token_uuid
    when the source Item has a token context. Follow with read_item using returned
    target_uuid/token_uuid. Resolution is owner-local, permission checked and
    immediate; detached nonempty IDs remain unverified. Missing/null/empty IDs
    remain missing. This records a chosen ID, never loaded/current ammunition,
    compatibility or usability. Source alone performs no target hydration;
    effective remains unsupported. Source completion covers selected fields,
    not every schema field.
    armor Items additionally expose authored category/group, acBonus, Strength
    requirement, Dexterity cap, check/speed penalties, grade, rune values/property
    codes, specific-magic baseline, traits/tags, slug and publication. No Actor AC,
    saves, speed or automatic rune application is calculated. Source completion
    covers selected fields; relationships/effective/rules remain unsupported.
    shield Items additionally expose authored acBonus/speedPenalty, grade,
    reinforcing runes, specific-magic baseline and integrated-weapon rune/versatile
    source, traits/tags, slug and publication. These establish no raised state,
    Shield Block, class reinforcement, Actor AC or broken/destroyed state. Shared
    physical HP preserves persisted current/max independently: source maximum can
    differ from an effective reinforced maximum and current HP is not clamped. Source
    completion covers selected fields; relationships/effective/rules remain unsupported.
    book Items expose source category (formula/spell or an unknown stored code),
    capacity and ordered contents UUID claims, with traits/tags and publication.
    Duplicate contents indexes remain distinct. Stored contents are definitions,
    not owned Items or evidence of preparation, learning, capacity use or access.
    Shared physical quantity/price/carrying fields retain their own provenance.
    Book relationships expose immediate book_content_reference rows with exact
    /system/contents/N origin indexes and resolved/missing/denied/unsupported/
    unverified status. Resolved targets include target_uuid, document_name, type,
    name, name_truncated and token_uuid for synthetic targets; follow read_item.
    Absent/empty arrays return missing/empty scope rows. At most 200 references
    are resolved per read; oversized selections fail ReadFailed. No recursive
    expansion occurs and duplicate references remain distinct. Book support has
    deterministic coverage only; representative live book fixtures are unavailable.
    ancestry Items expose authored HP contribution, size, base speed, hands,
    reach, vision, language offers/custom text, additional-language allowance,
    keyed boost/flaw offers and selections, nullable alternate boosts and legacy
    voluntary configuration. Null stored singleton selections are not proof of
    unused boosts; prepared PF2e choices can differ. Each source map/list admits
    up to 12000 entries; malformed/oversized source fails ReadFailed.
    These are definitions, never effective character
    statistics or acquired choices. Keyed ABC feature uuid/img/name/level fields
    retain escaped source paths. relationships returns ancestry_feature_reference
    for up to 200 explicit feature definitions: resolved includes the actual Item
    target_uuid/document_name/type/name/name_truncated and token_uuid only for
    synthetic targets; missing/denied/unsupported/unverified disclose no target.
    Absent or empty items maps return missing/empty markers. No recursive feature
    hydration, granted/acquired claim, physical fields or effective benefit math.
    Recorded feat flags.pf2e.rulesSelections expose only stored string/finite-number
    leaves (maximum12000 keys), never UUID guesses, acquisitions or eligibility.
    Missing/undefined and empty maps stay distinct. Unsupported object/array/null/
    boolean values are withheld and source is partial with reason
    unsupported_selection_values; partial results are not an exhaustive selection
    list. Malformed root maps return ReadFailed. No rule execution occurs.
    feat Items expose PF2e8.6.1 authored category as {code,kind}, where kind is
    feature (ancestryfeature/calling/classfeature/curse/deityboon/pfsboon), feat
    (ancestry/bonus/class/general/skill), or unknown. Source mapping is
    pf2e.feat.source.v1 with limitation feat_source_not_effective_benefit.
    Nominal level and nullable taken level are separate; activation codes stay
    unchanged and null action count does not imply free action. Prerequisites
    remain text, location remains a stored string, and selected frequency,
    traits/toggles, language/key options, proficiency ranks, senses, suppression
    UUIDs and self-effect leaves are authored source. These do not establish
    eligibility, acquired grants, active toggles, effective benefits or resources.
    Lists/maps are bounded to 12000 entries each; absent/null/empty remain
    distinct, malformed/oversized source fails ReadFailed. No rule elements,
    arbitrary flags, physical fields or prepared values are read. Selected
    flags.pf2e.itemGrants opaque-key id/onDelete/nested and grantedBy id/onDelete
    retain persisted source claims; onDelete codes are never executed. Source-only
    reads perform no relationship hydration. Explicit relationships resolves up
    to 200 immediate feat_grant_reference, feat_granted_by_reference,
    feat_self_effect_reference and feat_suppressed_feature_reference claims at
    relationships:feat:<escaped source path>. Mapping pf2e.feat.reference.v1
    has limitation persisted_reference_not_active_benefit. Every row has one
    exact source contributor. Grant IDs resolve only within the actual Actor
    owner, retaining synthetic token identity; unowned definitions return unowned.
    UUID claims retain exact canonical identity; self-effects require effect
    Items and suppression claims require feat Items. Missing/empty/unassociated/
    unowned/denied/unsupported/unverified outcomes retain target_uuid=null.
    Resolved values contain status, target_uuid, document_name, type, name,
    name_truncated and token_uuid only for synthetic targets. Follow read_item
    with those selectors. No recursive expansion, target source reading,
    reciprocal/causality claim, acquisition inference or active benefit assertion.
    deity Items expose PF2e8.6.1 authored category, nullable sanctification
    modal/what, primary/alternate domains, font, attributes, nullable skill,
    weapons, keyed spell UUIDs, otherTags, slug and publication. Missing fields
    remain absent; these options establish no active devotee benefits. No stock,
    trait rarity/value, effective benefits or automatic spell acquisition is read.
    relationships explicitly resolves at most 200 immediate deity_spell_reference
    claims at relationships:deity:<escaped /system/spells/key path>. One exact
    source UUID descriptor contributes to each; no font-name UUID guessing or
    target source reading. Missing spells map is missing; an empty map is empty.
    Missing/denied/unsupported/unverified outcomes have target_uuid=null and no
    target identity. Resolved canonical spell Items contain target_uuid (the exact
    claim), document_name, type, name, name_truncated and token_uuid only for
    synthetic targets. Follow read_item with those selectors. Source maps/lists
    are bounded to 12000 entries each; returned continuation preserves paging.
    heritage Items expose authored nullable ancestry association, separate stored
    ancestry name/slug/uuid leaves, traits/tags, rarity, slug and publication.
    Null association means unassociated, not proof of versatile eligibility or
    ancestry exclusivity; absent association stays missing. Explicit relationships
    returns one heritage_ancestry_reference at relationships:heritage:ancestry:
    unassociated/missing/denied/unsupported/unverified have target_uuid null and no
    target metadata. Resolved includes actual canonical ancestry Item target_uuid,
    document_name, type, name (at most 256 characters), name_truncated and token_uuid
    only for synthetic targets. Follow read_item with returned selectors. Stored
    association proves no owner ancestry membership. No target source, recursive
    expansion, physical fields, rule application or effective character math.
    Source lists admit 12000 entries; malformed/oversized source fails ReadFailed.
    background Items expose authored keyed boost offers and nullable stored
    selections, trainedSkills.value skill codes and trainedSkills.lore text,
    keyed ABC feature uuid/img/name/level, traits/tags, slug and publication.
    These definitions establish no effective character scores, training, acquired
    feat/Lore or duplicate-training replacement. Null selections stay null;
    prepared choices may differ. Empty structured Lore/training/feature entries
    do not prove no benefit; read description for prose choices and exceptions.
    Maps/lists admit up to 12000 entries; malformed
    or oversized source fails ReadFailed. Explicit relationships returns
    background_feature_reference for up to 200 immediate ABC definitions, keyed
    by exact escaped /system/items/<key>/uuid paths; duplicates stay distinct.
    Resolved targets provide target_uuid/document_name/type/name/name_truncated
    and token_uuid for synthetic targets; follow read_item. Missing/denied/
    unsupported/unverified targets disclose no identity. Absent/empty items maps
    return missing/empty scope markers. No recursive hydration, acquired joins,
    physical fields, benefit application or effective calculations are supplied.
    class Items expose PF2e8.6.1 definition source: keyAbility offers/nullable
    selected key attribute, hp contribution (not total HP), starting proficiency
    ranks, trainedSkills.value/additional, and five advancement value lists
    (ancestryFeatLevels, classFeatLevels, generalFeatLevels, skillFeatLevels,
    skillIncreaseLevels). Starting rank mapped.value is {rank,label}, with rank
    0..4 and label Untrained/Trained/Expert/Master/Legendary, never a check total.
    Absent other attack name stays absent. Progression numbers >=1 remain
    exact source;
    no current level filtering or advancement occurs. Keyed ABC uuid/img/name/
    level, otherTags/rarity, slug and publication retain source provenance.
    Class maps/lists admit 12000 entries; malformed/oversized source fails
    ReadFailed. Explicit relationships returns class_feature_reference for at
    most 200 immediate definition claims, keyed relationships:class:<exact
    escaped /system/items/<key>/uuid path>. Duplicate claims remain distinct.
    Resolved values expose status/target_uuid/document_name/type/name/
    name_truncated and token_uuid for synthetic targets; follow read_item with
    returned selectors. Missing/denied/unsupported/unverified disclose no target
    identity. Absent/empty items maps return missing/empty scope markers. No
    acquisition claims, recursive hydration, effective character
    statistics, advancement, physical fields or rule application are supplied.
    kit Items expose authored bundle component definitions, own price denominations,
    price.per and sizeSensitive, traits, slug and publication. Kits are not physical
    possessions: no quantity, carry, investment or container state is inferred.
    Nested system.items map keys use JSON-pointer escaping (~0 for ~, ~1 for /),
    retain duplicate UUID claims and have at most four entry levels. Entry uuid,
    img, quantity, name and isContainer remain source; terminal items is null.
    relationships exposes kit_component_reference per explicit component uuid
    with raw source path and status resolved/missing/denied/unsupported/unverified;
    target_uuid is null unless resolved. Resolved definitions include document_name,
    type, name, name_truncated and token_uuid for synthetic targets. Follow read_item
    with target_uuid and returned token_uuid. Root absent/empty items markers have
    missing/empty status. Resolution reads no target source and never expands kits,
    creates inventory, multiplies quantities or establishes ownership. At most 200
    component references and 12000 definition entries are admitted; narrow oversized
    source reads rather than treating failure as complete inventory evidence.
    treasure Items expose nullable category and authored traits/tags, rarity, slug
    and publication alongside shared physical quantity and price coin denominations
    and price.per. Quantity and price.per are independent stored values; no total
    value, sale proceeds, automatic currency conversion or derived stackGroup is
    calculated. Treasure Items owned by character, NPC or familiar Actors are supported;
    this does not add support for Loot Actors. Selected source is complete;
    relationships/effective/rules remain unsupported.
    equipment Items additionally expose source traits/tags, rarity, slug and
    publication alongside shared physical usage, carrying, investment and serialized
    attachment identities. Activations and modifications may exist only in prose:
    explicitly request description and follow its returned continuation for exact
    text. Missing structured activation fields do not mean no ability. Uninvested
    equipment can retain mundane benefits; no carried or magical benefit is applied
    or declared active. Selected source is complete; relationships/effective/rules
    remain unsupported.
    backpack Items are containers, including source stowing, held/stowed Bulk,
    capacity and ignored Bulk alongside common physical fields, traits and publication.
    Capacity is not current contents Bulk; ignored Bulk is not a universal subtraction.
    No total Bulk, encumbrance, access action or effective inventory state is calculated.
    Explicit relationships follows stored parent/descendant containerId claims only
    within the same owning Actor instance. container_parent reports a resolved
    backpack selector or missing/denied/unsupported/unverified and a cycle flag.
    An unresolved parent cycle:false means no verified cycle, not proof of acyclicity;
    unverified standalone scope is partial.
    container_content returns each reachable readable physical Item once with its
    actual target_uuid, parent_uuid, parent_status, depth and optional token_uuid.
    A non-container parent is explicit unsupported; cycles make the section partial.
    container_contents scope markers distinguish empty, denied and unverified
    standalone scope; denied can accompany readable descendants. Follow selectors
    with read_item, carrying token_uuid unchanged. Source-only reads do not scan contents.
    Standalone scope is unverified and never claims empty contents. Owned scope
    markers are empty or denied. Relationships inspect at most 12000 owner Items;
    exceeding that hard scope bound returns ReadFailed. Partial section reasons are
    container_scope_unverified, containment_cycle, container_parent_missing,
    container_parent_denied, container_parent_unsupported and container_contents_denied.
    spellcastingEntry Items expose stored tradition, casting mode/flexible/validItems,
    ability/proficiency, source spell attack/DC, auto-heighten rank and indexed slot
    value/max/preparations. Template slot11 is retained without spell-rank semantics.
    Slot value zero never proves exhaustion: each preparation
    keeps its own array index, nullable local spell ID and expended flag, including
    repeated IDs. These are stored resources/configuration, never current castability
    or a computed character spell statistic. Legacy object or malformed preparations
    are omitted with explicit partial-section reasons rather than coerced into arrays.
    Missing id/expended fields stay absent, never defaults. Prepared, spontaneous,
    innate and focus modes remain distinct; slot counters are not focus pools or
    innate per-spell uses. Selection rejects over 12000 descriptors, 6000 preparations
    per array or 64 malformed-source issues with ReadFailed; inspect/fix the selected
    source or request identity/description separately.
    Preparation IDs remain owner-local claims; no spell hydration or entry-to-spell
    relationship is provided. Request description for exact prose and follow returned
    continuation. Relationships/effective/rules remain unsupported.
    spell Items expose selected definition source: level.value maps to base rank;
    stored location heightenedLevel/autoHeightenLevel remain configuration, never
    a computed cast rank. Casting time, range, target, requirements and cost remain
    exact text. Damage components preserve formulas, damage/healing kind codes,
    materials, categories and applyMod independently; no formula is evaluated.
    Area, defense/save, sustained duration, ritual checks, traits/traditions and
    publication remain source. Fixed heightening layers and override overlays
    retain primitive leaves at their original source paths, including empty patch
    markers; no variant is applied and no nested Item UUID is invented. Explicit
    description returns exact root and nested layer/overlay prose with the shared
    continuation. Explicit relationships follows only location.value through the
    actual owner's Items to a spellcastingEntry: mapped.value.status distinguishes
    resolved/missing/denied/unsupported/unverified; target_uuid is null unless
    resolved, when document_name/type/name/name_truncated and token_uuid for token
    context are included. Follow read_item(item_uuid=target_uuid, token_uuid if
    returned) without assuming castability, prepared status, slots or resources.
    Effective/rules remain unsupported; no casting or spontaneous heightening is
    inferred from a higher configured rank.
    consumable Items expose selected source: category, uses.value/max/autoDestroy,
    nullable damage formula/type/kind, traits/tags, slug and publication. Quantity
    and uses remain separate persisted values; no consumption, damage or healing
    is applied. Contained spell source is null or selected local _id/name/type/rank
    metadata plus spell-definition fields under /system/spell/system/... using
    pf2e.spell.source.v1 and spell concepts (rank is stored base rank, not heightened casting rank).
    Contributors retain the consumable UUID; a contained
    SpellSource has no independently resolvable Item UUID. location.value remains
    a stored claim with no actor-entry resolution. Request description for exact
    activation prose and contained spell root/fixed-layer/overlay prose; text.path
    retains the full nested source path. Follow returned continuation for all
    fragments. No heightening/overlay application or casting is performed;
    relationships, effective and rules remain unsupported.
    ammo Items additionally expose persisted uses.value/max/autoDestroy, nullable
    craftableAs codes, traits/tags, source slug and publication. Uses are authored
    values, not a calculation of shots remaining or consumption. craftableAs codes
    do not establish weapon compatibility. No reverse weapon search occurs;
    relationships/effective/rules remain explicitly unsupported for ammunition.
    action Items have complete selected source mappings for activation kind/count,
    category, frequency, traits/tags, publication and named self-effect references.
    Null action counts never imply free actions. Explicit relationships resolve
    only the immediate self-effect without applying it: mapped.value contains
    target_uuid/status, plus token_uuid for resolved synthetic targets. Follow a
    resolved target with read_item(item_uuid=target_uuid, token_uuid=token_uuid
    if present). Missing/denied/unsupported/unverified targets retain named raw
    references with null target_uuid. Source alone performs no effect hydration;
    melee Items expose authored NPC attack mode/bonus, range/area, separate damage
    formulas/types/categories, MAP applicability and traits, independent of gear.
    Only action=strike maps to Strike; null range means no explicit range, not a
    proven melee capability. Attack-effect relationships retain indexed source
    labels as unverified with null target_uuid; labels are never resolved as UUIDs.
    Missing versus empty attackEffects arrays both report missing relationships
    while their raw present/value fields retain the distinction. Effective attack
    math and elite/weak adjustments remain unsupported.
    Lore Items expose stored modifier, proficiency rank with rank/label, variants
    and publication. NPC owners identify authored modifiers; character owners
    identify proficiency ranks. Detached/unknown owners retain stored semantics;
    no effective skill total or roll-option execution is implied. identity.actor
    may include actual owner type character/npc/familiar.
    Affliction Items are explicitly unsupported in the tested PF2e8.6.1 runtime:
    upstream construction is disabled. read_item rejects affliction selectors with
    UnsupportedType before reading their source; inspect get_actor_types for this
    limitation. No schema-only prototype establishes runtime affliction support.
    Condition Items expose persisted valuedness/value, persistent damage formula,
    damage type/recovery DC/critical-hit flag, local parent/child/override IDs and
    override slugs, group, traits and publication. Local IDs remain source text;
    no source-only hydration or formula execution is implied. Explicit relationships
    resolve local Item IDs only within the actual Actor owner, preserving token
    selectors; top-level override slugs remain unverified, never UUID selectors.
    Missing, denied, unsupported and unverified targets have null target_uuid.
    Resolution does not establish current activity, suppression, prepared duration
    or effective damage; effective condition state remains unsupported.
    Effect Items expose persisted level/duration/start, badge discriminator with
    numeric counter/value or unevaluated formula, traits, token-icon visibility,
    unidentified/fromSpell and origin/target/roll context. Stored UUID strings are
    source references only; source performs no hydration or formula execution.
    Persisted duration expiry is not current expired/active/suppressed state;
    those effective interpretations remain unsupported. Explicit relationships resolve
    five origin_actor/origin_token/origin_item/target_actor/target_token references.
    Each retains all five source context paths. mapped.value has status and
    target_uuid; resolved rows also have document_name, name, name_truncated and
    optional token_uuid for Actor/Item instance selectors. Unresolved status
    missing/denied/unsupported/unverified has null target_uuid and no target name.
    Follow Actor/Item references with read_actor/read_item, passing token_uuid
    when returned. Token references are instance selectors for read_actor.
    Optional description/rules/relationships/effective are delivered or explicitly
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
    unsupported_count counts excluded Items, including runtime-disabled PF2e8.6.1
    afflictions; those Items do not break navigation of other owned Items. Empty only means no literal matches
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
