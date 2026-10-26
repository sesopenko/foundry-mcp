"""Offline safety checks for optional genuine-character Strike verification."""
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
SPEC = importlib.util.spec_from_file_location('strike_live_check', ROOT / 'scripts/actor-strikes-current-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class StrikeLiveCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_wrong_world_rejects_before_credentials_or_client(self):
        with patch.object(HARNESS.Path, 'read_text', side_effect=AssertionError('Credentials must not be read')), \
             patch.object(HARNESS, 'Client', side_effect=AssertionError('Client must not connect')):
            with self.assertRaises(ValueError):
                await HARNESS.main('campaign')

    async def test_default_verification_never_requests_a_character_fixture(self):
        client = object()
        class Session:
            async def __aenter__(self):return client
            async def __aexit__(self, *args):return False
        output = io.StringIO()
        with patch.object(HARNESS.Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(HARNESS, 'StreamableHttpTransport', return_value=object()), \
             patch.object(HARNESS, 'Client', return_value=Session()) as factory, \
             patch.object(HARNESS, 'run_character_fixture', side_effect=AssertionError('Default fixture forbidden')) as fixture, \
             patch.object(HARNESS, 'verify', new=AsyncMock(return_value=dict(passed=True))) as verify, \
             contextlib.redirect_stdout(output):
            code = await HARNESS.main('test')
        self.assertEqual(code,0)
        self.assertEqual(factory.call_args.kwargs['timeout'],30)
        self.assertEqual(factory.call_args.kwargs['init_timeout'],10)
        self.assertEqual(HARNESS.SESSION_TIMEOUT_SECONDS,180)
        args,kwargs=verify.await_args
        self.assertEqual(args[:2],(client,'test'))
        self.assertFalse(kwargs.get('character_fixture',False))
        fixture.assert_not_called()
        self.assertNotIn('private-token',output.getvalue())

    async def test_connection_failure_is_sanitized(self):
        class Session:
            async def __aenter__(self):raise RuntimeError('private-token campaign source prose')
            async def __aexit__(self,*args):return False
        output=io.StringIO()
        with patch.object(HARNESS.Path,'read_text',return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(HARNESS,'StreamableHttpTransport',return_value=object()), \
             patch.object(HARNESS,'Client',return_value=Session()),contextlib.redirect_stdout(output):
            code=await HARNESS.main('test')
        self.assertEqual(code,1)
        self.assertFalse(json.loads(output.getvalue())['passed'])
        self.assertNotIn('private-token',output.getvalue())
        self.assertNotIn('campaign',output.getvalue())

    def test_actual_cleanup_preserves_unrelated_actors_and_exact_marker_identity(self):
        code=HARNESS.fixture_code(HARNESS.CHARACTER_CLEANUP,'offline-strike','Actor.ours')
        script=r"""
const code=JSON.parse(process.argv[1]);
globalThis.location={origin:'http://localhost:30000'};
const actors=[],deleted=[];
for(const [id,marker,type]of [['ours','offline-strike','character'],['other','other-run','character']]){
 const actor={id,uuid:'Actor.'+id,type,getFlag:()=>marker,async delete(){deleted.push(id);actors.splice(actors.indexOf(this),1);}};actors.push(actor);
}
globalThis.game={actors,ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
const chunks=await new Function('return (async()=>{'+code+'})()')();
console.log(JSON.stringify({deleted,remaining:actors.map(a=>a.id),result:JSON.parse(chunks.join(''))}));
"""
        process=subprocess.run(['node','--input-type=module','-e',script,json.dumps(code)],capture_output=True,text=True,cwd=ROOT,timeout=15)
        self.assertEqual(process.returncode,0,process.stderr)
        observed=json.loads(process.stdout)
        self.assertEqual(observed['deleted'],['ours'])
        self.assertEqual(observed['remaining'],['other'])
        self.assertEqual(observed['result']['pending'],0)

    def test_actual_deferred_character_creation_self_deletes_after_closed_cleanup(self):
        create=HARNESS.fixture_code(HARNESS.CHARACTER_CREATE,'offline-strike')
        cleanup=HARNESS.fixture_code(HARNESS.CHARACTER_CLEANUP,'offline-strike')
        script=r"""
import {webcrypto} from 'node:crypto';
Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
const [creation,cleanup]=JSON.parse(process.argv[1]);
globalThis.location={origin:'http://localhost:30000'};
const actors=[],deleted=[];let resolveCreate,creates=0;
globalThis.game={actors,ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
const other={uuid:'Actor.other',type:'character',getFlag:()=> 'other-run',async delete(){throw Error('Unrelated delete');}};actors.push(other);
globalThis.Actor={implementation:{create:async data=>{creates++;return new Promise(resolve=>{resolveCreate=()=>{
const actor={id:'ours',uuid:'Actor.ours',documentName:'Actor',type:data.type,items:new Map(),getFlag:()=> 'offline-strike',async delete(){deleted.push('ours');actors.splice(actors.indexOf(this),1);},toObject(){throw Error('Closed creation must not read source');}};
actors.push(actor);resolve(actor);
};});}}};
const execute=code=>new Function('return (async()=>{'+code+'})()')();
const pending=execute(creation).then(()=>({passed:true}),error=>({passed:false,error_type:error.name}));
for(let n=0;!resolveCreate&&n<40;n++)await Promise.resolve();
if(!resolveCreate)throw Error('Deferred create not reached');
globalThis.setTimeout=callback=>{callback();return 0;};
const early=JSON.parse((await execute(cleanup)).join(''));
resolveCreate();const outcome=await pending;
const final=JSON.parse((await execute(cleanup)).join(''));
console.log(JSON.stringify({early,final,outcome,creates,deleted,otherSurvived:actors.length===1&&actors[0]===other}));
"""
        process=subprocess.run(['node','--input-type=module','-e',script,json.dumps([create,cleanup])],capture_output=True,text=True,cwd=ROOT,timeout=15)
        self.assertEqual(process.returncode,0,process.stderr)
        observed=json.loads(process.stdout)
        self.assertEqual(observed['early']['pending'],1)
        self.assertFalse(observed['outcome']['passed'])
        self.assertEqual(observed['creates'],1)
        self.assertEqual(observed['deleted'],['ours'])
        self.assertTrue(observed['otherSurvived'])
        self.assertEqual(observed['final']['pending'],0)

    async def test_lost_creation_response_still_cleans_and_reports_no_private_details(self):
        class Client:
            def __init__(self,pending=0):self.calls=[];self.pending=pending
            async def call_tool(self,name,args):
                self.calls.append((name,args))
                if 'Actor.implementation.create' in args['code']:
                    raise RuntimeError('private-token campaign-name fixture body')
                return SimpleNamespace(structured_content={'value':json.dumps(dict(pending=self.pending,remaining=0))})
        for pending in (0,1):
            client=Client(pending)
            report=await HARNESS.run_character_fixture(client,'test','offline-strike')
            self.assertFalse(report['passed'])
            self.assertEqual(report['cleanup_verified'],pending==0)
            self.assertEqual(len(client.calls),2)
            self.assertIn('getFlag',client.calls[-1][1]['code'])
            self.assertNotIn('private-token',json.dumps(report))
            self.assertNotIn('campaign-name',json.dumps(report))
            self.assertEqual(report['exception_type'],'RuntimeError')

    async def test_optional_fixture_success_requires_generated_unarmed_and_cleanup(self):
        class Client:
            async def call_tool(self,name,args):
                value=dict(uuid='Actor.ours',owned_items=0) if 'Actor.implementation.create' in args['code'] else dict(pending=0,remaining=0)
                return SimpleNamespace(structured_content={'value':json.dumps(value)})
        for verified in (True,False):
            with patch.object(HARNESS,'verify',new=AsyncMock(return_value=dict(passed=True,character_generated_unarmed_verified=verified))) as verify:
                report=await HARNESS.run_character_fixture(Client(),'test','offline-strike')
            self.assertIs(report['passed'],verified)
            self.assertTrue(report['cleanup_verified'])
            verify.assert_awaited_once_with(unittest.mock.ANY,'test',character_uuid='Actor.ours')

    def test_actual_cleanup_rejects_same_marker_wrong_uuid_or_type(self):
        code=HARNESS.fixture_code(HARNESS.CHARACTER_CLEANUP,'offline-strike','Actor.expected')
        script=r"""
const [code,type]=JSON.parse(process.argv[1]);let deletes=0;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={actors:[{uuid:'Actor.other',type,getFlag:()=> 'offline-strike',async delete(){deletes++;}}],ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
let rejected=false;try{await new Function('return (async()=>{'+code+'})()')();}catch{rejected=true;}
console.log(JSON.stringify({rejected,deletes}));
"""
        for item_type in ('character','npc'):
            process=subprocess.run(['node','--input-type=module','-e',script,json.dumps([code,item_type])],capture_output=True,text=True,cwd=ROOT,timeout=15)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual(json.loads(process.stdout),dict(rejected=True,deletes=0))

    async def test_fixture_wrong_world_and_unsafe_marker_do_not_call_client(self):
        client=SimpleNamespace(call_tool=AsyncMock())
        with self.assertRaises(ValueError):
            await HARNESS.run_character_fixture(client,'campaign','safe')
        client.call_tool.assert_not_awaited()
        with self.assertRaises(ValueError):
            HARNESS.fixture_code(HARNESS.CHARACTER_CREATE,'unsafe marker')

