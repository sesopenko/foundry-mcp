"""Bounded native map-binding acceptance:<=8 MCP calls/600s, no game writes."""
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import CallToolResult as ProtocolResult

from .mcp_server.image_preview_models import ImageInfoResult,ImageUrlResult
from .mcp_server.map_models import MapSelector

SELECT="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const scene=game.scenes.contents.find(s=>s.testUserPermission(game.user,'OBSERVER')&&s.width===6800&&s.height===9000&&s.notes.size);
if(!scene)throw Error('Representative map unavailable');
const level=scene.levels.contents.find(l=>l.testUserPermission(game.user,'OBSERVER')&&l.toObject(true).background?.src);
if(!level)throw Error('Background unavailable');
return JSON.stringify({map:{scene_uuid:scene.uuid,level_id:level.id,role:'background'},active:game.scenes.active?.id??null});
"""
ACTIVE="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
return JSON.stringify({active:game.scenes.active?.id??null});
"""


def compact(value):return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())


async def verify(client):
    calls=0;measurements={}
    async def call(name,args,label):
        nonlocal calls
        if calls>=8:raise RuntimeError('MapImageVerificationBudgetExceeded')
        calls+=1
        result=await client.call_tool(name,args,raise_on_error=False)
        envelope=ProtocolResult(content=result.content,structured_content=result.structured_content,is_error=result.is_error,meta=result.meta).model_dump(mode='json',by_alias=True,exclude_none=True)
        measurements[label]=dict(json_bytes=compact(result.structured_content),mcp_bytes=compact(envelope),error=result.is_error)
        return result
    try:
        async with asyncio.timeout(600):
            calls+=1;catalog=await client.list_tools(max_pages=1)
            by_name={tool.name:tool for tool in catalog}
            info_tool=by_name['get_foundry_image_info'];url_tool=by_name['get_foundry_image_url']
            if 'map' not in info_tool.input_schema['$defs']['ImageInfoRequest']['properties']:raise ValueError('Missing map schema')
            flag=url_tool.input_schema['$defs']['ImageUrlRequest']['properties']['map_notes']
            if flag.get('type')!='boolean' or flag.get('default') is not False:raise ValueError('Missing annotation flag contract')
            selected=await call('execute_javascript',{'code':SELECT},'select')
            if selected.is_error:raise RuntimeError('NativeSelectionFailed')
            selected=json.loads(selected.structured_content['value']);map_selector=MapSelector.model_validate(selected['map'])
            assets=await call('get_map_info',dict(scene_uuid=map_selector.scene_uuid,level_id=map_selector.level_id),'assets')
            if assets.is_error:raise RuntimeError('NativeAssetsFailed')
            assets=assets.structured_content;next_call=assets['entries'][0]['background']['info_next_call']
            if next_call!={'tool':'get_foundry_image_info','arguments':{'request':{'map':map_selector.model_dump()}}}:raise ValueError('Wrong map next call')
            staged=await call(next_call['tool'],next_call['arguments'],'info')
            if staged.is_error:raise RuntimeError('NativeMapInfoFailed')
            info=ImageInfoResult.model_validate(staged.structured_content)
            issued=await call('get_foundry_image_url',{'request':dict(source_id=info.source_id,map_notes=True)},'annotated_url')
            issuance_verified=not issued.is_error
            if issued.is_error:
                if 'PreviewNotConfigured:' not in str(issued.content):raise RuntimeError('NativeAnnotationFailed')
                keys=[];legend_args=dict(scene_uuid=map_selector.scene_uuid,level_id=map_selector.level_id,section='notes',expected_revision=assets['revision'],limit=2)
            else:
                url=ImageUrlResult.model_validate(issued.structured_content)
                if url.map_notes is None or url.map_notes.map!=map_selector or url.map_notes.revision!=assets['revision']:raise ValueError('Wrong annotated context')
                keys=url.map_notes.keys
                legend_args=url.map_notes.legend_next_call.arguments.model_dump() if keys else None
            legend_rows=0;legend_complete=True
            if legend_args:
                legend=await call('get_map_info',legend_args,'legend')
                if legend.is_error:raise RuntimeError('NativeLegendFailed')
                value=legend.structured_content;legend_rows=len(value['entries']);legend_complete=value['complete']
                if value['revision']!=assets['revision'] or value['scene']['scene_uuid']!=map_selector.scene_uuid or value['level_id']!=map_selector.level_id:raise ValueError('Wrong legend identity')
            after=await call('execute_javascript',{'code':ACTIVE},'active')
            if after.is_error or json.loads(after.structured_content['value'])['active']!=selected['active']:raise ValueError('Active Scene changed')
            return dict(passed=True,calls=calls,catalog_tools=len(catalog),catalog_bytes=compact([tool.model_dump(mode='json') for tool in catalog]),
                info_tool_bytes=compact(info_tool.model_dump(mode='json')),url_tool_bytes=compact(url_tool.model_dump(mode='json')),
                source_width=info.width,source_height=info.height,source_bytes=info.size_bytes,frame_policy=info.frame_policy,
                map_info_bound=True,annotation_issuance_verified=issuance_verified,anonymous_delivery_verified=False,
                rendered_keys=len(keys),legend_rows=legend_rows,legend_complete=legend_complete,
                active_unchanged=True,persisted_fixtures=0,measurements=measurements,
                pending=['Real-listener delivery and target-client gates remain14a/14b.'] if issuance_verified else ['Configure the trusted preview HTTPS origin/private store for native URL issuance; real-listener delivery and target-client gates remain14a/14b.'])
    except Exception as error:return dict(passed=False,calls=calls,error_type=type(error).__name__)


async def main():
    root=Path(__file__).resolve().parents[1]
    token=next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token}),timeout=30,init_timeout=10) as client:
        report=await verify(client)
    print(json.dumps(report,sort_keys=True));return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
