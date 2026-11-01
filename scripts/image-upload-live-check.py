"""Bounded actual MCP User Data upload and journal embedding acceptance.

Existing localhost world test only. At most35 calls/180s plus cleanup30s.
Uses public Pillow sample images, one uniquely marked User Data folder and
one marked journal. Deletes only its journal; image files remain for manual
cleanup because FilePicker has no documented public deletion API.
"""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def size(value):
    return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())


async def verify(client):
    marker=uuid4().hex[:12]
    folder='mcp-upload-verify-'+marker
    journal_id=None; calls=0
    report=dict(passed=False,folder=folder,rows=[])

    async def call(name, arguments, *, error=False):
        nonlocal calls
        calls+=1
        if calls>35: raise AssertionError('Call budget exceeded')
        result=await client.call_tool(name,arguments,raise_on_error=not error)
        return result if error else result.structured_content

    async def execute(code):
        guard="if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');"
        result=await call('execute_javascript',dict(code=guard+code))
        return json.loads(result['value'])

    try:
        async with asyncio.timeout(180):
            await execute("return JSON.stringify({ready:true});")
            root=await call('browse_journal_images',{})
            assert root['capabilities']['can_create_directory'] and not root['capabilities']['can_upload']
            created=await call('create_image_directory',dict(directory='',name=folder))
            assert created['status']=='created' and created['capabilities']['can_upload']
            again=await call('create_image_directory',dict(directory='',name=folder))
            assert again['status']=='already_exists'
            report['rows'].append(dict(scenario='create_directory',bytes=size(created),complete=True))
            child=await call('create_image_directory',dict(directory=folder,name='α portraits'))
            assert child['status']=='created'
            reused=await call('create_image_directory',dict(directory=folder,name='α portraits'))
            assert reused['status']=='already_exists'
            destination=child['location']['directory']
            # Both a Unicode filename and a space exercise canonical path handling.
            args=dict(directory=destination,filename='α portrait',file=dict(download_url='https://raw.githubusercontent.com/python-pillow/Pillow/main/Tests/images/hopper.png',file_id='verification-public-png',mime_type='image/jpeg',file_name='untrusted.jpg'))
            uploaded=await call('upload_image',args)
            report['last_upload']=uploaded
            assert uploaded['status']=='uploaded' and uploaded['mime_type']=='image/png' and not uploaded['overwritten']
            report['rows'].append(dict(scenario='upload_png',bytes=size(uploaded),complete=True))
            collision=await call('upload_image',args,error=True)
            assert collision.is_error and 'FileExists' in str(collision.content)
            overwritten=await call('upload_image',{**args,'overwrite':True})
            assert overwritten['status']=='uploaded' and overwritten['overwritten']
            report['rows'].append(dict(scenario='explicit_overwrite',bytes=size(overwritten),complete=True))
            # A real JPEG follows the same URL -> decoder -> private WS pipeline.
            jpeg=await call('upload_image',dict(directory=folder,filename='jpeg-sample',file=dict(download_url='https://raw.githubusercontent.com/python-pillow/Pillow/main/Tests/images/hopper.jpg',file_id='verification-public-jpeg')))
            assert jpeg['status']=='uploaded' and jpeg['filename']=='jpeg-sample.jpg'
            report['rows'].append(dict(scenario='upload_jpeg',bytes=size(jpeg),complete=True))
            webp=await call('upload_image',dict(directory=folder,filename='webp-sample',file=dict(download_url='https://raw.githubusercontent.com/python-pillow/Pillow/main/Tests/images/hopper.webp',file_id='verification-public-webp')))
            assert webp['status']=='uploaded' and webp['filename']=='webp-sample.webp'
            report['rows'].append(dict(scenario='upload_webp',bytes=size(webp),complete=True))
            stamp=(await call('get_writing_guidance',dict(max_bytes=48000)))['timestamp']
            serial=0
            async def write(action):
                nonlocal serial
                serial+=1
                return await call('write_journal',dict(request_id=f'upload-{marker}-{serial}',gm_authorized=True,guidance_timestamp=stamp,action=action))
            journal=await write(dict(operation='create_journal',name='MCP upload verifier '+marker))
            journal_id=journal['identity']['journal_id']
            context=await call('get_journal_write_context',dict(target=dict(kind='journal',journal_id=journal_id)))
            page=await write(dict(operation='create_page',journal_id=journal_id,parent_revision=context['revision'],name='Uploaded image',content='<p>Upload verification fixture.</p>'))
            page_uuid=page['identity']['page_uuid']
            context=await call('get_journal_write_context',dict(target=dict(kind='page',page_uuid=page_uuid)))
            # Deliberately pass upload receipt directly: no intervening file browse.
            embedded=await write(dict(operation='embed_image',page_uuid=page_uuid,expected_revision=context['revision'],image=uploaded['image'],alt='Uploaded image verifier',width=128))
            checked=await execute('const p=await fromUuid('+json.dumps(page_uuid)+');const doc=new DOMParser().parseFromString(p.toObject(true).text.content,"text/html");const img=doc.querySelector("img");return JSON.stringify({src:img?.getAttribute("src"),alt:img?.getAttribute("alt")});')
            assert checked==dict(src=uploaded['image']['src'],alt='Uploaded image verifier')
            report['rows'].append(dict(scenario='embed_returned_selector',bytes=size(embedded),complete=True))
            report.pop('last_upload',None)
            report['passed']=True
    except Exception as error:
        report.update(exception_type=type(error).__name__,last_call=calls)
    finally:
        if journal_id:
            try:
                async with asyncio.timeout(30):
                    deleted=await execute('const j=game.journal.get('+json.dumps(journal_id)+');if(j?.name!=='+json.dumps('MCP upload verifier '+marker)+')throw Error("Marker mismatch");await j.delete();return JSON.stringify({deleted:true});')
                    report['journal_cleanup']=deleted['deleted']
            except Exception:
                report['journal_cleanup']=False;report['passed']=False
        report['calls']=calls
    return report


async def main():
    root=Path(__file__).resolve().parents[1]
    token=next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines() if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    transport=StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token})
    async with Client(transport,timeout=100,init_timeout=10) as client:
        catalog=await client.list_tools()
        tools={tool.name:tool for tool in catalog}
        assert tools['upload_image'].meta['openai/fileParams']==['file']
        report=dict(catalog_bytes=size([t.model_dump(mode='json') for t in catalog]),tools=len(catalog),discovery_calls=1)
        report.update(await verify(client))
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
