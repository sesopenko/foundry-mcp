"""Bounded GM-guide UI/MCP verification in the existing localhost test world.

Changes only the new module writing-guidance setting, retains its original
value in the browser, and restores it only if still original or exactly owned
by this random probe. No game documents, bridge credentials or other settings.
Budget: 20 calls/120 seconds plus reserved cleanup (30 seconds).
"""
import asyncio
import json
from pathlib import Path
import re
from uuid import uuid4

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

GUARD = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
"""
STATE = """
globalThis.__mcpGuidanceProbes??=new Map();
let state=globalThis.__mcpGuidanceProbes.get(RUN);
const api=await import('/modules/foundry-mcp/scripts/writingGuidance.js');
"""
SETUP = STATE + """
if(state)throw Error('Probe already exists');
state={original:game.settings.get('foundry-mcp','writingGuidance'),closed:false,pending:0,last:null,dialog:null};
globalThis.__mcpGuidanceProbes.set(RUN,state);
state.pending++;
try{state.last=await api.saveWritingGuidance('<p>MCP writing guide '+RUN+'</p>');}
finally{state.pending--;}
const result={saved:true};
"""
OPEN = STATE + """
if(!state||state.closed||state.pending)throw Error('Probe not ready');
const menu=game.settings.menus.get('foundry-mcp.writingGuidance');
if(!menu?.restricted)throw Error('Writing menu is not GM restricted');
state.dialog=new menu.type();
await state.dialog.render({force:true});
const result={opened:true};
"""
SAVE_UI = STATE + """
if(!state||state.closed||state.pending)throw Error('Probe not ready');
const root=state.dialog?.element?.querySelector('[data-writing-guidance]');
const editor=root?.querySelector('[data-guidance-editor]')?.firstElementChild;
if(!editor||typeof editor.save!=='function')throw Error('Rich text editor missing');
const previous=state.last.saved_at;
root.querySelector('[data-guidance-save]').click();
for(let n=0;n<40;n++){
 await new Promise(resolve=>setTimeout(resolve,50));GUARD;
 if(root.querySelector('[data-guidance-status]').textContent.startsWith('Saved: '))break;
}
if(!root.querySelector('[data-guidance-status]').textContent.startsWith('Saved: '))throw Error('UI save not confirmed');
state.last=api.getWritingGuidance();
if(!state.last.html.includes(RUN)||state.last.saved_at<=previous)throw Error('UI save identity mismatch');
const result={ui_saved:true,editor_tag:editor.tagName,timestamp_advanced:true};
"""
EMPTY = STATE + """
if(!state||state.closed||state.pending)throw Error('Probe not ready');
state.pending++;
try{state.last=await api.saveWritingGuidance('',state.last);}
finally{state.pending--;}
const result={saved:true};
"""
HEAVY = STATE + """
if(!state||state.closed||state.pending)throw Error('Probe not ready');
state.pending++;
try{state.last=await api.saveWritingGuidance('<p>'+RUN+' '+('😀'.repeat(2800))+'</p>',state.last);}
finally{state.pending--;}
const result={saved:true};
"""
CLEANUP = STATE + """
let restored=true;
if(state){
 state.closed=true;
 if(state.dialog)await state.dialog.close();
 for(let n=0;state.pending&&n<100;n++){await new Promise(resolve=>setTimeout(resolve,100));GUARD;}
 if(state.pending)throw Error('Probe save still pending');
 const current=game.settings.get('foundry-mcp','writingGuidance');
 const original=JSON.stringify(current)===JSON.stringify(state.original);
 const last=state.last&&current.html===state.last.html&&current.saved_at===state.last.saved_at;
 const marked=typeof current.html==='string'&&current.html.includes(RUN);
 if(!original&&!last&&!marked)throw Error('Guidance changed outside probe; restoration refused');
 await game.settings.set('foundry-mcp','writingGuidance',state.original);
 restored=JSON.stringify(game.settings.get('foundry-mcp','writingGuidance'))===JSON.stringify(state.original);
}
const result={restored,pending:state?.pending??0};
"""


def code(body, marker):
    if not isinstance(marker, str) or not re.fullmatch(r'[a-f0-9]{32}', marker):
        raise ValueError('Exact random marker required')
    return GUARD + body.replace('RUN', json.dumps(marker)).replace('GUARD', GUARD) + '\nreturn JSON.stringify(result);'


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


async def verify(client):
    marker, calls = uuid4().hex, 0
    report = {'passed': False, 'rows': []}

    async def call(name, args, *, cleanup=False, error=False):
        nonlocal calls
        calls += 1
        if calls > (21 if cleanup else 20):
            raise AssertionError('Call budget exceeded')
        result = await client.call_tool(name, args, raise_on_error=not error)
        return result if error else result.structured_content

    async def execute(body, *, cleanup=False):
        data = await call('execute_javascript', {'code': code(body, marker)}, cleanup=cleanup)
        return json.loads(data['value'])

    try:
        async with asyncio.timeout(120):
            await execute(SETUP)
            first = await call('get_writing_guidance', {})
            assert first['changed'] and marker in first['gm_guidance']['html']
            report['rows'].append({'scenario': 'default', 'bytes': size(first), 'complete': True})
            unchanged = await call('get_writing_guidance', {'since': first['timestamp']})
            assert not unchanged['changed'] and 'gm_guidance' not in unchanged
            report['rows'].append({'scenario': 'unchanged', 'bytes': size(unchanged), 'complete': True})
            await execute(OPEN)
            report['ui'] = await execute(SAVE_UI)
            changed = await call('get_writing_guidance', {'since': first['timestamp']})
            assert changed['changed'] and marker in changed['gm_guidance']['html']
            await execute(EMPTY)
            empty = await call('get_writing_guidance', {'since': changed['timestamp']})
            assert empty['changed'] and empty['gm_status'] == 'empty' and empty['gm_guidance']['html'] == ''
            await execute(HEAVY)
            too_large = await call('get_writing_guidance', {}, error=True)
            assert too_large.is_error and 'ResponseTooLarge' in str(too_large.content)
            expanded = await call('get_writing_guidance', {'max_bytes': 48000})
            assert expanded['gm_guidance']['html'] == '<p>' + marker + ' ' + '😀' * 2800 + '</p>'
            report['rows'].append({'scenario': 'explicit_long_guide', 'bytes': size(expanded), 'complete': True})
            report['passed'] = True
    except Exception as error:
        report['exception_type'] = type(error).__name__
    finally:
        try:
            async with asyncio.timeout(30):
                restored = await asyncio.shield(execute(CLEANUP, cleanup=True))
            report['restoration_verified'] = restored == {'restored': True, 'pending': 0}
            report['passed'] &= report['restoration_verified']
        except Exception as error:
            report.update(passed=False, cleanup_exception_type=type(error).__name__)
        report['calls'] = calls
    return report


async def main():
    root = Path(__file__).resolve().parents[1]
    token = next(line.partition('=')[2].strip() for line in (root / '.env.mcp').read_text().splitlines()
                 if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization': 'Bearer ' + token})
    async with Client(transport, timeout=20, init_timeout=10) as client:
        catalog = await client.list_tools()
        guide = next(t for t in catalog if t.name == 'get_writing_guidance')
        report = {'catalog_bytes': size([t.model_dump(mode='json') for t in catalog]), 'tools': len(catalog),
            'guide_schema_bytes': size(guide.model_dump(mode='json')), 'discovery_calls': 1}
        report.update(await verify(client))
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
