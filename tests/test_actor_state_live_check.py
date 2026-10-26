"""PF2e-specific state harness source identity versus prepared display labels."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('state_live_check', ROOT / 'scripts/actor-state-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class StateLiveCheckTests(unittest.TestCase):
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
