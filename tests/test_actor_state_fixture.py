"""Offline exact-cleanup and opt-in safety for state verification fixtures."""
import asyncio
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
SPEC = importlib.util.spec_from_file_location('state_fixture_harness',ROOT/'scripts/actor-state-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class StateFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def test_flag_and_world_guards_precede_credentials_and_client(self):
        with patch.object(HARNESS.Path,'read_text',side_effect=AssertionError('Credential access forbidden')), \
             patch.object(HARNESS,'Client',side_effect=AssertionError('Connection forbidden')):
            for kwargs in (dict(state_fixture=True),dict(state_fixture=True,world_id='campaign'),dict(discovery_only=True,state_fixture=True,world_id='test')):
                with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                    await HARNESS.main(**kwargs)

    async def test_default_dispatch_is_read_only(self):
        with patch.object(HARNESS,'_existing_main',new=AsyncMock(return_value=0)) as existing, \
             patch.object(HARNESS,'run_state_fixture',side_effect=AssertionError('Fixture forbidden')) as fixture:
            self.assertEqual(await HARNESS.main(),0)
            existing.assert_awaited_once_with(False)
            fixture.assert_not_called()

    def node(self,script,args):
        result=subprocess.run(['node','--input-type=module','-e',script,json.dumps(args)],capture_output=True,text=True,cwd=ROOT,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_actual_cleanup_only_deletes_exact_marked_actor(self):
        code=HARNESS.fixture_code(HARNESS.CLEANUP_STATE,'offline-state','Actor.ours')
        script=r"""
const code=JSON.parse(process.argv[1]);const actors=[],deleted=[];
globalThis.location={origin:'http://localhost:30000'};
for(const [id,marker]of [['ours','offline-state'],['other','different-run']])actors.push({uuid:'Actor.'+id,type:'character',getFlag:()=>marker,async delete(){deleted.push(id);actors.splice(actors.indexOf(this),1);}});
globalThis.game={actors,ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
const output=await new Function('return (async()=>{'+code+'})()')();
console.log(JSON.stringify({deleted,remaining:actors.map(a=>a.uuid),result:JSON.parse(output.join(''))}));
"""
        result=self.node(script,code)
        self.assertEqual(result['deleted'],['ours'])
        self.assertEqual(result['remaining'],['Actor.other'])
        self.assertEqual(result['result']['pending'],0)
        self.assertEqual(result['result']['remaining'],0)

    def test_actual_deferred_creation_is_pending_then_self_deletes_when_closed(self):
        creation=HARNESS.fixture_code(HARNESS.CREATE_STATE,'offline-state')
        cleanup=HARNESS.fixture_code(HARNESS.CLEANUP_STATE,'offline-state')
        script=r"""
const [creation,cleanup]=JSON.parse(process.argv[1]);const actors=[],deleted=[];let resolveCreate;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={actors,ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
globalThis.Actor={implementation:{create:async data=>new Promise(resolve=>{resolveCreate=()=>{const actor={uuid:'Actor.ours',type:data.type,getFlag:()=> 'offline-state',async delete(){deleted.push(this.uuid);actors.splice(actors.indexOf(this),1);},createEmbeddedDocuments(){throw Error('Closed creation must not add Items');}};actors.push(actor);resolve(actor);};})}};
const execute=code=>new Function('return (async()=>{'+code+'})()')();
const pending=execute(creation).then(()=>true,()=>false);
for(let n=0;!resolveCreate&&n<30;n++)await Promise.resolve();if(!resolveCreate)throw Error('No deferred create');
globalThis.setTimeout=callback=>{callback();return 0;};
const early=JSON.parse((await execute(cleanup)).join(''));
resolveCreate();const success=await pending;
const final=JSON.parse((await execute(cleanup)).join(''));
console.log(JSON.stringify({early,final,success,deleted}));
"""
        result=self.node(script,[creation,cleanup])
        self.assertEqual(result['early']['pending'],1)
        self.assertFalse(result['success'])
        self.assertEqual(result['deleted'],['Actor.ours'])
        self.assertEqual(result['final'],dict(pending=0,remaining=0))

    def test_actual_cleanup_rejects_wrong_uuid_and_wrong_type_without_deletion(self):
        code=HARNESS.fixture_code(HARNESS.CLEANUP_STATE,'offline-state','Actor.expected')
        script=r"""
const [code,type]=JSON.parse(process.argv[1]);let deletes=0;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={actors:[{uuid:'Actor.other',type,getFlag:()=> 'offline-state',async delete(){deletes++;}}],ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
let rejected=false;try{await new Function('return (async()=>{'+code+'})()')();}catch{rejected=true;}
console.log(JSON.stringify({rejected,deletes}));
"""
        for actor_type in ('character','npc'):
            self.assertEqual(self.node(script,[code,actor_type]),dict(rejected=True,deletes=0))

    async def test_lost_response_and_pending_cleanup_are_sanitized_and_fail_closed(self):
        class Client:
            def __init__(self,pending):self.pending=pending;self.calls=[]
            async def call_tool(self,name,arguments):
                self.calls.append((name,arguments))
                if 'Actor.implementation.create' in arguments['code']:
                    raise RuntimeError('private-token campaign-name secret prose')
                return SimpleNamespace(structured_content={'value':json.dumps(dict(pending=self.pending,remaining=0))})
        for pending in (0,1):
            client=Client(pending)
            report=await HARNESS.run_state_fixture(client,'test','offline-state')
            self.assertFalse(report['passed'])
            self.assertEqual(report['cleanup_verified'],pending==0)
            self.assertEqual(len(client.calls),2)
            self.assertNotIn('private-token',json.dumps(report))
            self.assertNotIn('campaign-name',json.dumps(report))

    async def test_cancelled_request_still_runs_bounded_cleanup(self):
        class Client:
            def __init__(self):self.calls=[]
            async def call_tool(self,name,arguments):
                self.calls.append((name,arguments))
                if 'Actor.implementation.create' in arguments['code']:
                    raise asyncio.CancelledError()
                return SimpleNamespace(structured_content={'value':json.dumps(dict(pending=0,remaining=0))})
        summary={};client=Client()
        with self.assertRaises(asyncio.CancelledError):
            await HARNESS.run_state_fixture(client,'test','offline-state',summary)
        self.assertTrue(summary['cleanup_verified'])
        self.assertEqual(len(client.calls),2)

    async def test_fixture_connection_failure_has_bounded_client_and_safe_output(self):
        class Session:
            async def __aenter__(self):raise RuntimeError('private-token campaign source contents')
            async def __aexit__(self,*args):return False
        output=io.StringIO()
        with patch.object(HARNESS.Path,'read_text',return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(HARNESS,'StreamableHttpTransport',return_value=object()), \
             patch.object(HARNESS,'Client',return_value=Session()) as factory,contextlib.redirect_stdout(output):
            code=await HARNESS.main(state_fixture=True,world_id='test')
        self.assertEqual(code,1)
        self.assertFalse(json.loads(output.getvalue())['passed'])
        self.assertEqual(factory.call_args.kwargs['timeout'],30)
        self.assertEqual(factory.call_args.kwargs['init_timeout'],10)
        self.assertEqual(HARNESS.SESSION_TIMEOUT_SECONDS,180)
        self.assertNotIn('private-token',output.getvalue())
        self.assertNotIn('campaign',output.getvalue())

    def test_actual_setup_creates_only_marked_state_items_then_cleans_actor(self):
        creation=HARNESS.fixture_code(HARNESS.CREATE_STATE,'offline-state')
        cleanup=HARNESS.fixture_code(HARNESS.CLEANUP_STATE,'offline-state','Actor.ours')
        script=r"""
const [creation,cleanup]=JSON.parse(process.argv[1]);const actors=[],types=[],updates=[],deleted=[];let itemIndex=0;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={actors,ready:true,user:{isGM:true},world:{id:'test'},time:{worldTime:1000},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
globalThis.Actor={implementation:{create:async data=>{
 const actor={uuid:'Actor.ours',type:data.type,items:new Map(),getFlag:()=>data.flags['foundry-mcp'].stateVerificationRun,
 async createEmbeddedDocuments(kind,inputs){if(kind!=='Item')throw Error('Unexpected document kind');return inputs.map(source=>{const id=String(++itemIndex),item={id,uuid:this.uuid+'.Item.'+id,type:source.type,parent:this,source};this.items.set(id,item);types.push(item.type);return item;});},
 async updateEmbeddedDocuments(kind,changes){if(kind!=='Item'||changes.length!==1)throw Error('Unexpected update');const item=this.items.get(changes[0]._id);if(item?.type!=='effect')throw Error('Wrong update target');updates.push(changes[0]);},
 async delete(){deleted.push(this.uuid);this.items.clear();actors.splice(actors.indexOf(this),1);}};
 actors.push(actor);return actor;
}}};
const execute=code=>new Function('return (async()=>{'+code+'})()')();
const created=JSON.parse((await execute(creation)).join(''));
const cleaned=JSON.parse((await execute(cleanup)).join(''));
console.log(JSON.stringify({types,updates,deleted,created,cleaned,remaining:actors.length}));
"""
        result=self.node(script,[creation,cleanup])
        self.assertEqual(result['types'].count('action'),2)
        self.assertEqual(result['types'].count('effect'),3)
        self.assertEqual(result['types'].count('condition'),3)
        self.assertEqual(len(result['updates']),1)
        self.assertEqual(result['updates'][0]['system.start.value'],400)
        self.assertEqual(result['deleted'],['Actor.ours'])
        self.assertEqual(result['remaining'],0)
        self.assertEqual(result['cleaned'],dict(pending=0,remaining=0))
