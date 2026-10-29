"""Bounded PF2e-specific v2 character/preparation check in existing localhost test.

Reuses the reviewed exact-marker creation/cleanup state machine. Creates one
character with inert Lore, one casting entry and one spell; never edits existing
documents. Core14.369 public Document.createEmbeddedDocuments and
updateEmbeddedDocuments: https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
PF2e8.6.1 spell location/level and spellcasting-entry slots/prepared source:
https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
Recorded preparations are source configuration, never castability. At most30
calls/180s; prints only aggregate checks, bytes and counts, never credentials.
"""
import asyncio
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('actor-character-current-live-check.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

POPULATE = fixture.SELECTED + """
const state=globalThis.__mcpCharacterCurrentProbes.get(RUN);
const check=()=>{GUARD;if(state.closed||actor.getFlag('foundry-mcp','characterCurrentProbe')!==RUN)throw Error('Fixture closed');};
check();state.pending++;let result;
try{
const [entry]=await actor.createEmbeddedDocuments('Item',[{name:'Selective verification preparation',type:'spellcastingEntry',system:{tradition:{value:'arcane'},prepared:{value:'prepared',flexible:false}}}]);check();
const [spell]=await actor.createEmbeddedDocuments('Item',[{name:'Selective verification spell',type:'spell',system:{level:{value:1},location:{value:entry.id},rules:[]}}]);check();
await actor.updateEmbeddedDocuments('Item',[{_id:entry.id,'system.slots.slot1':{value:2,max:2,prepared:[{id:spell.id,expended:false},{id:spell.id,expended:true}]}}]);check();
result={entry:entry.uuid,spell:spell.uuid,ac:actor.toObject(false).system.attributes.ac.value};
}finally{state.pending--;}
"""


async def verify(client):
    marker='selective-'+str(uuid4());expected=None;calls=0
    report={'passed':False,'cleanup_verified':False,'bytes':[]}
    async def call(name,args):
        nonlocal calls
        calls+=1
        if calls>30:raise AssertionError('Call bound')
        result=await client.call_tool(name,args)
        return fixture.payload(result)
    async def execute(body):
        value=(await call('execute_javascript',{'code':fixture.code(body,marker,expected)}))['value']
        if isinstance(value,dict) and value.get('$type')=='Array':
            assert not value['truncated'];value=''.join(value['values'])
        return json.loads(value)
    try:
        expected=(await execute(fixture.CREATE))['uuid']
        source=await execute(POPULATE)
        before=await execute(fixture.SELECTED+fixture.FINGERPRINT)
        ac=await call('read_actor',{'actor_uuid':expected,'select':{'details':['statistics.armor_class']}})
        assert ac['pagination']['complete'] and len(ac['entries'])==1
        assert next(v['value'] for v in ac['entries'][0]['values'] if v['concept']=='current_armor_class')==source['ac']
        args={'actor_uuid':expected,'select':{'details':['spellcasting.prepared'],'entry_uuids':[source['entry']]},'limit':1}
        pages=[];cursor=None
        for _ in range(5):
            page=await call('read_actor',dict(args,**({'cursor':cursor} if cursor else {})))
            pages.append(page);cursor=page['pagination']['next_cursor']
            if not cursor:break
        assert cursor is None and len(pages)==2
        options=[v for p in pages for e in p['entries'] for v in e['values'] if v['concept']=='casting_contextual_option']
        assert len(options)==2
        assert len({e['key'] for p in pages for e in p['entries']})==2
        assert all(v['value']['context']=='prepared_use' for v in options)
        evidence=await call('read_actor',dict(args,select=dict(args['select'],evidence=True),max_bytes=48000))
        assert all('evidence' in v for e in evidence['entries'] for v in e['values'])
        item=await call('read_item',{'item_uuid':source['entry'],'select':{'details':['source.preparations']},'limit':2})
        assert item['entries']
        after=await execute(fixture.SELECTED+fixture.FINGERPRINT)
        assert before==after
        report.update(passed=True,prepared_positions=len(options),source_unchanged=True,
                      bytes=[len(json.dumps(p,ensure_ascii=False,separators=(',',':')).encode()) for p in [ac,*pages,evidence,item]])
    finally:
        removed=await execute(fixture.CLEANUP)
        report['cleanup_verified']=removed=={'pending':0,'remaining':0}
        report['calls']=calls
        print(json.dumps(report))
    assert report['cleanup_verified']


async def main():
    token=next(line.partition('=')[2].strip() for line in Path('.env.mcp').read_text().splitlines() if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token})
    async with asyncio.timeout(180),Client(transport,timeout=30,init_timeout=10) as client:
        await verify(client)


if __name__=='__main__':asyncio.run(main())
