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
        selection=(await client.call_tool('execute_javascript',{'code':"const actor=game.actors.find(a=>a.type==='npc'&&a.items.size);return JSON.stringify({actor_uuid:actor.uuid,token_uuid:game.scenes.contents.flatMap(s=>s.tokens.contents).find(t=>t.actor?.type==='npc')?.uuid});"})).data
        # Development serializer wraps a returned primitive under value.
        if isinstance(selection,dict) and 'value' in selection:selection=json.loads(selection['value'])
        elif isinstance(selection,str):selection=json.loads(selection)
        else:raise ValueError('Unexpected selector probe shape')
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
        registry=await client.call_tool('get_actor_types',{})
        assert registry.data['availability']['supported']
        print(json.dumps({'passed':True,'discovered':sorted(needed),'source_pages':2,'item_owner_verified':True,'pack_hydration_verified':True,'token_verified':bool(selection.get('token_uuid')),'runtime':actor.data['runtime']}))
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
