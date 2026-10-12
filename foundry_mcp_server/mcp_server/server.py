from fastmcp import FastMCP

mcp = FastMCP("foundry-mcp")
mcp_app = mcp.http_app(path="/mcp")

__all__ = ["mcp", "mcp_app"]
