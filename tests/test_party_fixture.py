"""Fixture guard tests run offline before any live party verifier."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('party_fixture', ROOT / 'scripts/party-live-check.py')
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class PartyFixtureTests(unittest.TestCase):
    def test_wrong_world_cannot_create_or_clean_up(self):
        scripts = [harness.code(body, 'a' * 32) for body in (harness.CREATE, harness.CLEANUP, harness.CHANGE)]
        js = r"""
const scripts=JSON.parse(process.argv[1]);
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},world:{id:'gaming'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
for(const script of scripts){
 try{await new AsyncFunction(script)();throw Error('Accepted');}
 catch(error){if(error.message!=='Wrong development runtime')throw error;}
}
"""
        subprocess.run(['node', '--input-type=module', '-e', js, json.dumps(scripts)], cwd=ROOT, check=True, capture_output=True)

    def test_cleanup_only_exact_marker_and_party_before_characters(self):
        script = harness.code(harness.CLEANUP, 'a' * 32, 'Actor.party')
        js = r"""
import assert from 'node:assert/strict';
const script=JSON.parse(process.argv[1]),deleted=[];
const actor=(id,type,marker)=>({uuid:'Actor.'+id,type,getFlag:()=>marker,delete:async()=>{deleted.push(id);game.actors=game.actors.filter(a=>a.uuid!=='Actor.'+id);}});
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'},
 actors:[actor('first','character','a'.repeat(32)),actor('existing','character','unrelated'),actor('party','party','a'.repeat(32))]};
const result=JSON.parse(await new (Object.getPrototypeOf(async function(){}).constructor)(script)());
assert.deepEqual(deleted,['party','first']);assert.deepEqual(result,{pending:0,remaining:0});
assert.equal(game.actors[0].uuid,'Actor.existing');
"""
        subprocess.run(['node', '--input-type=module', '-e', js, json.dumps(script)], cwd=ROOT, check=True, capture_output=True)

    def test_invalid_marker_rejected(self):
        for marker in ['', 'arbitrary', 'a' * 33, None]:
            with self.assertRaises(ValueError):
                harness.code(harness.CREATE, marker)
