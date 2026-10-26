"""PF2e-specific state harness source identity versus prepared display labels."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('state_live_check', ROOT / 'scripts/actor-state-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class StateFixtureAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_fixture_flags_reject_before_credentials_or_client(self):
        for arguments in [dict(state_fixture=True), dict(world_id='test'),
                          dict(state_fixture=True, world_id='campaign'),
                          dict(state_fixture=True, world_id='test', discovery_only=True)]:
            with self.subTest(arguments=arguments), \
                 patch.object(HARNESS.Path, 'read_text', side_effect=AssertionError('Credentials prohibited')), \
                 patch.object(HARNESS, 'Client', side_effect=AssertionError('Client prohibited')):
                with self.assertRaises(ValueError):
                    await HARNESS.main(**arguments)


class StateLiveCheckTests(unittest.TestCase):
    def test_actual_fixture_setup_uses_only_marked_owner_and_unevaluated_formula(self):
        script = r"""
const code=JSON.parse(process.argv[1]),writes=[],created=[];let deleted=0;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},version:'14.369',system:{id:'pf2e',version:'8.6.1'},world:{id:'test'},time:{worldTime:1000},actors:[]};
const actor={uuid:'Actor.fixture',type:'character',items:new Map(),getFlag:()=> 'offline-state-run',async delete(){deleted++;},async createEmbeddedDocuments(type,inputs){writes.push('createOwned');return inputs.map((source,index)=>{const id='i'+this.items.size,item={id,uuid:this.uuid+'.Item.'+id,type:source.type,parent:this,source};this.items.set(id,item);created.push(item);return item;});},async updateEmbeddedDocuments(type,updates){writes.push('updateOwned');for(const update of updates){const item=this.items.get(update._id);if(!item)throw Error('Nonfixture Item update');item.source.system.start={value:update['system.start.value'],initiative:update['system.start.initiative']};}return updates;}};
globalThis.Actor={implementation:{create:async source=>{writes.push('createActor');if(source.type!=='character'||source.flags['foundry-mcp'].stateVerificationRun!=='offline-state-run')throw Error('Unsafe create');game.actors.push(actor);return actor;}}};
const chunks=await new Function('return (async()=>{'+code+'})()')();
const result=JSON.parse(chunks.join(''));
console.log(JSON.stringify({writes,deleted,count:actor.items.size,result,items:created.map(item=>({uuid:item.uuid,type:item.type,source:item.source}))}));
"""
        process = subprocess.run(['node', '--input-type=module', '-e', script,
                                  json.dumps(HARNESS.fixture_code(HARNESS.CREATE_STATE, 'offline-state-run'))],
                                 cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        observation = json.loads(process.stdout)
        self.assertEqual(observation['writes'], ['createActor', 'createOwned', 'createOwned', 'updateOwned'])
        self.assertEqual(observation['deleted'], 0)
        self.assertEqual(observation['count'], 8)
        effects = [item for item in observation['items'] if item['type'] == 'effect']
        self.assertEqual(len(effects), 3)
        self.assertEqual(effects[0]['source']['name'], effects[1]['source']['name'])
        self.assertNotEqual(effects[0]['source']['system']['context']['origin']['item'], effects[1]['source']['system']['context']['origin']['item'])
        self.assertEqual(effects[1]['source']['system']['start'], {'value': 400, 'initiative': None})
        self.assertEqual(effects[2]['source']['system']['badge'], {'type': 'formula', 'value': '1d4', 'evaluate': False, 'reevaluate': None})
        self.assertEqual(effects[2]['source']['system']['duration']['unit'], 'encounter')
        self.assertTrue(all(item['source']['system']['rules'] == [] for item in observation['items']))

    def test_actual_expiry_check_reads_public_own_data_without_serialization_or_getters(self):
        script = """
let serializations=0,getters=0;
const source={system:{duration:{unit:'unlimited'}}};
const item={documentName:'Item',type:'effect',testUserPermission:()=>true,system:{expired:false},toObject:sourceOnly=>{serializations++;if(!sourceOnly)return {system:{}};return structuredClone(source);}};
const before=JSON.stringify(source);
globalThis.game={user:{}};
globalThis.foundry={utils:{fromUuid:async()=>item}};
const claims=[{document_uuid:'Item.test',path:'/system/expired',basis:'transformed'}];
const probe=async()=>{CHECK;return result;};
const negative=await probe();item.system.expired=true;const positive=await probe();
delete item.system.expired;const missing=await probe();
Object.defineProperty(item.system,'expired',{get(){getters++;throw Error('Getter forbidden');},configurable:true});const accessor=await probe();
delete item.system.expired;Object.defineProperty(item,'system',{get(){getters++;throw Error('System getter forbidden');},configurable:true});const systemAccessor=await probe();
console.log(JSON.stringify({negative,positive,missing,accessor,systemAccessor,serializations,getters,unchanged:before===JSON.stringify(source)}));
""".replace('CHECK', HARNESS.WITNESS_CHECK)
        completed = subprocess.run(['node', '--input-type=module'], input=script, text=True, capture_output=True, cwd=ROOT, check=True)
        result = json.loads(completed.stdout)
        self.assertEqual(result['negative'], [dict(present=True,value=False)])
        self.assertEqual(result['positive'], [dict(present=True,value=True)])
        for key in ('missing','accessor','systemAccessor'):
            self.assertEqual(result[key], [dict(present=False)])
        self.assertEqual(result['serializations'],0)
        self.assertEqual(result['getters'],0)
        self.assertTrue(result['unchanged'])

    def test_actual_source_witness_still_uses_selected_source_serialization(self):
        script = """
let sourceCalls=0;
const item={documentName:'Item',testUserPermission:()=>true,toObject:source=>{if(source!==true)throw Error('Source required');sourceCalls++;return {system:{duration:{unit:'encounter'}}};}};
globalThis.game={user:{}};globalThis.foundry={utils:{fromUuid:async()=>item}};
const claims=[{document_uuid:'Item.test',path:'/system/duration/unit',basis:'source'},{document_uuid:'Item.test',path:'/system/absent',basis:'source'}];
""" + HARNESS.WITNESS_CHECK + '\nconsole.log(JSON.stringify({result,sourceCalls}));'
        completed = subprocess.run(['node', '--input-type=module'], input=script, text=True, capture_output=True, cwd=ROOT, check=True)
        result=json.loads(completed.stdout)
        self.assertEqual(result['result'], [dict(present=True,value='encounter'),dict(present=False)])
        self.assertEqual(result['sourceCalls'],2)

    def test_actual_target_check_preserves_source_identity_and_context_display(self):
        script = """
const doc={uuid:'Actor.test.Item.condition',documentName:'Item',type:'condition',name:'Frightened 2',testUserPermission:()=>true,toObject:source=>{if(source!==true)throw Error('Source required');return {name:'Frightened'};}};
globalThis.game={user:{}};
globalThis.foundry={utils:{fromUuid:async()=>doc}};
const claims=[{target_uuid:doc.uuid,type:doc.type,source_identity:true},{target_uuid:doc.uuid,type:doc.type,source_identity:false}];
""" + HARNESS.TARGET_CHECK + '\nconsole.log(JSON.stringify(result));'
        completed = subprocess.run(['node', '--input-type=module'], input=script, text=True, capture_output=True, cwd=ROOT, check=True)
        rows = json.loads(completed.stdout)
        self.assertEqual([row['name'] for row in rows], ['Frightened', 'Frightened 2'])
        self.assertTrue(all(not row['name_truncated'] for row in rows))
