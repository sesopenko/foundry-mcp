"""Test admission/restoration safety before executing the GM setting verifier."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('guidance_probe', ROOT / 'scripts/writing-guidance-live-check.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class GuidanceFixtureTests(unittest.TestCase):
    def test_wrong_world_rejects_all_probe_operations_before_imports_or_settings(self):
        scripts = [probe.code(body, 'a' * 32) for body in (probe.SETUP, probe.OPEN, probe.SAVE_UI, probe.EMPTY, probe.HEAVY, probe.CLEANUP)]
        source = """
const scripts=JSON.parse(process.argv[1]);
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},world:{id:'gaming'},version:'14.369'};
for(const script of scripts){
 try{await new (Object.getPrototypeOf(async function(){}).constructor)(script)();throw Error('Accepted');}
 catch(error){if(error.message!=='Wrong development runtime')throw error;}
}
"""
        subprocess.run(['node', '--input-type=module', '-e', source, json.dumps(scripts)], check=True, capture_output=True)

    def test_restoration_refuses_unrelated_gm_changes(self):
        script = probe.code(probe.CLEANUP, 'a' * 32).replace("await import('/modules/foundry-mcp/scripts/writingGuidance.js')", '{}')
        source = """
import assert from 'node:assert/strict';
globalThis.location={origin:'http://localhost:30000'};
const original={html:null,saved_at:null},other={html:'GM changed this',saved_at:'new'};
let writes=0;
globalThis.game={ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',settings:{get:()=>other,set:()=>{writes++;}}};
globalThis.__mcpGuidanceProbes=new Map([['a'.repeat(32),{original,last:{html:'probe',saved_at:'old'},closed:false,pending:0}]]);
await assert.rejects(new (Object.getPrototypeOf(async function(){}).constructor)(JSON.parse(process.argv[1]))(),/restoration refused/);
assert.equal(writes,0);
"""
        subprocess.run(['node', '--input-type=module', '-e', source, json.dumps(script)], check=True, capture_output=True)

    def test_invalid_markers_are_rejected(self):
        for marker in ['', None, 'text', 'a' * 33]:
            with self.assertRaises(ValueError):
                probe.code(probe.SETUP, marker)

    def test_restoration_keeps_exact_original_and_allows_only_owned_empty_or_marked_copy(self):
        script = probe.code(probe.CLEANUP, 'a' * 32).replace("await import('/modules/foundry-mcp/scripts/writingGuidance.js')", '{}')
        source = """
import assert from 'node:assert/strict';
globalThis.location={origin:'http://localhost:30000'};
const original={html:'Original GM rules',saved_at:'original-time'};
for(const copy of [{html:'a'.repeat(32),saved_at:'probe-time'},{html:'',saved_at:'empty-time'}]){
 let current=structuredClone(copy),closed=0;
 globalThis.game={ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',settings:{get:()=>current,set:async(ns,key,value)=>{assert.equal(ns,'foundry-mcp');assert.equal(key,'writingGuidance');current=value;}}};
 globalThis.__mcpGuidanceProbes=new Map([['a'.repeat(32),{original,last:copy,closed:false,pending:0,dialog:{close:async()=>{closed++;}}}]]);
 const result=JSON.parse(await new (Object.getPrototypeOf(async function(){}).constructor)(JSON.parse(process.argv[1]))());
 assert.deepEqual(result,{restored:true,pending:0});assert.deepEqual(current,original);assert.equal(closed,1);
}
"""
        subprocess.run(['node', '--input-type=module', '-e', source, json.dumps(script)], check=True, capture_output=True)
