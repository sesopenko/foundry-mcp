"""PF2e-specific read-only integrated state check on at most two existing NPCs.

Public Document.toObject/testUserPermission, Actor.items and fromUuid only:
https://foundryvtt.com/api/v14/classes/foundry.abstract.Document.html
https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html
PF2e 8.6.1 condition/effect schemas, revision
28d9d156f252d084371d994dc359509b49eadf18, establish source field meanings
and the derived EffectSystemData.expired boolean selected via toObject(false).
No fixtures, gameplay calls, production selector imports or document writes.
"""

import argparse
import asyncio
import json
from pathlib import Path

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


async def main(discovery_only=False):
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
            for text in ('state_item', 'state:capability:affliction', 'pf2e.actor.state-source.v1', 'pf2e.actor.state-capability.v1', 'effective_application_not_evaluated', 'affliction_reading_unsupported', 'unresolved_state_references', 'state_items_denied', '12000', '24000', '200'):
                assert text in tool.description
            if discovery_only:
                print(json.dumps({'passed': True, 'discovery_verified': True, 'runtime_checked': False, 'mcp_calls': calls}))
                return 0
            assert 'execute_javascript' in tools
            stage = 'selection'
            before = await js(SELECT)
            assert 1 <= len(before['samples']) <= 2
            totals = {'pages': 0, 'records': 0, 'source_pages': 0, 'raw_witnesses': 0, 'resolved_relationships': 0}
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
                        else:
                            assert raw['basis'] == 'source'
                        witnesses.append(raw)
                    value = row['mapped']['value']
                    if row['kind'] == 'relationship' and isinstance(value, dict) and value.get('status') == 'resolved':
                        targets.append(value)
                stage = 'independent_source_and_target_checks'
                # Request only selected source witnesses in batches, never whole prose snapshots.
                for offset in range(0, len(witnesses), 40):
                    batch = witnesses[offset:offset + 40]
                    result = await js('const claims=' + json.dumps(batch) + ';' + """
const checks=[];
for(const claim of claims){const item=await foundry.utils.fromUuid(claim.document_uuid);if(!item||item.documentName!=='Item'||!item.testUserPermission(game.user,'OBSERVER'))throw Error('Unavailable source Item');let value=JSON.parse(JSON.stringify(item.toObject(claim.basis!=='transformed'))),present=true;for(const encoded of claim.path.slice(1).split('/')){const key=encoded.replace(/~1/g,'/').replace(/~0/g,'~');if(value===null||typeof value!=='object'||!Object.hasOwn(value,key)){present=false;break;}value=value[key];}checks.push({present,...(present?{value}:{})});}
const result=checks;
""")
                    assert result == [{key: raw[key] for key in ('present', 'value') if key in raw} for raw in batch]
                for offset in range(0, len(targets), 30):
                    result = await js('const claims=' + json.dumps(targets[offset:offset + 30]) + ';' + """
const checks=[];
for(const claim of claims){const doc=await foundry.utils.fromUuid(claim.target_uuid);if(!doc||!doc.testUserPermission(game.user,'OBSERVER'))throw Error('Unavailable relationship target');const name=[...doc.name];checks.push({target_uuid:doc.uuid,document_name:doc.documentName,name:name.slice(0,256).join(''),name_truncated:name.length>256,...(Object.hasOwn(claim,'type')?{type:doc.type}:{})});}
const result=checks;
""")
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery-only', action='store_true', help='Inspect actual MCP discovery without requiring a browser or calling get_actor_types.')
    raise SystemExit(asyncio.run(main(parser.parse_args().discovery_only)))
