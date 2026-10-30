"""PF2e-specific read-only casting serialization check on existing NPCs.

Requires the existing visible GM development browser: localhost:30000, test
world, Foundry 14.369/PF2e 8.6.1. Never creates fixtures or casts/prepares spells.
Public APIs: Actor.items, Document.testUserPermission and Document.toObject:
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
PF2e-specific transformed schemas (focus value/max/cap; spell cast.focusPoints):
https://github.com/foundryvtt/pf2e/tree/28d9d156f252d084371d994dc359509b49eadf18/src/module
Selected transformed values are independent of persisted source; no getters,
sheet data, rules, preparation methods or source fallbacks supply expectations.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from fastmcp.exceptions import McpError
from mcp.types import REQUEST_TIMEOUT

REQUEST_TIMEOUT_SECONDS = 30
INIT_TIMEOUT_SECONDS = 10
SESSION_TIMEOUT_SECONDS = 180


def structured_error_code(error):
    """Return only a known structured tool code, never error text or context."""
    if not isinstance(error, ToolError):
        return None
    try:
        data = json.loads(str(error))
    except (ValueError, TypeError):
        return None
    code = data.get('code') if type(data) is dict else None
    return code if type(code) is str and code in {
        'InvalidFoundryResponse', 'ReadFailed', 'InvalidRequest', 'PermissionDenied',
        'ContentChanged', 'NotFound', 'UnsupportedType', 'UnsupportedSystem',
        'FoundryDisconnected', 'FoundryUnavailable', 'ResponseTooLarge',
    } else None


class CallProgress:
    """Count requested/completed SDK calls, including a failed request."""

    def __init__(self):
        self.requested = 0
        self.completed = 0

    async def call(self, function, *args):
        self.requested += 1
        result = await function(*args)
        self.completed += 1
        return result


async def bounded_pages(request, validate):
    """Restart one section at 48000 bytes only after ResponseTooLarge at 8000.

    Discard prior rows/cursors/revision on the sole retry. Each budget permits
    200 requests, at most 400 total. Caller retains existing SDK deadlines.
    """
    discarded = 0
    for restart, budget in enumerate((8000, 48000)):
        rows, cursor, seen, revision = [], None, set(), None
        for ordinal in range(1, 201):
            try:
                page = await request(budget, cursor, ordinal)
            except ToolError as error:
                if budget == 8000 and structured_error_code(error) == 'ResponseTooLarge':
                    discarded += ordinal - 1
                    break
                raise
            assert len(json.dumps(page, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')) <= budget
            validate(page)
            if revision is None:
                revision = page['revision']
            assert page['revision'] == revision
            rows.extend(page['records'])
            cursor = page['pagination']['next_cursor']
            if not cursor:
                return rows, ordinal, restart, discarded
            assert cursor not in seen
            seen.add(cursor)
        else:
            raise AssertionError('Pagination exceeded fixed 200-page budget bound')
    raise AssertionError('Pagination exhausted byte-limit budgets')


def timeout_failure(error):
    """Classify pinned client deadlines without exposing transport/error text."""
    if isinstance(error, TimeoutError):
        return 'probe_session_timeout'
    if isinstance(error, McpError) and error.error.code == REQUEST_TIMEOUT:
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
    """Decode structured MCP responses without displaying document data."""
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(block.text for block in result.content if block.type == 'text'))


def javascript_payload(result):
    value = payload(result)['value']
    if isinstance(value, dict) and value.get('$type') == 'Array':
        assert value.get('truncated') is False
        value = ''.join(value['values'])
    return json.loads(value)


SNAPSHOT = """
if(!game.ready||!game.user.isGM||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Unsupported development runtime');
if(location.origin!=='http://localhost:30000'||game.world.id!=='test')throw Error('Wrong development world');
function field(document,path){let value=document.toObject(false);for(const key of path.slice(1).split('/')){if(value===null||typeof value!=='object')return {path,present:false};const d=Object.getOwnPropertyDescriptor(value,key);if(!d||!Object.hasOwn(d,'value')||d.value===undefined)return {path,present:false};value=d.value;}return {path,present:true,value};}
const candidates=[];
for(const actor of game.actors.values()){
 if(actor.type!=='npc'||!actor.testUserPermission(game.user,'OBSERVER'))continue;
 const spells=[...actor.items.values()].filter(i=>i.type==='spell'&&i.testUserPermission(game.user,'OBSERVER'));
 if(!spells.length)continue;
 const entries=[...actor.items.values()].filter(i=>i.type==='spellcastingEntry'&&i.testUserPermission(game.user,'OBSERVER'));
 const modes=[...new Set(entries.map(i=>i.toObject(true).system?.prepared?.value).filter(m=>['prepared','spontaneous','innate','focus'].includes(m)))].sort();
 const fields=['value','max','cap'].map(k=>({document_uuid:actor.uuid,...field(actor,'/system/resources/focus/'+k)}));
 for(const spell of spells)fields.push({document_uuid:spell.uuid,...field(spell,'/system/cast/focusPoints')});
 const coverage=[...modes,...(fields.some(f=>f.path.endsWith('/focus/value')&&f.present)?['current_focus']:[]),...(fields.some(f=>f.path==='/system/cast/focusPoints'&&f.present)?['spell_cost']:[])];
 candidates.push({actor,fields,modes,coverage});
}
const selected=[],covered=new Set();
for(let n=0;n<2;n++){
 let best=null,score=0;
 for(const candidate of candidates){if(selected.includes(candidate))continue;const gain=candidate.coverage.filter(k=>!covered.has(k)).length;if(gain>score){best=candidate;score=gain;}}
 if(!best)break;selected.push(best);for(const k of best.coverage)covered.add(k);
}
const samples=[];
for(const {actor,fields,modes}of selected){const bytes=new TextEncoder().encode(JSON.stringify(actor.toObject(true)));const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');samples.push({uuid:actor.uuid,fields,modes,hash});}
const report=JSON.stringify({samples,coverage:[...covered].sort()});
return Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));
"""

OPTION_SETUP = """
if(!game.ready||!game.user.isGM||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1'||location.origin!=='http://localhost:30000'||game.world.id!=='test')throw Error('Wrong development runtime');
const actor=[...game.actors.values()].find(a=>a.uuid===ACTOR_UUID);
if(!actor||!actor.testUserPermission(game.user,'OBSERVER')||actor.items.size>12000)throw Error('Unavailable option Actor');
const sources=new Map();
function source(doc){if(!doc||!doc.testUserPermission(game.user,'OBSERVER'))throw Error('Unreadable option contributor');if(doc!==actor&&doc.parent!==actor)throw Error('Wrong option owner');if(!sources.has(doc.uuid))sources.set(doc.uuid,doc.toObject(true));return sources.get(doc.uuid);}
function at(value,path){for(const encoded of path.slice(1).split('/')){if(value===null||typeof value!=='object')return undefined;const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~'),d=Object.getOwnPropertyDescriptor(value,key);if(!d)return undefined;if(!Object.hasOwn(d,'value'))throw Error('Source accessor prohibited');value=d.value;}return value;}
const scalar=(value,path)=>at(value,path)??null;
const items=[...actor.items.values()];
const assigned=spell=>{const id=at(source(spell),'/system/location/value');return typeof id==='string'&&id?items.find(i=>i.id===id):null;};
const readableEntry=spell=>{const item=assigned(spell);return item?.testUserPermission(game.user,'OBSERVER')&&item.type==='spellcastingEntry'?item:null;};
const ordinary=['prepared','spontaneous','innate','focus'];
function positions(spell,entry){if(!entry)return [];const s=source(entry),p=source(spell);if(at(s,'/system/prepared/value')!=='prepared'||at(s,'/system/prepared/flexible')===true||at(p,'/system/ritual')!=null)return [];const result=[];for(let rank=0;rank<=10;rank++){const uses=at(s,'/system/slots/slot'+rank+'/prepared');if(!Array.isArray(uses))continue;if(uses.length>6000)throw Error('Preparation bound');for(let index=0;index<uses.length;index++)if(at(uses,'/'+index+'/id')===spell.id)result.push({rank,index,expended:typeof at(uses,'/'+index+'/expended')==='boolean'?at(uses,'/'+index+'/expended'):null});}return result;}
function identity(value,doc){const name=[...at(source(doc),'/name')];return value.status==='resolved'&&value.target_uuid===doc.uuid&&value.type===doc.type&&value.name===name.slice(0,256).join('')&&value.name_truncated===(name.length>256)&&!Object.hasOwn(value,'token_uuid');}
"""
OPTION_CENSUS = """
let expected_options=0;const modes=new Set(),observed=new Set(),keys=[];
for(const spell of items.filter(i=>i.type==='spell'&&i.testUserPermission(game.user,'OBSERVER'))){const p=source(spell),entry=readableEntry(spell),uses=positions(spell,entry);expected_options+=uses.length||1;if(uses.length>1)observed.add('repeated_preparations');if(uses.some(u=>u.expended===true))observed.add('expended_preparation');if(uses.some(u=>u.expended===false))observed.add('unexpended_preparation');
const mode=entry?at(source(entry),'/system/prepared/value'):null;
for(const use of uses.length?uses:[null])keys.push('spellcasting:option:'+spell.uuid+':'+(entry?.uuid??'unassigned')+':'+(use?.rank??'none')+':'+(use?.index??'none'));
if(entry&&uses.some(u=>at(source(entry),'/system/slots/slot'+u.rank+'/value')===0))observed.add('zero_generic_slot_counter');
if(ordinary.includes(mode)&&at(source(entry),'/system/prepared/flexible')!==true&&at(p,'/system/ritual')==null)modes.add(mode);
if(!entry)observed.add('unresolved_entry');if(at(p,'/system/location/signature')===true)observed.add('signature_recorded');if(at(p,'/system/traits/value')?.includes('cantrip'))observed.add(mode==='innate'?'innate_cantrip':'cantrip');if(mode==='innate'&&at(p,'/system/location/uses')===undefined)observed.add('innate_uses_absent');
}
const expected_keys_sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(keys.sort())))),b=>b.toString(16).padStart(2,'0')).join('');
const report=JSON.stringify({expected_options,expected_keys_sha256,modes:[...modes].sort(),observed:[...observed].sort()});
"""
OPTION_CHECK = """
const checks=[];
for(const value of claims){const spell=items.find(i=>i.uuid===value.spell.target_uuid&&i.type==='spell');if(!spell||!spell.testUserPermission(game.user,'OBSERVER'))throw Error('Option spell unavailable');const p=source(spell),entry=readableEntry(spell),e=entry?source(entry):null,mode=e?scalar(e,'/system/prepared/value'):null;
let ok=identity(value.spell,spell);
if(entry)ok=ok&&identity(value.entry,entry);else{const target=assigned(spell),status=!target?'missing':!target.testUserPermission(game.user,'OBSERVER')?'denied':'unsupported';ok=ok&&value.entry.status===status&&value.entry.target_uuid===null;}
const unsupported=at(p,'/system/ritual')!=null||(entry&&(at(e,'/system/prepared/flexible')===true||!ordinary.includes(mode)));
const all=positions(spell,entry);let position=null;
if(mode==='prepared'&&!unsupported&&all.length){position=all.find(r=>r.rank===value.slot_rank&&r.index===value.preparation_index);ok=ok&&!!position;}else ok=ok&&value.slot_rank===null&&value.preparation_index===null;
const context=unsupported?'unsupported_mode':position?'prepared_use':mode==='spontaneous'?'spontaneous_repertoire':mode==='innate'?'innate_spell':mode==='focus'?'focus_spell':'listed_spell';
const traits=at(p,'/system/traits/value'),cantrip=Array.isArray(traits)?traits.includes('cantrip'):null;
const expected={mode,context,base_rank:scalar(p,'/system/level/value'),configured_rank:scalar(p,'/system/location/heightenedLevel'),slot_rank:position?position.rank:null,preparation_index:position?position.index:null,expended:position?position.expended:null,cast_rank:null,spell_auto_heighten_rank:scalar(p,'/system/location/autoHeightenLevel'),entry_auto_heighten_rank:e?scalar(e,'/system/autoHeightenLevel/value'):null,signature:scalar(p,'/system/location/signature'),cantrip,uses:mode==='innate'?{value:scalar(p,'/system/location/uses/value'),max:scalar(p,'/system/location/uses/max')}:null,resource_scope:context==='prepared_use'?'individual_preparation':context==='spontaneous_repertoire'?'shared_entry_slots':context==='innate_spell'?'individual_spell_uses':context==='focus_spell'?'shared_actor_focus':'not_evaluated',availability:'not_evaluated'};
for(const [key,actual]of Object.entries(expected))ok=ok&&JSON.stringify(value[key])===JSON.stringify(actual);
checks.push(ok);}
const report=JSON.stringify(checks);
"""
OPTION_RAW = """
const checks=[];for(const claim of claims){const doc=claim.document_uuid===actor.uuid?actor:items.find(i=>i.uuid===claim.document_uuid);const value=at(source(doc),claim.path);checks.push(claim.basis==='source'&&claim.present===(value!==undefined)&&(!claim.present||JSON.stringify(claim.value)===JSON.stringify(value)));}
const report=JSON.stringify(checks);
"""


def option_code(actor_uuid, body, claims=None):
    """PF2e-specific independent source checks, bounded code and boolean reports."""
    code = OPTION_SETUP.replace('ACTOR_UUID', json.dumps(actor_uuid))
    if claims is not None:
        code += 'const claims=' + json.dumps(claims) + ';'
    code += body
    code += "\nreturn Array.from({length:Math.ceil(report.length/800)},(_,i)=>report.slice(i*800,(i+1)*800));"
    assert len(code.encode()) <= 32768
    return code


async def verify_contextual_options(browser, actor_uuid, rows):
    """PF2e-specific option semantics and all source witnesses, never availability.

    Independent public document reads check each returned interpretation and
    count expected source contexts. Only safe coverage tags and counts return.
    """
    options = [row for row in rows if row['provenance']['mapping'] == 'pf2e.actor.casting-options.v1']
    census = await browser(option_code(actor_uuid, OPTION_CENSUS))
    assert census['expected_options'] == len(options) and len(options) > 0
    keys = sorted(row['key'] for row in options)
    assert len(set(keys)) == len(keys)
    assert hashlib.sha256(json.dumps(keys, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() == census['expected_keys_sha256']
    raw = {}
    for row in options:
        assert row['section'] == 'spellcasting' and row['kind'] == 'relationship'
        assert row['mapped']['concept'] == 'casting_contextual_option'
        assert row['mapped']['value']['availability'] == 'not_evaluated'
        assert row['provenance']['limitations'] == ['availability_not_evaluated', 'configured_rank_not_final_cast_rank']
        assert row['provenance']['contributors'] == [{key: witness[key] for key in ('document_uuid', 'path', 'basis')} for witness in row['raw']]
        for witness in row['raw']:
            key = (witness['document_uuid'], witness['path'])
            assert key not in raw or raw[key] == witness
            raw[key] = witness

    async def check_batches(values, body, size):
        batch = []
        for value in values:
            candidate = batch + [value]
            try:
                option_code(actor_uuid, body, candidate)
            except AssertionError:
                assert batch
                checks = await browser(option_code(actor_uuid, body, batch))
                assert len(checks) == len(batch) and all(check is True for check in checks)
                batch = [value]
            else:
                batch = candidate
            if len(batch) >= size:
                checks = await browser(option_code(actor_uuid, body, batch))
                assert len(checks) == len(batch) and all(check is True for check in checks)
                batch = []
        if batch:
            checks = await browser(option_code(actor_uuid, body, batch))
            assert len(checks) == len(batch) and all(check is True for check in checks)

    await check_batches(list(raw.values()), OPTION_RAW, 80)
    await check_batches([row['mapped']['value'] for row in options], OPTION_CHECK, 10)
    return dict(options=len(options), unique_source_witnesses=len(raw), modes=census['modes'], observed=census['observed'])


async def main(discovery_only=False):
    summary = {'passed': False}
    stage = 'connection'
    progress = CallProgress()
    sample_ordinal, page_ordinal = 0, 0
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
            stage = 'discovery'
            tools = {tool.name: tool for tool in await progress.call(client.list_tools)}
            assert {'execute_javascript', 'read_actor', 'get_actor_types'} <= tools.keys()
            tool = tools['read_actor']
            properties = tool.inputSchema['properties']
            assert 'spellcasting' in properties['sections']['items']['enum']
            assert properties['limit']['minimum'] <= 7 <= properties['limit']['maximum']
            assert properties['max_bytes']['minimum'] <= 8000 <= properties['max_bytes']['maximum']
            assert tool.annotations.readOnlyHint
            assert all(term in tool.description.lower() for term in ('transformed', 'spellcasting', 'focus', 'partial'))
            assert all(term in tool.description for term in ('casting_contextual_option', 'pf2e.actor.casting-options.v1', 'cast_rank', 'not_evaluated'))
            if discovery_only:
                print(json.dumps({'passed': True, 'discovery_verified': True, 'mcp_calls': progress.completed, 'requested_calls': progress.requested, 'completed_calls': progress.completed, 'runtime_checked': False}))
                return 0
            stage = 'registry'
            registry = payload(await progress.call(client.call_tool, 'get_actor_types', {}))
            assert any(row['name'] == 'spellcasting' for row in registry['actor_sections'])
            stage = 'guarded_existing_npc_selection'
            before = javascript_payload(await progress.call(client.call_tool, 'execute_javascript', {'code': SNAPSHOT}))
            assert 1 <= len(before['samples']) <= 2
            totals = {'pages': 0, 'records': 0, 'current_records': 0, 'source_pages': 0, 'byte_limit_restarts': 0, 'discarded_pages': 0,
                      'contextual_options': 0, 'option_source_witnesses': 0}
            option_modes, option_observed = set(), set()
            for sample_ordinal, sample in enumerate(before['samples'], 1):
                async def pages(sections=None):
                    async def request(budget, cursor, ordinal):
                        nonlocal page_ordinal
                        page_ordinal = ordinal
                        args = {'actor_uuid': sample['uuid'], 'limit': 7, 'max_bytes': budget}
                        if sections is not None:
                            args['sections'] = sections
                        if cursor:
                            args['cursor'] = cursor
                        return payload(await progress.call(client.call_tool, 'read_actor', args))

                    def validate(result):
                        assert result['identity']['uuid'] == sample['uuid']
                        assert result['identity']['instance'] is None
                        if sections == ['spellcasting']:
                            section = next(row for row in result['sections'] if row['name'] == 'spellcasting')
                            assert section['status'] == 'partial'
                            assert 'availability_not_evaluated' in section['reasons']
                            if any(not field['present'] for field in sample['fields']):
                                assert 'current_fields_unavailable' in section['reasons']
                    rows, count, restarts, discarded = await bounded_pages(request, validate)
                    totals['byte_limit_restarts'] += restarts
                    totals['discarded_pages'] += discarded
                    return rows, count

                stage = 'explicit_spellcasting'
                rows, count = await pages(['spellcasting'])
                totals['pages'] += count
                totals['records'] += len(rows)
                assert len({row['key'] for row in rows}) == len(rows)
                current = [row for row in rows if any(raw['basis'] == 'transformed' for raw in row['raw'])]
                actual = {}
                for row in current:
                    assert row['section'] == 'spellcasting' and len(row['raw']) == 1
                    raw = row['raw'][0]
                    assert raw['basis'] == 'transformed'
                    assert row['kind'] == 'field'
                    assert row['key'] == f"spellcasting:current:{raw['document_uuid']}:{raw['path']}"
                    assert row['provenance']['mapping'] == 'pf2e.actor.casting-current.v1'
                    assert row['provenance']['limitations'] == ['casting_availability_not_evaluated']
                    concepts = {'/system/resources/focus/value': 'current_focus_points', '/system/resources/focus/max': 'current_focus_pool_maximum', '/system/resources/focus/cap': 'current_focus_pool_cap', '/system/cast/focusPoints': 'current_spell_focus_point_cost'}
                    assert row['mapped']['concept'] == concepts[raw['path']]
                    key = (raw['document_uuid'], raw['path'])
                    assert key not in actual
                    assert row['provenance']['contributors'] == [{key: raw[key] for key in ('document_uuid', 'path', 'basis')}]
                    actual[key] = {key: raw[key] for key in ('path', 'present', 'value') if key in raw}
                    assert row['mapped']['value'] == raw.get('value')
                expected = {(row['document_uuid'], row['path']): {key: row[key] for key in ('path', 'present', 'value') if key in row} for row in sample['fields']}
                assert actual == expected
                totals['current_records'] += len(current)
                stage = 'contextual_options'

                async def browser(code):
                    return javascript_payload(await progress.call(client.call_tool, 'execute_javascript', {'code': code}))

                options = await verify_contextual_options(browser, sample['uuid'], rows)
                totals['contextual_options'] += options['options']
                totals['option_source_witnesses'] += options['unique_source_witnesses']
                option_modes.update(options['modes'])
                option_observed.update(options['observed'])
                stage = 'source_and_default_exclusion'
                for sections in (['source'], None):
                    source, count = await pages(sections)
                    totals['source_pages'] += count
                    assert not any(raw['basis'] == 'transformed' for row in source for raw in row['raw'])
            stage = 'fingerprint_after'
            page_ordinal = 0
            after = javascript_payload(await progress.call(client.call_tool, 'execute_javascript', {'code': SNAPSHOT}))
            assert before == after, 'Selected source or transformed snapshot changed'
            missing = sorted(set(['prepared', 'spontaneous', 'innate', 'focus', 'current_focus', 'spell_cost']) - set(before['coverage']))
            mandatory_modes = {'prepared', 'spontaneous', 'innate', 'focus'}
            assert mandatory_modes <= option_modes
            optional_scenarios = {'repeated_preparations', 'zero_generic_slot_counter', 'innate_cantrip', 'unresolved_entry',
                                  'signature_recorded', 'expended_preparation', 'unexpended_preparation', 'cantrip', 'innate_uses_absent'}
            summary.update(passed=True, samples=len(before['samples']), coverage=before['coverage'], missing_coverage=missing,
                           contextual_option_modes=sorted(option_modes), observed_option_scenarios=sorted(option_observed),
                           unobserved_option_scenarios=sorted(optional_scenarios - option_observed),
                           availability_evaluated=False, unverified_actor_types=['character', 'familiar'], fingerprint_unchanged=True, **totals)
    except Exception as error:
        summary.update(failure_stage=stage, exception_type=type(error).__name__, recovery='Read-only verification did not complete; a probe deadline or transport failure does not establish a Foundry API or world failure. No world data was written.')
        if failure := timeout_failure(error):
            summary['failure_kind'] = failure
        if code := structured_error_code(error):
            summary['tool_error_code'] = code
        summary.update(sample_ordinal=sample_ordinal, page_ordinal=page_ordinal)
    summary.update(mcp_calls=progress.completed, requested_calls=progress.requested, completed_calls=progress.completed)
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery-only', action='store_true', help='Check actual MCP discovery without requiring a connected Foundry browser.')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.discovery_only)))
