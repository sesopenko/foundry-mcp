"""Bounded chat acceptance in the existing localhost test world, never a game session.

At most60 MCP calls/180 seconds; aggregates only, no private history in output.
PF2e-specific fixture uses only character type/name/flags on14.369/8.6.1,
no source or derived mechanics. Public Actor/ChatMessage create/delete/getFlag
APIs: https://foundryvtt.com/api/v14/classes/foundry.documents.ChatMessage.html
Cleanup is development-only, exact run marker and request IDs, never a chat tool.
"""
import asyncio
import json
from html.parser import HTMLParser
from pathlib import Path
import time
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ROOT = Path(__file__).resolve().parents[1]
GUARD = """if(location.origin!=='http://localhost:30000'||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1'||!game.ready||!game.user.isGM)throw Error('Wrong test runtime');"""


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


def assert_stored_markup(content):
    """Verify the synthetic message's stored formatting and deferred-roll content."""
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_link=False
            self.labels=[]
        def handle_starttag(self, tag, attrs):
            if tag=='a':
                self.in_link=True
                self.labels.append('')
        def handle_endtag(self, tag):
            if tag=='a': self.in_link=False
        def handle_data(self, data):
            if self.in_link: self.labels[-1]+=data
    links=Links()
    links.feed(content)
    # Foundry/PF2e persists deferred-roll source as HTML; assert its ordinary
    # link/label semantics rather than depending on publisher CSS/data attributes.
    assert 'font-size' in content and '@Check[' in content and '1' in links.labels


async def verify(client):
    marker = 'chat-accept-' + uuid4().hex[:20]
    calls = 0
    report = {'passed': False, 'call_cap': 60, 'seconds_cap': 180}
    actor_id = None
    sent = []
    sent_rows = []
    stage = 'discovery'
    started = time.monotonic()

    async def call(name, args, error=False):
        nonlocal calls
        calls += 1
        if calls > 60:
            raise RuntimeError('Call budget exhausted')
        result = await client.call_tool(name, args, raise_on_error=not error)
        return result if error else payload(result)

    async def js(source):
        result = await call('execute_javascript', {'code': GUARD + source})
        value = result.get('value')
        if not isinstance(value, str):
            raise RuntimeError('Unexpected development result')
        return json.loads(value)

    try:
        calls += 1
        catalog = await client.list_tools()
        tools = {t.name: t for t in catalog}
        names = ['read_chat_messages', 'read_chat_message_content', 'send_chat_message', 'get_pathfinder_writing_style_guide']
        assert all(n in tools and tools[n].output_schema for n in names)
        assert not any('delete' in n or 'clear_chat' in n for n in tools)
        report.update(catalog_count=len(catalog), catalog_bytes=size([t.model_dump(mode='json') for t in catalog]),
                      chat_discovery_bytes=size([tools[n].model_dump(mode='json') for n in names]))
        initial = await call('read_chat_messages', {})
        report['initial_default_bytes'] = size(initial)
        # Complete the existing small development history without printing bodies.
        history = list(initial['messages'])
        cursor = initial['cursor']
        for _ in range(10):
            if not initial['has_more']:
                break
            initial = await call('read_chat_messages', {'request': {'cursor': cursor}})
            cursor = initial['cursor']
            history.extend(initial['messages'])
        assert not initial['has_more']
        assert len({m['id'] for m in history}) == len(history)
        report['initial_history_count'] = len(history)
        stage = 'fixture'
        fixture = await js("""
const marker=MARKER;
const actor=await foundry.documents.Actor.implementation.create({name:marker,type:'character',flags:{'foundry-mcp':{chatFixture:marker}}});
return JSON.stringify({id:actor.id,user:game.user.id,gms:[...game.users.values()].filter(u=>u.isGM).map(u=>u.id)});
""".replace('MARKER', json.dumps(marker)))
        actor_id = fixture['id']
        found = await call('search_actors', {'query': marker, 'types': ['character'], 'limit': 1})
        assert found['nodes'][0]['identity']['id'] == actor_id
        modes = ['Public as User', 'private to game masters', 'blind to game masters', 'self only', 'public as character']
        html = f'<h2 style="text-align:center">{marker}</h2><p><strong>Bold</strong> <em>italic</em> <u>underline</u> <s>strike</s><sub>sub</sub><sup>sup</sup><br><span style="font-family:Arial;font-size:18px;color:#123456;background-color:#ffffff;font-weight:bold;font-style:italic;text-decoration:underline">Font</span></p><blockquote>Quote</blockquote><pre><code>Code</code></pre><ul><li>List</li></ul><ol><li>Ordered</li></ol><table><thead><tr><th>Head</th></tr></thead><tbody><tr><td colspan="2">Cell</td></tr></tbody></table><hr>'
        roll = await call('create_pf2e_inline_roll', {'roll': {'kind': 'non_damage', 'amount': {'modifier': 1}}})
        check = await call('create_pf2e_inline_check', {'statistic': 'reflex', 'dc': 20, 'basic': True})
        html += '<p>' + roll['text'] + ' ' + check['text'] + '</p>'
        stage = 'five_send_modes'
        for i, mode in enumerate(modes):
            request = dict(request_id=f'{marker}-{i}', mode=mode, content=html)
            if i == 4:
                request['actor_id'] = actor_id
            result = await call('send_chat_message', {'request': request})
            sent.append(result['id'])
            sent_rows.append(result)
            assert result['author']['id'] == fixture['user']
            assert result['speaker']['actor'] == (actor_id if i == 4 else None)
            assert result['blind'] == (i == 2)
            assert result['whisper'] == (fixture['gms'] if i in (1, 2) else [fixture['user']] if i == 3 else [])
            assert result['speaker']['alias']
            report.setdefault('send_bytes', []).append(size(result))
        repeated = await call('send_chat_message', {'request': request})
        assert repeated['id'] == sent[-1]
        stage = 'incremental_history'
        incremental = await call('read_chat_messages', {'request': {'cursor': cursor, 'limit': 2}})
        rows = list(incremental['messages'])
        total = size(incremental)
        page_calls = 1
        while incremental['has_more']:
            incremental = await call('read_chat_messages', {'request': {'cursor': incremental['cursor'], 'limit': 2}})
            rows.extend(incremental['messages'])
            total += size(incremental)
            page_calls += 1
        expected = [m['id'] for m in sorted(sent_rows, key=lambda m: (m['timestamp'], m['id']))]
        report['incremental_identity_match'] = set(m['id'] for m in rows) == set(sent)
        report['incremental_unique'] = len({m['id'] for m in rows}) == len(rows)
        report['incremental_order_match'] = [m['id'] for m in rows] == expected
        report['roll_source_normalized_to_html'] = all('[[/r ' not in m['content'] for m in rows)
        stage = 'incremental_order'
        assert [m['id'] for m in rows] == expected
        stage = 'persisted_html_markers'
        for row in rows:
            assert_stored_markup(row['content'])
        report.update(incremental_pages=page_calls, incremental_bytes=total, incremental_count=len(rows))
        full = await call('read_chat_messages', {'request': {'limit': 2}})
        full_count, full_bytes, full_calls = len(full['messages']), size(full), 1
        while full['has_more']:
            full = await call('read_chat_messages', {'request': {'limit': 2, 'cursor': full['cursor']}})
            full_count += len(full['messages'])
            full_bytes += size(full)
            full_calls += 1
        assert full_count == len(history) + len(sent)
        report.update(repeated_full_history_count=full_count, repeated_full_history_bytes=full_bytes, repeated_full_history_calls=full_calls)
        empty = await call('read_chat_messages', {'request': {'cursor': incremental['cursor']}})
        assert empty['messages'] == [] and empty['has_more'] is False
        report['poll_empty_bytes'] = size(empty)
        after = await call('read_chat_messages', {'request': {'after_id': expected[2]}})
        assert [m['id'] for m in after['messages']] == expected[3:]
        stage = 'html_and_visibility'
        observed = await js("""
const ids=IDS;
const rows=ids.map(id=>{const m=game.messages.get(id);const data=m.toObject(true);return {id,visible:m.visible,contentVisible:m.isContentVisible,style:data.style,rolls:data.rolls.length};});
const normalized=await import('/modules/foundry-mcp/scripts/chat.js');
const bad=['<img src="bad">','<script>1</script>','<p onclick="bad()">bad</p>','<span style="position:fixed">bad</span>'];
let rejected=0;for(const s of bad){try{normalized.normalizeChatHTML(s);}catch{rejected++;}}
return JSON.stringify({rows,rejected});
""".replace('IDS', json.dumps(sent)))
        assert all(r['visible'] and r['contentVisible'] and r['rolls'] == 0 for r in observed['rows'])
        assert [r['style'] for r in observed['rows']] == [1, 1, 1, 1, 2]
        assert observed['rejected'] == 4
        report['html_invalid_rejections'] = 4
        stage = 'oversized_content'
        big_text = '<p>' + marker + 'x' * 7999 + '😀' + 'y' * 3000 + '</p>'
        big_request = dict(request_id=marker+'-big', mode='self only', content=big_text)
        big = await call('send_chat_message', {'request': big_request})
        sent.append(big['id'])
        compact = await call('read_chat_messages', {'request': {'cursor': empty['cursor']}})
        assert len(compact['messages']) == 1 and compact['messages'][0]['content_available_separately']
        fragments = []
        args = {'message_id': big['id']}
        fragment_bytes = 0
        while True:
            fragment = await call('read_chat_message_content', args)
            fragments.append(fragment['content'])
            fragment_bytes += size(fragment)
            if fragment['next_offset'] is None:
                break
            args = dict(message_id=big['id'], offset=fragment['next_offset'], revision=fragment['revision'])
        assert ''.join(fragments) == big_text
        report.update(large_fragment_calls=len(fragments), large_fragment_bytes=fragment_bytes, large_default_bytes=size(compact))
        stage = 'guide_and_errors'
        guide = await call('get_pathfinder_writing_style_guide', {})
        report['guide_bytes'] = size(guide)
        assert guide['text'].endswith('and look it up!')
        missing = await call('send_chat_message', {'request': dict(request_id=marker+'-missing', mode=modes[4], actor_id='MCPNoSuchActor00', content=marker)}, error=True)
        assert missing.is_error
        invalid = await call('send_chat_message', {'request': dict(request_id=marker+'-invalid', mode='Clear chat log', content=marker)}, error=True)
        assert invalid.is_error
        report.update(passed=True, five_modes_verified=True, exact_content_reconstructed=True, duplicates_omitted=True)
    except Exception as exc:
        report.update(failed_stage=stage, exception_type=type(exc).__name__)
    finally:
        # Exact marker AND membership checks keep cleanup bounded even after a timeout.
        try:
            cleanup = await js("""
const marker=MARKER;
const messages=[...game.messages.values()].filter(m=>{const id=m.getFlag('foundry-mcp','requestId');return typeof id==='string'&&id.startsWith(marker+'-')&&m.content.includes(marker);});
if(messages.length>10)throw Error('Unexpected fixture count');
for(const m of messages)await m.delete();
const actors=[...game.actors.values()].filter(a=>a.name===marker&&a.getFlag('foundry-mcp','chatFixture')===marker);
if(actors.length>1)throw Error('Unexpected Actor count');
for(const a of actors)await a.delete();
return JSON.stringify({messages_removed:messages.length,actors_removed:actors.length});
""".replace('MARKER', json.dumps(marker)))
            report['cleanup'] = cleanup
        except Exception as exc:
            report.update(passed=False, cleanup_error=type(exc).__name__)
        report.update(mcp_calls=calls, elapsed_seconds=round(time.monotonic()-started, 2))
    return report


async def main():
    token = next(line.partition('=')[2].strip() for line in (ROOT/'.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer '+token})
    async with Client(transport, timeout=20, init_timeout=10) as client:
        async with asyncio.timeout(180):
            report = await verify(client)
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
