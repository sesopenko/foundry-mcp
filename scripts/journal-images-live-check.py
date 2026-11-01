"""Read-only bounded image browsing in the existing localhost test world.

At most24 MCP calls/90 seconds plus discovery. No fixtures, file writes,
recursive scans, downloads, journal mutations or user changes.
"""
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


async def verify(client):
    calls = 0
    report = dict(passed=False, rows=[])

    async def call(args):
        nonlocal calls
        calls += 1
        if calls > 24:
            raise AssertionError('Call budget exceeded')
        return (await client.call_tool('browse_journal_images', args)).structured_content

    try:
        async with asyncio.timeout(90):
            guard = await client.call_tool('execute_javascript', dict(code="if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');return JSON.stringify({ready:true});"))
            calls += 1
            assert json.loads(guard.structured_content['value']) == dict(ready=True)
            root = await call({})
            assert root['location'] == dict(source='data', directory='')
            report['rows'].append(dict(scenario='default_data_root', bytes=size(root), complete=root['complete']))
            public = await call(dict(source='public', directory='icons'))
            node = next(entry for entry in public['entries'] if entry['kind'] == 'directory')
            descended = await call(node['next_call']['arguments'])
            assert descended['location']['directory'] == node['directory']
            svg = await call(dict(source='public', directory='icons/svg'))
            assert svg['entries'] and all(entry['kind'] == 'image' for entry in svg['entries'])
            assert all(entry['image']['src'].endswith('.svg') for entry in svg['entries'])
            report['rows'].append(dict(scenario='default_images', bytes=size(svg), complete=svg['complete']))
            pages, entries, cursor = [], [], None
            for _ in range(15):
                page = await call(dict(source='public', directory='icons/svg', **({'cursor': cursor} if cursor else {})))
                pages.append(page); entries.extend(page['entries']); cursor = page['next_cursor']
                if cursor is None:
                    break
            assert cursor is None and len(entries) == svg['total']
            assert len({entry['image']['src'] for entry in entries}) == len(entries)
            report['rows'].append(dict(scenario='complete_images_pagination', calls=len(pages), bytes=sum(size(page) for page in pages), count=len(entries), complete=True))
            expanded = await call(dict(source='public', directory='icons/svg', limit=100, max_bytes=48000))
            assert expanded['entries'] == entries[:100]
            report['rows'].append(dict(scenario='explicit_expansion', bytes=size(expanded), complete=expanded['complete']))
            selected = await call(dict(source='public', directory='icons/svg', name_contains='anchor'))
            assert selected['complete'] and selected['entries']
            assert all('anchor' in entry['name'].lower() for entry in selected['entries'])
            report['rows'].append(dict(scenario='literal_selection', bytes=size(selected), complete=True))
            report['passed'] = True
    except Exception as error:
        report.update(exception_type=type(error).__name__, last_call=calls)
    report['calls'] = calls
    return report


async def main():
    root = Path(__file__).resolve().parents[1]
    token = next(line.partition('=')[2].strip() for line in (root / '.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    async with Client(transport, timeout=20, init_timeout=10) as client:
        catalog = await client.list_tools()
        tool = next(tool for tool in catalog if tool.name == 'browse_journal_images')
        report = dict(catalog_bytes=size([tool.model_dump(mode='json') for tool in catalog]), tools=len(catalog), discovery_calls=1,
            tool_bytes=size(tool.model_dump(mode='json')))
        report.update(await verify(client))
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
