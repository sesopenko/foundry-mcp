import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import WebSocketDisconnect
from foundry_mcp_server import main


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_reports_active_clients(self):
        manager = AsyncMock()
        manager.websockets = {"gm": object()}
        with patch.object(main, "foundry_manager", manager):
            response = await main.health()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body), {"status": "ok", "foundry_clients": ["gm"]})

    async def test_websocket_registers_dispatches_and_unregisters(self):
        manager, socket = AsyncMock(), AsyncMock()
        socket.receive_text.side_effect = ['{"id":"request","result":[]}', WebSocketDisconnect()]
        with patch.object(main, "foundry_manager", manager):
            await main.foundry_ws(socket)
        socket.accept.assert_awaited_once()
        manager.register.assert_awaited_once_with("gm", socket)
        manager.handle_incoming.assert_awaited_once_with('{"id":"request","result":[]}')
        manager.unregister.assert_awaited_once_with("gm")

    async def test_websocket_handler_failure_still_unregisters(self):
        manager, socket = AsyncMock(), AsyncMock()
        socket.receive_text.side_effect = ValueError("transport failure")
        with patch.object(main, "foundry_manager", manager):
            await main.foundry_ws(socket)
        manager.unregister.assert_awaited_once_with("gm")
