"""PF2e-specific8.6.1 disabled affliction boundary, not schema-only support."""
import json
import subprocess
import unittest
from pathlib import Path
from foundry_mcp_server.mcp_server.actors import read_item


class ActorAfflictionTests(unittest.TestCase):
    def test_published_reader_names_unsupported_runtime_and_recovery(self):
        description=read_item.description
        for phrase in ['Affliction Items are explicitly unsupported','PF2e8.6.1','UnsupportedType','get_actor_types']:
            self.assertIn(phrase,description)

    def test_actual_browser_rejects_affliction_without_reading_source(self):
        script=r"""
import {readItem,getActorTypes} from './foundry-module/scripts/actors.js';
let sourceReads=0;
const item={id:'a',uuid:'Item.a',name:'Affliction',type:'affliction',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{sourceReads++;throw new Error('source must not be read');}};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([[item.uuid,item]])};
globalThis.foundry={utils:{fromUuid:async uuid=>uuid===item.uuid?item:null}};
let error=null;try{await readItem({item_uuid:'Item.a',sections:['source']});}catch(e){error=e.rpcError;}
console.log(JSON.stringify({error,sourceReads,registry:await getActorTypes()}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        result=json.loads(process.stdout)
        self.assertEqual(result['sourceReads'],0)
        self.assertEqual(result['error']['code'],'UnsupportedType')
        entry=next(row for row in result['registry']['item_types'] if row['type']=='affliction')
        self.assertFalse(entry['source_supported']);self.assertFalse(entry['mapped_supported']);self.assertFalse(entry['effective_supported'])
        self.assertEqual(entry['verification']['live']['status'],'not_run')
