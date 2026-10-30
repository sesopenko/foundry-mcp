from fastmcp import FastMCP
from foundry_mcp_server.config import settings
from foundry_mcp_server.evaluation import EvaluationMiddleware, TraceRecorder
from foundry_mcp_server.auth.factory import create_auth

mcp = FastMCP("foundry-mcp", dereference_schemas=False, auth=create_auth(settings))
if settings.auth_mode == 'oauth':
    from foundry_mcp_server.auth.metadata import OAuthToolMetadata
    mcp.add_middleware(OAuthToolMetadata())
trace_recorder = TraceRecorder(settings.trace_path) if settings.trace_path else None
if trace_recorder is not None:
    mcp.add_middleware(EvaluationMiddleware(trace_recorder))
mcp_app = mcp.http_app(path="/mcp/mcp")

__all__ = ["mcp", "mcp_app"]
