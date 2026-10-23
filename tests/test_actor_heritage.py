"""PF2e-specific heritage8.6.1 source and ancestry association DTO boundaries."""
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_item, _heritage_spec
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def heritage(path='/system/ancestry',value=None,*,present=True):
    result=response(path,value,item_type='heritage',present=present);row=result['records'][0]
    spec=_heritage_spec(path)
    row.update(key='source:'+path,mapped=dict(concept=spec[0] if spec else 'forged',value=value if present else None,unit=None))
    row['provenance'].update(mapping='pf2e.heritage.source.v1',limitations=['heritage_source_not_effective_character'])
    return result


def reference(path='/system/ancestry/uuid',claim='Item.ancestry',status='resolved',present=True):
    result=heritage(path,claim,present=present);result['sections'][0]['name']='relationships';row=result['records'][0]
    row.update(section='relationships',kind='relationship',key='relationships:heritage:ancestry',mapped=dict(concept='heritage_ancestry_reference',value=dict(status=status,target_uuid=None),unit=None))
    row['provenance'].update(mapping='pf2e.heritage.ancestry-reference.v1',limitations=['ancestry_association_not_owner_membership'])
    if status=='resolved':row['mapped']['value'].update(target_uuid=claim,document_name='Item',type='ancestry',name='Actual ancestry',name_truncated=False)
    return result


class ActorHeritageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=[result['sections'][0]['name']])

    async def test_association_and_source_metadata_remain_authored(self):
        for path,value in [('/system/ancestry',None),('/system/ancestry/name','Stored name'),('/system/ancestry/slug','custom'),('/system/ancestry/uuid','Item.claim'),('/system/traits/value',[]),('/system/traits/value/0','custom-trait'),('/system/traits/otherTags',[]),('/system/traits/rarity','unknown-code'),('/system/slug',None),('/system/publication/title','Book'),('/system/publication/remaster',False)]:
            with self.subTest(path=path):await self.read(heritage(path,value))
        for path in ('/system/ancestry','/system/ancestry/uuid','/system/traits/value'):
            await self.read(heritage(path,present=False))

    async def test_rejects_nonphysical_effective_arbitrary_and_forged_source(self):
        for path,value in [('/system/ancestry',{}),('/system/ancestry',{'uuid':'Item.a'}),('/system/ancestry/name',None),('/system/ancestry/uuid',1),('/system/traits/value',['human']),('/system/traits/value/00','human'),('/system/traits/value/0',None),('/system/publication/remaster',0),('/system/rules',[]),('/system/quantity',1),('/system/level/value',1),('/system/equipped/invested',True),('/flags/secret','secret')]:
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(heritage(path,value))
        for change in [lambda r:r['mapped'].update(value=True),lambda r:r['provenance'].update(mapping='pf2e.physical.source.v1'),lambda r:r['provenance'].update(limitations=[]),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r.update(key='forged')]:
            bad=heritage();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_ancestry_resolution_is_not_owner_membership(self):
        for status in ('resolved','missing','denied','unsupported','unverified'):await self.read(reference(status=status))
        await self.read(reference('/system/ancestry',None,'unassociated'))
        await self.read(reference('/system/ancestry',None,'missing',False))
        await self.read(reference(status='missing',present=False))
        for claim in ('Ancestry name','Actor.a','','Item.x#anchor'):
            await self.read(reference(claim=claim,status='unsupported'))
            with self.assertRaises(ToolError):await self.read(reference(claim=claim))
        synthetic=reference(claim='Scene.s.Token.t.Actor.a.Item.x');synthetic['records'][0]['mapped']['value']['token_uuid']='Scene.s.Token.t';await self.read(synthetic)
        for change in [lambda r:r['mapped']['value'].update(target_uuid='Item.other'),lambda r:r['mapped']['value'].update(type='feat'),lambda r:r['mapped']['value'].update(name='x'*257),lambda r:r['mapped']['value'].update(token_uuid='Scene.s.Token.t'),lambda r:r['mapped']['value'].update(owner_has_ancestry=True),lambda r:r['raw'][0].update(document_uuid='Item.other'),lambda r:r['provenance'].update(limitations=[]),lambda r:r.update(key='forged')]:
            bad=reference();change(bad['records'][0])
            with self.assertRaises(ToolError):await self.read(bad)

    async def test_unresolved_relationships_never_disclose_identity(self):
        for status in ('missing','denied','unsupported','unverified','unassociated'):
            for leak in ({'name':'Leaked'},{'document_name':'Item'},{'type':'ancestry'},{'target_uuid':'Item.ancestry'},{'token_uuid':'Scene.s.Token.t'}):
                bad=reference('/system/ancestry',None,status) if status=='unassociated' else reference(status=status)
                bad['records'][0]['mapped']['value'].update(leak)
                with self.subTest(status=status,leak=leak),self.assertRaises(ToolError):await self.read(bad)
        for path,claim,status in [('/system/ancestry',None,'empty'),('/system/ancestry',{},'missing'),('/system/ancestry/uuid',None,'missing'),('/system/ancestry/name','Stored','unverified')]:
            with self.subTest(path=path,status=status),self.assertRaises(ToolError):await self.read(reference(path,claim,status))

    async def test_non_pf2e_boundary(self):
        bad=heritage();bad['runtime']['system_id']='dnd5e'
        with self.assertRaises(ToolError):await self.read(bad)

    async def test_actual_javascript_source_descriptors(self):
        script="""
import {heritageFields} from './foundry-module/scripts/actorHeritage.js';
const source={type:'heritage',system:{ancestry:{name:'Stored',slug:'human',uuid:'Item.ancestry'},traits:{value:['human'],otherTags:[],rarity:'common'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true}}};
console.log(JSON.stringify([...heritageFields(source),...heritageFields({type:'heritage',system:{ancestry:null}}),...heritageFields({type:'heritage',system:{}})]));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        fields=json.loads(process.stdout);self.assertGreater(len(fields),20)
        for field in fields:
            with self.subTest(path=field['path']):
                result=heritage(field['path'],field.get('value'),present=field['present']);row=result['records'][0];row['mapped']['concept']=field['concept'];row['provenance']['limitations']=field['limitations'];await self.read(result)

    async def test_actual_paginated_reader_preserves_independent_association(self):
        script=r"""
import {readItem} from './foundry-module/scripts/actors.js';
const source={name:'Heritage',type:'heritage',system:{ancestry:{name:'Stored ancestry name',slug:'stored-slug',uuid:'Item.ancestry'},traits:{value:['custom-trait'],otherTags:[],rarity:'common'},slug:null,publication:{title:'Book',authors:'Author',license:'ORC',remaster:true},description:{value:'<p>Exact heritage prose</p>',gm:'heritage_private_sentinel'},quantity:99,rules:[{key:'secret'}]},flags:{secret:'heritage_private_sentinel'}};
const item={id:'a',uuid:'Item.a',name:'Heritage',type:'heritage',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
const ancestry={id:'ancestry',uuid:'Item.ancestry',name:'Actual ancestry name',type:'ancestry',documentName:'Item',parent:null,folder:null,compendium:null,testUserPermission:()=>true,toObject:()=>{throw Error('Target source must not be read')}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map(),items:new Map([['a',item],['ancestry',ancestry]])};globalThis.foundry={utils:{fromUuid:async uuid=>uuid==='Item.a'?item:uuid==='Item.ancestry'?ancestry:null}};
let cursor;const pages=[];do{const page=await readItem({item_uuid:'Item.a',sections:['source','relationships','description','effective'],limit:3,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);source.system.ancestry=null;const unassociated=await readItem({item_uuid:'Item.a',sections:['relationships'],limit:3,max_bytes:8000});console.log(JSON.stringify({pages,unassociated}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1]);self.assertEqual(process.returncode,0,process.stderr)
        from foundry_mcp_server.mcp_server.actors import _validate
        output=json.loads(process.stdout);pages=output['pages'];self.assertGreater(len(pages),1)
        _validate(output['unassociated'],'read',limit=3,max_bytes=8000,sections=['relationships'])
        self.assertEqual(output['unassociated']['records'][0]['mapped']['value'],dict(status='unassociated',target_uuid=None))
        for page in pages:
            _validate(page,'read',limit=3,max_bytes=8000,sections=['source','relationships','description','effective'])
            self.assertNotIn('heritage_private_sentinel',json.dumps(page))
        rows=[r for page in pages for r in page['records']]
        self.assertEqual(len(rows),len({r['key'] for r in rows}))
        links=[r for r in rows if r['mapped']['concept']=='heritage_ancestry_reference'];self.assertEqual(len(links),1)
        self.assertEqual(links[0]['mapped']['value']['target_uuid'],'Item.ancestry')
        self.assertEqual(links[0]['mapped']['value']['name'],'Actual ancestry name')
        self.assertEqual(next(r['mapped']['value'] for r in rows if r['mapped']['concept']=='heritage_ancestry_name'),'Stored ancestry name')
        self.assertFalse({'/system/quantity','/system/rules'}&{r['raw'][0]['path'] for r in rows})
        self.assertTrue(all(next(s for s in p['sections'] if s['name']=='effective')['status']=='unsupported' for p in pages))
