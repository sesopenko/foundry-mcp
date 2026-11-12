"""Note identity baseline:2 read-only MCP calls/120s; no private note content."""
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
const counts={scenes:0,notes:0,empty:0,null:0,omitted:0,explicit:0,invalid:0,unlinked:0,missing_entry:0,denied_entry:0,linked:0,overrides:0,finite_coordinates:0};
for(const scene of game.scenes.contents){
 if(!scene.testUserPermission(game.user,'OBSERVER'))continue;counts.scenes++;
 for(const note of scene.getEmbeddedCollection('Note').contents){
  if(!note.testUserPermission(game.user,'OBSERVER'))continue;
  const s=note.toObject(true);counts.notes++;
  if(s.levels===undefined)counts.omitted++;
  else if(s.levels===null)counts.null++;
  else if(Array.isArray(s.levels)||s.levels instanceof Set){const ids=[...s.levels];counts[ids.length?'explicit':'empty']++;}
  else counts.invalid++;
  if(typeof s.text==='string'&&s.text.length)counts.overrides++;
  if(Number.isFinite(s.x)&&Number.isFinite(s.y))counts.finite_coordinates++;
  if(!s.entryId){counts.unlinked++;continue;}
  const entry=note.entry;
  if(!entry){counts.missing_entry++;continue;}
  if(!entry.testUserPermission(game.user,'OBSERVER'))counts.denied_entry++;else counts.linked++;
 }
}
const options=foundry.documents.NoteDocument.schema.getField('levels').options;
const label=typeof options.label==='string'?game.i18n.localize(options.label).slice(0,128):null;
const hint=typeof options.hint==='string'?game.i18n.localize(options.hint).slice(0,128):null;
return JSON.stringify({version:game.version,counts,field_label:label,field_hint:hint,active_unchanged:before===game.scenes.active?.id});
"""


async def measure(client):
    calls=0
    try:
        async with asyncio.timeout(120):
            calls+=1
            catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            calls+=1
            result=await client.call_tool('execute_javascript',{'code':CODE})
            data=json.loads(result.structured_content['value'])
            if data['version']!='14.369' or data['active_unchanged'] is not True:raise ValueError('Invalid runtime')
            keys=('scenes','notes','empty','null','omitted','explicit','invalid','unlinked','missing_entry','denied_entry','linked','overrides','finite_coordinates')
            counts={k:data['counts'][k] for k in keys}
            if any(type(v) is not int or not 0<=v<=10000000 for v in counts.values()):raise ValueError('Invalid counts')
            if sum(counts[k] for k in ('empty','null','omitted','explicit','invalid'))!=counts['notes']:raise ValueError('Inconsistent applicability counts')
            if sum(counts[k] for k in ('unlinked','missing_entry','denied_entry','linked'))!=counts['notes']:raise ValueError('Inconsistent target counts')
            hints={k:data[k] for k in ('field_label','field_hint')}
            if any(v is not None and (type(v) is not str or len(v)>128) for v in hints.values()):raise ValueError('Invalid schema hint')
            return dict(passed=True,calls=calls,version='14.369',counts=counts,active_unchanged=True,**hints,
                catalog_tools=len(catalog),catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()))
    except Exception as error:return dict(passed=False,calls=calls,error_type=type(error).__name__)


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--membership',action='store_true',help='Verify public note membership using unpersisted documents:1 call/60s.')
    parser.add_argument('--legend',action='store_true',help='Verify complete native Note legend and key follow-up:<=30 calls/120s.')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    token=next(line.partition('=')[2].strip() for line in (root/'.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip()=='FOUNDRY_MCP_CALLER_TOKEN')
    async with Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',headers={'Authorization':'Bearer '+token}),timeout=30,init_timeout=10) as client:
        report=await (verify_legend(client) if args.legend else verify_membership(client) if args.membership else measure(client))
    print(json.dumps(report,sort_keys=True))
    return 0 if report['passed'] else 1


async def verify_membership(client):
    """No create/update/view calls: constructed public documents never persist."""
    try:
        async with asyncio.timeout(60):
            result=await client.call_tool('execute_javascript',{'code':"""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const scene=game.scenes.contents.find(s=>s.testUserPermission(game.user,'OBSERVER')&&s.levels.contents.length&&s.notes.contents.length);
const level=scene.levels.contents[0],before=scene.notes.size,active=game.scenes.active?.id;
const rows=[];
for(const [label,levels] of [['empty',[]],['null',null],['explicit',[level.id]],['foreign',['NoSuchLevel00001']]]){
 const note=new foundry.documents.NoteDocument({_id:'ImgNoteProbe0001',text:'temporary verification',x:0,y:0,levels,
  flags:{'foundry-mcp':{verification:'image-note-membership-M03a'}}},{parent:scene});
 rows.push({label,included:note.includedInLevel(level),included_by_id:note.includedInLevel(level.id),stored_null:note.toObject(true).levels===null});
}
let real_empty=0,real_included=0;
for(const note of scene.notes.contents){if(!note.testUserPermission(game.user,'OBSERVER'))continue;
 const s=note.toObject(true);if(Array.isArray(s.levels)&&!s.levels.length){real_empty++;if(note.includedInLevel(level))real_included++;}}
return JSON.stringify({rows,real_empty,real_included,collection_unchanged:before===scene.notes.size,active_unchanged:active===game.scenes.active?.id});
"""},raise_on_error=False)
            if result.is_error:return dict(passed=False,calls=1,error_type='MembershipCallFailed')
            data=json.loads(result.structured_content['value'])
            if data['collection_unchanged'] is not True or data['active_unchanged'] is not True:raise ValueError('Mutation observed')
            if [r['label'] for r in data['rows']]!=['empty','null','explicit','foreign']:raise ValueError('Invalid cases')
            rows=[]
            for row in data['rows']:
                if any(type(row[k]) is not bool for k in ('included','included_by_id','stored_null')):raise ValueError('Invalid result')
                expected=row['label']!='foreign'
                if row['included']!=expected or row['included_by_id']!=expected:raise ValueError('Unexpected applicability')
                rows.append({k:row[k] for k in ('label','included','included_by_id','stored_null')})
            if type(data['real_empty']) is not int or data['real_empty']<1 or data['real_empty']!=data['real_included']:raise ValueError('Existing applicability mismatch')
            return dict(passed=True,calls=1,rows=rows,real_empty=data['real_empty'],real_included=data['real_included'],
                collection_unchanged=True,active_unchanged=True,persisted_fixtures=0)
    except Exception as error:return dict(passed=False,calls=1,error_type=type(error).__name__)


async def verify_legend(client):
    """Private exact identities stay in this bounded complete-stream verifier."""
    calls=0;rows={}
    async def call(name,args,label=None):
        nonlocal calls
        if calls>=30:raise RuntimeError('LegendBudgetExceeded')
        calls+=1
        result=await client.call_tool(name,args,raise_on_error=False)
        if result.is_error:
            codes=('InvalidFoundryResponse','MapReadFailed','MapDataUnavailable','ContentChanged','UnsupportedCapability','BridgeUnavailable')
            raise RuntimeError(next((c for c in codes if c+':' in str(result.content)),'LegendCallFailed'))
        if label:
            raw=result.structured_content
            envelope=ProtocolResult(content=result.content,structured_content=raw,is_error=result.is_error,meta=result.meta).model_dump(mode='json',by_alias=True,exclude_none=True)
            row=rows.setdefault(label,dict(calls=0,json_bytes=0,mcp_bytes=0,complete=False))
            row['calls']+=1;row['json_bytes']+=len(json.dumps(raw,ensure_ascii=False,separators=(',',':')).encode())
            row['mcp_bytes']+=len(json.dumps(envelope,ensure_ascii=False,separators=(',',':')).encode());row['complete']=raw['complete']
        return result.structured_content
    try:
        async with asyncio.timeout(120):
            calls+=1;catalog=[t.model_dump(mode='json') for t in await client.list_tools(max_pages=1)]
            tool=next(t for t in catalog if t['name']=='get_map_info')
            selection=await call('execute_javascript',{'code':"""
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const scene=game.scenes.contents.find(s=>s.testUserPermission(game.user,'OBSERVER')&&s.notes.size>=20&&s.notes.size<=40&&s.levels.contents.length);
if(!scene)throw Error('No bounded representative Scene');
return JSON.stringify({scene_uuid:scene.uuid,level_id:scene.levels.contents[0].id,active:game.scenes.active?.id??null});
"""})
            selected=json.loads(selection['value']);base={k:selected[k] for k in ('scene_uuid','level_id')}
            asset=await call('get_map_info',base,'assets_default');revision=asset['revision']
            args={**base,'section':'notes','expected_revision':revision};all_notes=[];seen=set();total=None;partial=False
            while True:
                raw=await call('get_map_info',args,'complete_legend');data=MapInfoResult.model_validate(raw)
                if data.revision!=revision or data.scene.scene_uuid!=base['scene_uuid'] or data.level_id!=base['level_id']:raise ValueError('Wrong legend context')
                if total is None:total=data.total
                if total!=data.total:raise ValueError('Changed legend count')
                partial|=data.scope_status=='partial'
                for note in data.entries:
                    if note.kind!='note' or note.note_uuid in seen or note.key!='N'+str(len(all_notes)+1):raise ValueError('Unstable alias identity')
                    seen.add(note.note_uuid);all_notes.append(note.model_dump())
                if data.complete:
                    if data.next_cursor is not None or len(all_notes)!=total:raise ValueError('Incomplete legend')
                    break
                if not data.next_cursor or not data.entries:raise ValueError('Nonadvancing legend')
                args={**args,'cursor':data.next_cursor}
            if not all_notes:raise ValueError('Empty representative legend')
            keys=[all_notes[0]['key'],all_notes[-1]['key']]
            filtered=await call('get_map_info',{**base,'section':'notes','expected_revision':revision,'note_keys':keys},'key_followup')
            if not filtered['complete'] or filtered['revision']!=revision or filtered['entries']!=[all_notes[0],all_notes[-1]]:raise ValueError('Wrong key identity')
            expanded=await call('get_map_info',{**base,'section':'notes','expected_revision':revision,'limit':100,'max_bytes':48000},'expanded_legend')
            if not expanded['complete'] or expanded['revision']!=revision or expanded['entries']!=all_notes:raise ValueError('Changed expanded legend')
            active=await call('execute_javascript',{'code':'return game.scenes.active?.id??null;'})
            if active['value']!=selected['active']:raise ValueError('Active Scene changed')
            return dict(passed=True,calls=calls,notes=total,filter_keys=len(keys),active_unchanged=True,complete=True,
                scope_status='partial' if partial else 'complete',rows=rows,catalog_tools=len(catalog),
                catalog_bytes=len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode()),
                tool_bytes=len(json.dumps(tool,ensure_ascii=False,separators=(',',':')).encode()))
    except Exception as error:
        codes=('InvalidFoundryResponse','MapReadFailed','MapDataUnavailable','ContentChanged','UnsupportedCapability','BridgeUnavailable')
        return dict(passed=False,calls=calls,error_type=type(error).__name__,rows=rows,
            **({'failure_code':str(error)} if str(error) in codes else {}))


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
