"""Selected-map metadata baseline:2 read-only MCP calls/120s, aggregate output only."""
import asyncio
import argparse
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import CallToolResult as ProtocolResult
from .mcp_server.map_info_models import MapInfoResult

CODE="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const before=game.scenes.active?.id;
const scenes=game.scenes.contents.filter(s=>s.testUserPermission(game.user,'OBSERVER'));
let levels=0,tiles=0,backgrounds=0,foregrounds=0,empty_levels=0,source_match=true,identities_match=true,dimensions_valid=true;
const grid_fields=new Set(),texture_fields=new Set(),tile_fields=new Set();
for(const scene of scenes){
 const source=scene.toObject(true),dim=scene.getDimensions();
 dimensions_valid&&=['sceneX','sceneY','sceneWidth','sceneHeight'].every(k=>Number.isFinite(dim[k]));
 source_match&&=Array.isArray(source.levels)&&source.levels.length===scene.levels.contents.length;
 for(const k of ['type','size','distance','units','style','thickness','color','alpha'])if(Object.hasOwn(source.grid,k))grid_fields.add(k);
 for(const level of scene.levels.contents){
  if(!level.testUserPermission(game.user,'OBSERVER'))continue;
  const data=level.toObject(true);levels++;
  identities_match&&=level.parent===scene&&level.uuid===scene.uuid+'.Level.'+level.id;
  if(data.background?.src)backgrounds++;
  if(data.foreground?.src)foregrounds++;
  if(!data.background?.src&&!data.foreground?.src)empty_levels++;
  for(const k of ['anchorX','anchorY','offsetX','offsetY','fit','scaleX','scaleY','rotation'])if(Object.hasOwn(data.textures??{},k))texture_fields.add(k);
 }
 for(const tile of scene.tiles.contents){
  if(!tile.testUserPermission(game.user,'OBSERVER'))continue;
  const data=tile.toObject(true);tiles++;
  identities_match&&=tile.parent===scene&&tile.uuid===scene.uuid+'.Tile.'+tile.id;
  for(const k of ['levels','x','y','width','height','rotation','texture'])if(Object.hasOwn(data,k))tile_fields.add(k);
 }
}
return JSON.stringify({version:game.version,scenes:scenes.length,levels,tiles,backgrounds,foregrounds,empty_levels,source_match,identities_match,dimensions_valid,active_unchanged:before===game.scenes.active?.id,grid_fields:[...grid_fields].sort(),texture_fields:[...texture_fields].sort(),tile_fields:[...tile_fields].sort()});
"""


async def measure(client):
    """Validate and expose only technical counts and fixed field names."""
    calls=0
    try:
        async with asyncio.timeout(120):
            calls+=1
            catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            calls+=1
            result=await client.call_tool('execute_javascript',{'code':CODE})
            data=json.loads(result.structured_content['value'])
            if data['version']!='14.369' or any(data.get(k) is not True for k in (
                    'source_match','identities_match','dimensions_valid','active_unchanged')):raise ValueError('Metadata boundary mismatch')
            report=dict(passed=True,calls=calls,version='14.369',active_unchanged=True,
                source_match=True,identities_match=True,dimensions_valid=True,catalog_tools=len(catalog),
                catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()))
            for key in ('scenes','levels','tiles','backgrounds','foregrounds','empty_levels'):
                value=data[key]
                if type(value) is not int or not 0<=value<=10000000:raise ValueError('Invalid count')
                report[key]=value
            for key,allowed in (
                    ('grid_fields',{'type','size','distance','units','style','thickness','color','alpha'}),
                    ('texture_fields',{'anchorX','anchorY','offsetX','offsetY','fit','scaleX','scaleY','rotation'}),
                    ('tile_fields',{'levels','x','y','width','height','rotation','texture'})):
                value=data[key]
                if not isinstance(value,list) or any(type(v) is not str or v not in allowed for v in value):raise ValueError('Invalid fields')
                report[key]=sorted(set(value))
            return report
    except Exception as error:return dict(passed=False,calls=calls,error_type=type(error).__name__)


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--read',action='store_true',help='Verify implemented selected-map assets/tiles, <=30 calls/120s.')
    parser.add_argument('--diagnose-schema',action='store_true',help='Read-only handler/schema diagnosis:1 call/60s, no source values.')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    token=next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',
            headers={'Authorization':'Bearer '+token}),timeout=30,init_timeout=10) as client:
        report=await (diagnose_schema(client) if args.diagnose_schema else verify_read(client) if args.read else measure(client))
    print(json.dumps(report,sort_keys=True))
    return 0 if report['passed'] else 1


async def verify_read(client):
    """Bounded representative selected Scene workflows; raw IDs stay private."""
    calls=0;rows=[]
    async def call(name,args):
        nonlocal calls
        if calls>=30:raise RuntimeError('MapReadBudgetExceeded')
        calls+=1
        result=await client.call_tool(name,args,raise_on_error=False)
        if result.is_error:
            codes=('MapReadFailed','InvalidRequest','InvalidFoundryResponse','MapDataUnavailable','UnsupportedCapability','PermissionDenied','NotReady',
                'UnsupportedVersion','ContextChanged','ContentChanged','ResponseTooLarge','SceneNotFound','LevelNotFound','BridgeUnavailable')
            code=next((code for code in codes if code+':' in str(result.content)),'MapReadCallFailed')
            raise RuntimeError(code)
        return result
    try:
        async with asyncio.timeout(120):
            calls+=1;catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            tool=next(t for t in catalog if t['name']=='get_map_info')
            selection=await call('execute_javascript',{'code':"""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const scenes=game.scenes.contents.filter(s=>s.testUserPermission(game.user,'OBSERVER'));
const groups=[scenes.find(s=>s.levels.contents.some(l=>l.toObject(true).foreground?.src)),scenes.find(s=>s.levels.contents.every(l=>!l.toObject(true).background?.src)),scenes.find(s=>s.tiles.contents.length)];
return JSON.stringify({active:game.scenes.active?.id??null,scenes:[...new Set(groups.filter(Boolean).map(s=>s.uuid))]});
"""})
            chosen=json.loads(selection.structured_content['value'])
            if not 1<=len(chosen['scenes'])<=3:raise ValueError('Invalid sample')
            for scene in chosen['scenes']:
                revision=None
                for section in ('assets','tiles'):
                    args=dict(scene_uuid=scene,section=section);seen=set();total=None;pages=0;raw_bytes=0;protocol_bytes=0;partial=False
                    while True:
                        result=await call('get_map_info',args);raw=result.structured_content
                        data=MapInfoResult.model_validate(raw)
                        if data.scene.scene_uuid!=scene or data.section!=section:raise ValueError('Wrong map context')
                        if revision is not None and data.revision!=revision:raise ValueError('Changed sample revision')
                        revision=data.revision;pages+=1
                        if total is None:total=data.total
                        if data.total!=total:raise ValueError('Changed sample count')
                        for row in data.entries:
                            identity=getattr(row,'level_uuid',getattr(row,'tile_uuid',None))
                            if identity in seen:raise ValueError('Duplicate map identity')
                            seen.add(identity)
                        partial|=data.scope_status=='partial'
                        raw_bytes+=len(json.dumps(raw,ensure_ascii=False,separators=(',',':')).encode())
                        envelope=ProtocolResult(content=result.content,structured_content=raw,is_error=result.is_error,meta=result.meta).model_dump(mode='json',by_alias=True,exclude_none=True)
                        protocol_bytes+=len(json.dumps(envelope,ensure_ascii=False,separators=(',',':')).encode())
                        if data.complete:
                            if data.next_cursor is not None or len(seen)!=total:raise ValueError('Incomplete map stream')
                            break
                        if not data.next_cursor or not data.entries:raise ValueError('Nonadvancing map stream')
                        args.update(cursor=data.next_cursor,expected_revision=revision)
                    rows.append(dict(section=section,calls=pages,entries=len(seen),json_bytes=raw_bytes,mcp_bytes=protocol_bytes,
                        complete=True,scope_status='partial' if partial else 'complete'))
            end=await call('execute_javascript',{'code':"return game.scenes.active?.id??null;"})
            if end.structured_content['value']!=chosen['active']:raise ValueError('Active Scene changed')
            return dict(passed=True,calls=calls,samples=len(chosen['scenes']),rows=rows,active_unchanged=True,
                catalog_tools=len(catalog),catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()),
                tool_bytes=len(json.dumps(tool,ensure_ascii=False,separators=(',',':')).encode()))
    except Exception as error:return dict(passed=False,calls=calls,error_type=type(error).__name__,rows=rows,
        **({'failure_code':str(error)} if str(error) in ('MapReadFailed','InvalidRequest','InvalidFoundryResponse','MapDataUnavailable','UnsupportedCapability',
            'PermissionDenied','NotReady','UnsupportedVersion','ContextChanged','ContentChanged','ResponseTooLarge',
            'SceneNotFound','LevelNotFound','BridgeUnavailable') else {}))


async def diagnose_schema(client):
    """One fixed handler/schema-field probe; compact technical output only.

    The development executor clips each returned string at1000 characters;
    full typed-response validation belongs to the actual get_map_info call.
    """
    try:
        async with asyncio.timeout(60):
            result=await client.call_tool('execute_javascript',{'code':r"""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const scene=game.scenes.contents.find(s=>s.testUserPermission(game.user,'OBSERVER')&&s.levels.contents.some(l=>l.toObject(true).foreground?.src));
try{const m=await import('/modules/foundry-mcp/scripts/mapInfo.js');const schema=foundry.documents.TileDocument.schema.getField('texture');
await m.getMapInfo({scene_uuid:scene.uuid,caller_key:'a'.repeat(64)});
return JSON.stringify({handler_valid:true,declared_tile_texture:[...schema.keys()].filter(k=>['anchorX','anchorY','offsetX','offsetY','scaleX','scaleY','rotation','fit','src'].includes(k))});}
catch(e){return JSON.stringify({failed:true,type:['TypeError','RangeError','Error'].includes(e.name)?e.name:'OtherError',locations:(e.stack??'').split('\n').map(s=>s.match(/(mapInfo|mapBrowse)\.js:(\d+):(\d+)/)?.slice(1)).filter(Boolean).slice(0,4)});}
"""},raise_on_error=False)
            if result.is_error:return dict(passed=False,calls=1,failure_code='DiagnosticCallFailed')
            raw=json.loads(result.structured_content['value'])
            if raw.get('failed'):
                return dict(passed=False,calls=1,error_type=raw['type'] if raw.get('type') in ('TypeError','RangeError','Error') else 'OtherError',
                    locations=[v for v in raw.get('locations',[]) if isinstance(v,list) and len(v)==3
                        and v[0] in ('mapInfo','mapBrowse') and all(isinstance(n,str) and n.isdigit() for n in v[1:])][:4])
            if raw.get('handler_valid') is not True:raise ValueError('Invalid diagnostic summary')
            allowed={'anchorX','anchorY','offsetX','offsetY','scaleX','scaleY','rotation','fit','src'}
            return dict(passed=True,calls=1,handler_valid=True,
                declared_tile_texture=sorted(k for k in raw.get('declared_tile_texture',[]) if isinstance(k,str) and k in allowed))
    except Exception as error:return dict(passed=False,calls=1,error_type=type(error).__name__)


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
