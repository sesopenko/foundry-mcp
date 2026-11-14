"""Bounded test-only real JS dispatch/RPC/MCP/decoder/HTTP composition.

Only Foundry documents/FilePicker/fetch and the physical WebSocket transport are
fixtures. No game instance/network/assets are used. Reusable by12b measurements.
"""
import asyncio
import base64
from contextlib import AsyncExitStack,asynccontextmanager
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import httpx2 as httpx

from foundry_mcp_server import main
from foundry_mcp_server.auth.principal import current_principal
from foundry_mcp_server.config import Settings
from foundry_mcp_server.image_preview_runtime import PreviewRuntime
from foundry_mcp_server.image_preview_source_runtime import SourceRuntime
from foundry_mcp_server.image_preview_sources import SourceSnapshots
from foundry_mcp_server.image_preview_store import PreviewStore
from foundry_mcp_server.mcp_server import tools as registry,image_previews
from foundry_mcp_server.ws.connection import FoundryConnectionManager

ROOT=Path(__file__).resolve().parents[1]


def compact(value):
    return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())


class NodeSocket:
    """Physical socket replacement; production Python correlation stays intact."""
    async def start(self,manager):
        self.manager=manager
        self.closed=False
        self.process=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/js/fixtures/image-preview-workflow.js'),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,limit=65536)
        await manager.register('gm',self)
        self.reader=asyncio.create_task(self.receive())
        return self

    async def send_text(self,text):
        self.process.stdin.write(text.encode()+b'\n')
        await self.process.stdin.drain()

    async def receive(self):
        try:
            while line:=await self.process.stdout.readline():
                await self.manager.handle_incoming(line.decode(),self)
        finally:
            # Mirror the production WebSocket endpoint's finally callback.
            # EOF must fail this socket's pending RPCs, not wait for timeouts.
            await self.manager.unregister('gm',self)

    async def close(self):
        if self.closed:return
        self.closed=True
        await self.manager.unregister('gm',self)
        self.process.stdin.close()
        await self.process.stdin.wait_closed()
        try:await asyncio.wait_for(self.process.wait(),5)
        except TimeoutError:
            self.process.kill()
            await self.process.wait()
        await self.reader


class Workflow:
    """Enforce40 actual MCP requests/600s; retain only aggregate measurements."""
    def __init__(self,client,manager,source,delivery,clock):
        self.client,self.manager,self.source,self.delivery,self.clock=client,manager,source,delivery,clock
        self.calls=self.http_reads=0
        self.started=time.monotonic()
        self.rows={}

    async def request(self,method,params):
        if self.calls>=40 or time.monotonic()-self.started>=600:raise RuntimeError('WorkflowBudgetExceeded')
        self.calls+=1
        async with asyncio.timeout_at(self.started+600):
            response=await self.client.post('/mcp/mcp',headers={'Authorization':'Basic Z206cGFzc3dvcmQ=',
                'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2026-07-28','MCP-Method':method,
                **({'MCP-Name':params['name']} if method=='tools/call' else {})},
                json={'jsonrpc':'2.0','id':self.calls,'method':method,'params':{**params,'_meta':{
                    'io.modelcontextprotocol/protocolVersion':'2026-07-28',
                    'io.modelcontextprotocol/clientCapabilities':{}}}})
        if response.status_code!=200:raise RuntimeError('WorkflowHTTPFailure')
        return response.json()['result']

    async def discovery(self):
        result=await self.request('tools/list',{})
        return {'tools':len(result['tools']),'json_bytes':compact(result['tools']),
            'names':{t['name'] for t in result['tools']}}

    async def call(self,name,args,*,error=False,label=None):
        result=await self.request('tools/call',{'name':name,'arguments':args})
        data=result.get('structuredContent')
        row=self.rows.setdefault(label or name,dict(calls=0,json_bytes=0,mcp_bytes=0,errors=0,complete=False))
        row['calls']+=1
        row['json_bytes']+=compact(data) if data is not None else 0
        row['mcp_bytes']+=compact(result)
        row['errors']+=bool(result.get('isError'))
        row['complete']=not result.get('isError') and isinstance(data,dict) and data.get('complete',True) and not data.get('next_cursor')
        if error:return result
        if result.get('isError') or not isinstance(data,dict):raise RuntimeError('WorkflowToolFailure')
        return data

    async def read_src(self):
        args={'page_uuid':'JournalEntry.fixture.JournalEntryPage.page','max_chars':32}
        pieces=[]
        while True:
            page=await self.call('read_journal_page',args)
            pieces.append(page['content'])
            if page['complete']:break
            args={**args,'cursor':page['next_cursor']}
        class Images(HTMLParser):
            def __init__(self):super().__init__();self.sources=[]
            def handle_starttag(self,tag,attrs):
                if tag=='img':self.sources.extend(v for k,v in attrs if k=='src')
        parser=Images()
        parser.feed(''.join(pieces))
        if len(parser.sources)!=1:raise RuntimeError('IncompleteFixtureImageTag')
        return parser.sources[0],len(pieces)

    async def fetch(self,url):
        self.http_reads+=1
        if self.http_reads>40:raise RuntimeError('WorkflowReadBudgetExceeded')
        response=await self.client.get(url)
        if response.status_code!=200:raise RuntimeError('WorkflowPixelReadFailure')
        return response.content

    async def stats(self):return await self.manager.call('gm','fixture.stats',{},timeout=5)
    async def change(self,**changes):return await self.manager.call('gm','fixture.change',changes,timeout=5)
    def report(self):return dict(calls=self.calls,http_reads=self.http_reads,rows=self.rows)


@asynccontextmanager
async def workflow(data,*,image=None,prefix='',clock=None):
    image=image or dict(source='data',directory='assets/%CE%B1%20maps',src='assets/%CE%B1%20maps/opaque%20file.png')
    manager=FoundryConnectionManager()
    socket=await NodeSocket().start(manager)
    try:
        html='<p>'+('x'*29)+'</p><img src="'+image['src']+'"><p>end</p>'
        await manager.call('gm','fixture.init',{'image':image,'html':html,'prefix':prefix,
            'data_base64':base64.b64encode(data).decode(),'reverse_replies':True},timeout=5)
        with tempfile.TemporaryDirectory(prefix='preview-workflow-') as directory:
            config=Settings(auth_mode='basic',basic_username='gm',basic_password='password',bridge_token='browser',
                image_preview_origin='https://previews.example.com',image_preview_data_dir=directory,image_preview_jpeg=False)
            clock=clock if clock is not None else [1000.0]
            source=SourceRuntime(factory=lambda:SourceSnapshots(principal=lambda:current_principal(config),clock=lambda:clock[0]))
            delivery=PreviewRuntime(store_factory=lambda path:PreviewStore(path,clock=lambda:clock[0]))
            async with AsyncExitStack() as stack:
                for target,name,value in ((main,'settings',config),(image_previews,'settings',config),(registry,'_foundry_manager',manager),
                        (main,'source_runtime',source),(image_previews,'source_runtime',source),
                        (main,'preview_runtime',delivery),(image_previews,'preview_runtime',delivery)):
                    stack.enter_context(patch.object(target,name,value))
                await stack.enter_async_context(main.app.router.lifespan_context(main.app))
                client=await stack.enter_async_context(httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app,
                    client=('127.0.0.1',1234)),base_url='https://previews.example.com'))
                yield Workflow(client,manager,source,delivery,clock)
    finally:
        await socket.close()
