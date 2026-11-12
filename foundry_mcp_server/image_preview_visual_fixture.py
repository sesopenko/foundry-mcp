"""Bounded visual-handoff preparation using existing marked fixture owners."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from .image_preview_live_support import AssetFixture,Budget,require
from .image_preview_visual_handoff import load_bundle,prompts,public_report


MAP_TARGET="""
const scene=game.scenes.contents.find(s=>s.testUserPermission(game.user,'OBSERVER')&&s.width===6800&&s.height===9000&&s.notes.size);
if(!scene)throw Error('Representative map unavailable');
const names=[];let id=scene.toObject(true).folder,depth=0;
while(id){if(depth++>=16)throw Error('Hierarchy depth');const folder=game.folders.get(id);if(!folder?.testUserPermission(game.user,'OBSERVER'))throw Error('Folder unavailable');names.unshift(folder.name);id=folder.toObject(true).folder;}
const level=scene.levels.contents.find(l=>l.testUserPermission(game.user,'OBSERVER')&&l.toObject(true).background?.src);
if(!level)throw Error('Level unavailable');
const result={map_name:scene.name,ancestry:names.join(' / '),level_name:level.name};
"""


async def prepare(client,directory,data_root,journal_fixture):
    """Retain only newly marked fixture until explicit cleanup, no public issuance."""
    directory=Path(directory);expected,state=load_bundle(directory);require(not state['ready'])
    budget=Budget(limit=20,seconds=180);marker=state['marker'];asset=AssetFixture(data_root,marker)
    # Cleanup ends a fixture lifecycle, not the browser writer's retry ledger.
    # A later preparation is a new operation, while marker ownership persists.
    generation=uuid4().hex[:8]
    async def call(name,args):
        budget.admit();response=await client.call_tool(name,args,raise_on_error=False)
        require(not response.is_error);return response.structured_content
    try:
        async with asyncio.timeout(180):
            context=await call('execute_javascript',dict(code=journal_fixture.code(MAP_TARGET,marker)))
            target=json.loads(context['value'])
            asset.__enter__();(asset.path/asset.filename).write_bytes((directory/state['filename']).read_bytes())
            guidance=await call('get_writing_guidance',dict(max_bytes=48000))
            async def write(serial,action):return await call('write_journal',dict(request_id='journal-'+marker+'-'+generation+'-'+str(serial),
                gm_authorized=True,guidance_timestamp=guidance['timestamp'],action=action))
            journal=await write(1,dict(operation='create_journal',name='MCP visual fixture '+marker))
            parent=await call('get_journal_write_context',dict(target=dict(kind='journal',journal_id=journal['identity']['journal_id'])))
            page=await write(2,dict(operation='create_page',journal_id=journal['identity']['journal_id'],parent_revision=parent['revision'],
                name='Visual fixture',content='<p>Visual acceptance fixture.</p><img src="'+asset.src+'" alt="">'))
            updated=prompts(page['identity']['page_uuid'],target['map_name'],target['ancestry'],target['level_name'])
            for value in updated.values():require(expected['label'].casefold() not in value.casefold())
            (directory/'prompts.json').write_text(json.dumps(updated,indent=2));(directory/'prompts.json').chmod(0o600)
            state.update(ready=True,page_uuid=page['identity']['page_uuid'])
            (directory/'fixture.json').write_text(json.dumps(state));(directory/'fixture.json').chmod(0o600)
            report=public_report(directory);report.update(prepared=True,calls=budget.calls,public_urls_issued=0)
            return report
    except BaseException:
        # Recovery scans this exact marker even if a receipt was not returned.
        await cleanup(client,directory,data_root,journal_fixture)
        raise


async def cleanup(client,directory,data_root,journal_fixture):
    """Delete only this bundle's marked journal/files; keep private prompts/answers."""
    directory=Path(directory);_,state=load_bundle(directory);marker=state['marker']
    async with asyncio.timeout(30):
        response=await client.call_tool('execute_javascript',dict(code=journal_fixture.code(journal_fixture.CLEANUP,marker)),raise_on_error=False)
        require(not response.is_error)
        result=json.loads(response.structured_content['value'])
        require(result==dict(journals_remaining=0,folders_remaining=0))
    asset=AssetFixture(data_root,marker)
    if asset.path.exists():
        require(not asset.path.is_symlink() and (asset.path/'.preview-owner').read_text()==marker)
        asset.created=True;asset.cleanup()
    state.update(ready=False);state.pop('page_uuid',None)
    (directory/'fixture.json').write_text(json.dumps(state));(directory/'fixture.json').chmod(0o600)
    (directory/'prompts.json').write_text(json.dumps(prompts(),indent=2));(directory/'prompts.json').chmod(0o600)
    return dict(cleanup_complete=True,game_fixtures_remaining=0,private_handoff_bundle_retained=True,calls=1)
