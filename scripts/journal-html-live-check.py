"""Read-only publisher HTML audit through MCP and the dedicated dev browser.

Run from the checkout: .venv/bin/python scripts/journal-html-live-check.py
Reads 18 named Seven Dooms pages from eight journals through localhost MCP,
reconstructs exact UTF-16 fragments, then validates in the browser's real DOM.
No writes, enrichment, rolls, asset fetch checks or DOM insertion. Does not reload
the browser: run ./scripts/actor-tools.sh refresh after module changes first.
Budgets: 48 MCP calls/120 seconds, 6 fragments/50,000 UTF-16 units per page,
48,000 JSON bytes per response, 30 seconds for one browser evaluation.
Source stays in memory; output contains aggregate measurements and page names.
Discovery adds one catalog call and checks the loaded authoring description.
"""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import httpx2 as httpx
import websockets


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = {
    'Frontmatter': ('Landing', 'Campaign Overview', 'Campaign Timeline'),
    'Ch 1: Bones and Ashes': ('Getting Started', 'Entrance', 'Commander’s Study'),
    'Ch 3: Whistles in the Dark': ('Ground Level', 'Hall of Threats', 'Tunch’s Workshop'),
    'Ch 9: The Red Bishop’s Gift': ('The Red Bishop’s Gift', 'K. Abandoned Village'),
    'Sandpoint Gazetteer A Doomed Town': ('Earning Reputation', 'Sandpoint Cathedral'),
    'Adventure Toolbox': ('Researching the Eighth', 'Clockwork Serpent'),
    'Handout #1': ('Handout #1',),
    "Player's Guide": ('Backgrounds', 'Suggested Character Options'),
}
READ_TOOLS = {'get_journal_tree', 'get_journal_contents', 'read_journal_page'}


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def utf16(value):
    return len(value.encode('utf-16-le')) // 2


class Reader:
    """Fixed read-only MCP allowlist with a session-wide call budget."""
    def __init__(self, client):
        self.client, self.calls, self.bytes = client, 0, 0

    async def call(self, name, args):
        if name not in READ_TOOLS or self.calls >= 48:
            raise ValueError('Read-only call/budget boundary')
        self.calls += 1
        response = await self.client.call_tool(name, args)
        if response.is_error or not isinstance(response.structured_content, dict):
            raise ValueError('Invalid MCP read response')
        result = response.structured_content
        measured = size(result)
        if measured > 48000:
            raise ValueError('Response byte budget')
        self.bytes += measured
        return result


async def read_page(reader, page):
    """Reconstruct a complete same-revision source or fail without partial proof."""
    cursor, revision, seen, fragments, end = None, None, set(), [], 0
    for _ in range(6):
        args = dict(page_uuid=page['page_uuid'], source='html', max_chars=8000, max_bytes=48000)
        if cursor is not None:
            args['cursor'] = cursor
        part = await reader.call('read_journal_page', args)
        revision = revision or part['revision']
        if (part['page_uuid'] != page['page_uuid'] or part['source'] != 'html'
                or not part['source_present'] or part['revision'] != revision
                or part['offset_units'] != 'UTF-16 code units' or part['offset'] != end
                or part['end_offset'] != end + utf16(part['content'])):
            raise ValueError('Source identity/revision/fragment mismatch')
        end = part['end_offset']
        if end > 50000:
            raise ValueError('Source size budget')
        fragments.append(part['content'])
        cursor = part['next_cursor']
        if cursor is None:
            if not part['complete'] or part['total_chars'] != end:
                raise ValueError('Incomplete source')
            return dict(name=page['name'], content=''.join(fragments))
        if part['complete'] or cursor in seen:
            raise ValueError('Invalid/repeated continuation')
        seen.add(cursor)
    raise ValueError('Source fragment budget')


async def collect_samples(reader):
    """Discover returned selectors; select the same bounded cross-section each run."""
    root = await reader.call('get_journal_tree', dict(max_depth=0, limit=100))
    folders = [n for n in root['children'] if n['kind'] == 'folder' and n['name'] == 'Seven Dooms for Sandpoint']
    if len(folders) != 1:
        raise ValueError('Expected one Seven Dooms folder in root sample')
    folder = await reader.call('get_journal_tree', dict(folder_id=folders[0]['folder_id'], max_depth=0, limit=100))
    if not folder['complete']:
        raise ValueError('Incomplete folder discovery')
    samples = []
    for journal_name, names in SAMPLE.items():
        journals = [n for n in folder['children'] if n['kind'] == 'journal' and n['name'] == journal_name]
        if len(journals) != 1:
            raise ValueError('Missing/ambiguous sample journal')
        pages, cursor, seen, revision = [], None, set(), None
        for _ in range(2):
            args = dict(journal_id=journals[0]['journal_id'], limit=50, max_bytes=48000)
            if cursor is not None:
                args['cursor'] = cursor
            part = await reader.call('get_journal_contents', args)
            revision = revision or part['revision']
            if part['revision'] != revision:
                raise ValueError('Contents changed')
            pages.extend(part['pages'])
            if all(any(p['name'] == name for p in pages) for name in names):
                break
            cursor = part['next_cursor']
            if cursor is None or cursor in seen:
                raise ValueError('Missing sample page or invalid continuation')
            seen.add(cursor)
        else:
            raise ValueError('Contents page budget')
        for name in names:
            matches = [p for p in pages if p['name'] == name]
            if len(matches) != 1:
                raise ValueError('Missing/ambiguous sample page')
            samples.append(await read_page(reader, matches[0]))
    return samples


def browser_expression(samples):
    """Serialize source as data; never evaluate its scripts or enrich notation."""
    if len(samples) != 18 or any(set(s) != {'name', 'content'} or not isinstance(s['content'], str)
                                 or utf16(s['content']) > 50000 for s in samples):
        raise ValueError('Expected eighteen bounded source samples')
    return """(async()=>{
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test')throw Error('Wrong development runtime');
const {normalizeTextHTML}=await import('/modules/foundry-mcp/scripts/textHtml.js');
const samples=SAMPLES;
const rows=samples.map(({name,content})=>{
  try {
    const expected=new DOMParser().parseFromString(content,'text/html').body.innerHTML;
    const actual=normalizeTextHTML(content,{links:true});
    return {name,accepted:true,unchanged_normalized_source:actual===expected,chars:content.length};
  }catch(e){return {name,accepted:false,error_code:e.rpcError?.code??'Unknown'};}
});
const unsafe=['<script>throw Error("must not execute")</script>','<img src="javascript:alert(1)">','<p onclick="run()">x</p>','<iframe src="https://example.org"></iframe>','<p data-action="run">x</p>','<img style="shape-outside:url(data:image/svg+xml,test)">'];
const rejected=unsafe.every(html=>{try{normalizeTextHTML(html,{links:true});return false;}catch(e){return e.rpcError?.code==='InvalidHTML';}});
return {passed:rows.every(r=>r.accepted&&r.unchanged_normalized_source)&&rejected,pages:rows.length,unsafe_rejected:rejected,rows};
})()""".replace('SAMPLES', json.dumps(samples))


def validate_endpoint(url, port):
    endpoint = urlsplit(url)
    if (endpoint.scheme != 'ws' or endpoint.hostname not in ('127.0.0.1', 'localhost')
            or endpoint.port != port or not endpoint.path.startswith('/devtools/page/')
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment):
        raise ValueError('Unexpected development debugger endpoint')


async def check_browser(samples):
    port = int((ROOT / '.browser-dev/chrome-profile/DevToolsActivePort').read_text().splitlines()[0])
    if not 1 <= port <= 65535:
        raise ValueError('Invalid development debugger port')
    async with httpx.AsyncClient(trust_env=False, timeout=5) as http:
        response = await http.get(f'http://127.0.0.1:{port}/json/list')
        response.raise_for_status()
        tabs = [t for t in response.json() if t.get('type') == 'page'
                and t.get('url', '').startswith('http://localhost:30000/')]
    if len(tabs) != 1:
        raise ValueError('Expected one dedicated development tab')
    endpoint = tabs[0]['webSocketDebuggerUrl']
    validate_endpoint(endpoint, port)
    async with websockets.connect(endpoint, max_size=2000000, open_timeout=5, close_timeout=5) as ws:
        await ws.send(json.dumps(dict(id=1, method='Runtime.evaluate', params=dict(
            expression=browser_expression(samples), awaitPromise=True, returnByValue=True))))
        async with asyncio.timeout(30):
            while True:
                reply = json.loads(await ws.recv())
                if reply.get('id') == 1:
                    if 'error' in reply or 'exceptionDetails' in reply.get('result', {}):
                        raise ValueError('Development browser evaluation failed')
                    return reply['result']['result']['value']


async def main():
    report, reader, stage = dict(passed=False), None, 'connect'
    try:
        token = next(line.partition('=')[2].strip() for line in (ROOT / '.env.mcp').read_text().splitlines()
                     if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
        async with Client(transport, timeout=20, init_timeout=10) as client:
            stage = 'discovery'
            catalog = await client.list_tools()
            tool = next(t for t in catalog if t.name == 'write_journal')
            report.update(discovery_calls=1, catalog_tools=len(catalog),
                          catalog_bytes=size([t.model_dump(mode='json') for t in catalog]),
                          write_journal_bytes=size(tool.model_dump(mode='json')))
            if 'CSS class lists' not in tool.description or 'passive IMG markup' not in tool.description:
                raise ValueError('Restart local MCP service to load the updated journal contract')
            reader = Reader(client)
            stage = 'read_sources'
            async with asyncio.timeout(120):
                samples = await collect_samples(reader)
            report['source_chars'] = sum(utf16(s['content']) for s in samples)
            stage = 'browser_validation'
            report.update(await check_browser(samples))
    except Exception as error:
        # Exception messages may contain private source, URLs or credentials.
        report.update(passed=False, stage=stage, exception_type=type(error).__name__)
    if reader is not None:
        report.update(mcp_calls=reader.calls, response_bytes=reader.bytes)
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
