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
