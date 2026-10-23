"""PF2e-specific8.6.1 recorded selection source boundaries."""
import unittest
from unittest.mock import AsyncMock
from fastmcp.exceptions import ToolError
from test_actor_feat import feat_source
from foundry_mcp_server.mcp_server.actors import read_item
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
class FeatSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager=AsyncMock();register_foundry_manager(self.manager)
    async def read(self,result):
        self.manager.call.return_value=result
        return await read_item.fn(item_uuid='Item.a',sections=['source'])
    async def test_selected_scalars_and_missing_empty_markers(self):
        for path,value in [('/flags/pf2e/rulesSelections',{}),('/flags/pf2e/rulesSelections/','x'),('/flags/pf2e/rulesSelections/a~1~0',2.5)]:
            await self.read(feat_source(path,value))
        await self.read(feat_source('/flags/pf2e/rulesSelections',present=False))
    async def test_unsupported_values_and_forged_complete_rejected(self):
        for value in [None,True,[],{},float('inf')]:
            with self.assertRaises(ToolError):await self.read(feat_source('/flags/pf2e/rulesSelections/choice',value))
        result=feat_source('/flags/pf2e/rulesSelections/choice','x');result['sections'][0].update(status='partial',reasons=['unsupported_selection_values']);await self.read(result)
        result['sections'][0]['status']='complete'
        with self.assertRaises(ToolError):await self.read(result)
