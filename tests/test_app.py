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
        manager.register.assert_awaited_once_with("gm", socket, welcome={"type": "serverInfo", "server_build": main.SERVER_BUILD})
        manager.handle_incoming.assert_awaited_once_with('{"id":"request","result":[]}', socket)
        manager.unregister.assert_awaited_once_with("gm", socket)

    async def test_websocket_handler_failure_still_unregisters(self):
        manager, socket = AsyncMock(), AsyncMock()
        socket.receive_text.side_effect = ValueError("transport failure")
        with patch.object(main, "foundry_manager", manager):
            await main.foundry_ws(socket)
        manager.unregister.assert_awaited_once_with("gm", socket)

    async def test_development_socket_authentication_and_local_boundary(self):
        from foundry_mcp_server.config import Settings
        settings = Settings(development=True, mcp_token="a" * 32, browser_token="b" * 32)
        for peer, token, accepted in [
            ("192.0.2.1", settings.browser_token, False),
            ("127.0.0.1", "wrong", False),
            ("127.0.0.1", settings.browser_token, True),
        ]:
            with self.subTest(peer=peer, accepted=accepted):
                manager, socket = AsyncMock(), AsyncMock()
                socket.client.host = peer
                socket.receive_json.return_value = {"token": token}
                socket.receive_text.side_effect = WebSocketDisconnect()
                with patch.object(main, "settings", settings), patch.object(main, "foundry_manager", manager):
                    await main.foundry_ws(socket)
                if accepted:
                    manager.register.assert_awaited_once_with("gm", socket, welcome={"type": "serverInfo", "server_build": main.SERVER_BUILD})
                    manager.unregister.assert_awaited_once_with("gm", socket)
                else:
                    manager.register.assert_not_awaited()
                    socket.close.assert_awaited_once_with(code=1008)

    async def test_duplicate_authenticated_socket_preserves_owner(self):
        from foundry_mcp_server.config import Settings
        manager, socket = AsyncMock(), AsyncMock()
        socket.client.host = "127.0.0.1"
        socket.receive_json.return_value = {"token": "b" * 32}
        manager.register.side_effect = RuntimeError("duplicate")
        with patch.object(main, "settings", Settings(development=True, browser_token="b" * 32)), patch.object(main, "foundry_manager", manager):
            await main.foundry_ws(socket)
        socket.close.assert_awaited_once_with(code=1008, reason="GM bridge already connected")
        manager.unregister.assert_not_awaited()

    async def test_oversized_response_closes_socket_and_unregisters(self):
        manager, socket = AsyncMock(), AsyncMock()
        socket.receive_text.return_value = "x" * 65537
        with patch.object(main, "foundry_manager", manager):
            await main.foundry_ws(socket)
        socket.close.assert_awaited_once_with(code=1009)
        manager.unregister.assert_awaited_once_with("gm", socket)
        manager.handle_incoming.assert_not_awaited()
