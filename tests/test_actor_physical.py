"""PF2e physical source trust boundary and actual browser DTO integration."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError

from foundry_mcp_server.mcp_server.actors import read_item
from foundry_mcp_server.mcp_server.tools import register_foundry_manager


def response(path, value=None, *, present=True, item_type='weapon', section='source'):
    raw=dict(document_uuid='Item.i',path=path,present=present,basis='source')
    if present:raw['value']=value
    contributor={key:raw[key] for key in ('document_uuid','path','basis')}
    record=dict(key='source.field',section=section,kind='field',raw=[raw],mapped=dict(concept='selected_source',value=value if present else None,unit=None),provenance=dict(contributors=[contributor],mapping='pf2e.physical.source.v1',limitations=['source_only_no_effective_calculation']))
    return dict(contract_version=1,runtime=dict(core_version='14.369',system_id='pf2e',system_version='8.6.1'),identity=dict(document_name='Item',id='i',uuid='Item.i',name='Example',type=item_type,source_kind='world',folder=None,pack=None,actor=None,instance=None),revision='revision',sections=[dict(name='identity',status='complete',reasons=[]),dict(name=section,status='partial',reasons=['type_reader_pending'])],records=[record],pagination=dict(complete=True,next_cursor=None,returned=1),limitations=[])


class ActorPhysicalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def test_null_zero_absent_and_unknown_codes_are_distinct(self):
        cases=[('/system/quantity',0,True),('/system/equipped/invested',None,True),('/system/price/per',None,False),('/system/material/grade','custom-grade',True)]
        for path,value,present in cases:
            self.manager.call.return_value=response(path,value,present=present)
            result=await read_item.fn(item_uuid='Item.i')
            raw=result['records'][0]['raw'][0]
            self.assertEqual(raw['present'],present)
            if present:self.assertEqual(raw['value'],value)
            else:self.assertNotIn('value',raw)

    async def test_serialized_attachments_have_source_identity_only(self):
        for path,value in [('/system/subitems',[]),('/system/subitems/0/_id','attachment-local'),('/system/subitems/0/name','Attachment'),('/system/subitems/0/type','weapon')]:
            self.manager.call.return_value=response(path,value)
            result=await read_item.fn(item_uuid='Item.i')
            self.assertEqual(result['records'][0]['raw'][0]['document_uuid'],'Item.i')
        for path,value in [('/system/subitems',[{'name':'Nested object'}]),('/system/subitems',None),('/system/quantity',[]),('/system/subitems/0/system/rules',[]),('/system/subitems/0/flags',{}),('/system/subitems/00/name','Noncanonical index')]:
            self.manager.call.return_value=response(path,value)
            with self.subTest(path=path),self.assertRaises(ToolError):await read_item.fn(item_uuid='Item.i')

    async def test_nested_mapped_payload_and_fabricated_attachment_documents_rejected(self):
        for change in ('mapped', 'document'):
            result=response('/system/subitems/0/name','Attachment')
            if change=='mapped':result['records'][0]['mapped']['value']={'flags':{'secret':'never'}}
            else:result['records'][0]['raw'][0]['document_uuid']='Item.fake-attachment'
            self.manager.call.return_value=result
            with self.subTest(change=change),self.assertRaises(ToolError):await read_item.fn(item_uuid='Item.i')

    async def test_physical_paths_cannot_leak_from_other_types_or_override_absences(self):
        for item_type,path in [('spell','/system/quantity'),('kit','/system/price/per'),('armor','/system/usage/value'),('shield','/system/usage/value'),('treasure','/system/equipped/invested'),('treasure','/system/equipped/handsHeld'),('consumable','/system/subitems/0/name')]:
            self.manager.call.return_value=response(path,1,item_type=item_type)
            with self.subTest(item_type=item_type,path=path),self.assertRaises(ToolError):await read_item.fn(item_uuid='Item.i')
        for path in ['/flags/private','/system/rules','/system/_migration','/system/identification/unidentified/data/description/gm']:
            self.manager.call.return_value=response(path,'secret')
            with self.subTest(path=path),self.assertRaises(ToolError):await read_item.fn(item_uuid='Item.i')

    async def test_unidentified_description_requires_explicit_description_section(self):
        path='/system/identification/unidentified/data/description/value'
        self.manager.call.return_value=response(path,'<p>Unidentified</p>')
        with self.assertRaises(ToolError):await read_item.fn(item_uuid='Item.i')
        valid=response(path,'<p>Unidentified</p>',section='description')
        valid['records'][0].update(kind='text',text=dict(path=path,start=0,end=19,total=19,complete=True))
        self.manager.call.return_value=valid
        self.assertEqual((await read_item.fn(item_uuid='Item.i',sections=['identity','description']))['records'][0]['raw'][0]['value'],'<p>Unidentified</p>')

    async def test_actual_browser_physical_source_and_long_alternate_description(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const alternate='<p>Unknown 😀 &amp;</p>'.repeat(900);
const source={name:'Stack',type:'weapon',system:{quantity:0,price:{value:{gp:2},per:10},equipped:{invested:null},material:{grade:'custom-grade'},subitems:[{_id:'local',name:'Attached',type:'weapon',flags:{private:'never'}}],identification:{status:'unidentified',unidentified:{name:'Unknown',data:{description:{value:alternate,gm:'never'}}}},description:{value:'<p>Identified</p>',gm:'never'}},flags:{private:'never'}};
const item={id:'i',uuid:'Item.i',name:source.name,type:source.type,documentName:'Item',folder:null,parent:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([['i',item]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.i'?item:null}};
const sourcePages=[];let cursor;
do {const page=await readItem({item_uuid:'Item.i',sections:['identity','source'],limit:20,max_bytes:8000,...(cursor?{cursor}:{})});sourcePages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
const textPages=[];
do {const page=await readItem({item_uuid:'Item.i',sections:['description'],limit:2,max_bytes:8000,...(cursor?{cursor}:{})});textPages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
console.log(JSON.stringify({sourcePages,textPages,alternate}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fixture=json.loads(process.stdout)
        source_records=[]
        for page in fixture['sourcePages']:
            self.manager.call.return_value=page
            validated=await read_item.fn(item_uuid='Item.i',limit=20,max_bytes=8000)
            source_records.extend(validated['records'])
            self.assertNotIn('never',json.dumps(validated))
            self.assertNotIn(fixture['alternate'],json.dumps(validated))
        fields={record['raw'][0]['path']:record['raw'][0] for record in source_records}
        self.assertEqual(fields['/system/quantity']['value'],0)
        self.assertIsNone(fields['/system/equipped/invested']['value'])
        self.assertFalse(fields['/system/hardness']['present'])
        self.assertEqual(fields['/system/price/per']['value'],10)
        self.assertNotIn('/system/identification/unidentified/data/description/value',fields)
        fragments=[]
        for page in fixture['textPages']:
            self.manager.call.return_value=page
            validated=await read_item.fn(item_uuid='Item.i',sections=['description'],limit=2,max_bytes=8000)
            fragments.extend(record['raw'][0]['value'] for record in validated['records'] if record['raw'][0]['path']=='/system/identification/unidentified/data/description/value')
        self.assertEqual(''.join(fragments),fixture['alternate'])
