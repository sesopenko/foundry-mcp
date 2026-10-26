"""Check actual Actor MCP discovery without requiring a Foundry browser.

Uses the existing local caller credential without displaying it. This checks
published descriptions/input schemas only, never runtime support or world data.
"""

import argparse
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def main(section, required_terms):
    try:
        root = Path(__file__).resolve().parent.parent
        token = next(line.partition('=')[2].strip()
                     for line in (root / '.env.mcp').read_text().splitlines()
                     if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        transport = StreamableHttpTransport(
            'http://127.0.0.1:8000/mcp/mcp',
            headers={'Authorization': 'Bearer ' + token},
        )
        async with Client(transport) as client:
            published = {tool.name: tool for tool in await client.list_tools()}
            tool = published['read_actor']
            properties = tool.inputSchema['properties']
            assert {'actor_uuid', 'token_uuid', 'sections', 'limit', 'max_bytes', 'cursor'} <= properties.keys()
            assert section in properties['sections']['items']['enum']
            assert tool.annotations.readOnlyHint
            assert all(term in tool.description for term in required_terms)
        print(json.dumps({'passed': True, 'discovery_verified': True,
                          'section': section, 'required_terms': len(required_terms),
                          'mcp_calls': 1, 'runtime_checked': False}))
        return 0
    except Exception as error:
        print(json.dumps({'passed': False, 'exception_type': type(error).__name__,
                          'runtime_checked': False}))
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section', required=True)
    parser.add_argument('--require-term', action='append', default=[])
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(arguments.section, arguments.require_term)))
