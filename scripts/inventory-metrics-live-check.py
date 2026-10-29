"""Bounded PF2e-specific wealth/Bulk verification in existing localhost test.

Reuses the reviewed exact-marker party fixture and cleanup (two characters,
one party); adds inert physical Items only to its temporary character. Public
Actor.createEmbeddedDocuments contract: https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
PF2e8.6.1 source quantity/price/bulk and guarded current inventory getters:
https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
Maximum 30 calls/180 seconds plus one reserved cleanup. Aggregate output only.
"""
import asyncio
import importlib.util
import json
from pathlib import Path
from uuid import uuid4
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

spec=importlib.util.spec_from_file_location('party_probe',Path(__file__).with_name('party-live-check.py'))
P=importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

POPULATE=P.SELECTED+"""
const actor=actors.find(a=>a.type==='character');
GUARD;
state.pending++;
try {
 if(state.closed)throw Error('Fixture closed');
 await actor.createEmbeddedDocuments('Item',[
 {name:'Metric gold',type:'treasure',system:{category:'coin',quantity:10,price:{value:{gp:1},per:1},rules:[]}},
 {name:'Metric equipment',type:'equipment',system:{quantity:2,price:{value:{gp:3},per:1},bulk:{value:1},rules:[]}}
 ]);
}finally{state.pending--;}
const result={populated:actor.uuid};
"""
EXPECTED=P.SELECTED+"""
const result=actors.filter(a=>a.type==='character').map(a=>({uuid:a.uuid,
 total_currency:a.inventory.currency.copperValue,total_wealth:a.inventory.totalWealth.copperValue,
 carried_bulk:a.inventory.bulk.value.normal*10+a.inventory.bulk.value.light,
 encumbered_after:a.inventory.bulk.encumberedAfter,maximum_bulk:a.inventory.bulk.max,
 is_encumbered:a.inventory.bulk.isEncumbered,is_over_max:a.inventory.bulk.isOverMax}));
"""


async def verify(client):
    marker=uuid4().hex
    party=None
    calls=0
    report=dict(passed=False,cleanup_verified=False,rows=[])

    async def call(name,args,cleanup=False):
        nonlocal calls
        calls+=1
        assert calls <= (31 if cleanup else 30)
        response=await client.call_tool(name,args)
        return response.structured_content or json.loads(next(c.text for c in response.content if c.type=='text'))

    async def execute(body,cleanup=False):
        response=await call('execute_javascript',{'code':P.code(body,marker,party)},cleanup)
        return json.loads(response['value'])

    try:
        async with asyncio.timeout(180):
            created=await execute(P.CREATE)
            party=created['party']
            populated=(await execute(POPULATE))['populated']
            before=await execute(P.FINGERPRINT)
            expected=await execute(EXPECTED)
            observed=next(v for v in expected if v['uuid']==populated)
            assert observed['total_currency']==1000 and observed['total_wealth']==1600
            roster=await call('get_party_members',{'party_uuid':party})
            assert roster['pagination']['complete'] and len(roster['entries'])==2
            for witness in expected:
                args={'actor_uuid':witness['uuid'],'select':{'details':['wealth','bulk']}}
                page=await call('read_actor',args)
                assert page['pagination']['complete']
                assert not any(text.startswith('Character selected persisted source only:') for text in page['limitations'])
                values={v['concept']:v for e in page['entries'] for v in e['values']}
                assert all(v['availability']=='available' for v in values.values())
                assert all(values[k]['value']==v for k,v in witness.items() if k!='uuid')
                report['rows'].append(dict(scenario='character_summary',bytes=P.size(page),calls=1,complete=True))
            default=await call('read_actor',{'actor_uuid':populated})
            assert not default['entries']
            report['rows'].append(dict(scenario='default_identity',bytes=P.size(default),calls=1,complete=True))
            for scenario,details,evidence,limit in [('summary_evidence',['wealth','bulk'],True,10),('item_details',['wealth.items','bulk.items'],False,10),('complete_pagination',['wealth.items','bulk.items'],False,1)]:
                cursor=None;pages=[];entries=[]
                for _ in range(8):
                    args={'actor_uuid':populated,'select':{'details':details,'evidence':evidence},'limit':limit}
                    if cursor:args['cursor']=cursor
                    page=await call('read_actor',args);pages.append(page);entries.extend(page['entries'])
                    cursor=page['pagination']['next_cursor']
                    if cursor is None:break
                assert cursor is None
                if scenario=='item_details':full=entries
                if scenario=='complete_pagination':assert entries==full
                report['rows'].append(dict(scenario=scenario,bytes=sum(P.size(p) for p in pages),calls=len(pages),complete=True))
            assert await execute(P.FINGERPRINT)==before
            report.update(passed=True,source_unchanged=True,system_getters_match=True)
    except Exception as error:
        report.update(exception_type=type(error).__name__,failed_call=calls)
    finally:
        try:
            async with asyncio.timeout(30):
                cleanup=await execute(P.CLEANUP,True)
                report['cleanup_verified']=cleanup==dict(pending=0,remaining=0)
                report['passed'] &= report['cleanup_verified']
        except Exception as error:report.update(passed=False,cleanup_exception_type=type(error).__name__)
        report['calls']=calls
    return report


async def main():
    root=Path(__file__).resolve().parents[1]
    token=next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines() if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token})
    async with Client(transport,timeout=30,init_timeout=10) as client:
        catalog=await client.list_tools()
        report={'catalog_bytes':P.size([t.model_dump(mode='json') for t in catalog]),'tools':len(catalog),'discovery_calls':1}
        tool=next(t for t in catalog if t.name=='read_actor')
        assert 'wealth.items' in json.dumps(tool.inputSchema) and 'potentially_missing' in json.dumps(tool.outputSchema)
        report.update(await verify(client))
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
