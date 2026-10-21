import asyncio
from typing import Any, Dict, List, Literal, TypedDict

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
from . import actors  # noqa: E402,F401


class BuildIdentity(TypedDict):
    version: str | None
    release_tag: str | None
    revision: str | None
    build_kind: Literal['release', 'unreleased', 'source', 'unknown']


class BridgeVersionResult(TypedDict):
    server: BuildIdentity
    module: BuildIdentity | None
    comparison: Literal['match', 'mismatch', 'unverified', 'unavailable']
    module_status: Literal['connected', 'not_connected', 'unsupported', 'timed_out', 'disconnected', 'invalid_metadata']
    message: str


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
async def get_bridge_versions() -> BridgeVersionResult:
    """Diagnose the packaged MCP server and currently connected GM browser module.

    Read-only, no inputs. Available under the server's normal authentication in
    production and development. No connected GM is required to obtain server
    identity; module identity requires the single admitted GM browser. Does not
    read game documents, query available releases online, or install updates.

    Returns server and module build objects with version (X.Y.Z or null),
    release_tag (vX.Y.Z or null), revision (commit SHA or null), and build_kind
    (release, unreleased, source, unknown). Module is null if its query fails.
    comparison is match/mismatch only for two validated tagged releases, using
    exact version equality; otherwise unverified or unavailable. This is not a
    guarantee of Foundry/core or protocol compatibility. module_status is
    connected, not_connected, unsupported, timed_out, disconnected, or
    invalid_metadata; message explains the result and recovery.

    Queries the loaded module over RPC with a five-second timeout. No browser,
    legacy modules lacking this RPC, disconnects, timeouts and invalid metadata
    return diagnostic results, not tool errors; server identity is preserved.
    Connect the intended GM, update/reload an unsupported module, or retry after
    reconnecting as directed by message. After diagnosis, use get_player_names
    to verify an actual read reaches the intended world. Unreleased/source builds
    never claim a verified release match, even if declared versions are equal.
    """
    from foundry_mcp_server.build_info import SERVER_BUILD, compare_builds, validate_build_info
    from foundry_mcp_server.ws.connection import RpcError

    result = dict(server=dict(SERVER_BUILD), module=None, comparison='unavailable',
                  module_status='not_connected', message='No GM browser connected. Connect the intended GM browser and retry; server identity is still available.')
    if 'gm' not in _foundry_manager.websockets:
        return result
    try:
        raw = await _foundry_manager.call('gm', 'getModuleBuildInfo', {}, timeout=5.0)
        module = validate_build_info(raw)
    except RpcError as error:
        message = error.error.get('message')
        if isinstance(message, str) and message.startswith('Unknown method'):
            result.update(module_status='unsupported', message='The connected module lacks build diagnostics. Update the Foundry module and reload the GM browser.')
        else:
            result.update(module_status='invalid_metadata', message='Module build query failed. Update/reload the module and retry.')
    except asyncio.TimeoutError:
        result.update(module_status='timed_out', message='Module build query timed out after five seconds. Check the GM browser and retry.')
    except (ConnectionError, RuntimeError):
        result.update(module_status='disconnected', message='GM browser disconnected during the query. Reconnect and retry.')
    except (ValueError, TypeError, RecursionError):
        result.update(module_status='invalid_metadata', message='Module returned invalid build metadata. Update/reload the module and retry.')
    else:
        comparison = compare_builds(SERVER_BUILD, module)
        messages = {
            'match': 'Packaged release versions match. Use get_player_names for an end-to-end world read.',
            'mismatch': 'Packaged release versions differ. Update the older server/container or Foundry module, reload the GM browser and reconnect. Normal tools remain available.',
            'unverified': 'At least one identity is source, unreleased or unknown; a tagged release match cannot be verified.',
        }
        result.update(module=module, comparison=comparison, module_status='connected', message=messages[comparison])
    return result

from . import pdfs  # noqa: E402,F401
