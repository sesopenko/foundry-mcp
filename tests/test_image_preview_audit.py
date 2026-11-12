"""The baseline is instrumented, bounded and content-free, not agent arithmetic."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from fastmcp.client.client import CallToolResult

from foundry_mcp_server.image_preview_audit import MAX_CALLS, Measurements, measure, size


class AuditTests(unittest.TestCase):
    def test_compact_utf8_and_exact_totals_without_private_payloads(self):
        meter = Measurements()
        first = dict(content='α private https://private.example/image-previews/secret.png', complete=False, next_cursor='private-cursor')
        final = dict(content='private', complete=True, next_cursor=None)
        self.assertEqual(size({'α': 'β'}), len('{"α":"β"}'.encode()))
        for data in (first, final):
            meter.reserve()
            meter.add('journal_page_complete', data, dict(structuredContent=data))
        self.assertEqual(meter.calls, 2)
        row = meter.rows['journal_page_complete']
        self.assertEqual(row['json_bytes'], size(first) + size(final))
        self.assertEqual(row['mcp_bytes'], size(dict(structuredContent=first)) + size(dict(structuredContent=final)))
        self.assertTrue(row['complete'])
        self.assertNotIn('private', json.dumps(meter.rows))
        meter.add('journal_page_complete', None, {'error': 'secret signed URL'}, error=True)
        self.assertFalse(row['complete'])
        self.assertEqual(row['errors'], 1)
        self.assertNotIn('secret', json.dumps(meter.rows))

    def test_call_budget_is_enforced_before_dispatch(self):
        meter = Measurements()
        for _ in range(MAX_CALLS):
            meter.reserve()
        with self.assertRaisesRegex(RuntimeError, 'CallBudgetExceeded'):
            meter.reserve()
        self.assertEqual(meter.calls, MAX_CALLS)


class AuditAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_sdk_call_result_is_measured_without_pydantic_assumption(self):
        client = AsyncMock()
        client.list_tools.return_value = []
        client.call_tool.side_effect = [
            CallToolResult(content=[], structured_content={'value': '{"version":"14.369"}'}, meta=None, data=None, is_error=False),
            RuntimeError('stop before browsing'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            report = await measure(client, Path(folder) / 'selection.json')
        self.assertEqual(report.get('foundry_version'), '14.369')
        self.assertEqual(report['rows']['runtime_guard']['calls'], 1)
        self.assertEqual(report['calls'], 3)

    async def test_native_failure_text_is_never_reported(self):
        client = AsyncMock()
        client.list_tools.side_effect = RuntimeError('credential https://secret.example/path?signature=value')
        with tempfile.TemporaryDirectory() as folder:
            report = await measure(client, Path(folder) / 'selection.json')
        self.assertFalse(report['passed'])
        self.assertEqual(report['calls'], 1)
        self.assertEqual(report['failure_type'], 'RuntimeError')
        self.assertNotIn('secret', json.dumps(report))
        client.call_tool.assert_not_awaited()
