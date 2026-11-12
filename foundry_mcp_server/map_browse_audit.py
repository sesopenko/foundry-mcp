"""Pre-map-tool localhost baseline:2 MCP requests/120s, read-only aggregates.

Existing dedicated14.369/test GM only; no raw Scene/folder data is returned.
Uses documented collections/schema fields/ForeignDocumentField/permissions.
"""
import asyncio
import argparse
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.types import CallToolResult as ProtocolResult

CODE="""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const before=game.scenes.active?.id;
const folders=game.folders.contents.filter(f=>f.type==='Scene'&&f.testUserPermission(game.user,'OBSERVER'));
const scenes=game.scenes.contents.filter(s=>s.testUserPermission(game.user,'OBSERVER'));
const parent=d=>typeof d.folder==='string'?d.folder:d.folder?.id??null;
const source_fields_match=[...folders.slice(0,3),...scenes.slice(0,3)].every(d=>parent(d)===(d.toObject(true).folder??null));
const children=p=>[
  ...folders.filter(d=>parent(d)===p).map(d=>({kind:'folder',uuid:d.uuid,name:d.name,parent_uuid:p?'Folder.'+p:null,sort:d.sort,sorting:d.sorting})),
  ...scenes.filter(d=>parent(d)===p).map(d=>({kind:'map',uuid:d.uuid,name:d.name,parent_uuid:p?'Folder.'+p:null,sort:d.sort}))
];
const row=(label,p)=>{const all=children(p);const result={entries:all.slice(0,10),total:all.length,complete:all.length<=10};return{label,entries:result.entries.length,total:all.length,complete:result.complete,json_bytes:new TextEncoder().encode(JSON.stringify(result)).length};};
const rows=[row('root_default',null)];
if(folders.length)rows.push(row('folder_default',folders[0].id));
return JSON.stringify({version:game.version,folders:folders.length,scenes:scenes.length,source_fields_match,active_unchanged:before===game.scenes.active?.id,rows});
"""


def count(value):
    if type(value) is not int or not 0<=value<=10000000:raise ValueError('Invalid aggregate')
    return value


async def measure(client):
    calls=0
    try:
        async with asyncio.timeout(120):
            calls+=1
            catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            calls+=1
            result=await client.call_tool('execute_javascript',{'code':CODE})
            data=json.loads(result.structured_content['value'])
            if data['version']!='14.369' or data['source_fields_match'] is not True or data['active_unchanged'] is not True:
                raise ValueError('Invalid baseline runtime')
            rows=[]
            if not 1<=len(data['rows'])<=2:raise ValueError('Invalid aggregate')
            for index,row in enumerate(data['rows']):
                if row['label']!=('root_default','folder_default')[index] or type(row['complete']) is not bool:
                    raise ValueError('Invalid aggregate')
                entries,total=count(row['entries']),count(row['total'])
                if entries!=min(10,total) or row['complete']!=(entries==total):raise ValueError('Invalid aggregate')
                rows.append(dict(label=row['label'],entries=entries,total=total,complete=row['complete'],json_bytes=count(row['json_bytes'])))
            return dict(passed=True,calls=calls,version=data['version'],folders=count(data['folders']),scenes=count(data['scenes']),
                source_fields_match=True,active_unchanged=True,rows=rows,catalog_tools=len(catalog),
                catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()))
    except Exception as error:
        return dict(passed=False,calls=calls,error_type=type(error).__name__)


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browse',action='store_true',help='Verify implemented browse_maps navigation, <=30 calls/120s.')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    token=next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',
            headers={'Authorization':'Bearer '+token}),timeout=30,init_timeout=10) as client:
        report=await (verify_browse(client) if args.browse else measure(client))
    print(json.dumps(report,sort_keys=True))
    return 0 if report['passed'] else 1


async def verify_browse(client):
    """Fresh-client folder next calls; private raw metadata stays in this process."""
    calls=0;rows={};folders=set();scenes=set();folder_names=[];scene_names=[];partial=False
    def reserve():
        nonlocal calls
        if calls>=30:raise RuntimeError('MapVerificationBudgetExceeded')
        calls+=1
    async def active():
        reserve()
        result=await client.call_tool('execute_javascript',{'code':"if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');return game.scenes.active?.id??null;"})
        return result.structured_content['value']
    async def call(args,label):
        nonlocal partial
        reserve()
        result=await client.call_tool('browse_maps',args,raise_on_error=False)
        if result.is_error:raise RuntimeError('MapVerificationCallFailed')
        data=result.structured_content
        if data['location']['folder_uuid']!=args.get('folder_uuid'):raise RuntimeError('WrongMapLocation')
        partial|=data['scope_status']=='partial'
        envelope=ProtocolResult(content=result.content,structured_content=data,is_error=result.is_error,meta=result.meta).model_dump(mode='json',by_alias=True,exclude_none=True)
        row=rows.setdefault(label,dict(calls=0,json_bytes=0,mcp_bytes=0,complete=False))
        row['calls']+=1
        row['json_bytes']+=len(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode())
        row['mcp_bytes']+=len(json.dumps(envelope,ensure_ascii=False,separators=(',',':')).encode())
        row['complete']=data['complete'] and data['next_cursor'] is None
        return data
    try:
        async with asyncio.timeout(120):
            reserve();catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            if not any(t['name']=='browse_maps' for t in catalog):raise RuntimeError('MissingMapTool')
            before=await active()
            root=await call({},'root_default')
            expanded=await call({'limit':100,'max_bytes':48000},'root_expanded')
            if root['total']!=expanded['total']:raise RuntimeError('ChangedMapCatalog')
            if root['entries']:
                filtered=await call({'name_contains':root['entries'][0]['name']},'literal_root')
                if not filtered['entries']:raise RuntimeError('LiteralMapMatchFailed')
            queue=[({},root)];seen_locations=set()
            while queue:
                args,page=queue.pop(0);folder=args.get('folder_uuid')
                if folder in seen_locations:raise RuntimeError('DuplicateFolderTraversal')
                seen_locations.add(folder)
                while True:
                    for entry in page['entries']:
                        if entry['parent_uuid']!=folder:raise RuntimeError('WrongMapParent')
                        if entry['kind']=='folder':
                            if entry['folder_uuid'] in folders:raise RuntimeError('DuplicateFolderIdentity')
                            folders.add(entry['folder_uuid']);folder_names.append(entry['name'])
                            queue.append((entry['next_call']['arguments'],None))
                        else:
                            if entry['scene_uuid'] in scenes:raise RuntimeError('DuplicateSceneIdentity')
                            scenes.add(entry['scene_uuid']);scene_names.append(entry['name'])
                    if page['complete']:break
                    page=await call({**args,'cursor':page['next_cursor']},'complete_navigation')
                if queue and queue[0][1] is None:
                    next_args,_=queue[0];queue[0]=(next_args,await call(next_args,'complete_navigation'))
            if before!=await active():raise RuntimeError('ActiveSceneChanged')
            return dict(passed=True,calls=calls,catalog_tools=len(catalog),
                catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()),
                folders=len(folders),scenes=len(scenes),duplicate_folder_names=len(folder_names)-len(set(folder_names)),
                duplicate_map_names=len(scene_names)-len(set(scene_names)),active_unchanged=True,
                scope_status='partial' if partial else 'complete',rows=rows)
    except Exception as error:return dict(passed=False,calls=calls,error_type=type(error).__name__,rows=rows)


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
