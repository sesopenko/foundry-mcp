"""Read-only PF2e-specific14.369/8.6.1 declared Strike verification.

By default reuse existing NPC world/synthetic Actors and a character when available. Read
only own public Actor.system.actions data; no preparation, getters, rolls,
damage functions, imports, document creation or updates. The explicit optional
--character-fixture creates one marked genuine blank character and deletes it
in finally; it never changes existing documents. Public contracts:
https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ActorData.html
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/base.ts
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180
GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
CHUNKS = """
const encoded=JSON.stringify(result);if(encoded.length>10000)throw Error('Probe metadata bound');
return Array.from({length:Math.ceil(encoded.length/800)},(_,i)=>encoded.slice(i*800,(i+1)*800));
"""
CHARACTER_CREATE = """
globalThis.__mcpStrikeProbes??=new Map();const state=globalThis.__mcpStrikeProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpStrikeProbes.set(RUN,state);
if(state.closed)throw Error('Probe closed');state.pending++;let actor;
try{actor=await Actor.implementation.create({name:'MCP temporary generated Strike verification',type:'character',flags:{'foundry-mcp':{strikeVerificationRun:RUN}}});
if(!actor||actor.type!=='character'||typeof actor.uuid!=='string'||actor.getFlag('foundry-mcp','strikeVerificationRun')!==RUN)throw Error('Fixture identity mismatch');
if(state.closed){GUARD;await actor.delete();throw Error('Probe closed during creation');}
if(actor.items.size!==0)throw Error('Unexpected owned fixture Items');}finally{state.pending--;}
const result={uuid:actor.uuid,owned_items:actor.items.size};
"""
CHARACTER_CLEANUP = """
globalThis.__mcpStrikeProbes??=new Map();const state=globalThis.__mcpStrikeProbes.get(RUN)??{closed:false,pending:0};globalThis.__mcpStrikeProbes.set(RUN,state);state.closed=true;
for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
const matches=game.actors.filter(a=>a.getFlag('foundry-mcp','strikeVerificationRun')===RUN);
if(matches.length>1||matches.some(a=>a.type!=='character'))throw Error('Ambiguous fixture marker');
for(const actor of matches){if((EXPECTED!==null&&actor.uuid!==EXPECTED)||actor.getFlag('foundry-mcp','strikeVerificationRun')!==RUN)throw Error('Cleanup identity mismatch');GUARD;await actor.delete();}
const result={pending:state.pending,remaining:game.actors.filter(a=>a.getFlag('foundry-mcp','strikeVerificationRun')===RUN).length};
"""
SELECT = """
const samples=[];
const eligible=actor=>{if(!actor||!['character','npc'].includes(actor.type)||!actor.testUserPermission(game.user,'OBSERVER'))return false;const s=Object.getOwnPropertyDescriptor(actor,'system');if(!s||!Object.hasOwn(s,'value'))return false;const a=Object.getOwnPropertyDescriptor(s.value,'actions');return a&&Object.hasOwn(a,'value')&&Array.isArray(a.value)&&a.value.length>0;};
const npc=[...game.actors.values()].find(a=>a.type==='npc'&&eligible(a));if(npc)samples.push({actor:npc,selector:{actor_uuid:npc.uuid},kind:'npc_world'});
let scanned=0;
for(const scene of game.scenes.values()){if(!scene.testUserPermission(game.user,'OBSERVER'))continue;for(const token of scene.tokens.values()){if(++scanned>3000)throw Error('Token bound');if(!token.isLinked&&token.actor?.type==='npc'&&token.testUserPermission(game.user,'OBSERVER')&&eligible(token.actor)){samples.push({actor:token.actor,selector:{token_uuid:token.uuid},kind:'npc_synthetic'});break;}}if(samples.some(s=>s.kind==='npc_synthetic'))break;}
const pc=[...game.actors.values()].find(a=>a.type==='character'&&eligible(a));if(pc)samples.push({actor:pc,selector:{actor_uuid:pc.uuid},kind:'character_world'});
const result={samples:samples.map(({actor,selector,kind})=>({uuid:actor.uuid,selector,kind})),character_available:!!pc};
"""


def fixture_code(template, run_id, expected_uuid=None):
    """Build PF2e-specific exact-marker test-character operations, never names."""
    if not isinstance(run_id, str) or re.fullmatch(r'[A-Za-z0-9-]{1,80}', run_id) is None:
        raise ValueError('Safe per-run marker required')
    return GUARD + template.replace('RUN', json.dumps(run_id)).replace('EXPECTED', json.dumps(expected_uuid)).replace('GUARD', GUARD) + CHUNKS


def payload(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


async def verify(client, world_id, character_uuid=None):
    """PF2e-specific bounded independent own-data witnesses; no world writes."""
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    calls = 0
    stage = 'discovery'
    summary = dict(passed=False, pages=0, records=0, raw_witnesses=0,
                   accessor_capabilities=0, generated_origins=0, owned_origins=0)

    async def call(name, arguments):
        nonlocal calls
        calls += 1
        return payload(await client.call_tool(name, arguments))

    async def js(code):
        value = (await call('execute_javascript', {'code': GUARD + code + CHUNKS}))['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    try:
        tools = {tool.name: tool for tool in await client.list_tools()}
        calls += 1
        for name in ('read_actor', 'read_item', 'get_actor_types'):
            assert tools[name].annotations.readOnlyHint
        assert 'token_uuid' in tools['read_actor'].inputSchema['properties']
        for phrase in ('strikes', 'next_cursor', 'generated', 'damage'):
            assert phrase in tools['read_actor'].description
        registry = await call('get_actor_types', {})
        strikes = next(row for row in registry['actor_sections'] if row['name'] == 'strikes')
        assert strikes['mapped_supported']
        stage = 'existing_selection'
        selection_code = SELECT
        if character_uuid is not None:
            selection_code = selection_code.replace("a.type==='character'&&eligible(a)", "a.type==='character'&&a.uuid===" + json.dumps(character_uuid) + "&&eligible(a)")
        selection = await js(selection_code)
        kinds = {sample['kind'] for sample in selection['samples']}
        assert {'npc_world', 'npc_synthetic'} <= kinds
        if character_uuid is not None:
            assert any(sample['kind'] == 'character_world' and sample['uuid'] == character_uuid for sample in selection['samples'])
        for sample in selection['samples']:
            selector = sample['selector']
            resolve = 'const selector=' + json.dumps(selector) + """;
const doc=await foundry.utils.fromUuid(selector.token_uuid??selector.actor_uuid);
if(!doc||!doc.testUserPermission(game.user,'OBSERVER'))throw Error('Missing selection');
const actor=selector.token_uuid?doc.actor:doc;
if(!actor||!actor.testUserPermission(game.user,'OBSERVER'))throw Error('Actor unavailable');
"""
            fingerprint = resolve + """
const sources=[actor.toObject(true),...Array.from(actor.items.values(),item=>item.toObject(true))];
if(selector.token_uuid)sources.push(doc.toObject(true));
const result=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(sources)))),b=>b.toString(16).padStart(2,'0')).join('');
"""
            stage = 'source_fingerprint_before'
            before = await js(fingerprint)
            cursor, revision, seen, records = None, None, set(), []
            stage = 'strikes_read'
            for _ in range(300):
                arguments = dict(selector, sections=['strikes'], limit=8, max_bytes=8000)
                if cursor:
                    arguments['cursor'] = cursor
                page = await call('read_actor', arguments)
                assert page['identity']['uuid'] == sample['uuid']
                if selector.get('token_uuid'):
                    assert page['identity']['instance']['token_uuid'] == selector['token_uuid']
                assert page['runtime'] == dict(core_version='14.369', system_id='pf2e', system_version='8.6.1')
                assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':')).encode()) <= 8000
                section = page['sections'][0]
                assert section['status'] == 'partial'
                assert {'target_context_not_evaluated', 'current_strike_damage_unsupported'} <= set(section['reasons'])
                revision = revision or page['revision']
                assert page['revision'] == revision
                records.extend(page['records'])
                summary['pages'] += 1
                cursor = page['pagination']['next_cursor']
                if cursor is None:
                    break
                assert cursor not in seen
                seen.add(cursor)
            else:
                raise AssertionError('Page bound')
            assert len({row['key'] for row in records}) == len(records)
            assert any(row['provenance']['mapping'] == 'pf2e.actor.strike-current.v1' for row in records)
            if character_uuid is not None and sample['uuid'] == character_uuid:
                assert any(row['provenance']['mapping'] == 'pf2e.actor.strike-origin.v1' and row['mapped']['value']['status'] == 'generated' for row in records)
                assert any(row['mapped']['concept'] == 'current_strike_attack_modifier' and row['raw'][0]['present'] and
                           type(row['raw'][0].get('value')) in (int, float) and
                           float('-inf') < row['raw'][0]['value'] < float('inf') for row in records)
                summary['character_generated_unarmed_verified'] = True
            witnesses = []
            accessors = []
            for row in records:
                for raw in row['raw']:
                    witness = dict(raw)
                    if row['kind'] == 'text':
                        witness['fragment'] = row['text']
                    witnesses.append(witness)
                if row['provenance']['mapping'] == 'pf2e.actor.strike-capability.v1' and row['mapped']['value'].get('reason') == 'accessor_not_read':
                    accessors.append(row['mapped']['value']['path'])
                if row['provenance']['mapping'] == 'pf2e.actor.strike-origin.v1':
                    origin = row['mapped']['value']
                    if origin['status'] == 'generated':
                        assert origin['target_uuid'] is None
                        summary['generated_origins'] += 1
                    elif origin['status'] == 'resolved':
                        follow = dict(item_uuid=origin['target_uuid'], sections=['identity'])
                        if origin.get('token_uuid'):
                            follow['token_uuid'] = origin['token_uuid']
                        target = await call('read_item', follow)
                        assert target['identity']['uuid'] == origin['target_uuid']
                        assert target['identity']['actor']['uuid'] == sample['uuid']
                        summary['owned_origins'] += 1
            stage = 'independent_witnesses'
            fragments = {}
            for witness in witnesses:
                if 'fragment' in witness:
                    key = (witness['document_uuid'], witness['path'], witness['basis'])
                    fragments.setdefault(key, []).append(witness['fragment'])
            for pieces in fragments.values():
                assert pieces[0]['start'] == 0
                assert all(left['end'] == right['start'] and left['total'] == right['total']
                           for left, right in zip(pieces, pieces[1:]))
                assert pieces[-1]['end'] == pieces[-1]['total'] and pieces[-1]['complete']
            for start in range(0, len(witnesses), 8):
                batch = witnesses[start:start + 8]
                checks = await js(resolve + 'const claims=' + json.dumps(batch) + ';' + """
const result=[];
for(const claim of claims){const target=claim.document_uuid===actor.uuid?actor:await foundry.utils.fromUuid(claim.document_uuid);if(!target||!target.testUserPermission(game.user,'OBSERVER'))throw Error('Witness unavailable');let value=claim.basis==='source'?target.toObject(true):target,present=true;
for(const encoded of claim.path.slice(1).split('/')){const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~');if(!value||typeof value!=='object'){present=false;break;}const descriptor=Object.getOwnPropertyDescriptor(value,key);if(!descriptor||!Object.hasOwn(descriptor,'value')){present=false;break;}value=descriptor.value;}
if(claim.fragment){const f=claim.fragment;result.push(present===claim.present&&typeof value==='string'&&value.length===f.total&&value.slice(f.start,f.end)===claim.value);}else result.push(present===claim.present&&(!present||JSON.stringify(value)===JSON.stringify(claim.value)));}
""")
                assert len(checks) == len(batch) and all(check is True for check in checks)
            for path in accessors:
                checked = await js(resolve + 'const path=' + json.dumps(path) + ';' + """
let value=actor,accessor=false;for(const encoded of path.slice(1).split('/')){if(!value||typeof value!=='object')break;const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~'),descriptor=Object.getOwnPropertyDescriptor(value,key);if(!descriptor)break;if(!Object.hasOwn(descriptor,'value')){accessor=true;break;}value=descriptor.value;}const result=accessor;
""")
                assert checked is True
            stage = 'source_fingerprint_after'
            assert await js(fingerprint) == before
            summary['records'] += len(records)
            summary['raw_witnesses'] += len(witnesses)
            summary['accessor_capabilities'] += len(accessors)
        summary.update(passed=True, samples=len(selection['samples']),
                       character_checked=selection['character_available'], source_unchanged=True)
    except Exception as error:
        summary.update(failure_stage=stage, exception_type=type(error).__name__)
    summary['mcp_calls'] = calls
    return summary


async def run_character_fixture(client, world_id, run_id, summary=None):
    """PF2e-specific optional genuine blank character, exact cleanup after failure.

    Public Actor.create/delete/getFlag are documented at the v14 Actor API.
    Only this unpredictable run marker and saved UUID can authorize deletion.
    A closed browser-owned run self-deletes a late creation before returning.
    """
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    summary = summary if summary is not None else {}
    summary.update(passed=False, cleanup_verified=False)
    expected_uuid = None
    fixture_calls = 0
    stage = 'character_fixture_creation'

    async def operation(template):
        nonlocal fixture_calls
        fixture_calls += 1
        response = payload(await client.call_tool('execute_javascript', {'code': fixture_code(template, run_id, expected_uuid)}))
        value = response['value']
        if isinstance(value, dict) and value.get('$type') == 'Array':
            assert value.get('truncated') is False
            value = ''.join(value['values'])
        return json.loads(value)

    try:
        created = await operation(CHARACTER_CREATE)
        assert created['owned_items'] == 0
        expected_uuid = created['uuid']
        stage = 'character_fixture_verification'
        result = await verify(client, world_id, character_uuid=expected_uuid)
        assert result.get('character_generated_unarmed_verified') is True
        summary.update(result, fixture_owned_items=0)
    except Exception as error:
        summary.update(passed=False, failure_stage=stage, exception_type=type(error).__name__)
    finally:
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                removed = await asyncio.shield(operation(CHARACTER_CLEANUP))
            assert removed['remaining'] == 0 and removed['pending'] == 0
            summary['cleanup_verified'] = True
        except Exception as error:
            summary.update(passed=False, cleanup_exception_type=type(error).__name__)
        summary['mcp_calls'] = summary.get('mcp_calls', 0) + fixture_calls
    return summary


async def main(world_id, character_fixture=False):
    if world_id != 'test':
        raise ValueError('Explicit existing test world required')
    token = next(line.partition('=')[2].strip() for line in (Path(__file__).resolve().parents[1] / '.env.mcp').read_text().splitlines()
                 if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    result = dict(passed=False, cleanup_verified=False) if character_fixture else dict(passed=False)
    try:
        async with Client(transport, timeout=REQUEST_TIMEOUT_SECONDS, init_timeout=INIT_TIMEOUT_SECONDS) as client:
            async with asyncio.timeout(SESSION_TIMEOUT_SECONDS):
                if character_fixture:
                    await run_character_fixture(client, world_id, uuid4().hex, result)
                else:
                    result = await verify(client, world_id)
    except Exception as error:
        result.update(passed=False, exception_type=type(error).__name__)
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-id', required=True, choices=['test'])
    parser.add_argument('--character-fixture', action='store_true', help='Create one marked genuine blank character to verify generated unarmed; always attempt exact cleanup.')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.world_id, args.character_fixture)))
