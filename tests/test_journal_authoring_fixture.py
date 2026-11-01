"""Admission and exact-marker deletion checks for the live journal verifier."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('journal_probe', ROOT / 'scripts/journal-authoring-live-check.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class JournalFixtureTests(unittest.TestCase):
    def run_node(self, source, script):
        subprocess.run(['node', '--input-type=module', '-e', source, json.dumps(script)], check=True, capture_output=True, timeout=5)

    def test_wrong_world_blocks_every_operation_before_document_reads(self):
        source = """
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},world:{id:'gaming'},version:'14.369'};
for(const script of JSON.parse(process.argv[1])){
 try{await new (Object.getPrototypeOf(async function(){}).constructor)(script)();throw Error('Accepted');}
 catch(error){if(error.message!=='Wrong development runtime')throw error;}
}
"""
        self.run_node(source, [probe.code(body, 'a' * 32) for body in (probe.FINGERPRINT, probe.VERIFY, probe.CLEANUP)])

    def test_cleanup_refuses_unmarked_documents_inside_fixture(self):
        source = """
import assert from 'node:assert/strict';
globalThis.location={origin:'http://localhost:30000'};let deletes=0;
const folder={id:'marked',name:'a'.repeat(32),getFlag:()=>({['journal-'+ 'a'.repeat(32)+'-1']:'receipt'}),delete:()=>{deletes++;}};
const journal={name:'Existing',folder,getFlag:()=>undefined,delete:()=>{deletes++;}};
globalThis.game={ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',folders:new Map([['marked',folder]]),journal:new Map([['existing',journal]])};
await assert.rejects(new (Object.getPrototypeOf(async function(){}).constructor)(JSON.parse(process.argv[1]))(),/Unmarked journal/);
assert.equal(deletes,0);
"""
        self.run_node(source, probe.code(probe.CLEANUP, 'a' * 32))

    def test_invalid_marker_is_rejected(self):
        for marker in (None, '', 'unknown', 'a' * 33):
            with self.assertRaises(ValueError):
                probe.code(probe.CLEANUP, marker)
