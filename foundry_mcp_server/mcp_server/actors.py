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
    if value['type'] not in get_args(ItemType) or role != 'parent_reference' and value['type'] != 'condition': return False
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
    return (identity['document_name']=='Actor' and identity['type']=='npc' and _npc_spec(path) is not None and _npc_spec(path)[1] in ('object','predicate')) or identity['document_name']=='Item' and ((identity['type']=='melee' and path=='/system/damageRolls') or (identity['type']=='lore' and path=='/system/variants') or (identity['type']=='weapon' and _weapon_spec(path) is not None and _weapon_spec(path)[1]=='object') or (identity['type']=='armor' and _armor_spec(path) is not None and _armor_spec(path)[1]=='object') or (identity['type']=='shield' and _shield_spec(path) is not None and _shield_spec(path)[1]=='object') or (identity['type']=='spell' and _spell_spec(path) is not None and _spell_spec(path)[1]=='object') or (identity['type']=='consumable' and _contained_spell_spec(path) is not None and _contained_spell_spec(path)[1]=='object'))


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
    if identity is not None and identity['document_name']=='Actor' and identity['type']=='npc':
        return path in NPC_NOTES or _npc_spec(path) is not None
    if identity is None or identity['document_name'] != 'Item':
        return False
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


def _casting_owned(uuid, identity):
    """PF2e-specific immediate owned spell/entry UUID; generated UUIDs excluded."""
    prefix=identity['uuid']+'.Item.'
    return type(uuid) is str and len(uuid)<=512 and uuid.startswith(prefix) and re.fullmatch(r'[^.\s#]+',uuid[len(prefix):]) is not None


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
    if identity['document_name']=='Item' and identity['type']=='book' and row['section']=='relationships':
        return _book_relationship(row,identity)
    if identity['document_name']=='Item' and identity['type']=='backpack' and row['section']=='relationships':
        return _container_relationship(row,identity)
    if identity['document_name']=='Actor' and row['section']=='spellcasting':
        return _actor_casting_record(row,identity)
    if identity['document_name']=='Actor' and row['section']=='inventory':
        return _actor_inventory_record(row,identity)
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
    if identity['document_name']=='Actor' and row['section']=='description' and identity['type']!='npc':
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
                    # PF2e-specific casting configuration excludes current availability.
                    if result['identity']['document_name']=='Actor':
                        valid = valid and all(row['status']=='partial' and 'availability_not_evaluated' in row['reasons'] for row in rows if row['name']=='spellcasting')
                    # PF2e-specific NPC8.6.1 Item references never claim full sections.
                    if result['identity']['document_name']=='Actor' and result['identity']['type']=='npc':
                        pending={'strikes':'other_attacks_pending','abilities':'other_abilities_pending'}
                        valid = valid and all(row['status']=='partial' and pending[row['name']] in row['reasons'] for row in rows if row['name'] in pending)
                    valid = valid and all(_record(row, sections, result['identity']) for row in result['records']) and len({row['key'] for row in result['records']}) == len(result['records']) and _pagination(result.get('pagination'), len(result['records']), limit)
                    if valid and result['identity']['document_name']=='Actor':
                        valid = all(_inventory_section(result['records'], row) for row in rows if row['name']=='inventory')
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
    Known sections description/build/statistics/skills/strikes/abilities/spellcasting/inventory/
    state/effective can be unsupported; get_actor_types reports delivered support.
    Sections must be unique/nonempty (at most 12). PF2e character/npc/familiar only;
    other systems/versions/types give UnsupportedSystem/Version/Type errors.

    Returns contract_version/runtime/identity/revision/sections/records/pagination/
    limitations. Records retain selected raw fields, mapped concepts and provenance;
    sections distinguish partial/unsupported/not_applicable from complete. Missing
    fields differ from null/zero; source is not complete effective statistics.
    NPC source includes authored attributes, AC/saves/Perception/skills, stored HP,
    senses/languages/movement, IWR and publication. Elite/weak arithmetic is not
    applied; integrated statistics remain pending. Explicit description returns NPC
    stored blurb, publicNotes and privateNotes only, including GM-private biography;
    default source never includes them. Character/familiar description is unsupported.
    Skills currently contains owned Lore specialty references only, with partial
    other_skills_pending. Each lore_specialty mapped value has resolved target_uuid
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
    applicable; follow read_item. casting_spell_assignment/casting_preparation
    statuses resolved/missing/denied/unsupported/unverified/mismatched_assignment
    distinguish stored membership from invalid or inaccessible links. Repeated
    preparations retain independent slot/index keys and expended source fields.
    Denied markers expose no related identity. The section remains partial with
    availability_not_evaluated: source slots/uses are not current castability,
    generated groups, adjusted ranks or attack/DC totals. Character focus maximum
    is derived and excluded; stored zero differs from missing. Casting selection
    rejects over 12000 owned Items or 24000 selected records with ReadFailed; these
    source-complexity guards are separate from page count/byte limits. Request
    identity or selected Item readers separately if the casting view is too large.
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
