import asyncio
import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status


logger = logging.getLogger("foundry_mcp")
logging.basicConfig(level=logging.INFO)

class FoundryConnectionManager:
    """
    Manages WebSocket connections to Foundry VTT browser clients and
    provides a simple JSON-RPC style call() API for MCP tools.
    """

    def __init__(self) -> None:
        # Active WebSocket connections keyed by client_id (e.g. "gm")
        self.websockets: Dict[str, WebSocket] = {}
        # Pending RPC calls keyed by rpc_id
        self.pending: Dict[str, asyncio.Future] = {}

    async def register(self, client_id: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection for a given client_id.
        """
        logger.info("Registering Foundry client %s", client_id)
        self.websockets[client_id] = websocket

    async def unregister(self, client_id: str) -> None:
        """
        Remove a WebSocket connection for a given client_id.
        """
        logger.info("Unregistering Foundry client %s", client_id)
        self.websockets.pop(client_id, None)

    def _get_websocket(self, client_id: str) -> WebSocket:
        if client_id not in self.websockets:
            raise RuntimeError(f"No active Foundry client with id '{client_id}'")
        return self.websockets[client_id]

    async def call(
        self,
        client_id: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Any:
        """
        Send a JSON-RPC style request over the WebSocket to the given client_id
        and wait for the response.

        Raises:
            RuntimeError if no client is connected.
            asyncio.TimeoutError if the call times out.
        """
        ws = self._get_websocket(client_id)
        rpc_id = str(uuid4())
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        self.pending[rpc_id] = fut

        message = {
            "id": rpc_id,
            "method": method,
            "params": params or {},
        }

        logger.debug("Sending RPC to %s: %s", client_id, message)
        await ws.send_text(json.dumps(message))

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            logger.debug("Received RPC result for %s: %s", rpc_id, result)
            return result
        finally:
            # Ensure we always clean up the pending future
            self.pending.pop(rpc_id, None)

    async def handle_incoming(self, raw_message: str) -> None:
        """
        Handle an incoming JSON message from a Foundry WebSocket client.

        Expected format:
        {
            "id": "uuid",
            "result": ...,
            "error": { ... }  # optional
        }
        """
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON from Foundry client: %s", raw_message)
            return

        rpc_id = data.get("id")
        if not rpc_id:
            logger.warning("Received message without 'id': %s", data)
            return

        fut = self.pending.get(rpc_id)
        if not fut:
            logger.warning("No pending RPC for id %s", rpc_id)
            return

        if fut.done():
            # Should not happen, but guard against double-resolution
            logger.warning("Future for id %s is already done", rpc_id)
            return

        if "error" in data and data["error"] is not None:
            # Represent errors as exceptions
            error = data["error"]
            message = error.get("message", "Unknown error from Foundry client")
            fut.set_exception(RuntimeError(message))
        else:
            fut.set_result(data.get("result"))