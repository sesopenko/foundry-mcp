import asyncio
from fastmcp.exceptions import ToolError

from foundry_mcp_server.ws.connection import FoundryConnectionManager
from foundry_mcp_server.mcp_server.server import mcp

_foundry_manager: FoundryConnectionManager

@mcp.tool
async def get_world_name() -> str:
    """
    Example MCP tool that asks the Foundry client for the current world name.

    The Foundry browser module should implement a handler for method "getWorldName"
    and return a string.
    """
    try:
        result = await _foundry_manager.call(
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

def register_foundry_manager(foundry_manager: FoundryConnectionManager)->None:
    _foundry_manager = foundry_manager