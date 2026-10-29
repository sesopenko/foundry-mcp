"""PF2e-specific journal -> world Actor -> owned action/spell acceptance.

Foundry14.369/PF2e8.6.1 existing test world only; exact persisted source/prose,
not current usability. Public fromUuid/toObject evidence is already adopted
by the document readers; this probe imports nothing and performs no writes.
https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html#toobject
"""
import asyncio
import hashlib
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180
GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS = """
const report=JSON.stringify(result);if(new TextEncoder().encode(report).length>16000)throw Error('Probe metadata bound');
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
FINGERPRINT = """
const actor=await foundry.utils.fromUuid(ACTOR),item=await foundry.utils.fromUuid(ITEM);
if(!actor||actor.documentName!=='Actor'||!actor.testUserPermission(game.user,'OBSERVER')||!item||item.documentName!=='Item'||!['action','spell'].includes(item.type)||item.parent!==actor||!item.testUserPermission(game.user,'OBSERVER'))throw Error('Wrong selected ownership');
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),b=>b.toString(16).padStart(2,'0')).join('');
const source=item.toObject(true),description=source.system?.description?.value;
if(typeof description!=='string'||!description.trim())throw Error('Selected ability/spell prose absent');
const result={source_hash:await hash(JSON.stringify([actor.toObject(true),source])),description_hash:await hash(description),description_length:description.length,type:item.type};
"""


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


async def verify(client, report=None):
    """PF2e-specific exact owned follow-up, bounded counts/bytes, safe results."""
    result = report if report is not None else {}
    result.update(passed=False)
    requested, completed, stage = 0, 0, 'discovery'

    def counts():
        result.update(mcp_calls=completed, requested_calls=requested, completed_calls=completed)

    async def call(name, args):
        nonlocal requested, completed
        requested += 1; counts()
        response = await client.call_tool(name, args)
        completed += 1; counts()
        return payload(response)

    async def fingerprint(actor_uuid, item_uuid):
        code = GUARD + FINGERPRINT.replace('ACTOR', json.dumps(actor_uuid)).replace('ITEM', json.dumps(item_uuid)) + CHUNKS
        value = (await call('execute_javascript', {'code': code}))['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    async def journal(page_uuid):
        cursor, revision, seen, fragments, references, last_end = None, None, set(), [], [], 0
        for _ in range(100):
            args = dict(page_uuid=page_uuid, source='html', max_chars=20000)
            if cursor:
                args['cursor'] = cursor
            page = await call('read_journal_page', args)
            assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 48000
            revision = revision or page['revision']; assert page['revision'] == revision
            assert page['offset'] == last_end and page['references_complete']
            last_end = page['end_offset']
            assert len(page['content'].encode('utf-16-le')) // 2 == last_end - page['offset']
            fragments.append(page['content']); references.extend(page['references'])
            cursor = page['next_cursor']
            if cursor is None:
                assert page['complete'] and last_end == page['total_chars']
                text = ''.join(fragments)
                return dict(hash=hashlib.sha256(text.encode()).hexdigest(), revision=revision, references=references, pages=len(fragments))
            assert not page['complete'] and cursor not in seen; seen.add(cursor)
        raise AssertionError('Journal page bound')

    try:
        requested += 1; counts()
        tools = {tool.name: tool for tool in await client.list_tools()}
        completed += 1; counts()
        for name in ('search_journals','read_journal_page','resolve_journal_reference','read_actor','list_actor_items','read_item'):
            assert tools[name].annotations.readOnlyHint
        stage = 'journal_search'
        cursor, seen, matches, revision = None, set(), [], None
        for _ in range(50):
            args = dict(query='Zantus', limit=2)
            if cursor:
                args['cursor'] = cursor
            page = await call('search_journals', args)
            revision = revision or page['revision']; assert revision == page['revision']
            matches.extend(row for row in page['matches'] if row['page_name'] == 'The Violated Grave')
            cursor = page['next_cursor']
            if cursor is None:
                assert page['complete']; break
            assert cursor not in seen; seen.add(cursor)
        else:
            raise AssertionError('Journal search bound')
        assert len(matches) == 1
        page_uuid = matches[0]['page_uuid']
        stage = 'journal_source_before'
        before_journal = await journal(page_uuid)
        actors = [reference for reference in before_journal['references'] if reference['target'].startswith('Actor.') and reference.get('resolve_next_call')]
        assert actors
        # Follow the actual returned resolver, not a constructed UUID call.
        resolver = actors[0]['resolve_next_call']
        assert resolver['tool'] == 'resolve_journal_reference'
        stage = 'journal_actor_resolution'
        resolved = await call(resolver['tool'], resolver['arguments'])
        assert resolved['status'] == 'resolved' and resolved['identity']['document_name'] == 'Actor'
        assert resolved['identity']['uuid'] == actors[0]['target']
        actor_call = resolved['next_call']
        assert actor_call['tool'] == 'read_actor'
        actor_uuid = resolved['identity']['uuid']
        actor = await call(actor_call['tool'], dict(actor_call['arguments'], sections=['identity']))
        assert actor['identity']['uuid'] == actor_uuid and actor['identity']['source_kind'] == 'world'
        stage = 'typed_owned_item'
        owned = await call('list_actor_items', dict(actor_call['arguments'], types=['action','spell'], limit=1, max_bytes=8000))
        assert len(owned['nodes']) == 1
        node = owned['nodes'][0]
        assert node['identity']['type'] in ('action','spell') and node['identity']['actor']['uuid'] == actor_uuid
        item_call = node['next_call']
        assert item_call['tool'] == 'read_item'
        item_uuid = node['identity']['uuid']
        stage = 'independent_source_before'
        before = await fingerprint(actor_uuid, item_uuid)
        stage = 'item_source_description'
        rows, cursor, revision, seen, item_pages = [], None, None, set(), 0
        for _ in range(200):
            args = dict(item_call['arguments'], sections=['source','description'], limit=7, max_bytes=48000)
            if cursor:
                args['cursor'] = cursor
            page = await call(item_call['tool'], args)
            assert page['identity']['uuid'] == item_uuid and page['identity']['type'] == before['type']
            assert page['identity']['type'] in ('action','spell') and page['identity']['actor']['uuid'] == actor_uuid
            assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 48000
            revision = revision or page['revision']; assert revision == page['revision']
            rows.extend(page['records']); item_pages += 1
            cursor = page['pagination']['next_cursor']
            if cursor is None:
                assert all(section['status'] == 'complete' for section in page['sections']); break
            assert cursor not in seen; seen.add(cursor)
        else:
            raise AssertionError('Item page bound')
        assert len({row['key'] for row in rows}) == len(rows)
        stage = 'exact_owned_prose'
        assert any(row['section'] == 'source' and row['kind'] == 'field' and row['raw'] for row in rows)
        fragments = [row for row in rows if row['kind'] == 'text' and row['text']['path'] == '/system/description/value']
        assert fragments and fragments[0]['text']['start'] == 0 and fragments[-1]['text']['complete']
        assert all(a['text']['end'] == b['text']['start'] for a,b in zip(fragments,fragments[1:]))
        text = ''.join(row['raw'][0]['value'] for row in fragments)
        assert text.strip() and hashlib.sha256(text.encode()).hexdigest() == before['description_hash']
        assert len(text.encode('utf-16-le')) // 2 == before['description_length']
        assert fragments[-1]['text']['end'] == before['description_length']
        assert all(raw['document_uuid'] == item_uuid and raw['basis'] == 'source' for row in rows for raw in row['raw'])
        stage = 'unchanged_sources'
        assert await fingerprint(actor_uuid, item_uuid) == before
        assert await journal(page_uuid) == before_journal
        result.update(passed=True, selected_item_type=before['type'], item_pages=item_pages, item_records=len(rows),
                      description_fragments=len(fragments), journal_pages=before_journal['pages'], exact_prose_verified=True,
                      journal_unchanged=True, source_fingerprints_unchanged=True)
    except Exception as error:
        result.update(passed=False, failure_stage=stage, exception_type=type(error).__name__)
    counts()
    return result


async def main():
    result = dict(passed=False)
    try:
        token = next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1] / '.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise RuntimeError('Missing local caller credential')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization':'Bearer '+token})
        async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                await verify(client,result)
    except Exception as error:
        result.update(passed=False, exception_type=type(error).__name__)
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
