"""Image discovery contracts through actual MCP invocation and discovery."""
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager


class JournalImageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)
        self.image = dict(kind='image', name='α image.png', name_truncated=False,
            image=dict(source='data', directory='assets', src='assets/α image.png'))
        self.result = dict(location=dict(source='data', directory='assets'), sources=[dict(source='data'), dict(source='public')],
            revision='opaque', entries=[self.image], total=1, unfiltered_total=1, complete=True, next_cursor=None, limitations=['One directory.'])
        self.manager.call.return_value = self.result

    async def test_discovery_and_exact_image_selector(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            tool = next(tool for tool in await client.list_tools() if tool.name == 'browse_journal_images')
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertIsNotNone(tool.output_schema)
            self.assertFalse(tool.input_schema['additionalProperties'])
            self.assertIn('complete native directory', tool.description)
            result = (await client.call_tool(tool.name, dict(directory='assets'))).structured_content
            self.assertEqual(result, self.result)
            self.assertEqual(self.manager.call.await_args.args[:2], ('gm', 'browseJournalImages'))
            self.assertEqual(self.manager.call.await_args.args[2]['limit'], 10)

    async def test_invalid_requests_do_not_browse(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for request in [dict(directory='../private'), dict(directory='%2e%2e/private'), dict(directory='/etc'),
                    dict(source='s3'), dict(bucket='irrelevant'), dict(extra=True), dict(limit=True), dict(directory='assets/*')]:
                result = await client.call_tool('browse_journal_images', request, raise_on_error=False)
                self.assertTrue(result.is_error, request)
            self.manager.call.assert_not_awaited()

    async def test_malformed_image_context_and_continuations_fail_closed(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for change in [dict(complete=False), dict(total=2), dict(sources=[]),
                    dict(entries=[{**self.image, 'image': {**self.image['image'], 'source': 'public'}}]),
                    dict(entries=[{**self.image, 'image': {**self.image['image'], 'src': 'javascript:fake.png'}}]),
                    dict(entries=[self.image, self.image], total=2, unfiltered_total=2)]:
                self.manager.call.return_value = {**self.result, **change}
                result = await client.call_tool('browse_journal_images', dict(directory='assets'), raise_on_error=False)
                self.assertTrue(result.is_error)
                self.assertIn('InvalidFoundryResponse', str(result.content))

    async def test_directory_followups_and_complete_pagination(self):
        directory = dict(kind='directory', name='sub folder', name_truncated=False, directory='assets/sub folder',
            next_call=dict(tool='browse_journal_images', arguments=dict(source='data', directory='assets/sub folder')))
        first = {**self.result, 'entries': [directory], 'total': 2, 'unfiltered_total': 2, 'complete': False, 'next_cursor': dict(offset=1, revision='opaque')}
        second = {**self.result, 'total': 2, 'unfiltered_total': 2}
        self.manager.call.side_effect = [first, second]
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            page = (await client.call_tool('browse_journal_images', dict(directory='assets', limit=1))).structured_content
            final = (await client.call_tool('browse_journal_images', dict(directory='assets', limit=1, cursor=page['next_cursor']))).structured_content
            self.assertTrue(final['complete'])
            self.assertEqual(page['entries'][0]['next_call'], directory['next_call'])
            self.assertEqual(final['entries'][0]['image']['src'], 'assets/α image.png')
