"""PF2e-specific8.6.1 familiar serialization after source master admission."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_familiar import familiar


SCRIPT=r"""
import {familiarCurrentFields} from './foundry-module/scripts/actorFamiliarCurrent.js';
const trace={value:7,totalModifier:8,breakdown:'Explanation'};
const current={type:'familiar',system:{attributes:{ac:{value:17,breakdown:'AC',details:''},hp:{value:3,max:10,temp:0}},saves:{fortitude:{...trace},reflex:{...trace},will:{...trace}},perception:{...trace,vision:true},movement:{speeds:{land:{value:25,base:25,type:'land',source:null},travel:{value:25,base:25,type:'travel',source:null},burrow:null,climb:null,fly:null,swim:null}},skills:{'A/B~ skill':{slug:'ordinary',label:'Ordinary',...trace,dc:18,lore:false,itemId:null},SECRET_LINK:{lore:true,itemId:'secret'}}}};
console.log(JSON.stringify(familiarCurrentFields(current)));
"""


def javascript(script):
    result=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
    if result.returncode:raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def master(status='resolved',claim='m',present=True):
    page=familiar('/system/master/id',claim,present);row=page['records'][0]
    row['raw'].append(dict(document_uuid='Actor.a',path='/system/master/ability',present=True,value='cha',basis='source'))
    value=dict(status=status,target_uuid=None)
    if status=='resolved':value.update(target_uuid='Actor.m',document_name='Actor',type='character',name='Master',name_truncated=False,next_call=dict(tool='read_actor',arguments=dict(actor_uuid='Actor.m')))
    row.update(key='statistics:familiar_master',section='statistics',kind='relationship',mapped=dict(concept='familiar_master',value=value,unit=None))
    row['provenance']=dict(contributors=[{k:r[k] for k in ('document_uuid','path','basis')} for r in row['raw']],mapping='pf2e.familiar.master.v1',limitations=['stored_master_reference_not_current_statistics'])
    return row


class FamiliarCurrentTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        selected=javascript(SCRIPT);cls.reasons=selected['reasons'];cls.rows=[]
        for field in selected['fields']:
            raw=dict(document_uuid='Actor.a',path=field['path'],present=field['present'],basis='transformed')
            if field['present']:raw['value']=field['value']
            cls.rows.append(dict(key='statistics:'+field['path'],section='statistics',kind='field',raw=[raw],mapped=dict(concept=field['concept'],value=field.get('value') if field['path']!='/system/skills' else None,unit=None),provenance=dict(contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}],mapping='pf2e.familiar.current.v1',limitations=field['limitations'])))

    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    def page(self,rows=None,reasons=None):
        page=familiar('/system/master/id','m');page['records']=copy.deepcopy([master(),*self.rows] if rows is None else rows)
        page['sections']=[dict(name='statistics',status='partial',reasons=self.reasons.copy() if reasons is None else reasons)]
        page['pagination']['returned']=len(page['records']);return page

    async def read(self,page,**selectors):
        self.manager.call.return_value=page
        return await read_actor.fn(sections=[s['name'] for s in page['sections']],limit=100,**(selectors or dict(actor_uuid='Actor.a')))

    async def test_actual_helper_primitives_and_ordinary_skill_boundaries(self):
        page=self.page();await self.read(page)
        self.assertNotIn('SECRET',json.dumps(page))
        self.assertTrue(any(r['raw'][0]['path']=='/system/skills/A~1B~0 skill/totalModifier' for r in self.rows))
        self.assertFalse(any('/abilities/' in r['key'] or '/attack' in r['key'] or '/rank' in r['key'] for r in self.rows))
        # The admitted master record can be on a different page.
        await self.read(self.page(self.rows[:1]))

    async def test_unresolved_master_never_permits_transformed_rows(self):
        for status,claim,present in [('missing','m',True),('missing',None,False),('unassociated',None,True),('denied','m',True),('unsupported','m',True),('unverified','m',True)]:
            row=master(status,claim,present);reasons=['familiar_master_'+status]
            await self.read(self.page([row],reasons))
            with self.subTest(status=status),self.assertRaises(ToolError):await self.read(self.page([row,self.rows[0]],reasons))
            with self.assertRaises(ToolError):await self.read(self.page([row],['other_statistics_pending']))

    async def test_closed_fields_provenance_primitive_types_and_master_context(self):
        original=self.rows[0]
        changes=[lambda r:r['raw'][0].update(value=True),lambda r:r['raw'][0].update(value=float('inf')),lambda r:r['raw'][0].update(document_uuid='Actor.other'),lambda r:r['raw'][0].update(basis='source'),lambda r:r['mapped'].update(value=False),lambda r:r['provenance'].update(mapping='pf2e.actor.current.v1'),lambda r:r['provenance'].update(limitations=[])]
        for change in changes:
            row=copy.deepcopy(original);change(row)
            with self.subTest(row=row),self.assertRaises(ToolError):await self.read(self.page([row]))
        for path in ('/system/abilities/str/mod','/system/attack/value','/system/resources/focus/value','/system/perception/rank','/system/skills/ordinary/lore','/system/skills/ordinary/rank','/system/skills//value','/system/skills/a~2b/value','/system/skills/'+'x'*257+'/value'):
            row=copy.deepcopy(original);row['key']='statistics:'+path;row['raw'][0]['path']=path;row['provenance']['contributors'][0]['path']=path
            with self.subTest(path=path),self.assertRaises(ToolError):await self.read(self.page([row]))
        for ability in (True,4,{}):
            row=master();row['raw'][1]['value']=ability
            with self.assertRaises(ToolError):await self.read(self.page([row]))
        row=master();row['raw'].pop();row['provenance']['contributors'].pop()
        with self.assertRaises(ToolError):await self.read(self.page([row]))

    async def test_same_page_source_master_and_movement_contradictions_rejected(self):
        stats=master();identity=dict(copy.deepcopy(stats),section='identity',key='identity:familiar_master');identity['raw']=identity['raw'][:1];identity['provenance']['contributors']=identity['provenance']['contributors'][:1]
        page=self.page([stats,identity]);page['sections'].insert(0,dict(name='identity',status='complete',reasons=[]));await self.read(page)
        identity=page['records'][1];identity['raw'][0]['value']='other'
        identity['mapped']['value'].update(target_uuid='Actor.other',next_call=dict(tool='read_actor',arguments=dict(actor_uuid='Actor.other')))
        with self.assertRaises(ToolError):await self.read(page)
        marker=copy.deepcopy(next(r for r in self.rows if r['key']=='statistics:/system/movement/speeds/fly'))
        leaf=copy.deepcopy(self.rows[0]);path='/system/movement/speeds/fly/value';leaf['key']='statistics:'+path;leaf['raw'][0]['path']=path;leaf['provenance']['contributors'][0]['path']=path;leaf['mapped']['concept']='current_fly_speed'
        with self.assertRaises(ToolError):await self.read(self.page([marker,leaf]))

    async def test_actual_paginated_reader_and_unavailable_master_serializer_guards(self):
        script=SCRIPT.replace('console.log(JSON.stringify(familiarCurrentFields(current)));','')+r"""
import {readActor} from './foundry-module/scripts/actors.js';
let transformed=0;
const source={type:'familiar',name:'Familiar',system:{master:{id:'m',ability:'cha'},attributes:{hp:{value:3,temp:0}}}};
const actor={documentName:'Actor',uuid:'Actor.a',id:'a',name:'Familiar',type:'familiar',parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject(flag){if(!flag){transformed++;return structuredClone(current);}return structuredClone(source);}};
const master={documentName:'Actor',uuid:'Actor.m',id:'m',name:'Master',type:'character',parent:null,folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject(){throw Error('Do not expand master source');}};
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors:new Map([['a',actor],['m',master]]),items:new Map()};globalThis.foundry={utils:{fromUuid:async uuid=>uuid===actor.uuid?actor:uuid===master.uuid?master:null}};
const defaults=await readActor({actor_uuid:actor.uuid});if(transformed!==0)throw Error('Default serialized current');
const pages=[];let cursor;do{const page=await readActor({actor_uuid:actor.uuid,sections:['statistics'],limit:5,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
const missing=[];
for(const mode of ['deleted','unassociated','denied','unsupported','unverified']){
 source.system.master.id='m';master.type='character';master.uuid='Actor.m';master.parent=null;master.testUserPermission=()=>true;game.actors.set('m',master);
 if(mode==='deleted')game.actors.delete('m');if(mode==='unassociated')source.system.master.id=null;if(mode==='denied')master.testUserPermission=()=>false;if(mode==='unsupported')master.type='npc';if(mode==='unverified')master.parent={};
 const before=transformed,page=await readActor({actor_uuid:actor.uuid,sections:['statistics']});if(transformed!==before)throw Error('Unavailable master serialized familiar');missing.push({mode,page});
}
console.log(JSON.stringify({defaults,pages,missing}));
"""
        result=javascript(script);self.assertGreater(len(result['pages']),1)
        rows=[]
        for page in result['pages']:rows.extend((await self.read(page))['records'])
        self.assertEqual(len([r for r in rows if r['key']=='statistics:familiar_master']),1)
        self.assertTrue(any(r['provenance']['mapping']=='pf2e.familiar.current.v1' for r in rows))
        self.assertNotIn('SECRET',json.dumps(rows))
        for entry in result['missing']:
            page=entry['page'];await self.read(page)
            self.assertEqual(len(page['records']),1)
            self.assertEqual(page['records'][0]['provenance']['mapping'],'pf2e.familiar.master.v1')
            self.assertTrue(page['sections'][0]['reasons'][0].startswith('familiar_master_'))

    async def test_token_owner_context_and_missing_collection_are_exact(self):
        page=self.page([master(),self.rows[0]]);prefix='Scene.s.Token.t.Actor.a'
        page['identity'].update(uuid=prefix,source_kind='token',instance=dict(scene_uuid='Scene.s',scene_name='Scene',token_uuid='Scene.s.Token.t',token_name='Token',actor_link=False,base_actor=dict(uuid='Actor.a',name='Base')))
        for row in page['records']:
            for raw in row['raw']:raw['document_uuid']=prefix
            row['provenance']['contributors']=[{k:r[k] for k in ('document_uuid','path','basis')} for r in row['raw']]
        await self.read(page,token_uuid='Scene.s.Token.t')
        page['records'][1]['raw'][0]['document_uuid']='Actor.a'
        with self.assertRaises(ToolError):await self.read(page,token_uuid='Scene.s.Token.t')
        row=copy.deepcopy(self.rows[0]);path='/system/skills';row['key']='statistics:'+path
        row['raw'][0].update(path=path,value={});row['provenance']['contributors'][0]['path']=path;row['mapped']=dict(concept='current_skill_collection',value=None,unit=None)
        await self.read(self.page([row]))
        row['raw'][0].update(present=False);row['raw'][0].pop('value')
        with self.assertRaises(ToolError):await self.read(self.page([row]))
        await self.read(self.page([row],['other_statistics_pending','current_fields_unavailable']))
