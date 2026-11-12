"""Read-only source-resolution probe in the existing localhost test-world GM.

At most two tool calls/60 seconds. No fixtures, bytes fetched or game mutations.
Prints booleans/fixed error categories only. Run after offline checks and refresh.
Also verifies a real private source fetch/copy/release through the03a service.
"""
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

CODE = """
if(location.origin!=='http://localhost:30000'||!game.ready||!game.user.isGM||game.world.id!=='test'||game.version!=='14.369')throw Error('Wrong development runtime');
const {resolvePreviewSource}=await import(foundry.utils.getRoute('modules/foundry-mcp/scripts/journalImages.js'));
const image={source:'public',directory:'icons/svg',src:'icons/svg/anchor.svg'};
const rows={};
for(const [name,args] of [['canonical',{image}],['bare',{src:image.src}],['absolute',{src:location.origin+foundry.utils.getRoute(image.src)+'?v=1'}]]){
  try{const result=await resolvePreviewSource(args);rows[name]={passed:result.image.src===image.src&&result.credentials==='same-origin'&&result.world_id==='test'&&result.user_id===game.user.id};}
  catch(error){const code=error.rpcError?.code;rows[name]={passed:false,error_code:['BrowseFailed','ImageNotFound','InvalidRequest','ContextChanged','UnsupportedSource','AmbiguousSource'].includes(code)?code:'ProbeFailed'};}
}
const {previewSourceFetch}=await import(foundry.utils.getRoute('modules/foundry-mcp/scripts/imagePreviewFetch.js'));
let lease;
try{
  lease=await previewSourceFetch.begin({image});
  const first=await lease.read(0,Math.min(lease.size_bytes,32768)), original=first[0];
  first[0]^=255;
  const second=await lease.read(0,1);
  rows.fetch={passed:lease.size_bytes>0&&lease.size_bytes<=134217728&&second[0]===original};
}catch(error){const code=error.rpcError?.code;rows.fetch={passed:false,error_code:['ImageUnavailable','ImageTooLarge','ImageReadTimeout','IncompleteTransfer','TransferTimeout'].includes(code)?code:'ProbeFailed'};}
finally{lease?.release();}
rows.fetch.passed=rows.fetch.passed&&!previewSourceFetch.busy;
return JSON.stringify({version:game.version,rows});
"""


async def verify(client):
    result = await client.call_tool('execute_javascript', {'code': CODE})
    data = json.loads(result.structured_content['value'])
    # Reconstruct only allowlisted fields: never print the returned blob/raw errors.
    rows = {name: {'passed': data['rows'][name]['passed'] is True,
        **({'error_code': data['rows'][name]['error_code']} if data['rows'][name].get('error_code') in
            ('BrowseFailed','ImageNotFound','InvalidRequest','ContextChanged','UnsupportedSource','AmbiguousSource','ProbeFailed',
             'ImageUnavailable','ImageTooLarge','ImageReadTimeout','IncompleteTransfer','TransferTimeout') else {})}
        for name in ('canonical','bare','absolute','fetch')}
    return {'passed': all(row['passed'] for row in rows.values()), 'calls': 1, 'rows': rows}


async def main():
    root = Path(__file__).resolve().parents[1]
    token = next(line.partition('=')[2].strip() for line in (root / '.env.mcp').read_text().splitlines()
        if line.partition('=')[0].strip() == 'FOUNDRY_MCP_CALLER_TOKEN')
    try:
        async with asyncio.timeout(60), Client(StreamableHttpTransport('http://127.0.0.1:8000/mcp/mcp',
                headers={'Authorization': 'Bearer '+token}), timeout=30, init_timeout=10) as client:
            report = await verify(client)
    except Exception as error:
        report = {'passed': False, 'exception_type': type(error).__name__}
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
