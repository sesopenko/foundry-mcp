"""Read-only localhost info acceptance: four MCP calls,60 seconds, no fixtures.

Uses the existing dedicated14.369/test GM and public core SVG. Prints technical
aggregates only, never source handles, paths, credentials or native errors.
Run after offline checks; original snapshots expire privately after30 minutes.
"""
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from .mcp_server.image_preview_models import ImageInfoResult

FAILURE_CODES = ('AuthenticatedContextRequired','SourceUnavailable','SourceContextLost',
    'UnsupportedImage','ImageTooLarge','ImageProcessingFailed','ImageMemoryLimit','ImageScratchLimit',
    'ImageProcessingTimeout','ImageProcessingBusy','BridgeUnavailable','InvalidFoundryResponse',
    'ImageTransferFailed','ImageTransferTimeout','ImageUnavailable','AmbiguousSource','BrowseFailed',
    'ImageNotFound','PermissionDenied','NotReady','UnsupportedVersion','UnsupportedCapability')


async def verify(client):
    calls = 0
    async def call(name,args):
        nonlocal calls
        calls += 1
        if calls>4:raise RuntimeError('CallBudgetExceeded')
        result = await client.call_tool(name,args,raise_on_error=False)
        if result.is_error:
            text = str(result.content)
            code = next((code for code in FAILURE_CODES if code+':' in text),'AcceptanceCallFailed')
            raise RuntimeError(code)
        return result.structured_content
    try:
        async with asyncio.timeout(60):
            guard = await call('execute_javascript',{'code':"if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');return true;"})
            if guard.get('value') is not True:raise RuntimeError('WrongRuntime')
            calls += 1
            catalog = await client.list_tools(max_pages=1)
            tool = next(t for t in catalog if t.name=='get_foundry_image_info')
            image = dict(source='public',directory='icons/svg',src='icons/svg/anchor.svg')
            rows = []
            handles = []
            for selector in ({'image':image},{'src':image['src']}):
                data = await call('get_foundry_image_info',{'request':selector})
                info = ImageInfoResult.model_validate(data)
                if set(data)!=set(ImageInfoResult.model_fields):raise RuntimeError('UnexpectedOutputFields')
                handles.append(info.source_id)
                rows.append(dict(width=info.width,height=info.height,mime_type=info.mime_type,
                    size_bytes=info.size_bytes,frame_policy=info.frame_policy,
                    json_bytes=len(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode())))
            if rows[0]!=rows[1] or handles[0]==handles[1]:raise RuntimeError('SnapshotContractMismatch')
            return dict(passed=True,calls=calls,rows=rows,catalog_tools=len(catalog),
                tool_bytes=len(json.dumps(tool.model_dump(mode='json'),ensure_ascii=False,separators=(',',':')).encode()))
    except Exception as error:
        return dict(passed=False,calls=calls,error_type=type(error).__name__,
            **({'failure_code':str(error)} if str(error) in FAILURE_CODES else {}))


async def main():
    root = Path(__file__).resolve().parents[1]
    token = next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',
            headers={'Authorization':'Bearer '+token}),timeout=30,init_timeout=10) as client:
        report = await verify(client)
    print(json.dumps(report,sort_keys=True))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
