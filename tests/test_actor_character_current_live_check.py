"""Offline safety/orchestration for the same-client character current fixture."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch


ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('character_current_live',ROOT/'scripts/actor-character-current-live-check.py')
HARNESS=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(HARNESS)


def response(value):return SimpleNamespace(structured_content={'value':json.dumps(value)})


class Client:
    def __init__(self,failure=None):self.failure=failure;self.calls=[];self.cleanup=False;self.fingerprints=0
    async def call_tool(self,name,args):
        self.calls.append((name,args))
        if name=='execute_javascript':
            code=args['code']
            if 'const matches=' in code:
                self.cleanup=True;return response(dict(pending=1 if self.failure=='pending' else 0,remaining=0))
            if 'Actor.implementation.create' in code:
                if self.failure=='lost_creation':raise RuntimeError('private lost creation response')
                return response(dict(uuid='Actor.fixture'))
            if 'const claims=' in code:
                claims=json.loads(code.split('const claims=',1)[1].split(';',1)[0]);return response(dict(checks=[self.failure!='witness']*len(claims)))
            self.fingerprints+=1;return response(dict(source='source',current='changed' if self.failure=='fingerprint' and self.fingerprints>1 else 'current'))
        rows=[]
        for path,value,mapping in [('/system/attributes/ac/value',20,'pf2e.actor.current.v1'),('/system/details/languages/value/0','common','pf2e.actor.creature-current.v1'),('/system/attributes/immunities',[],'pf2e.actor.creature-current.v1')]:
            raw=dict(document_uuid='Actor.fixture',path=path,present=True,value=value,basis='transformed')
            rows.append(dict(key='statistics:'+path,raw=[raw],provenance=dict(mapping=mapping,contributors=[{key:raw[key] for key in ('document_uuid','path','basis')}])) )
        if self.failure=='missing_language':rows=rows[:1]+rows[2:]
        return SimpleNamespace(structured_content=dict(identity=dict(uuid='Actor.fixture',type='character'),revision='one',sections=[dict(name='statistics',status='partial',reasons=['other_statistics_pending'])],records=rows,pagination=dict(next_cursor=None)))


class CharacterCurrentHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_client_skills_then_independent_statistics_and_cleanup(self):
        client=Client();skills=AsyncMock(return_value=dict(passed=True,character_checked=True,actor_types=['character','npc'],requested_calls=4,completed_calls=4))
        with patch.object(HARNESS,'skills_verify',skills):result=await HARNESS.verify(client,'test','run')
        self.assertTrue(result['passed']);self.assertTrue(client.cleanup);self.assertTrue(result['cleanup_verified'])
        skills.assert_awaited_once_with(client,'test','Actor.fixture')
        self.assertEqual((result['core_records_checked'],result['supplement_records_checked']),(1,2))
        self.assertEqual(result['requested_calls'],len(client.calls)+4)
        create=client.calls[0][1]['code'];self.assertIn("value:['common']",create);self.assertIn('proficient:{value:1}',create);self.assertIn('rules:[]',create)

    async def test_failures_cleanup_without_secret_or_false_success(self):
        for failure in ('lost_creation','pending','witness','fingerprint','missing_language'):
            client=Client(failure)
            with patch.object(HARNESS,'skills_verify',AsyncMock(return_value=dict(passed=True,character_checked=True,actor_types=['character','npc']))):result=await HARNESS.verify(client,'test','run')
            self.assertFalse(result['passed']);self.assertTrue(client.cleanup);self.assertNotIn('private',json.dumps(result))

    async def test_wrong_world_and_marker_do_not_create(self):
        client=Client()
        with self.assertRaises(ValueError):await HARNESS.verify(client,'campaign','run')
        self.assertFalse(client.calls)
        with self.assertRaises(ValueError):HARNESS.code(HARNESS.CREATE,'invalid;marker')

    def test_actual_node_late_create_self_cleanup_after_probe_closure(self):
        script=r"""
const code=JSON.parse(process.argv[1]);const actors=[];let release,started;const begun=new Promise(r=>started=r),gate=new Promise(r=>release=r);let deleted=0;
globalThis.location={origin:'http://localhost:30000'};globalThis.game={ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'},actors:{filter:fn=>actors.filter(fn)}};
globalThis.Actor={implementation:{create:async input=>{started();await gate;const actor={type:input.type,uuid:'Actor.fixture',getFlag:()=>input.flags['foundry-mcp'].characterCurrentProbe,delete:async()=>{deleted++;actors.splice(actors.indexOf(actor),1);},createEmbeddedDocuments:()=>{throw Error('Closed probe must not add Items');}};actors.push(actor);return actor;}}};
const execute=body=>new Function('return (async()=>{'+body+'})()')();
const pending=execute(code).then(()=>false,()=>true);await begun;globalThis.__mcpCharacterCurrentProbes.get('run').closed=true;release();const rejected=await pending;console.log(JSON.stringify({rejected,deleted,remaining:actors.length,pending:globalThis.__mcpCharacterCurrentProbes.get('run').pending}));
"""
        completed=subprocess.run(['node','--input-type=module','-e',script,json.dumps(HARNESS.code(HARNESS.CREATE,'run'))],text=True,capture_output=True,cwd=ROOT,check=True)
        self.assertEqual(json.loads(completed.stdout),dict(rejected=True,deleted=1,remaining=0,pending=0))

    def test_actual_node_cleanup_rejects_other_uuid_or_type(self):
        script=r"""
const [code,type]=JSON.parse(process.argv[1]);let deleted=0;const actor={type,uuid:'Actor.other',getFlag:()=> 'run',delete:async()=>deleted++};
globalThis.location={origin:'http://localhost:30000'};globalThis.game={ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'},actors:{filter:fn=>[actor].filter(fn)}};
let rejected=false;try{await new Function('return (async()=>{'+code+'})()')();}catch{rejected=true;}console.log(JSON.stringify({rejected,deleted}));
"""
        for typ in ('character','npc'):
            completed=subprocess.run(['node','--input-type=module','-e',script,json.dumps([HARNESS.code(HARNESS.CLEANUP,'run','Actor.fixture'),typ])],text=True,capture_output=True,cwd=ROOT,check=True)
            self.assertEqual(json.loads(completed.stdout),dict(rejected=True,deleted=0))

    def test_actual_independent_check_rejects_nested_getters_without_invocation(self):
        script=r"""
const body=JSON.parse(process.argv[1]);let reads=0;const custom={};Object.defineProperty(custom,'label',{enumerable:true,get(){reads++;throw Error('Getter invoked');}});
const actor={uuid:'Actor.fixture',toObject:flag=>{if(flag!==false)throw Error('Wrong basis');return {system:{attributes:{immunities:[custom]}}};}};
const claims=[{document_uuid:actor.uuid,path:'/system/attributes/immunities',basis:'transformed',present:true,value:[]}];
let rejected=false;try{new Function('actor','claims',body+';return result;')(actor,claims);}catch{rejected=true;}console.log(JSON.stringify({rejected,reads}));
"""
        completed=subprocess.run(['node','--input-type=module','-e',script,json.dumps(HARNESS.CHECK)],text=True,capture_output=True,cwd=ROOT,check=True)
        self.assertEqual(json.loads(completed.stdout),dict(rejected=True,reads=0))
