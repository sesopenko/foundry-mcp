"""Bounded PF2e-specific party check in the existing localhost test world.

Creates two inert characters and one party using core public Actor.create,
update/delete/getFlag/toObject, then cleans only this run's exact marker.
https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html
PF2e8.6.1 persisted party system.details.members[].uuid:
https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/party/data.ts
No prepared party getters or existing-document writes. At most 20 calls/180s
plus a reserved bounded cleanup. Reports only counts/bytes, not game content.
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369'||game.system.id!=='pf2e'||game.system.version!=='8.6.1')throw Error('Wrong development runtime');
"""
STATE = """
globalThis.__mcpPartyProbes??=new Map();
const state=globalThis.__mcpPartyProbes.get(RUN)??{closed:false,pending:0};
globalThis.__mcpPartyProbes.set(RUN,state);
const matches=()=>game.actors.filter(a=>a.getFlag('foundry-mcp','partyProbe')===RUN);
"""
CREATE = STATE + """
if(state.closed||matches().length)throw Error('Fixture already exists or closed');
state.pending++;const created=[];let result;
try {
 for(const role of ['first','second','party']) {
  GUARD;if(state.closed)throw Error('Fixture closed');
  const type=role==='party'?'party':'character';
  const actor=await Actor.implementation.create({name:'MCP temporary party verification '+role,type,
   ...(type==='party'?{system:{details:{members:created.map(a=>({uuid:a.uuid}))}}}:{}),
   flags:{'foundry-mcp':{partyProbe:RUN,partyProbeRole:role}}});
  GUARD;
  if(!actor||actor.type!==type||actor.getFlag('foundry-mcp','partyProbe')!==RUN)throw Error('Wrong fixture identity');
  if(state.closed){await actor.delete();throw Error('Fixture closed during creation');}
  created.push(actor);
 }
 result={party:created[2].uuid,members:created.slice(0,2).map(a=>a.uuid)};
} finally {state.pending--;}
"""
SELECTED = STATE + """
if(state.closed||state.pending)throw Error('Fixture not ready');
const actors=matches();
if(actors.length!==3||actors.filter(a=>a.type==='character').length!==2||actors.filter(a=>a.type==='party').length!==1)throw Error('Fixture identity mismatch');
const party=actors.find(a=>a.type==='party');
if(party.uuid!==EXPECTED)throw Error('Wrong party');
"""
FINGERPRINT = SELECTED + """
const value=JSON.stringify(actors.map(a=>a.toObject(true)));
const result={hash:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value))),b=>b.toString(16).padStart(2,'0')).join('')};
"""
CHANGE = SELECTED + """
GUARD;
const refs=party.toObject(true).system.details.members;
if(refs.length!==2||refs.some(r=>!actors.some(a=>a.type==='character'&&a.uuid===r.uuid)))throw Error('Unexpected fixture references');
await party.update({'system.details.members':refs.slice(0,1)});
const result={changed:true};
"""
CLEANUP = STATE + """
state.closed=true;
for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
const actors=matches();
if(actors.length>3||actors.some(a=>!['character','party'].includes(a.type)))throw Error('Ambiguous fixture marker');
if(actors.filter(a=>a.type==='party').length>1||actors.filter(a=>a.type==='character').length>2)throw Error('Ambiguous fixture types');
for(const actor of actors.sort((a,b)=>(a.type==='party'?-1:0)-(b.type==='party'?-1:0))) {
 GUARD;
 if(actor.getFlag('foundry-mcp','partyProbe')!==RUN||(actor.type==='party'&&EXPECTED!==null&&actor.uuid!==EXPECTED))throw Error('Cleanup identity mismatch');
 await actor.delete();
}
const result={pending:state.pending,remaining:matches().length};
"""


def code(body, marker, expected=None):
    """PF2e-specific fixed-fixture script with exact-marker/runtime admission."""
    if not isinstance(marker, str) or not re.fullmatch(r'[a-f0-9]{32}', marker):
        raise ValueError('Exact random marker required')
    return (GUARD + body.replace('RUN', json.dumps(marker)).replace('EXPECTED', json.dumps(expected)).replace('GUARD', GUARD)
            + '\nreturn JSON.stringify(result);')


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


async def verify(client):
    marker = uuid4().hex
    party = None
    calls = 0
    report = {'passed': False, 'cleanup_verified': False, 'rows': []}

    async def call(name, args, *, cleanup=False, error=False):
        nonlocal calls
        calls += 1
        if calls > (21 if cleanup else 20):
            raise AssertionError('Call bound exceeded')
        response = await client.call_tool(name, args, raise_on_error=not error)
        if error:
            return response
        return response.structured_content or json.loads(next(c.text for c in response.content if c.type == 'text'))

    async def execute(body, *, cleanup=False):
        result = await call('execute_javascript', {'code': code(body, marker, party)}, cleanup=cleanup)
        return json.loads(result['value'])

    try:
        async with asyncio.timeout(180):
            created = await execute(CREATE)
            party = created['party']
            before = await execute(FINGERPRINT)
            default = await call('get_party_members', {})
            report['rows'].append({'scenario': 'default_candidates', 'bytes': size(default), 'complete': default['pagination']['complete']})
            summary = await call('get_party_members', {'party_uuid': party})
            assert summary['scope_status'] == 'complete' and summary['pagination']['complete']
            assert [e['identity']['uuid'] for e in summary['entries']] == created['members']
            assert all(e['identity']['type'] == 'character' for e in summary['entries'])
            report['rows'].append({'scenario': 'selected_roster', 'bytes': size(summary), 'complete': True})
            entries, pages, cursor = [], [], None
            for _ in range(3):
                args = {'party_uuid': party, 'limit': 1}
                if cursor:
                    args['cursor'] = cursor
                page = await call('get_party_members', args)
                assert page['revision'] == summary['revision']
                entries.extend(page['entries']); pages.append(page)
                cursor = page['pagination']['next_cursor']
                if cursor is None:
                    break
            assert cursor is None and entries == summary['entries'] and len(pages) == 2
            report['rows'].append({'scenario': 'complete_pagination', 'bytes': sum(size(p) for p in pages), 'calls': len(pages), 'complete': True})
            for entry in entries:
                actor = await call(entry['next_call']['tool'], entry['next_call']['arguments'])
                assert actor['identity']['uuid'] == entry['identity']['uuid']
            assert await execute(FINGERPRINT) == before
            await execute(CHANGE)
            stale = await call('get_party_members', {'party_uuid': party, 'limit': 1, 'cursor': pages[0]['pagination']['next_cursor']}, error=True)
            assert stale.is_error and 'ContentChanged' in str(stale.content)
            report.update(passed=True, source_unchanged=True, stale_cursor_rejected=True)
    except Exception as error:
        report.update(passed=False, exception_type=type(error).__name__)
    finally:
        try:
            async with asyncio.timeout(30):
                removed = await asyncio.shield(execute(CLEANUP, cleanup=True))
            report['cleanup_verified'] = removed == {'pending': 0, 'remaining': 0}
            report['passed'] &= report['cleanup_verified']
        except Exception as error:
            report.update(passed=False, cleanup_exception_type=type(error).__name__)
        report['calls'] = calls
    return report


async def main(catalog_only):
    root = Path(__file__).resolve().parents[1]
    token = next(line.partition('=')[2].strip() for line in (root / '.env.mcp').read_text().splitlines()
                 if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    async with Client(transport, timeout=30, init_timeout=10) as client:
        catalog = await client.list_tools()
        party_tool = next((t for t in catalog if t.name == 'get_party_members'), None)
        report = {'catalog_bytes': size([t.model_dump(mode='json') for t in catalog]),
                  'tools': len(catalog), 'discovery_calls': 1,
                  'party_schema_bytes': size(party_tool.model_dump(mode='json')) if party_tool else None}
        if not catalog_only:
            assert party_tool is not None and party_tool.outputSchema is not None
            report.update(await verify(client))
    print(json.dumps(report))
    return 0 if catalog_only or report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-only', action='store_true', help='Read-only discovery baseline; no fixture creation.')
    raise SystemExit(asyncio.run(main(parser.parse_args().catalog_only)))
