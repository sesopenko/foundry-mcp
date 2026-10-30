import asyncio
import unittest
from unittest.mock import AsyncMock

from fastmcp.exceptions import ToolError
from foundry_mcp_server.mcp_server.tools import get_player_names, register_foundry_manager


class PlayerNamesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_returns_names_and_uses_existing_rpc(self):
        self.manager.call.return_value = ["Alice", "Bob"]
        self.assertEqual(await get_player_names(), ["Alice", "Bob"])
        self.manager.call.assert_awaited_once_with(client_id="gm", method="getPlayerNameList", params={}, timeout=5.0)

    async def test_empty_player_list(self):
        self.manager.call.return_value = []
        self.assertEqual(await get_player_names(), [])

    async def test_rejects_invalid_response(self):
        for response in [None, {}, "Alice", ["Alice", 5]]:
            with self.subTest(response=response):
                self.manager.call.return_value = response
                with self.assertRaises(ToolError):
                    await get_player_names()

    async def test_rpc_errors_become_tool_errors(self):
        for error in [RuntimeError("missing client"), asyncio.TimeoutError()]:
            self.manager.call.side_effect = error
            with self.assertRaises(ToolError):
                await get_player_names()
