#!/usr/bin/env python3
"""Protocol-aware checks against an isolated local test service, never a live world.

Requires an empty bridge. Uses a synthetic browser solely to test transport.
"""
import argparse
import asyncio
import json
import os
import httpx
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import websockets

TOOLS = {'get_player_names', 'get_journal_tree', 'get_journal_contents', 'search_journals', 'read_journal_page'}


def health(base):
    with build_opener(ProxyHandler({})).open(base + '/health', timeout=3) as response:
        return json.load(response)


async def smoke(base):
    assert health(base)['foundry_clients'] == [], 'Use an isolated empty service, not a connected world'
    parsed = urlsplit(base)
    ws_url = ('wss' if parsed.scheme == 'https' else 'ws') + '://' + parsed.netloc + '/ws/foundry'
    username = os.getenv('FOUNDRY_MCP_SMOKE_USERNAME', 'smoke')
    password = os.getenv('FOUNDRY_MCP_SMOKE_PASSWORD', 'smoke-password-for-isolated-tests-only')
    token = os.getenv('FOUNDRY_MCP_SMOKE_BRIDGE_TOKEN', 'smoke-browser-token-for-isolated-tests-only')
    async with httpx.AsyncClient(trust_env=False) as http:
        for auth in [None, httpx.BasicAuth(username, 'wrong')]:
            response = await http.post(base + '/mcp/mcp', auth=auth)
            assert response.status_code == 401
    async with websockets.connect(ws_url) as rejected:
        await rejected.send(json.dumps({'type': 'auth', 'token': 'wrong'}))
        await rejected.wait_closed()
        assert rejected.close_code == 1008
    async def authenticate(browser):
        await browser.send(json.dumps({'type': 'auth', 'token': token}))
        assert json.loads(await browser.recv()) == {'type': 'auth', 'status': 'ok'}
    async with Client(StreamableHttpTransport(base + '/mcp/mcp', auth=httpx.BasicAuth(username, password))) as client:
        tools = await client.list_tools()
        assert {t.name for t in tools} == TOOLS, 'Unexpected production discovery catalog'
        for tool in tools:
            assert tool.description and tool.inputSchema.get('type') == 'object'
        missing = await client.call_tool('get_player_names', {}, raise_on_error=False)
        assert missing.is_error
        async with websockets.connect(ws_url) as browser:
            await authenticate(browser)
            # Registration may finish just after the WebSocket handshake.
            for _ in range(50):
                if health(base)['foundry_clients'] == ['gm']:
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError('GM was not registered')
            async with websockets.connect(ws_url) as duplicate:
                await duplicate.send(json.dumps({'type': 'auth', 'token': token}))
                await duplicate.wait_closed()
                assert duplicate.close_code == 1008
            call = asyncio.create_task(client.call_tool('get_player_names', {}))
            request = json.loads(await browser.recv())
            assert request['method'] == 'getPlayerNameList'
            await browser.send(json.dumps({'id': request['id'], 'result': ['Synthetic GM']}))
            result = await call
            assert not result.is_error and 'Synthetic GM' in str(result)
            # Disconnect while a call is pending: fail promptly, do not wait for timeout.
            call = asyncio.create_task(client.call_tool('get_player_names', {}, raise_on_error=False))
            await browser.recv()
            await browser.close()
            assert (await asyncio.wait_for(call, 2)).is_error
        async with websockets.connect(ws_url) as reconnected:
            await authenticate(reconnected)
            await reconnected.close()
    print('PASS: authentication, health, discovery/schema, no-GM, RPC, duplicate rejection, disconnect, reconnect')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:18000')
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(smoke(args.url.rstrip('/')), 30))
