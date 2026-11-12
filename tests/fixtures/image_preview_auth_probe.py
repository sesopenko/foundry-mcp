"""Bounded fresh production-app authentication probe; never prints capabilities."""
import asyncio
from io import BytesIO
import json
import os
import re
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,os.getcwd())
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import httpx2 as httpx
from PIL import Image
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration
from fastmcp.server.auth.providers.jwt import JWTVerifier
from test_oauth import KEY,OTHER_KEY,DISCOVERY,token


async def probe(mode):
    calls = 0
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
            httpx.Response(200,json={'keys':[KEY.as_dict(private=False)]}))) as keys:
        def verifier(**kwargs):return JWTVerifier(**kwargs,http_client=keys)
        with patch.object(OIDCConfiguration,'get_oidc_configuration',return_value=OIDCConfiguration(**DISCOVERY)), \
                patch('foundry_mcp_server.auth.auth0.JWTVerifier',side_effect=verifier):
            from foundry_mcp_server import main
        from foundry_mcp_server.image_preview_failure import PreviewFailure
        if mode=='oauth':good = 'Bearer '+token()
        elif mode=='basic':good = 'Basic dXNlcjpwYXNz'
        elif mode=='development':good = 'Bearer development-caller'
        else:good = None
        async with main.app.router.lifespan_context(main.app),httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app,client=('127.0.0.1',1234)),base_url='https://mcp.example.com') as client:
            stream = BytesIO()
            Image.new('RGB',(17,11),(20,40,60)).save(stream,format='PNG')
            if mode=='none':
                try:await main.preview_runtime.publish(stream.getvalue(),'image/png')
                except PreviewFailure as failure:assert failure.code=='PreviewNotConfigured','AnonymousIssuanceCategory'
                else:raise AssertionError('AnonymousIssuanceAccepted')
                receipt = main.preview_runtime.store.publish(stream.getvalue(),'image/png')
            else:receipt = await main.preview_runtime.publish(stream.getvalue(),'image/png')
            path = f'/image-previews/{receipt.token}.png'
            for variant in (path,path+'?probe=1'):
                response = await client.get(variant)
                calls += 1
                assert response.status_code==200 and response.content==stream.getvalue(),'AnonymousReadFailed'
                assert 'set-cookie' not in response.headers and 'location' not in response.headers,'UnexpectedReaderHeaders'
            assert not main.foundry_manager.websockets,'UnexpectedGMFixture'
            async def call(credential=None,*,name='get_bridge_versions',duplicate=False,method='tools/call',arguments=None):
                nonlocal calls
                calls += 1
                headers = [('Accept','application/json, text/event-stream'),('MCP-Protocol-Version','2026-07-28'),
                    ('MCP-Method',method)]
                if method=='tools/call':headers.append(('MCP-Name',name))
                if credential:
                    headers.append(('Authorization',credential))
                    if duplicate:headers.append(('Authorization',credential))
                return await client.post('/mcp/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':method,
                    'params':{**({'name':name,'arguments':arguments or {}} if method=='tools/call' else {}),'_meta':{
                        'io.modelcontextprotocol/protocolVersion':'2026-07-28',
                        'io.modelcontextprotocol/clientCapabilities':{}}}})
            if good:
                for credential in (None,'Bearer forged',path):
                    response = await call(credential)
                    assert response.status_code==401,'InvalidMCPCredentialsAccepted'
                assert (await call(good,duplicate=True)).status_code==401,'DuplicateCredentialsAccepted'
                assert (await call(name='list_pdf_documents')).status_code==401,'AnonymousPDFReadAccepted'
            response = await call(good)
            assert response.status_code==200 and not response.json()['result'].get('isError'),'AuthorizedMCPFailed'
            if mode=='oauth':
                for invalid,status in (('Bearer '+token(key=OTHER_KEY),401),
                        ('Bearer '+token(changes={'sub':'not-allowed'}),401),
                        ('Bearer '+token(changes={'scope':''}),403),('Basic dXNlcjpwYXNz',401)):
                    assert (await call(invalid)).status_code==status,'OAuthPolicyDrift'
            if good:
                # Actual production WebSocket route; capability ownership cannot
                # substitute for the separate bridge credential.
                messages = iter([{'type':'websocket.connect'},{'type':'websocket.receive',
                    'text':json.dumps({'type':'auth','token':path})}])
                sent = []
                async def receive():return next(messages)
                async def send(message):sent.append(message)
                await main.app({'type':'websocket','asgi':{'version':'3.0'},'scheme':'wss','path':'/ws/foundry',
                    'raw_path':b'/ws/foundry','root_path':'','query_string':b'','headers':[],
                    'client':('127.0.0.1',1234),'server':('mcp.example.com',443),'subprotocols':[]},receive,send)
                assert sent[-1].get('code')==1008,'CapabilityAcceptedAsBridgeCredential'
                assert not main.foundry_manager.websockets,'UnauthorizedBridgeRegistered'
            before = main.preview_runtime.origin
            main.preview_runtime.issuance_enabled = False
            try:main.preview_runtime.require_issuance()
            except PreviewFailure as failure:assert failure.code=='PreviewNotConfigured','DisabledIssuanceCategory'
            else:raise AssertionError('DisabledIssuanceAccepted')
            assert before=='https://previews.example.com','UntrustedOriginSelected'
            disabled = await call(good,name='get_foundry_image_url',arguments={'request':{'src':'icons/svg/anchor.svg'}})
            assert disabled.status_code==200 and disabled.json()['result'].get('isError'),'DisabledURLToolAccepted'
            assert 'PreviewNotConfigured:' in disabled.text,'DisabledURLToolCategory'
            discovery = await call(good,method='tools/list')
            assert discovery.status_code==200,'DisabledIssuanceLostDiscovery'
            catalog = discovery.json()['result']['tools']
            assert len(catalog)>=40 and any(t['name']=='get_foundry_image_url' for t in catalog),'MissingPreviewToolRegistration'
            catalog_bytes = len(json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode())
    return {'mode':mode,'calls':calls,'complete':True,'anonymous_read':True,'issuance':mode!='none',
        'catalog_tools':len(catalog),'catalog_bytes':catalog_bytes}


if __name__=='__main__':
    try:
        result = asyncio.run(asyncio.wait_for(probe(sys.argv[1]),20))
    except Exception as failure:
        def reason(error):
            if isinstance(error,BaseExceptionGroup):return [reason(e) for e in error.exceptions[:4]]
            if isinstance(error,AssertionError) and re.fullmatch(r'[A-Za-z0-9_]{1,80}',str(error)):return str(error)
            return type(error).__name__
        print(json.dumps({'error':reason(failure)}))
        raise SystemExit(1)
    print(json.dumps(result))
