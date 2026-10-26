"""PF2e-specific integrated state check, read-only by default on existing NPCs.

Public Document.toObject/testUserPermission, Actor.items and fromUuid only:
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
PF2e 8.6.1 condition/effect schemas, revision
28d9d156f252d084371d994dc359509b49eadf18, establish source field meanings
and the derived EffectSystemData.expired boolean selected through public
Item.system own data properties (never getters or preparation methods).
Default mode makes no fixtures or document writes. Explicit --state-fixture
--world-id test creates one marked genuine character with inert owned Items,
updates only its timed effect's start, verifies without further writes, and
always attempts exact-marker cleanup. No gameplay, preparation, clock changes,
formula evaluation or production selector imports are performed by this probe.
--token-state --world-id test instead checks existing unlinked token state
without creating or changing documents; an absent eligible instance is a gap.
"""

import argparse
import asyncio
import json
from pathlib import Path
import re
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.shared.exceptions import McpError

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180


def timeout_failure(error):
    """Classify pinned client deadlines without exposing transport/error text."""
    if isinstance(error, TimeoutError):
        return 'probe_session_timeout'
    if isinstance(error, McpError) and error.error.code == 408:
        return 'probe_request_timeout'
    # Pinned FastMCP 2.14.1 emits these exact messages only for its handshake
    # TimeoutError (the outer Client connection wrapper preserves the message).
    if isinstance(error, RuntimeError) and str(error) in (
        'Failed to initialize server session',
        'Client failed to connect: Failed to initialize server session',
    ):
        return 'probe_initialization_timeout'
    return None


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


GUARD = """
if(!game.ready||!game.user.isGM||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Unsupported development runtime');
if(location.origin!=='http://localhost:30000'||game.world.id!=='test')throw Error('Wrong development world');
"""
CHUNKS = """
const report=JSON.stringify(result);
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""
SELECT = """
const candidates=[];
for(const actor of game.actors.values()){
 if(actor.type!=='npc'||!actor.testUserPermission(game.user,'OBSERVER'))continue;
 const items=[...actor.items.values()].filter(i=>['condition','effect'].includes(i.type)&&i.testUserPermission(game.user,'OBSERVER'));
 if(items.length)candidates.push({actor,coverage:[...new Set(items.map(i=>i.type))]});
}
const selected=[],covered=new Set();
for(let i=0;i<2;i++){let best=null,score=0;for(const c of candidates){if(selected.includes(c))continue;const gain=c.coverage.filter(k=>!covered.has(k)).length;if(gain>score){best=c;score=gain;}}if(!best)break;selected.push(best);for(const k of best.coverage)covered.add(k);}
const samples=[];
for(const {actor,coverage}of selected){const bytes=new TextEncoder().encode(JSON.stringify(actor.toObject(true)));const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');samples.push({uuid:actor.uuid,coverage,hash,items:[...actor.items.values()].filter(i=>['condition','effect'].includes(i.type)&&i.testUserPermission(game.user,'OBSERVER')).map(i=>({uuid:i.uuid,type:i.type}))});}
const result={samples,coverage:[...covered].sort()};
"""

CREATE_STATE = """
globalThis.__mcpStateProbes??=new Map();const state=globalThis.__mcpStateProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpStateProbes.set(RUN,state);
if(state.closed)throw Error('Probe closed');state.pending++;let actor;
const owned=()=>{if(!actor||actor.type!=='character'||typeof actor.uuid!=='string'||actor.getFlag('foundry-mcp','stateVerificationRun')!==RUN)throw Error('Fixture identity mismatch');};
const open=async()=>{owned();if(state.closed){GUARD;await actor.delete();throw Error('Probe closed during setup');}};
let result;
try{
actor=await Actor.implementation.create({name:'MCP temporary state verification',type:'character',flags:{'foundry-mcp':{stateVerificationRun:RUN}}});await open();
GUARD;
const origins=await actor.createEmbeddedDocuments('Item',['First origin','Second origin'].map(name=>({name,type:'action',system:{actionType:{value:'passive'},actions:{value:null},traits:{value:[],otherTags:[]},rules:[]}})));await open();if(origins.length!==2)throw Error('Origin count');
const context=item=>({origin:{actor:actor.uuid,token:null,item:item.uuid,rollOptions:[],spellcasting:null},target:null,roll:null});
const effect=(name,duration,origin,badge=null)=>({name,type:'effect',system:{level:{value:1},duration,traits:{value:[],otherTags:[]},fromSpell:false,tokenIcon:{show:false},unidentified:false,context:context(origin),badge,rules:[]}});
const condition=(name,slug,isValued,value,persistent=null)=>({name,type:'condition',system:{slug,value:{isValued,value},persistent,traits:{value:[],otherTags:[]},fromSpell:false,group:null,references:{parent:null,children:[],overrides:[],overriddenBy:[]},overrides:[],rules:[]}});
const inputs=[effect('Overlapping state effect',{value:-1,unit:'unlimited',expiry:null,sustained:false},origins[0]),effect('Overlapping state effect',{value:1,unit:'rounds',expiry:'turn-start',sustained:false},origins[1]),effect('Encounter formula state',{value:-1,unit:'encounter',expiry:null,sustained:false},origins[0],{type:'formula',value:'1d4',evaluate:false,reevaluate:null}),condition('Valued state','frightened',true,2),condition('Unvalued state','prone',false,null),condition('Persistent state','persistent-damage',false,null,{formula:'1d6',damageType:'fire',dc:15,criticalHit:false})];
GUARD;const items=await actor.createEmbeddedDocuments('Item',inputs);await open();if(items.length!==6||actor.items.size!==8)throw Error('Unexpected state fixture membership');
const timed=items[1];if(timed.parent!==actor||timed.type!=='effect')throw Error('Wrong timed effect');
GUARD;await actor.updateEmbeddedDocuments('Item',[{_id:timed.id,'system.start.value':game.time.worldTime-600,'system.start.initiative':null}]);await open();
result={uuid:actor.uuid,origins:origins.map(i=>i.uuid),items:items.map(i=>({uuid:i.uuid,type:i.type})),unlimited:items[0].uuid,timed:timed.uuid,formula:items[2].uuid,valued:items[3].uuid,unvalued:items[4].uuid,persistent:items[5].uuid};
}finally{state.pending--;}
"""
TOKEN_SELECT = """
const stats={scenes:0,tokens:0,readable_unlinked_actors:0,unlinked_with_state:0},candidates=[];
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(value)))),b=>b.toString(16).padStart(2,'0')).join('');
for(const scene of game.scenes.values()){if(++stats.scenes>200)throw Error('Scene census bound');if(!scene.testUserPermission(game.user,'OBSERVER'))continue;
for(const token of scene.tokens.values()){if(++stats.tokens>2000)throw Error('Token census bound');if(token.isLinked||!token.testUserPermission(game.user,'OBSERVER'))continue;const actor=token.actor;if(!actor||!['character','npc','familiar'].includes(actor.type)||!actor.testUserPermission(game.user,'OBSERVER'))continue;stats.readable_unlinked_actors++;if(actor.items.size>12000)throw Error('Owned Item census bound');
const items=[...actor.items.values()].filter(i=>['condition','effect'].includes(i.type)&&i.testUserPermission(game.user,'OBSERVER'));if(!items.length)continue;stats.unlinked_with_state++;
const coverage=[...new Set(items.map(i=>i.type))],expiry=[];
for(const item of items.filter(i=>i.type==='effect')){const system=Object.getOwnPropertyDescriptor(item,'system'),d=system&&Object.hasOwn(system,'value')&&system.value&&typeof system.value==='object'?Object.getOwnPropertyDescriptor(system.value,'expired'):null;const present=!!d&&Object.hasOwn(d,'value')&&typeof d.value==='boolean';expiry.push({uuid:item.uuid,present,...(present?{value:d.value}:{})});}if(expiry.some(e=>e.present))coverage.push('effect_expiry');
candidates.push({actor,token,scene,items,expiry,coverage});}}
const selected=[],covered=new Set();for(let n=0;n<2;n++){let best=null,score=0;for(const c of candidates){if(selected.includes(c))continue;const gain=c.coverage.filter(k=>!covered.has(k)).length;if(gain>score){best=c;score=gain;}}if(!best)break;selected.push(best);for(const key of best.coverage)covered.add(key);}
const samples=[];for(const {actor,token,scene,items,expiry,coverage}of selected){const base=token.baseActor;const base_uuid=base?.testUserPermission(game.user,'OBSERVER')?base.uuid:null;samples.push({uuid:actor.uuid,selector:{token_uuid:token.uuid},scene_uuid:scene.uuid,base_uuid,coverage,items:items.map(i=>({uuid:i.uuid,type:i.type})),source_hash:await hash([token.toObject(true),actor.toObject(true),...items.map(i=>i.toObject(true))]),current_hash:await hash(expiry)});}
const result={stats,samples,coverage:[...covered].sort(),coverage_gaps:samples.length?[]:['existing_readable_unlinked_token_with_owned_condition_or_effect']};
if(new TextEncoder().encode(JSON.stringify(result)).length>16000)throw Error('Token state metadata bound');
"""
CLEANUP_STATE = """
globalThis.__mcpStateProbes??=new Map();const state=globalThis.__mcpStateProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpStateProbes.set(RUN,state);state.closed=true;
for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
const matches=game.actors.filter(a=>a.getFlag('foundry-mcp','stateVerificationRun')===RUN);
if(matches.length>1||matches.some(a=>a.type!=='character'))throw Error('Ambiguous fixture marker');
for(const actor of matches){if((EXPECTED!==null&&actor.uuid!==EXPECTED)||actor.getFlag('foundry-mcp','stateVerificationRun')!==RUN)throw Error('Cleanup identity mismatch');GUARD;await actor.delete();}
const result={pending:state.pending,remaining:game.actors.filter(a=>a.getFlag('foundry-mcp','stateVerificationRun')===RUN).length};
"""


def fixture_code(template, run_id, expected_uuid=None):
    """PF2e-specific optional state fixture, exact marker/type/UUID operations."""
    if not isinstance(run_id, str) or re.fullmatch(r'[A-Za-z0-9-]{1,80}', run_id) is None:
        raise ValueError('Safe per-run marker required')
    return GUARD + template.replace('RUN', json.dumps(run_id)).replace('EXPECTED', json.dumps(expected_uuid)).replace('GUARD', GUARD) + CHUNKS


# PF2e-specific state_item names are persisted source identities; immediate
# context references deliberately retain the resolved document display name.
WITNESS_CHECK = """
const checks=[];
for(const claim of claims){
 const item=await foundry.utils.fromUuid(claim.document_uuid);
 if(!item||item.documentName!=='Item'||!item.testUserPermission(game.user,'OBSERVER'))throw Error('Unavailable source Item');
 if(claim.basis==='transformed'){
  if(claim.path!=='/system/expired'||item.type!=='effect')throw Error('Unexpected current witness');
  const system=Object.getOwnPropertyDescriptor(item,'system');
  const expired=system&&Object.hasOwn(system,'value')&&system.value!==null&&typeof system.value==='object'?Object.getOwnPropertyDescriptor(system.value,'expired'):null;
  const present=!!expired&&Object.hasOwn(expired,'value')&&typeof expired.value==='boolean';
  checks.push({present,...(present?{value:expired.value}:{})});continue;
 }
 let value=JSON.parse(JSON.stringify(item.toObject(true))),present=true;
 for(const encoded of claim.path.slice(1).split('/')){const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~');if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)){present=false;break;}value=value[key];}
 checks.push({present,...(present?{value}:{})});
}
const result=checks;
"""
TARGET_CHECK = """
const checks=[];
for(const claim of claims){const doc=await foundry.utils.fromUuid(claim.target_uuid);if(!doc||!doc.testUserPermission(game.user,'OBSERVER'))throw Error('Unavailable relationship target');const selectedName=claim.source_identity?doc.toObject(true).name:doc.name;if(typeof selectedName!=='string')throw Error('Unavailable relationship name');const name=[...selectedName];checks.push({target_uuid:doc.uuid,document_name:doc.documentName,name:name.slice(0,256).join(''),name_truncated:name.length>256,...(Object.hasOwn(claim,'type')?{type:doc.type}:{})});}
const result=checks;
"""


async def _existing_main(discovery_only=False):
    summary, calls, stage = {'passed': False}, 0, 'connection'
    try:
        root = Path(__file__).resolve().parent.parent
        token = None
        for line in (root / '.env.mcp').read_text().splitlines():
            key, separator, value = line.partition('=')
            if separator and key.strip() == 'FOUNDRY_MCP_CALLER_TOKEN':
                token = value.strip()
        if not token:
            raise RuntimeError('Missing local caller credential')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
        # FastMCP bounds context cleanup separately with a five-second grace.
        async with asyncio.timeout(SESSION_TIMEOUT_SECONDS), Client(
            transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS,
        ) as client:
            async def call(name, arguments):
                nonlocal calls
                calls += 1
                return await client.call_tool(name, arguments)

            async def js(code):
                value = payload(await call('execute_javascript', {'code': GUARD + code + CHUNKS}))['value']
                if isinstance(value, dict) and value.get('$type') == 'Array':
                    assert value.get('truncated') is False
                    value = ''.join(value['values'])
                return json.loads(value)

            stage = 'discovery'
            tools = {tool.name: tool for tool in await client.list_tools()}
            calls += 1
            tool = tools['read_actor']
            props = tool.inputSchema['properties']
            assert 'state' in props['sections']['items']['enum']
            assert props['limit']['minimum'] <= 7 <= props['limit']['maximum']
            assert props['max_bytes']['minimum'] <= 8000 <= props['max_bytes']['maximum']
            assert tool.annotations.readOnlyHint
            for text in ('state_item', 'state:capability:affliction', 'pf2e.actor.state-source.v1', 'pf2e.actor.state-capability.v1', 'effective_application_not_evaluated', 'affliction_reading_unsupported', 'unresolved_state_references', 'state_items_denied', 'Item.system', 'effect_expiry_not_application', '12000', '24000', '200'):
                assert text in tool.description
            if discovery_only:
                print(json.dumps({'passed': True, 'discovery_verified': True, 'runtime_checked': False, 'mcp_calls': calls}))
                return 0
            assert 'execute_javascript' in tools
            stage = 'selection'
            before = await js(SELECT)
            assert 1 <= len(before['samples']) <= 2
            totals = {'pages': 0, 'records': 0, 'source_pages': 0, 'raw_witnesses': 0, 'resolved_relationships': 0,
                      'current_expiry_present': 0, 'current_expiry_absent': 0,
                      'expired_true': 0, 'expired_false': 0}
            for sample in before['samples']:
                async def pages(sections):
                    rows, cursor, seen, revision = [], None, set(), None
                    for count in range(200):
                        args = {'actor_uuid': sample['uuid'], 'limit': 7, 'max_bytes': 8000}
                        if sections is not None:
                            args['sections'] = sections
                        if cursor:
                            args['cursor'] = cursor
                        page = payload(await call('read_actor', args))
                        assert page['identity']['uuid'] == sample['uuid'] and page['identity']['instance'] is None
                        if revision is None:
                            revision = page['revision']
                        assert page['revision'] == revision
                        if sections == ['state']:
                            section = next(row for row in page['sections'] if row['name'] == 'state')
                            assert section['status'] == 'partial'
                            assert {'effective_application_not_evaluated', 'affliction_reading_unsupported'} <= set(section['reasons'])
                        rows.extend(page['records'])
                        cursor = page['pagination']['next_cursor']
                        if cursor is None:
                            return rows, count + 1
                        assert cursor not in seen
                        seen.add(cursor)
                    raise AssertionError('Fixed page bound exceeded')

                stage = 'state_pages'
                rows, count = await pages(['state'])
                totals['pages'] += count
                totals['records'] += len(rows)
                assert len({row['key'] for row in rows}) == len(rows)
                capability = [row for row in rows if row['key'] == 'state:capability:affliction']
                assert len(capability) == 1
                assert capability[0]['mapped']['value'] == {'status': 'unsupported', 'reason': 'pf2e_8_6_1_affliction_disabled'}
                assert capability[0]['raw'] == [] and capability[0]['provenance']['contributors'] == []
                assert capability[0]['provenance']['mapping'] == 'pf2e.actor.state-capability.v1'
                identities = [row for row in rows if row['key'].startswith('state:item:')]
                assert {row['mapped']['value']['target_uuid'] for row in identities} == {item['uuid'] for item in sample['items']}
                assert all(row['mapped']['value']['application'] == 'unknown' for row in identities)
                allowed = {item['uuid'] for item in sample['items']}
                witnesses, targets = [], []
                for row in rows:
                    assert row['section'] == 'state'
                    assert row['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')} for raw in row['raw']]
                    for raw in row['raw']:
                        assert raw['document_uuid'] in allowed
                        if row['provenance']['mapping'] == 'pf2e.effect.current.v1':
                            assert raw['basis'] == 'transformed' and raw['path'] == '/system/expired'
                            totals['current_expiry_present' if raw['present'] else 'current_expiry_absent'] += 1
                            if raw['present']:
                                totals['expired_true' if raw['value'] else 'expired_false'] += 1
                        else:
                            assert raw['basis'] == 'source'
                        witnesses.append(raw)
                    value = row['mapped']['value']
                    if row['kind'] == 'relationship' and isinstance(value, dict) and value.get('status') == 'resolved':
                        targets.append({**value, 'source_identity': row['key'].startswith('state:item:')})
                stage = 'independent_source_and_target_checks'
                # Request only selected source witnesses in batches, never whole prose snapshots.
                for offset in range(0, len(witnesses), 40):
                    batch = witnesses[offset:offset + 40]
                    result = await js('const claims=' + json.dumps(batch) + ';' + WITNESS_CHECK)
                    assert result == [{key: raw[key] for key in ('present', 'value') if key in raw} for raw in batch]
                for offset in range(0, len(targets), 30):
                    result = await js('const claims=' + json.dumps(targets[offset:offset + 30]) + ';' + TARGET_CHECK)
                    expected = [{key: value[key] for key in ('target_uuid', 'document_name', 'name', 'name_truncated', 'type') if key in value} for value in targets[offset:offset + 30]]
                    assert result == expected
                totals['raw_witnesses'] += len(witnesses)
                totals['resolved_relationships'] += len(targets)
                stage = 'source_default_exclusion'
                for sections in (['source'], None):
                    source, count = await pages(sections)
                    totals['source_pages'] += count
                    assert not any(row['section'] == 'state' for row in source)
            stage = 'unchanged_source_fingerprints'
            assert await js(SELECT) == before
            summary.update(passed=True, discovery_verified=True, runtime_checked=True, samples=len(before['samples']), coverage=before['coverage'], missing_coverage=sorted({'condition', 'effect'} - set(before['coverage'])), unverified=['character', 'familiar', 'synthetic_token', 'effective_application', 'affliction'], fingerprint_unchanged=True, **totals)
    except Exception as error:
        summary.update(failure_stage=stage, exception_type=type(error).__name__, recovery='Read-only verification did not complete; a probe deadline or transport failure does not establish a Foundry API or world failure. No game data was written.')
        if failure := timeout_failure(error):
            summary['failure_kind'] = failure
    summary['mcp_calls'] = calls
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


def validate_fixture_records(rows, fixture):
    """PF2e-specific declared fixture coverage, no application/suppression claim."""
    identities = [row for row in rows if row['key'].startswith('state:item:')]
    assert len(identities) == 6 and len({row['key'] for row in identities}) == 6
    assert {row['mapped']['value']['target_uuid'] for row in identities} == {item['uuid'] for item in fixture['items']}
    assert all(row['mapped']['value']['application'] == 'unknown' for row in identities)

    def value(uuid, path, basis='source'):
        values = [raw['value'] for row in rows for raw in row['raw'] if raw['document_uuid'] == uuid and raw['path'] == path and raw['basis'] == basis and raw['present']]
        assert values and all(candidate == values[0] for candidate in values)
        return values[0]

    assert value(fixture['unlimited'], '/system/expired', 'transformed') is False
    assert value(fixture['timed'], '/system/expired', 'transformed') is True
    assert value(fixture['unlimited'], '/name') == value(fixture['timed'], '/name')
    for uuid, origin in zip((fixture['unlimited'], fixture['timed']), fixture['origins']):
        assert value(uuid, '/system/context/origin/item') == origin
        reference = next(row for row in rows if row['key'] == f'state:effect:{uuid}:origin_item')
        assert reference['mapped']['value']['status'] == 'resolved' and reference['mapped']['value']['target_uuid'] == origin
    assert len(set(fixture['origins'])) == 2
    assert value(fixture['formula'], '/system/duration/unit') == 'encounter'
    assert value(fixture['formula'], '/system/badge/type') == 'formula'
    assert value(fixture['formula'], '/system/badge/value') == '1d4'
    assert value(fixture['formula'], '/system/badge/evaluate') is False
    assert value(fixture['valued'], '/system/value/isValued') is True and value(fixture['valued'], '/system/value/value') == 2
    assert value(fixture['unvalued'], '/system/value/isValued') is False and value(fixture['unvalued'], '/system/value/value') is None
    for path, expected in [('/system/persistent/formula', '1d6'), ('/system/persistent/damageType', 'fire'), ('/system/persistent/dc', 15), ('/system/persistent/criticalHit', False)]:
        assert value(fixture['persistent'], path) == expected
    capability = next(row for row in rows if row['key'] == 'state:capability:affliction')
    assert capability['mapped']['value'] == {'status': 'unsupported', 'reason': 'pf2e_8_6_1_affliction_disabled'}


async def run_state_fixture(client, world_id, run_id, summary=None):
    """PF2e-specific genuine test Actor setup, public witnesses, exact cleanup."""
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    summary = summary if summary is not None else {}
    summary.update(passed=False, cleanup_verified=False)
    expected_uuid, calls, completed_calls, stage = None, 0, 0, 'state_fixture_creation'

    async def call(name, arguments):
        nonlocal calls, completed_calls
        calls += 1
        response = await client.call_tool(name, arguments)
        completed_calls += 1
        return payload(response)

    async def execute(code):
        value = (await call('execute_javascript', {'code': code}))['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    async def js(body):
        return await execute(GUARD + body + CHUNKS)

    try:
        fixture = await execute(fixture_code(CREATE_STATE, run_id))
        expected_uuid = fixture['uuid']
        prefix = 'const uuid=' + json.dumps(expected_uuid) + ';' + """
const actor=[...game.actors.values()].find(a=>a.uuid===uuid);
if(!actor||actor.type!=='character'||actor.getFlag('foundry-mcp','stateVerificationRun')!==RUN)throw Error('Fixture identity mismatch');
""".replace('RUN', json.dumps(run_id))
        fingerprint = prefix + """
const bytes=new TextEncoder().encode(JSON.stringify([actor.toObject(true),...Array.from(actor.items.values(),i=>i.toObject(true))]));
const result=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
"""
        stage = 'state_fixture_fingerprint_before'
        before = await js(fingerprint)
        stage = 'state_fixture_read'
        rows, cursor, revision, seen, pages = [], None, None, set(), 0
        for _ in range(200):
            args = dict(actor_uuid=expected_uuid, sections=['state'], limit=7, max_bytes=8000)
            if cursor:
                args['cursor'] = cursor
            page = await call('read_actor', args)
            assert page['identity']['uuid'] == expected_uuid and page['identity']['type'] == 'character'
            assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 8000
            section = page['sections'][0]
            assert section['status'] == 'partial' and {'effective_application_not_evaluated', 'affliction_reading_unsupported'} <= set(section['reasons'])
            revision = revision or page['revision']
            assert page['revision'] == revision
            rows.extend(page['records'])
            pages += 1
            cursor = page['pagination']['next_cursor']
            if cursor is None:
                break
            assert cursor not in seen
            seen.add(cursor)
        else:
            raise AssertionError('State fixture page bound')
        assert len({row['key'] for row in rows}) == len(rows)
        validate_fixture_records(rows, fixture)
        stage = 'state_fixture_independent_witnesses'
        witnesses, targets = [], []
        for row in rows:
            assert row['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')} for raw in row['raw']]
            witnesses.extend(row['raw'])
            value = row['mapped']['value']
            if row['kind'] == 'relationship' and isinstance(value, dict) and value.get('status') == 'resolved':
                targets.append({**value, 'source_identity': row['key'].startswith('state:item:')})
        for start in range(0, len(witnesses), 30):
            batch = witnesses[start:start + 30]
            checked = await js('const claims=' + json.dumps(batch) + ';' + WITNESS_CHECK)
            assert checked == [{key: raw[key] for key in ('present', 'value') if key in raw} for raw in batch]
        for start in range(0, len(targets), 20):
            batch = targets[start:start + 20]
            checked = await js('const claims=' + json.dumps(batch) + ';' + TARGET_CHECK)
            assert checked == [{key: value[key] for key in ('target_uuid', 'document_name', 'name', 'name_truncated', 'type') if key in value} for value in batch]
        stage = 'state_fixture_fingerprint_after'
        assert await js(fingerprint) == before
        summary.update(passed=True, actor_type='character', pages=pages, records=len(rows), raw_witnesses=len(witnesses), resolved_relationships=len(targets),
                       expired_true_verified=True, expired_false_verified=True, overlapping_effects_verified=True,
                       distinct_item_origins_verified=True, encounter_formula_verified=True, condition_source_cases=3,
                       fingerprint_unchanged=True, application_evaluated=False, suppression_evaluated=False, affliction_supported=False)
    except Exception as error:
        summary.update(passed=False, failure_stage=stage, exception_type=type(error).__name__)
    finally:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                cleaned = await asyncio.shield(execute(fixture_code(CLEANUP_STATE, run_id, expected_uuid)))
            assert cleaned['pending'] == 0 and cleaned['remaining'] == 0
            summary['cleanup_verified'] = True
        except Exception as error:
            summary.update(passed=False, cleanup_exception_type=type(error).__name__)
        summary.update(mcp_calls=completed_calls, requested_calls=calls, completed_calls=completed_calls)
    return summary


async def run_token_state(client, world_id):
    """PF2e-specific existing synthetic state, canonical selectors, no writes."""
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    summary = dict(passed=False, pages=0, records=0, raw_witnesses=0, item_followups=0,
                   current_expiry_present=0, current_expiry_absent=0, expired_true=0, expired_false=0)
    requested, completed, stage = 0, 0, 'token_state_selection'

    async def call(name, arguments):
        nonlocal requested, completed
        requested += 1
        response = await client.call_tool(name, arguments)
        completed += 1
        return payload(response)

    async def js(body):
        code = GUARD + body + CHUNKS
        assert len(code.encode()) <= 32768
        value = (await call('execute_javascript', {'code': code}))['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    try:
        before = await js(TOKEN_SELECT)
        summary.update(census=before['stats'], coverage=before['coverage'], coverage_gaps=before['coverage_gaps'])
        if before['coverage_gaps']:
            return dict(summary, mcp_calls=completed, requested_calls=requested, completed_calls=completed)
        assert 1 <= len(before['samples']) <= 2
        for sample in before['samples']:
            rows, cursor, revision, seen = [], None, None, set()
            stage = 'token_state_read'
            for _ in range(200):
                args = dict(sample['selector'], sections=['state'], limit=7, max_bytes=8000)
                if cursor:
                    args['cursor'] = cursor
                page = await call('read_actor', args)
                identity = page['identity']
                assert identity['uuid'] == sample['uuid'] and identity['source_kind'] == 'token'
                instance = identity['instance']
                assert instance['token_uuid'] == sample['selector']['token_uuid'] and instance['scene_uuid'] == sample['scene_uuid'] and instance['actor_link'] is False
                assert (instance['base_actor']['uuid'] if instance['base_actor'] is not None else None) == sample['base_uuid']
                assert page['runtime'] == dict(core_version='14.369', system_id='pf2e', system_version='8.6.1')
                assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 8000
                section = page['sections'][0]
                assert section['status'] == 'partial' and {'effective_application_not_evaluated', 'affliction_reading_unsupported'} <= set(section['reasons'])
                revision = revision or page['revision']
                assert page['revision'] == revision
                rows.extend(page['records'])
                summary['pages'] += 1
                cursor = page['pagination']['next_cursor']
                if cursor is None:
                    break
                assert cursor not in seen
                seen.add(cursor)
            else:
                raise AssertionError('Token state page bound')
            assert len({row['key'] for row in rows}) == len(rows)
            identities = [row for row in rows if row['key'].startswith('state:item:')]
            assert {row['mapped']['value']['target_uuid'] for row in identities} == {item['uuid'] for item in sample['items']}
            assert all(row['mapped']['value']['token_uuid'] == sample['selector']['token_uuid'] and row['mapped']['value']['application'] == 'unknown' for row in identities)
            capability = next(row for row in rows if row['key'] == 'state:capability:affliction')
            assert capability['mapped']['value'] == {'status': 'unsupported', 'reason': 'pf2e_8_6_1_affliction_disabled'}
            allowed = {item['uuid'] for item in sample['items']}
            witnesses, targets = [], []
            for row in rows:
                assert row['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')} for raw in row['raw']]
                for raw in row['raw']:
                    assert raw['document_uuid'] in allowed
                    if row['provenance']['mapping'] == 'pf2e.effect.current.v1':
                        assert raw['path'] == '/system/expired' and raw['basis'] == 'transformed'
                        summary['current_expiry_present' if raw['present'] else 'current_expiry_absent'] += 1
                        if raw['present']:
                            assert type(raw['value']) is bool
                            summary['expired_true' if raw['value'] else 'expired_false'] += 1
                    else:
                        assert raw['basis'] == 'source'
                witnesses.extend(row['raw'])
                value = row['mapped']['value']
                if row['kind'] == 'relationship' and isinstance(value, dict) and value.get('status') == 'resolved':
                    targets.append({**value, 'source_identity': row['key'].startswith('state:item:')})
            stage = 'token_state_independent_witnesses'
            for start in range(0, len(witnesses), 20):
                batch = witnesses[start:start + 20]
                actual = await js('const claims=' + json.dumps(batch) + ';' + WITNESS_CHECK)
                assert actual == [{key: raw[key] for key in ('present', 'value') if key in raw} for raw in batch]
            for start in range(0, len(targets), 15):
                batch = targets[start:start + 15]
                actual = await js('const claims=' + json.dumps(batch) + ';' + TARGET_CHECK)
                assert actual == [{key: value[key] for key in ('target_uuid', 'document_name', 'name', 'name_truncated', 'type') if key in value} for value in batch]
                contexts = await js('const claims=' + json.dumps(batch) + ';' + """
const result=[];for(const claim of claims){if(!claim.token_uuid){result.push(!claim.target_uuid.startsWith('Scene.'));continue;}const token=await foundry.utils.fromUuid(claim.token_uuid),target=await foundry.utils.fromUuid(claim.target_uuid);if(!token||!token.testUserPermission(game.user,'OBSERVER')||!token.parent?.testUserPermission(game.user,'OBSERVER')||!token.actor||!token.actor.testUserPermission(game.user,'OBSERVER'))throw Error('Unavailable context');result.push(target?.documentName==='Token'?target.uuid===token.uuid:target?.documentName==='Actor'?target.uuid===token.actor.uuid:target?.documentName==='Item'?target.parent===token.actor&&[...token.actor.items.values()].some(i=>i===target):false);}
""")
                assert len(contexts) == len(batch) and all(value is True for value in contexts)
            stage = 'token_state_item_followup'
            owned = identities[0]['mapped']['value']
            follow = await call('read_item', dict(item_uuid=owned['target_uuid'], token_uuid=owned['token_uuid'], sections=['identity']))
            assert follow['identity']['uuid'] == owned['target_uuid'] and follow['identity']['actor']['uuid'] == sample['uuid']
            assert follow['identity']['instance']['token_uuid'] == sample['selector']['token_uuid']
            summary['item_followups'] += 1
            summary['raw_witnesses'] += len(witnesses)
            summary['records'] += len(rows)
            stage = 'token_state_source_default_exclusion'
            for sections in (['source'], None):
                cursor, seen, source_revision = None, set(), None
                for _ in range(200):
                    args = dict(sample['selector'], limit=7, max_bytes=8000)
                    if sections is not None:
                        args['sections'] = sections
                    if cursor:
                        args['cursor'] = cursor
                    page = await call('read_actor', args)
                    assert page['identity']['uuid'] == sample['uuid'] and page['identity']['instance']['token_uuid'] == sample['selector']['token_uuid']
                    assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 8000
                    source_revision = source_revision or page['revision']
                    assert page['revision'] == source_revision
                    assert not any(row['section'] == 'state' for row in page['records'])
                    cursor = page['pagination']['next_cursor']
                    if cursor is None:
                        break
                    assert cursor not in seen
                    seen.add(cursor)
                else:
                    raise AssertionError('Token source page bound')
        stage = 'token_state_unchanged_fingerprints'
        assert await js(TOKEN_SELECT) == before
        summary.update(passed=True, samples=len(before['samples']), fingerprint_unchanged=True,
                       missing_coverage=sorted({'condition', 'effect', 'effect_expiry'} - set(before['coverage'])),
                       application_evaluated=False, suppression_evaluated=False, affliction_supported=False)
    except Exception as error:
        summary.update(passed=False, failure_stage=stage, exception_type=type(error).__name__)
    summary.update(mcp_calls=completed, requested_calls=requested, completed_calls=completed)
    return summary


async def main(discovery_only=False, state_fixture=False, world_id=None, token_state=False):
    if (state_fixture and token_state or (state_fixture or token_state) and (world_id != 'test' or discovery_only)
            or not (state_fixture or token_state) and world_id is not None):
        raise ValueError('Select one explicit test-world state mode; discovery-only cannot select fixtures or tokens')
    if not (state_fixture or token_state):
        return await _existing_main(discovery_only)
    summary = dict(passed=False) if token_state else dict(passed=False, cleanup_verified=False)
    try:
        token = next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1] / '.env.mcp').read_text().splitlines()
                     if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
        if not token:
            raise RuntimeError('Missing local caller credential')
        transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
        async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                if token_state:
                    summary = await run_token_state(client, world_id)
                else:
                    await run_state_fixture(client, world_id, uuid4().hex, summary)
    except Exception as error:
        summary.update(passed=False, exception_type=type(error).__name__)
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery-only', action='store_true', help='Inspect actual MCP discovery without requiring a browser or calling get_actor_types.')
    parser.add_argument('--state-fixture', action='store_true', help='Create one exact-marked character with inert state Items and always attempt cleanup.')
    parser.add_argument('--world-id', choices=['test'], help='Required with --state-fixture or --token-state.')
    parser.add_argument('--token-state', action='store_true', help='Read existing unlinked token state only; requires --world-id test and creates no fixtures.')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.discovery_only, args.state_fixture, args.world_id, args.token_state)))
