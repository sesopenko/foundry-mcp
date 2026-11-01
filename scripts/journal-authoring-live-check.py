"""Bounded journal-authoring workflow in the existing localhost test world.

Only random-run-marked new journals/folders are mutated or deleted. Existing
documents and user records are fingerprinted/read, never written. Budget60
MCP calls/180 seconds plus one reserved cleanup call/30 seconds. No game session.
Public core14 Document create/update/delete/getFlag/toObject APIs:
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
"""
import asyncio
import json
from pathlib import Path
import re
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
"""
STATE = """
const prefix='journal-'+RUN+'-';
const marked=doc=>Object.keys(doc.getFlag('foundry-mcp','journalWrites')??{}).some(key=>key.startsWith(prefix));
const journals=()=>[...game.journal.values()].filter(marked);
const folders=()=>[...game.folders.values()].filter(marked);
"""
FINGERPRINT = STATE + """
const source=JSON.stringify({journals:[...game.journal.values()].filter(doc=>!marked(doc)).map(doc=>doc.toObject(true)),
 folders:[...game.folders.values()].filter(doc=>!marked(doc)).map(doc=>doc.toObject(true)),users:[...game.users.values()].map(doc=>doc.toObject(true))});
const result={hash:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(source))),b=>b.toString(16).padStart(2,'0')).join('')};
"""
VERIFY = STATE + """
if(journals().length!==1||folders().length!==2)throw Error('Fixture count mismatch');
const journal=journals()[0],pages=[...journal.pages.values()];
if(pages.length!==2||!pages.every(page=>page.type==='text'))throw Error('Fixture page mismatch');
if(![...game.users.values()].filter(user=>user.isGM).every(user=>journal.testUserPermission(user,'OWNER')&&pages.every(page=>page.testUserPermission(user,'OWNER'))))throw Error('GM access lost');
const page=pages.find(page=>page.name==='First '+RUN);
const html=page.toObject(true).text.content;
const own=document.createElement('div');own.innerHTML=html;document.body.append(own);
let rendered;
try{rendered=own.querySelector('table')!==null&&own.querySelector('ul')!==null&&own.querySelector('ol')!==null&&own.querySelector('hr')!==null&&own.querySelector('a')?.getAttribute('href')==='https://example.com/';}
finally{own.remove();}
if(!rendered||!html.includes('Appended once'))throw Error('HTML retention/render mismatch');
const result={gm_access:true,text_pages:pages.length,html_rendered:true,append_occurrences:html.split('Appended once').length-1};
"""
CLEANUP = STATE + """
const entries=journals(),dirs=folders();
if(entries.length>1||dirs.length>2||[...entries,...dirs].some(doc=>!doc.name.includes(RUN)))throw Error('Ambiguous cleanup marker');
for(const folder of dirs){
 if([...game.journal.values()].some(doc=>doc.folder?.id===folder.id&&!marked(doc)))throw Error('Unmarked journal inside fixture; cleanup refused');
 if([...game.folders.values()].some(doc=>doc.folder?.id===folder.id&&!marked(doc)))throw Error('Unmarked folder inside fixture; cleanup refused');
}
for(const doc of entries){GUARD;if(!marked(doc))throw Error('Cleanup identity changed');await doc.delete();}
for(const doc of dirs.sort((a,b)=>(b.folder?1:0)-(a.folder?1:0))){GUARD;if(!marked(doc))throw Error('Cleanup identity changed');await doc.delete();}
const result={journals_remaining:journals().length,folders_remaining:folders().length};
"""


def code(body, marker):
    if not isinstance(marker, str) or not re.fullmatch(r'[a-f0-9]{32}', marker):
        raise ValueError('Exact random marker required')
    return GUARD + body.replace('RUN', json.dumps(marker)).replace('GUARD', GUARD) + '\nreturn JSON.stringify(result);'


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


async def verify(client):
    marker, calls, serial = uuid4().hex, 0, 0
    report = dict(passed=False, rows=[])

    async def call(name, args, *, cleanup=False, error=False):
        nonlocal calls
        calls += 1
        if calls > (61 if cleanup else 60):
            raise AssertionError('Call budget exceeded')
        response = await client.call_tool(name, args, raise_on_error=not error)
        return response if error else response.structured_content

    async def execute(body, *, cleanup=False):
        result = await call('execute_javascript', dict(code=code(body, marker)), cleanup=cleanup)
        return json.loads(result['value'])

    async def context(kind, identity):
        key = {'folder': 'folder_id', 'journal': 'journal_id', 'page': 'page_uuid'}[kind]
        return await call('get_journal_write_context', dict(target=dict(kind=kind, **{key: identity[key]})))

    stamp = None

    async def write(action):
        nonlocal serial
        serial += 1
        args = dict(request_id=f'journal-{marker}-{serial}', gm_authorized=True, guidance_timestamp=stamp, action=action)
        return await call('write_journal', args), args

    try:
        async with asyncio.timeout(180):
            before = await execute(FINGERPRINT)
            guidance = await call('get_writing_guidance', dict(max_bytes=48000))
            stamp = guidance['timestamp']
            players = await call('get_journal_authoring_options', dict(kind='players'))
            fonts = await call('get_journal_authoring_options', dict(kind='fonts'))
            font = next((entry['font_family'] for entry in fonts['entries'] if re.fullmatch(r'[\w -]{1,256}', entry['font_family'])), None)
            assert font is not None, 'No supported loaded font in the bounded default page'
            report['rows'].extend([dict(scenario='players_default', bytes=size(players), complete=players['complete']),
                dict(scenario='fonts_default', bytes=size(fonts), complete=fonts['complete'])])
            font_pages, cursor = [], None
            for _ in range(20):
                page = await call('get_journal_authoring_options', dict(kind='fonts', limit=1, **({'cursor': cursor} if cursor else {})))
                font_pages.append(page); cursor = page['next_cursor']
                if cursor is None:
                    break
            assert cursor is None
            report['rows'].append(dict(scenario='fonts_complete_pagination', calls=len(font_pages), bytes=sum(size(page) for page in font_pages), complete=True))
            root, _ = await write(dict(operation='create_folder', name='MCP journal probe ' + marker, color='#254c84', sorting='manual'))
            root_context = await context('folder', root['identity'])
            child, _ = await write(dict(operation='create_folder', name='MCP child ' + marker, parent_folder_id=root['identity']['folder_id'], parent_revision=root_context['revision']))
            journal, create_args = await write(dict(operation='create_journal', name='MCP handout ' + marker, folder_id=root['identity']['folder_id'], parent_revision=root_context['revision']))
            retry = await call('write_journal', create_args)
            assert retry['identity'] == journal['identity']
            report['rows'].append(dict(scenario='create_receipt', bytes=size(journal), complete=True))
            html = '<h2>Notes</h2><p><strong>Bold</strong> <a href="https://example.com/">link</a></p><ul><li>Bullet</li></ul><ol><li>Number</li></ol><hr><table><tr><td>Cell</td></tr></table>'
            for name in ('First', 'Second'):
                parent = await context('journal', journal['identity'])
                page, _ = await write(dict(operation='create_page', journal_id=journal['identity']['journal_id'], parent_revision=parent['revision'], name=name+' '+marker,
                    type='text', content=html, format=dict(font_family=font, font_size='large', font_color='#254c84')))
                if name == 'First':
                    first = page
            contents = await call('get_journal_contents', dict(journal_id=journal['identity']['journal_id']))
            assert contents['complete']
            page_context = await context('page', first['identity'])
            append, append_args = await write(dict(operation='update_page', page_uuid=first['identity']['page_uuid'], expected_revision=page_context['revision'], content='<p>Appended once</p>', mode='append', format=dict(font_size='custom', custom_size_pt=14)))
            await call('write_journal', append_args)
            stale = await call('write_journal', {**append_args, 'request_id': f'journal-{marker}-stale'}, error=True)
            assert stale.is_error and 'ContentChanged' in str(stale.content)
            read = await call('read_journal_page', dict(page_uuid=first['identity']['page_uuid']))
            report['rows'].append(dict(scenario='page_readback', bytes=size(read), complete=read['complete']))
            parent = await context('folder', child['identity'])
            current = await context('journal', journal['identity'])
            await write(dict(operation='update_journal', journal_id=journal['identity']['journal_id'], expected_revision=current['revision'], name='MCP renamed '+marker,
                folder_id=child['identity']['folder_id'], parent_revision=parent['revision']))
            current = await context('folder', child['identity'])
            await write(dict(operation='update_folder', folder_id=child['identity']['folder_id'], expected_revision=current['revision'], name='MCP sorted '+marker, color='#abcdef', sorting='alphabetical'))
            scope = dict(target=dict(kind='folder', folder_id=root['identity']['folder_id']), recursive=True)
            if players['entries']:
                scope['user_ids'] = [players['entries'][0]['user_id']]
            preview = await call('get_journal_ownership_context', scope)
            assert preview['count'] == 1
            changes = [dict(user_id=scope['user_ids'][0], level='observer')] if scope.get('user_ids') else []
            shared, _ = await write(dict(operation='set_ownership', **scope, expected_revision=preview['revision'], all_players='none', players=changes))
            assert shared['status'] == 'complete'
            after_preview = await call('get_journal_ownership_context', scope)
            if changes:
                assert after_preview['entries'][0]['players'][0]['value'] == 2 and after_preview['entries'][0]['players'][0]['can_observe']
            report['rows'].append(dict(scenario='ownership_preview', bytes=size(after_preview), complete=True))
            page_scope = dict(target=dict(kind='page', page_uuid=first['identity']['page_uuid']), user_ids=scope.get('user_ids', []))
            page_ownership = await call('get_journal_ownership_context', page_scope)
            if changes:
                assert page_ownership['entries'][0]['players'][0]['parent_can_observe']
                hidden_page, _ = await write(dict(operation='set_ownership', **page_scope, expected_revision=page_ownership['revision'],
                    players=[dict(user_id=scope['user_ids'][0], level='none')]))
                assert hidden_page['status'] == 'complete'
                page_after = await call('get_journal_ownership_context', page_scope)
                assert page_after['entries'][0]['players'][0]['value'] == 0
                assert page_after['entries'][0]['players'][0]['parent_can_observe']
                assert not page_after['entries'][0]['players'][0]['can_observe']
                report['page_override_checked'] = True
            report['runtime'] = await execute(VERIFY)
            assert report['runtime']['append_occurrences'] == 1
            assert await execute(FINGERPRINT) == before
            report['passed'] = True
    except Exception as error:
        report.update(exception_type=type(error).__name__, last_call=calls)
    finally:
        try:
            async with asyncio.timeout(30):
                cleanup = await asyncio.shield(execute(CLEANUP, cleanup=True))
            report['cleanup_verified'] = cleanup == dict(journals_remaining=0, folders_remaining=0)
            report['passed'] &= report['cleanup_verified']
        except Exception as error:
            report.update(passed=False, cleanup_exception_type=type(error).__name__)
        report['calls'] = calls
    return report


async def main():
    root = Path(__file__).resolve().parents[1]
    token = next(line.partition('=')[2].strip() for line in (root / '.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    async with Client(transport, timeout=20, init_timeout=10) as client:
        catalog = await client.list_tools()
        report = dict(catalog_bytes=size([tool.model_dump(mode='json') for tool in catalog]), tools=len(catalog), discovery_calls=1,
            tool_bytes={tool.name: size(tool.model_dump(mode='json')) for tool in catalog if tool.name in ('get_journal_write_context', 'write_journal', 'get_journal_authoring_options', 'get_journal_ownership_context')})
        report.update(await verify(client))
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
