"""Keep the isolated container probe aligned with actual production discovery."""
import importlib.util
from pathlib import Path
import unittest

from fastmcp import Client
from foundry_mcp_server import main
from foundry_mcp_server.mcp_server.server import mcp


SPEC = importlib.util.spec_from_file_location(
    'container_smoke', Path(__file__).resolve().parents[1] / 'scripts/container-smoke.py')
SMOKE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SMOKE)


class ContainerSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_expected_catalog_matches_actual_production_discovery(self):
        async with Client(mcp) as client:
            tools = await client.list_tools()
        self.assertEqual({tool.name for tool in tools}, SMOKE.TOOLS)
        self.assertNotIn('execute_javascript', SMOKE.TOOLS)
        for tool in tools:
            self.assertTrue(tool.description)
            self.assertEqual(tool.inputSchema.get('type'), 'object')
