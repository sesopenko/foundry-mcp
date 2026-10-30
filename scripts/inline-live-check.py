"""Bounded WISH-008 discovery, invocation and detached enrichment verification.

Existing localhost test world only. No documents/messages are created or edited,
no clicks, effects or roll evaluation. Maximum 30 MCP calls / 180 seconds.
Use --refresh to reload only the existing dedicated development test-world tab.
"""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import websockets
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ROOT = Path(__file__).resolve().parents[1]
GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


async def refresh(inspect_console=False):
    """Reload or inspect only the dedicated localhost test-world profile."""
    port = (ROOT / '.browser-dev/chrome-profile/DevToolsActivePort').read_text().splitlines()[0]
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError('Invalid development port')
    async with httpx.AsyncClient(trust_env=False) as http:
        response = await http.get(f'http://127.0.0.1:{port}/json/list')
        response.raise_for_status()
        tabs = [t for t in response.json() if t.get('type') == 'page' and t.get('url', '').startswith('http://localhost:30000/')]
    if len(tabs) != 1:
        raise ValueError('Expected dedicated Foundry tab')
    endpoint = urlsplit(tabs[0]['webSocketDebuggerUrl'])
    if endpoint.scheme != 'ws' or endpoint.hostname not in ('localhost', '127.0.0.1') or endpoint.port != int(port) or not endpoint.path.startswith('/devtools/page/') or endpoint.query or endpoint.fragment or endpoint.username:
        raise ValueError('Unexpected debugger endpoint')
    async with websockets.connect(tabs[0]['webSocketDebuggerUrl']) as socket:
        if inspect_console:
            await socket.send(json.dumps(dict(id=2, method='Runtime.enable')))
            errors = 0
            error_sources = []
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), 10))
                if event.get('method') == 'Runtime.consoleAPICalled' and event.get('params', {}).get('type') == 'error':
                    errors += 1
                    params = event.get('params', {})
                    text = ' '.join(a.get('value', '') for a in params.get('args', []) if isinstance(a.get('value'), str)).lower()
                    categories = [word for word in ('canvas', 'webgl', 'texture', 'inline', 'damage', 'embed', 'socket', 'authentication') if word in text]
                    frames = params.get('stackTrace', {}).get('callFrames', [])
                    error_sources.append(dict(categories=categories, sources=sorted({urlsplit(f.get('url', '')).path for f in frames})[:5]))
                if event.get('id') == 2:
                    break
            print(json.dumps(dict(console_errors_since_refresh=errors, error_sources=error_sources)))
            return
        await socket.send(json.dumps(dict(id=1, method='Runtime.evaluate', params=dict(expression='(()=>{' + GUARD + 'setTimeout(()=>location.reload(),0);return true;})()', returnByValue=True))))
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), 10))
            if event.get('id') == 1:
                assert event.get('result', {}).get('result', {}).get('value') is True
                break
    print(json.dumps(dict(refresh_requested=True)))


async def verify(client):
    """PF2e-specific14.369/8.6.1 syntax smoke check, not target/Actor automation."""
    calls = 0
    measurements = []

    async def call(name, arguments):
        nonlocal calls
        if calls >= 30:
            raise RuntimeError('Call budget exhausted')
        calls += 1
        result = await client.call_tool(name, arguments)
        measurements.append(dict(tool=name, response_bytes=size(dict(content=[b.model_dump(mode='json') for b in result.content], structuredContent=result.structured_content)), complete=True))
        return result

    async def browser(body):
        result = await call('execute_javascript', dict(code=GUARD + body))
        return json.loads(result.structured_content['value'])

    calls += 1
    catalog = await client.list_tools()
    names = ['create_pf2e_inline_' + suffix for suffix in ('roll', 'check', 'embed')]
    selected = [t for t in catalog if t.name in names]
    assert len(selected) == 3
    assert all(t.outputSchema and not t.inputSchema['additionalProperties'] for t in selected)
    assert 'discriminator' in next(t for t in selected if t.name.endswith('_roll')).inputSchema['properties']['roll']
    # Obtain canonical identity from a public compendium document, not a name.
    before = await browser("""
const pack=game.packs.get('pf2e.feats-srd');if(!pack?.testUserPermission(game.user,'OBSERVER'))throw Error('No readable feat pack');
const index=await pack.getIndex();const id=index.contents[0]?._id;if(!id)throw Error('No compendium Item');
const item=await pack.getDocument(id);if(!item?.testUserPermission(game.user,'OBSERVER'))throw Error('No readable Item');
return JSON.stringify({uuid:item.uuid,messages:game.messages.size,journals:game.journal.size,items:game.items.size,core:game.version,system:game.system.version});
""")
    scenarios = [
        ('roll', {'roll': {'kind': 'non_damage', 'amount': {'dice': [{'count': 1, 'faces': 20}], 'modifier': 17}, 'flavor': 'Counteract'}}),
        ('roll', {'roll': {'kind': 'non_damage', 'amount': {'modifier': 4}, 'visibility': 'gm'}}),
        ('roll', {'roll': {'kind': 'non_damage', 'amount': {'dice': [{'count': 1, 'faces': 20}]}, 'visibility': 'blind'}}),
        ('roll', {'roll': {'kind': 'non_damage', 'amount': {'dice': [{'count': 1, 'faces': 20}]}, 'visibility': 'self'}}),
        ('roll', {'roll': {'kind': 'damage', 'damage': [{'type': 'fire', 'amount': {'dice': [{'count': 2, 'faces': 6}], 'modifier': 3}}], 'label': 'Flaming burst'}}),
        ('roll', {'roll': {'kind': 'damage', 'damage': [{'type': 'slashing', 'amount': {'dice': [{'count': 2, 'faces': 6}], 'modifier': 4}, 'precision': {'dice': [{'count': 1, 'faces': 6}]}, 'splash': {'modifier': 2}}, {'type': 'fire', 'amount': {'dice': [{'count': 1, 'faces': 6}]}, 'persistent': True}], 'options': ['area-damage']}}),
        ('check', {'statistic': 'reflex', 'dc': 20, 'basic': True}),
        ('check', {'statistic': 'perception', 'against': 'deception', 'roller_role': 'target', 'show_dc': 'all', 'adjustment': -2, 'immutable': True, 'name': 'Notice', 'traits': ['secret'], 'options': ['action:seek'], 'override_traits': True}),
        ('check', {'statistic': 'engineering-lore', 'defense': 'perception', 'label': 'Engineering'}),
        ('embed', {'item_uuid': before['uuid']}),
        ('embed', {'item_uuid': before['uuid'], 'suppress_hr': True}),
    ]
    texts = []
    for suffix, args in scenarios:
        result = await call('create_pf2e_inline_' + suffix, args)
        assert len(result.content) == 1 and result.content[0].text == result.structured_content['text']
        texts.append(result.content[0].text)
    inspection = (ROOT / 'scripts/inline-enrichment.mjs').read_text().replace('export function', 'function')
    enrichment = await browser(inspection + '\nconst texts=' + json.dumps(texts) + ';const uuid=' + json.dumps(before['uuid']) + ';' + """
const item=await foundry.utils.fromUuid(uuid);
const journal=[...game.journal.values()].find(j=>j.testUserPermission(game.user,'OBSERVER')&&j.pages.contents.length)?.pages.contents[0];
const contexts=[['chat',null],['journal',journal],['item_description',item]];
const rows=[];
for(const [context,relativeTo] of contexts){
 if(context==='journal'&&!relativeTo){rows.push({context,available:false});continue;}
 let enriched=0;
 for(const text of texts){
  const html=await foundry.applications.ux.TextEditor.implementation.enrichHTML(text,{relativeTo:relativeTo??undefined});
  // Inspect only detached generated markup, never sheet/UI DOM.
  const container=document.createElement('div');container.innerHTML=html;
  if(!isInlineEnrichment(text,container))throw Error('Unenriched markup: '+context+' case '+texts.indexOf(text));
  enriched++;
 }
 rows.push({context,available:true,enriched});
}
return JSON.stringify({contexts:rows,messages:game.messages.size,journals:game.journal.size,items:game.items.size});
""")
    assert all(enrichment[k] == before[k] for k in ('messages', 'journals', 'items'))
    assert all(row.get('available') and row.get('enriched') == len(texts) for row in enrichment['contexts'])
    return dict(passed=True, calls=calls, call_cap=30, time_cap_seconds=180, catalog_tools=len(catalog), catalog_bytes=size([t.model_dump(mode='json') for t in catalog]), added_catalog_bytes=size([t.model_dump(mode='json') for t in selected]), measurements=measurements, runtime={k: before[k] for k in ('core', 'system')}, enrichment=enrichment['contexts'], document_message_counts_unchanged=True, tokens=None)


async def main(do_refresh, inspect_console=False):
    async with asyncio.timeout(180):
        if do_refresh or inspect_console:
            await refresh(inspect_console)
            return
        token = next(line.partition('=')[2].strip() for line in (ROOT / '.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise ValueError('Missing local caller credential')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
        async with Client(transport, timeout=20, init_timeout=10) as client:
            print(json.dumps(await verify(client)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--console', action='store_true')
    args = parser.parse_args()
    asyncio.run(main(args.refresh, args.console))
