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
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


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


async def main(discovery_only=False):
    summary = {'passed': False}
    stage = 'connection'
    calls = 0
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
        async with Client(transport) as client:
            stage = 'discovery'
            tools = {tool.name: tool for tool in await client.list_tools()}
            calls += 1
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
                print(json.dumps({'passed': True, 'discovery_verified': True, 'mcp_calls': calls, 'runtime_checked': False}))
                return 0
            registry = payload(await client.call_tool('get_actor_types', {}))
            calls += 1
            assert any(row['name'] == 'spellcasting' for row in registry['actor_sections'])
            stage = 'guarded_existing_npc_selection'
            before = javascript_payload(await client.call_tool('execute_javascript', {'code': SNAPSHOT}))
            calls += 1
            assert 1 <= len(before['samples']) <= 2
            totals = {'pages': 0, 'records': 0, 'current_records': 0, 'source_pages': 0}
            for sample in before['samples']:
                async def pages(sections=None):
                    nonlocal calls
                    rows, cursor, cursors, revision = [], None, set(), None
                    for _ in range(200):
                        args = {'actor_uuid': sample['uuid'], 'limit': 7, 'max_bytes': 8000}
                        if sections is not None:
                            args['sections'] = sections
                        if cursor:
                            args['cursor'] = cursor
                        result = payload(await client.call_tool('read_actor', args))
                        calls += 1
                        assert result['identity']['uuid'] == sample['uuid']
                        assert result['identity']['instance'] is None
                        if sections == ['spellcasting']:
                            section = next(row for row in result['sections'] if row['name'] == 'spellcasting')
                            assert section['status'] == 'partial'
                            assert 'availability_not_evaluated' in section['reasons']
                            if any(not field['present'] for field in sample['fields']):
                                assert 'current_fields_unavailable' in section['reasons']
                        if revision is None:
                            revision = result['revision']
                        assert result['revision'] == revision
                        rows.extend(result['records'])
                        cursor = result['pagination']['next_cursor']
                        if not cursor:
                            return rows, len(cursors) + 1
                        assert cursor not in cursors
                        cursors.add(cursor)
                    raise AssertionError('Pagination exceeded fixed 200-page bound')

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
                stage = 'source_and_default_exclusion'
                for sections in (['source'], None):
                    source, count = await pages(sections)
                    totals['source_pages'] += count
                    assert not any(raw['basis'] == 'transformed' for row in source for raw in row['raw'])
            stage = 'fingerprint_after'
            after = javascript_payload(await client.call_tool('execute_javascript', {'code': SNAPSHOT}))
            calls += 1
            assert before == after, 'Selected source or transformed snapshot changed'
            missing = sorted(set(['prepared', 'spontaneous', 'innate', 'focus', 'current_focus', 'spell_cost']) - set(before['coverage']))
            summary.update(passed=True, samples=len(before['samples']), coverage=before['coverage'], missing_coverage=missing, unverified_actor_types=['character', 'familiar'], fingerprint_unchanged=True, **totals)
    except Exception as error:
        summary.update(failure_stage=stage, exception_type=type(error).__name__, recovery='Run ./scripts/server.sh status and ./scripts/codex-dev.sh; open the existing localhost:30000 test world as GM, connect its development bridge, then retry. No world data was written.')
    summary['mcp_calls'] = calls
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery-only', action='store_true', help='Check actual MCP discovery without requiring a connected Foundry browser.')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.discovery_only)))
