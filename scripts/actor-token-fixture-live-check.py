"""Opt-in PF2e-specific token fixture in the existing localhost test world.

Foundry14.369/PF2e8.6.1: one marked NPC/action, one inactive Scene, two
unlinked same-base tokens (HP7/19 and different action source) and a linked
control. No existing document, active Scene, time, combat or settings is changed.
Reader checks reuse actor-token-live-check.py; fixture cleanup is separate.
Public APIs: https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
https://foundryvtt.com/api/v14/classes/foundry.documents.Scene.html
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
TokenData.actorId/actorLink/delta and ActorDeltaData.system are public schema:
https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.TokenData.html
https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorDeltaData.html
PF2e NPC HP and action source, pinned8.6.1:
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

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180
GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS = """
const encoded=JSON.stringify(result);if(new TextEncoder().encode(encoded).length>16000)throw Error('Metadata bound');
return Array.from({length:Math.ceil(encoded.length/800)},(_,i)=>encoded.slice(i*800,(i+1)*800));
"""
LIFECYCLE = """
const activeUuid=()=>[...game.scenes.values()].find(scene=>scene.active)?.uuid??null;
globalThis.__mcpTokenFixtureProbes??=new Map();
const state=globalThis.__mcpTokenFixtureProbes.get(run)??{closed:false,pending:0,actor_uuid:null,scene_uuid:null,active_scene_uuid:Object.hasOwn(expected,'active_scene_uuid')?expected.active_scene_uuid:activeUuid()};
globalThis.__mcpTokenFixtureProbes.set(run,state);
const marker=document=>document.getFlag('foundry-mcp','tokenFixtureProbe');
function roots(){
 const knownActor=expected.actor_uuid??state.actor_uuid,knownScene=expected.scene_uuid??state.scene_uuid;
 if(expected.actor_uuid&&state.actor_uuid&&expected.actor_uuid!==state.actor_uuid||expected.scene_uuid&&state.scene_uuid&&expected.scene_uuid!==state.scene_uuid)throw Error('Known fixture identity mismatch');
 const actor=knownActor?[...game.actors.values()].find(doc=>doc.uuid===knownActor):null,scene=knownScene?[...game.scenes.values()].find(doc=>doc.uuid===knownScene):null;
 if(actor&&(actor.documentName!=='Actor'||actor.type!=='npc'||marker(actor)!==run))throw Error('Known Actor identity mismatch');
 if(scene&&(scene.documentName!=='Scene'||marker(scene)!==run||scene.active!==false))throw Error('Known Scene identity mismatch');
 const actors=game.actors.filter(doc=>marker(doc)===run),scenes=game.scenes.filter(doc=>marker(doc)===run);
 if(actors.length>1||scenes.length>1||actors.some(doc=>doc.documentName!=='Actor'||doc.type!=='npc'||knownActor&&doc.uuid!==knownActor)||scenes.some(doc=>doc.documentName!=='Scene'||doc.active!==false||knownScene&&doc.uuid!==knownScene))throw Error('Ambiguous fixture identity');
 for(const selected of scenes)if(selected.tokens.size>3||[...selected.tokens.values()].some(token=>token.parent!==selected||marker(token)!==run))throw Error('Foreign fixture token');
 return {actors,scenes};
}
async function dropRoots(){
 guard();const selected=roots();
 for(const scene of selected.scenes){guard();await scene.delete();if([...game.scenes.values()].some(doc=>doc.uuid===scene.uuid))throw Error('Scene removal incomplete');}
 for(const actor of selected.actors){guard();await actor.delete();if([...game.actors.values()].some(doc=>doc.uuid===actor.uuid))throw Error('Actor removal incomplete');}
}
async function open(){
 guard();roots();
 if(state.closed){await dropRoots();throw Error('Probe closed during creation');}
 if(activeUuid()!==state.active_scene_uuid)throw Error('Active Scene changed');
}
"""
CREATE = """
if(state.closed||state.pending||state.actor_uuid||state.scene_uuid)throw Error('Probe already started or closed');
state.pending++;let result;
try{
 guard();const actor=await Actor.implementation.create({name:'MCP temporary token verification',type:'npc',system:{attributes:{hp:{value:30,max:30,temp:0}}},flags:{'foundry-mcp':{tokenFixtureProbe:run}}});
 if(!actor)throw Error('Actor creation unavailable');state.actor_uuid=actor.uuid;await open();
 guard();const items=await actor.createEmbeddedDocuments('Item',[{name:'Token fixture base ability',type:'action',system:{actionType:{value:'passive'},actions:{value:null},description:{value:'<p>Token fixture base source.</p>'},rules:[]},flags:{'foundry-mcp':{tokenFixtureProbe:run}}}]);await open();
 if(items.length!==1||actor.items.size!==1||items[0].parent!==actor||actor.items.get(items[0].id)!==items[0])throw Error('Base Item membership mismatch');
 guard();const scene=await Scene.implementation.create({name:'MCP temporary inactive token verification',active:false,navigation:false,width:1000,height:1000,padding:0,flags:{'foundry-mcp':{tokenFixtureProbe:run}}});
 if(!scene)throw Error('Scene creation unavailable');state.scene_uuid=scene.uuid;await open();
 const inputs=[];
 for(let i=0;i<3;i++){
  const prototype=await actor.getTokenDocument({name:'Token fixture '+i,actorLink:i===2,x:100+i*150,y:100},{parent:scene});await open();
  const input=prototype.toObject(true);delete input._id;
  if(input.actorId!==actor.id||input.actorLink!==(i===2))throw Error('Prototype token identity mismatch');
  input.flags={...input.flags,'foundry-mcp':{...input.flags?.['foundry-mcp'],tokenFixtureProbe:run}};
  if(i<2)input.delta={...input.delta,system:{attributes:{hp:{value:i===0?7:19}}}};
  inputs.push(input);
 }
 guard();const tokens=await scene.createEmbeddedDocuments('Token',inputs);await open();
 if(tokens.length!==3||scene.tokens.size!==3)throw Error('Token membership mismatch');
 for(let i=0;i<3;i++){
  const token=tokens[i],owner=token.actor;
  if(token.parent!==scene||scene.tokens.get(token.id)!==token||marker(token)!==run||token.baseActor!==actor||token.isLinked!==(i===2)||!owner)throw Error('Token identity mismatch');
  if(i===2){if(owner!==actor)throw Error('Linked control mismatch');continue;}
  if(owner===actor||owner.uuid===actor.uuid||owner.uuid===tokens[1-i].actor?.uuid)throw Error('Synthetic identity mismatch');
  const item=owner.items.get(items[0].id);
  if(!item||item.type!=='action'||item.parent!==owner||owner.items.get(item.id)!==item)throw Error('Synthetic Item membership mismatch');
  guard();await owner.updateEmbeddedDocuments('Item',[{_id:item.id,name:'Token fixture ability '+i,'system.description.value':'<p>Token fixture '+i+' source.</p>'}]);await open();
 }
 const sourceHp=tokens.slice(0,2).map(token=>token.actor.toObject(true).system.attributes.hp.value),currentHp=tokens.slice(0,2).map(token=>token.actor.toObject(false).system.attributes.hp.value);
 if(JSON.stringify(sourceHp)!=='[7,19]'||JSON.stringify(currentHp)!=='[7,19]'||actor.toObject(true).system.attributes.hp.value!==30||items[0].toObject(true).name!=='Token fixture base ability')throw Error('Fixture source separation mismatch');
 const selectedItems=tokens.map(token=>token.actor.items.get(items[0].id));
 if(new Set(selectedItems.map(item=>item.uuid)).size!==3||new Set(selectedItems.map(item=>item.toObject(true).name)).size!==3)throw Error('Fixture Item separation mismatch');
 result={actor_uuid:actor.uuid,scene_uuid:scene.uuid,token_uuids:tokens.map(token=>token.uuid),unlinked_actor_uuids:tokens.slice(0,2).map(token=>token.actor.uuid),item_uuids:selectedItems.map(item=>item.uuid),source_hp:sourceHp,current_hp:currentHp,linked_actor_uuid:tokens[2].actor.uuid,active_scene_uuid:state.active_scene_uuid,active_scene_unchanged:activeUuid()===state.active_scene_uuid};
}finally{state.pending--;}
"""
CLEANUP = """
state.closed=true;
for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));guard();}
if(!state.pending)await dropRoots();
const remaining=roots();
const result={pending:state.pending,actors:remaining.actors.length,scenes:remaining.scenes.length,active_scene_unchanged:activeUuid()===state.active_scene_uuid};
"""
FINGERPRINT = """
await open();const selected=roots();
if(selected.actors.length!==1||selected.scenes.length!==1||selected.scenes[0].tokens.size!==3)throw Error('Fixture roots unavailable');
const bytes=new TextEncoder().encode(JSON.stringify([selected.actors[0].toObject(true),selected.scenes[0].toObject(true)]));
const result=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),byte=>byte.toString(16).padStart(2,'0')).join('');
"""


def code(body, run_id, expected=None):
    """PF2e-specific guarded fixture operations; selectors come from setup only."""
    if not isinstance(run_id,str) or re.fullmatch(r'[A-Za-z0-9-]{1,80}',run_id) is None:
        raise ValueError('Safe per-run marker required')
    if expected is not None and not isinstance(expected,dict):
        raise ValueError('Fixture metadata object required')
    expected={key:expected[key] for key in ('actor_uuid','scene_uuid','active_scene_uuid') if expected is not None and key in expected}
    return GUARD+'const guard=()=>{'+GUARD+'};const run='+json.dumps(run_id)+';const expected='+json.dumps(expected)+';'+LIFECYCLE+body+CHUNKS


def payload(response):
    return response.structured_content if response.structured_content is not None else json.loads(next(block.text for block in response.content if block.type=='text'))


async def token_verify(client, world_id, scene_uuid):
    """Reuse the PF2e-specific original token acceptance on the exact new Scene."""
    spec=importlib.util.spec_from_file_location('token_fixture_reader',Path(__file__).with_name('actor-token-live-check.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return await module.verify(client,world_id,scene_uuid=scene_uuid)


async def verify(client, world_id, run_id, summary=None):
    """PF2e-specific token proof with separately authorized setup and exact cleanup."""
    if world_id!='test':
        raise ValueError('Explicit existing test world required')
    result=summary if summary is not None else {}
    result.update(passed=False,cleanup_verified=False,requested_calls=0,completed_calls=0,mcp_calls=0)
    fixture=None;stage='fixture_creation'

    class CountedClient:
        async def call_tool(self,*args,**kwargs):
            result['requested_calls']+=1
            response=await client.call_tool(*args,**kwargs)
            result['completed_calls']+=1;result['mcp_calls']=result['completed_calls']
            return response

        async def list_tools(self,*args,**kwargs):
            result['requested_calls']+=1
            response=await client.list_tools(*args,**kwargs)
            result['completed_calls']+=1;result['mcp_calls']=result['completed_calls']
            return response

    counted=CountedClient()

    async def execute(body):
        response=await counted.call_tool('execute_javascript',{'code':code(body,run_id,fixture)})
        value=payload(response)['value']
        if isinstance(value,dict) and value.get('$type')=='Array':
            assert value.get('truncated') is False
            value=''.join(value['values'])
        return json.loads(value)

    try:
        fixture=await execute(CREATE)
        assert len(set(fixture['token_uuids']))==3 and len(set(fixture['unlinked_actor_uuids']))==2 and len(set(fixture['item_uuids']))==3
        assert fixture['source_hp']==[7,19] and fixture['current_hp']==[7,19] and fixture['linked_actor_uuid']==fixture['actor_uuid'] and fixture['active_scene_unchanged']
        result['fixture_created']=True
        stage='fixture_fingerprint_before';before=await execute(FINGERPRINT)
        stage='token_reader_acceptance';proof=await token_verify(counted,world_id,fixture['scene_uuid'])
        result['token_check']=proof
        assert proof['passed'] and proof['source_unchanged'] and proof['unlinked_tokens']==2 and proof['linked_controls']==1 and proof['inactive_scene_verified']
        assert proof['distinct_source_hp'] and proof['distinct_item_content'] and proof['coverage_gaps']==[]
        stage='fixture_fingerprint_after';assert await execute(FINGERPRINT)==before
        result.update(passed=True,fixture_fingerprint_unchanged=True)
    except Exception as error:
        result.update(passed=False,failure_stage=stage,exception_type=type(error).__name__)
    finally:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                removed=await asyncio.shield(execute(CLEANUP))
            assert removed==dict(pending=0,actors=0,scenes=0,active_scene_unchanged=True)
            result['cleanup_verified']=True
        except Exception as error:
            result.update(passed=False,cleanup_exception_type=type(error).__name__)
    return result


async def main(world_id):
    if world_id!='test':
        raise ValueError('Explicit existing test world required')
    result=dict(passed=False,cleanup_verified=False)
    try:
        token=next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1]/'.env.mcp').read_text().splitlines() if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise RuntimeError('Missing local caller credential')
        transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token})
        async with Client(transport,timeout=REQUEST_TIMEOUT_SECONDS,init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                await verify(client,world_id,uuid4().hex,result)
    except Exception as error:
        result.update(passed=False,exception_type=type(error).__name__)
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id',required=True,choices=['test'])
    raise SystemExit(asyncio.run(main(parser.parse_args().world_id)))
