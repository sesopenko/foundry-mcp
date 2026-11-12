#!/usr/bin/env python3
"""Existing localhost test-world acceptance:<=60 MCP calls/20min, owned cleanup."""
import asyncio
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import CallToolResult as ProtocolResult
from foundry_mcp_server.image_preview_live_support import (
    AssetFixture,Budget,PreviewTLS,cleanup_map_review,compact,curl_delivery,preview_settings,require)
from foundry_mcp_server.map_workflow_acceptance import verify_map
from foundry_mcp_server.image_preview_visual_handoff import create_bundle,public_report
from foundry_mcp_server.image_preview_visual_fixture import prepare as prepare_visual,cleanup as cleanup_visual

SPEC=importlib.util.spec_from_file_location('preview_journal_fixture',ROOT/'scripts/journal-authoring-live-check.py')
fixture=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(fixture)


async def verify(client,asset,reader,*,budget=None):
    budget=budget or Budget();marker=asset.marker;report=dict(passed=False,rows=[])
    async def call(name,args,*,cleanup=False):
        if not cleanup:require(budget.calls<budget.limit-1)
        budget.admit(cleanup=cleanup)
        value=await client.call_tool(name,args,raise_on_error=False)
        require(not value.is_error)
        raw=value.structured_content
        protocol=ProtocolResult(content=value.content,structured_content=raw,is_error=False,meta=value.meta).model_dump(mode='json',by_alias=True,exclude_none=True)
        report['rows'].append(dict(tool=name,json_bytes=compact(raw),mcp_bytes=compact(protocol),complete=raw.get('complete',True)))
        return raw
    async def execute(body,*,cleanup=False):
        value=await call('execute_javascript',{'code':fixture.code(body,marker)},cleanup=cleanup)
        return json.loads(value['value'])
    try:
        async with asyncio.timeout(1200):
            budget.admit();catalog=await client.list_tools(max_pages=1)
            report.update(catalog_tools=len(catalog),catalog_bytes=compact([tool.model_dump(mode='json') for tool in catalog]),
                tool_bytes={tool.name:compact(tool.model_dump(mode='json')) for tool in catalog if tool.name in
                    ('get_foundry_image_info','get_foundry_image_url','browse_journal_images','read_journal_page')})
            before=await execute(fixture.FINGERPRINT)
            stamp=(await call('get_writing_guidance',dict(max_bytes=48000)))['timestamp']
            async def write(serial,action):
                return await call('write_journal',dict(request_id='journal-'+marker+'-'+str(serial),gm_authorized=True,
                    guidance_timestamp=stamp,action=action))
            journal=await write(1,dict(operation='create_journal',name='MCP preview acceptance '+marker))
            journal_id=journal['identity']['journal_id']
            context=await call('get_journal_write_context',dict(target=dict(kind='journal',journal_id=journal_id)))
            content='<p>Technical fixture.</p><img src="'+asset.src+'">'
            page=await write(2,dict(operation='create_page',journal_id=journal_id,parent_revision=context['revision'],name='Technical fixture',content=content))
            args=dict(page_uuid=page['identity']['page_uuid'],max_chars=32);fragments=[]
            while True:
                value=await call('read_journal_page',args);fragments.append(value['content'])
                if value['complete']:break
                args={**args,'cursor':value['next_cursor']}
                require(len(fragments)<16)
            recovered=''.join(fragments);require(recovered==content)
            reference=re.search(r'<img src="([^"]+)">',recovered).group(1)
            require(reference==asset.src and len(fragments)>1)
            require(not any('<img' in part and '>' in part[part.index('<img'):] for part in fragments))
            info=await call('get_foundry_image_info',dict(request=dict(src=reference)))
            require((info['width'],info['height'])==(512,384))
            delivered=[];issued=[]
            for crop in (None,dict(x=250,y=200,width=160,height=120),dict(x=511,y=383,width=1,height=1)):
                request=dict(source_id=info['source_id'])
                if crop is not None:request['crop']=crop
                value=await call('get_foundry_image_url',dict(request=request))
                require(value['source_id']==info['source_id'])
                require(value['region']==(crop or dict(x=0,y=0,width=512,height=384)))
                require((value['width'],value['height'])==((crop['width'],crop['height']) if crop else (512,384)))
                delivered.append(reader(value));issued.append(value['url'])
            require(len(set(issued))==3)
            selected=await call('browse_journal_images',dict(source='data',directory=asset.path.name))
            image=next(entry['image'] for entry in selected['entries'] if entry.get('kind')=='image')
            require(selected['complete'])
            portrait=await call('get_foundry_image_url',dict(request=dict(image=image)))
            delivered.append(reader(portrait))
            svg=await call('get_foundry_image_info',dict(request=dict(src='icons/svg/anchor.svg')))
            require(svg['mime_type']=='image/svg+xml')
            icon=await call('get_foundry_image_url',dict(request=dict(source_id=svg['source_id'])))
            delivered.append(reader(icon))
            require(await execute(fixture.FINGERPRINT)==before)
            report.update(passed=True,fragment_count=len(fragments),journal_reconstructed=True,source_handle_reused=True,
                issued_distinct=True,reader_checks=delivered,existing_documents_unchanged=True,
                pending=['Externally reachable trusted public HTTPS and target ChatGPT visual acceptance remain14b.',
                    'Live S3 requires a configured browser-readable bucket and CORS; prefixed deployment remains unavailable.'])
    except Exception as error:report.update(passed=False,error_type=type(error).__name__)
    finally:
        try:
            async with asyncio.timeout(30):
                cleaned=await execute(fixture.CLEANUP,cleanup=True)
            report['journal_cleanup']=cleaned==dict(journals_remaining=0,folders_remaining=0)
        except Exception:report['journal_cleanup']=False
        report['calls']=budget.calls
        report['passed']=report['passed'] and report['journal_cleanup']
    return report


def service_restart():
    subprocess.run([str(ROOT/'scripts/server.sh'),'restart'],check=True,capture_output=True,timeout=65)
    import urllib.request
    for _ in range(60):
        with urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3) as response:value=json.load(response)
        if 'gm' in value['foundry_clients']:return
        time.sleep(1)
    raise RuntimeError('DevelopmentGMReadinessDeadline')


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--map',action='store_true',help='Read-only complete map/annotation/legend acceptance, <=60 calls/900s.')
    modes.add_argument('--cleanup-map-review',action='store_true',help='Remove only the exact marked private derivative-review files.')
    modes.add_argument('--visual-handoff',action='store_true',help='Create a private pending visual challenge/prompts bundle, no game writes.')
    modes.add_argument('--prepare-visual-fixture',action='store_true',help='Prepare exactly marked image/journal from private bundle; retain until explicit cleanup.')
    modes.add_argument('--cleanup-visual-fixture',action='store_true',help='Delete only the private bundle marker-owned game fixture; retain the handoff bundle.')
    modes.add_argument('--visual-handoff-status',action='store_true',help='Report pending/pass/fail from private operator-reviewed client observations, without answers.')
    args=parser.parse_args()
    bundle=ROOT/'.local/image-preview-visual-handoff'
    if args.visual_handoff or args.visual_handoff_status:
        try:
            if args.visual_handoff:report=create_bundle(bundle)
            else:
                observation=bundle/'observations.json'
                if observation.exists():require(observation.is_file() and not observation.is_symlink() and observation.stat().st_size<=32768)
                report=public_report(bundle,json.loads(observation.read_text()) if observation.exists() else None)
        except Exception as error:report=dict(passed=False,error_type=type(error).__name__)
        print(json.dumps(report,sort_keys=True));return 1 if report.get('passed') is False or report.get('visual_acceptance')=='failed' else 0
    if args.prepare_visual_fixture or args.cleanup_visual_fixture:
        try:
            token=next(line.partition('=')[2].strip() for line in (ROOT/'.env.mcp').read_text().splitlines()
                if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
            async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token}),timeout=60,init_timeout=10) as client:
                action=prepare_visual if args.prepare_visual_fixture else cleanup_visual
                report=await action(client,bundle,ROOT/'foundry-data/Data',fixture)
        except Exception as error:report=dict(passed=False,error_type=type(error).__name__)
        print(json.dumps(report,sort_keys=True));return 1 if report.get('passed') is False else 0
    if args.cleanup_map_review:
        try:report=cleanup_map_review(ROOT/'.local/image-preview-map-review')
        except Exception as error:report=dict(cleanup_complete=False,error_type=type(error).__name__)
        print(json.dumps(report));return 0 if report['cleanup_complete'] else 1
    marker=uuid4().hex;report=dict(passed=False)
    try:
        with tempfile.TemporaryDirectory(prefix='foundry-preview-live-') as private:
            private=Path(private)
            import contextlib
            assets=contextlib.nullcontext(None) if args.map else AssetFixture(ROOT/'foundry-data/Data',marker)
            with PreviewTLS(private) as tls,assets as asset:
                try:
                    with preview_settings(ROOT/'.env.mcp',tls.origin,private/'store'):
                        service_restart()
                        token=next(line.partition('=')[2].strip() for line in (ROOT/'.env.mcp').read_text().splitlines()
                            if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
                        def reader(value):return curl_delivery(value['url'],value,tls.origin,tls.certificate,private)
                        def map_reader(value,label,pin):
                            from PIL import Image
                            result=reader(value)
                            path=private/'body-0'
                            if pin:
                                with Image.open(path) as decoded:require(decoded.convert('RGB').getpixel(pin)==(255,255,255))
                                result['independent_pin_verified']=True
                            output=ROOT/'.local/image-preview-map-review'
                            if not output.exists():output.mkdir(mode=0o700);(output/'.owner').write_text(marker)
                            require(not output.is_symlink() and (output/'.owner').read_text()==marker)
                            destination=output/(label+('.png' if value['mime_type']=='image/png' else '.webp'));require(not destination.exists())
                            destination.write_bytes(path.read_bytes())
                            return result
                        async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token}),
                            timeout=100,init_timeout=10) as client:
                            report=await verify_map(client,map_reader) if args.map else await verify(client,asset,reader)
                finally:service_restart()
            report.update(asset_cleanup=asset is None or not asset.path.exists(),settings_restored=True,local_tls_only=True)
    except Exception as error:report.update(passed=False,error_type=type(error).__name__)
    print(json.dumps(report,sort_keys=True));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
