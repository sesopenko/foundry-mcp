import asyncio
import json
import logging
from uuid import uuid4

logger = logging.getLogger("foundry_mcp")


class RpcError(RuntimeError):
    def __init__(self, error):
        self.error = error
        super().__init__(error.get("message", "Foundry RPC error"))


class FoundryConnectionManager:
    """Correlate responses with the exact socket that received each request."""

    def __init__(self):
        self.websockets = {}
        self.pending = {}

    async def register(self, client_id, websocket):
        if client_id in self.websockets:
            raise RuntimeError("Authorized client already connected; close it first")
        self.websockets[client_id] = websocket

    async def unregister(self, client_id, websocket):
        if self.websockets.get(client_id) is websocket:
            self.websockets.pop(client_id)
        for future, owner in list(self.pending.values()):
            if owner is websocket and not future.done():
                future.set_exception(ConnectionError("Foundry client disconnected"))

    async def call(self, client_id, method, params=None, timeout=10.0):
        ws = self.websockets.get(client_id)
        if ws is None:
            raise RuntimeError(f"No active Foundry client with id '{client_id}'")
        rpc_id = str(uuid4())
        future = asyncio.get_running_loop().create_future()
        self.pending[rpc_id] = (future, ws)
        try:
            async with asyncio.timeout(timeout):
                await ws.send_text(json.dumps({"id": rpc_id, "method": method, "params": params or {}}))
                return await future
        finally:
            self.pending.pop(rpc_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Consume disconnect errors even if sending failed.

    async def handle_incoming(self, raw_message, websocket):
        try:
            data = json.loads(raw_message)
        except (ValueError, TypeError):
            return
        if not isinstance(data, dict) or not isinstance(data.get("id"), str):
            return
        entry = self.pending.get(data["id"])
        if not entry:
            return
        future, owner = entry
        if owner is not websocket or future.done():
            return
        error = data.get("error")
        if error is not None:
            if not isinstance(error, dict):
                error = {"type": "RpcTransportError", "message": "Malformed browser error"}
            future.set_exception(RpcError(error))
        else:
            future.set_result(data.get("result"))
