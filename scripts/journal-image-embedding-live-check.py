"""Bounded browse/select/embed/read/render verification on new marked journals.

Uses the already tested journal verifier's guard, fingerprints and exact-marker
cleanup. Existing localhost test world only; no file writes or existing document
changes. Budget35 calls/120s plus one cleanup call/30s.
"""
import asyncio
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

spec = importlib.util.spec_from_file_location('journal_fixture', Path(__file__).with_name('journal-authoring-live-check.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
size = fixture.size

VERIFY = fixture.STATE + """
if(journals().length!==1||folders().length)throw Error('Fixture count mismatch');
const journal=journals()[0],pages=[...journal.pages.values()];
if(pages.length!==2)throw Error('Page count mismatch');
const page=pages.find(page=>page.name==='Illustrated '+RUN),sibling=pages.find(candidate=>candidate!==page);
if(!page||sibling.toObject(true).text.content!=='<p>Sibling untouched</p>')throw Error('Sibling changed');
const html=page.toObject(true).text.content,own=document.createElement('div');own.innerHTML=html;document.body.append(own);
let result;
try{
 const images=[...own.querySelectorAll('img')];
 if(images.length!==3||own.textContent!=='Before & afterMap locationKeep after.')throw Error('Surrounding content changed');
 const first=own.querySelector('h2').nextElementSibling;
 if(first.tagName!=='IMG'||first.alt!=='A "map" & <route>'||first.getAttribute('width')!=='320'||first.getAttribute('height')!=='160')throw Error('Image attributes/placement changed');
 for(const image of images)await new Promise((resolve,reject)=>{
  if(image.complete&&image.naturalWidth>0){resolve();return;}
  const timer=setTimeout(()=>reject(Error('Render timeout')),5000);
  image.onload=()=>{clearTimeout(timer);resolve();};image.onerror=()=>{clearTimeout(timer);reject(Error('Render failed'));};
 });
 const last=images.at(-1),natural=images[0];
 if(last.getAttribute('width')!=='120'||last.hasAttribute('height')||natural.hasAttribute('width')||natural.hasAttribute('height')||natural.alt!=='')throw Error('Natural/one-dimensional sizing changed');
 const box=last.getBoundingClientRect();
 if(Math.abs(box.width/box.height-last.naturalWidth/last.naturalHeight)>0.05)throw Error('Aspect ratio not preserved');
 const publicAsset=await fetch(first.src,{method:'HEAD',credentials:'omit'});
 if(!publicAsset.ok)throw Error('Public fixture asset unavailable without GM credentials');
 if(![...game.users.values()].filter(user=>user.isGM).every(user=>journal.testUserPermission(user,'OWNER')&&pages.every(page=>page.testUserPermission(user,'OWNER'))))throw Error('GM access lost');
 result={image_count:3,attributes_retained:true,html_rendered:true,aspect_ratio_preserved:true,public_asset_without_gm_credentials:publicAsset.ok,gm_access:true,sibling_unchanged:true};
}finally{own.remove();}
"""


async def verify(client):
    marker, calls, serial = uuid4().hex, 0, 0
    report = dict(passed=False, rows=[])

    async def call(name, args, *, cleanup=False, error=False):
        nonlocal calls
        calls += 1
        if calls > (36 if cleanup else 35):
            raise AssertionError('Call budget exceeded')
        result = await client.call_tool(name, args, raise_on_error=not error)
        return result if error else result.structured_content

    async def execute(body, *, cleanup=False):
        result = await call('execute_javascript', dict(code=fixture.code(body, marker)), cleanup=cleanup)
        return json.loads(result['value'])

    async def context(identity):
        key = 'page_uuid' if identity['kind'] == 'page' else 'journal_id'
        return await call('get_journal_write_context', dict(target=dict(kind=identity['kind'], **{key: identity[key]})))

    stamp = None

    async def write(action):
        nonlocal serial
        serial += 1
        args = dict(request_id=f'journal-{marker}-{serial}', gm_authorized=True, guidance_timestamp=stamp, action=action)
        return await call('write_journal', args), args

    try:
        async with asyncio.timeout(120):
            before = await execute(fixture.FINGERPRINT)
            stamp = (await call('get_writing_guidance', dict(max_bytes=48000)))['timestamp']
            selection = await call('browse_journal_images', dict(source='public', directory='icons/svg', name_contains='anchor'))
            image = next(entry['image'] for entry in selection['entries'] if entry['kind'] == 'image')
            journal, _ = await write(dict(operation='create_journal', name='MCP image probe '+marker))
            parent = await context(journal['identity'])
            page, _ = await write(dict(operation='create_page', journal_id=journal['identity']['journal_id'], parent_revision=parent['revision'], name='Illustrated '+marker,
                content='<p>Before &amp; after</p><h2>Map location</h2><p>Keep <strong>after</strong>.</p>'))
            parent = await context(journal['identity'])
            await write(dict(operation='create_page', journal_id=journal['identity']['journal_id'], parent_revision=parent['revision'], name='Sibling '+marker, content='<p>Sibling untouched</p>'))
            current = await context(page['identity'])
            action = dict(operation='embed_image', page_uuid=page['identity']['page_uuid'], expected_revision=current['revision'], image=image,
                alt='A "map" & <route>', width=320, height=160, position='after', anchor=dict(tag='h2', text='Map location'))
            embedded, args = await write(action)
            retry = await call('write_journal', args)
            assert retry['identity'] == embedded['identity']
            stale = await call('write_journal', {**args, 'request_id': f'journal-{marker}-stale'}, error=True)
            assert stale.is_error and 'ContentChanged' in str(stale.content)
            report['rows'].append(dict(scenario='image_write_receipt', bytes=size(embedded), complete=True))
            for position, options in [('append', dict(alt='One dimension', width=120)), ('prepend', dict(alt=''))]:
                current = await context(page['identity'])
                await write(dict(operation='embed_image', page_uuid=page['identity']['page_uuid'], expected_revision=current['revision'], image=image, position=position, **options))
            read = await call('read_journal_page', dict(page_uuid=page['identity']['page_uuid']))
            assert read['complete'] and read['content'].count('<img ') == 3
            report['rows'].append(dict(scenario='image_page_readback', bytes=size(read), complete=True))
            current = await context(page['identity'])
            missing = await call('write_journal', {**args, 'request_id': f'journal-{marker}-missing', 'action': {**action,
                'expected_revision': current['revision'], 'image': {**image, 'src': 'icons/svg/mcp-missing-'+marker+'.svg'}}}, error=True)
            assert missing.is_error and 'ImageNotFound' in str(missing.content)
            report['runtime'] = await execute(VERIFY)
            assert await execute(fixture.FINGERPRINT) == before
            report['passed'] = True
    except Exception as error:
        report.update(exception_type=type(error).__name__, last_call=calls)
    finally:
        try:
            async with asyncio.timeout(30):
                cleaned = await asyncio.shield(execute(fixture.CLEANUP, cleanup=True))
            report['cleanup_verified'] = cleaned == dict(journals_remaining=0, folders_remaining=0)
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
            tool_bytes={tool.name: size(tool.model_dump(mode='json')) for tool in catalog if tool.name in ('write_journal', 'browse_journal_images')})
        report.update(await verify(client))
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
