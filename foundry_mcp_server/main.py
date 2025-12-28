import asyncio
import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from fastmcp import FastMCP, tools
from fastmcp.exceptions import ToolError

from foundry_mcp_server.ws.connection import FoundryConnectionManager

logger = logging.getLogger("foundry_mcp")
logging.basicConfig(level=logging.INFO)



# Instantiate global connection manager
foundry_manager = FoundryConnectionManager()

# Create FastAPI app
app = FastAPI(
    title="Foundry MCP Bridge",
    description="MCP HTTP server + WebSocket bridge to Foundry VTT",
    version="0.1.0",
)

# Optional CORS configuration (tune as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider restricting in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MCP Server Setup -------------------------------------------------------

# Create FastMCP instance; this exposes an ASGI app we can mount.
mcp = FastMCP("foundry-mcp")


@mcp.tool
async def get_world_name() -> str:
    """
    Example MCP tool that asks the Foundry client for the current world name.

    The Foundry browser module should implement a handler for method "getWorldName"
    and return a string.
    """
    try:
        result = await foundry_manager.call(
            client_id="gm",  # For now, assume a single GM client
            method="getWorldName",
            params={},
            timeout=5.0,
        )
    except RuntimeError as e:
        # No client connected or client-side error
        raise ToolError("no client connected or client side error")
    except asyncio.TimeoutError:
        raise ToolError("no client connected or client side error")
        raise tools.ToolError("Timed out waiting for Foundry client response")

    if not isinstance(result, str):
        raise ToolError(f"Expected string response from Foundry client, got: {result}")

    return result

# Create ASGI app from MCP server
mcp_app = mcp.http_app(path='/mcp')

# Mount MCP HTTP routes under /mcp
# FastMCP exposes an ASGI app via `mcp_server.app`.
app.mount("/mcp",mcp_app)


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
    # Optionally, derive client_id from query params or headers
    client_id = "gm"

    await websocket.accept()
    await foundry_manager.register(client_id, websocket)

    logger.info("Foundry client %s connected", client_id)

    try:
        while True:
            msg = await websocket.receive_text()
            await foundry_manager.handle_incoming(msg)
    except WebSocketDisconnect:
        logger.info("Foundry client %s disconnected", client_id)
    except Exception as e:
        logger.exception("Error in WebSocket handler for client %s: %s", client_id, e)
    finally:
        await foundry_manager.unregister(client_id)


# --- Simple Health Check -----------------------------------------------------


@app.get("/health")
async def health() -> JSONResponse:
    """
    Basic health check endpoint.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "foundry_clients": list(foundry_manager.websockets)},
    )


# --- Entry Point -------------------------------------------------------------


def main() -> None:
    """
    Run the ASGI server with uvicorn.
    """
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
