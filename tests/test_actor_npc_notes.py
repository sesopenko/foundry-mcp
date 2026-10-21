"""PF2e-specific NPC8.6.1 opt-in biography boundary and exact source text."""
import json
import subprocess
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor, NPC_NOTES, SOURCE_PATHS
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_action import response


def notes(path='/system/details/privateNotes', value='<p>GM 😀 &amp; exact</p>', present=True):
    page=response(path,value,present=present,section='description')
    page['identity'].update(document_name='Actor',uuid='Actor.a',type='npc')
    row=page['records'][0];raw=row['raw'][0];raw['document_uuid']='Actor.a'
    row.update(key='description:'+path+(':0' if present else ''),kind='text' if present else 'field',mapped=dict(concept=NPC_NOTES.get(path,'unknown'),value=None,unit=None))
    row['provenance'].update(mapping='pf2e.npc.notes.v1',contributors=[{k:raw[k] for k in ('document_uuid','path','basis')}])
    if present:
        units=len(value.encode('utf-16-le'))//2 if type(value) is str else 0
        row['text']=dict(path=path,start=0,end=units,total=units,complete=True)
    return page


class NpcNotesBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def read(self,page,sections=None):
        self.manager.call.return_value=page
        return await read_actor.fn(actor_uuid='Actor.a',sections=sections or ['description'])

    async def test_explicit_notes_exact_empty_and_absent(self):
        self.assertFalse(set(NPC_NOTES)&SOURCE_PATHS)
        for path in NPC_NOTES:
            for value,present in [('<p>GM 😀 &amp; exact</p>',True),('',True),(None,False)]:
                with self.subTest(path=path,value=value):
                    result=await self.read(notes(path,value,present))
                    raw=result['records'][0]['raw'][0]
                    self.assertEqual(raw.get('value'),value)
                    self.assertEqual(raw['present'],present)

    async def test_notes_cannot_enter_implicit_source_or_other_types(self):
        for actor_type in ('character','familiar'):
            page=notes();page['identity']['type']=actor_type
            with self.assertRaises(ToolError):await self.read(page)
        page=notes();page['sections'][0]['name']='source';page['records'][0]['section']='source'
        with self.assertRaises(ToolError):await self.read(page,['source'])
        page=notes();page['records'][0]['raw'][0]['path']='/system/details/unknown'
        with self.assertRaises(ToolError):await self.read(page)

    async def test_provenance_kind_mapping_and_fragment_contract_are_strict(self):
        for mutate in [
            lambda p:p['records'][0]['mapped'].update(value='duplicated note'),
            lambda p:p['records'][0].update(key='description:/system/details/privateNotes:01'),
            lambda p:p['records'][0]['raw'][0].update(path='/name'),
            lambda p:p['records'][0]['mapped'].update(concept='creature_publicNotes_source'),
            lambda p:p['records'][0]['provenance'].update(mapping='pf2e.npc.source.v1'),
            lambda p:p['records'][0]['provenance']['contributors'][0].update(document_uuid='Actor.other'),
            lambda p:p['records'][0]['raw'][0].update(document_uuid='Actor.other'),
            lambda p:p['records'][0].update(kind='field'),
            lambda p:p['records'][0]['text'].update(end=1),
            lambda p:p['records'][0]['raw'][0].update(value=None),
        ]:
            page=notes();mutate(page)
            with self.assertRaises(ToolError):await self.read(page)
        page=notes(present=False);page['records'][0]['key']='source:/system/details/privateNotes'
        with self.assertRaises(ToolError):await self.read(page)

    async def test_other_actor_descriptions_are_explicitly_unsupported(self):
        for actor_type in ('character','familiar'):
            page=notes();page['identity']['type']=actor_type;page['records']=[]
            page['pagination']['returned']=0
            page['sections'][0].update(status='unsupported',reasons=['actor_description_pending'])
            self.assertEqual((await self.read(page))['records'],[])

    async def test_actual_node_notes_dtos_round_trip(self):
        script=r"""
import {readActor} from './foundry-module/scripts/actors.js';
const text='<p>Secret 😀 &amp; exact</p>'.repeat(700);
const source={name:'NPC',type:'npc',system:{details:{blurb:'',privateNotes:text}}};
const actor={id:'a',uuid:'Actor.a',name:'NPC',type:'npc',documentName:'Actor',folder:null,compendium:null,items:new Map(),testUserPermission:()=>true,toObject:()=>structuredClone(source)};
globalThis.game={version:'14.369',system:{id:'pf2e',version:'8.6.1'},ready:true,user:{isGM:true},items:new Map(),actors:new Map([['a',actor]])};globalThis.foundry={utils:{fromUuid:async()=>actor}};
const pages=[];let cursor=null;do {const page=await readActor({actor_uuid:'Actor.a',sections:['description'],limit:3,max_bytes:8000,...(cursor?{cursor}:{})});pages.push(page);cursor=page.pagination.next_cursor;}while(cursor);
console.log(JSON.stringify({pages,text}));
"""
        process=subprocess.run(['node','--input-type=module'],input=script,text=True,capture_output=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(process.returncode,0,process.stderr)
        fixture=json.loads(process.stdout);records=[]
        for page in fixture['pages']:records.extend((await self.read(page))['records'])
        private=[row['raw'][0]['value'] for row in records if row['raw'][0]['path']=='/system/details/privateNotes']
        self.assertEqual(''.join(private),fixture['text'])
        absent=next(row for row in records if row['raw'][0]['path']=='/system/details/publicNotes')
        self.assertFalse(absent['raw'][0]['present'])
