"""PF2e-specific combined Actor reader pages cross the actual Python boundary.

Uses the shared deterministic character/NPC/familiar fixture and production
JavaScript readActor. These mocks prove composition, not live Foundry support.
"""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.actors import read_actor
from foundry_mcp_server.mcp_server.tools import register_foundry_manager


ROOT = Path(__file__).resolve().parents[1]
RUNNER = r"""
import {integratedPages} from './tests/js/fixtures/actor-integrated.js';
const cases=[];
for(const type of ['character','npc','familiar']){
 const result=await integratedPages(type,'world');
 cases.push({type,context:'world',pages:result.pages,selector:result.selector,actor_uuid:result.actor_uuid,master_uuid:result.master_uuid,item_uuids:result.item_uuids});
}
console.log(JSON.stringify(cases));
"""


class IntegratedActorTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        completed=subprocess.run(['node','--input-type=module'],input=RUNNER,text=True,capture_output=True,cwd=ROOT,check=True,timeout=60)
        cls.cases=json.loads(completed.stdout)

    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)

    async def verify_case(self,case):
        pages=case['pages'];self.assertGreater(len(pages),1)
        sections=[section['name'] for section in pages[0]['sections']]
        self.assertTrue({'identity','source','statistics','skills','strikes','abilities','spellcasting','inventory','state'}<=set(sections))
        records=[];cursor=None;seen=set();revision=pages[0]['revision']
        for page in pages:
            self.assertEqual(page['identity']['uuid'],case['actor_uuid'])
            self.assertEqual(page['identity']['type'],case['type'])
            self.assertEqual(page['revision'],revision)
            self.assertEqual([section['name'] for section in page['sections']],sections)
            self.assertLessEqual(len(page['records']),7)
            self.assertLessEqual(len(json.dumps(page,ensure_ascii=False,separators=(',',':')).encode('utf-8')),48000)
            arguments={**case['selector'],'sections':sections,'limit':7,'max_bytes':48000}
            if cursor:arguments['cursor']=cursor
            self.manager.call.return_value=page
            accepted=await read_actor.fn(**arguments)
            self.assertEqual(accepted,page)
            forwarded=self.manager.call.await_args.args
            self.assertEqual(forwarded[:2],('gm','readActor'))
            self.assertEqual(forwarded[2]['cursor'],cursor)
            self.assertEqual(forwarded[2]['sections'],sections)
            self.assertEqual(forwarded[2]['max_bytes'],48000)
            records.extend(accepted['records'])
            cursor=accepted['pagination']['next_cursor']
            if cursor:
                self.assertNotIn(cursor,seen);seen.add(cursor)
        self.assertIsNone(cursor)
        self.assertEqual(len({row['key'] for row in records}),len(records))
        expected_mapping={'character':'pf2e.character.ability-reference.v1','npc':'pf2e.npc.item-reference.v1','familiar':'pf2e.familiar.current.v1'}[case['type']]
        self.assertIn(expected_mapping,{row['provenance']['mapping'] for row in records})
        self.assertEqual(len([row for row in records if row['key']=='state:capability:affliction']),1)
        self.assertEqual(self.manager.call.await_count,len(pages))
        allowed={case['actor_uuid'],*case['item_uuids'].values()}
        for row in records:
            self.assertIn(row['section'],sections)
            self.assertEqual(row['provenance']['contributors'],[{key:raw[key] for key in ('document_uuid','path','basis')} for raw in row['raw']])
            for raw in row['raw']:
                self.assertIn(raw['document_uuid'],allowed)
                self.assertIn(raw['basis'],('source','transformed'))
        self.assertTrue(any(raw['basis']=='source' for row in records for raw in row['raw']))
        self.assertTrue(any(raw['basis']=='transformed' for row in records for raw in row['raw']))
        state=next(section for section in pages[-1]['sections'] if section['name']=='state')
        self.assertEqual(state['status'],'partial')
        self.assertIn('affliction_reading_unsupported',state['reasons'])

    async def test_character_combined_sections(self):
        await self.verify_case(next(case for case in self.cases if case['type']=='character'))

    async def test_npc_combined_sections(self):
        await self.verify_case(next(case for case in self.cases if case['type']=='npc'))

    async def test_familiar_combined_sections(self):
        await self.verify_case(next(case for case in self.cases if case['type']=='familiar'))

    async def test_combined_page_cannot_hide_foreign_current_provenance(self):
        case=next(case for case in self.cases if case['type']=='character')
        page=copy.deepcopy(next(page for page in case['pages'] if any(raw['basis']=='transformed' for row in page['records'] for raw in row['raw'])))
        row=next(row for row in page['records'] if any(raw['basis']=='transformed' for raw in row['raw']))
        row['raw'][0]['document_uuid']='Actor.foreign'
        row['provenance']['contributors']=[{key:raw[key] for key in ('document_uuid','path','basis')} for raw in row['raw']]
        self.manager.call.return_value=page
        with self.assertRaises(ToolError):
            await read_actor.fn(**case['selector'],sections=[section['name'] for section in page['sections']],limit=7,max_bytes=48000)
