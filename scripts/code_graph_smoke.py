#!/usr/bin/env python3
"""Bounded SDK initialize/list/query/shutdown check; no Codex or Foundry needed."""
import asyncio
import json
from pathlib import Path
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
TOOLS = {"project_map", "module_overview", "get_ast_node", "get_call_graph",
         "find_references", "semantic_code_search", "ast_search"}


async def smoke():
    async with stdio_client(StdioServerParameters(
        command="bash", args=[str(ROOT / "scripts/code-graph.sh"), "serve"],
        cwd=str(ROOT),
    )) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            catalog = await session.list_tools()
            assert TOOLS == {tool.name for tool in catalog.tools}, catalog
            for name, file in (
                ("FoundryConnectionManager", "foundry_mcp_server/ws/connection.py"),
                ("handleRpcMessage", "foundry-module/scripts/foundryBridge.js"),
            ):
                result = await session.call_tool("get_ast_node", {
                    "symbol_name": name, "file_path": file, "compact": True,
                })
                assert not result.is_error, result
                payload = "\n".join(c.text for c in result.content if c.type == "text")
                node = json.loads(payload)
                assert node['name'] == name and node['file_path'] == file, node
                assert node['start_line'] > 0 and node['end_line'] >= node['start_line'], node
                print(f"code-graph: MCP resolved {name} in {file}", file=sys.stderr)
            if "--dump-schemas" in sys.argv:
                print(json.dumps([t.model_dump() for t in catalog.tools], indent=2))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(smoke(), timeout=90))
