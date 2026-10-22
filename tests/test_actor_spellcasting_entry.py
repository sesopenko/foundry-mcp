"""PF2e-specific8.6.1 casting entry source DTO validation; no effective casting."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _casting_entry_spec, CASTING_ENTRY_LIMIT
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def entry(path='/system/prepared/value', value='prepared', *, present=True):
    result=response(path,value,item_type='spellcastingEntry',present=present)
    row=result['records'][0];spec=_casting_entry_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.spellcasting-entry.source.v1',limitations=CASTING_ENTRY_LIMIT.copy())
    return result


class ActorSpellcastingEntryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid=result['identity']['uuid'],sections=['source'])

    async def test_exact_mode_resources_and_independent_preparations(self):
        for path,value in [('/system/prepared/value','unknown-mode'),('/system/prepared/flexible',True),('/system/prepared/validItems',None),('/system/ability/value',''),('/system/tradition/value','unknown-tradition'),('/system/proficiency/value',4),('/system/spelldc/value',0),('/system/spelldc/dc',22),('/system/autoHeightenLevel/value',None),('/system/slots/slot0/value',0),('/system/slots/slot10/max',3),('/system/slots/slot11/value',2),('/system/slots/slot3/prepared',[]),('/system/slots/slot3/prepared/0/id','same'),('/system/slots/slot3/prepared/1/id','same'),('/system/slots/slot3/prepared/0/expended',True),('/system/slots/slot3/prepared/1/expended',False),('/system/slots/slot3/prepared/2/id',None),('/system/traits/otherTags',[]),('/system/publication/remaster',True)]:
            with self.subTest(path=path): await self.read(entry(path,value))
        await self.read(entry('/system/prepared/flexible',present=False))
        await self.read(entry('/system/slots/slot1/prepared',present=False))

    async def test_forged_paths_shapes_and_provenance_rejected(self):
        for path,value in [('/system/slots/slot12/value',2),('/system/slots/slot01/value',2),('/system/slots/slot1/prepared',{}),('/system/slots/slot1/prepared',[{'id':'x','expended':False}]),('/system/slots/slot1/prepared/00/id','x'),('/system/slots/slot1/prepared/key/id','x'),('/system/slots/slot1/value/0/id','x'),('/system/slots/slot1/prepared/0/expended',0),('/system/spelldc/dc',True),('/system/proficiency/slug','arcane'),('/system/statistic',{}),('/system/slots/slot1/prepared/0/name','secret'),('/system/traits/otherTags',['secret'])]:
            with self.subTest(path=path),self.assertRaises(ToolError): await self.read(entry(path,value))
        for change in [lambda r:r['mapped'].update(concept='remaining_slots'),lambda r:r['mapped'].update(value='spontaneous'),lambda r:r['mapped'].update(unit='slots'),lambda r:r['provenance'].update(mapping='pf2e.spell.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='forged'),lambda r:r.update(kind='relationship')]:
            bad=entry();change(bad['records'][0])
            with self.assertRaises(ToolError): await self.read(bad)
        bad=entry();bad['identity']['type']='equipment'
        with self.assertRaises(ToolError): await self.read(bad)

    async def test_actual_source_selector_descriptors_cross_boundary(self):
        script=r"""
import {spellcastingEntryFields,spellcastingEntryIssues} from './foundry-module/scripts/actorSpellcastingEntry.js';
const source={type:'spellcastingEntry',system:{prepared:{value:'prepared',flexible:false,validItems:null},ability:{value:'int'},tradition:{value:'arcane'},proficiency:{value:3},spelldc:{value:12,dc:22},autoHeightenLevel:{value:null},slots:{slot0:{value:0,max:3,prepared:[]},slot1:{value:0,max:2,prepared:[{id:'same',expended:true},{id:'same',expended:false},{id:null,expended:false}]},slot2:{value:0,max:1,prepared:{0:{id:'legacy',expended:false}}},slot3:{value:0,max:1,prepared:[{id:'good',expended:false},{id:4,expended:'bad'}]}},traits:{otherTags:[]},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
console.log(JSON.stringify({fields:[...spellcastingEntryFields(source),...spellcastingEntryFields({type:'spellcastingEntry',system:{}})],issues:spellcastingEntryIssues(source)}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        payload=json.loads(process.stdout);fields=payload['fields'];self.assertGreater(len(fields),50)
        self.assertTrue(any(i['reason']=='malformed_preparations' for i in payload['issues']))
        self.assertFalse(any(f['path'].startswith('/system/slots/slot2/prepared') for f in fields if f['present']))
        for field in fields:
            with self.subTest(path=field['path']):
                result=entry(field['path'],field.get('value'),present=field['present']);row=result['records'][0]
                row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations']
                await self.read(result)

    async def test_actual_reader_continuation_legacy_partial_and_exact_prose(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const text='<p>'+('Exact 😀 é '.repeat(1600))+'</p>';
const source={name:'Entry',type:'spellcastingEntry',system:{prepared:{value:'prepared'},slots:{slot1:{value:0,max:2,prepared:[{id:'same',expended:true},{id:'same',expended:false}]},slot2:{value:0,max:1,prepared:{0:{id:'legacy',expended:false}}}},description:{value:text}}};
const item={id:'a',uuid:'Item.a',name:source.name,type:source.type,documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},actors:new Map(),items:new Map([['a',item]])};globalThis.foundry={utils:{fromUuid:async()=>item}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:item.uuid,sections:['source','description','effective'],limit:4,max_bytes:12000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);console.log(JSON.stringify({pages,text}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        payload=json.loads(process.stdout);records=[]
        self.assertGreater(len(payload['pages']),3)
        for page in payload['pages']:
            self.manager.call.return_value=page
            checked=await read_item.fn(item_uuid='Item.a',sections=['source','description','effective'],limit=4,max_bytes=12000)
            records.extend(checked['records'])
            self.assertEqual(next(s for s in checked['sections'] if s['name']=='effective')['status'],'unsupported')
        source=[r for r in records if r['section']=='source'];paths=[r['raw'][0]['path'] for r in source]
        self.assertEqual(len(paths),len(set(paths)))
        by_path={r['raw'][0]['path']:r['mapped']['value'] for r in source}
        self.assertEqual(by_path['/system/slots/slot1/value'],0)
        self.assertTrue(by_path['/system/slots/slot1/prepared/0/expended'])
        self.assertFalse(by_path['/system/slots/slot1/prepared/1/expended'])
        self.assertNotIn('/system/slots/slot2/prepared',paths)
        self.assertEqual(next(s for s in payload['pages'][-1]['sections'] if s['name']=='source')['status'],'partial')
        prose=[r for r in records if r['kind']=='text']
        self.assertGreater(len(prose),1)
        self.assertEqual(''.join(r['raw'][0]['value'] for r in prose),payload['text'])
