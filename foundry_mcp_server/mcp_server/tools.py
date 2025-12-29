import asyncio
from typing import Any, Dict, List

from fastmcp.exceptions import ToolError

from foundry_mcp_server.ws.connection import FoundryConnectionManager
from foundry_mcp_server.mcp_server.server import mcp

_foundry_manager: FoundryConnectionManager


@mcp.tool
async def get_player_names() -> List[str]:
    """
    MCP tool that asks the Foundry client for the current player name list.

    The Foundry browser module should implement a handler for method
    "getPlayerNameList" and return a list of strings.
    """
    try:
        result = await _foundry_manager.call(
            client_id="gm",  # For now, assume a single GM client
            method="getPlayerNameList",
            params={},
            timeout=5.0,
        )
    except RuntimeError as e:
        # No client connected or client-side error
        raise ToolError(f"no client connected or client side error: {e}") from e
    except asyncio.TimeoutError as e:
        raise ToolError("Timed out waiting for Foundry client response") from e

    # Verify result is a list of strings
    if not isinstance(result, list):
        raise ToolError(f"Expected list response from Foundry client, got: {type(result).__name__}")

    if not all(isinstance(item, str) for item in result):
        raise ToolError("Expected list of strings from Foundry client")

    return result


def register_foundry_manager(foundry_manager: FoundryConnectionManager) -> None:
    global _foundry_manager
    _foundry_manager = foundry_manager
