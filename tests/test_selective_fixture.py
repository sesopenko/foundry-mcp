"""Verify new fixture writes remain gated by the existing runtime/marker guard."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('selective_fixture',ROOT/'scripts/selective-fixture-check.py')
harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)


class FixtureSafety(unittest.TestCase):
    def test_wrong_world_and_wrong_marker_never_mutate(self):
        code=harness.fixture.code(harness.POPULATE,'safe-marker','Actor.fixture')
        js=r"""
const code=JSON.parse(process.argv[1]), AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
for(const wrong of ['world','marker']){
 let writes=0;
 const actor={uuid:'Actor.fixture',type:'character',getFlag:()=>wrong==='marker'?'unrelated':'safe-marker',createEmbeddedDocuments:()=>{writes++;}};
 globalThis.location={origin:'http://localhost:30000'};
 globalThis.game={ready:true,user:{isGM:true},world:{id:wrong==='world'?'gaming':'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'},actors:[actor]};
 try{await new AsyncFunction(code)();throw Error('Accepted invalid scope');}catch(e){if(e.message==='Accepted invalid scope'||writes)throw e;}
}
"""
        subprocess.run(['node','--input-type=module','-e',js,json.dumps(code)],cwd=ROOT,check=True,capture_output=True)
