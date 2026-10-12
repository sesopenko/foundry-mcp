from fastmcp import FastMCP
from foundry_mcp_server.config import settings
from foundry_mcp_server.evaluation import EvaluationMiddleware, TraceRecorder

mcp = FastMCP("foundry-mcp")
trace_recorder = TraceRecorder(settings.trace_path) if settings.trace_path else None
if trace_recorder is not None:
    mcp.add_middleware(EvaluationMiddleware(trace_recorder))
mcp_app = mcp.http_app(path="/mcp")

__all__ = ["mcp", "mcp_app"]
