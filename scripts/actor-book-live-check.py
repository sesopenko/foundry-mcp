"""PF2e-specific 8.6.1 genuine book fixture check in the existing test world.

Creates two standalone books only, then removes exact run-marked fixtures.
Public v14 Item create/delete/getFlag/toObject and compendium index/fromUuid:
https://foundryvtt.com/api/v14/classes/foundry.documents.Item.html
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts
No existing document updates, imports, activation, enrichment, rolls or chat.
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
import uuid

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180
DESCRIPTION = '<p>' + ('界😀 é &amp; ' * 1400) + '</p>'
GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS = """
const encoded=JSON.stringify(result);
return Array.from({length:Math.ceil(encoded.length/800)},(_,i)=>encoded.slice(i*800,(i+1)*800));
"""


def payload(result):
    """Decode MCP structured results without logging private fixture content."""
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


async def verify(client, world_id, run_id, progress=None):
    """PF2e-specific test-world book source/relationship proof with exact cleanup.

    Effectively mutable only for this run's standalone book fixtures. Every JS
    request guards localhost, world, GM and pinned runtime before any operation.
    Cleanup searches exact flags even if creation response was lost.
    """
    if world_id != 'test' or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', run_id):
        raise ValueError('Explicit test world and safe run marker required')
    calls = 0
    summary = progress if progress is not None else {}
    summary.update(passed=False, cleanup_verified=False)
    stage = 'discovery'
    totals = dict(books=0, pages=0, raw_witnesses=0, relationships=0, description_fragments=0)

    async def call(name, arguments):
        nonlocal calls
        calls += 1
        return payload(await client.call_tool(name, arguments))

    async def js(code):
        result = await call('execute_javascript', {'code': GUARD + code + CHUNKS})
        value = result['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    marker = json.dumps(run_id)
    cleanup = """
globalThis.__mcpBookProbes??=new Map();const state=globalThis.__mcpBookProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpBookProbes.set(RUN,state);state.closed=true;
for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
const marked=game.items.filter(i=>i.type==='book'&&i.getFlag('foundry-mcp','bookProbe')===RUN);
for(const item of marked){GUARD;await item.delete();}
const result={deleted:marked.length,pending:state.pending,remaining:game.items.filter(i=>i.getFlag('foundry-mcp','bookProbe')===RUN).length};
""".replace('RUN', marker).replace('GUARD', GUARD)
    try:
        tools = {tool.name: tool for tool in await client.list_tools()}
        calls += 1
        tool = tools['read_item']
        assert tool.annotations.readOnlyHint and not tool.inputSchema['additionalProperties']
        for text in ('book Items expose', 'book_content_reference', '/system/contents/N', 'next_cursor'):
            assert text in tool.description
        registry = await call('get_actor_types', {})
        support = next(row for row in registry['item_types'] if row['type'] == 'book')
        assert support['source_supported'] and support['mapped_supported'] and not support['effective_supported']
        # Bound discovery to existing indexes, hydrate only the first matching
        # definition of each type; no pack imports or bulk document hydration.
        stage = 'fixture_creation'
        fixtures = await js("""
globalThis.__mcpBookProbes??=new Map();const state=globalThis.__mcpBookProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpBookProbes.set(RUN,state);
const selected={};let searched=0;
for(const pack of game.packs){if(pack.documentName!=='Item'||!pack.testUserPermission(game.user,'OBSERVER'))continue;if(++searched>40)throw Error('Pack bound');
const index=await pack.getIndex({fields:['type']});
for(const type of ['equipment','spell']){if(selected[type])continue;const entry=index.find(e=>e.type===type);if(!entry)continue;const item=await foundry.utils.fromUuid(pack.getUuid(entry._id));if(item?.type===type&&item.testUserPermission(game.user,'OBSERVER'))selected[type]={uuid:item.uuid,name:item.name,type:item.type};}if(selected.equipment&&selected.spell)break;}
if(!selected.equipment||!selected.spell)throw Error('Missing definitions');
const result=[];
for(const category of ['formula','spell']){const target=selected[category==='formula'?'equipment':'spell'];
const description='<p>'+('界😀 é &amp; '.repeat(1400))+'</p>';
GUARD;
if(state.closed)throw Error('Probe closed');state.pending++;let item;
try{item=await Item.implementation.create({name:'MCP book verification '+category,type:'book',flags:{'foundry-mcp':{bookProbe:RUN}},system:{category,capacity:100,contents:[target.uuid,target.uuid,'Item.MCPMissingBook00'],description:{value:description},rules:[]}});
if(!item||item.type!=='book'||item.getFlag('foundry-mcp','bookProbe')!==RUN)throw Error('Fixture creation failed');
if(state.closed){GUARD;await item.delete();throw Error('Probe closed during creation');}}finally{state.pending--;}
const source=item.toObject(true);const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(source)))),b=>b.toString(16).padStart(2,'0')).join('');
result.push({uuid:item.uuid,category,target,description_matches:source.system.description.value===description,hash});}
""".replace('RUN', marker).replace('GUARD', GUARD))
        assert len(fixtures) == 2
        for fixture in fixtures:
            assert fixture['description_matches'] is True
            async def pages(section):
                rows, cursor, seen, revision = [], None, set(), None
                for _ in range(180):
                    arguments = dict(item_uuid=fixture['uuid'], sections=[section], limit=7, max_bytes=8000)
                    if cursor:
                        arguments['cursor'] = cursor
                    page = await call('read_item', arguments)
                    assert page['identity']['uuid'] == fixture['uuid'] and page['identity']['type'] == 'book'
                    assert page['identity']['source_kind'] == 'world' and page['identity']['actor'] is None
                    assert page['identity']['id'] == fixture['uuid'].split('.')[-1]
                    assert page['runtime'] == dict(core_version='14.369', system_id='pf2e', system_version='8.6.1')
                    assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 8000
                    revision = revision or page['revision']
                    assert revision == page['revision']
                    rows.extend(page['records']);totals['pages'] += 1
                    cursor = page['pagination']['next_cursor']
                    if cursor is None:
                        status = next(row for row in page['sections'] if row['name'] == section)['status']
                        assert status == 'complete'
                        assert len({row['key'] for row in rows}) == len(rows)
                        return rows
                    assert cursor not in seen
                    seen.add(cursor)
                raise AssertionError('Page bound')

            stage = 'source_read'
            source = await pages('source')
            witnesses = [raw for row in source for raw in row['raw']]
            assert any(raw['path'] == '/system/category' and raw['value'] == fixture['category'] for raw in witnesses)
            assert any(raw['path'] == '/system/capacity' and raw['value'] == 100 for raw in witnesses)
            assert [raw['value'] for raw in witnesses if raw['path'].startswith('/system/contents/')] == [fixture['target']['uuid'], fixture['target']['uuid'], 'Item.MCPMissingBook00']
            stage = 'independent_source_check'
            for offset in range(0, len(witnesses), 40):
                batch = witnesses[offset:offset + 40]
                checks = await js('const claims=' + json.dumps(batch) + ';' + """
const result=[];for(const claim of claims){const item=await foundry.utils.fromUuid(claim.document_uuid);if(!item||item.getFlag('foundry-mcp','bookProbe')!==RUN)throw Error('Wrong fixture');let value=item.toObject(true),present=true;for(const key of claim.path.slice(1).split('/').map(k=>k.replace(/~1/g,'/').replace(/~0/g,'~'))){if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)){present=false;break;}value=value[key];}result.push({present,...(present?{value}:{})});}
""".replace('RUN', marker))
                assert checks == [{key: raw[key] for key in ('present', 'value') if key in raw} for raw in batch]
                assert all(raw['basis'] == 'source' and raw['document_uuid'] == fixture['uuid'] for raw in batch)
            stage = 'description_read'
            description = await pages('description')
            fragments = [row for row in description if row['kind'] == 'text' and row['raw'][0]['path'] == '/system/description/value']
            # Exact prose is represented by ordered UTF-16 source fragments.
            text = ''.join(row['raw'][0]['value'] for row in fragments)
            assert text == DESCRIPTION and len(fragments) > 1
            stage = 'relationships_read'
            relationships = await pages('relationships')
            refs = sorted((row for row in relationships if row['mapped']['concept'] == 'book_content_reference'), key=lambda row: int(row['key'].rsplit(':', 1)[1]))
            assert len(refs) == 3
            for index, row in enumerate(refs):
                assert row['raw'][0]['path'] == f'/system/contents/{index}'
                value = row['mapped']['value']
                if index < 2:
                    assert value['status'] == 'resolved' and value['target_uuid'] == fixture['target']['uuid']
                    assert value['type'] == fixture['target']['type'] and value['name'] == fixture['target']['name']
                else:
                    assert value == dict(status='missing', target_uuid=None)
            follow = await call('read_item', dict(item_uuid=fixture['target']['uuid'], sections=['identity'], limit=7, max_bytes=8000))
            assert follow['identity']['uuid'] == fixture['target']['uuid'] and follow['identity']['type'] == fixture['target']['type']
            effective = await call('read_item', dict(item_uuid=fixture['uuid'], sections=['effective'], limit=7, max_bytes=8000))
            assert next(row for row in effective['sections'] if row['name'] == 'effective')['status'] == 'unsupported'
            stage = 'source_fingerprint'
            assert await js('const item=await foundry.utils.fromUuid(' + json.dumps(fixture['uuid']) + ");if(item?.getFlag('foundry-mcp','bookProbe')!==" + marker + ")throw Error('Wrong fixture');const result=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(item.toObject(true))))),b=>b.toString(16).padStart(2,'0')).join('');") == fixture['hash']
            totals['books'] += 1;totals['raw_witnesses'] += len(witnesses);totals['relationships'] += len(refs);totals['description_fragments'] += len(fragments)
        summary.update(passed=True, source_unchanged=True)
    except Exception as error:
        summary.update(failure_stage=stage, exception_type=type(error).__name__)
    except asyncio.CancelledError:
        summary.update(failure_stage=stage, exception_type='CancelledError')
        raise
    finally:
        # Separate deadline remains active after an outer verification timeout.
        # Marker lookup also covers creation committed before a lost response.
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                removed = await asyncio.shield(js(cleanup))
            assert removed['remaining'] == 0 and removed['pending'] == 0
            summary['cleanup_verified'] = True
        except Exception as error:
            summary.update(passed=False, cleanup_exception_type=type(error).__name__)
            summary.setdefault('failure_stage', 'cleanup')
        summary.update(mcp_calls=calls, **totals)
    return summary


async def main(world_id, discovery_only=False):
    """Connect only to local MCP with bounded requests and a unique run marker."""
    token = None
    for line in (Path(__file__).resolve().parent.parent / '.env.mcp').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator and key.strip() == 'FOUNDRY_MCP_CALLER_TOKEN':
            token = value.strip()
    if not token:
        raise RuntimeError('Missing local caller credential')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    result = dict(passed=False, cleanup_verified=False)
    try:
        async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                if discovery_only:
                    available = {tool.name: tool for tool in await client.list_tools()}
                    assert available['read_item'].annotations.readOnlyHint
                    registry = payload(await client.call_tool('get_actor_types', {}))
                    book = next(row for row in registry['item_types'] if row['type'] == 'book')
                    assert book['source_supported'] and book['mapped_supported'] and not book['effective_supported']
                    assert book['verification']['live']['status'] == 'passed'
                    result = dict(passed=True, discovery_verified=True, runtime_checked=False,
                                  fixtures_created=False, mcp_calls=2)
                else:
                    result = await verify(client, world_id, uuid.uuid4().hex, result)
    except Exception as error:
        result.update(passed=False, exception_type=type(error).__name__)
        result.setdefault('failure_stage', 'connection')
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id', required=True, choices=['test'])
    parser.add_argument('--discovery-only', action='store_true', help='Check published support without creating fixtures.')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.world_id, args.discovery_only)))
