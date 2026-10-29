"""Opt-in PF2e-specific character current-statistics fixture in existing test.

Creates one marked character and one inert Lore; exact-marker cleanup handles
lost/late creation responses. Public Actor.create/createEmbeddedDocuments/delete,
getFlag and toObject only. No preparation, rolls, imports or existing-document writes.
https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
PF2e8.6.1 character details.languages and Lore proficient.value source contracts:
https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
"""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import re
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS=30
INIT_TIMEOUT_SECONDS=10
SESSION_TIMEOUT_SECONDS=180
GUARD="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS="""
const encoded=JSON.stringify(result);if(new TextEncoder().encode(encoded).length>16000)throw Error('Metadata bound');
return Array.from({length:Math.ceil(encoded.length/800)},(_,i)=>encoded.slice(i*800,(i+1)*800));
"""
CREATE="""
globalThis.__mcpCharacterCurrentProbes??=new Map();const state=globalThis.__mcpCharacterCurrentProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpCharacterCurrentProbes.set(RUN,state);
if(state.closed)throw Error('Probe closed');state.pending++;let actor,result;
const open=async()=>{if(!actor||actor.type!=='character'||typeof actor.uuid!=='string'||actor.getFlag('foundry-mcp','characterCurrentProbe')!==RUN)throw Error('Fixture identity mismatch');if(state.closed){GUARD;await actor.delete();throw Error('Probe closed during creation');}};
try{GUARD;actor=await Actor.implementation.create({name:'MCP temporary character current verification',type:'character',system:{details:{languages:{value:['common'],details:'Current language qualification.'}}},flags:{'foundry-mcp':{characterCurrentProbe:RUN}}});await open();
GUARD;const items=await actor.createEmbeddedDocuments('Item',[{name:'Verification Lore',type:'lore',system:{proficient:{value:1},rules:[]}}]);await open();
if(items.length!==1||actor.items.size!==1||items[0].type!=='lore'||items[0].parent!==actor)throw Error('Unexpected fixture membership');result={uuid:actor.uuid};
}finally{state.pending--;}
"""
CLEANUP="""
globalThis.__mcpCharacterCurrentProbes??=new Map();const state=globalThis.__mcpCharacterCurrentProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpCharacterCurrentProbes.set(RUN,state);state.closed=true;
for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
const matches=game.actors.filter(a=>a.getFlag('foundry-mcp','characterCurrentProbe')===RUN);
if(matches.length>1||matches.some(a=>a.type!=='character'))throw Error('Ambiguous fixture marker');
for(const actor of matches){if((EXPECTED!==null&&actor.uuid!==EXPECTED)||actor.getFlag('foundry-mcp','characterCurrentProbe')!==RUN)throw Error('Cleanup identity mismatch');GUARD;await actor.delete();}
const result={pending:state.pending,remaining:game.actors.filter(a=>a.getFlag('foundry-mcp','characterCurrentProbe')===RUN).length};
"""
SELECTED="""
const actor=game.actors.find(a=>a.uuid===EXPECTED);
if(!actor||actor.type!=='character'||actor.getFlag('foundry-mcp','characterCurrentProbe')!==RUN)throw Error('Fixture identity mismatch');
"""
FINGERPRINT="""
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)))),b=>b.toString(16).padStart(2,'0')).join('');
const result={source:await hash(actor.toObject(true)),current:await hash(actor.toObject(false))};
"""
CHECK=r"""
const serialized=actor.toObject(false),checks=[];
if(claims.length>40)throw Error('Claim bound');
function clean(value,depth=0,budget={nodes:0}){if(depth>10||++budget.nodes>1024)throw Error('Selected value bound');if(value===null||typeof value==='string'||typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value))return value;if(!value||typeof value!=='object')throw Error('Unsupported selected value');const keys=Array.isArray(value)?Array.from({length:value.length},(_,i)=>String(i)):Object.getOwnPropertyNames(value),result=Array.isArray(value)?[]:{};for(const key of keys){const d=Object.getOwnPropertyDescriptor(value,key);if(!d||!Object.hasOwn(d,'value'))throw Error('Accessor prohibited');Object.defineProperty(result,key,{value:clean(d.value,depth+1,budget),enumerable:true,configurable:true,writable:true});}return result;}
for(const claim of claims){let value=serialized,present=true;for(const encoded of claim.path.slice(1).split('/')){const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~');if(!value||typeof value!=='object'){present=false;break;}const d=Object.getOwnPropertyDescriptor(value,key);if(!d){present=false;break;}if(!Object.hasOwn(d,'value'))throw Error('Accessor prohibited');if(d.value===undefined){present=false;break;}value=d.value;}
if(value===Infinity){if(!/^\/system\/perception\/senses\/\d+\/range$/.test(claim.path))throw Error('Nonfinite value');value={'$number':'Infinity'};}
checks.push(claim.document_uuid===actor.uuid&&claim.basis==='transformed'&&claim.present===present&&(!present||JSON.stringify(clean(value))===JSON.stringify(claim.value)));}
const result={checks};
"""


def code(body,run_id,expected=None):
    """PF2e-specific bounded exact-marker fixture code; no free-form selectors."""
    if not isinstance(run_id,str) or re.fullmatch(r'[A-Za-z0-9-]{1,80}',run_id) is None:raise ValueError('Safe marker required')
    return GUARD+body.replace('RUN',json.dumps(run_id)).replace('EXPECTED',json.dumps(expected)).replace('GUARD',GUARD)+CHUNKS


def payload(response):
    return response.structured_content if response.structured_content is not None else json.loads(next(block.text for block in response.content if block.type=='text'))


async def skills_verify(client,world_id,actor_uuid):
    """Reuse the PF2e-specific NPC/character current skill verifier unchanged."""
    spec=importlib.util.spec_from_file_location('character_current_skills',Path(__file__).with_name('actor-skills-live-check.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return await module.verify(client,world_id,actor_uuid)


async def verify(client,world_id,run_id,summary=None):
    """PF2e-specific same-client current skill and selected statistic proof."""
    if world_id!='test':raise ValueError('Explicit existing test world required')
    result=summary if summary is not None else {};result.update(passed=False,cleanup_verified=False)
    expected=None;requested=completed=0;stage='fixture_creation';skills={}

    async def execute(script):
        nonlocal requested,completed
        requested+=1;response=await client.call_tool('execute_javascript',{'code':script});completed+=1
        value=payload(response)['value']
        if isinstance(value,dict) and value.get('$type')=='Array':
            assert value.get('truncated') is False;value=''.join(value['values'])
        return json.loads(value)

    try:
        created=await execute(code(CREATE,run_id));expected=created['uuid']
        before=await execute(code(SELECTED+FINGERPRINT,run_id,expected))
        stage='current_skills';skills=await skills_verify(client,world_id,expected)
        assert skills['passed'] and skills['character_checked'] and set(skills['actor_types'])=={'character','npc'}
        stage='character_statistics';rows=[];cursor=None;seen=set();revision=None
        for pages in range(1,201):
            args=dict(actor_uuid=expected,sections=['statistics'],limit=7,max_bytes=48000)
            if cursor:args['cursor']=cursor
            requested+=1;response=await client.call_tool('read_actor',args);completed+=1;page=payload(response)
            assert page['identity']['uuid']==expected and page['identity']['type']=='character'
            assert len(json.dumps(page,ensure_ascii=False,separators=(',',':')).encode('utf-8'))<=48000
            if revision is None:revision=page['revision']
            assert page['revision']==revision
            section=next(section for section in page['sections'] if section['name']=='statistics')
            assert section['status']=='partial' and 'other_statistics_pending' in section['reasons']
            rows.extend(page['records']);cursor=page['pagination']['next_cursor']
            if not cursor:break
            assert cursor not in seen;seen.add(cursor)
        else:raise AssertionError('Page bound')
        assert len(rows)<=24000 and len({row['key'] for row in rows})==len(rows)
        mappings={'pf2e.actor.current.v1','pf2e.actor.creature-current.v1'}
        for row in rows:
            assert row['provenance']['mapping'] in mappings and len(row['raw'])==1
            raw=row['raw'][0];assert raw['document_uuid']==expected and raw['basis']=='transformed'
            assert row['provenance']['contributors']==[{key:raw[key] for key in ('document_uuid','path','basis')}]
        core=[row for row in rows if row['provenance']['mapping']=='pf2e.actor.current.v1']
        supplement=[row for row in rows if row['provenance']['mapping']=='pf2e.actor.creature-current.v1']
        assert any(row['raw'][0]['present'] and type(row['raw'][0].get('value')) in (int,float) for row in core)
        assert any(row['raw'][0]['path'].startswith('/system/details/languages/value/') and row['raw'][0].get('value')=='common' for row in supplement)
        assert any(row['raw'][0]['present'] and row['raw'][0].get('value')==[] for row in supplement)
        stage='independent_current_witnesses'
        for offset in range(0,len(rows),40):
            claims=[row['raw'][0] for row in rows[offset:offset+40]]
            checked=await execute(code(SELECTED+'const claims='+json.dumps(claims)+';'+CHECK,run_id,expected))
            assert len(checked['checks'])==len(claims) and all(value is True for value in checked['checks'])
        stage='unchanged_read_phase';assert await execute(code(SELECTED+FINGERPRINT,run_id,expected))==before
        result.update(passed=True,statistics_pages=pages,core_records_checked=len(core),supplement_records_checked=len(supplement),fingerprint_unchanged=True,skills=skills)
    except Exception as error:
        result.update(passed=False,failure_stage=stage,exception_type=type(error).__name__)
    finally:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                removed=await asyncio.shield(execute(code(CLEANUP,run_id,expected)))
            assert removed==dict(pending=0,remaining=0);result['cleanup_verified']=True
        except Exception as error:result.update(passed=False,cleanup_exception_type=type(error).__name__)
        result.update(requested_calls=requested+skills.get('requested_calls',0),completed_calls=completed+skills.get('completed_calls',0),mcp_calls=completed+skills.get('completed_calls',0))
    return result


async def main(world_id):
    result=dict(passed=False,cleanup_verified=False)
    try:
        token=next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1]/'.env.mcp').read_text().splitlines() if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
        if not token:raise RuntimeError('Missing local caller credential')
        transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token})
        async with Client(transport,timeout=REQUEST_TIMEOUT_SECONDS,init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):await verify(client,world_id,uuid4().hex,result)
    except Exception as error:result.update(passed=False,exception_type=type(error).__name__)
    print(json.dumps(result));return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--world-id',required=True,choices=['test'])
    raise SystemExit(asyncio.run(main(parser.parse_args().world_id)))
