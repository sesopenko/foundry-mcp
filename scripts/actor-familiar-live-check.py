"""PF2e-specific familiar source/current check in the existing development world.

Creates one run-marked character, one familiar and two inert owned actions;
finally deletes only exact marked UUIDs, familiar before character. Requires
--world-id and the existing localhost:30000 GM browser, F14.369/PF2e8.6.1.
Public fixture APIs: Actor.implementation.create, createEmbeddedDocuments,
Document.update/delete/getFlag/toObject and game.actors collections:
https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
Current values use declared own public Actor.system data after master admission:
https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorData.html#system
PF2e-specific source contracts (never preparation or master getter):
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts
Familiar master.id is a nullable world-character ID. Actions use category
familiar, empty traits and rules; scope is prose, never inferred classification.
Current witnesses read declared FamiliarSystemData through public Actor.system
own data descriptors after checking the recorded master; serialization omission
does not stand in for unavailable current statistics.
"""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180

# Browser-owned probe coordination, never Foundry internals or persisted state.
RUN_STATE = """
globalThis.__mcpFamiliarProbes??=new Map();
const runState=globalThis.__mcpFamiliarProbes.get(RUN)??{closed:false,pending:0};
globalThis.__mcpFamiliarProbes.set(RUN,runState);
"""

CURRENT_WITNESS = """
if(paths.length>1000)throw Error('Verification path bound exceeded');
const recorded=actor.toObject(true).system.master;
if(recorded?.id!==master.id||recorded.ability!=='cha')throw Error('Current master mismatch');
const fields=[];
for(const path of paths){
 let value=actor,present=true;
 for(const encoded of path.slice(1).split('/')){
  const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~');
  if(value===null||typeof value!=='object'){present=false;break;}
  const descriptor=Object.getOwnPropertyDescriptor(value,key);
  if(!descriptor||!Object.hasOwn(descriptor,'value')||descriptor.value===undefined){present=false;break;}
  value=descriptor.value;
 }
 fields.push({path,present,...(present?{value}:{})});
}
const report=JSON.stringify({fields});
"""


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


def probe(value):
    if isinstance(value, dict) and 'value' in value:
        value = value['value']
    if isinstance(value, dict) and value.get('$type') == 'Array':
        assert value.get('truncated') is False
        value = ''.join(value['values'])
    assert isinstance(value, str), 'Unexpected bounded development response.'
    return json.loads(value)


def require_representative_current(fields):
    """PF2e-specific 8.6.1 familiar AC/save/ordinary skill/land speed coverage.

    Derived own-data witnesses must include real finite values; matching absent
    serialized fields does not prove master-derived familiar functionality.
    """
    def finite(field):
        return field['present'] and type(field.get('value')) in (int, float) and float('-inf') < field['value'] < float('inf')
    for required in ('/system/attributes/ac/value', '/system/movement/speeds/land/value'):
        assert any(field['path'] == required and finite(field) for field in fields)
    for prefix in ('/system/saves/', '/system/skills/'):
        assert any(field['path'].startswith(prefix) and field['path'].endswith(('/value', '/totalModifier')) and finite(field) for field in fields)


def verify_unassociated_statistics(rows, page, source_master):
    """PF2e-specific 8.6.1 nullable-master source witnesses, no derived rows.

    Public update can normalize the master's ability to null. Compare actual
    post-update source rather than assuming its prior selected attribute.
    """
    assert source_master['id'] is None
    assert len(rows) == 1
    master = rows[0]
    assert master['key'] == 'statistics:familiar_master'
    assert master['section'] == 'statistics' and master['kind'] == 'relationship'
    assert master['provenance']['mapping'] == 'pf2e.familiar.master.v1'
    assert master['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')} for raw in master['raw']]
    assert master['mapped']['value'] == {'status': 'unassociated', 'target_uuid': None}
    assert [raw['path'] for raw in master['raw']] == ['/system/master/id', '/system/master/ability']
    assert all(raw['basis'] == 'source' for raw in master['raw'])
    assert all(raw['document_uuid'] == page['identity']['uuid'] and raw['present'] is True for raw in master['raw'])
    assert master['raw'][0]['value'] is None
    assert type(master['raw'][1]['value']) is type(source_master['ability'])
    assert master['raw'][1]['value'] == source_master['ability']
    assert page['sections'][0]['status'] == 'partial'
    assert 'familiar_master_unassociated' in page['sections'][0]['reasons']
    assert not any(raw['basis'] == 'transformed' for row in rows for raw in row['raw'])


async def _run(world_id, check_statistics, summary):
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    root = Path(__file__).resolve().parent.parent
    token = next(line.partition('=')[2].strip() for line in (root / '.env.mcp').read_text().splitlines() if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    marker = json.dumps(str(uuid4()))
    master_uuid, familiar_uuid = None, None
    summary.update(passed=False, cleanup_confirmed=False, statistics_checked=False,
                   mcp_calls=0, current_present=0, current_missing=0)
    stage = 'discovery'
    guard = """
if(!game.ready||!game.user.isGM||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Unsupported development runtime');
if(location.origin!=='http://localhost:30000'||game.world.id!==WORLD)throw Error('Wrong development world');
""".replace('WORLD', json.dumps(world_id))
    async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
        async def js(code):
            summary['mcp_calls'] += 1
            code += "\nreturn Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));"
            return probe(payload(await client.call_tool('execute_javascript', {'code': code})))

        async def pages(tool, selector, sections=None):
            rows, cursor, count = [], None, 0
            while True:
                assert count < 100, 'Verification page bound exceeded.'
                arguments = {**selector, 'limit': 2, 'max_bytes': 8000}
                if sections is not None:
                    arguments['sections'] = sections
                if cursor:
                    arguments['cursor'] = cursor
                page = payload(await client.call_tool(tool, arguments))
                summary['mcp_calls'] += 1
                assert page['identity']['uuid'] == next(iter(selector.values()))
                rows.extend(page['records'])
                cursor = page['pagination']['next_cursor']
                if count and page['revision'] != revision:
                    raise AssertionError('Verification revision changed')
                revision = page['revision']
                count += 1
                if not cursor:
                    return rows, page, count

        try:
            tools = {tool.name: tool for tool in await client.list_tools()}
            summary['mcp_calls'] += 1
            assert {'read_actor', 'read_item', 'execute_javascript', 'get_actor_types'} <= tools.keys()
            assert tools['read_actor'].annotations.readOnlyHint
            assert 'familiar' in tools['read_actor'].description.lower()
            registry = payload(await client.call_tool('get_actor_types', {}))
            summary['mcp_calls'] += 1
            support = next(actor for actor in registry['actor_types'] if actor['type'] == 'familiar')
            assert support['source_supported'] and support['mapped_supported'] and support['effective_supported']
            limitations = ' '.join(support['limitations']).lower()
            assert 'full integrated views remain unsupported' in limitations
            stage = 'master_creation'
            created = await js(guard + RUN_STATE.replace('RUN', marker) + """
if(runState.closed)throw Error('Probe closed');runState.pending++;let actor;
try{actor=await Actor.implementation.create({name:'MCP temporary familiar master',type:'character',flags:{'foundry-mcp':{familiarVerificationRun:RUN}}});
if(!actor||actor.type!=='character'||typeof actor.uuid!=='string'||actor.getFlag('foundry-mcp','familiarVerificationRun')!==RUN)throw Error('Fixture marker mismatch');
if(runState.closed){GUARD;await actor.delete();throw Error('Probe closed during creation');}}finally{runState.pending--;}
const report=JSON.stringify({uuid:actor.uuid});
""".replace('RUN', marker).replace('GUARD', guard))
            master_uuid = created['uuid']
            stage = 'familiar_creation'
            created = await js(guard + RUN_STATE.replace('RUN', marker) + """
const master=game.actors.find(a=>a.uuid===MASTER);
if(!master||master.type!=='character'||master.getFlag('foundry-mcp','familiarVerificationRun')!==RUN)throw Error('Master identity mismatch');
if(runState.closed)throw Error('Probe closed');runState.pending++;let actor;
try{actor=await Actor.implementation.create({name:'MCP temporary familiar verification',type:'familiar',system:{master:{id:master.id,ability:'cha'},attributes:{hp:{value:5,temp:2}},details:{creature:{value:'<p>Familiar source verification creature.</p>'}}},flags:{'foundry-mcp':{familiarVerificationRun:RUN}}});
if(!actor||actor.type!=='familiar'||typeof actor.uuid!=='string'||actor.getFlag('foundry-mcp','familiarVerificationRun')!==RUN)throw Error('Fixture marker mismatch');
if(runState.closed){GUARD;await actor.delete();throw Error('Probe closed during creation');}}finally{runState.pending--;}
const report=JSON.stringify({uuid:actor.uuid});
""".replace('MASTER', json.dumps(master_uuid)).replace('RUN', marker).replace('GUARD', guard))
            familiar_uuid = created['uuid']
            owned_guard = guard + """
const actor=game.actors.find(a=>a.uuid===FAMILIAR),master=game.actors.find(a=>a.uuid===MASTER);
if(!actor||actor.type!=='familiar'||actor.getFlag('foundry-mcp','familiarVerificationRun')!==RUN||!master||master.type!=='character'||master.getFlag('foundry-mcp','familiarVerificationRun')!==RUN)throw Error('Fixture identity mismatch');
""".replace('FAMILIAR', json.dumps(familiar_uuid)).replace('MASTER', json.dumps(master_uuid)).replace('RUN', marker)
            stage = 'owned_action_setup'
            setup = await js(owned_guard + RUN_STATE.replace('RUN', marker) + """
if(runState.closed)throw Error('Probe closed');runState.pending++;let items;
const inputs=[{name:'Familiar scope note',text:'<p>This inert verification ability describes a benefit for the familiar.</p>'},{name:'Master scope note',text:'<p>This inert verification ability describes a benefit for the master.</p>'}];
try{items=await actor.createEmbeddedDocuments('Item',inputs.map(({name,text})=>({name,type:'action',system:{category:'familiar',actionType:{value:'passive'},actions:{value:null},traits:{value:[]},rules:[],description:{value:text}}})));}finally{runState.pending--;}
if(runState.closed)throw Error('Probe closed during action creation');
if(items.length!==2||actor.items.size!==2)throw Error('Unexpected fixture membership');
const report=JSON.stringify({items:items.map((item,index)=>({uuid:item.uuid,text:inputs[index].text})),master_id:master.id});
""")
            fingerprint = owned_guard + """
const data=JSON.stringify([actor.toObject(true),master.toObject(true)]);
const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(data))),v=>v.toString(16).padStart(2,'0')).join('');
const report=JSON.stringify({hash,count:actor.items.size});
"""
            before = await js(fingerprint)
            stage = 'familiar_pagination'
            rows, page, count = await pages('read_actor', {'actor_uuid': familiar_uuid}, ['identity', 'source', 'description', 'abilities'])
            assert count > 1 and len({row['key'] for row in rows}) == len(rows)
            relationship = next(row for row in rows if row['key'] == 'identity:familiar_master')
            value = relationship['mapped']['value']
            assert value['status'] == 'resolved' and value['target_uuid'] == master_uuid
            assert value['next_call'] == {'tool': 'read_actor', 'arguments': {'actor_uuid': master_uuid}}
            assert 'token_uuid' not in value
            master_page = payload(await client.call_tool(value['next_call']['tool'], {**value['next_call']['arguments'], 'sections': ['identity']}))
            summary['mcp_calls'] += 1
            assert master_page['identity']['uuid'] == master_uuid and master_page['identity']['type'] == 'character'
            assert relationship['raw'] == [{'document_uuid': familiar_uuid, 'path': '/system/master/id', 'present': True, 'value': setup['master_id'], 'basis': 'source'}]
            expected = {'/system/master/id': setup['master_id'], '/system/master/ability': 'cha', '/system/attributes/hp/value': 5, '/system/attributes/hp/temp': 2, '/system/details/creature/value': '<p>Familiar source verification creature.</p>'}
            for path, expected_value in expected.items():
                assert any(raw['path'] == path and raw.get('value') == expected_value and raw['document_uuid'] == familiar_uuid and raw['basis'] == 'source' for row in rows for raw in row['raw'])
            abilities = [row for row in rows if row['mapped']['concept'] == 'familiar_ability']
            assert len(abilities) == 2 and {row['mapped']['value']['target_uuid'] for row in abilities} == {item['uuid'] for item in setup['items']}
            for row in abilities:
                assert row['mapped']['value']['ability_kind'] == 'unclassified'
                assert row['raw'][-1]['path'] == '/system/traits/value' and row['raw'][-1]['value'] == []
                assert 'ability_scope_requires_description' in row['provenance']['limitations']
            assert 'other_abilities_pending' in next(section for section in page['sections'] if section['name'] == 'abilities')['reasons']
            stage = 'item_prose'
            item_pages = 0
            for item in setup['items']:
                item_rows, _, used = await pages('read_item', {'item_uuid': item['uuid']}, ['source', 'description'])
                item_pages += used
                text = ''.join(raw.get('value', '') for row in item_rows for raw in row['raw'] if raw['path'] == '/system/description/value')
                assert text == item['text']
            stage = 'default_privacy'
            defaults, _, _ = await pages('read_actor', {'actor_uuid': familiar_uuid})
            assert not any(row['section'] == 'description' for row in defaults)
            assert not any(raw['basis'] == 'transformed' for row in defaults for raw in row['raw'])
            assert not any(raw['basis'] == 'transformed' for row in rows for raw in row['raw'])
            assert 'Familiar source verification creature.' not in json.dumps(defaults)
            if check_statistics:
                stage = 'statistics_pagination'
                statistics, statistics_page, statistics_pages = await pages('read_actor', {'actor_uuid': familiar_uuid}, ['statistics'])
                assert len({row['key'] for row in statistics}) == len(statistics)
                assert statistics_page['sections'][0]['status'] == 'partial'
                assert 'other_statistics_pending' in statistics_page['sections'][0]['reasons']
                master_rows = [row for row in statistics if row['key'] == 'statistics:familiar_master']
                assert len(master_rows) == 1
                current_master = master_rows[0]
                assert current_master['mapped']['value'] == value
                assert current_master['provenance']['mapping'] == 'pf2e.familiar.master.v1'
                assert current_master['raw'] == [
                    {'document_uuid': familiar_uuid, 'path': '/system/master/id', 'present': True, 'value': setup['master_id'], 'basis': 'source'},
                    {'document_uuid': familiar_uuid, 'path': '/system/master/ability', 'present': True, 'value': 'cha', 'basis': 'source'},
                ]
                assert current_master['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')} for raw in current_master['raw']]
                current_rows = [row for row in statistics if row['provenance']['mapping'] == 'pf2e.familiar.current.v1']
                assert 0 < len(current_rows) <= 1000
                assert len(current_rows) + 1 == len(statistics)
                expected = []
                for row in current_rows:
                    assert row['section'] == 'statistics' and row['kind'] == 'field' and len(row['raw']) == 1
                    raw = row['raw'][0]
                    assert raw['document_uuid'] == familiar_uuid and raw['basis'] == 'transformed'
                    assert row['key'] == 'statistics:' + raw['path']
                    assert row['provenance']['limitations'] == ['familiar_value_not_recalculated']
                    assert row['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')}]
                    expected.append({key: raw[key] for key in ('path', 'present', 'value') if key in raw})
                stage = 'statistics_independent_model'
                actual = await js(owned_guard + 'const paths=' + json.dumps([row['path'] for row in expected]) + ';' + CURRENT_WITNESS)
                assert actual['fields'] == expected
                require_representative_current(expected)
                summary.update(statistics_checked=True, statistics_pages=statistics_pages, statistics_records=len(statistics), current_statistics_records=len(current_rows), current_present=sum(row['raw'][0]['present'] for row in current_rows), current_missing=sum(not row['raw'][0]['present'] for row in current_rows))
            assert await js(fingerprint) == before
            stage = 'nullable_master_setup'
            post_update = await js(owned_guard + """
await actor.update({'system.master.id':null});
const sourceMaster=actor.toObject(true).system.master;
const report=JSON.stringify({updated:sourceMaster.id===null,source_master:{id:sourceMaster.id,ability:sourceMaster.ability}});
""")
            assert post_update['updated'] is True
            null_before = await js(fingerprint)
            null_rows, null_page, _ = await pages('read_actor', {'actor_uuid': familiar_uuid}, ['identity', 'source'])
            null_link = next(row for row in null_rows if row['key'] == 'identity:familiar_master')
            assert null_link['mapped']['value'] == {'status': 'unassociated', 'target_uuid': None}
            assert 'familiar_master_unassociated' in next(section for section in null_page['sections'] if section['name'] == 'identity')['reasons']
            if check_statistics:
                stage = 'statistics_unassociated_master'
                null_statistics, null_statistics_page, null_statistics_pages = await pages('read_actor', {'actor_uuid': familiar_uuid}, ['statistics'])
                verify_unassociated_statistics(null_statistics, null_statistics_page, post_update['source_master'])
                summary['unassociated_statistics_pages'] = null_statistics_pages
            assert await js(fingerprint) == null_before
            summary.update(passed=True, actor_pages=count, actor_records=len(rows), item_pages=item_pages, owned_items=2, fingerprint_unchanged=True, nullable_master_verified=True)
        except Exception as error:
            summary.update(failure_stage=stage, exception_type=type(error).__name__)
        except asyncio.CancelledError:
            summary.update(failure_stage=stage, exception_type='CancelledError')
            raise
        finally:
            for attempt in range(3):
                try:
                    async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                        cleaned = await asyncio.shield(js(guard + RUN_STATE.replace('RUN', marker) + """
runState.closed=true;
for(let n=0;runState.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
const matches=game.actors.filter(a=>a.getFlag('foundry-mcp','familiarVerificationRun')===RUN);
if(matches.length>2||matches.some(a=>!['character','familiar'].includes(a.type)))throw Error('Ambiguous verification marker');
const expected={familiar:FAMILIAR,character:MASTER};
for(const type of ['familiar','character']){
 const selected=matches.filter(a=>a.type===type);if(selected.length>1)throw Error('Ambiguous fixture type');
 if(selected.length){const actor=selected[0];if((expected[type]&&actor.uuid!==expected[type])||actor.getFlag('foundry-mcp','familiarVerificationRun')!==RUN)throw Error('Cleanup identity mismatch');GUARD;await actor.delete();}
}
const report=JSON.stringify({pending:runState.pending,clean:!game.actors.some(a=>a.getFlag('foundry-mcp','familiarVerificationRun')===RUN)});
""".replace('RUN', marker).replace('FAMILIAR', json.dumps(familiar_uuid)).replace('MASTER', json.dumps(master_uuid)).replace('GUARD', guard)))
                    if cleaned['clean'] and cleaned['pending'] == 0:
                        summary['cleanup_confirmed'] = True
                        break
                except Exception as error:
                    summary['cleanup_exception_type'] = type(error).__name__
                if attempt < 2:
                    await asyncio.sleep(1)
            summary['passed'] = summary['passed'] and summary['cleanup_confirmed']
    return summary


async def main(world_id, check_statistics=False):
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    summary = dict(passed=False, cleanup_confirmed=False, statistics_checked=False)
    try:
        async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
            await _run(world_id, check_statistics, summary)
    except Exception as error:
        summary.update(passed=False, exception_type=type(error).__name__)
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id', required=True, choices=['test'], help='Exact existing development world ID; required before fixture writes.')
    parser.add_argument('--statistics', action='store_true', help='Verify permission-checked current fields using the same marked pair, plus suppression after master unassignment.')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.world_id, args.statistics)))
