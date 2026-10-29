"""Check actual Actor/Item MCP discovery without requiring a Foundry browser.

Uses the existing local caller credential without displaying it. This checks
published descriptions/input schemas only, never runtime support or world data.
"""

import argparse
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180


async def main(section, required_terms, tool_name='read_actor'):
    requested = completed = 0
    stage = 'local_credential'
    try:
        if tool_name not in ('read_actor','read_item'):
            raise ValueError('Unsupported discovery tool')
        root = Path(__file__).resolve().parent.parent
        token = next(line.partition('=')[2].strip()
                     for line in (root / '.env.mcp').read_text().splitlines()
                     if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise RuntimeError('Local caller credential unavailable')
        transport = StreamableHttpTransport(
            'http://127.0.0.1:8000/mcp/mcp',
            headers={'Authorization': 'Bearer ' + token},
        )
        stage = 'connection'
        async with asyncio.timeout(SESSION_TIMEOUT_SECONDS), Client(
            transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS,
        ) as client:
            stage = 'discovery'
            requested += 1
            published = {tool.name: tool for tool in await client.list_tools()}
            completed += 1
            tool = published[tool_name]
            properties = tool.inputSchema['properties']
            selectors = {'actor_uuid','token_uuid'} if tool_name=='read_actor' else {'item_uuid','token_uuid'}
            assert selectors | {'sections','limit','max_bytes','cursor'} <= properties.keys()
            sections = properties['sections']
            if 'anyOf' in sections:
                sections = next(choice for choice in sections['anyOf'] if choice.get('type')=='array')
            assert section in sections['items']['enum']
            assert tool.annotations.readOnlyHint
            assert all(term in tool.description for term in required_terms)
        print(json.dumps({'passed': True, 'discovery_verified': True,
                          'section': section, 'required_terms': len(required_terms),
                          'tool': tool_name, 'mcp_calls': completed,
                          'requested_calls': requested, 'completed_calls': completed,
                          'runtime_checked': False}))
        return 0
    except Exception as error:
        print(json.dumps({'passed': False, 'exception_type': type(error).__name__,
                          'failure_stage': stage, 'mcp_calls': completed,
                          'requested_calls': requested, 'completed_calls': completed,
                          'runtime_checked': False}))
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section', required=True)
    parser.add_argument('--tool', choices=['read_actor','read_item'], default='read_actor')
    parser.add_argument('--require-term', action='append', default=[])
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(arguments.section, arguments.require_term, arguments.tool)))
