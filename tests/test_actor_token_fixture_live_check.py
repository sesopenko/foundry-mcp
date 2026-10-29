"""Offline safety proof for the authorized, marked PF2e token fixture.

Actual fixture JavaScript runs against mock public Documents; no Foundry world
is contacted. These tests prove lifecycle guards, not live ActorDelta behavior.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('token_fixture_live', ROOT / 'scripts/actor-token-fixture-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)
RUN = 'offline-token-run'
EXPECTED = dict(actor_uuid='Actor.fixture', scene_uuid='Scene.fixture')


NODE = r"""
import {webcrypto} from 'node:crypto';
Object.defineProperty(globalThis,'crypto',{value:webcrypto});
const [create,cleanupKnown,cleanupUnknown,scenario]=JSON.parse(process.argv[1]);
const deleted=[],updates=[],forbidden=[];let creates=0,release,entered;
const begun=new Promise(resolve=>entered=resolve),gate=new Promise(resolve=>release=resolve);
const fail=label=>{forbidden.push(label);throw Error('Prohibited '+label);};
Object.defineProperty(globalThis,'canvas',{get:()=>fail('canvas')});
const collection=()=>{const result=new Map();result.filter=fn=>[...result.values()].filter(fn);result.find=fn=>[...result.values()].find(fn);result.some=fn=>[...result.values()].some(fn);Object.defineProperty(result,'contents',{get:()=>[...result.values()]});return result;};
const actors=collection(),scenes=collection();
const original={documentName:'Scene',id:'original',uuid:'Scene.original',active:true,tokens:collection(),flags:{'foundry-mcp':{tokenFixtureProbe:'unrelated'}},getFlag(ns,key){return this.flags[ns]?.[key];},delete:()=>fail('unrelated Scene deletion'),update:()=>fail('unrelated Scene update'),activate:()=>fail('activation')};
scenes.set(original.id,original);Object.defineProperty(scenes,'active',{get:()=>original});
const unrelated={documentName:'Actor',id:'unrelated',uuid:'Actor.unrelated',type:'npc',flags:{'foundry-mcp':{tokenFixtureProbe:'unrelated'}},getFlag(ns,key){return this.flags[ns]?.[key];},delete:()=>fail('unrelated Actor deletion'),update:()=>fail('unrelated Actor update')};actors.set(unrelated.id,unrelated);
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={actors,scenes,ready:true,user:{isGM:true},world:{id:scenario==='wrong_world'?'campaign':'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'},time:Object.freeze({worldTime:12345}),combat:null};
function marker(document){return document.flags?.['foundry-mcp']?.tokenFixtureProbe;}
function item(owner,data){
 const source=structuredClone(data),id=source._id??'inert';source._id=id;
 return {documentName:'Item',id,uuid:owner.uuid+'.Item.'+id,type:source.type,parent:owner,flags:source.flags??{},getFlag(ns,key){return this.flags[ns]?.[key];},toObject(flag=true){if(flag!==true)fail('Item transformed source');return structuredClone(source);},get name(){return source.name;},setSource(update){for(const [key,value]of Object.entries(update)){if(key==='_id')continue;const parts=key.split('.');let target=source;for(const part of parts.slice(0,-1))target=target[part]??={};target[parts.at(-1)]=structuredClone(value);}},update:()=>fail('direct Item update'),roll:()=>fail('roll'),prepareData:()=>fail('preparation')};
}
function actor(data,uuid='Actor.fixture'){
 const source=structuredClone(data),id=uuid.split('.').at(-1);source._id=id;
 const value={documentName:'Actor',id,uuid,type:source.type,flags:source.flags??{},items:collection(),getFlag(ns,key){return this.flags[ns]?.[key];},testUserPermission:()=>true,toObject(flag=true){if(typeof flag!=='boolean')fail('source basis');return structuredClone({...source,items:[...this.items.values()].map(i=>i.toObject(true))});},async createEmbeddedDocuments(kind,inputs){if(kind!=='Item'||marker(this)!=='offline-token-run')fail('foreign embedded creation');const made=inputs.map(input=>item(this,input));for(const child of made)this.items.set(child.id,child);return made;},async updateEmbeddedDocuments(kind,inputs){if(kind!=='Item'||marker(this)!=='offline-token-run'||!this.uuid.startsWith('Scene.fixture.Token.'))fail('foreign Item update');return inputs.map(update=>{const child=this.items.get(update._id);if(!child||child.parent!==this)fail('wrong owned Item');updates.push(child.uuid);child.setSource(update);return child;});},async getTokenDocument(data,options){if(options?.parent?.uuid!=='Scene.fixture')fail('unscoped token construction');return {toObject(flag=true){if(flag!==true)fail('token source basis');return structuredClone({name:'Token',actorId:value.id,...data});}};},async delete(){deleted.push(this.uuid);actors.delete(this.id);},prepareData:()=>fail('preparation'),rollInitiative:()=>fail('roll')};
 Object.defineProperty(value,'_source',{get:()=>fail('private source')});return value;
}
async function createActor(data){
 creates++;if(scenario==='late_actor'){entered();await gate;}
 const made=actor(data);actors.set(made.id,made);return made;
}
async function createScene(data){
 creates++;if(scenario==='late_scene'){entered();await gate;}
 if(data.active!==false||data.navigation!==false)fail('active fixture Scene');
 const source=structuredClone(data),value={documentName:'Scene',id:'fixture',uuid:'Scene.fixture',active:false,flags:source.flags??{},tokens:collection(),getFlag(ns,key){return this.flags[ns]?.[key];},testUserPermission:()=>true,toObject:()=>structuredClone(source),async createEmbeddedDocuments(kind,inputs){if(kind!=='Token'||marker(this)!=='offline-token-run')fail('foreign token creation');return inputs.map((input,index)=>{const base=actors.get(input.actorId);if(!base||marker(base)!=='offline-token-run')fail('foreign base Actor');const id='token'+index,uuid=this.uuid+'.Token.'+id,synthetic=input.actorLink?base:actor({...base.toObject(true),system:{...base.toObject(true).system,...input.delta?.system}},uuid+'.Actor.'+base.id);if(!input.actorLink){for(const child of base.items.values()){const copy=item(synthetic,child.toObject(true));synthetic.items.set(copy.id,copy);}}
 const token={documentName:'Token',id,uuid,parent:this,flags:input.flags??{},actor:synthetic,baseActor:base,isLinked:!!input.actorLink,getFlag(ns,key){return this.flags[ns]?.[key];},testUserPermission:()=>true,toObject:()=>structuredClone(input),update:()=>fail('token update')};synthetic.token=token;this.tokens.set(id,token);return token;});},async delete(){deleted.push(this.uuid);scenes.delete(this.id);},activate:()=>fail('activation'),view:()=>fail('view'),update:()=>fail('Scene update')};
 scenes.set(value.id,value);return value;
}
globalThis.Actor={implementation:{create:createActor},create:createActor};globalThis.Scene={implementation:{create:createScene},create:createScene};
globalThis.foundry={utils:{fromUuid:async uuid=>[...actors.values(),...scenes.values(),...scenes.values()].flatMap(doc=>[doc,...(doc.tokens?[...doc.tokens.values()]:[])]).find(doc=>doc.uuid===uuid)}};
const execute=body=>new Function('return (async()=>{'+body+'})()')();
const decode=value=>Array.isArray(value)?JSON.parse(value.join('')):value;
let creation=null,cleanup=null,rejected=false,early=null,setup=null;
if(scenario.startsWith('late_')){
 const pending=execute(create).then(value=>{creation=decode(value);return false;},()=>true);
 await begun;globalThis.setTimeout=callback=>{callback();return 0;};
 early=decode(await execute(cleanupUnknown));release();rejected=await pending;cleanup=decode(await execute(cleanupUnknown));
}else{
 try{creation=decode(await execute(create));}catch{rejected=true;}
 if(creation){
  const own=scenes.get('fixture'),base=actors.get('fixture');
  const tokens=[...own.tokens.values()];setup={active:own.active,linked:tokens.filter(t=>t.isLinked).length,unlinked:tokens.filter(t=>!t.isLinked).length,hp:tokens.filter(t=>!t.isLinked).map(t=>t.actor.toObject(true).system.attributes.hp.value),names:tokens.filter(t=>!t.isLinked).map(t=>[...t.actor.items.values()][0].toObject(true).name),baseName:[...base.items.values()][0].toObject(true).name};
  if(scenario==='wrong_uuid'){own.uuid='Scene.wrong';}
  if(scenario==='wrong_actor_type'){base.type='character';}
  if(scenario==='wrong_scene_type'){own.documentName='Actor';}
  if(scenario==='changed_marker'){own.flags['foundry-mcp'].tokenFixtureProbe='other-run';}
  if(scenario==='ambiguous'){const second={...base,id:'duplicate',uuid:'Actor.duplicate',delete:()=>fail('ambiguous deletion')};actors.set(second.id,second);}
  if(scenario==='foreign_token'){own.tokens.set('foreign',{uuid:own.uuid+'.Token.foreign',getFlag:()=> 'other-run'});}
  try{cleanup=decode(await execute(cleanupKnown));}catch{rejected=true;}
 }
}
console.log(JSON.stringify({creation,cleanup,early,setup,rejected,creates,deleted,updates,forbidden,active:scenes.active.uuid,remainingActors:actors.filter(a=>marker(a)==='offline-token-run').length,remainingScenes:scenes.filter(s=>marker(s)==='offline-token-run').length,unrelatedSurvived:actors.get('unrelated')===unrelated&&scenes.get('original')===original}));
"""


def response(value):
    return SimpleNamespace(structured_content={'value': json.dumps(value)})


class Client:
    def __init__(self, failure=None):
        self.failure, self.calls, self.cleaned, self.fingerprints = failure, [], False, 0

    async def list_tools(self):
        self.calls.append(('list_tools', {}))
        return []

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if name != 'execute_javascript':
            if self.failure == 'reader_transport':
                raise RuntimeError('PRIVATE_TEST_CONTENT')
            return SimpleNamespace(structured_content={})
        script = args['code']
        if script == HARNESS.code(HARNESS.CREATE, RUN):
            if self.failure == 'lost_creation':
                raise RuntimeError('PRIVATE_TEST_CONTENT')
            return response(dict(EXPECTED, token_uuids=['Scene.fixture.Token.a','Scene.fixture.Token.b','Scene.fixture.Token.c'],
                                 unlinked_actor_uuids=['Scene.fixture.Token.a.Actor.fixture','Scene.fixture.Token.b.Actor.fixture'],
                                 item_uuids=['Scene.fixture.Token.a.Actor.fixture.Item.i','Scene.fixture.Token.b.Actor.fixture.Item.i','Actor.fixture.Item.i'],
                                 source_hp=[7,19],current_hp=[7,19],linked_actor_uuid='Actor.fixture',active_scene_unchanged=True))
        if script == HARNESS.code(HARNESS.FINGERPRINT,RUN,EXPECTED):
            self.fingerprints += 1
            return response('changed-read-phase' if self.failure=='fingerprint_changed' and self.fingerprints>1 else 'unchanged-read-phase')
        if script not in (HARNESS.code(HARNESS.CLEANUP,RUN,EXPECTED),HARNESS.code(HARNESS.CLEANUP,RUN)):
            raise AssertionError('Unexpected fixture operation')
        self.cleaned = True
        if self.failure == 'cleanup_transport':
            raise RuntimeError('PRIVATE_TEST_CONTENT')
        return response(dict(pending=1 if self.failure=='pending' else 0,actors=0,scenes=0,active_scene_unchanged=self.failure!='active_changed'))


def proof(**changes):
    result=dict(passed=True,source_unchanged=True,unlinked_tokens=2,linked_controls=1,inactive_scene_verified=True,
                distinct_source_hp=True,distinct_item_content=True,coverage_gaps=[])
    result.update(changes)
    return result


class TokenFixtureTests(unittest.IsolatedAsyncioTestCase):
    def browser(self, scenario):
        source=[HARNESS.code(HARNESS.CREATE,RUN),HARNESS.code(HARNESS.CLEANUP,RUN,EXPECTED),HARNESS.code(HARNESS.CLEANUP,RUN),scenario]
        process=subprocess.run(['node','--input-type=module','-e',NODE,json.dumps(source)],cwd=ROOT,text=True,capture_output=True,timeout=10)
        self.assertEqual(process.returncode,0,process.stderr)
        return json.loads(process.stdout)

    def test_actual_setup_has_distinct_same_base_copies_and_scene_first_cleanup(self):
        result=self.browser('valid')
        self.assertFalse(result['rejected'],result)
        self.assertEqual(result['setup']['hp'],[7,19])
        self.assertEqual((result['setup']['linked'],result['setup']['unlinked']),(1,2))
        self.assertFalse(result['setup']['active'])
        self.assertNotEqual(*result['setup']['names'])
        self.assertEqual(result['deleted'],['Scene.fixture','Actor.fixture'])
        self.assertEqual(len(result['updates']),2)
        self.assertTrue(all(uuid.startswith('Scene.fixture.Token.') for uuid in result['updates']))
        self.assertEqual(result['forbidden'],[])
        self.assertTrue(result['unrelatedSurvived'])
        self.assertEqual(result['active'],'Scene.original')
        self.assertEqual((result['remainingActors'],result['remainingScenes']),(0,0))

    def test_actual_late_actor_and_scene_creation_self_cleanup_without_orphans(self):
        for scenario in ('late_actor','late_scene'):
            with self.subTest(scenario=scenario):
                result=self.browser(scenario)
                self.assertTrue(result['rejected'],result)
                self.assertGreater(result['early']['pending'],0)
                self.assertEqual(result['cleanup']['pending'],0)
                self.assertEqual((result['remainingActors'],result['remainingScenes']),(0,0))
                self.assertEqual(result['forbidden'],[])
                self.assertTrue(result['unrelatedSurvived'])
                if scenario=='late_scene':self.assertEqual(result['deleted'],['Scene.fixture','Actor.fixture'])

    def test_actual_cleanup_rejects_changed_identity_marker_type_and_foreign_members(self):
        for scenario in ('wrong_uuid','wrong_actor_type','wrong_scene_type','changed_marker','ambiguous','foreign_token'):
            with self.subTest(scenario=scenario):
                result=self.browser(scenario)
                self.assertTrue(result['rejected'],result)
                self.assertEqual(result['deleted'],[])
                self.assertEqual(result['forbidden'],[])
                self.assertTrue(result['unrelatedSurvived'])

    def test_actual_wrong_world_precedes_creation_and_all_writes(self):
        result=self.browser('wrong_world')
        self.assertTrue(result['rejected'])
        self.assertEqual(result['creates'],0)
        self.assertEqual(result['updates'],[])
        self.assertEqual(result['deleted'],[])

    async def test_same_client_nested_proof_counts_and_exact_cleanup(self):
        client=Client()
        async def nested(adapter,world,scene):
            self.assertEqual((world,scene),('test','Scene.fixture'))
            await adapter.list_tools()
            await adapter.call_tool('read_actor',dict(token_uuid='Scene.fixture.Token.a'))
            return proof()
        with patch.object(HARNESS,'token_verify',side_effect=nested):
            report=await HARNESS.verify(client,'test',RUN)
        self.assertTrue(report['passed'],report)
        self.assertTrue(report['cleanup_verified'])
        self.assertTrue(client.cleaned)
        self.assertEqual(report['requested_calls'],len(client.calls))
        self.assertEqual(report['completed_calls'],len(client.calls))

    async def test_failed_creation_reader_or_cleanup_never_reports_false_success(self):
        for failure in ('lost_creation','reader_transport','cleanup_transport','pending','active_changed','fingerprint_changed'):
            with self.subTest(failure=failure):
                client=Client(failure)
                async def nested(adapter,world,scene):
                    await adapter.call_tool('read_actor',{})
                    return proof()
                with patch.object(HARNESS,'token_verify',side_effect=nested):
                    report=await HARNESS.verify(client,'test',RUN)
                self.assertFalse(report['passed'],report)
                self.assertTrue(client.cleaned)
                self.assertNotIn('PRIVATE_TEST_CONTENT',json.dumps(report))
                self.assertEqual(report['requested_calls'],len(client.calls))
                if failure in ('lost_creation','reader_transport','cleanup_transport'):
                    self.assertEqual(report['requested_calls']-report['completed_calls'],1)

    async def test_incomplete_nested_runtime_proof_cannot_pass_even_when_cleanup_succeeds(self):
        for invalid in (dict(passed=False),dict(source_unchanged=False),dict(unlinked_tokens=1),dict(linked_controls=0),
                        dict(inactive_scene_verified=False),dict(distinct_source_hp=False),dict(distinct_item_content=False),dict(coverage_gaps=['missing'])):
            with self.subTest(invalid=invalid):
                with patch.object(HARNESS,'token_verify',AsyncMock(return_value=proof(**invalid))):
                    report=await HARNESS.verify(Client(),'test',RUN)
                self.assertFalse(report['passed'],report)
                self.assertTrue(report['cleanup_verified'])

    async def test_world_marker_and_client_deadlines_guard_unattended_entry(self):
        client=Client()
        with self.assertRaises(ValueError):await HARNESS.verify(client,'campaign',RUN)
        self.assertEqual(client.calls,[])
        with self.assertRaises(ValueError):HARNESS.code(HARNESS.CREATE,'unsafe;marker')
        class Session:
            async def __aenter__(self):raise RuntimeError('PRIVATE_TEST_CONTENT')
            async def __aexit__(self,*args):return False
        output=io.StringIO()
        with patch.object(HARNESS.Path,'read_text',return_value='FOUNDRY_MCP_CALLER_TOKEN=LOCAL_TEST_CREDENTIAL'),patch.object(HARNESS,'StreamableHttpTransport',return_value=object()),patch.object(HARNESS,'Client',return_value=Session()) as factory,contextlib.redirect_stdout(output):
            self.assertEqual(await HARNESS.main('test'),1)
        self.assertEqual(factory.call_args.kwargs,dict(timeout=30,init_timeout=10))
        self.assertEqual(HARNESS.SESSION_TIMEOUT_SECONDS,180)
        self.assertNotIn('PRIVATE_TEST_CONTENT',output.getvalue())
        self.assertNotIn('LOCAL_TEST_CREDENTIAL',output.getvalue())
