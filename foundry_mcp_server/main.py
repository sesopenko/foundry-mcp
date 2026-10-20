import asyncio
import base64
import binascii
import json
import secrets
import logging

from foundry_mcp_server.config import settings

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
import uvicorn

from foundry_mcp_server.ws.connection import FoundryConnectionManager

from foundry_mcp_server.mcp_server.server import mcp_app, trace_recorder
from foundry_mcp_server.mcp_server.tools import register_foundry_manager

logger = logging.getLogger("foundry_mcp")
logging.basicConfig(level=logging.INFO)

# Instantiate global connection manager
foundry_manager = FoundryConnectionManager()
register_foundry_manager(foundry_manager)

# Create FastAPI app
app = FastAPI(
    title="Foundry MCP Bridge",
    description="MCP HTTP server + WebSocket bridge to Foundry VTT",
    version="1.2.2",
    lifespan=mcp_app.lifespan
)

class MCPAccessControl:
    """Authenticate MCP before FastMCP handles discovery, calls or sessions."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        mcp_request = scope["type"] == "http" and (scope["path"] == "/mcp" or scope["path"].startswith("/mcp/"))
        if settings.auth_mode == "basic" and mcp_request:
            headers = [value for key, value in scope.get("headers", []) if key == b"authorization"]
            valid = False
            if len(headers) == 1 and len(headers[0]) <= 8192:
                try:
                    scheme, encoded = headers[0].split(b" ", 1)
                    if scheme.lower() == b"basic":
                        decoded = base64.b64decode(encoded, validate=True)
                        expected = (settings.basic_username + ":" + settings.basic_password).encode("utf-8")
                        valid = secrets.compare_digest(decoded, expected)
                except (ValueError, binascii.Error):
                    pass
            if not valid:
                await JSONResponse({"error": "Unauthorized"}, status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Foundry MCP", charset="UTF-8"'})(scope, receive, send)
                return
        if settings.development and mcp_request:
            headers = dict(scope.get("headers", []))
            expected = ("Bearer " + settings.mcp_token).encode()
            peer = (scope.get("client") or ("",))[0]
            if peer not in {"127.0.0.1", "::1"} or not secrets.compare_digest(headers.get(b"authorization", b""), expected):
                await JSONResponse({"error": "Unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app.add_middleware(MCPAccessControl)

app.mount("/mcp", mcp_app)


# --- WebSocket Endpoint for Foundry Clients ---------------------------------


@app.websocket("/ws/foundry")
async def foundry_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for Foundry VTT browser clients.

    The Foundry module should connect here and then:
      - Receive JSON-RPC requests from the server
      - Execute Foundry API calls
      - Send back JSON-RPC responses
    """
    client_id = "gm"
    if settings.development:
        peer = websocket.client.host if websocket.client else ""
        if peer not in {"127.0.0.1", "::1"}:
            await websocket.close(code=1008)
            return
    await websocket.accept()
    if settings.development:
        try:
            hello = await asyncio.wait_for(websocket.receive_json(), timeout=5)
            token = hello.get("token") if isinstance(hello, dict) else None
            if not isinstance(token, str) or not secrets.compare_digest(token.encode(), settings.browser_token.encode()):
                await websocket.close(code=1008)
                return
        except (ValueError, asyncio.TimeoutError, WebSocketDisconnect):
            await websocket.close(code=1008)
            return
    production_auth = settings.auth_mode == "basic"
    if production_auth:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=5)
            if len(raw.encode("utf-8")) > 4096:
                await websocket.close(code=1009)
                return
            hello = json.loads(raw)
            token = hello.get("token") if isinstance(hello, dict) else None
            if (not isinstance(hello, dict) or hello.get("type") != "auth"
                or not isinstance(token, str)
                or not secrets.compare_digest(token.encode(), settings.bridge_token.encode())):
                await websocket.close(code=1008)
                return
        except (ValueError, UnicodeError, asyncio.TimeoutError, WebSocketDisconnect, RuntimeError, KeyError):
            await websocket.close(code=1008)
            return
    try:
        if production_auth:
            await foundry_manager.register(client_id, websocket, welcome={"type": "auth", "status": "ok"})
        else:
            await foundry_manager.register(client_id, websocket)
    except RuntimeError:
        await websocket.close(code=1008, reason="GM bridge already connected")
        return

    logger.info("Foundry client %s connected", client_id)

    try:
        while True:
            msg = await websocket.receive_text()
            if len(msg.encode("utf-8")) > settings.max_response_bytes:
                await websocket.close(code=1009)
                break
            await foundry_manager.handle_incoming(msg, websocket)
    except WebSocketDisconnect:
        logger.info("Foundry client %s disconnected", client_id)
    except Exception as e:
        logger.exception("Error in WebSocket handler for client %s: %s", client_id, e)
    finally:
        await foundry_manager.unregister(client_id, websocket)


# --- Simple Health Check -----------------------------------------------------


@app.get("/health")
async def health() -> JSONResponse:
    """
    Basic health check endpoint.
    """
    data = {"status": "ok", "foundry_clients": list(foundry_manager.websockets)}
    if trace_recorder is not None:
        data["evaluation_logging"] = {"enabled": True, "write_failures": trace_recorder.write_failures}
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=data,
    )


# --- Entry Point -------------------------------------------------------------


def main() -> None:
    """
    Run the ASGI server with uvicorn.
    """
    uvicorn.run(
        "foundry_mcp_server.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
