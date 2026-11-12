"""Read-only runtime harness only emits fixed summaries, never source payloads."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
import json

spec = importlib.util.spec_from_file_location('preview_source_probe', Path(__file__).resolve().parents[1] / 'scripts/image-preview-sources-live-check.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class SourceProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_output_and_honest_partial_failure(self):
        client = AsyncMock()
        data = {'version': '14.369', 'secret': 'signed URL', 'rows': {
            'canonical': {'passed': True, 'secret': 'native path'},
            'bare': {'passed': False, 'error_code': 'BrowseFailed'},
            'absolute': {'passed': True}}}
        client.call_tool.return_value = SimpleNamespace(structured_content={'value': json.dumps(data)})
        report = await probe.verify(client)
        self.assertFalse(report['passed'])
        self.assertEqual(report['rows']['bare']['error_code'], 'BrowseFailed')
        self.assertNotIn('secret', json.dumps(report))
        client.call_tool.assert_awaited_once_with('execute_javascript', {'code': probe.CODE})
        self.assertIn("location.origin!=='http://localhost:30000'", probe.CODE)
        self.assertIn("game.world.id!=='test'", probe.CODE)
