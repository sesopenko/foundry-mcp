"""Actual JS packets through typed MCP discovery, invocation and validation."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.server import mcp

SCRIPT = """
import {fixture} from './tests/js/helpers/compendiumFixture.js';
import * as C from './foundry-module/scripts/compendiumJournals.js';
const f=fixture(),pack_id=f.pack.collection,page_uuid=f.entries[0].pages.contents[0].uuid;
f.entries[0].pages.contents[1].documentName='JournalEntryPage';
const cases=[['list_compendiums','listCompendiums',{}],
['search_compendium_journals','searchCompendiumJournals',{pack_id,query:'DCs by Level',max_entries:1}],
['search_compendium_journals','searchCompendiumJournals',{pack_id,query:'20',field:'text',select:{excerpts:true},max_entries:1}],
['get_compendium_journal_contents','getCompendiumJournalContents',{pack_id,journal_id:f.entries[0].id,select:{headings:true,categories:true,presentation:true}}],
['read_compendium_journal_page','readCompendiumJournalPage',{pack_id,page_uuid}],
['read_compendium_journal_page','readCompendiumJournalPage',{pack_id,page_uuid,select:{references:true,source_metadata:true}}],
['resolve_compendium_journal_reference','resolveCompendiumJournalReference',{pack_id,page_uuid,target:'.p1'}]];
const rows=[];for(const [tool,method,args]of cases)rows.push({tool,method,args,result:await C[method](args)});
console.log(JSON.stringify(rows));
"""


class CompendiumTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run(['node', '--input-type=module'], input=SCRIPT, text=True, capture_output=True,
                             cwd=Path(__file__).resolve().parents[1], check=True)
        cls.cases = json.loads(run.stdout)

    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_actual_browser_packets_at_mcp_boundary(self):
        async with Client(mcp) as client:
            for case in self.cases:
                with self.subTest(tool=case['tool'], args=case['args']):
                    self.manager.call.return_value = case['result']
                    response = await client.call_tool(case['tool'], case['args'])
                    self.assertEqual(response.structured_content, case['result'])
                    self.assertEqual(self.manager.call.call_args.args[1], case['method'])

    async def test_discovery_is_typed_bounded_and_read_only(self):
        async with Client(mcp) as client:
            catalog = {t.name: t for t in await client.list_tools()}
        for name in {c['tool'] for c in self.cases}:
            tool = catalog[name]
            self.assertFalse(tool.input_schema['additionalProperties'])
            self.assertIsNotNone(tool.output_schema)
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertFalse(tool.annotations.destructive_hint)
            self.assertIn('No imports', tool.description)
        self.assertEqual(catalog['search_compendium_journals'].input_schema['properties']['field']['default'], 'page_name')
        self.assertEqual(catalog['read_compendium_journal_page'].input_schema['properties']['max_chars']['default'], 2000)

    async def test_invalid_requests_rejected_before_rpc(self):
        async with Client(mcp) as client:
            for name, args in [('list_compendiums', {'update': {}}),
                               ('search_compendium_journals', {'pack_id': 'x', 'query': ' '}),
                               ('search_compendium_journals', {'pack_id': 'x', 'query': 'x', 'max_entries': 11}),
                               ('search_compendium_journals', {'pack_id': 'x', 'query': 'x', 'limit': True}),
                               ('search_compendium_journals', {'pack_id': 'x', 'query': 'x', 'select': {'body': True}}),
                               ('get_compendium_journal_contents', {'pack_id': 'x', 'journal_id': 'j', 'page_id': 'p', 'categories_only': True}),
                               ('read_compendium_journal_page', {'pack_id': 'x', 'page_uuid': 'p', 'max_bytes': 7999})]:
                with self.subTest(name=name, args=args):
                    self.assertTrue((await client.call_tool(name, args, raise_on_error=False)).is_error)
        self.manager.call.assert_not_awaited()

    async def test_malformed_responses_rejected(self):
        case = self.cases[4]
        async with Client(mcp) as client:
            for mutate in [lambda r: r.update(unexpected='leak'),
                           lambda r: r.update(page_uuid='wrong'),
                           lambda r: r['pack'].update(id='wrong'),
                           lambda r: r.update(end_offset=99999),
                           lambda r: r.update(content='x'*9000)]:
                result = copy.deepcopy(case['result']); mutate(result)
                self.manager.call.return_value = result
                self.assertTrue((await client.call_tool(case['tool'], case['args'], raise_on_error=False)).is_error)

    async def test_response_validation_is_enforced_by_tool(self):
        tool = await mcp.get_tool('list_compendiums')
        clone = tool.model_copy(update={'handler': AsyncMock(return_value={'nodes': 'invalid'})})
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError):
            await clone.run({})

    async def test_cross_pack_search_and_unrequested_data_rejected(self):
        case = self.cases[1]
        async with Client(mcp) as client:
            for mutate in [lambda r: r['matches'][0].update(page_uuid='Compendium.other.rules.JournalEntry.j.JournalEntryPage.p'),
                           lambda r: r['matches'][0].update(excerpt='unrequested'),
                           lambda r: r.update(searched_field='text'),
                           lambda r: r.update(complete=True)]:
                result = copy.deepcopy(case['result']); mutate(result)
                self.manager.call.return_value = result
                self.assertTrue((await client.call_tool(case['tool'], case['args'], raise_on_error=False)).is_error)
            reference = self.cases[-1]
            result = copy.deepcopy(reference['result']); result['next_call']['tool'] = 'send_chat_message'
            self.manager.call.return_value = result
            self.assertTrue((await client.call_tool(reference['tool'], reference['args'], raise_on_error=False)).is_error)
