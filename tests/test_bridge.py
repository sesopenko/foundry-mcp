import asyncio
import json
import os
import subprocess
import unittest
from unittest.mock import patch

from foundry_mcp_server.config import Settings
from foundry_mcp_server.ws.connection import FoundryConnectionManager, RpcError


class Socket:
    def __init__(self, fail=False):
        self.sent = asyncio.Queue()
        self.fail = fail

    async def send_text(self, value):
        if self.fail:
            raise ConnectionError("send failed")
        await self.sent.put(json.loads(value))


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = FoundryConnectionManager()
        self.socket = Socket()
        await self.manager.register("gm", self.socket)

    async def test_response_owner_and_structured_error(self):
        task = asyncio.create_task(self.manager.call("gm", "executeJavaScript"))
        request = await self.socket.sent.get()
        error = {"type": "JavaScriptRuntimeError", "message": "failed", "stack": "trace"}
        response = json.dumps({"id": request["id"], "error": error})
        await self.manager.handle_incoming(response, Socket())
        self.assertFalse(task.done())
        await self.manager.handle_incoming(response, self.socket)
        with self.assertRaises(RpcError) as raised:
            await task
        self.assertEqual(raised.exception.error, error)
        self.assertEqual(self.manager.pending, {})

    async def test_duplicate_connection_and_stale_disconnect(self):
        other = Socket()
        with self.assertRaises(RuntimeError):
            await self.manager.register("gm", other)
        await self.manager.unregister("gm", other)
        self.assertIs(self.manager.websockets["gm"], self.socket)

    async def test_disconnect_fails_call(self):
        task = asyncio.create_task(self.manager.call("gm", "test"))
        await self.socket.sent.get()
        await self.manager.unregister("gm", self.socket)
        with self.assertRaises(ConnectionError):
            await task
        self.assertEqual(self.manager.pending, {})

    async def test_send_failure_timeout_and_cancellation_cleanup(self):
        self.socket.fail = True
        with self.assertRaises(ConnectionError):
            await self.manager.call("gm", "test")
        self.assertFalse(self.manager.pending)
        self.socket.fail = False
        with self.assertRaises(asyncio.TimeoutError):
            await self.manager.call("gm", "test", timeout=0.001)
        self.assertFalse(self.manager.pending)
        task = asyncio.create_task(self.manager.call("gm", "test"))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(self.manager.pending)


class ConfigurationTests(unittest.TestCase):
    def test_disabled_default_and_fail_closed_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(Settings.from_env().development)
            os.environ["FOUNDRY_MCP_DEV_EXECUTION"] = "true"
            with self.assertRaises(ValueError):
                Settings.from_env()
            os.environ["FOUNDRY_MCP_CALLER_TOKEN"] = "a" * 32
            os.environ["FOUNDRY_MCP_BROWSER_TOKEN"] = "b" * 32
            self.assertTrue(Settings.from_env().development)

    def test_discovery_and_http_authorization(self):
        script = '''
import asyncio
import httpx2 as httpx
from foundry_mcp_server.main import app
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.config import settings
async def run():
    tools = {t.name: t for t in await mcp.list_tools()}
    assert ("execute_javascript" in tools) == settings.development
    if settings.development:
        async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for method in ["GET", "POST", "DELETE"]:
                response = await client.request(method, "/mcp/mcp")
                assert response.status_code == 401
            response = await client.get("/mcp/mcp", headers={"Authorization": "Bearer " + settings.mcp_token})
            assert response.status_code != 401
asyncio.run(run())
'''
        for enabled in ["false", "true"]:
            env = {**os.environ, "FOUNDRY_MCP_DEV_EXECUTION": enabled,
                   "FOUNDRY_MCP_CALLER_TOKEN": "a" * 32, "FOUNDRY_MCP_BROWSER_TOKEN": "b" * 32}
            result = subprocess.run([os.sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


class ExecutionToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_validation_results_and_error_categories(self):
        from unittest.mock import AsyncMock
        from fastmcp.exceptions import ToolError
        from foundry_mcp_server import config
        from foundry_mcp_server.mcp_server import tools
        manager = AsyncMock()
        settings = Settings(development=True)
        with patch.object(config, "settings", settings), patch.object(tools, "_foundry_manager", manager, create=True):
            for code in [None, " ", "x" * 32769, "😀" * 10000, "\ud800"]:
                with self.assertRaisesRegex(ToolError, "InvalidParameters"):
                    await tools.execute_javascript(code)
            manager.call.assert_not_awaited()
            manager.call.return_value = {"value": 1, "foundryVersion": "13"}
            self.assertEqual((await tools.execute_javascript("return 1"))["value"], 1)
            manager.call.assert_awaited_once_with("gm", "executeJavaScript", {"code": "return 1"}, timeout=settings.timeout)
            for error, category in [
                (RpcError({"type": "JavaScriptRuntimeError", "message": "failed", "stack": "trace"}), "JavaScriptRuntimeError"),
                (RuntimeError("missing"), "NoConnectedClient"),
                (ConnectionError("gone"), "RpcTransportError"),
                (asyncio.TimeoutError(), "ExecutionTimeout"),
            ]:
                manager.call.side_effect = error
                with self.assertRaisesRegex(ToolError, category):
                    await tools.execute_javascript("return 1")
            manager.call.side_effect = None
            manager.call.return_value = {"value": "x" * 65537}
            with self.assertRaisesRegex(ToolError, "SerializationError"):
                await tools.execute_javascript("return 1")
        with patch.object(config, "settings", Settings()):
            with self.assertRaisesRegex(ToolError, "UnauthorizedExecution"):
                await tools.execute_javascript("return 1")
