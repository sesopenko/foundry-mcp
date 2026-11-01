"""Journal edit-context identity and schema checks through actual MCP calls."""
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.writing import GuidanceSource, guidance_revision


class JournalAuthoringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)
        self.context = dict(identity=dict(kind='page', uuid='JournalEntry.entry.JournalEntryPage.page',
            page_uuid='JournalEntry.entry.JournalEntryPage.page', page_id='page', journal_id='entry',
            name='Notes', name_truncated=False, type='text'), revision='opaque-change-marker', sort=0,
            ownership_default=dict(present=True, value=-1),
            read_next_call=dict(tool='read_journal_page', arguments=dict(page_uuid='JournalEntry.entry.JournalEntryPage.page')))
        self.manager.call.return_value = self.context
        self.request = dict(target=dict(kind='page', page_uuid='JournalEntry.entry.JournalEntryPage.page'))

    async def test_discovery_and_canonical_context(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            tool = next(t for t in await client.list_tools() if t.name == 'get_journal_write_context')
            self.assertFalse(tool.input_schema['additionalProperties'])
            self.assertIsNotNone(tool.output_schema)
            self.assertIn('get_writing_guidance', tool.description)
            result = (await client.call_tool(tool.name, self.request)).structured_content
            self.assertEqual(result, self.context)
            self.manager.call.assert_awaited_with('gm', 'getJournalWriteContext', {**self.request, 'max_bytes': 8000}, timeout=15.0)

    async def test_invalid_selectors_rejected_before_reads(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for request in [dict(target=dict(kind='page', page_uuid='Compendium.pack.id')), dict(target=dict(kind='folder', folder_id='bad.id')),
                    {**self.request, 'extra': True}, {**self.request, 'max_bytes': True}]:
                result = await client.call_tool('get_journal_write_context', request, raise_on_error=False)
                self.assertTrue(result.is_error)
            self.manager.call.assert_not_awaited()

    async def test_wrong_identity_followup_and_ownership_fail_closed(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            variants = [dict(identity={**self.context['identity'], 'journal_id': 'other'}),
                dict(read_next_call=dict(tool='read_journal_page', arguments=dict(page_uuid='JournalEntry.other.JournalEntryPage.page'))),
                dict(ownership_default=dict(present=False, value=0)), dict(ownership_default=None), dict(revision=None)]
            for variant in variants:
                self.manager.call.return_value = {**self.context, **variant}
                result = await client.call_tool('get_journal_write_context', self.request, raise_on_error=False)
                self.assertTrue(result.is_error, variant)
                self.assertIn('InvalidFoundryResponse', str(result.content))


class JournalWriteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)
        self.source = GuidanceSource(world_id='test', html='<p>Protect Official.</p>', saved_at='2026-10-31T20:00:00.001Z')
        self.request = dict(request_id='journal-write-00001', gm_authorized=True,
            guidance_timestamp=dict(saved_at=self.source.saved_at, revision=guidance_revision(self.source)),
            action=dict(operation='create_page', journal_id='entry', parent_revision='observed', name='Notes', content='<p>Hello</p>'))
        self.receipt = dict(request_id=self.request['request_id'], status='created',
            identity=dict(kind='page', uuid='JournalEntry.entry.JournalEntryPage.page',
                page_uuid='JournalEntry.entry.JournalEntryPage.page', page_id='page', journal_id='entry',
                name='Notes', name_truncated=False, type='text'), revision='after',
            read_next_call=dict(tool='read_journal_page', arguments=dict(page_uuid='JournalEntry.entry.JournalEntryPage.page')))
        self.manager.call.side_effect = [self.source.model_dump(), self.receipt]

    async def test_actual_mcp_write_schema_and_forwarding(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            tool = next(t for t in await client.list_tools() if t.name == 'write_journal')
            self.assertFalse(tool.annotations.read_only_hint)
            self.assertIn('get_writing_guidance', tool.description)
            self.assertNotIn('expected_guidance', tool.input_schema['properties'])
            self.assertIsNotNone(tool.output_schema)
            result = (await client.call_tool(tool.name, self.request)).structured_content
            self.assertEqual(result, self.receipt)
            args = self.manager.call.await_args_list[-1]
            self.assertEqual(args.args[:2], ('gm', 'writeJournal'))
            params = args.args[2]
            self.assertEqual(params['action'], self.request['action'])
            self.assertEqual(params['expected_guidance'], self.source.model_dump())
            self.assertEqual(len(params['request_digest']), 64)
            self.assertNotIn('guidance_timestamp', params)

    async def test_invalid_operations_rejected_without_reading_or_writing(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            variants = [dict(gm_authorized=False), dict(expected_guidance=self.source.model_dump()),
                dict(action=dict(operation='update_journal', journal_id='entry', expected_revision='before')),
                dict(action={**self.request['action'], 'type': 'image'}),
                dict(action={**self.request['action'], 'content': '😀' * 4001}),
                dict(action=dict(operation='create_folder', name=' ', color='#254c84')),
                dict(action=dict(operation='create_journal', name='Notes', folder_id='folder')),
                dict(action=dict(operation='update_page', page_uuid='JournalEntry.entry.JournalEntryPage.page', expected_revision='x', content=None))]
            for variant in variants:
                result = await client.call_tool('write_journal', {**self.request, **variant}, raise_on_error=False)
                self.assertTrue(result.is_error, variant)
            self.manager.call.assert_not_awaited()

    async def test_changed_guidance_prevents_write(self):
        self.manager.call.side_effect = None
        self.manager.call.return_value = {**self.source.model_dump(), 'html': '<p>New instruction</p>'}
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            result = await client.call_tool('write_journal', self.request, raise_on_error=False)
            self.assertTrue(result.is_error)
            self.assertIn('GuidanceChanged', str(result.content))
            self.assertEqual(self.manager.call.await_count, 1)

    async def test_write_timeout_warns_of_possible_completion(self):
        self.manager.call.side_effect = [self.source.model_dump(), TimeoutError()]
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            result = await client.call_tool('write_journal', self.request, raise_on_error=False)
            self.assertTrue(result.is_error)
            self.assertIn('WriteOutcomeUnknown', str(result.content))
            self.assertIn('identical request_id', str(result.content))

    async def test_receipt_must_match_operation_target_and_request(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for bad in [dict(request_id='wrong'), dict(status='updated'),
                    dict(identity={**self.receipt['identity'], 'journal_id': 'other'}), dict(revision=None)]:
                self.manager.call.side_effect = [self.source.model_dump(), {**self.receipt, **bad}]
                result = await client.call_tool('write_journal', self.request, raise_on_error=False)
                self.assertTrue(result.is_error)
                self.assertIn('InvalidFoundryResponse', str(result.content))

    async def test_format_schema_rejects_conflicting_or_unbounded_sizes_before_rpc(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for format in [dict(font_size='custom'), dict(font_size='normal', custom_size_pt=12),
                    dict(font_size='custom', custom_size_pt=201), dict(font_color='red'), dict(font_family=None)]:
                result = await client.call_tool('write_journal', {**self.request, 'action': {**self.request['action'], 'format': format}}, raise_on_error=False)
                self.assertTrue(result.is_error)
            self.manager.call.assert_not_awaited()


class AuthoringOptionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_actual_mcp_discovery_and_complete_player_pagination(self):
        pages = [dict(kind='players', world_id='test', revision='r', entries=[dict(user_id='p1', name='One')], total=2, complete=False, next_cursor=dict(offset=1, revision='r')),
            dict(kind='players', world_id='test', revision='r', entries=[dict(user_id='p2', name='Two')], total=2, complete=True, next_cursor=None)]
        self.manager.call.side_effect = pages
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            tool = next(t for t in await client.list_tools() if t.name == 'get_journal_authoring_options')
            self.assertIsNotNone(tool.output_schema)
            first = (await client.call_tool(tool.name, dict(kind='players', limit=1))).structured_content
            second = (await client.call_tool(tool.name, dict(kind='players', limit=1, cursor=first['next_cursor']))).structured_content
            self.assertEqual(first, pages[0]); self.assertEqual(second, pages[1])
            self.assertEqual(self.manager.call.await_args.args[2]['cursor'], first['next_cursor'])

    async def test_malformed_or_mismatched_pages_are_rejected(self):
        base = dict(kind='players', world_id='test', revision='r', entries=[], total=0, complete=True, next_cursor=None)
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for change in [dict(kind='fonts'), dict(total=1), dict(entries=[dict(font_family='Arial')], total=1), dict(complete=False)]:
                self.manager.call.return_value = {**base, **change}
                result = await client.call_tool('get_journal_authoring_options', dict(kind='players'), raise_on_error=False)
                self.assertTrue(result.is_error)
                self.assertIn('InvalidFoundryResponse', str(result.content))


class JournalOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)
        self.identity = dict(kind='journal', uuid='JournalEntry.entry', journal_id='entry', name='Handout', name_truncated=False, folder_id='folder')
        self.scope = dict(target=dict(kind='journal', journal_id='entry'), user_ids=['player'])
        self.preview = dict(target=self.identity, revision='ownership-scope', count=1, recursive=False,
            entries=[dict(identity=self.identity, ownership_default=dict(present=True, value=0),
                players=[dict(user_id='player', present=False, can_observe=False, parent_can_observe=None)])], limitations=['Not an inherited folder ACL.'])

    async def test_actual_mcp_ownership_preview_and_write(self):
        source = GuidanceSource(world_id='test', html=None, saved_at=None)
        receipt = dict(request_id='ownership-write-0001', status='complete', count=1, entries=[dict(identity=self.identity, status='updated')])
        self.manager.call.side_effect = [self.preview, source.model_dump(), receipt]
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            tools = {t.name: t for t in await client.list_tools()}
            self.assertIsNotNone(tools['get_journal_ownership_context'].output_schema)
            preview = (await client.call_tool('get_journal_ownership_context', self.scope)).structured_content
            self.assertEqual(preview, self.preview)
            result = (await client.call_tool('write_journal', dict(request_id='ownership-write-0001', gm_authorized=True,
                guidance_timestamp=dict(saved_at=None, revision=guidance_revision(source)),
                action=dict(operation='set_ownership', **self.scope, expected_revision=preview['revision'], all_players='none',
                    players=[dict(user_id='player', level='observer')])))).structured_content
            self.assertEqual(result, receipt)
            self.assertEqual(self.manager.call.await_args.args[2]['action']['players'], [dict(user_id='player', level='observer')])

    async def test_bad_ownership_requests_fail_before_rpc(self):
        source = GuidanceSource(world_id='test', html=None, saved_at=None)
        base = dict(request_id='ownership-write-0001', gm_authorized=True, guidance_timestamp=dict(saved_at=None, revision=guidance_revision(source)))
        action = dict(operation='set_ownership', **self.scope, expected_revision='r')
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for change in [dict(all_players='inherit'), dict(all_players='no_change'), dict(players=[dict(user_id='player', level='delete')]),
                    dict(players=[dict(user_id='player', level='none')] * 2), dict(all_players='observer', recursive=True)]:
                result = await client.call_tool('write_journal', {**base, 'action': {**action, **change}}, raise_on_error=False)
                self.assertTrue(result.is_error)
            self.manager.call.assert_not_awaited()

    async def test_preview_rejects_wrong_users_targets_and_ownership_presence(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for change in [dict(count=2), dict(entries=[]), dict(entries=[{**self.preview['entries'][0], 'players': []}]),
                    dict(entries=[{**self.preview['entries'][0], 'ownership_default': dict(present=True, value=None)}])]:
                self.manager.call.return_value = {**self.preview, **change}
                result = await client.call_tool('get_journal_ownership_context', self.scope, raise_on_error=False)
                self.assertTrue(result.is_error)
                self.assertIn('InvalidFoundryResponse', str(result.content))
