"""Core14 geometry/default-placement baseline:2 read-only MCP calls/120s."""
import asyncio
import argparse
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from .map_geometry import SceneImageMapping
from .mcp_server.image_preview_models import ImageInfoResult

CODE="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const active=game.scenes.active?.id,before=game.scenes.size;
const canonical=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
let levels=0,defaults_matching=0,initial_objects=0,cleaned_objects=0;
const field=foundry.documents.Level.schema.getField('textures');
for(const scene of game.scenes.contents){if(!scene.testUserPermission(game.user,'OBSERVER'))continue;
 for(const level of scene.levels.contents){if(!level.testUserPermission(game.user,'OBSERVER'))continue;
  const source=level.toObject(true),initial=field.getInitialValue(source),cleaned=field.clean(undefined,{source});levels++;
  if(initial&&typeof initial==='object')initial_objects++;
  if(cleaned&&typeof cleaned==='object')cleaned_objects++;
  if(canonical(source.textures)===canonical(cleaned))defaults_matching++;
 }}
const rows=[];
for(const [label,width,height,shiftX,shiftY] of [['normal',6800,9000,0,0],['shifted',6800,9000,120,-80],['scaled',3400,4500,0,0]]){
 const scene=new foundry.documents.Scene({_id:'ImgGeomProbe0001',name:'temporary verification',width,height,padding:.25,shiftX,shiftY,
  grid:{type:1,size:200,distance:5,units:'ft'},flags:{'foundry-mcp':{verification:'image-geometry-M03b'}}});
 const d=scene.getDimensions();rows.push({label,sceneX:d.sceneX,sceneY:d.sceneY,sceneWidth:d.sceneWidth,sceneHeight:d.sceneHeight});
}
return JSON.stringify({version:game.version,levels,defaults_matching,initial_objects,cleaned_objects,rows,active_unchanged:active===game.scenes.active?.id,collection_unchanged:before===game.scenes.size});
"""


async def measure(client):
    calls=0
    try:
        async with asyncio.timeout(120):
            calls+=1;catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            calls+=1;result=await client.call_tool('execute_javascript',{'code':CODE})
            data=json.loads(result.structured_content['value'])
            if data['version']!='14.369' or data['active_unchanged'] is not True or data['collection_unchanged'] is not True:raise ValueError('Wrong runtime or mutation')
            counts={k:data[k] for k in ('levels','defaults_matching','initial_objects','cleaned_objects')}
            if any(type(v) is not int or not 0<=v<=1000000 for v in counts.values()):raise ValueError('Invalid counts')
            if not counts['levels'] or any(counts[k]>counts['levels'] for k in counts):raise ValueError('Invalid count relation')
            if len(data['rows'])!=3:raise ValueError('Invalid geometry cases')
            rows=[]
            for expected,row in zip(('normal','shifted','scaled'),data['rows']):
                if row['label']!=expected:raise ValueError('Invalid geometry case')
                clean={k:row[k] for k in ('sceneX','sceneY','sceneWidth','sceneHeight')}
                if any(type(v) not in (int,float) or not -1000000<=v<=1000000 for v in clean.values()):raise ValueError('Invalid geometry')
                rows.append(dict(label=expected,**clean))
            return dict(passed=True,calls=calls,version='14.369',counts=counts,rows=rows,active_unchanged=True,
                collection_unchanged=True,persisted_fixtures=0,catalog_tools=len(catalog),
                catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()))
    except Exception as error:return dict(passed=False,calls=calls,error_type=type(error).__name__)


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',action='store_true',help='Native module dispatch + public source probe:<=6 calls/600s, no fixtures.')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    token=next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token}),timeout=30,init_timeout=10) as client:
        report=await (verify_context(client) if args.context else measure(client))
    print(json.dumps(report,sort_keys=True));return 0 if report['passed'] else 1


async def verify_context(client):
    """Bounded native handler/probe evidence; source-cache attachment belongs M05."""
    calls=0
    async def call(name,args):
        nonlocal calls
        if calls>=6:raise RuntimeError('ContextVerificationBudgetExceeded')
        calls+=1
        result=await client.call_tool(name,args,raise_on_error=False)
        if result.is_error:raise RuntimeError('NativeContextCallFailed')
        return result.structured_content
    try:
        async with asyncio.timeout(600):
            calls+=1;catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            data=await call('execute_javascript',{'code':"""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const scene=game.scenes.contents.find(s=>s.testUserPermission(game.user,'OBSERVER')&&s.width===6800&&s.height===9000&&s.notes.size);
if(!scene)throw Error('No verified representative map');
const level=scene.levels.contents.find(l=>l.testUserPermission(game.user,'OBSERVER')&&l.toObject(true).background?.src);
if(!level)throw Error('No background level');
const {handleRpcMessage}=await import('/modules/foundry-mcp/scripts/foundryBridge.js');
const map={scene_uuid:scene.uuid,level_id:level.id,role:'background'};
const reply=await handleRpcMessage({id:'geometry-context-verification',method:'getMapImageContext',params:{map,caller_key:'d'.repeat(64)}});
if(reply.error)throw Error('Native context failed');const c=reply.result;
return JSON.stringify({map,revision:c.revision,alias_digest:c.alias_digest,reference_digest:c.reference_digest,rectangle:c.rectangle,supported:c.mapping.status==='supported',active:game.scenes.active?.id??null,context_bytes:new TextEncoder().encode(JSON.stringify(c)).length});
"""})
            context=json.loads(data['value'])
            if context['supported'] is not True:raise ValueError('Unsupported representative mapping')
            selected=context['map']
            assets=await call('get_map_info',dict(scene_uuid=selected['scene_uuid'],level_id=selected['level_id'],expected_revision=context['revision']))
            media=assets['entries'][0]['background']
            if media['reference_status']!='safe' or media['media_kind']!='image':raise ValueError('A safe local source is required for this pre-M05 verifier')
            info=ImageInfoResult.model_validate(await call('get_foundry_image_info',{'request':{'src':media['reference']}}))
            rect=context['rectangle'];mapping=SceneImageMapping(rect['sceneX'],rect['sceneY'],rect['sceneWidth'],rect['sceneHeight'],info.width,info.height)
            args=dict(map=selected,expected_revision=context['revision'],expected_reference_digest=context['reference_digest'],
                source_size=dict(width=info.width,height=info.height),source_scope='e'*64,
                crop=dict(x=0,y=0,width=info.width,height=info.height),caller_key='d'*64,max_bytes=48000)
            async def candidates(request):
                code="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const request=VERIFICATION_REQUEST;
const {handleRpcMessage}=await import('/modules/foundry-mcp/scripts/foundryBridge.js');
const reply=await handleRpcMessage({id:'geometry-region-verification',method:'getMapRegionCandidates',params:request});
if(reply.error)throw Error('Native candidates failed');const r=reply.result;
return JSON.stringify({revision:r.context.revision,alias_digest:r.context.alias_digest,total:r.total_in_region,returned:r.entries.length,complete:r.complete,scope_status:r.context.scope_status,
samples:r.entries.slice(0,2).map(n=>({key:n.key,x:n.x,y:n.y,source_x:n.source_x,source_y:n.source_y})),result_bytes:new TextEncoder().encode(JSON.stringify(r)).length,active:game.scenes.active?.id??null});
""".replace('VERIFICATION_REQUEST',json.dumps(request,ensure_ascii=False,separators=(',',':')))
                return json.loads((await call('execute_javascript',{'code':code}))['value'])
            whole=await candidates(args)
            if not whole['samples'] or whole['revision']!=context['revision'] or whole['alias_digest']!=context['alias_digest']:raise ValueError('Wrong candidate snapshot')
            for pin in whole['samples']:
                expected=mapping.source_point(pin['x'],pin['y'])
                if any(abs(a-b)>1e-9 for a,b in zip(expected,(pin['source_x'],pin['source_y']))):raise ValueError('Wrong candidate geometry')
            pin=whole['samples'][0]
            detail=await candidates({**args,'crop':dict(x=int(pin['source_x']),y=int(pin['source_y']),width=1,height=1)})
            if pin['key'] not in [n['key'] for n in detail['samples']] or detail['revision']!=context['revision']:raise ValueError('Detail alias changed')
            if whole['active']!=context['active'] or detail['active']!=context['active']:raise ValueError('Active Scene changed')
            return dict(passed=True,calls=calls,source_width=info.width,source_height=info.height,source_bytes=info.size_bytes,
                mapping_validated=True,detail_alias_preserved=True,total_in_region=whole['total'],returned=whole['returned'],
                complete=whole['complete'],scope_status=whole['scope_status'],context_bytes=context['context_bytes'],
                candidate_bytes=whole['result_bytes'],detail_candidate_bytes=detail['result_bytes'],active_unchanged=True,
                catalog_tools=len(catalog),catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()),
                persisted_fixtures=0)
    except Exception as error:return dict(passed=False,calls=calls,error_type=type(error).__name__)


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
