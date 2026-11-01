"""Actual typed MCP discovery/invocation for the combined writing guide."""
from html import unescape
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager


class WritingGuidanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)
        self.saved = {'world_id': 'test', 'html': '<p>Do not edit Official Adventure without my permission.</p>', 'saved_at': '2026-10-31T20:00:00.001Z'}
        self.manager.call.return_value = self.saved

    async def test_discovery_and_unchanged_timestamp_contract(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            tools = {t.name: t for t in await client.list_tools()}
            self.assertTrue('get_writing_guidance' in tools)
            self.assertFalse('get_pathfinder_writing_style_guide' in tools)
            tool = tools['get_writing_guidance']
            self.assertFalse(tool.input_schema['additionalProperties'])
            self.assertIsNotNone(tool.output_schema)
            self.assertIn('critically important', tool.description)
            self.assertIn('since', tool.description)
            first = (await client.call_tool('get_writing_guidance', {})).structured_content
            self.assertTrue(first['changed']); self.assertEqual(first['gm_status'], 'configured')
            self.assertEqual(first['gm_guidance']['html'], self.saved['html'])
            self.assertEqual(first['timestamp']['saved_at'], self.saved['saved_at'])
            self.assertIn('Throughout this rulebook', first['pathfinder_guidance']['html'])
            original = '\n'.join((Path(__file__).resolve().parents[1] / 'docs' / name).read_text() for name in ('feature-wishlist.md', 'feature-wishlist-finished.md'))
            expected = original.split('## WISH-007', 1)[1].split('```text\n', 1)[1].split('\n```', 1)[0]
            paragraphs = first['pathfinder_guidance']['html'].splitlines()
            self.assertEqual(unescape('\n\n'.join(p[3:-4] for p in paragraphs)), expected)
            self.assertEqual(first['pathfinder_guidance']['attribution_status'], 'user_supplied_publication_unverified')
            second = (await client.call_tool('get_writing_guidance', {'since': first['timestamp']})).structured_content
            self.assertFalse(second['changed'])
            self.assertNotIn('gm_guidance', second); self.assertNotIn('pathfinder_guidance', second)
            self.manager.call.assert_awaited_with('gm', 'getWritingGuidance', {}, timeout=15.0)

    async def test_changes_in_html_timestamp_style_or_world_never_return_unchanged(self):
        from foundry_mcp_server.mcp_server import writing
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            original = (await client.call_tool('get_writing_guidance', {})).structured_content
            for field, value in [('html', '<p>Changed</p>'), ('saved_at', '2026-10-31T20:00:00.002Z'), ('world_id', 'other')]:
                self.manager.call.return_value = {**self.saved, field: value}
                result = (await client.call_tool('get_writing_guidance', {'since': original['timestamp']})).structured_content
                self.assertTrue(result['changed'], field)
            self.manager.call.return_value = self.saved
            with patch.object(writing, 'STYLE_GUIDE', writing.STYLE_GUIDE + '\n\nUpdated style.'):
                result = (await client.call_tool('get_writing_guidance', {'since': original['timestamp']})).structured_content
                self.assertTrue(result['changed'])

    async def test_unconfigured_empty_and_unavailable_guidance_are_distinct(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for data, status in [({'world_id': 'test', 'html': None, 'saved_at': None}, 'not_configured'), ({**self.saved, 'html': ''}, 'empty')]:
                self.manager.call.return_value = data
                result = (await client.call_tool('get_writing_guidance', {})).structured_content
                self.assertEqual(result['gm_status'], status)
                self.assertEqual(result['gm_guidance']['html'], data['html'])
            self.manager.call.side_effect = ConnectionError()
            result = await client.call_tool('get_writing_guidance', {}, raise_on_error=False)
            self.assertTrue(result.is_error); self.assertIn('BridgeUnavailable', str(result.content))

    async def test_invalid_inputs_and_malformed_saved_source_fail_closed(self):
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            for args in [{'extra': True}, {'since': 'timestamp'}, {'since': {'saved_at': None}}, {'max_bytes': True}, {'max_bytes': 48001}]:
                self.assertTrue((await client.call_tool('get_writing_guidance', args, raise_on_error=False)).is_error)
            self.manager.call.assert_not_awaited()
            for change in [{'html': None}, {'saved_at': 'not-a-date'}, {'secret': 'must not escape'}, {'html': '😀' * 3001}]:
                self.manager.call.return_value = {**self.saved, **change}
                result = await client.call_tool('get_writing_guidance', {}, raise_on_error=False)
                self.assertTrue(result.is_error)
                self.assertIn('InvalidFoundryResponse', str(result.content))

    async def test_large_guide_requires_explicit_byte_budget_and_never_truncates(self):
        self.manager.call.return_value = {**self.saved, 'html': '<p>' + '😀' * 2800 + '</p>'}
        async with Client(mcp, timeout=5, init_timeout=5) as client:
            result = await client.call_tool('get_writing_guidance', {}, raise_on_error=False)
            self.assertTrue(result.is_error); self.assertIn('ResponseTooLarge', str(result.content))
            full = (await client.call_tool('get_writing_guidance', {'max_bytes': 48000})).structured_content
            self.assertEqual(full['gm_guidance']['html'], self.manager.call.return_value['html'])
