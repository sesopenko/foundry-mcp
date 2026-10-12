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


async def execute_javascript(code: str) -> Dict[str, Any]:
    """Execute an async JavaScript function body in the authorized local GM browser.

    Development only. Use explicit return statements. Timeouts do not stop code
    or undo changes; use a disposable world.
    """
    import hashlib
    import json
    import logging
    from foundry_mcp_server.config import settings
    from foundry_mcp_server.ws.connection import RpcError

    if not settings.development:
        raise ToolError("UnauthorizedExecution: development execution disabled")
    if not isinstance(code, str) or not code.strip():
        raise ToolError("InvalidParameters: provide nonempty JavaScript source")
    try:
        source = code.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ToolError("InvalidParameters: source must be valid UTF-8") from exc
    if len(source) > settings.max_code_bytes:
        raise ToolError("InvalidParameters: source exceeds 32768 UTF-8 bytes")
    # Hash rather than raw source: code can contain arbitrary secrets.
    audit = logging.getLogger("foundry_mcp.execution")
    digest = hashlib.sha256(source).hexdigest()
    audit.info("execution source_sha256=%s bytes=%d", digest, len(source))
    try:
        result = await _foundry_manager.call("gm", "executeJavaScript", {"code": code}, timeout=settings.timeout)
        if not isinstance(result, dict) or len(json.dumps(result).encode()) > settings.max_response_bytes:
            raise ToolError("SerializationError: invalid or oversized browser result")
        audit.info("execution source_sha256=%s outcome=success", digest)
        return result
    except RpcError as exc:
        audit.info("execution source_sha256=%s outcome=browser_error", digest)
        raise ToolError(json.dumps({"error": exc.error})) from exc
    except asyncio.TimeoutError as exc:
        audit.info("execution source_sha256=%s outcome=timeout", digest)
        raise ToolError("ExecutionTimeout: browser code may still be running") from exc
    except ToolError:
        audit.info("execution source_sha256=%s outcome=serialization_error", digest)
        raise
    except ConnectionError as exc:
        audit.info("execution source_sha256=%s outcome=transport_error", digest)
        raise ToolError("RpcTransportError: Foundry disconnected or send failed") from exc
    except RuntimeError as exc:
        audit.info("execution source_sha256=%s outcome=no_client", digest)
        raise ToolError(f"NoConnectedClient: {exc}") from exc


from foundry_mcp_server.config import settings
if settings.development:
    mcp.tool(execute_javascript)

# Registration is independent of the development-only JavaScript console.
from . import journals  # noqa: E402,F401
