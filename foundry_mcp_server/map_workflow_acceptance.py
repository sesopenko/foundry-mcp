"""Read-only existing-world map workflow; called by the shared local verifier."""
import asyncio
import json
from mcp.types import CallToolResult as ProtocolResult

from .image_preview_live_support import Budget,compact,require

GUARD="if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');"
SELECT=GUARD+"""
const scene=game.scenes.contents.find(s=>s.testUserPermission(game.user,'OBSERVER')&&s.width===6800&&s.height===9000&&s.notes.size);
if(!scene)throw Error('Representative map unavailable');
const level=scene.levels.contents.find(l=>l.testUserPermission(game.user,'OBSERVER')&&l.toObject(true).background?.src);
if(!level)throw Error('Background unavailable');
const d=scene.getDimensions(),notes=scene.notes.contents.filter(n=>n.testUserPermission(game.user,'OBSERVER')&&n.includedInLevel(level)).sort((a,b)=>a.uuid<b.uuid?-1:a.uuid>b.uuid?1:0);
const visible=notes.map((n,i)=>({key:'N'+(i+1),x:n.x-d.sceneX,y:n.y-d.sceneY})).filter(n=>n.x>=0&&n.y>=0&&n.x<6800&&n.y<9000);
if(!visible.length)throw Error('No visible pins');
return JSON.stringify({scene_uuid:scene.uuid,level_id:level.id,active:game.scenes.active?.id??null,grid:scene.toObject(true).grid,
 count:visible.length,pin:visible[0],folder:scene.toObject(true).folder??null});
"""


def legend_check(scene_uuid,level_id,rows):
    """Compare typed returned identities/coordinates with independent public docs."""
    require(len(rows)<=100)
    projection=[dict(key=row['key'],note=row['note_uuid'],x=row['x'],y=row['y'],
        journal=row['journal']['journal_uuid'] if row['journal'] else None,
        page=row['page']['page_uuid'] if row['page'] else None) for row in rows]
    return GUARD+'const scene=game.scenes.get('+json.dumps(scene_uuid.split('.')[1])+'),level=scene.levels.get('+json.dumps(level_id)+');'+"""
const notes=scene.notes.contents.filter(n=>n.testUserPermission(game.user,'OBSERVER')&&n.includedInLevel(level)).sort((a,b)=>a.uuid<b.uuid?-1:a.uuid>b.uuid?1:0);
const rows="""+json.dumps(projection,separators=(',',':'))+""";
const matched=rows.every(row=>{const n=notes[Number(row.key.slice(1))-1];if(!n||n.uuid!==row.note||n.x!==row.x||n.y!==row.y)return false;
 const entry=n.entry,page=n.page;const allowedEntry=entry&&entry.testUserPermission(game.user,'OBSERVER');
 const allowedPage=page&&page.testUserPermission(game.user,'OBSERVER');
 return row.journal===(allowedEntry?entry.uuid:null)&&row.page===(allowedEntry&&allowedPage?page.uuid:null);});
return JSON.stringify({matched,count:rows.length});
"""


async def verify_map(client,reader,*,budget=None):
    budget=budget or Budget(seconds=900);rows=[];report=dict(passed=False)
    async def call(name,args,label):
        budget.admit();response=await client.call_tool(name,args,raise_on_error=False)
        require(not response.is_error);value=response.structured_content
        envelope=ProtocolResult(content=response.content,structured_content=value,is_error=False,meta=response.meta).model_dump(mode='json',by_alias=True,exclude_none=True)
        rows.append(dict(label=label,json_bytes=compact(value),mcp_bytes=compact(envelope),complete=value.get('complete',True)))
        return value
    async def execute(code,label):return json.loads((await call('execute_javascript',dict(code=code),label))['value'])
    async def pages(name,args,label):
        entries=[];revision=None
        for _ in range(20):
            value=await call(name,args,label)
            require(revision is None or revision==value['revision']);revision=value['revision']
            entries.extend(value['entries'])
            if value['complete']:return value,entries
            require(value['next_cursor'] is not None);args={**args,'cursor':value['next_cursor']}
        raise ValueError('MapPageBudgetExceeded')
    try:
        async with asyncio.timeout(900):
            budget.admit();catalog=await client.list_tools(max_pages=1)
            report.update(catalog_tools=len(catalog),catalog_bytes=compact([tool.model_dump(mode='json') for tool in catalog]),
                tool_bytes={tool.name:compact(tool.model_dump(mode='json')) for tool in catalog if tool.name in ('browse_maps','get_map_info','get_foundry_image_info','get_foundry_image_url')})
            selected=await execute(SELECT,'independent_metadata')
            queue=[dict()];folders={};maps={};names=[]
            while queue:
                args=queue.pop(0);value,entries=await pages('browse_maps',args,'complete_catalog')
                require(value['scope_status']=='complete')
                for entry in entries:
                    require(entry['parent_uuid']==args.get('folder_uuid'))
                    if entry['kind']=='folder':
                        require(entry['folder_uuid'] not in folders);folders[entry['folder_uuid']]=entry
                        queue.append(entry['next_call']['arguments'])
                    else:require(entry['scene_uuid'] not in maps);maps[entry['scene_uuid']]=entry
                    names.append((entry['kind'],entry['name']))
            entry=maps[selected['scene_uuid']]
            require(entry['parent_uuid']==('Folder.'+selected['folder'] if selected['folder'] else None))
            assets,levels=await pages('get_map_info',entry['next_call']['arguments'],'all_assets')
            level=next(row for row in levels if row['level_id']==selected['level_id'])
            require(assets['grid']==selected['grid'])
            tiles,tile_rows=await pages('get_map_info',dict(scene_uuid=selected['scene_uuid'],level_id=selected['level_id'],section='tiles'),'selected_tiles')
            source_call=level['background']['info_next_call']
            info=await call(source_call['tool'],source_call['arguments'],'map_source')
            require((info['width'],info['height'])==(6800,9000))
            x=max(0,min(info['width']-800,int(selected['pin']['x'])-100))
            y=max(0,min(info['height']-600,int(selected['pin']['y'])-100))
            crop=dict(x=x,y=y,width=800,height=600)
            outputs=[];legend_rows=0;legend_pages=0
            for label,region in [('overview',None),('detail',crop)]:
                request=dict(source_id=info['source_id'],map_notes=True)
                if region:request['crop']=region
                output=await call('get_foundry_image_url',dict(request=request),'annotated_'+label)
                require(output['source_id']==info['source_id'])
                notes=output['map_notes'];require(notes['map']==source_call['arguments']['request']['map'])
                require(notes['rendered_count']>0)
                if region:require(selected['pin']['key'] in notes['keys'])
                else:require(notes['total_in_region']==selected['count'])
                pin=(int(selected['pin']['x'])-crop['x'],int(selected['pin']['y'])-crop['y']) if region else None
                reading=reader(output,label,pin)
                follow=notes['legend_next_call'];before=len(rows)
                value,legend=await pages(follow['tool'],follow['arguments'],'legend_'+label)
                legend_pages+=len(rows)-before;legend_rows+=len(legend)
                require([row['key'] for row in legend]==notes['keys'])
                require(value['revision']==notes['revision'] and value['level_id']==selected['level_id'])
                checked=await execute(legend_check(selected['scene_uuid'],selected['level_id'],legend),'independent_legend_'+label)
                require(checked==dict(matched=True,count=len(legend)))
                outputs.append(dict(case=label,width=output['width'],height=output['height'],bytes=output['size_bytes'],
                    total=notes['total_in_region'],rendered=notes['rendered_count'],omitted=notes['omitted_count'],
                    complete=notes['complete'],scope_status=notes['scope_status'],omission_reasons=notes['omission_reasons'],reader=reading))
            active=await execute(GUARD+'return JSON.stringify({active:game.scenes.active?.id??null});','active')
            require(active['active']==selected['active'])
            report.update(passed=True,folders=len(folders),maps=len(maps),duplicate_names=len(names)-len(set(names)),
                levels=len(levels),tiles=len(tile_rows),legend_rows=legend_rows,legend_pages=legend_pages,
                outputs=outputs,active_unchanged=True,persisted_fixtures=0,
                pending=['Public HTTPS and target-ChatGPT visual/key-following acceptance remain14b.'])
    except Exception as error:report.update(passed=False,error_type=type(error).__name__)
    report.update(calls=budget.calls,rows=rows)
    return report
