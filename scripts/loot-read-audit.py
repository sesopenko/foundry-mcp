"""Bounded loot MCP payload audit; prints aggregates, never game data/secrets.

--catalog-only reads the existing localhost catalog (one discovery, no RPC).
Default uses inert source fixtures through actual in-memory FastMCP validation:
at most 100 calls and 180 seconds. No browser or document mutation is performed.
JSON bytes are not billed tokens. Synthetic results are not live verification.
"""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode())


def catalog_summary(catalog):
    tools = {t.name:t for t in catalog}
    for name in ('read_actor','read_item','list_actor_items','get_actor_types'):
        assert tools[name].output_schema is not None and 'loot' in tools[name].description.lower()
        assert tools[name].annotations.read_only_hint
    assert 'loot' in json.dumps(tools['search_actors'].input_schema)
    assert 'loot' in json.dumps(tools['list_scene_actors'].input_schema)
    assert 'loot' not in json.dumps(tools['search_compendium_actors'].input_schema)
    selected = {'read_actor', 'read_item', 'list_actor_items', 'get_actor_types',
                'get_actor_tree', 'search_actors', 'list_scene_actors', 'search_compendium_actors'}
    return dict(tools=len(catalog), bytes=size([t.model_dump(mode='json') for t in catalog]),
                affected_bytes={t.name:size(t.model_dump(mode='json')) for t in catalog if t.name in selected})


SCRIPT = r"""
import {lootFixture} from './tests/js/helpers/loot-fixture.js';
import {readActorSelected,readItemSelected,listActorItems} from './foundry-module/scripts/actors.js';
const f=lootFixture(),cases=[];
// Heavy collection: independent stacks, nested containment and Unicode prose.
// Keep definitions/description expansion independently bounded.
for(let i=0;i<45;i++)f.add(f.base,'stack'+i,'equipment',{quantity:i,containerId:'bag',description:{value:'<p>Stored item detail 😀.</p>'.repeat(50)}});
const add=async(label,tool,args,handler)=>{
 if(cases.length>=100)throw Error('Call cap');
 const packet=await handler(args);cases.push({label,tool,args,packet});return packet.result??packet;
};
await add('identity','read_actor',{actor_uuid:f.base.uuid,select:{details:[]},limit:10,max_bytes:8000},readActorSelected);
await add('summary_first','read_actor',{actor_uuid:f.base.uuid,select:{details:['inventory.summary']},limit:10,max_bytes:8000},readActorSelected);
await add('selected_item','read_actor',{actor_uuid:f.base.uuid,select:{details:['inventory.summary'],item_uuids:[f.base.items.get('coins').uuid]},limit:10,max_bytes:8000},readActorSelected);
await add('full_inventory_first','read_actor',{actor_uuid:f.base.uuid,select:{details:['inventory']},limit:10,max_bytes:48000},readActorSelected);
await add('evidence','read_actor',{actor_uuid:f.base.uuid,select:{details:['inventory.summary'],item_uuids:[f.base.items.get('coins').uuid],evidence:true},limit:10,max_bytes:48000},readActorSelected);
await add('item_properties','read_item',{item_uuid:f.base.items.get('coins').uuid,select:{details:['source.physical']},limit:10,max_bytes:8000},readItemSelected);
for(const [label,tool,args,handler] of [
 ['summary_traversal','read_actor',{actor_uuid:f.base.uuid,select:{details:['inventory.summary']},limit:10,max_bytes:8000},readActorSelected],
 ['items_traversal','list_actor_items',{actor_uuid:f.base.uuid,select:{context:false,relationships:false,follow_up:true,limitations:false},limit:10,max_bytes:8000},listActorItems],
 ['description_traversal','read_item',{item_uuid:f.base.items.get('stack0').uuid,select:{details:['description']},limit:1,max_bytes:8000},readItemSelected]
]){
 let cursor;
 do{const page=await add(label,tool,{...args,...(cursor?{cursor}:{})},handler);cursor=page.pagination.next_cursor;}while(cursor);
}
console.log(JSON.stringify(cases));
"""


async def audit(catalog_only=False):
    async with asyncio.timeout(180):
        if catalog_only:
            token = next(line.partition('=')[2].strip() for line in (ROOT / '.env.mcp').read_text().splitlines()
                         if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
            transport = StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp', headers={'Authorization':'Bearer '+token})
            async with Client(transport, timeout=30, init_timeout=10) as client:
                return dict(catalog=catalog_summary(await client.list_tools()), tool_calls=0, live_runtime_verified=False)
        from foundry_mcp_server.mcp_server.server import mcp
        from foundry_mcp_server.mcp_server.tools import register_foundry_manager
        process = subprocess.run(['node', '--input-type=module'], input=SCRIPT, capture_output=True,
                                 text=True, cwd=ROOT, timeout=30, check=True)
        cases = json.loads(process.stdout)
        assert len(cases) <= 100
        manager = AsyncMock()
        register_foundry_manager(manager)
        rows = {}
        traversals = {'summary_traversal':set(),'items_traversal':set()}
        fragments = []
        async with Client(mcp) as client:
            catalog = catalog_summary(await client.list_tools())
            for case in cases:
                manager.call.return_value = case['packet']
                result = (await client.call_tool(case['tool'],case['args'])).structured_content
                row = rows.setdefault(case['label'],dict(calls=0,bytes=0,entries=0,complete=False))
                row['calls'] += 1
                row['bytes'] += size(result)
                row['entries'] += len(result.get('entries',result.get('nodes',[])))
                row['complete'] = result['pagination']['complete']
                assert size(result) <= case['args']['max_bytes']
                if case['label'] in traversals:
                    keys = [e['key'] for e in result['entries']] if 'entries' in result else [n['identity']['uuid'] for n in result['nodes']]
                    seen = traversals[case['label']]
                    assert not seen.intersection(keys)
                    seen.update(keys)
                if case['label']=='description_traversal':
                    for entry in result['entries']:
                        fragments.extend((v['text']['start'],v['text']['end'],v['value']) for v in entry['values'] if 'text' in v)
        assert rows['summary_traversal']['entries'] == rows['items_traversal']['entries'] == 47
        assert all(len(seen)==47 for seen in traversals.values())
        fragments.sort()
        assert fragments[0][0]==0 and all(a[1]==b[0] for a,b in zip(fragments,fragments[1:]))
        assert ''.join(text for _,_,text in fragments)=='<p>Stored item detail 😀.</p>'*50
        assert all(rows[name]['complete'] for name in ('summary_traversal','items_traversal','description_traversal'))
        return dict(catalog=catalog,tool_calls=len(cases),scenarios=rows,live_runtime_verified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-only',action='store_true')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(audit(args.catalog_only)),sort_keys=True))
