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
        assert 'resolve_journal_reference' in available
        assert available['resolve_journal_reference'].annotations.readOnlyHint
        assert 'target' in available['resolve_journal_reference'].inputSchema['required']
        assert 'untruncated' in available['resolve_journal_reference'].description
        journal_candidates=payload(await client.call_tool('search_journals',dict(query='Zantus',limit=2)))
        journal_page=next(row for row in journal_candidates['matches'] if row['page_name']=='The Violated Grave')
        journal_source=payload(await client.call_tool('read_journal_page',dict(page_uuid=journal_page['page_uuid'],max_chars=20000)))
        assert journal_source['complete'] and journal_source['references_complete']
        source_refs=journal_source['references']
        actor_ref=next(row for row in source_refs if row['target'].startswith('Actor.'))
        item_ref=next(row for row in source_refs if row['target'].startswith('Compendium.') and '.Item.' in row['target'])
        for reference in (actor_ref,item_ref):
            follow=reference['resolve_next_call']
            resolved=payload(await client.call_tool(follow['tool'],follow['arguments']))
            assert resolved['status']=='resolved' and resolved['identity']['uuid']==reference['target']
            assert resolved['anchor'] is None
            target=resolved['next_call']
            identity=payload(await client.call_tool(target['tool'],dict(**target['arguments'],sections=['identity'],limit=1)))
            assert identity['identity']['uuid']==resolved['identity']['uuid']
            if resolved['identity']['document_name']=='Actor':
                owned=payload(await client.call_tool('list_actor_items',dict(**target['arguments'],limit=1)))
                item=owned['nodes'][0]['next_call']
                child=payload(await client.call_tool(item['tool'],dict(**item['arguments'],sections=['identity'],limit=1)))
                assert child['identity']['actor']['uuid']==resolved['identity']['uuid']
        journal_again=payload(await client.call_tool('read_journal_page',dict(page_uuid=journal_page['page_uuid'],max_chars=20000)))
        assert journal_again['content']==journal_source['content'] and journal_again['revision']==journal_source['revision']
        assert 'description' in available['read_actor'].inputSchema['properties']['sections']['items']['enum']
        assert 'GM-private biography' in available['read_actor'].description
        assert 'Missing structured activation fields do not mean no ability' in available['read_item'].description
        assert 'equipment Items' in available['read_item'].description
        assert 'consumable Items expose selected source' in available['read_item'].description
        assert 'rank is stored base rank, not heightened casting rank' in available['read_item'].description
        assert 'spell Items expose selected definition source' in available['read_item'].description
        assert 'actual owner' in available['read_item'].description
        assert 'spellcastingEntry Items expose stored tradition' in available['read_item'].description
        assert 'slot11 is retained without spell-rank semantics' in available['read_item'].description
        assert 'Missing id/expended fields stay absent' in available['read_item'].description
        assert 'Spellcasting exposes owned spell/casting-entry identities' in available['read_actor'].description
        assert 'availability_not_evaluated' in available['read_actor'].description
        assert 'backpack Items are containers' in available['read_item'].description
        assert 'container_content returns each reachable' in available['read_item'].description
        assert 'treasure Items expose nullable category' in available['read_item'].description
        assert 'Quantity and price.per are independent stored values' in available['read_item'].description
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
        treasure_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const actors=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type)),owned=actors.flatMap(a=>a.items.contents).find(i=>i.type==='treasure');
const token=game.scenes.contents.flatMap(s=>s.tokens.contents).find(t=>!t.isLinked&&['character','npc','familiar'].includes(t.actor?.type)&&t.actor.items.some(i=>i.type==='treasure'));
const pack=game.packs.get('pf2e.equipment-srd'),index=await pack.getIndex({fields:['type','system.category']});const rows=index.filter(r=>r.type==='treasure');
const candidates=[...(owned?[{doc:owned}]:[]),...(token?[{doc:token.actor.items.find(i=>i.type==='treasure'),token_uuid:token.uuid}]:[]),...['coin','gem','art-object',null].map(category=>rows.find(r=>category===null?r.system?.category==null:r.system?.category===category)).filter(Boolean).map(row=>({uuid:pack.getUuid(row._id)}))];
const report=[];for(const candidate of candidates){const doc=candidate.doc??await foundry.utils.fromUuid(candidate.uuid),source=doc.toObject(true),s=source.system,expected={'/system/category':s.category,'/system/quantity':s.quantity,'/system/price/per':s.price.per};for(const key of ['pp','gp','sp','cp'])if(Object.hasOwn(s.price.value,key))expected['/system/price/value/'+key]=s.price.value[key];report.push({uuid:doc.uuid,...(candidate.token_uuid?{token_uuid:candidate.token_uuid}:{}),expected,revision:await digest(source),description_sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s.description.value))),v=>v.toString(16).padStart(2,'0')).join('')});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        treasure_samples=probe(payload(await client.call_tool('execute_javascript',{'code':treasure_probe})))
        assert len(treasure_samples)==6 and any(s.get('token_uuid') for s in treasure_samples)
        for sample in treasure_samples:
            rows=[];treasure_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if sample.get('token_uuid'):args['token_uuid']=sample['token_uuid']
                if treasure_cursor:args['cursor']=treasure_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                treasure_cursor=page['pagination']['next_cursor']
                if not treasure_cursor:break
            assert treasure_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['raw'][0]['path'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():assert next(r for r in rows if r['raw'][0]['path']==path)['raw'][0]['value']==expected
            assert next(r for r in rows if r['raw'][0]['path']=='/system/category')['provenance']['mapping']=='pf2e.treasure.source.v1'
            assert not any('/usage/' in r['raw'][0]['path'] or '/equipped/invested'==r['raw'][0]['path'] for r in rows)
            if sample.get('token_uuid'):assert page['identity']['instance']['token_uuid']==sample['token_uuid']
            description=[];treasure_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['description'],'limit':25}
                if sample.get('token_uuid'):args['token_uuid']=sample['token_uuid']
                if treasure_cursor:args['cursor']=treasure_cursor
                page=payload(await client.call_tool('read_item',args));description.extend(page['records'])
                treasure_cursor=page['pagination']['next_cursor']
                if not treasure_cursor:break
            text=''.join(r['raw'][0]['value'] for r in description if r['raw'][0]['path']=='/system/description/value')
            assert treasure_cursor is None and hashlib.sha256(text.encode()).hexdigest()==sample['description_sha256']
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
        container_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const physical=['weapon','armor','shield','equipment','consumable','ammo','backpack','book','treasure'];
const owned=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type)).flatMap(a=>a.items.contents).filter(i=>i.type==='backpack');
const pack=game.packs.get('pf2e.equipment-srd'),index=await pack.getIndex({fields:['type','system.stowing','system.bulk']});const rows=index.filter(r=>r.type==='backpack');
const candidates=[...owned,...[rows.find(r=>r.system?.stowing===false),rows.find(r=>r.system?.stowing===true&&r.system?.bulk?.ignored>0)].filter(Boolean).map(row=>pack.getUuid(row._id))];
const report=[];for(const candidate of candidates){const doc=typeof candidate==='string'?await foundry.utils.fromUuid(candidate):candidate;const source=doc.toObject(true),s=source.system;const contents=[],seen=new Set([doc.id]),queue=[doc.id];if(doc.parent)for(let q=0;q<queue.length;q++)for(const item of doc.parent.items.values()){if(!physical.includes(item.type)||seen.has(item.id)||item.toObject(true).system.containerId!==queue[q])continue;seen.add(item.id);contents.push(item.uuid);queue.push(item.id);}report.push({uuid:doc.uuid,expected:{'/system/bulk/value':s.bulk.value,'/system/bulk/heldOrStowed':s.bulk.heldOrStowed,'/system/bulk/capacity':s.bulk.capacity,'/system/bulk/ignored':s.bulk.ignored,'/system/stowing':s.stowing},owned:!!doc.parent,contents,revision:await digest(source),...(doc.parent?{owner_uuid:doc.parent.uuid,owner_revision:await digest(doc.parent.toObject(true))}:{}),description_sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s.description.value))),v=>v.toString(16).padStart(2,'0')).join('')});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        container_samples=probe(payload(await client.call_tool('execute_javascript',{'code':container_probe})))
        assert len(container_samples)>=2
        container_owned_samples=sum(bool(s['owned']) for s in container_samples)
        for sample in container_samples:
            rows=[];container_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if container_cursor:args['cursor']=container_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                container_cursor=page['pagination']['next_cursor']
                if not container_cursor:break
            assert container_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['raw'][0]['path'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():assert next(r for r in rows if r['raw'][0]['path']==path)['raw'][0]['value']==expected
            relation=[];container_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['relationships'],'limit':2}
                if container_cursor:args['cursor']=container_cursor
                page=payload(await client.call_tool('read_item',args));relation.extend(page['records'])
                container_cursor=page['pagination']['next_cursor']
                if not container_cursor:break
            assert container_cursor is None
            contents=[r['mapped']['value']['target_uuid'] for r in relation if r['mapped']['concept']=='container_content']
            assert len(contents)==len(set(contents)) and set(contents)==set(sample['contents'])
            if sample['owned']:assert page['sections'][0]['status']=='complete'
            else:assert page['sections'][0]['status']=='partial' and 'container_scope_unverified' in page['sections'][0]['reasons']
            description=[];container_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['description'],'limit':25}
                if container_cursor:args['cursor']=container_cursor
                page=payload(await client.call_tool('read_item',args));description.extend(page['records'])
                container_cursor=page['pagination']['next_cursor']
                if not container_cursor:break
            text=''.join(r['raw'][0]['value'] for r in description if r['raw'][0]['path']=='/system/description/value')
            assert container_cursor is None and hashlib.sha256(text.encode()).hexdigest()==sample['description_sha256']
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
            if sample['owned']:
                owner_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const actor=await foundry.utils.fromUuid("+json.dumps(sample['owner_uuid'])+");return JSON.stringify({revision:await digest(actor.toObject(true))});"
                assert probe(payload(await client.call_tool('execute_javascript',{'code':owner_code})))['revision']==sample['owner_revision']
        assert 'inventory_item' in available['read_actor'].description
        assert 'kit Items expose' in available['read_item'].description
        assert 'ancestry Items expose' in available['read_item'].description
        assert 'background Items expose' in available['read_item'].description
        assert 'heritage Items expose' in available['read_item'].description
        assert 'class Items expose' in available['read_item'].description
        assert 'feat Items expose' in available['read_item'].description
        # Feat definition source only: no acquired-grant fixture is available.
        feat_selectors_probe="""
const rows=[];for(const [id,names]of [['pf2e.feats-srd',['Battle Medicine']],['pf2e.ancestryfeatures',['Awakened Mind']],['pf2e.classfeatures',['Quick-Tempered','Versatile Legend']]]){const pack=game.packs.get(id);if(!pack?.testUserPermission(game.user,'OBSERVER'))throw Error('Unreadable feat fixture pack');const index=await pack.getIndex({fields:['type']});for(const name of names){const matches=[...index].filter(r=>r.type==='feat'&&r.name===name);if(matches.length!==1)throw Error('Missing or ambiguous existing feat fixture');rows.push({uuid:pack.getUuid(matches[0]._id)});}}return JSON.stringify(rows).match(/[\\s\\S]{1,800}/g);
"""
        feat_samples=probe(payload(await client.call_tool('execute_javascript',{'code':feat_selectors_probe})))
        assert len(feat_samples)==4
        feat_source_pages=0;feat_source_records=0
        for selector in feat_samples:
            feat_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const doc=await foundry.utils.fromUuid(FEAT_UUID);if(!doc?.testUserPermission(game.user,'OBSERVER'))throw Error('Unreadable feat fixture');const s=doc.toObject(true),expected={};
const esc=s=>s.replaceAll('~','~0').replaceAll('/','~1');
const pick=path=>{let value=s,present=true;for(const k of path.slice(1).split('/').map(k=>k.replaceAll('~1','/').replaceAll('~0','~'))){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}if(value===undefined)present=false;expected[path]={present,...(present?{value}:{})};};
const array=path=>{pick(path);const selected=expected[path];if(selected.present&&Array.isArray(selected.value)&&selected.value.length){delete expected[path];selected.value.forEach((value,i)=>expected[path+'/'+i]={present:true,value});}};
for(const path of ['category','level/value','level/taken','onlyLevel1','maxTakable','actionType/value','actions/value','location','traits/rarity','slug','publication/title','publication/authors','publication/license','publication/remaster'])pick('/system/'+path);
for(const path of ['traits/value','traits/otherTags','subfeatures/keyOptions','subfeatures/suppressedFeatures'])array('/system/'+path);
const prerequisites=s.system.prerequisites.value;if(!prerequisites.length)pick('/system/prerequisites/value');else prerequisites.forEach((_,i)=>pick('/system/prerequisites/value/'+i+'/value'));
for(const key of ['frequency','selfEffect']){if(s.system[key]==null)pick('/system/'+key);else for(const leaf of key==='frequency'?['value','max','per']:['uuid','name'])pick('/system/'+key+'/'+leaf);}
const sub=s.system.subfeatures;for(const key of ['proficiencies','senses']){const entries=sub[key];if(!Object.keys(entries).length)pick('/system/subfeatures/'+key);else for(const name of Object.keys(entries))for(const leaf of key==='proficiencies'?['rank','attribute']:['acuity','range'])pick('/system/subfeatures/'+key+'/'+esc(name)+'/'+leaf);}
if(sub.languages===undefined)pick('/system/subfeatures/languages');else{pick('/system/subfeatures/languages/slots');array('/system/subfeatures/languages/granted');}
pick('/system/traits/toggles');pick('/flags/pf2e/rulesSelections');
return JSON.stringify({uuid:doc.uuid,expected,category:s.system.category,revision:await digest(s),description_sha256:await digest(s.system.description.value)}).match(/[\\s\\S]{1,800}/g);
""".replace('FEAT_UUID',json.dumps(selector['uuid']))
            sample=probe(payload(await client.call_tool('execute_javascript',{'code':feat_probe})))
            rows=[];feat_cursor=None;sample_pages=0
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['identity','source','description','effective'],limit=7)
                if feat_cursor:args['cursor']=feat_cursor
                page=payload(await client.call_tool('read_item',args));sample_pages+=1;feat_source_pages+=1
                assert page['identity']['uuid']==sample['uuid'] and page['identity']['type']=='feat'
                statuses={s['name']:s['status'] for s in page['sections']}
                assert statuses['effective']=='unsupported'
                rows.extend(page['records']);feat_cursor=page['pagination']['next_cursor']
                if not feat_cursor:break
            assert feat_cursor is None and statuses['source']=='complete' and statuses['description']=='complete'
            assert sample_pages>1 and len({r['key'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():
                row=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']==path)
                assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                assert row['provenance']['mapping']=='pf2e.feat.source.v1'
            category=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']=='/system/category')
            assert category['mapped']['value']==dict(code=sample['category'],kind='feature' if sample['category'] in ('ancestryfeature','classfeature') else 'feat')
            assert not any(r['section']=='relationships' for r in rows)
            prose=[r for r in rows if r['section']=='description' and r['raw'][0]['path']=='/system/description/value']
            text=''.join(r['raw'][0]['value'] for r in sorted(prose,key=lambda r:r.get('text',{}).get('start',0)))
            assert hashlib.sha256(json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==sample['description_sha256']
            # Existing compendium fixtures have no acquired grant records. Verify
            # their explicit absent/empty reference states without manufacturing any.
            references=payload(await client.call_tool('read_item',dict(item_uuid=sample['uuid'],sections=['relationships'],limit=100)))
            assert references['pagination']['next_cursor'] is None
            assert references['sections'][0]['status']=='complete'
            assert len(references['records'])==4
            expected_states={'/flags/pf2e/itemGrants':'missing','/flags/pf2e/grantedBy':'missing','/system/selfEffect':'missing','/system/subfeatures/suppressedFeatures':'empty'}
            for row in references['records']:
                assert row['mapped']['value']==dict(status=expected_states[row['raw'][0]['path']],target_uuid=None)
                assert row['provenance']['mapping']=='pf2e.feat.reference.v1'
            after=probe(payload(await client.call_tool('execute_javascript',{'code':feat_probe})))
            assert after['revision']==sample['revision']
            feat_source_records+=len(rows)
        assert 'deity Items expose' in available['read_item'].description
        deity_selectors_probe="""
const pack=game.packs.get('pf2e.deities'),index=await pack.getIndex({fields:['type']});return JSON.stringify(['Abadar','Asmodeus','Green Faith'].map(name=>{const row=[...index].find(r=>r.type==='deity'&&r.name===name);if(!row)throw Error('Missing existing deity fixture');return {uuid:pack.getUuid(row._id)};})).match(/[\\s\\S]{1,800}/g);
"""
        deity_samples=probe(payload(await client.call_tool('execute_javascript',{'code':deity_selectors_probe})))
        assert len(deity_samples)==3
        deity_reference_count=0
        for selector in deity_samples:
            deity_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const doc=await foundry.utils.fromUuid(DEITY_UUID),s=doc.toObject(true),expected={},references=[];
const esc=s=>s.replaceAll('~','~0').replaceAll('/','~1');
const pick=path=>{let value=s,present=true;for(const k of path.slice(1).split('/').map(k=>k.replaceAll('~1','/').replaceAll('~0','~'))){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}if(value===undefined)present=false;expected[path]={present,...(present?{value}:{})};};
const array=path=>{pick(path);const selected=expected[path];if(selected.present&&Array.isArray(selected.value)&&selected.value.length){delete expected[path];selected.value.forEach((value,i)=>expected[path+'/'+i]={present:true,value});}};
for(const path of ['category','slug','publication/title','publication/authors','publication/license','publication/remaster'])pick('/system/'+path);
if(s.system.sanctification===null)pick('/system/sanctification');else{pick('/system/sanctification/modal');array('/system/sanctification/what');}
for(const path of ['domains/primary','domains/alternate','font','attribute','skill','weapons','traits/otherTags'])array('/system/'+path);
const spells=s.system.spells;if(!Object.keys(spells).length)expected['/system/spells']={present:true,value:{}};for(const [key,claim]of Object.entries(spells)){const path='/system/spells/'+esc(key);pick(path);references.push({path,claim});}
return JSON.stringify({uuid:doc.uuid,expected,references,revision:await digest(s),description_sha256:await digest(s.system.description.value)}).match(/[\\s\\S]{1,800}/g);
""".replace('DEITY_UUID',json.dumps(selector['uuid']))
            sample=probe(payload(await client.call_tool('execute_javascript',{'code':deity_probe})))
            rows=[];deity_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['source','description','effective'],limit=100)
                if deity_cursor:args['cursor']=deity_cursor
                page=payload(await client.call_tool('read_item',args))
                assert page['identity']['uuid']==sample['uuid'] and page['identity']['type']=='deity'
                assert page['sections'][2]['status']=='unsupported'
                rows.extend(page['records']);deity_cursor=page['pagination']['next_cursor']
                if not deity_cursor:break
            assert deity_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['key'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():
                row=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']==path)
                assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                assert row['provenance']['mapping']=='pf2e.deity.source.v1'
            assert not any(r['raw'][0]['path'].startswith('/system/traits/value') for r in rows)
            prose=[r for r in rows if r['section']=='description' and r['raw'][0]['path']=='/system/description/value']
            text=''.join(r['raw'][0]['value'] for r in sorted(prose,key=lambda r:r.get('text',{}).get('start',0)))
            assert hashlib.sha256(json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==sample['description_sha256']
            links=[];deity_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['relationships'],limit=100)
                if deity_cursor:args['cursor']=deity_cursor
                page=payload(await client.call_tool('read_item',args));links.extend(page['records']);deity_cursor=page['pagination']['next_cursor']
                if not deity_cursor:break
            assert deity_cursor is None and len(links)==len(sample['references'])
            by_path={r['raw'][0]['path']:r for r in links}
            for expected in sample['references']:
                row=by_path[expected['path']]
                assert row['raw'][0]['value']==expected['claim'] and row['mapped']['value']['target_uuid']==expected['claim']
                assert row['mapped']['value']['status']=='resolved' and 'acquired' not in row['mapped']['value']
                deity_reference_count+=1
            first=links[0]['mapped']['value']
            follow=payload(await client.call_tool('read_item',dict(item_uuid=first['target_uuid'],sections=['identity'],limit=1)))
            assert follow['identity']['uuid']==first['target_uuid'] and follow['identity']['type']=='spell'
            check="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':check})))['revision']==sample['revision']
        class_selectors_probe="""
const pack=game.packs.get('pf2e.classes'),index=await pack.getIndex({fields:['type']});return JSON.stringify(['Fighter','Rogue','Wizard'].map(name=>{const row=[...index].find(r=>r.type==='class'&&r.name===name);if(!row)throw Error('Missing existing class fixture');return {uuid:pack.getUuid(row._id)};})).match(/[\\s\\S]{1,800}/g);
"""
        class_samples=probe(payload(await client.call_tool('execute_javascript',{'code':class_selectors_probe})))
        assert len(class_samples)==3
        class_reference_count=0
        for selector in class_samples:
            class_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const doc=await foundry.utils.fromUuid(CLASS_UUID),s=doc.toObject(true),expected={},references=[];
const esc=s=>s.replaceAll('~','~0').replaceAll('/','~1');
const pick=path=>{let value=s,present=true;for(const k of path.slice(1).split('/').map(k=>k.replaceAll('~1','/').replaceAll('~0','~'))){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}if(value===undefined)present=false;expected[path]={present,...(present?{value}:{})};};
const array=path=>{pick(path);const selected=expected[path];if(selected.present&&Array.isArray(selected.value)&&selected.value.length){delete expected[path];selected.value.forEach((value,i)=>expected[path+'/'+i]={present:true,value});}};
for(const path of ['keyAbility/selected','hp','perception','spellcasting','trainedSkills/additional','attacks/other/name','traits/rarity'])pick('/system/'+path);
for(const group of [['savingThrows',['fortitude','reflex','will']],['attacks',['simple','martial','advanced','unarmed']],['defenses',['unarmored','light','medium','heavy']]])for(const key of group[1])pick('/system/'+group[0]+'/'+key);pick('/system/attacks/other/rank');
for(const path of ['keyAbility/value','trainedSkills/value','traits/otherTags','ancestryFeatLevels/value','classFeatLevels/value','generalFeatLevels/value','skillFeatLevels/value','skillIncreaseLevels/value'])array('/system/'+path);
const features=s.system.items;if(!Object.keys(features).length)expected['/system/items']={present:true,value:{}};for(const [key,entry]of Object.entries(features)){const path='/system/items/'+esc(key);for(const leaf of ['uuid','name','level'])pick(path+'/'+leaf);references.push({path:path+'/uuid',claim:entry.uuid});}
return JSON.stringify({uuid:doc.uuid,expected,references,revision:await digest(s),description_sha256:await digest(s.system.description.value)}).match(/[\\s\\S]{1,800}/g);
""".replace('CLASS_UUID',json.dumps(selector['uuid']))
            sample=probe(payload(await client.call_tool('execute_javascript',{'code':class_probe})))
            rows=[];class_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['source','description','effective'],limit=100)
                if class_cursor:args['cursor']=class_cursor
                page=payload(await client.call_tool('read_item',args))
                assert page['identity']['uuid']==sample['uuid'] and page['identity']['type']=='class'
                assert page['sections'][2]['status']=='unsupported'
                rows.extend(page['records']);class_cursor=page['pagination']['next_cursor']
                if not class_cursor:break
            assert class_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['key'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():
                row=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']==path)
                assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                assert row['provenance']['mapping']=='pf2e.class.source.v1'
                if row['mapped']['concept'].startswith('class_starting_') and expected['present']:
                    rank=expected['value'];assert row['mapped']['value']==dict(rank=rank,label=['Untrained','Trained','Expert','Master','Legendary'][rank])
            assert not any(r['raw'][0]['path'].startswith('/system/traits/value') for r in rows)
            prose=[r for r in rows if r['section']=='description' and r['raw'][0]['path']=='/system/description/value']
            text=''.join(r['raw'][0]['value'] for r in sorted(prose,key=lambda r:r.get('text',{}).get('start',0)))
            assert hashlib.sha256(json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==sample['description_sha256']
            links=[];class_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['relationships'],limit=100)
                if class_cursor:args['cursor']=class_cursor
                page=payload(await client.call_tool('read_item',args));links.extend(page['records']);class_cursor=page['pagination']['next_cursor']
                if not class_cursor:break
            assert class_cursor is None and len(links)==len(sample['references'])
            by_path={r['raw'][0]['path']:r for r in links}
            for expected in sample['references']:
                row=by_path[expected['path']]
                assert row['raw'][0]['value']==expected['claim'] and row['mapped']['value']['target_uuid']==expected['claim']
                assert row['mapped']['value']['status']=='resolved' and 'acquired' not in row['mapped']['value']
                class_reference_count+=1
            first=links[0]['mapped']['value']
            follow=payload(await client.call_tool('read_item',dict(item_uuid=first['target_uuid'],sections=['identity'],limit=1)))
            assert follow['identity']['uuid']==first['target_uuid']
            check="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':check})))['revision']==sample['revision']
        heritage_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.heritages'),index=await pack.getIndex({fields:['type']});const samples=[];
for(const name of ['Arctic Elf','Nephilim','Changeling']){
 const row=[...index].find(r=>r.type==='heritage'&&r.name===name);if(!row)throw Error('Missing existing heritage fixture');const doc=await pack.getDocument(row._id),s=doc.toObject(true),expected={};
 const pick=path=>{let value=s,present=true;for(const k of path.slice(1).split('/')){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}expected[path]={present,...(present?{value}:{})};};
 const array=path=>{pick(path);const selected=expected[path];if(selected.present&&Array.isArray(selected.value)&&selected.value.length){delete expected[path];selected.value.forEach((value,i)=>expected[path+'/'+i]={present:true,value});}};
 if(s.system.ancestry===null||!Object.hasOwn(s.system,'ancestry'))pick('/system/ancestry');else for(const leaf of ['name','slug','uuid'])pick('/system/ancestry/'+leaf);
 for(const path of ['traits/value','traits/otherTags'])array('/system/'+path);pick('/system/traits/rarity');
 samples.push({uuid:doc.uuid,expected,ancestry_uuid:s.system.ancestry?.uuid??null,revision:await digest(s),description_sha256:await digest(s.system.description.value)});
}
return JSON.stringify(samples).match(/[\\s\\S]{1,800}/g);
"""
        heritage_samples=probe(payload(await client.call_tool('execute_javascript',{'code':heritage_probe})))
        assert len(heritage_samples)==3
        heritage_reference_count=0
        for sample in heritage_samples:
            rows=[];heritage_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['source','description','effective'],limit=100)
                if heritage_cursor:args['cursor']=heritage_cursor
                page=payload(await client.call_tool('read_item',args))
                assert page['identity']['uuid']==sample['uuid'] and page['identity']['type']=='heritage'
                assert page['sections'][2]['status']=='unsupported'
                rows.extend(page['records']);heritage_cursor=page['pagination']['next_cursor']
                if not heritage_cursor:break
            assert heritage_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['key'] for r in rows})==len(rows)
            assert not any('pending their stories' in value for value in page['limitations'])
            for path,expected in sample['expected'].items():
                row=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']==path)
                assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                assert row['provenance']['mapping']=='pf2e.heritage.source.v1'
            prose=[r for r in rows if r['section']=='description' and r['raw'][0]['path']=='/system/description/value']
            text=''.join(r['raw'][0]['value'] for r in sorted(prose,key=lambda r:r.get('text',{}).get('start',0)))
            assert hashlib.sha256(json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==sample['description_sha256']
            links=payload(await client.call_tool('read_item',dict(item_uuid=sample['uuid'],sections=['relationships'],limit=100)))
            assert links['pagination']['complete'] and len(links['records'])==1
            value=links['records'][0]['mapped']['value']
            if sample['ancestry_uuid']:
                assert value['status']=='resolved' and value['target_uuid']==sample['ancestry_uuid'] and value['type']=='ancestry'
                assert 'owner_has_ancestry' not in value
                follow=payload(await client.call_tool('read_item',dict(item_uuid=value['target_uuid'],sections=['identity'],limit=1)))
                assert follow['identity']['uuid']==sample['ancestry_uuid']
                heritage_reference_count+=1
            else:assert value==dict(status='unassociated',target_uuid=None)
            check="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':check})))['revision']==sample['revision']
        background_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.backgrounds'),index=await pack.getIndex({fields:['type']});const samples=[];
const esc=s=>s.replaceAll('~','~0').replaceAll('/','~1');
for(const name of ['Acolyte','Animal Whisperer','Amnesiac']){
 const row=[...index].find(r=>r.type==='background'&&r.name===name);if(!row)throw Error('Missing existing background fixture');const doc=await pack.getDocument(row._id),s=doc.toObject(true),expected={},references=[];
 const pick=path=>{let value=s,present=true;for(const k of path.slice(1).split('/').map(k=>k.replaceAll('~1','/').replaceAll('~0','~'))){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}expected[path]={present,...(present?{value}:{})};};
 const array=path=>{pick(path);const selected=expected[path];if(selected.present&&Array.isArray(selected.value)&&selected.value.length){delete expected[path];selected.value.forEach((value,i)=>expected[path+'/'+i]={present:true,value});}};
 for(const path of ['trainedSkills/value','trainedSkills/lore','traits/value','traits/otherTags'])array('/system/'+path);pick('/system/traits/rarity');
 const boosts=s.system.boosts;if(!Object.keys(boosts).length)expected['/system/boosts']={present:true,value:{}};for(const key of Object.keys(boosts)){const path='/system/boosts/'+esc(key);array(path+'/value');pick(path+'/selected');}
 const features=s.system.items;if(!Object.keys(features).length)expected['/system/items']={present:true,value:{}};for(const [key,entry]of Object.entries(features)){const path='/system/items/'+esc(key);for(const leaf of ['uuid','img','name','level'])pick(path+'/'+leaf);references.push({path:path+'/uuid',claim:entry.uuid});}
 samples.push({uuid:doc.uuid,expected,references,revision:await digest(s),description_sha256:await digest(s.system.description.value)});
}
return JSON.stringify(samples).match(/[\\s\\S]{1,800}/g);
"""
        background_samples=probe(payload(await client.call_tool('execute_javascript',{'code':background_probe})))
        assert len(background_samples)==3
        background_reference_count=0
        for sample in background_samples:
            rows=[];background_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['source','description','effective'],limit=100)
                if background_cursor:args['cursor']=background_cursor
                page=payload(await client.call_tool('read_item',args))
                assert page['identity']['uuid']==sample['uuid'] and page['identity']['type']=='background'
                assert page['sections'][2]['status']=='unsupported'
                rows.extend(page['records']);background_cursor=page['pagination']['next_cursor']
                if not background_cursor:break
            assert background_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['key'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():
                row=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']==path)
                assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                assert row['provenance']['mapping']=='pf2e.background.source.v1'
            prose=[r for r in rows if r['section']=='description' and r['raw'][0]['path']=='/system/description/value']
            text=''.join(r['raw'][0]['value'] for r in sorted(prose,key=lambda r:r.get('text',{}).get('start',0)))
            assert hashlib.sha256(json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==sample['description_sha256']
            links=[];background_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['relationships'],limit=100)
                if background_cursor:args['cursor']=background_cursor
                page=payload(await client.call_tool('read_item',args));links.extend(page['records']);background_cursor=page['pagination']['next_cursor']
                if not background_cursor:break
            assert background_cursor is None
            by_path={r['raw'][0]['path']:r for r in links}
            if sample['references']:
                assert len(links)==len(sample['references'])
                for expected in sample['references']:
                    row=by_path[expected['path']]
                    assert row['raw'][0]['value']==expected['claim'] and row['mapped']['value']['target_uuid']==expected['claim']
                    assert row['mapped']['value']['status']=='resolved' and row['mapped']['value']['type']=='feat'
                    assert 'acquired' not in row['mapped']['value']
                    follow=payload(await client.call_tool('read_item',dict(item_uuid=row['mapped']['value']['target_uuid'],sections=['identity'],limit=1)))
                    assert follow['identity']['uuid']==expected['claim']
                    background_reference_count+=1
            else:assert len(links)==1 and links[0]['mapped']['value']==dict(status='empty',target_uuid=None)
            check="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':check})))['revision']==sample['revision']
        ancestry_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.ancestries'),index=await pack.getIndex({fields:['type']});const samples=[];
const esc=s=>s.replaceAll('~','~0').replaceAll('/','~1');
for(const name of ['Dwarf','Human','Leshy']){
 const row=[...index].find(r=>r.type==='ancestry'&&r.name===name);if(!row)throw Error('Missing existing ancestry fixture');const doc=await pack.getDocument(row._id),s=doc.toObject(true),expected={},references=[];
 const pick=path=>{let value=s,present=true;for(const k of path.slice(1).split('/').map(k=>k.replaceAll('~1','/').replaceAll('~0','~'))){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}expected[path]={present,...(present?{value}:{})};};
 const array=path=>{pick(path);const selected=expected[path];if(selected.present&&Array.isArray(selected.value)&&selected.value.length){delete expected[path];selected.value.forEach((value,i)=>expected[path+'/'+i]={present:true,value});}};
 for(const path of ['hp','size','speed','hands','reach','vision','languages/custom','additionalLanguages/count','additionalLanguages/custom','voluntary/legacy','voluntary/boost','traits/rarity'])pick('/system/'+path);
 for(const path of ['alternateAncestryBoosts','voluntary/flaws','languages/value','additionalLanguages/value','traits/value','traits/otherTags'])array('/system/'+path);
 for(const type of ['boosts','flaws']){const map=s.system[type];if(!Object.keys(map).length)expected['/system/'+type]={present:true,value:{}};for(const key of Object.keys(map)){const path='/system/'+type+'/'+esc(key);array(path+'/value');pick(path+'/selected');}}
 const features=s.system.items;if(!Object.keys(features).length)expected['/system/items']={present:true,value:{}};for(const [key,entry]of Object.entries(features)){const path='/system/items/'+esc(key);for(const leaf of ['uuid','img','name','level'])pick(path+'/'+leaf);references.push({path:path+'/uuid',claim:entry.uuid});}
 samples.push({uuid:doc.uuid,expected,references,revision:await digest(s),description_sha256:await digest(s.system.description.value)});
}
return JSON.stringify(samples).match(/[\\s\\S]{1,800}/g);
"""
        ancestry_samples=probe(payload(await client.call_tool('execute_javascript',{'code':ancestry_probe})))
        assert len(ancestry_samples)==3
        ancestry_reference_count=0
        for sample in ancestry_samples:
            rows=[];ancestry_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['source','description','effective'],limit=100)
                if ancestry_cursor:args['cursor']=ancestry_cursor
                page=payload(await client.call_tool('read_item',args))
                assert page['identity']['uuid']==sample['uuid'] and page['identity']['type']=='ancestry'
                assert page['sections'][2]['status']=='unsupported'
                rows.extend(page['records']);ancestry_cursor=page['pagination']['next_cursor']
                if not ancestry_cursor:break
            assert ancestry_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['key'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():
                row=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']==path)
                assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                assert row['provenance']['mapping']=='pf2e.ancestry.source.v1'
            prose=[r for r in rows if r['section']=='description' and r['raw'][0]['path']=='/system/description/value']
            text=''.join(r['raw'][0]['value'] for r in sorted(prose,key=lambda r:r.get('text',{}).get('start',0)))
            assert hashlib.sha256(json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==sample['description_sha256']
            links=[];ancestry_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['relationships'],limit=100)
                if ancestry_cursor:args['cursor']=ancestry_cursor
                page=payload(await client.call_tool('read_item',args));links.extend(page['records']);ancestry_cursor=page['pagination']['next_cursor']
                if not ancestry_cursor:break
            assert ancestry_cursor is None
            by_path={r['raw'][0]['path']:r for r in links}
            if sample['references']:
                assert len(links)==len(sample['references'])
                for expected in sample['references']:
                    row=by_path[expected['path']]
                    assert row['raw'][0]['value']==expected['claim'] and row['mapped']['value']['target_uuid']==expected['claim']
                    assert row['mapped']['value']['status']=='resolved' and row['mapped']['value']['type']=='feat'
                    assert 'acquired' not in row['mapped']['value']
                    follow=payload(await client.call_tool('read_item',dict(item_uuid=row['mapped']['value']['target_uuid'],sections=['identity'],limit=1)))
                    assert follow['identity']['uuid']==expected['claim']
                    ancestry_reference_count+=1
            else:assert len(links)==1 and links[0]['mapped']['value']==dict(status='empty',target_uuid=None)
            check="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':check})))['revision']==sample['revision']
        kit_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const pack=game.packs.get('pf2e.equipment-srd'),index=await pack.getIndex({fields:['type']});
const samples=[];const esc=s=>s.replaceAll('~','~0').replaceAll('/','~1');
for(const row of [...index].filter(r=>r.type==='kit').slice(0,2)){
 const doc=await pack.getDocument(row._id),s=doc.toObject(true),expected={},references=[];
 const visit=(map,path)=>{if(map===null||Object.keys(map).length===0){expected[path]={present:true,value:map};return;}for(const [key,entry]of Object.entries(map)){const p=path+'/'+esc(key);for(const leaf of ['uuid','img','quantity','name','isContainer']){const present=Object.hasOwn(entry,leaf);expected[p+'/'+leaf]={present,...(present?{value:entry[leaf]}:{})};}references.push({path:p+'/uuid',claim:entry.uuid});if(Object.hasOwn(entry,'items'))visit(entry.items,p+'/items');else expected[p+'/items']={present:false};}};
 visit(s.system.items,'/system/items');for(const path of ['/system/price/per','/system/price/value/gp','/system/price/value/sp','/system/price/sizeSensitive']){let value=s,present=true;for(const k of path.slice(1).split('/')){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}if(value===undefined)present=false;expected[path]={present,...(present?{value}:{})};}
 const text=s.system.description.value,description_sha256=await digest(text);samples.push({uuid:doc.uuid,expected,references,revision:await digest(s),description_sha256});
}
return JSON.stringify(samples).match(/[\\s\\S]{1,800}/g);
"""
        kit_samples=probe(payload(await client.call_tool('execute_javascript',{'code':kit_probe})))
        assert len(kit_samples)==2
        kit_reference_count=0
        for sample in kit_samples:
            rows=[];kit_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['source','description','effective'],limit=100)
                if kit_cursor:args['cursor']=kit_cursor
                page=payload(await client.call_tool('read_item',args))
                assert page['identity']['uuid']==sample['uuid'] and page['identity']['type']=='kit'
                assert page['sections'][2]['status']=='unsupported'
                rows.extend(page['records']);kit_cursor=page['pagination']['next_cursor']
                if not kit_cursor:break
            assert kit_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['key'] for r in rows})==len(rows)
            for path,expected in sample['expected'].items():
                row=next(r for r in rows if r['section']=='source' and r['raw'][0]['path']==path)
                assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                assert row['provenance']['mapping']=='pf2e.kit.source.v1'
            assert not any(r['raw'][0]['path'] in ('/system/quantity','/system/equipped/invested') for r in rows)
            prose=[r for r in rows if r['section']=='description' and r['raw'][0]['path']=='/system/description/value']
            text=''.join(r['raw'][0]['value'] for r in sorted(prose,key=lambda r:r.get('text',{}).get('start',0)))
            # digest() hashes canonical JSON, including string quoting.
            assert hashlib.sha256(json.dumps(text,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==sample['description_sha256']
            links=[];kit_cursor=None
            for _ in range(100):
                args=dict(item_uuid=sample['uuid'],sections=['relationships'],limit=100)
                if kit_cursor:args['cursor']=kit_cursor
                page=payload(await client.call_tool('read_item',args));links.extend(page['records']);kit_cursor=page['pagination']['next_cursor']
                if not kit_cursor:break
            assert kit_cursor is None and len(links)==len(sample['references'])
            by_path={r['raw'][0]['path']:r for r in links}
            for expected in sample['references']:
                row=by_path[expected['path']]
                assert row['raw'][0]['value']==expected['claim'] and row['mapped']['value']['target_uuid']==expected['claim']
                assert row['mapped']['value']['status']=='resolved'
                kit_reference_count+=1
            first=links[0]['mapped']['value']
            follow=payload(await client.call_tool('read_item',dict(item_uuid=first['target_uuid'],sections=['identity'],limit=1)))
            assert follow['identity']['uuid']==first['target_uuid']
            check="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':check})))['revision']==sample['revision']
        inventory_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const types=['weapon','armor','shield','equipment','consumable','ammo','backpack','book','treasure'];
const actors=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type));
const selected=new Map();for(const type of types){const actor=actors.find(a=>a.items.some(i=>i.type===type));if(actor)selected.set(actor.uuid,{actor,selector:{actor_uuid:actor.uuid}});}
const token=game.scenes.contents.flatMap(s=>s.tokens.contents).find(t=>['character','npc','familiar'].includes(t.actor?.type)&&t.actor.items.some(i=>types.includes(i.type)));if(token)selected.set(token.uuid,{actor:token.actor,selector:{token_uuid:token.uuid}});
const report=[];for(const {actor,selector}of selected.values()){const possessions=actor.items.filter(i=>types.includes(i.type)).map(item=>{const s=item.toObject(true),expected={};for(const path of ['/system/quantity','/system/price/per','/system/price/value/gp','/system/containerId','/system/equipped/carryType']){let value=s,present=true;for(const k of path.slice(1).split('/')){if(value===null||typeof value!=='object'||!Object.hasOwn(value,k)){present=false;break;}value=value[k];}expected[path]={present,...(present?{value}:{})};}return {uuid:item.uuid,type:item.type,name:s.name,expected};});report.push({selector,uuid:actor.uuid,possessions,revision:await digest(actor.toObject(true))});}
return JSON.stringify(report).match(/[\\s\\S]{1,800}/g);
"""
        inventory_samples=probe(payload(await client.call_tool('execute_javascript',{'code':inventory_probe})))
        assert len(inventory_samples)>=2
        inventory_types=set()
        for sample in inventory_samples:
            rows=[];inventory_cursor=None
            for _ in range(200):
                args=dict(sample['selector'],sections=['inventory','effective'],limit=100)
                if inventory_cursor:args['cursor']=inventory_cursor
                page=payload(await client.call_tool('read_actor',args))
                assert page['identity']['uuid']==sample['uuid'] and page['sections'][1]['status']=='unsupported'
                rows.extend(page['records']);inventory_cursor=page['pagination']['next_cursor']
                if not inventory_cursor:break
            assert inventory_cursor is None and page['sections'][0]['status']=='complete'
            assert len({r['key'] for r in rows})==len(rows)
            references={r['mapped']['value']['target_uuid']:r for r in rows if r['mapped']['concept']=='inventory_item'}
            assert set(references)=={i['uuid'] for i in sample['possessions']}
            for item in sample['possessions']:
                inventory_types.add(item['type'])
                ref=references[item['uuid']]['mapped']['value']
                assert ref['name']==item['name'][:256] and ref['type']==item['type']
                if 'token_uuid' in sample['selector']:assert ref['token_uuid']==sample['selector']['token_uuid']
                for path,expected in item['expected'].items():
                    row=next(r for r in rows if r['key']=='inventory:source:'+item['type']+':'+item['uuid']+':'+path)
                    assert {k:v for k,v in row['raw'][0].items() if k in ('present','value')}==expected
                edge=next(r for r in rows if r['key']=='inventory:container:'+item['uuid'])
                assert edge['mapped']['value']==dict(status='missing',target_uuid=None,cycle=False)
            for row in rows:
                if row['mapped']['concept']=='inventory_selected_ammunition':assert row['mapped']['value']==dict(status='missing',target_uuid=None)
            if sample['possessions']:
                follow_args=dict(item_uuid=sample['possessions'][0]['uuid'],sections=['identity'],limit=1)
                if 'token_uuid' in sample['selector']:follow_args['token_uuid']=sample['selector']['token_uuid']
                follow=payload(await client.call_tool('read_item',follow_args))
                assert follow['identity']['uuid']==sample['possessions'][0]['uuid']
                assert follow['identity']['actor']['uuid']==sample['uuid']
            args=dict(sample['selector'],sections=['identity'],limit=1)
            assert payload(await client.call_tool('read_actor',args))['identity']['uuid']==sample['uuid']
            check="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const a=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(a.toObject(true))});"
            after=probe(payload(await client.call_tool('execute_javascript',{'code':check})))
            assert after['revision']==sample['revision']
        assert inventory_types>={'weapon','armor','equipment','consumable','ammo','treasure'}
        actor_casting_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const actors=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type));
const selected=[...new Map(['prepared','spontaneous','innate','focus'].map(mode=>actors.find(a=>a.items.some(i=>i.type==='spellcastingEntry'&&i.toObject(true).system.prepared.value===mode))).filter(Boolean).map(a=>[a.uuid,{actor:a,selector:{actor_uuid:a.uuid}}])).values()];
const token=game.scenes.contents.flatMap(s=>s.tokens.contents).find(t=>['character','npc','familiar'].includes(t.actor?.type)&&t.actor.items.some(i=>i.type==='spellcastingEntry'));
if(token)selected.push({actor:token.actor,selector:{token_uuid:token.uuid}});
const report=[];for(const {actor,selector}of selected){const spells=actor.items.filter(i=>i.type==='spell'),entries=actor.items.filter(i=>i.type==='spellcastingEntry');const assignments=spells.map(i=>{const id=i.toObject(true).system.location.value;const target=actor.items.get(id);return {uuid:i.uuid,target_uuid:target?.type==='spellcastingEntry'?target.uuid:null};});let preparations=0;for(const entry of entries)for(const slot of Object.values(entry.toObject(true).system.slots))if(Array.isArray(slot.prepared))preparations+=slot.prepared.filter(p=>p&&typeof p==='object'&&!Array.isArray(p)).length;const source=actor.toObject(true);report.push({selector,uuid:actor.uuid,spell_uuids:spells.map(i=>i.uuid),entry_uuids:entries.map(i=>i.uuid),assignments,preparations,focus:source.system.resources?.focus??null,revision:await digest(source)});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        actor_casting_samples=probe(payload(await client.call_tool('execute_javascript',{'code':actor_casting_probe})))
        assert len(actor_casting_samples)>=3
        for sample in actor_casting_samples:
            rows=[];actor_casting_cursor=None
            for _ in range(200):
                args=dict(sample['selector'],sections=['spellcasting','effective'],limit=100)
                if actor_casting_cursor:args['cursor']=actor_casting_cursor
                page=payload(await client.call_tool('read_actor',args));rows.extend(page['records'])
                assert page['sections'][0]['status']=='partial' and 'availability_not_evaluated' in page['sections'][0]['reasons']
                assert page['sections'][1]['status']=='unsupported'
                actor_casting_cursor=page['pagination']['next_cursor']
                if not actor_casting_cursor:break
            assert actor_casting_cursor is None and len({row['key'] for row in rows})==len(rows)
            for concept,expected in [('casting_entry',sample['entry_uuids']),('casting_spell',sample['spell_uuids'])]:
                references=[row['mapped']['value'] for row in rows if row['mapped']['concept']==concept]
                assert {v['target_uuid'] for v in references}==set(expected)
                if sample['selector'].get('token_uuid'):assert all(v['token_uuid']==sample['selector']['token_uuid'] for v in references)
                if references:
                    reference=references[0];follow_args={'item_uuid':reference['target_uuid'],'sections':['identity']}
                    if reference.get('token_uuid'):follow_args['token_uuid']=reference['token_uuid']
                    assert payload(await client.call_tool('read_item',follow_args))['identity']['uuid']==reference['target_uuid']
            assignment_rows={r['raw'][0]['document_uuid']:r['mapped']['value'] for r in rows if r['mapped']['concept']=='casting_spell_assignment'}
            for expected in sample['assignments']:
                actual=assignment_rows[expected['uuid']];assert actual['target_uuid']==expected['target_uuid']
                assert actual['status']==('resolved' if expected['target_uuid'] else 'missing')
            assert len([r for r in rows if r['mapped']['concept']=='casting_preparation'])==sample['preparations']
            for key in ('value','max'):
                raw=next(r for r in rows if r['key']=='spellcasting:focus:'+key)['raw'][0]
                assert raw['present']==(sample['focus'] is not None and key in sample['focus'])
                if raw['present']:assert raw['value']==sample['focus'][key]
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
        casting_probe="""
const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');
const entries=game.actors.contents.filter(a=>['character','npc','familiar'].includes(a.type)).flatMap(a=>a.items.contents).filter(i=>i.type==='spellcastingEntry');
const samples=['prepared','spontaneous','innate','focus'].map(mode=>({doc:entries.find(i=>i.toObject(true).system.prepared.value===mode)}));
const token=game.scenes.contents.flatMap(s=>s.tokens.contents).find(t=>['character','npc','familiar'].includes(t.actor?.type)&&t.actor.items.some(i=>i.type==='spellcastingEntry'));
if(token)samples.push({doc:token.actor.items.find(i=>i.type==='spellcastingEntry'),token_uuid:token.uuid});
const report=[];for(const {doc,token_uuid}of samples){if(!doc)continue;const source=doc.toObject(true),s=source.system,expected={'/system/prepared/value':s.prepared.value,'/system/tradition/value':s.tradition.value,'/system/spelldc/value':s.spelldc.value,'/system/spelldc/dc':s.spelldc.dc};const absent=[];for(let rank=0;rank<=11;rank++){const slot=s.slots['slot'+rank];if(!slot)continue;const path='/system/slots/slot'+rank;expected[path+'/value']=slot.value;expected[path+'/max']=slot.max;for(let i=0;i<slot.prepared.length;i++)for(const key of ['id','expended']){const p=path+'/prepared/'+i+'/'+key;if(Object.hasOwn(slot.prepared[i],key))expected[p]=slot.prepared[i][key];else absent.push(p);}}report.push({uuid:doc.uuid,...(token_uuid?{token_uuid}:{}),expected,absent,revision:await digest(source)});}
const json=JSON.stringify(report);return Array.from({length:Math.ceil(json.length/800)},(_,i)=>json.slice(i*800,(i+1)*800));
"""
        casting_samples=probe(payload(await client.call_tool('execute_javascript',{'code':casting_probe})))
        assert len(casting_samples)==5
        assert {s['expected']['/system/prepared/value'] for s in casting_samples}>={'prepared','spontaneous','innate','focus'}
        for sample in casting_samples:
            rows=[];casting_cursor=None
            for _ in range(100):
                args={'item_uuid':sample['uuid'],'sections':['source','effective'],'limit':25}
                if sample.get('token_uuid'):args['token_uuid']=sample['token_uuid']
                if casting_cursor:args['cursor']=casting_cursor
                page=payload(await client.call_tool('read_item',args));rows.extend(page['records'])
                assert page['sections'][1]['status']=='unsupported'
                casting_cursor=page['pagination']['next_cursor']
                if not casting_cursor:break
            assert casting_cursor is None and page['sections'][0]['status']=='complete'
            assert len({row['raw'][0]['path'] for row in rows})==len(rows)
            for path,expected in sample['expected'].items():
                row=next(row for row in rows if row['raw'][0]['path']==path)
                assert row['raw'][0]['value']==expected and row['provenance']['mapping']=='pf2e.spellcasting-entry.source.v1'
            for path in sample['absent']:assert next(row for row in rows if row['raw'][0]['path']==path)['raw'][0]['present'] is False
            if sample.get('token_uuid'):assert page['identity']['instance']['token_uuid']==sample['token_uuid']
            fingerprint_code="const {digest}=await import('/modules/foundry-mcp/scripts/actorReadUtils.js');const doc=await foundry.utils.fromUuid("+json.dumps(sample['uuid'])+");return JSON.stringify({revision:await digest(doc.toObject(true))});"
            assert probe(payload(await client.call_tool('execute_javascript',{'code':fingerprint_code})))['revision']==sample['revision']
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
        treasure_support=next(entry for entry in registry.data['item_types'] if entry['type']=='treasure')
        assert treasure_support['mapped_supported'] and not treasure_support['effective_supported']
        assert treasure_support['verification']['live']['status']=='passed'
        container_support=next(entry for entry in registry.data['item_types'] if entry['type']=='backpack')
        assert container_support['mapped_supported'] and not container_support['effective_supported']
        assert container_support['verification']['live']['status']=='passed'
        deity_support=next(entry for entry in registry.data['item_types'] if entry['type']=='deity')
        assert deity_support['mapped_supported'] and not deity_support['effective_supported']
        assert deity_support['verification']['live']['status']=='passed'
        class_support=next(entry for entry in registry.data['item_types'] if entry['type']=='class')
        assert class_support['source_supported'] and class_support['mapped_supported'] and not class_support['effective_supported']
        assert class_support['verification']['live']['status']=='passed'
        heritage_support=next(entry for entry in registry.data['item_types'] if entry['type']=='heritage')
        assert heritage_support['source_supported'] and heritage_support['mapped_supported'] and not heritage_support['effective_supported']
        assert heritage_support['verification']['live']['status']=='passed'
        background_support=next(entry for entry in registry.data['item_types'] if entry['type']=='background')
        assert background_support['source_supported'] and background_support['mapped_supported'] and not background_support['effective_supported']
        assert background_support['verification']['live']['status']=='passed'
        ancestry_support=next(entry for entry in registry.data['item_types'] if entry['type']=='ancestry')
        assert ancestry_support['source_supported'] and ancestry_support['mapped_supported'] and not ancestry_support['effective_supported']
        assert ancestry_support['verification']['live']['status']=='passed'
        kit_support=next(entry for entry in registry.data['item_types'] if entry['type']=='kit')
        assert kit_support['source_supported'] and kit_support['mapped_supported'] and not kit_support['effective_supported']
        assert kit_support['verification']['live']['status']=='passed'
        book_support=next(entry for entry in registry.data['item_types'] if entry['type']=='book')
        assert book_support['source_supported'] and book_support['mapped_supported'] and not book_support['effective_supported']
        assert book_support['verification']['deterministic']['status']=='passed'
        assert book_support['verification']['live']['status']=='passed'
        assert 'book Items expose' in available['read_item'].description
        assert '200' in available['read_item'].description
        inventory_support=next(entry for entry in registry.data['actor_sections'] if entry['name']=='inventory')
        assert inventory_support['source_supported'] and inventory_support['mapped_supported'] and not inventory_support['effective_supported']
        assert inventory_support['verification']['live']['status']=='passed'
        actor_casting_support=next(entry for entry in registry.data['actor_sections'] if entry['name']=='spellcasting')
        assert actor_casting_support['source_supported'] and actor_casting_support['mapped_supported'] and not actor_casting_support['effective_supported']
        assert actor_casting_support['verification']['live']['status']=='passed'
        casting_support=next(entry for entry in registry.data['item_types'] if entry['type']=='spellcastingEntry')
        assert casting_support['mapped_supported'] and not casting_support['effective_supported']
        assert casting_support['verification']['live']['status']=='passed'
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
        print(json.dumps({'passed':True,'discovered':sorted(needed),'source_pages':source_pages,'feat_source_samples_verified':len(feat_samples),'feat_source_pages_verified':feat_source_pages,'feat_source_records_verified':feat_source_records,'deity_source_samples_verified':len(deity_samples),'deity_spell_references_verified':deity_reference_count,'class_source_samples_verified':len(class_samples),'class_feature_references_verified':class_reference_count,'heritage_source_samples_verified':len(heritage_samples),'heritage_ancestry_references_verified':heritage_reference_count,'background_source_samples_verified':len(background_samples),'background_feature_references_verified':background_reference_count,'ancestry_source_samples_verified':len(ancestry_samples),'ancestry_feature_references_verified':ancestry_reference_count,'kit_source_samples_verified':len(kit_samples),'kit_component_references_verified':kit_reference_count,'inventory_actor_samples_verified':len(inventory_samples),'inventory_physical_types_verified':len(inventory_types),'treasure_source_samples_verified':len(treasure_samples),'container_source_samples_verified':len(container_samples),'container_owned_samples_verified':container_owned_samples,'actor_casting_source_samples_verified':len(actor_casting_samples),'casting_entry_source_samples_verified':len(casting_samples),'spell_source_samples_verified':len(spell_samples),'consumable_source_samples_verified':len(consumable_samples),'equipment_source_samples_verified':len(equipment_samples),'shield_pack_samples_verified':len(shield_samples),'armor_source_samples_verified':len(armor_samples),'ammo_source_samples_verified':len(ammo_samples),'weapon_missing_selection_verified':True,'weapon_source_samples_verified':len(weapon_samples),'condition_empty_reference_relationships_verified':True,'condition_source_samples_verified':len(condition_samples)+len(pack_conditions),'effect_source_samples_verified':len(effect_samples)+len(pack_effects),'effect_empty_context_relationships_verified':True,'npc_source_verified':True,'npc_notes_verified':True,'npc_item_references_verified':reference_count,'item_owner_verified':True,'pack_hydration_verified':True,'physical_types_verified':physical_verified,'token_verified':bool(selection.get('token_uuid')),'lore_source_skills_verified':True,'attack_source_contexts_verified':3,'pack_attack_verified':True,'activation_modes_verified':4,'self_effect_followup_verified':True,'familiar_action_pack_verified':True,'runtime':actor.data['runtime']}))
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
        error_locations=[]
        while True:
            r=json.loads(await asyncio.wait_for(ws.recv(),5))
            if r.get('method')=='Runtime.exceptionThrown' or (r.get('method')=='Runtime.consoleAPICalled' and r.get('params',{}).get('type')=='error'):
                console_errors+=1
                details=r.get('params',{}).get('exceptionDetails',r.get('params',{}))
                # Report code locations, never console arguments or exception
                # values, which can contain world content or credentials.
                frames=details.get('stackTrace',{}).get('callFrames',[])[:3]
                if len(error_locations)<8:
                    texts=[argument.get('value',argument.get('description','')) for argument in r.get('params',{}).get('args',[])]
                    window_size=any(isinstance(text,str) and ('resolution' in text.lower() or 'window' in text.lower() and any(word in text.lower() for word in ('small','width','dimensions'))) for text in texts)
                    error_locations.append({'category':'window_size_notification' if window_size else 'unclassified','frames':[{'url':frame.get('url','').split('?',1)[0],'line':frame.get('lineNumber'),'function':frame.get('functionName','')} for frame in frames]})
            if r.get('id')==1:break
        expression="JSON.stringify({ready:!!globalThis.game?.ready,isGM:!!globalThis.game?.user?.isGM,version:globalThis.game?.version,url:location.pathname})"
        await ws.send(json.dumps({'id':2,'method':'Runtime.evaluate','params':{'expression':expression,'returnByValue':True}}))
        while True:
            r=json.loads(await asyncio.wait_for(ws.recv(),5))
            if r.get('id')==2:
                value=json.loads(r.get('result',{}).get('result',{}).get('value','{}'))
                value['console_errors']=console_errors
                if error_locations:value['console_error_locations']=error_locations
                print(json.dumps(value));break

if __name__=='__main__':
    asyncio.run(browser_status(refresh=sys.argv[1:]==['--refresh']) if sys.argv[1:] in (['--browser'],['--refresh']) else main())
