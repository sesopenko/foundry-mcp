"""Fixed read-only smoke checks against the existing development GM bridge.

Run through scripts/actor-tools.sh live. Requires .env.mcp caller credential
and the authorized development console. Never outputs document IDs or secrets.
"""
import asyncio,json,sys
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
const loreItems=items.filter(i=>i.type==='lore');const loreItem=loreItems.find(i=>i.parent?.type==='npc');
const attacks=items.filter(i=>i.type==='melee');
const meleeSamples=[
 ['explicit_range',attacks.find(i=>i.toObject(true).system.range!==null&&i.toObject(true).system.range!==undefined)],
 ['null_thrown',attacks.find(i=>i.toObject(true).system.range===null&&i.toObject(true).system.traits?.value.some(t=>t.startsWith('thrown-')))],
 ['effect_labels',attacks.find(i=>i.toObject(true).system.attackEffects?.value.length)]
].filter(([,item])=>item);
const fingerprintItems=[...new Map([...actionSamples,effectAction,tokenAction,...meleeSamples.map(([,i])=>i),...loreItems].filter(Boolean).map(i=>[i.uuid,i])).values()];
const report=JSON.stringify({actor_uuid:actor.uuid,token_uuid:token?.uuid,
physical_items:physicalTypes.map(type=>items.find(item=>item.type===type)?.uuid).filter(Boolean),
melee_samples:meleeSamples.map(([context,i])=>({context,uuid:i.uuid})),
lore_item_uuid:loreItem?.uuid,lore_actor_uuid:loreItem?.parent?.uuid,
action_samples:await Promise.all(actionSamples.map(async i=>({uuid:i.uuid,kind:i.toObject(true).system.actionType.value,revision:await digest(i.toObject(true))}))),
self_effect_item_uuid:effectAction?.uuid,token_action_uuid:tokenAction?.uuid,
source_fingerprints:await Promise.all(fingerprintItems.map(async i=>({uuid:i.uuid,revision:await digest(i.toObject(true))})))});
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
        selection=probe(payload(await client.call_tool('execute_javascript',{'code':selector_probe})))
        actor=await client.call_tool('read_actor',{'actor_uuid':selection['actor_uuid'],'limit':1})
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
        next_page=await client.call_tool('read_actor',{'actor_uuid':selection['actor_uuid'],'limit':1,'cursor':actor.data['pagination']['next_cursor']})
        assert next_page.data['pagination']['complete']
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
        attack_support=next(entry for entry in registry.data['item_types'] if entry['type']=='melee')
        assert attack_support['mapped_supported'] and not attack_support['effective_supported']
        assert attack_support['verification']['live']['status']=='passed'
        print(json.dumps({'passed':True,'discovered':sorted(needed),'source_pages':2,'item_owner_verified':True,'pack_hydration_verified':True,'physical_types_verified':physical_verified,'token_verified':bool(selection.get('token_uuid')),'lore_source_skills_verified':True,'attack_source_contexts_verified':3,'pack_attack_verified':True,'activation_modes_verified':4,'self_effect_followup_verified':True,'familiar_action_pack_verified':True,'runtime':actor.data['runtime']}))
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
