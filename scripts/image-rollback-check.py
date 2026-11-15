"""Bounded read-only acceptance of the rollback on the existing local service.

Eight requests maximum: discovery, bridge versions, one image-directory page,
player names, and four removed-route GET/HEAD requests. No fixture writes.
Uses the existing local development credential without printing it or game data.
"""
import asyncio
import json
import tomllib
from pathlib import Path

import httpx2 as httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

VERSION = tomllib.loads((Path(__file__).resolve().parent.parent / 'pyproject.toml').read_text())['project']['version']

async def check(client, http):
    tools = await client.list_tools()
    names = {tool.name for tool in tools}
    assert {'get_foundry_image_info', 'get_foundry_image_url', 'browse_maps', 'get_map_info'}.isdisjoint(names)
    assert {'browse_journal_images', 'write_journal', 'upload_image', 'create_image_directory'} <= names
    bridge = (await client.call_tool('get_bridge_versions', {})).structured_content
    assert bridge['module_status'] == 'connected'
    assert bridge['server']['version'] == bridge['module']['version'] == VERSION
    browse = (await client.call_tool('browse_journal_images', {'limit': 1})).structured_content
    assert len(browse['entries']) <= 1
    players = await client.call_tool('get_player_names', {})
    assert not players.is_error
    for path in ('/image-previews', '/image-previews/00000000-0000-4000-8000-000000000000.png'):
        for method in ('GET', 'HEAD'):
            response = await http.request(method, path)
            assert response.status_code == 404
    return dict(passed=True, requests=8, tools=len(names), gm_connected=True,
                browse_entries=len(browse['entries']), browse_complete=browse['complete'],
                removed_routes=4)


async def main():
    root = Path(__file__).resolve().parent.parent
    credential = next(line.partition('=')[2].strip() for line in
                      (root / '.env.mcp').read_text().splitlines()
                      if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',
                                      headers={'Authorization': 'Bearer ' + credential})
    async with asyncio.timeout(30), Client(transport, timeout=10, init_timeout=5) as client:
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8000',
                                     trust_env=False, timeout=5) as http:
            print(json.dumps(await check(client, http)))


if __name__ == '__main__':
    asyncio.run(main())
