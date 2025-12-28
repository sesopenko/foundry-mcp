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

mcp = FastMCP("foundry-mcp")

mcp_app = mcp.http_app(path="/mcp")

__all__ = [
    "mcp",
    "mcp_app",
]