"""PF2e-specific Build integration check in the existing development world.

Creates exactly one marked temporary character and seven inert owned Items, then
removes only that run's Actor in finally. Requires the visible development GM
tab and an explicit --world-id; never provisions a world or Foundry instance.
Tested contract: Foundry 14.369 / PF2e 8.6.1 persisted source, not effective
benefits. Official public document APIs used by the fixture:
https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
PF2e schema: https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module/item
Fixture inputs were checked against that exact local research revision:
ancestry/heritage/class/feat data.ts models, background/deity data.ts contracts,
and static/template.json background/Lore/deity defaults. Numeric boost key 0,
nullable selected/ancestry, trainedSkills arrays, class additional count, feat
category/taken level, Lore proficient.value and deity spell UUID map are source
fields. Omitted fields are hydrated by the installed system's document defaults.
"""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


def probe(value):
    if isinstance(value, dict) and 'value' in value:
        value = value['value']
    if isinstance(value, dict) and value.get('$type') == 'Array':
        assert value.get('truncated') is False
        assert all(isinstance(part, str) for part in value.get('values', []))
        value = ''.join(value['values'])
    assert isinstance(value, str), 'Unexpected bounded development response.'
    return json.loads(value)


async def verify_discovery(client):
    """Inspect actual MCP schemas/descriptions and source support, read only."""
    available = {tool.name: tool for tool in await client.list_tools()}
    assert {'execute_javascript', 'read_actor', 'read_item', 'get_actor_types'} <= available.keys()
    actor_tool = available['read_actor']
    properties = actor_tool.inputSchema['properties']
    assert {'actor_uuid', 'token_uuid', 'sections', 'limit', 'max_bytes', 'cursor'} <= properties.keys()
    assert 'build' in properties['sections']['items']['enum']
    for contract in ('build_item', 'build_grant_claim', 'build_granted_by_claim', 'owner-local IDs', 'Reciprocity agree/disagree/absent', 'incoming and unresolved claims remain not_evaluated', 'future feature definitions do not imply acquisition', 'NPC/familiar Build is unsupported', '12000 owned Items', '24000 selected records'):
        assert contract in actor_tool.description
    assert actor_tool.annotations.readOnlyHint
    registry = payload(await client.call_tool('get_actor_types', {}))
    build = next(section for section in registry['actor_sections'] if section['name'] == 'build')
    assert build['source_supported'] and build['mapped_supported'] and not build['effective_supported']
    character = next(actor for actor in registry['actor_types'] if actor['type'] == 'character')
    assert character['source_supported'] and character['mapped_supported'] and character['effective_supported']
    for contract in ('Null abilities remain', 'one root marker, never six zero modifiers', 'Character source excludes derived HP maximum and focus maximum/capacity', 'Default source excludes biography prose', 'empty arrays stay field markers'):
        assert contract in actor_tool.description


async def main(world_id, discovery_only=False, check_statistics=False):
    root = Path(__file__).resolve().parent.parent
    credentials = {}
    for line in (root / '.env.mcp').read_text().splitlines():
        key, sep, value = line.partition('=')
        if sep and key.strip() == 'FOUNDRY_MCP_CALLER_TOKEN':
            credentials[key.strip()] = value.strip()
    transport = StreamableHttpTransport(
        'http://127.0.0.1:8000/mcp/mcp',
        headers={'Authorization': 'Bearer ' + credentials['FOUNDRY_MCP_CALLER_TOKEN']},
    )
    run_id, actor_uuid = str(uuid4()), None
    summary = {'passed': False, 'cleanup_confirmed': False}
    stage = 'client_discovery'
    container_shapes = None
    async with Client(transport) as client:
        if discovery_only:
            result = {'passed': False, 'discovery_verified': False}
            try:
                await verify_discovery(client)
                result.update(passed=True, discovery_verified=True)
            except Exception as error:
                result.update(failure_stage='client_discovery', exception_type=type(error).__name__)
            print(json.dumps(result))
            return 0 if result['passed'] else 1

        async def js(code):
            wrapped = code + "\nreturn Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));"
            return probe(payload(await client.call_tool('execute_javascript', {'code': wrapped})))

        # Every mutating request repeats the same fixed runtime/world guard.
        guard = """
if(!game.ready||!game.user.isGM||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Unsupported development runtime');
if(location.origin!=='http://localhost:30000'||game.world.id!==WORLD)throw Error('Wrong development world');
""".replace('WORLD', json.dumps(world_id))
        marker = json.dumps(run_id)
        try:
            await verify_discovery(client)
            summary['discovery_verified'] = True
            # Select definitions through existing pack indexes; never hydrate or import.
            stage = 'definition_indexes'
            selected = await js(guard + """
const featPack=game.packs.get('pf2e.feats-srd'),spellPack=game.packs.get('pf2e.spells-srd');
if(!featPack||!spellPack)throw Error('Expected existing PF2e packs');
const featIndex=await featPack.getIndex(),spellIndex=await spellPack.getIndex();
const future=featIndex.find(row=>row.name==='Battle Medicine'),spell=spellIndex.find(row=>row.name==='Heal');
if(!future||!spell)throw Error('Required definition index rows unavailable');
const report=JSON.stringify({future:future.uuid,spell:spell.uuid});
""")
            assert selected['future'].startswith('Compendium.') and selected['spell'].startswith('Compendium.')
            # Create first and retain identity before any embedded fixture writes.
            stage = 'actor_creation'
            created = await js(guard + """
const actor=await Actor.implementation.create({name:'MCP temporary Build verification',type:'character',system:{abilities:null,details:{level:{value:1},age:{value:'Adult'},biography:{appearance:'<p>Character source verification.</p>',edicts:['Keep the record.'],anathema:[]},languages:{value:['common'],details:'Authored language note.'}},skills:{nature:{rank:1}},resources:{heroPoints:{value:1,max:3},focus:{value:0}},build:{attributes:{manual:false,boosts:{1:[]},apex:null}}},flags:{'foundry-mcp':{buildVerificationRun:RUN}}});
if(!actor||actor.getFlag('foundry-mcp','buildVerificationRun')!==RUN)throw Error('Fixture marker mismatch');
const report=JSON.stringify({uuid:actor.uuid});
""".replace('RUN', marker))
            actor_uuid = created['uuid']
            selector = json.dumps(actor_uuid)
            owned_guard = guard + """
const actor=game.actors.find(a=>a.uuid===UUID);
if(!actor||actor.getFlag('foundry-mcp','buildVerificationRun')!==RUN)throw Error('Fixture identity mismatch');
""".replace('UUID', selector).replace('RUN', marker)
            stage = 'owned_item_setup'
            setup = await js(owned_guard + """
const inputs=[
 {name:'Build ancestry',type:'ancestry',system:{rules:[],items:{},boosts:{'0':{value:['str','wis'],selected:null}}}},
 {name:'Build heritage',type:'heritage',system:{rules:[],ancestry:null}},
 {name:'Build background',type:'background',system:{rules:[],items:{},boosts:{'0':{value:['str','wis'],selected:null}},trainedSkills:{value:['nature'],lore:['Terrain Lore']},description:{value:'Build verification background source.'}}},
 {name:'Build class',type:'class',system:{rules:[],items:{},trainedSkills:{value:['nature'],additional:1}}},
 {name:'Build deity',type:'deity',system:{rules:[],spells:{'1':SPELL}}},
 {name:'Build feature',type:'feat',system:{rules:[],category:'classfeature',level:{value:1,taken:1},description:{value:'Build verification feature source.'}},flags:{pf2e:{rulesSelections:{choice:'recorded choice'}}}},
 {name:'Terrain Lore',type:'lore',system:{rules:[],proficient:{value:1}}}
];
const items=await actor.createEmbeddedDocuments('Item',inputs);
if(items.length!==7||actor.items.size!==7)throw Error('Unexpected fixture membership');
const byType=Object.fromEntries(items.map(item=>[item.type,item]));
const grants={lore:{id:byType.lore.id,onDelete:'detach'},feature:{id:byType.feat.id,onDelete:'detach'}};
await actor.updateEmbeddedDocuments('Item',[
 {_id:byType.background.id,'flags.pf2e.itemGrants':grants},
 {_id:byType.class.id,'flags.pf2e.itemGrants':grants,'system.items':{future:{uuid:FUTURE,name:'Battle Medicine',img:'icons/svg/item-bag.svg',level:19}}},
 {_id:byType.lore.id,'flags.pf2e.grantedBy':{id:byType.background.id,onDelete:'detach'}},
 {_id:byType.feat.id,'flags.pf2e.grantedBy':{id:byType.background.id,onDelete:'detach'}}
]);
if(actor.items.size!==7||actor.items.some(item=>item.type==='spell'))throw Error('Unexpected automatic acquisition');
const report=JSON.stringify({items:Object.fromEntries(items.map(item=>[item.type,item.uuid]))});
""".replace('SPELL', json.dumps(selected['spell'])).replace('FUTURE', json.dumps(selected['future'])))
            fingerprint_code = owned_guard + """
const data=JSON.stringify(actor.toObject(true));
const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(data))),v=>v.toString(16).padStart(2,'0')).join('');
const report=JSON.stringify({hash,count:actor.items.size});
"""
            stage = 'source_fingerprint_before'
            before = await js(fingerprint_code)
            stage = 'character_stored_source'
            stored = await js(owned_guard + """
const s=actor.toObject(true).system;
const report=JSON.stringify({abilities:s.abilities,level:s.details.level.value,age:s.details.age.value,appearance:s.details.biography.appearance,edicts:s.details.biography.edicts,anathema:s.details.biography.anathema,languages:s.details.languages,nature:s.skills.nature.rank,hero:s.resources.heroPoints,focus:s.resources.focus.value,manual:s.build.attributes.manual,boosts:s.build.attributes.boosts['1'],apex:s.build.attributes.apex});
""")
            assert stored == {'abilities': None, 'level': 1, 'age': 'Adult', 'appearance': '<p>Character source verification.</p>', 'edicts': ['Keep the record.'], 'anathema': [], 'languages': {'value': ['common'], 'details': 'Authored language note.'}, 'nature': 1, 'hero': {'value': 1, 'max': 3}, 'focus': 0, 'manual': False, 'boosts': [], 'apex': None}
            stage = 'character_source_description'
            character_rows, character_cursor, character_pages = [], None, 0
            while True:
                assert character_pages < 100
                arguments = {'actor_uuid': actor_uuid, 'sections': ['source', 'description'], 'limit': 7, 'max_bytes': 8000}
                if character_cursor:
                    arguments['cursor'] = character_cursor
                character_page = payload(await client.call_tool('read_actor', arguments))
                assert character_page['identity']['uuid'] == actor_uuid
                assert all(section['status'] in ('complete', 'partial') and set(section['reasons']) <= {'pagination'} for section in character_page['sections'])
                character_rows.extend(character_page['records'])
                character_pages += 1
                character_cursor = character_page['pagination']['next_cursor']
                if not character_cursor:
                    break
            assert all(section['status'] == 'complete' for section in character_page['sections'])
            def character_field(path):
                return next(row for row in character_rows if row['raw'][0]['path'] == path)
            expected_source = {'/system/abilities': stored['abilities'], '/system/details/level/value': stored['level'], '/system/details/age/value': stored['age'], '/system/skills/nature/rank': stored['nature'], '/system/resources/heroPoints/value': stored['hero']['value'], '/system/resources/heroPoints/max': stored['hero']['max'], '/system/resources/focus/value': stored['focus'], '/system/build/attributes/manual': stored['manual'], '/system/build/attributes/boosts/1': stored['boosts'], '/system/build/attributes/apex': stored['apex'], '/system/details/languages/value/0': stored['languages']['value'][0]}
            expected_notes = {'/system/details/biography/appearance': stored['appearance'], '/system/details/biography/edicts/0': stored['edicts'][0], '/system/details/biography/anathema': stored['anathema'], '/system/details/languages/details': stored['languages']['details']}
            for path, value in {**expected_source, **expected_notes}.items():
                row = character_field(path)
                assert row['raw'][0]['document_uuid'] == actor_uuid and row['raw'][0]['present'] and row['raw'][0]['value'] == value
                assert row['section'] == ('description' if path in expected_notes else 'source')
            assert character_field('/system/skills/nature/rank')['mapped']['value'] == {'rank': 1, 'label': 'Trained'}
            assert not any(raw['path'].startswith('/system/abilities/') or raw['path'] in ('/system/attributes/hp/max', '/system/resources/focus/max', '/system/resources/focus/cap') for row in character_rows for raw in row['raw'])
            stage = 'character_default_source_privacy'
            default_rows, default_cursor = [], None
            for _ in range(100):
                arguments = {'actor_uuid': actor_uuid, 'limit': 7, 'max_bytes': 8000}
                if default_cursor:
                    arguments['cursor'] = default_cursor
                default_page = payload(await client.call_tool('read_actor', arguments))
                default_rows.extend(default_page['records'])
                default_cursor = default_page['pagination']['next_cursor']
                if not default_cursor:
                    break
            assert default_cursor is None
            assert not any(row['section'] == 'description' for row in default_rows)
            assert not any(text in json.dumps(default_rows) for text in (stored['appearance'], stored['edicts'][0], stored['languages']['details']))
            if check_statistics:
                stage = 'statistics_discovery'
                registry = payload(await client.call_tool('get_actor_types', {}))
                support = next(section for section in registry['actor_sections'] if section['name'] == 'statistics')
                assert not support['source_supported'] and support['mapped_supported'] and support['effective_supported']
                stage = 'statistics_serialized_preflight'
                current = await js(owned_guard + """
const serialized=actor.toObject(false);
// Independent fixture expectation: inspect own data properties only. Never
// call a statistic getter/method or substitute persisted source values.
function own(keys){let value=serialized;for(const key of keys){if(value===null||typeof value!=='object')return {present:false};const d=Object.getOwnPropertyDescriptor(value,key);if(!d||!Object.hasOwn(d,'value')||d.value===undefined)return {present:false};value=d.value;}return {present:true,value};}
const paths=[];
for(const ability of ['str','dex','con','int','wis','cha'])for(const leaf of ['mod','base'])paths.push(['abilities',ability,leaf]);
for(const leaf of ['value','breakdown','details'])paths.push(['attributes','ac',leaf]);
for(const leaf of ['value','max','temp'])paths.push(['attributes','hp',leaf]);
for(const save of ['fortitude','reflex','will'])for(const leaf of ['value','totalModifier','breakdown','rank'])paths.push(['saves',save,leaf]);
for(const leaf of ['value','totalModifier','breakdown','vision','rank'])paths.push(['perception',leaf]);
for(const mode of ['land','burrow','climb','fly','swim','travel']){const root=['movement','speeds',mode],row=own(['system',...root]);if(!['land','travel'].includes(mode)&&row.present&&row.value===null)paths.push(root);else for(const leaf of ['value','base','type','source'])paths.push([...root,leaf]);}
const fields=paths.map(keys=>({path:'/system/'+keys.join('/'),...own(['system',...keys])}));
const shapePaths=[['attributes','hp'],['attributes','ac'],['abilities'],['perception'],['saves','fortitude'],['movement','speeds','land']];
const shapes=shapePaths.map(keys=>{const row=own(['system',...keys]),value=row.value;return {path:'/system/'+keys.join('/'),present:row.present,type:!row.present?'absent':value===null?'null':Array.isArray(value)?'array':typeof value,plain:row.present&&value!==null&&typeof value==='object'&&[Object.prototype,null].includes(Object.getPrototypeOf(value))};});
const report=JSON.stringify({fields,shapes});
""")
                container_shapes = current['shapes']
                stage = 'statistics_pagination'
                statistics_rows, statistics_cursor, statistics_pages = [], None, 0
                while True:
                    assert statistics_pages < 100
                    arguments = {'actor_uuid': actor_uuid, 'sections': ['statistics'], 'limit': 7, 'max_bytes': 8000}
                    if statistics_cursor:
                        arguments['cursor'] = statistics_cursor
                    statistics_page = payload(await client.call_tool('read_actor', arguments))
                    assert statistics_page['identity']['uuid'] == actor_uuid
                    section = statistics_page['sections'][0]
                    assert section['status'] == 'partial' and 'other_statistics_pending' in section['reasons']
                    assert set(section['reasons']) <= {'other_statistics_pending', 'current_fields_unavailable', 'pagination'}
                    statistics_rows.extend(statistics_page['records'])
                    statistics_pages += 1
                    statistics_cursor = statistics_page['pagination']['next_cursor']
                    if not statistics_cursor:
                        break
                stage = 'statistics_assertions'
                assert len(statistics_rows) == len(current['fields'])
                actual = {}
                for row in statistics_rows:
                    assert row['section'] == 'statistics' and len(row['raw']) == 1
                    raw = row['raw'][0]
                    assert raw['document_uuid'] == actor_uuid and raw['basis'] == 'transformed'
                    assert row['provenance']['mapping'] == 'pf2e.actor.current.v1'
                    assert row['provenance']['contributors'] == [{'document_uuid': actor_uuid, 'path': raw['path'], 'basis': 'transformed'}]
                    assert raw['path'] not in actual
                    actual[raw['path']] = {key: raw[key] for key in ('path', 'present', 'value') if key in raw}
                assert actual == {field['path']: field for field in current['fields']}
                assert ('current_fields_unavailable' in statistics_page['sections'][0]['reasons']) == any(not field['present'] for field in current['fields'])
                summary.update(statistics_pages=statistics_pages, statistics_records=len(statistics_rows))
            stage = 'build_pagination'
            rows, cursor, pages = [], None, 0
            while True:
                assert pages < 150, 'Build verification page bound exceeded.'
                arguments = {'actor_uuid': actor_uuid, 'sections': ['build'], 'limit': 7, 'max_bytes': 8000}
                if cursor:
                    arguments['cursor'] = cursor
                page = payload(await client.call_tool('read_actor', arguments))
                assert page['identity']['uuid'] == actor_uuid
                section = page['sections'][0]
                assert section['status'] in ('complete', 'partial')
                assert set(section['reasons']) <= {'pagination'}
                assert (section['status'] == 'partial') == bool(page['pagination']['next_cursor'])
                rows.extend(page['records'])
                pages += 1
                cursor = page['pagination']['next_cursor']
                if not cursor:
                    break
            stage = 'build_assertions'
            assert len({row['key'] for row in rows}) == len(rows)
            identities = [row for row in rows if row['mapped']['concept'] == 'build_item']
            assert len(identities) == 7
            assert {row['mapped']['value']['target_uuid'] for row in identities} == set(setup['items'].values())
            claims = [row for row in rows if row['mapped']['concept'] == 'build_grant_claim']
            assert len(claims) == 4
            for kind in ('lore', 'feat'):
                matching = [row for row in claims if row['mapped']['value']['target_uuid'] == setup['items'][kind]]
                assert len(matching) == 2
                assert {row['mapped']['value']['reciprocity'] for row in matching} == {'agree', 'disagree'}
                assert all(len(row['raw']) == 3 for row in matching)

            def source(kind, path):
                return next(row for row in rows if row['kind'] == 'field' and row['raw'][0]['document_uuid'] == setup['items'][kind] and row['raw'][1]['path'] == path)

            assert source('heritage', '/system/ancestry')['raw'][1]['value'] is None
            assert source('background', '/system/boosts/0/selected')['raw'][1]['value'] is None
            assert source('feat', '/system/category')['mapped']['value'] == {'code': 'classfeature', 'kind': 'feature'}
            assert source('feat', '/flags/pf2e/rulesSelections/choice')['raw'][1]['value'] == 'recorded choice'
            assert source('class', '/system/items/future/uuid')['raw'][1]['value'] == selected['future']
            assert source('class', '/system/items/future/level')['raw'][1]['value'] == 19
            assert source('deity', '/system/spells/1')['raw'][1]['value'] == selected['spell']
            assert all(source(kind, '/system/trainedSkills/value/0')['raw'][1]['value'] == 'nature' for kind in ('background', 'class'))
            item_pages = 0
            for kind in ('background', 'feat'):
                stage = 'background_source_pagination' if kind == 'background' else 'feat_source_pagination'
                item_cursor, item_rows = None, []
                while True:
                    assert item_pages < 100, 'Item verification page bound exceeded.'
                    arguments = {'item_uuid': setup['items'][kind], 'sections': ['source', 'description'], 'limit': 7, 'max_bytes': 8000}
                    if item_cursor:
                        arguments['cursor'] = item_cursor
                    item_page = payload(await client.call_tool('read_item', arguments))
                    assert item_page['identity']['uuid'] == setup['items'][kind]
                    assert item_page['identity']['actor']['uuid'] == actor_uuid
                    assert all(section['status'] in ('complete', 'partial') and set(section['reasons']) <= {'pagination'} for section in item_page['sections'])
                    item_rows.extend(item_page['records'])
                    item_pages += 1
                    item_cursor = item_page['pagination']['next_cursor']
                    if not item_cursor:
                        break
                assert all(section['status'] == 'complete' and not section['reasons'] for section in item_page['sections'])
                assert any(raw['path'] == '/system/description/value' and raw.get('value') for row in item_rows for raw in row['raw'])
            stage = 'source_fingerprint_after'
            after = await js(fingerprint_code)
            assert before == after and after['count'] == 7
            summary.update(passed=True, build_pages=pages, build_records=len(rows), owned_items=7, outgoing_claims=4, item_pages=item_pages, character_pages=character_pages, character_records=len(character_rows), description_verified=True, fingerprint_unchanged=True)
        except Exception as error:
            # Do not print tool exceptions, credentials, document IDs or prose.
            summary['failure'] = 'Build live verification failed; inspect the fixed harness checks.'
            summary.update(failure_stage=stage, exception_type=type(error).__name__)
            if container_shapes is not None:
                summary['container_shapes'] = container_shapes
        finally:
            # Exact UUID plus exact per-run marker authorizes removal. If create's
            # response was lost, discover only this unpredictable marker, never names.
            for attempt in range(3):
                try:
                    cleaned = await js(guard + """
const matches=game.actors.filter(a=>a.getFlag('foundry-mcp','buildVerificationRun')===RUN);
if(matches.length>1)throw Error('Ambiguous verification marker');
const expected=UUID;
if(expected&&matches.some(a=>a.uuid!==expected))throw Error('Verification UUID mismatch');
if(matches.length){const actor=matches[0];if(actor.uuid!==(expected??actor.uuid)||actor.getFlag('foundry-mcp','buildVerificationRun')!==RUN)throw Error('Cleanup identity mismatch');await actor.delete();}
const report=JSON.stringify({clean:!game.actors.some(a=>a.getFlag('foundry-mcp','buildVerificationRun')===RUN)});
""".replace('RUN', marker).replace('UUID', json.dumps(actor_uuid)))
                    if cleaned['clean']:
                        summary['cleanup_confirmed'] = True
                        if actor_uuid is not None:
                            break
                except Exception as error:
                    summary['cleanup_confirmed'] = False
                    summary['cleanup_exception_type'] = type(error).__name__
                if attempt < 2:
                    await asyncio.sleep(1)
            summary['passed'] = summary['passed'] and summary['cleanup_confirmed']
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id', help='Exact existing development world ID; required before fixture writes.')
    parser.add_argument('--discovery-only', action='store_true', help='Read MCP discovery and support only; create no fixture and perform no cleanup writes.')
    parser.add_argument('--statistics', action='store_true', help='Also verify transformed current-statistics fields on the same marked fixture.')
    args = parser.parse_args()
    if not args.discovery_only and not args.world_id:
        parser.error('--world-id is required for fixture verification')
    raise SystemExit(asyncio.run(main(args.world_id, args.discovery_only, args.statistics)))
