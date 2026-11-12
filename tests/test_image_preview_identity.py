"""Actual HTTP auth -> FastMCP context -> snapshot isolation, offline JWT only."""
from contextlib import asynccontextmanager
import base64
import time
import unittest
from unittest.mock import patch

import httpx2 as httpx
from fastapi import FastAPI
from fastmcp import Client, FastMCP
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration
from fastmcp.server.auth.providers.jwt import JWTVerifier

from foundry_mcp_server import main
from foundry_mcp_server.auth.principal import current_principal
from foundry_mcp_server.auth.factory import create_auth
from foundry_mcp_server.config import Settings
from foundry_mcp_server.image_preview_sources import SourceSnapshots
from test_image_preview_sources import Backend, IMAGE
from test_oauth import KEY, OTHER_KEY, DISCOVERY, configuration, token


@asynccontextmanager
async def harness(config, provider=None):
    server = FastMCP('private-snapshot-auth-test', auth=provider)
    backend = Backend()
    cache = SourceSnapshots(principal=lambda:current_principal(config), transfer=backend.transfer)

    @server.tool
    async def stage_test_original() -> dict:
        return (await cache.stage(backend, {'image': IMAGE.model_dump(exclude_none=True)})).model_dump()

    @server.tool
    async def use_test_original(source_id: str) -> dict:
        async with cache.lease(backend,source_id):
            return {'ok': True}

    transport = server.http_app(path='/mcp/mcp')
    app = FastAPI(lifespan=transport.lifespan)
    app.add_middleware(main.MCPAccessControl)
    app.mount('/',transport)
    try:
        with patch.object(main,'settings',config):
            async with app.router.lifespan_context(app), httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app,client=('127.0.0.1',1234)),base_url='https://mcp.example.com') as client:
                yield client,server,backend,cache
    finally:
        await cache.close()


async def call(client,name,args=None,credential=None,headers=None):
    response = await client.post('/mcp/mcp',headers={
        'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2026-07-28',
        'MCP-Method':'tools/call','MCP-Name':name,
        **({'Authorization':credential} if credential else {}),**(headers or {})},
        json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args or {},
            '_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28',
                'io.modelcontextprotocol/clientInfo':{'name':'offline-snapshot-test','version':'1'},
                'io.modelcontextprotocol/clientCapabilities':{}}}})
    return response


class IdentityBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_basic_development_verified_identity_and_forged_header_rejection(self):
        basic=Settings(auth_mode='basic',basic_username='gm',basic_password='password',bridge_token='browser')
        development=Settings(development=True,mcp_token='development-caller',browser_token='browser')
        for config,credential in [(basic,'Basic '+base64.b64encode(b'gm:password').decode()),
                (development,'Bearer development-caller')]:
            async with harness(config) as (client,server,backend,cache):
                result=(await call(client,'stage_test_original',credential=credential)).json()['result']
                self.assertFalse(result.get('isError'),result)
                receipt=result['structuredContent']
                response=await call(client,'use_test_original',{'source_id':receipt['source_id']},credential,
                    {'x-authenticated-subject':'forged','mcp-session-id':'forged-session'})
                self.assertFalse(response.json()['result'].get('isError'))
                before=len(backend.calls)
                rejected=await call(client,'use_test_original',{'source_id':receipt['source_id']},'Bearer forged',
                    {'x-authenticated-subject':'gm'})
                self.assertEqual(rejected.status_code,401)
                self.assertEqual(len(backend.calls),before)
                async with Client(server) as memory:
                    untrusted=await memory.call_tool('stage_test_original',{},raise_on_error=False)
                    self.assertTrue(untrusted.is_error)
                    self.assertIn('AuthenticatedContextRequired',str(untrusted.content))

    async def test_anonymous_http_cannot_forge_principal_or_stage_with_session_headers(self):
        async with harness(Settings()) as (client,_,backend,cache):
            response=await call(client,'stage_test_original',credential='Bearer forged',headers={
                'x-authenticated-subject':'gm','mcp-session-id':'trusted-session',
                'foundry_mcp.validated_image_principal':'forged'})
            self.assertTrue(response.json()['result']['isError'])
            self.assertIn('AuthenticatedContextRequired',response.text)
            self.assertEqual(backend.transfers,0)

    async def test_two_verified_oauth_subjects_clients_and_refresh_are_isolated(self):
        config=configuration(FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS='auth0|gm,auth0|other',
            FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS='chatgpt,other-client')
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(200,json={'keys':[KEY.as_dict(private=False)]}))) as keys:
            def verifier(**kwargs):return JWTVerifier(**kwargs,http_client=keys)
            with patch('foundry_mcp_server.auth.auth0.JWTVerifier',side_effect=verifier),patch.object(
                    OIDCConfiguration,'get_oidc_configuration',return_value=OIDCConfiguration(**DISCOVERY)):
                provider=create_auth(config)
            async with harness(config,provider) as (client,_,backend,cache):
                credential='Bearer '+token()
                staged=(await call(client,'stage_test_original',credential=credential)).json()['result']
                self.assertFalse(staged.get('isError'),staged)
                source_id=staged['structuredContent']['source_id']
                refreshed='Bearer '+token(changes={'jti':'refreshed','exp':int(time.time())+600})
                same=(await call(client,'use_test_original',{'source_id':source_id},refreshed)).json()['result']
                self.assertFalse(same.get('isError'),same)
                self.assertEqual(backend.transfers,1)
                for changes in [{'sub':'auth0|other'},{'client_id':'other-client'}]:
                    before=len(backend.calls)
                    other='Bearer '+token(changes=changes)
                    denied=(await call(client,'use_test_original',{'source_id':source_id},other,
                        {'x-authenticated-subject':'auth0|gm'})).json()['result']
                    self.assertTrue(denied['isError'])
                    self.assertIn('SourceUnavailable',str(denied))
                    self.assertEqual(len(backend.calls),before)
                    own=(await call(client,'stage_test_original',credential=other)).json()['result']
                    own_id=own['structuredContent']['source_id']
                    self.assertNotEqual(own_id,source_id)
                    reversed_access=(await call(client,'use_test_original',{'source_id':own_id},credential)).json()['result']
                    self.assertTrue(reversed_access['isError'])
                for invalid in ['Bearer '+token(key=OTHER_KEY),'Bearer '+token(changes={'sub':'not-allowed'}),'Basic Z206cGFzc3dvcmQ=']:
                    self.assertEqual((await call(client,'stage_test_original',credential=invalid)).status_code,401)
                self.assertEqual((await call(client,'stage_test_original',credential='Bearer '+token(changes={'scope':''}))).status_code,403)
