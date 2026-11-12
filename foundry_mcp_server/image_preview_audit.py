"""Read-only localhost baseline: <=40 calls including discovery, <=120 seconds.

Run with .venv/bin/python -m foundry_mcp_server.image_preview_audit. Prints only
aggregate bytes/counts and fixed scenario labels. Reuses private journal/page
selectors in .local/image-preview-baseline-selection.json; never prints content,
paths, credentials, capability URLs or native errors. No model calls or fixtures.
"""
import asyncio
import json
import os
from pathlib import Path
import time

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import CallToolResult as ProtocolResult

MAX_CALLS = 40
TIMEOUT = 120


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8'))


class Measurements:
    """Aggregate immediately, retaining no arguments, responses or error text."""

    def __init__(self):
        self.calls = 0
        self.rows = {}

    def reserve(self):
        if self.calls >= MAX_CALLS:
            raise RuntimeError('CallBudgetExceeded')
        self.calls += 1

    def add(self, label, data, envelope, *, error=False):
        row = self.rows.setdefault(label, dict(calls=0, json_bytes=0, mcp_bytes=0, complete=False, errors=0))
        row['calls'] += 1
        row['json_bytes'] += size(data) if data is not None else 0
        row['mcp_bytes'] += size(envelope)
        row['errors'] += int(error)
        row['complete'] = not error and isinstance(data, dict) and data.get('complete') is True and data.get('next_cursor') is None


async def measure(client, selection_path):
    meter = Measurements()
    report = dict(passed=False, max_calls=MAX_CALLS, max_seconds=TIMEOUT)
    started = time.monotonic()

    async def call(label, tool, arguments):
        meter.reserve()
        result = await client.call_tool(tool, arguments, raise_on_error=False)
        data = result.structured_content
        envelope = ProtocolResult(content=result.content, structured_content=data,
            is_error=result.is_error, meta=result.meta).model_dump(mode='json', by_alias=True, exclude_none=True)
        meter.add(label, data, envelope, error=result.is_error)
        if result.is_error or not isinstance(data, dict):
            raise RuntimeError('ScenarioUnavailable')
        return data

    async def pages(label, tool, args, first=None):
        page = first if first is not None else await call(label, tool, args)
        while not page['complete']:
            if page.get('next_cursor') is None:
                raise RuntimeError('InvalidContinuation')
            page = await call(label, tool, {**args, 'cursor': page['next_cursor']})
        return page

    try:
        async with asyncio.timeout(TIMEOUT):
            meter.reserve()
            catalog = [tool.model_dump(mode='json') for tool in await client.list_tools(max_pages=1)]
            report.update(catalog_size=len(catalog), catalog_bytes=size(catalog), discovery_calls=1)
            guard = await call('runtime_guard', 'execute_javascript', dict(code="if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test')throw Error('Wrong development runtime');return JSON.stringify({version:game.version});"))
            report['foundry_version'] = json.loads(guard['value'])['version']
            await call('browse_default_root', 'browse_journal_images', {})
            args = dict(source='public', directory='icons/svg')
            await call('browse_default_images', 'browse_journal_images', args)
            await call('browse_literal', 'browse_journal_images', {**args, 'name_contains': 'anchor'})
            await call('browse_expanded', 'browse_journal_images', {**args, 'limit': 100, 'max_bytes': 48000})
            await pages('browse_complete', 'browse_journal_images', args)
            if selection_path.exists():
                selected = json.loads(selection_path.read_text())
            else:
                tree = await call('journal_navigation', 'get_journal_tree', dict(max_depth=8, limit=100))

                def journals(nodes):
                    for node in nodes:
                        if node.get('kind') == 'journal' and node.get('text_page_count', 0):
                            yield node
                        yield from journals(node.get('children', []))

                journal = next(journals(tree['children']))
                contents = await call('journal_navigation', 'get_journal_contents', dict(journal_id=journal['journal_id']))
                page = next(page for page in contents['pages'] if page.get('type') == 'text' and page.get('readable'))
                selected = dict(journal_id=journal['journal_id'], page_uuid=page['page_uuid'])
                selection_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                fd = os.open(selection_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as out:
                    json.dump(selected, out)
            journal_args = dict(journal_id=selected['journal_id'])
            await call('journal_contents_default', 'get_journal_contents', journal_args)
            await call('journal_contents_expanded', 'get_journal_contents', {**journal_args, 'select': dict(headings=True, categories=True, presentation=True, folder_path=True), 'max_bytes': 48000})
            page_args = dict(page_uuid=selected['page_uuid'])
            await call('journal_page_default', 'read_journal_page', page_args)
            await call('journal_page_expanded', 'read_journal_page', {**page_args, 'select': dict(references=True, source_metadata=True, folder_path=True), 'max_bytes': 48000})
            await pages('journal_page_complete', 'read_journal_page', page_args)
            report['passed'] = True
    except Exception as error:
        # Exception type only: messages may contain source data or signed URLs.
        report['failure_type'] = type(error).__name__
    report.update(calls=meter.calls, seconds=round(time.monotonic() - started, 3), rows=meter.rows)
    return report


async def main():
    root = Path(__file__).resolve().parents[1]
    token = next(line.partition('=')[2].strip() for line in (root / '.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    async with Client(transport, timeout=15, init_timeout=10) as client:
        report = await measure(client, root / '.local/image-preview-baseline-selection.json')
    print(json.dumps(report, sort_keys=True))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
