"""Opt-in PF2e-specific character ability-reference fixture in existing test world.

One marked character and three inert owned Items only. Public Actor.create,
createEmbeddedDocuments/delete/getFlag/toObject: https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
PF2e8.6.1 ability/feat schemas: https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
No existing document updates, imports, casting, rolls or preparation calls.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180
DESCRIPTION = '<p>Ability 😀 source text.</p>' * 60
GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS = """
const encoded=JSON.stringify(result);if(new TextEncoder().encode(encoded).length>16000)throw Error('Metadata bound');
return Array.from({length:Math.ceil(encoded.length/800)},(_,i)=>encoded.slice(i*800,(i+1)*800));
"""
CREATE_CHARACTER = """
globalThis.__mcpCharacterAbilityProbes??=new Map();const state=globalThis.__mcpCharacterAbilityProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpCharacterAbilityProbes.set(RUN,state);
if(state.closed)throw Error('Probe closed');state.pending++;let actor,result;
const open=async()=>{if(!actor||actor.type!=='character'||typeof actor.uuid!=='string'||actor.getFlag('foundry-mcp','characterAbilityProbe')!==RUN)throw Error('Fixture identity mismatch');if(state.closed){GUARD;await actor.delete();throw Error('Probe closed during creation');}};
try{actor=await Actor.implementation.create({name:'MCP temporary character abilities verification',type:'character',flags:{'foundry-mcp':{characterAbilityProbe:RUN}}});await open();
const description='<p>Ability 😀 source text.</p>'.repeat(60);
const action={name:'Same ability',type:'action',system:{actionType:{value:'passive'},actions:{value:null},traits:{value:[],otherTags:[]},description:{value:description},rules:[]}};
const feat=category=>({name:'Same ability',type:'feat',system:{category,level:{value:1,taken:1},actionType:{value:'passive'},actions:{value:null},traits:{value:[],otherTags:[]},description:{value:description},rules:[]}});
GUARD;const items=await actor.createEmbeddedDocuments('Item',[action,feat('general'),feat('classfeature')]);await open();
if(items.length!==3||actor.items.size!==3)throw Error('Unexpected fixture membership');
const metadata=[];for(const item of items){const source=item.toObject(true),text=source.system.description.value;if(typeof text!=='string')throw Error('Description source unavailable');const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),b=>b.toString(16).padStart(2,'0')).join('');metadata.push({uuid:item.uuid,type:item.type,name:source.name,...(item.type==='feat'?{category:source.system.category}:{}),description_sha256:digest,description_utf16_length:text.length,authored_input_unchanged:text===description});}
result={uuid:actor.uuid,items:metadata};
}finally{state.pending--;}
"""
CLEANUP_CHARACTER = """
globalThis.__mcpCharacterAbilityProbes??=new Map();const state=globalThis.__mcpCharacterAbilityProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpCharacterAbilityProbes.set(RUN,state);state.closed=true;
for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
const matches=game.actors.filter(a=>a.getFlag('foundry-mcp','characterAbilityProbe')===RUN);
if(matches.length>1||matches.some(a=>a.type!=='character'))throw Error('Ambiguous fixture marker');
for(const actor of matches){if((EXPECTED!==null&&actor.uuid!==EXPECTED)||actor.getFlag('foundry-mcp','characterAbilityProbe')!==RUN)throw Error('Cleanup identity mismatch');GUARD;await actor.delete();}
const result={pending:state.pending,remaining:game.actors.filter(a=>a.getFlag('foundry-mcp','characterAbilityProbe')===RUN).length};
"""


SOURCE_WITNESS_CHECK = """
const checks=[],failed_paths=[];let schema_undefined_absences=0;
const at=(source,path)=>{let value=source;for(const encoded of path.slice(1).split('/')){const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~');if(!value||typeof value!=='object'||!Object.hasOwn(value,key))return {present:false};value=value[key];}return {present:true,value};};
for(const claim of claims){const item=[...actor.items.values()].find(i=>i.uuid===claim.document_uuid);if(!item)throw Error('Wrong contributor');const detached=item.toObject(true),original=at(detached,claim.path),selected=at(JSON.parse(JSON.stringify(detached)),claim.path);
if(original.present&&original.value===undefined&&!claim.present)schema_undefined_absences++;
const ok=claim.basis==='source'&&claim.present===selected.present&&(!selected.present||JSON.stringify(claim.value)===JSON.stringify(selected.value));checks.push(ok);if(!ok)failed_paths.push(claim.path);}
const result={checks,schema_undefined_absences,failed_paths:[...new Set(failed_paths)]};
"""


def fixture_code(template, run_id, expected_uuid=None):
    """PF2e-specific exact-marker test fixture operations with bounded output."""
    if not isinstance(run_id, str) or re.fullmatch(r'[A-Za-z0-9-]{1,80}', run_id) is None:
        raise ValueError('Safe per-run marker required')
    return GUARD + template.replace('RUN', json.dumps(run_id)).replace('EXPECTED', json.dumps(expected_uuid)).replace('GUARD', GUARD) + CHUNKS


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


async def verify(client, world_id, run_id, summary=None):
    """PF2e-specific paged actual-reader proof, independent source and cleanup."""
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    summary = summary if summary is not None else {}
    summary.update(passed=False, cleanup_verified=False)
    expected_uuid, requested, completed, stage = None, 0, 0, 'discovery'

    async def call(name, arguments):
        nonlocal requested, completed
        requested += 1
        response = await client.call_tool(name, arguments)
        completed += 1
        return payload(response)

    async def execute(code):
        value = (await call('execute_javascript', {'code': code}))['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    async def js(body):
        return await execute(GUARD + body + CHUNKS)

    async def pages(tool, selector, sections):
        rows, cursor, seen, revision, count = [], None, set(), None, 0
        for _ in range(200):
            args = dict(selector, sections=sections, limit=7, max_bytes=8000)
            if cursor:
                args['cursor'] = cursor
            page = await call(tool, args)
            assert page['identity']['uuid'] == next(iter(selector.values()))
            assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 8000
            assert page['runtime'] == dict(core_version='14.369', system_id='pf2e', system_version='8.6.1')
            revision = revision or page['revision']
            assert page['revision'] == revision
            rows.extend(page['records']); count += 1
            cursor = page['pagination']['next_cursor']
            if cursor is None:
                return rows, page, count
            assert cursor not in seen
            seen.add(cursor)
        raise AssertionError('Fixture page bound')

    try:
        requested += 1
        tools = {tool.name: tool for tool in await client.list_tools()}
        completed += 1
        assert tools['read_actor'].annotations.readOnlyHint
        for phrase in ('character_ability_item', 'other_abilities_not_enumerated', 'ability_items_denied'):
            assert phrase in tools['read_actor'].description
        stage = 'fixture_creation'
        fixture = await execute(fixture_code(CREATE_CHARACTER, run_id))
        expected_uuid = fixture['uuid']
        summary['description_setup_normalized'] = any(item['authored_input_unchanged'] is False for item in fixture['items'])
        guard = 'const uuid=' + json.dumps(expected_uuid) + ';' + """
const actor=[...game.actors.values()].find(a=>a.uuid===uuid);
if(!actor||actor.type!=='character'||actor.getFlag('foundry-mcp','characterAbilityProbe')!==RUN)throw Error('Fixture identity mismatch');
""".replace('RUN', json.dumps(run_id))
        fingerprint = guard + """
const result=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify([actor.toObject(true),...Array.from(actor.items.values(),i=>i.toObject(true))])))),b=>b.toString(16).padStart(2,'0')).join('');
"""
        stage = 'source_fingerprint_before'
        before = await js(fingerprint)
        stage = 'ability_references'
        rows, page, actor_pages = await pages('read_actor', {'actor_uuid': expected_uuid}, ['abilities'])
        assert len(rows) == 3 and {row['mapped']['value']['target_uuid'] for row in rows} == {item['uuid'] for item in fixture['items']}
        assert page['sections'][0]['status'] == 'partial' and 'other_abilities_not_enumerated' in page['sections'][0]['reasons']
        for row in rows:
            origin = next(item for item in fixture['items'] if item['uuid'] == row['mapped']['value']['target_uuid'])
            assert row['key'] == 'abilities:item:' + origin['uuid'] and row['kind'] == 'relationship'
            assert row['mapped'] == dict(concept='character_ability_item', value=dict(status='resolved', target_uuid=origin['uuid'], type=origin['type'], name=origin['name'], name_truncated=False), unit=None)
            assert row['raw'] == [dict(document_uuid=origin['uuid'], path='/' + key, present=True, value=value, basis='source') for key, value in [('name', origin['name']), ('type', origin['type'])]]
            assert row['provenance'] == dict(mapping='pf2e.character.ability-reference.v1', contributors=[{key: raw[key] for key in ('document_uuid', 'path', 'basis')} for raw in row['raw']], limitations=['owned_item_reference_not_complete_or_active_ability'])
        item_pages = 0
        for item in fixture['items']:
            stage = 'item_followup'
            records, page, count = await pages('read_item', {'item_uuid': item['uuid']}, ['source', 'description'])
            item_pages += count
            stage = 'item_followup_owner'
            assert page['identity']['actor']['uuid'] == expected_uuid
            stage = 'item_source_description_completeness'
            assert all(section['status'] == 'complete' for section in page['sections'])
            fragments = [row for row in records if row['kind'] == 'text' and row['text']['path'] == '/system/description/value']
            stage = 'item_description_reconstruction'
            text = ''.join(row['raw'][0]['value'] for row in fragments)
            assert hashlib.sha256(text.encode()).hexdigest() == item['description_sha256']
            assert len(text.encode('utf-16-le')) // 2 == item['description_utf16_length']
            stage = 'item_description_fragment_offsets'
            assert fragments
            assert fragments[0]['text']['start'] == 0 and fragments[-1]['text']['complete']
            assert all(a['text']['end'] == b['text']['start'] for a, b in zip(fragments, fragments[1:]))
            assert all(row['text']['total'] == item['description_utf16_length'] for row in fragments)
            assert fragments[-1]['text']['end'] == item['description_utf16_length']
            witnesses = [raw for row in records if row['kind'] != 'text' for raw in row['raw']]
            if item['type'] == 'feat':
                stage = 'item_feat_category'
                assert any(raw['path'] == '/system/category' and raw['present'] and raw['value'] == item['category'] for raw in witnesses)
            stage = 'item_independent_source_witnesses'
            for offset in range(0, len(witnesses), 20):
                batch = witnesses[offset:offset + 20]
                checked = await js(guard + 'const claims=' + json.dumps(batch) + ';' + SOURCE_WITNESS_CHECK)
                summary['schema_undefined_absences'] = summary.get('schema_undefined_absences', 0) + checked['schema_undefined_absences']
                summary['source_checks_passed'] = summary.get('source_checks_passed', 0) + sum(value is True for value in checked['checks'])
                if checked['failed_paths']:
                    summary['failed_source_paths'] = checked['failed_paths']
                assert len(checked['checks']) == len(batch) and all(value is True for value in checked['checks'])
        stage = 'source_fingerprint_after'
        assert await js(fingerprint) == before
        summary.update(passed=True, ability_items=3, actor_pages=actor_pages, item_pages=item_pages, fingerprint_unchanged=True,
                       description_verified=True, active_benefits_evaluated=False, complete_abilities=False)
    except Exception as error:
        summary.update(passed=False, failure_stage=stage, exception_type=type(error).__name__)
    finally:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                removed = await asyncio.shield(execute(fixture_code(CLEANUP_CHARACTER, run_id, expected_uuid)))
            assert removed['pending'] == 0 and removed['remaining'] == 0
            summary['cleanup_verified'] = True
        except Exception as error:
            summary.update(passed=False, cleanup_exception_type=type(error).__name__)
        summary.update(mcp_calls=completed, requested_calls=requested, completed_calls=completed)
    return summary


async def main(world_id):
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    summary = dict(passed=False, cleanup_verified=False)
    try:
        token = next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1] / '.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise RuntimeError('Missing local caller credential')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
        async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                await verify(client, world_id, uuid4().hex, summary)
    except Exception as error:
        summary.update(passed=False, exception_type=type(error).__name__)
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id', required=True, choices=['test'])
    raise SystemExit(asyncio.run(main(parser.parse_args().world_id)))
