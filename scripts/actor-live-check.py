"""Fixed read-only smoke checks against the existing development GM bridge.

Run through scripts/actor-tools.sh live. Requires .env.mcp caller credential
and the authorized development console. Never outputs document IDs or secrets.
"""
import asyncio,hashlib,json,sys
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type=="text"))

def probe(value):
    """Decode bounded development-probe chunks, rejecting partial snapshots."""
    if isinstance(value,dict) and 'value' in value:value=value['value']
    if isinstance(value,dict) and value.get('$type')=='Array':
        if value.get('truncated') is not False or not all(isinstance(part,str) for part in value.get('values',[])):
            raise ValueError('Development probe was truncated or malformed.')
        value=''.join(value['values'])
    if not isinstance(value,str):raise ValueError('Unexpected development probe shape.')
    return json.loads(value)

async def main():
    root=Path(__file__).resolve().parent.parent
    values={}
    for line in (root / '.env.mcp').read_text().splitlines():
        key,sep,value=line.partition('=')
        if sep and key.strip()=='FOUNDRY_MCP_CALLER_TOKEN':values[key.strip()]=value.strip()
    headers={'Authorization':'Bearer '+values['FOUNDRY_MCP_CALLER_TOKEN']}
    transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers=headers)
    async with Client(transport) as client:
        available={t.name:t for t in await client.list_tools()}
        # Restart/refresh may briefly leave a healthy server without its GM socket.
        for attempt in range(20):
            bridge=payload(await client.call_tool('get_bridge_versions', {}))
            if bridge['module_status']=='connected':break
            if attempt==19:raise RuntimeError('Existing GM bridge has not reconnected; inspect the development tab.')
            await asyncio.sleep(1)
        needed={'get_actor_types','read_actor','read_item','list_actor_items','get_actor_tree','search_actors','list_scene_actors','list_actor_compendiums','search_compendium_actors'}
        assert needed<=available.keys()
        for name in needed:assert available[name].annotations.readOnlyHint
        assert 'description' in available['read_actor'].inputSchema['properties']['sections']['items']['enum']
        assert 'GM-private biography' in available['read_actor'].description
        assert 'Missing structured activation fields do not mean no ability' in available['read_item'].description
        assert 'equipment Items' in available['read_item'].description
        assert 'consumable Items expose selected source' in available['read_item'].description
        assert 'rank is stored base rank, not heightened casting rank' in available['read_item'].description
        assert 'spell Items expose selected definition source' in available['read_item'].description
        assert 'actual owner' in available['read_item'].description
        selector_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const actor=game.actors.find(a=>a.type==='npc'&&a.items.size);
const supported=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type));
const items=[...game.items.contents,...supported.flatMap(a=>a.items.contents)];
const physicalTypes=['weapon','armor','shield','equipment','consumable','ammo','backpack','book','treasure'];
const actionSamples=['passive','free','reaction','action'].map(kind=>items.find(i=>i.type==='action'&&i.toObject(true).system.actionType?.value===kind)).filter(Boolean);
const effectAction=items.find(i=>i.type==='action'&&i.toObject(true).system.selfEffect?.uuid);
const token=game.scenes.contents.flatMap(s=>s.tokens.contents).find(t=>t.actor?.type==='npc');
const tokenAction=token?.actor.items.find(i=>i.type==='action');
const armorItems=items.filter(i=>i.type==='armor');
const ammunition=items.filter(i=>i.type==='ammo');
const weapons=items.filter(i=>i.type==='weapon');
const weaponSamples=[weapons.find(i=>i.toObject(true).system.range===null),weapons.find(i=>typeof i.toObject(true).system.range==='number')].filter(Boolean);
const conditions=items.filter(i=>i.type==='condition');
const effects=items.filter(i=>i.type==='effect');
const loreItems=items.filter(i=>i.type==='lore');const loreItem=loreItems.find(i=>i.parent?.type==='npc');
const attacks=items.filter(i=>i.type==='melee');
const meleeSamples=[
 ['explicit_range',attacks.find(i=>i.toObject(true).system.range!==null&&i.toObject(true).system.range!==undefined)],
 ['null_thrown',attacks.find(i=>i.toObject(true).system.range===null&&i.toObject(true).system.traits?.value.some(t=>t.startsWith('thrown-')))],
 ['effect_labels',attacks.find(i=>i.toObject(true).system.attackEffects?.value.length)]
].filter(([,item])=>item);
const fingerprintItems=[...new Map([actor,...actionSamples,effectAction,tokenAction,...meleeSamples.map(([,i])=>i),...loreItems,...effects,...conditions,...weaponSamples,...ammunition,...armorItems.slice(0,2)].filter(Boolean).map(i=>[i.uuid,i])).values()];
const npcSource=actor.toObject(true);
const report=JSON.stringify({actor_uuid:actor.uuid,npc_notes:await Promise.all(['blurb','publicNotes','privateNotes'].map(async key=>{const value=npcSource.system.details[key];return {key,present:typeof value==='string',...(typeof value==='string'?{sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),v=>v.toString(16).padStart(2,'0')).join('')}: {})}})),npc_ac:npcSource.system.attributes.ac.value,npc_hp:npcSource.system.attributes.hp.value,token_uuid:token?.uuid,
physical_items:physicalTypes.map(type=>items.find(item=>item.type===type)?.uuid).filter(Boolean),
melee_samples:meleeSamples.map(([context,i])=>({context,uuid:i.uuid})),
armor_samples:armorItems.slice(0,2).map(i=>({uuid:i.uuid,strength:i.toObject(true).system.strength,ac_bonus:i.toObject(true).system.acBonus})),
ammo_samples:ammunition.slice(0,2).map(i=>({uuid:i.uuid,value:i.toObject(true).system.uses.value,max:i.toObject(true).system.uses.max,craftable_as:i.toObject(true).system.craftableAs})),
weapon_samples:weaponSamples.map(i=>({uuid:i.uuid,range:i.toObject(true).system.range,category:i.toObject(true).system.category,damage_type:i.toObject(true).system.damage.damageType})),
condition_samples:conditions.slice(0,5).map(i=>({uuid:i.uuid,is_valued:i.toObject(true).system.value.isValued,value:i.toObject(true).system.value.value})),
effect_samples:[...new Map(effects.map(i=>[`${i.parent?'owned':'world'}:${i.toObject(true).system.badge?.type??'null'}`,i])).values()].slice(0,10).map(i=>({uuid:i.uuid,unit:i.toObject(true).system.duration.unit,badge:i.toObject(true).system.badge?.type??null})),
lore_item_uuid:loreItem?.uuid,lore_actor_uuid:loreItem?.parent?.uuid,
action_samples:await Promise.all(actionSamples.map(async i=>({uuid:i.uuid,kind:i.toObject(true).system.actionType.value,revision:await digest(i.toObject(true))}))),
self_effect_item_uuid:effectAction?.uuid,token_action_uuid:tokenAction?.uuid,
source_fingerprints:await Promise.all(fingerprintItems.map(async i=>({uuid:i.uuid,revision:await digest(i.toObject(true))})))});
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
        selection=probe(payload(await client.call_tool('execute_javascript',{'code':selector_probe})))
        actor=await client.call_tool('read_actor',{'actor_uuid':selection['actor_uuid'],'limit':25})
        assert actor.data['identity']['uuid']==selection['actor_uuid']
        tree=payload(await client.call_tool('get_actor_tree',{'limit':1}))
        assert tree['pagination']['returned']<=1
        found=payload(await client.call_tool('search_actors',{'query':actor.data['identity']['name'][:200],'limit':100}))
        assert any(node['identity']['uuid']==selection['actor_uuid'] for node in found['nodes']) or not found['pagination']['complete']
        scenes=payload(await client.call_tool('list_scene_actors',{}))
        assert scenes['nodes']
        packs=payload(await client.call_tool('list_actor_compendiums',{'document_type':'Item','limit':5}))
        assert packs['nodes']
        pack_scope={'document_type':'Item','pack_ids':[node['id'] for node in packs['nodes']],'query':'a','limit':1}
        pack_matches=payload(await client.call_tool('search_compendium_actors',pack_scope))
        assert pack_matches['nodes'], 'Expected an existing Item pack with a literal a match.'
        candidate=pack_matches['nodes'][0]
        pack_item=payload(await client.call_tool(candidate['next_call']['tool'],candidate['next_call']['arguments']))
        assert pack_item['identity']['uuid']==candidate['identity']['uuid']
        assert pack_item['identity']['source_kind']=='compendium'
        source_records=list(actor.data['records'])
        source_pages=1
        cursor=actor.data['pagination']['next_cursor']
        while cursor:
            assert source_pages<100, 'NPC source continuation exceeded the declared smoke-check bound.'
            page=payload(await client.call_tool('read_actor',{'actor_uuid':selection['actor_uuid'],'limit':25,'cursor':cursor}))
            source_records.extend(page['records'])
            source_pages+=1
            cursor=page['pagination']['next_cursor']
        for path,expected in [('/system/attributes/ac/value',selection['npc_ac']),('/system/attributes/hp/value',selection['npc_hp'])]:
            row=next(row for row in source_records if row['raw'][0]['path']==path)
            assert row['raw'][0]['value']==expected and row['mapped']['value']==expected
            assert row['provenance']['mapping']=='pf2e.npc.source.v1'
        notes=[]
        note_cursor=None
        for _ in range(100):
            arguments={'actor_uuid':selection['actor_uuid'],'sections':['description'],'limit':25}
            if note_cursor:arguments['cursor']=note_cursor
            note_page=payload(await client.call_tool('read_actor',arguments))
            notes.extend(note_page['records'])
            note_cursor=note_page['pagination']['next_cursor']
            if not note_cursor:break
        assert note_cursor is None, 'NPC biography exceeds smoke-check continuation bound.'
        for expected in selection['npc_notes']:
            rows=[row for row in notes if row['raw'][0]['path']=='/system/details/'+expected['key']]
            assert rows and all(row['provenance']['mapping']=='pf2e.npc.notes.v1' for row in rows)
            assert all(row['raw'][0]['present']==expected['present'] for row in rows)
            if expected['present']:
                text=''.join(row['raw'][0]['value'] for row in rows)
                assert hashlib.sha256(text.encode()).hexdigest()==expected['sha256']
        reference_count=0
        ref_cursor=None
        for _ in range(100):
            arguments={'actor_uuid':selection['actor_uuid'],'sections':['strikes','abilities'],'limit':25}
            if ref_cursor:arguments['cursor']=ref_cursor
            refs=payload(await client.call_tool('read_actor',arguments))
            assert all(section['status']=='partial' for section in refs['sections'])
            for row in refs['records']:
                value=row['mapped']['value']
                if value['status']!='resolved':continue
                followed=payload(await client.call_tool('read_item',{'item_uuid':value['target_uuid'],'sections':['identity']}))
                assert followed['identity']['type']==('melee' if row['section']=='strikes' else 'action')
                assert followed['identity']['actor']['uuid']==selection['actor_uuid']
                reference_count+=1
            ref_cursor=refs['pagination']['next_cursor']
            if not ref_cursor:break
        assert ref_cursor is None and reference_count>0, 'Expected bounded existing NPC attack/ability references.'
        items=await client.call_tool('list_actor_items',{'actor_uuid':selection['actor_uuid'],'limit':1})
        item=await client.call_tool(**dict(name=items.data['nodes'][0]['next_call']['tool'],arguments=items.data['nodes'][0]['next_call']['arguments']))
        assert item.data['identity']['actor']['uuid']==selection['actor_uuid']
        if selection.get('token_uuid'):
            token=await client.call_tool('read_actor',{'token_uuid':selection['token_uuid']})
            assert token.data['identity']['instance']['token_uuid']==selection['token_uuid']
            placed=payload(await client.call_tool('list_scene_actors',{'scene_uuid':token.data['identity']['instance']['scene_uuid'],'limit':100}))
            assert any(node['uuid']==selection['token_uuid'] for node in placed['nodes']) or not placed['pagination']['complete']
        physical_verified=0
        for item_uuid in selection.get('physical_items',[]):
            physical=payload(await client.call_tool('read_item',{'item_uuid':item_uuid,'limit':100}))
            assert any(raw['path']=='/system/quantity' for record in physical['records'] for raw in record['raw'])
            assert all(raw['basis']=='source' for record in physical['records'] for raw in record['raw'])
            physical_verified+=1
        assert physical_verified, 'No existing in-scope physical Item fixture was available.'
        assert len(selection['action_samples'])==4, 'Representative activation source fixtures are missing.'
        labels={'passive':'passive_ability','free':'free_action','reaction':'reaction','action':'action_or_activity'}
        for sample in selection['action_samples']:
            action_item=payload(await client.call_tool('read_item',{'item_uuid':sample['uuid'],'limit':100}))
            activation=next(record for record in action_item['records'] if record['raw'][0]['path']=='/system/actionType/value')
            assert activation['mapped']['value']==labels[sample['kind']]
            assert action_item['sections'][1]['status']=='complete'
        assert selection.get('self_effect_item_uuid')
        relation=payload(await client.call_tool('read_item',{'item_uuid':selection['self_effect_item_uuid'],'sections':['relationships']}))
        relationship=relation['records'][0]['mapped']['value']
        assert relationship['status']=='resolved'
        effect_args={'item_uuid':relationship['target_uuid']}
        if relationship.get('token_uuid'):effect_args['token_uuid']=relationship['token_uuid']
        effect=payload(await client.call_tool('read_item',dict(effect_args,sections=['identity'])))
        assert effect['identity']['type']=='effect'
        if selection.get('token_action_uuid'):
            token_item=payload(await client.call_tool('read_item',{'item_uuid':selection['token_action_uuid'],'token_uuid':selection['token_uuid'],'sections':['identity','source']}))
            assert token_item['identity']['instance']['token_uuid']==selection['token_uuid']
        familiar_packs=payload(await client.call_tool('list_actor_compendiums',{'document_type':'Item','query':'familiar'}))
        assert familiar_packs['nodes']
        familiar_matches=payload(await client.call_tool('search_compendium_actors',{'document_type':'Item','pack_ids':[node['id'] for node in familiar_packs['nodes'][:10]],'query':'a','types':['action'],'limit':1}))
        assert familiar_matches['nodes']
        familiar_call=familiar_matches['nodes'][0]['next_call']
        familiar=payload(await client.call_tool(familiar_call['tool'],dict(familiar_call['arguments'],limit=100)))
        assert familiar['identity']['source_kind']=='compendium'
        assert any(record['raw'][0]['path']=='/system/category' and record['raw'][0].get('value')=='familiar' for record in familiar['records'])
        # Compare persisted source fingerprints after reads; no gameplay mutation.
        spell_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.spells-srd');const index=await pack.getIndex({fields:['type','system.time','system.damage','system.heightening','system.overlays','system.ritual']});
const rows=index.filter(row=>row.type==='spell');
const predicates=[r=>/or|to/.test(r.system?.time?.value??''),r=>/minute|hour|day/.test(r.system?.time?.value??''),r=>Object.values(r.system?.damage??{}).some(d=>d.kinds?.includes('healing')&&d.kinds?.includes('damage')),r=>r.system?.heightening?.type==='interval',r=>r.system?.heightening?.type==='fixed',r=>Object.keys(r.system?.overlays??{}).length,r=>r.system?.ritual!=null];
const owned=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type)).flatMap(a=>a.items.contents).filter(i=>i.type==='spell');
const candidates=[...predicates.map(match=>rows.find(match)).filter(Boolean).map(row=>pack.getUuid(row._id)),owned.find(i=>i.toObject(true).system.location.value),owned.find(i=>!i.toObject(true).system.location.value)];
const report=[];for(const selected of candidates){const doc=typeof selected==='string'?await foundry.utils.fromUuid(selected):selected;if(!doc)continue;const source=doc.toObject(true),s=source.system;report.push({uuid:doc.uuid,base:s.level.value,time:s.time.value,damage:Object.entries(s.damage).map(([key,v])=>({key,formula:v.formula,kinds:v.kinds})),entry_uuid:doc.parent?.items.get(s.location.value)?.uuid??null,revision:await digest(source),description_sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s.description.value))),v=>v.toString(16).padStart(2,'0')).join('')});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        spell_samples=probe(payload(await client.call_tool('execute_javascript',{'code':spell_probe})))
        assert len(spell_samples)==9
        for sample in spell_samples:
            rows=[];spell_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if spell_cursor:args['cursor']=spell_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                spell_cursor=page['pagination']['next_cursor']
                if not spell_cursor:break
            assert spell_cursor is None and page['sections'][0]['status']=='complete'
            assert len({row['raw'][0]['path'] for row in rows})==len(rows)
            for path,expected in [('/system/level/value',sample['base']),('/system/time/value',sample['time'])]:
                row=next(row for row in rows if row['raw'][0]['path']==path)
                assert row['raw'][0]['value']==expected and row['provenance']['mapping']=='pf2e.spell.source.v1'
            for component in sample['damage']:
                key=component['key'].replace('~','~0').replace('/','~1');path='/system/damage/'+key
                assert next(row for row in rows if row['raw'][0]['path']==path+'/formula')['raw'][0]['value']==component['formula']
                if component.get('kinds'):
                    assert [row['raw'][0]['value'] for row in rows if row['raw'][0]['path'].startswith(path+'/kinds/')]==component['kinds']
            relation=payload(await client.call_tool('read_item',{'item_uuid':sample['uuid'],'sections':['relationships']}))['records'][0]['mapped']['value']
            if sample['entry_uuid']:
                assert relation['status']=='resolved' and relation['target_uuid']==sample['entry_uuid']
                follow=payload(await client.call_tool('read_item',{'item_uuid':relation['target_uuid'],'sections':['identity']}))
                assert follow['identity']['type']=='spellcastingEntry'
            else:assert relation['status'] in ('missing','unverified')
            description=[];spell_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['description'],'limit':25}
                if spell_cursor:args['cursor']=spell_cursor
                page=payload(await client.call_tool('read_item',args));description.extend(page['records'])
                spell_cursor=page['pagination']['next_cursor']
                if not spell_cursor:break
            assert spell_cursor is None
            text=''.join(row['raw'][0]['value'] for row in description if row['raw'][0]['path']=='/system/description/value')
            assert hashlib.sha256(text.encode()).hexdigest()==sample['description_sha256']
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
        consumable_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.equipment-srd');
const index=await pack.getIndex({fields:['type','system.category','system.damage','system.spell']});
const rows=index.filter(row=>row.type==='consumable');
const owned=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type)).flatMap(a=>a.items.contents).find(i=>i.type==='consumable');
const candidates=[owned,...[rows.find(row=>row.system?.category==='scroll'&&row.system?.spell==null),rows.find(row=>row.system?.damage?.kind==='healing'),rows.find(row=>row.system?.damage?.kind==='damage'),rows.find(row=>row.system?.spell)].filter(Boolean).map(row=>pack.getUuid(row._id))];
const report=[];for(const selected of candidates){const doc=typeof selected==='string'?await foundry.utils.fromUuid(selected):selected;if(!doc)continue;const source=doc.toObject(true),s=source.system;const expected={'/system/category':s.category,'/system/quantity':s.quantity,'/system/uses/value':s.uses.value,'/system/uses/max':s.uses.max,'/system/uses/autoDestroy':s.uses.autoDestroy};if(s.damage===null)expected['/system/damage']=null;else for(const key of ['formula','type','kind'])expected['/system/damage/'+key]=s.damage[key];if(s.spell===null)expected['/system/spell']=null;else{expected['/system/spell/name']=s.spell.name;expected['/system/spell/system/level/value']=s.spell.system.level.value;expected['/system/spell/system/time/value']=s.spell.system.time.value;if(Object.hasOwn(s.spell.system.location,'heightenedLevel'))expected['/system/spell/system/location/heightenedLevel']=s.spell.system.location.heightenedLevel;}const text=s.spell?.system.description.value;report.push({uuid:doc.uuid,expected,revision:await digest(source),...(typeof text==='string'?{spell_description_sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),v=>v.toString(16).padStart(2,'0')).join('')}:{})});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        consumable_samples=probe(payload(await client.call_tool('execute_javascript',{'code':consumable_probe})))
        assert len(consumable_samples)==5
        for sample in consumable_samples:
            rows=[];consumable_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if consumable_cursor:args['cursor']=consumable_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert 'contained_spell_mapping_pending' not in page['sections'][0]['reasons']
                assert page['sections'][1]['status']=='unsupported'
                consumable_cursor=page['pagination']['next_cursor']
                if not consumable_cursor:break
            assert consumable_cursor is None and page['sections'][0]['status']=='complete' and len({row['raw'][0]['path'] for row in rows})==len(rows)
            for path,expected in sample['expected'].items():
                assert next(row for row in rows if row['raw'][0]['path']==path)['raw'][0]['value']==expected
            assert next(row for row in rows if row['raw'][0]['path']=='/system/category')['provenance']['mapping']=='pf2e.consumable.source.v1'
            assert all(row['raw'][0]['document_uuid']==sample['uuid'] for row in rows)
            if 'spell_description_sha256' in sample:
                description=[];contained_cursor=None
                for _ in range(100):
                    args={'item_uuid':sample['uuid'],'sections':['description'],'limit':25}
                    if contained_cursor:args['cursor']=contained_cursor
                    page=payload(await client.call_tool('read_item',args));description.extend(page['records'])
                    contained_cursor=page['pagination']['next_cursor']
                    if not contained_cursor:break
                assert contained_cursor is None
                text=''.join(row['raw'][0]['value'] for row in description if row['raw'][0]['path']=='/system/spell/system/description/value')
                assert hashlib.sha256(text.encode()).hexdigest()==sample['spell_description_sha256']
                assert all(row['raw'][0]['document_uuid']==sample['uuid'] for row in description)
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
        equipment_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.equipment-srd');
const index=await pack.getIndex({fields:['type','system.traits.value','system.description.value']});
const equipment=index.filter(row=>row.type==='equipment');
const owned=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type)).flatMap(a=>a.items.contents).find(i=>i.type==='equipment'&&/activate/i.test(i.toObject(true).system.description.value));
const candidates=[owned,...[equipment.find(row=>row.system?.traits?.value?.includes('invested')&&/activate/i.test(row.system?.description?.value)),equipment.find(row=>!row.system?.traits?.value?.includes('invested'))].filter(Boolean).map(row=>pack.getUuid(row._id))];
const report=[];for(const selected of candidates){const doc=typeof selected==='string'?await foundry.utils.fromUuid(selected):selected;if(!doc)continue;const source=doc.toObject(true);report.push({uuid:doc.uuid,usage:source.system.usage.value,invested:source.system.equipped.invested,traits:source.system.traits.value,revision:await digest(source),description_sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source.system.description.value))),v=>v.toString(16).padStart(2,'0')).join('')});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        equipment_samples=probe(payload(await client.call_tool('execute_javascript',{'code':equipment_probe})))
        assert len(equipment_samples)==3
        for sample in equipment_samples:
            rows=[];equipment_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if equipment_cursor:args['cursor']=equipment_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                equipment_cursor=page['pagination']['next_cursor']
                if not equipment_cursor:break
            assert equipment_cursor is None and len({row['raw'][0]['path'] for row in rows})==len(rows)
            for path,expected in [('/system/usage/value',sample['usage']),('/system/equipped/invested',sample['invested'])]:
                assert next(row for row in rows if row['raw'][0]['path']==path)['raw'][0]['value']==expected
            trait_rows=[row for row in rows if row['raw'][0]['path'].startswith('/system/traits/value/')]
            assert [row['raw'][0]['value'] for row in trait_rows]==sample['traits']
            assert all(row['provenance']['mapping']=='pf2e.equipment.source.v1' for row in trait_rows)
            description=[];equipment_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['description'],'limit':1,'max_bytes':8000}
                if equipment_cursor:args['cursor']=equipment_cursor
                page=payload(await client.call_tool('read_item',args));description.extend(page['records'])
                equipment_cursor=page['pagination']['next_cursor']
                if not equipment_cursor:break
            assert equipment_cursor is None
            text=''.join(row['raw'][0]['value'] for row in description if row['raw'][0]['path']=='/system/description/value')
            assert hashlib.sha256(text.encode()).hexdigest()==sample['description_sha256']
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
        shield_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.equipment-srd');
const index=await pack.getIndex({fields:['type','system.runes.reinforcing','system.traits.integrated','system.specific']});
const shields=index.filter(row=>row.type==='shield');
const candidates=[];for(const match of [row=>row.system?.runes?.reinforcing>0,row=>row.system?.traits?.integrated,row=>row.system?.specific]){const row=shields.find(row=>match(row)&&!candidates.some(prior=>prior._id===row._id));if(row)candidates.push(row);}
const report=[];for(const row of candidates){const uuid=pack.getUuid(row._id);const source=(await foundry.utils.fromUuid(uuid)).toObject(true);report.push({uuid,reinforcing:source.system.runes.reinforcing,hp:source.system.hp.value,max:source.system.hp.max,hardness:source.system.hardness,revision:await digest(source)});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        shield_samples=probe(payload(await client.call_tool('execute_javascript',{'code':shield_probe})))
        assert len(shield_samples)==3
        for sample in shield_samples:
            rows=[];shield_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if shield_cursor:args['cursor']=shield_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                shield_cursor=page['pagination']['next_cursor']
                if not shield_cursor:break
            assert shield_cursor is None and len({row['raw'][0]['path'] for row in rows})==len(rows)
            for path,expected in [('/system/runes/reinforcing',sample['reinforcing']),('/system/hp/value',sample['hp']),('/system/hp/max',sample['max']),('/system/hardness',sample['hardness'])]:
                row=next(row for row in rows if row['raw'][0]['path']==path)
                assert row['raw'][0]['value']==expected
            assert next(row for row in rows if row['raw'][0]['path']=='/system/runes/reinforcing')['provenance']['mapping']=='pf2e.shield.source.v1'
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
        armor_probe="""
const pack=game.packs.get('pf2e.equipment-srd');
const index=await pack.getIndex({fields:['type','system.strength','system.specific']});
const armor=index.filter(row=>row.type==='armor');
const candidates=[armor.find(row=>row.system?.specific),armor.find(row=>row.system?.strength===null),armor.find(row=>row.system?.strength===0)].filter(Boolean);
const report=[];for(const row of candidates){const uuid=pack.getUuid(row._id);const source=(await foundry.utils.fromUuid(uuid)).toObject(true);report.push({uuid,strength:source.system.strength,ac_bonus:source.system.acBonus});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        pack_armor=probe(payload(await client.call_tool('execute_javascript',{'code':armor_probe})))
        armor_samples=[*selection['armor_samples'],*pack_armor]
        assert selection['armor_samples'] and len(pack_armor)==3
        for sample in armor_samples:
            rows=[];armor_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if armor_cursor:args['cursor']=armor_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                armor_cursor=page['pagination']['next_cursor']
                if not armor_cursor:break
            assert armor_cursor is None and len({row['raw'][0]['path'] for row in rows})==len(rows)
            for path,expected in [('/system/strength',sample['strength']),('/system/acBonus',sample['ac_bonus'])]:
                row=next(row for row in rows if row['raw'][0]['path']==path)
                assert row['raw'][0]['value']==expected and row['provenance']['mapping']=='pf2e.armor.source.v1'
        ammo_probe="""
const pack=game.packs.get('pf2e.equipment-srd');
const index=await pack.getIndex({fields:['type','system.craftableAs']});
const ammo=index.filter(row=>row.type==='ammo');
const candidates=[ammo.find(row=>row.system?.craftableAs===null),ammo.find(row=>Array.isArray(row.system?.craftableAs)&&row.system.craftableAs.length===0),ammo.find(row=>row.system?.craftableAs?.length)].filter(Boolean);
const report=[];for(const row of candidates){const uuid=pack.getUuid(row._id);const source=(await foundry.utils.fromUuid(uuid)).toObject(true);report.push({uuid,value:source.system.uses.value,max:source.system.uses.max,craftable_as:source.system.craftableAs});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        pack_ammo=probe(payload(await client.call_tool('execute_javascript',{'code':ammo_probe})))
        ammo_samples=[*selection['ammo_samples'],*pack_ammo]
        assert pack_ammo
        for sample in ammo_samples:
            rows=[];ammo_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if ammo_cursor:args['cursor']=ammo_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                ammo_cursor=page['pagination']['next_cursor']
                if not ammo_cursor:break
            assert ammo_cursor is None and len({row['raw'][0]['path'] for row in rows})==len(rows)
            crafting=[row['raw'][0] for row in rows if row['raw'][0]['path'].startswith('/system/craftableAs')]
            expected_crafting=sample['craftable_as']
            if expected_crafting is None or expected_crafting==[]:assert len(crafting)==1 and crafting[0]['value']==expected_crafting
            else:assert [raw['value'] for raw in crafting]==expected_crafting
            for path,expected in [('/system/uses/value',sample['value']),('/system/uses/max',sample['max'])]:
                row=next(row for row in rows if row['raw'][0]['path']==path)
                assert row['raw'][0]['value']==expected and row['provenance']['mapping']=='pf2e.ammo.source.v1'
        weapon_probe="""
const pack=game.packs.get('pf2e.equipment-srd');
const index=await pack.getIndex({fields:['type','system.ammo','system.damage.persistent','system.meleeUsage','system.specific']});
const weapons=index.filter(row=>row.type==='weapon');
const candidates=[weapons.find(row=>row.system?.ammo),weapons.find(row=>row.system?.damage?.persistent),weapons.find(row=>row.system?.meleeUsage),weapons.find(row=>row.system?.specific)].filter(Boolean);
const report=[];for(const row of candidates){const uuid=pack.getUuid(row._id);const source=(await foundry.utils.fromUuid(uuid)).toObject(true);report.push({uuid,range:source.system.range,category:source.system.category,damage_type:source.system.damage.damageType});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        pack_weapons=probe(payload(await client.call_tool('execute_javascript',{'code':weapon_probe})))
        weapon_samples=[*selection['weapon_samples'],*pack_weapons]
        assert selection['weapon_samples'] and len(pack_weapons)==4
        for sample in weapon_samples:
            rows=[];weapon_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if weapon_cursor:args['cursor']=weapon_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                weapon_cursor=page['pagination']['next_cursor']
                if not weapon_cursor:break
            assert weapon_cursor is None
            assert len({row['raw'][0]['path'] for row in rows})==len(rows)
            selected_ammo=next(row['raw'][0] for row in rows if row['raw'][0]['path']=='/system/selectedAmmoId')
            relations=payload(await client.call_tool('read_item',{'item_uuid':sample['uuid'],'sections':['relationships']}))
            assert relations['pagination']['complete'] and len(relations['records'])==1
            ref=relations['records'][0]
            assert ref['raw'][0]==selected_ammo and ref['provenance']['mapping']=='pf2e.weapon.selected-ammo.v1'
            assert ref['mapped']['value']=={'status':'missing','target_uuid':None}
            for path,expected in [('/system/range',sample['range']),('/system/category',sample['category']),('/system/damage/damageType',sample['damage_type'])]:
                row=next(row for row in rows if row['raw'][0]['path']==path)
                assert row['raw'][0]['value']==expected and row['provenance']['mapping']=='pf2e.weapon.source.v1'
        condition_samples=selection['condition_samples']
        condition_probe="""
const pack=game.packs.get('pf2e.conditionitems');
const index=await pack.getIndex({fields:['type','system.value.isValued','system.overrides']});
const conditions=index.filter(row=>row.type==='condition');
const candidates=[conditions.find(row=>row.system?.value?.isValued===true),conditions.find(row=>row.system?.value?.isValued===false),conditions.find(row=>row.system?.overrides?.length)].filter(Boolean);
const report=[];
for(const row of candidates){const uuid=pack.getUuid(row._id);const source=(await foundry.utils.fromUuid(uuid)).toObject(true);report.push({uuid,is_valued:source.system.value.isValued,value:source.system.value.value,override_slugs:source.system.overrides});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        pack_conditions=probe(payload(await client.call_tool('execute_javascript',{'code':condition_probe})))
        assert condition_samples and len(pack_conditions)==3
        for sample in [*condition_samples,*pack_conditions]:
            records=[];condition_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if condition_cursor:args['cursor']=condition_cursor
                page=payload(await client.call_tool('read_item',args));records.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                condition_cursor=page['pagination']['next_cursor']
                if not condition_cursor:break
            assert condition_cursor is None
            for path,expected in [('/system/value/isValued',sample['is_valued']),('/system/value/value',sample['value'])]:
                row=next(row for row in records if row['raw'][0]['path']==path)
                assert row['raw'][0]['value']==expected and row['provenance']['mapping']=='pf2e.condition.source.v1'
            relations=payload(await client.call_tool('read_item',{'item_uuid':sample['uuid'],'sections':['relationships'],'limit':100}))
            assert relations['pagination']['complete']
            assert all(row['mapped']['value']['status'] in ('missing','unverified') for row in relations['records'])
            assert all(row['mapped']['value']['target_uuid'] is None for row in relations['records'])
            if 'override_slugs' in sample:
                assert [row['raw'][0]['value'] for row in records if row['raw'][0]['path'].startswith('/system/overrides/')]==sample['override_slugs']
        effect_samples=selection['effect_samples']
        assert effect_samples
        effect_probe="""
const pack=game.packs.get('pf2e.spell-effects');
const index=await pack.getIndex({fields:['type','system.badge.type','system.duration.unit']});
const effects=index.filter(row=>row.type==='effect');
const candidates=[effects.find(row=>row.system?.badge?.type==='formula'),effects.find(row=>row.system?.duration?.unit==='encounter')].filter(Boolean);
const report=[];
for(const row of candidates){const uuid=pack.getUuid(row._id);const doc=await foundry.utils.fromUuid(uuid);const source=doc.toObject(true);report.push({uuid,unit:source.system.duration.unit,badge:source.system.badge?.type??null});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        pack_effects=probe(payload(await client.call_tool('execute_javascript',{'code':effect_probe})))
        # Development results may wrap arrays; compact report uses bounded JSON.
        if not isinstance(pack_effects,list):raise AssertionError('Expected selected pack effect candidates.')
        for sample in [*effect_samples,*pack_effects]:
            records=[];effect_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if effect_cursor:args['cursor']=effect_cursor
                page=payload(await client.call_tool('read_item',args));records.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                effect_cursor=page['pagination']['next_cursor']
                if not effect_cursor:break
            assert effect_cursor is None
            relationships=payload(await client.call_tool('read_item',{'item_uuid':sample['uuid'],'sections':['relationships'],'limit':25}))
            assert len(relationships['records'])==5 and relationships['pagination']['complete']
            assert all(row['mapped']['value']=={'status':'missing','target_uuid':None} for row in relationships['records'])
            unit=next(row for row in records if row['raw'][0]['path']=='/system/duration/unit')
            assert unit['raw'][0]['value']==sample['unit'] and unit['provenance']['mapping']=='pf2e.effect.source.v1'
            badge=next((row for row in records if row['raw'][0]['path']=='/system/badge/type'),None)
            if sample['badge'] is not None:assert badge and badge['raw'][0]['value']==sample['badge']
        after=probe(payload(await client.call_tool('execute_javascript',{'code':selector_probe})))
        assert after['action_samples']==selection['action_samples']
        assert len(selection['melee_samples'])==3, 'Existing explicit range/thrown/effect-label attack samples are missing.'
        for sample in selection['melee_samples']:
            attack=payload(await client.call_tool('read_item',{'item_uuid':sample['uuid'],'sections':['source','relationships','effective'],'limit':100}))
            assert attack['identity']['type']=='melee'
            assert attack['sections'][0]['status']=='complete' and attack['sections'][2]['status']=='unsupported'
            if sample['context']=='explicit_range':
                assert any(record['raw'][0]['path'].startswith('/system/range/') for record in attack['records'])
            elif sample['context']=='null_thrown':
                assert next(record for record in attack['records'] if record['raw'][0]['path']=='/system/range')['mapped']['value']=='no_explicit_range'
            else:
                assert any(record['kind']=='relationship' and record['mapped']['value']['status']=='unverified' for record in attack['records'])
        monster_packs=payload(await client.call_tool('list_actor_compendiums',{'document_type':'Actor','query':'monster','limit':10}))
        assert monster_packs['nodes']
        monsters=payload(await client.call_tool('search_compendium_actors',{'pack_ids':[node['id'] for node in monster_packs['nodes']],'query':'a','types':['npc'],'limit':1}))
        assert monsters['nodes']
        pack_attacks=payload(await client.call_tool('list_actor_items',{'actor_uuid':monsters['nodes'][0]['identity']['uuid'],'types':['melee'],'limit':1}))
        assert pack_attacks['nodes']
        attack_call=pack_attacks['nodes'][0]['next_call']
        pack_attack=payload(await client.call_tool(attack_call['tool'],dict(attack_call['arguments'],limit=100)))
        assert pack_attack['identity']['source_kind']=='compendium' and pack_attack['identity']['actor']
        after=probe(payload(await client.call_tool('execute_javascript',{'code':selector_probe})))
        assert after['source_fingerprints']==selection['source_fingerprints']
        assert selection.get('lore_item_uuid') and selection.get('lore_actor_uuid'), 'Existing NPC Lore fixture is unavailable.'
        lore=payload(await client.call_tool('read_item',{'item_uuid':selection['lore_item_uuid'],'limit':100}))
        assert lore['identity']['actor']['type']=='npc'
        modifier=next(record for record in lore['records'] if record['raw'][0]['path']=='/system/mod/value')
        assert modifier['mapped']['concept']=='npc_lore_authored_modifier'
        assert modifier['mapped']['value']==modifier['raw'][0]['value']
        rank=next(record for record in lore['records'] if record['raw'][0]['path']=='/system/proficient/value')
        assert rank['mapped']['value']['rank']==rank['raw'][0]['value']
        skills=payload(await client.call_tool('read_actor',{'actor_uuid':selection['lore_actor_uuid'],'sections':['skills'],'limit':100}))
        assert skills['sections'][0]['status']=='partial' and 'other_skills_pending' in skills['sections'][0]['reasons']
        assert any(record['mapped']['value']['target_uuid']==selection['lore_item_uuid'] for record in skills['records'])
        for record in skills['records']:
            value=record['mapped']['value']
            if value['status']!='resolved':continue
            followed=payload(await client.call_tool('read_item',{'item_uuid':value['target_uuid'],'sections':['identity']}))
            assert followed['identity']['type']=='lore' and followed['identity']['actor']['type']=='npc'
        after=probe(payload(await client.call_tool('execute_javascript',{'code':selector_probe})))
        assert after['source_fingerprints']==selection['source_fingerprints']
        registry=await client.call_tool('get_actor_types',{})
        assert registry.data['availability']['supported']
        action_support=next(entry for entry in registry.data['item_types'] if entry['type']=='action')
        assert action_support['mapped_supported'] and not action_support['effective_supported']
        assert action_support['verification']['live']['status']=='passed'
        spell_support=next(entry for entry in registry.data['item_types'] if entry['type']=='spell')
        assert spell_support['mapped_supported'] and not spell_support['effective_supported']
        assert spell_support['verification']['live']['status']=='passed'
        consumable_support=next(entry for entry in registry.data['item_types'] if entry['type']=='consumable')
        assert consumable_support['mapped_supported'] and not consumable_support['effective_supported']
        assert consumable_support['verification']['live']['status']=='passed'
        assert 'contained spell definitions' in ' '.join(consumable_support['limitations'])
        equipment_support=next(entry for entry in registry.data['item_types'] if entry['type']=='equipment')
        assert equipment_support['mapped_supported'] and not equipment_support['effective_supported']
        assert equipment_support['verification']['live']['status']=='passed'
        shield_support=next(entry for entry in registry.data['item_types'] if entry['type']=='shield')
        assert shield_support['mapped_supported'] and not shield_support['effective_supported']
        assert shield_support['verification']['live']['status']=='passed'
        armor_support=next(entry for entry in registry.data['item_types'] if entry['type']=='armor')
        assert armor_support['mapped_supported'] and not armor_support['effective_supported']
        assert armor_support['verification']['live']['status']=='passed'
        ammo_support=next(entry for entry in registry.data['item_types'] if entry['type']=='ammo')
        assert ammo_support['mapped_supported'] and not ammo_support['effective_supported']
        assert ammo_support['verification']['live']['status']=='passed'
        weapon_support=next(entry for entry in registry.data['item_types'] if entry['type']=='weapon')
        assert weapon_support['mapped_supported'] and not weapon_support['effective_supported']
        assert weapon_support['verification']['live']['status']=='passed'
        affliction_support=next(entry for entry in registry.data['item_types'] if entry['type']=='affliction')
        assert not affliction_support['source_supported'] and not affliction_support['mapped_supported'] and not affliction_support['effective_supported']
        assert affliction_support['verification']['live']['status']=='not_run'
        condition_support=next(entry for entry in registry.data['item_types'] if entry['type']=='condition')
        assert condition_support['mapped_supported'] and not condition_support['effective_supported']
        assert condition_support['verification']['live']['status']=='passed'
        effect_support=next(entry for entry in registry.data['item_types'] if entry['type']=='effect')
        assert effect_support['mapped_supported'] and not effect_support['effective_supported']
        assert effect_support['verification']['live']['status']=='passed'
        attack_support=next(entry for entry in registry.data['item_types'] if entry['type']=='melee')
        assert attack_support['mapped_supported'] and not attack_support['effective_supported']
        assert attack_support['verification']['live']['status']=='passed'
        print(json.dumps({'passed':True,'discovered':sorted(needed),'source_pages':source_pages,'spell_source_samples_verified':len(spell_samples),'consumable_source_samples_verified':len(consumable_samples),'equipment_source_samples_verified':len(equipment_samples),'shield_pack_samples_verified':len(shield_samples),'armor_source_samples_verified':len(armor_samples),'ammo_source_samples_verified':len(ammo_samples),'weapon_missing_selection_verified':True,'weapon_source_samples_verified':len(weapon_samples),'condition_empty_reference_relationships_verified':True,'condition_source_samples_verified':len(condition_samples)+len(pack_conditions),'effect_source_samples_verified':len(effect_samples)+len(pack_effects),'effect_empty_context_relationships_verified':True,'npc_source_verified':True,'npc_notes_verified':True,'npc_item_references_verified':reference_count,'item_owner_verified':True,'pack_hydration_verified':True,'physical_types_verified':physical_verified,'token_verified':bool(selection.get('token_uuid')),'lore_source_skills_verified':True,'attack_source_contexts_verified':3,'pack_attack_verified':True,'activation_modes_verified':4,'self_effect_followup_verified':True,'familiar_action_pack_verified':True,'runtime':actor.data['runtime']}))
async def browser_status(refresh=False):
    import httpx, websockets
    root=Path(__file__).resolve().parent.parent
    port=(root / '.browser-dev/chrome-profile/DevToolsActivePort').read_text().splitlines()[0]
    async with httpx.AsyncClient(trust_env=False) as http:
        pages=(await http.get('http://127.0.0.1:'+port+'/json/list')).json()
    tabs=[p for p in pages if p.get('type')=='page' and p.get('url','').startswith('http://localhost:30000/')]
    if len(tabs)!=1:raise RuntimeError('Expected one existing development Foundry tab.')
    async with websockets.connect(tabs[0]['webSocketDebuggerUrl']) as ws:
        if refresh:
            await ws.send(json.dumps({'id':3,'method':'Page.reload'}))
            while True:
                reply=json.loads(await asyncio.wait_for(ws.recv(),5))
                if reply.get('id')==3:
                    if 'error' in reply:raise RuntimeError('Development browser reload failed.')
                    print(json.dumps({'refresh_requested':True}));return
        await ws.send(json.dumps({'id':1,'method':'Runtime.enable'}))
        console_errors=0
        while True:
            r=json.loads(await asyncio.wait_for(ws.recv(),5))
            if r.get('method')=='Runtime.exceptionThrown' or (r.get('method')=='Runtime.consoleAPICalled' and r.get('params',{}).get('type')=='error'):console_errors+=1
            if r.get('id')==1:break
        expression="JSON.stringify({ready:!!globalThis.game?.ready,isGM:!!globalThis.game?.user?.isGM,version:globalThis.game?.version,url:location.pathname})"
        await ws.send(json.dumps({'id':2,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True}}))
        while True:
            r=json.loads(await asyncio.wait_for(ws.recv(),5))
            if r.get('id')==2:
                value=json.loads(r.get('result',{}).get('result',{}).get('value','{}'))
                value['console_errors']=console_errors
                print(json.dumps(value));break

if __name__=='__main__':
    asyncio.run(browser_status(refresh=sys.argv[1:]==['--refresh']) if sys.argv[1:] in (['--browser'],['--refresh']) else main())
