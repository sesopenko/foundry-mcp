import asyncio
import json
import unittest

from foundry_mcp_server.ws.connection import FoundryConnectionManager


class FakeSocket:
    def __init__(self):
        self.sent = asyncio.Queue()

    async def send_text(self, message):
        await self.sent.put(json.loads(message))


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = FoundryConnectionManager()
        self.socket = FakeSocket()
        await self.manager.register("gm", self.socket)

    async def respond(self, response):
        await self.manager.handle_incoming(json.dumps(response), self.socket)

    async def test_register_unregister_and_missing_client(self):
        self.assertIs(self.manager.websockets["gm"], self.socket)
        await self.manager.unregister("gm", self.socket)
        with self.assertRaisesRegex(RuntimeError, "No active Foundry client"):
            await self.manager.call("gm", "getPlayerNameList")

    async def test_request_and_response_correlation(self):
        first = asyncio.create_task(self.manager.call("gm", "first", {"actor": "a"}))
        second = asyncio.create_task(self.manager.call("gm", "second"))
        one, two = await self.socket.sent.get(), await self.socket.sent.get()
        self.assertNotEqual(one["id"], two["id"])
        self.assertEqual(one["method"], "first")
        self.assertEqual(one["params"], {"actor": "a"})
        self.assertEqual(two["params"], {})
        await self.respond({"id": two["id"], "result": ["second"]})
        await self.respond({"id": one["id"], "result": ["first"]})
        self.assertEqual(await first, ["first"])
        self.assertEqual(await second, ["second"])
        self.assertFalse(self.manager.pending)

    async def test_browser_error_propagates_and_cleans_up(self):
        task = asyncio.create_task(self.manager.call("gm", "test"))
        request = await self.socket.sent.get()
        await self.respond({"id": request["id"], "error": {"message": "browser failed"}})
        with self.assertRaisesRegex(RuntimeError, "browser failed"):
            await task
        self.assertFalse(self.manager.pending)

    async def test_invalid_unknown_and_duplicate_responses(self):
        task = asyncio.create_task(self.manager.call("gm", "test"))
        request = await self.socket.sent.get()
        for message in ["invalid JSON", '{}', '{"id":"unknown","result":1}']:
            await self.manager.handle_incoming(message, self.socket)
        self.assertFalse(task.done())
        await self.respond({"id": request["id"], "result": "accepted"})
        await self.respond({"id": request["id"], "result": "duplicate"})
        self.assertEqual(await task, "accepted")

    async def test_timeout_and_cancellation_cleanup(self):
        with self.assertRaises(asyncio.TimeoutError):
            await self.manager.call("gm", "test", timeout=0.001)
        self.assertFalse(self.manager.pending)
        task = asyncio.create_task(self.manager.call("gm", "test"))
        await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(self.manager.pending)

    async def test_send_failure_propagates(self):
        async def fail(message):
            raise ConnectionError("send failed")
        self.socket.send_text = fail
        with self.assertRaisesRegex(ConnectionError, "send failed"):
            await self.manager.call("gm", "test")
        self.assertFalse(self.manager.pending)
