"""Offline Auth0 boundary tests: no tenant, credentials or game required."""
import os
import asyncio
import json
import time
import unittest
from unittest.mock import AsyncMock, patch

import httpx2 as httpx
from fastapi import FastAPI, WebSocketDisconnect
from fastmcp import FastMCP
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration
from fastmcp.server.auth.providers.jwt import JWTVerifier
from joserfc import jwk, jwt

from foundry_mcp_server.auth.factory import create_auth
from foundry_mcp_server.auth.policy import GMTokenVerifier
from foundry_mcp_server.auth.metadata import OAuthToolMetadata

from foundry_mcp_server.config import Settings

ENV = {
    'FOUNDRY_MCP_AUTH_MODE': 'oauth',
    'FOUNDRY_MCP_OAUTH_PROVIDER': 'auth0',
    'FOUNDRY_MCP_PUBLIC_URL': 'https://mcp.example.com',
    'FOUNDRY_MCP_OAUTH_ISSUER': 'https://tenant.auth0.com/',
    'FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS': 'auth0|gm',
    'FOUNDRY_MCP_OAUTH_ALLOWED_CLIENT_IDS': 'chatgpt',
    'FOUNDRY_MCP_BRIDGE_TOKEN': 'separate-browser-secret',
}


def configuration(**overrides):
    with patch.dict(os.environ, {**ENV, **overrides}, clear=True):
        return Settings.from_env()


class OAuthConfigurationTests(unittest.TestCase):
    def test_valid(self):
        settings = configuration()
        self.assertEqual(settings.resource_url, 'https://mcp.example.com/mcp/mcp')
        self.assertEqual(settings.oauth_allowed_subjects, ('auth0|gm',))
        self.assertTrue(settings.production_auth)

    def test_missing_conflicting_and_malformed(self):
        cases = [{key: ''} for key in ENV]
        cases += [{'FOUNDRY_MCP_AUTH_MODE': value} for value in ('both', 'basic,oauth', 'basic', 'none')]
        cases += [{key: 'retained-secret'} for key in ('FOUNDRY_MCP_BASIC_USERNAME', 'FOUNDRY_MCP_BASIC_PASSWORD')]
        cases += [{'FOUNDRY_MCP_DEV_EXECUTION': 'true'}, {'FOUNDRY_MCP_OAUTH_PROVIDER': 'other'}]
        cases += [{'FOUNDRY_MCP_PUBLIC_URL': value} for value in (
            'http://mcp.example.com', 'https://user:pass@mcp.example.com',
            'https://mcp.example.com/', 'https://mcp.example.com/prefix',
            'https://mcp.example.com?x', 'https://mcp.example.com#x',
            'https://mcp.example.com:bad', 'https://mcp.example.com\\bad',
            'https://MCP.example.com', 'https://mcp.example.com:443',
        )]
        cases += [{'FOUNDRY_MCP_OAUTH_ISSUER': value} for value in (
            'https://tenant.auth0.com', 'http://tenant.auth0.com/',
            'https://tenant.auth0.com/path/', 'https://tenant.auth0.com/?x',
        )]
        cases += [{'FOUNDRY_MCP_OAUTH_ALLOWED_SUBJECTS': value} for value in (' ', ',', 'gm,,other')]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError) as error:
                configuration(**change)
            self.assertNotIn('retained-secret', str(error.exception))

    def test_non_oauth_rejects_oauth_environment(self):
        for mode in ('basic', 'none'):
            base = {'FOUNDRY_MCP_AUTH_MODE': mode}
            if mode == 'basic':
                base.update(FOUNDRY_MCP_BASIC_USERNAME='user', FOUNDRY_MCP_BASIC_PASSWORD='pass', FOUNDRY_MCP_BRIDGE_TOKEN='bridge')
            for key in [k for k in ENV if 'OAUTH_' in k] + ['FOUNDRY_MCP_PUBLIC_URL', 'FOUNDRY_MCP_OAUTH_UNKNOWN']:
                with self.subTest(mode=mode, key=key), patch.dict(os.environ, {**base, key: 'unexpected'}, clear=True):
                    with self.assertRaises(ValueError): Settings.from_env()


ISSUER = ENV['FOUNDRY_MCP_OAUTH_ISSUER']
RESOURCE = ENV['FOUNDRY_MCP_PUBLIC_URL'] + '/mcp/mcp'
DISCOVERY = dict(
    issuer=ISSUER, jwks_uri=ISSUER + '.well-known/jwks.json',
    authorization_endpoint=ISSUER + 'authorize', token_endpoint=ISSUER + 'oauth/token',
    response_types_supported=['code'], subject_types_supported=['public'],
    id_token_signing_alg_values_supported=['RS256'],
    code_challenge_methods_supported=['S256'],
    token_endpoint_auth_methods_supported=['client_secret_post'],
    scopes_supported=['openid', 'profile', 'email', 'offline_access'],
)
KEY = jwk.RSAKey.generate_key(2048, parameters={'kid': 'first'})
OTHER_KEY = jwk.RSAKey.generate_key(2048, parameters={'kid': 'second'})


def token(*, changes=None, omit=(), key=KEY, typ='at+jwt', algorithm='RS256'):
    claims = dict(iss=ISSUER, aud=RESOURCE, sub='auth0|gm', client_id='chatgpt',
                  exp=int(time.time()) + 300, iat=int(time.time()) - 1,
                  jti='test-token', scope='foundry:gm')
    claims.update(changes or {})
    for name in omit: claims.pop(name, None)
    return jwt.encode({'alg': algorithm, 'typ': typ, 'kid': key.kid}, claims, key, algorithms=[algorithm])


class TokenPolicyTests(unittest.IsolatedAsyncioTestCase):
    def verifier(self):
        return GMTokenVerifier(JWTVerifier(public_key=KEY.as_pem(private=False),
            issuer=ISSUER, audience=RESOURCE, algorithm='RS256'), ['auth0|gm'], ['chatgpt'])

    async def test_valid_and_denied_claims(self):
        verifier = self.verifier()
        accepted = await verifier.verify_token(token())
        self.assertEqual(accepted.scopes, ['foundry:gm'])
        bad = [token(key=OTHER_KEY), token(typ='JWT'), token(algorithm='RS512'), 'malformed']
        bad += [token(omit=[name]) for name in ('exp', 'iat', 'jti', 'sub', 'client_id', 'aud', 'iss')]
        bad += [token(changes={name: value}) for name, value in (
            ('iss', 'https://wrong.example/'), ('aud', 'wrong'), ('exp', 0),
            ('exp', 'later'), ('exp', True), ('exp', None), ('exp', float('inf')), ('nbf', time.time() + 600),
            ('nbf', 'later'), ('iat', time.time() + 600), ('sub', 'auth0|other'),
            ('sub', 'machine@clients'), ('client_id', 'other'), ('client_id', ''),
            ('gty', 'client-credentials'), ('scope', ['foundry:gm']),
        )]
        for value in bad:
            with self.subTest(case=bad.index(value)):
                self.assertIsNone(await verifier.verify_token(value))
        # Only actual granted scope is authoritative. Transport supplies 403.
        for claims in ({'scope': ''}, {'scope': '', 'permissions': ['foundry:gm']}, {'scope': '', 'scp': 'foundry:gm'}):
            self.assertEqual((await verifier.verify_token(token(changes=claims))).scopes, [])
        self.assertEqual((await verifier.verify_token(token(omit=['scope']))).scopes, [])

    async def test_jwks_cache_rotation_throttle_outage_and_malformed(self):
        requests = []
        payload = {'keys': [KEY.as_dict(private=False)]}
        failure = None
        def fetch(request):
            requests.append(request)
            if failure: raise failure
            return httpx.Response(200, json=payload)
        async with httpx.AsyncClient(transport=httpx.MockTransport(fetch)) as client:
            raw = JWTVerifier(jwks_uri=ISSUER + '.well-known/jwks.json', issuer=ISSUER,
                              audience=RESOURCE, algorithm='RS256', http_client=client)
            verifier = GMTokenVerifier(raw, ['auth0|gm'], ['chatgpt'])
            self.assertIsNotNone(await verifier.verify_token(token()))
            self.assertIsNotNone(await verifier.verify_token(token()))
            self.assertEqual(len(requests), 1)
            for _ in range(5): self.assertIsNone(await verifier.verify_token(token(key=OTHER_KEY)))
            self.assertEqual(len(requests), 1)
            payload = {'keys': [OTHER_KEY.as_dict(private=False)]}
            with patch('fastmcp.server.auth.providers.jwt.time.monotonic', return_value=time.monotonic() + 31):
                self.assertIsNotNone(await verifier.verify_token(token(key=OTHER_KEY)))
            self.assertEqual(len(requests), 2)
            failure = httpx.ReadTimeout('private diagnostic')
            with patch('fastmcp.server.auth.providers.jwt.time.monotonic', return_value=time.monotonic() + 4000):
                for _ in range(5): self.assertIsNone(await verifier.verify_token(token(key=OTHER_KEY)))
            self.assertEqual(len(requests), 3)
            failure = None
            for payload in ({'keys': []}, {'keys': [None, {}]}, [], {'keys': 'bad'}):
                # Fresh verifiers exercise malformed JWKS without waiting for TTL.
                malformed = GMTokenVerifier(JWTVerifier(jwks_uri=ISSUER + '.well-known/jwks.json',
                    issuer=ISSUER, audience=RESOURCE, algorithm='RS256', http_client=client), ['auth0|gm'], ['chatgpt'])
                self.assertIsNone(await malformed.verify_token(token()))


class OAuthHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from foundry_mcp_server import main
        self.main = main
        self.settings = configuration()
        self.setting_patch = patch.object(main, 'settings', self.settings)
        self.setting_patch.start()
        self.addCleanup(self.setting_patch.stop)
        self.keys = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={'keys': [KEY.as_dict(private=False)]})))
        self.addAsyncCleanup(self.keys.aclose)
        def verifier(**kwargs): return JWTVerifier(**kwargs, http_client=self.keys)
        with patch('foundry_mcp_server.auth.auth0.JWTVerifier', side_effect=verifier), patch.object(
            OIDCConfiguration, 'get_oidc_configuration', return_value=OIDCConfiguration(**DISCOVERY)):
            self.provider = create_auth(self.settings)
        self.server = FastMCP('oauth-boundary', auth=self.provider, dereference_schemas=False)
        self.server.add_middleware(OAuthToolMetadata())
        self.calls = 0
        @self.server.tool(annotations={'readOnlyHint': True, 'destructiveHint': False})
        async def diagnostic() -> dict:
            self.calls += 1
            return {'ok': True}
        self.transport = self.server.http_app(path='/mcp/mcp')
        self.app = FastAPI(lifespan=self.transport.lifespan)
        self.app.add_middleware(main.MCPAccessControl)
        self.app.add_api_websocket_route('/ws/foundry', main.foundry_ws)
        self.app.mount('/', self.transport)
        started, stopped = asyncio.Event(), asyncio.Event()
        async def lifespan():
            async with self.app.router.lifespan_context(self.app):
                started.set()
                await stopped.wait()
        self.life_task = asyncio.create_task(lifespan())
        await asyncio.wait_for(started.wait(), 5)
        async def close_lifespan():
            stopped.set()
            await self.life_task
        self.addAsyncCleanup(close_lifespan)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='https://mcp.example.com')
        self.addAsyncCleanup(self.client.aclose)

    async def request(self, method='tools/call', credential=None, headers=None):
        return await self.client.post('/mcp/mcp', headers={
            'Authorization': credential or 'Bearer ' + token(),
            'Accept': 'application/json, text/event-stream',
            'MCP-Method': method,
            **({'MCP-Name': 'diagnostic'} if method == 'tools/call' else {}),
            'MCP-Protocol-Version': '2026-07-28', **(headers or {}),
        }, json={'jsonrpc': '2.0', 'id': 1, 'method': method,
                 'params': {**({'name': 'diagnostic', 'arguments': {}} if method == 'tools/call' else {}),
                            '_meta': {'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                                      'io.modelcontextprotocol/clientInfo': {'name': 'offline', 'version': '1'},
                                      'io.modelcontextprotocol/clientCapabilities': {}}}})

    async def test_discovery_and_authorized_call(self):
        response = await self.client.get('/.well-known/oauth-protected-resource/mcp/mcp')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['resource'], RESOURCE)
        self.assertEqual(response.json()['authorization_servers'], [ISSUER])
        self.assertEqual(response.json()['scopes_supported'], ['foundry:gm'])
        response = await self.request('tools/list')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('securitySchemes', response.text)
        self.assertIn('foundry:gm', response.text)
        self.assertEqual((await self.request()).status_code, 200)
        self.assertEqual(self.calls, 1)

    async def test_invalid_credentials_and_scope_never_reach_tools(self):
        credentials = ['Basic dXNlcjpwYXNz', 'Basic !!!', 'Bearer malformed',
            'Bearer ' + token(key=OTHER_KEY), 'Bearer ' + token(typ='JWT'),
            'Bearer ' + token(changes={'sub': 'auth0|other'}),
            'Bearer ' + token(changes={'client_id': 'other'}),
            'Bearer ' + token(changes={'aud': 'other-api'}),
            'Bearer ' + token(omit=['exp'])]
        for credential in credentials:
            for method in ('initialize', 'tools/list', 'tools/call'):
                response = await self.request(method, credential)
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.headers['www-authenticate'].startswith('Bearer'))
                self.assertNotIn('Basic', response.headers['www-authenticate'])
        for changes in ({'scope': ''}, {'scope': '', 'permissions': ['foundry:gm']}):
            response = await self.request(credential='Bearer ' + token(changes=changes))
            self.assertEqual(response.status_code, 403)
            self.assertIn('insufficient_scope', response.text)
        self.assertEqual(self.calls, 0)

    async def test_every_method_duplicate_headers_sessions_and_challenge(self):
        for method in ('GET', 'POST', 'DELETE', 'OPTIONS'):
            for headers in ({}, {'mcp-session-id': 'old-basic-session'},
                [('Authorization', 'Bearer ' + token()), ('Authorization', 'Bearer ' + token())],
                {'Authorization': 'Bearer  ' + token()}):
                response = await self.client.request(method, '/mcp/mcp', headers=headers)
                self.assertEqual(response.status_code, 401)
                challenge = response.headers['www-authenticate']
                url = challenge.split('resource_metadata="')[1].split('"')[0]
                self.assertEqual((await self.client.get(url)).status_code, 200)
        self.assertEqual(self.calls, 0)

    async def test_browser_credential_independent(self):
        manager = AsyncMock()
        for credential in ('wrong', token(), ''):
            socket = AsyncMock()
            socket.receive_text.return_value = json.dumps({'type': 'auth', 'token': credential})
            with patch.object(self.main, 'foundry_manager', manager):
                await self.main.foundry_ws(socket)
            socket.close.assert_awaited_once_with(code=1008)
        manager.register.assert_not_awaited()
        socket = AsyncMock()
        socket.receive_text.side_effect = [json.dumps({'type': 'auth', 'token': self.settings.bridge_token}), WebSocketDisconnect()]
        with patch.object(self.main, 'foundry_manager', manager): await self.main.foundry_ws(socket)
        self.assertEqual(manager.register.call_args.kwargs['welcome']['status'], 'ok')

    async def test_existing_bridge_limits_and_admission_in_oauth(self):
        import test_production_auth as existing
        with patch.object(existing, 'AUTH', self.settings):
            for name in ('test_socket_rejections_never_register',
                         'test_timeout_disconnect_and_binary_frame',
                         'test_authenticated_socket_acknowledges_and_unregisters',
                         'test_ack_precedes_visibility_and_duplicate_cannot_displace_owner',
                         'test_failed_ack_does_not_register',
                         'test_concurrent_admission_has_one_winner_and_no_rpc_before_ack'):
                await getattr(existing.ProductionAuthTests, name)(self)

    async def test_token_policy_removal_and_mode_transition(self):
        self.assertEqual((await self.request()).status_code, 200)
        self.provider.token_verifier.subjects = frozenset()
        self.assertEqual((await self.request(headers={'mcp-session-id': 'old-session'})).status_code, 401)
        self.assertEqual(self.calls, 1)
        # Recreate an independent Basic stack; neither provider nor metadata is carried over.
        basic_server = FastMCP('basic-after-oauth')
        basic_transport = basic_server.http_app(path='/mcp/mcp')
        basic_app = FastAPI(lifespan=basic_transport.lifespan)
        basic_app.add_middleware(self.main.MCPAccessControl)
        basic_app.mount('/', basic_transport)
        basic = Settings(auth_mode='basic', basic_username='user', basic_password='pass', bridge_token='bridge')
        with patch.object(self.main, 'settings', basic):
            async with basic_app.router.lifespan_context(basic_app), httpx.AsyncClient(
                transport=httpx.ASGITransport(app=basic_app), base_url='https://mcp.example.com') as client:
                response = await client.post('/mcp/mcp', headers={'Authorization': 'Bearer ' + token(), 'mcp-session-id': 'old-oauth-session'})
                self.assertEqual(response.status_code, 401)
                self.assertTrue(response.headers['www-authenticate'].startswith('Basic'))
                self.assertEqual((await client.get('/.well-known/oauth-protected-resource/mcp/mcp')).status_code, 404)
                self.assertNotEqual((await client.get('/mcp/mcp', auth=('user', 'pass'))).status_code, 401)
        # Returning to the OAuth instance still rejects formerly working Basic.
        self.assertEqual((await self.request(credential='Basic dXNlcjpwYXNz')).status_code, 401)

    async def test_outage_and_secret_free_diagnostics(self):
        with patch.object(self.keys, 'get', side_effect=httpx.ReadTimeout('outage')):
            with self.assertLogs(level='INFO') as logs:
                for credential in ('Bearer ' + token(), 'Basic dXNlcjpwYXNz'):
                    self.assertEqual((await self.request(credential=credential)).status_code, 401)
        self.assertEqual(self.calls, 0)
        self.assertNotIn(token(), '\n'.join(logs.output))
        self.assertNotIn(self.settings.bridge_token, '\n'.join(logs.output))


class OAuthPDFTests(unittest.TestCase):
    def test_explicit_trust_and_separate_capability_still_required(self):
        from foundry_mcp_server.pdf import config
        env = {'FOUNDRY_MCP_PDF_ENABLED': 'true', 'FOUNDRY_MCP_PDF_TRUSTED_GM_MCP': 'true',
               'FOUNDRY_MCP_PDF_LIBRARY_DIR': '/tmp/oauth-books', 'FOUNDRY_MCP_PDF_INDEX_DIR': '/tmp/oauth-index',
               'FOUNDRY_MCP_PDF_UPLOAD_ENABLED': 'true', 'FOUNDRY_MCP_PDF_UPLOAD_TOKEN': 'upload-only'}
        with patch.object(config, 'settings', configuration()):
            with patch.dict(os.environ, env, clear=True):
                value = config.PDFConfig.from_env()
                self.assertTrue(value.enabled)
                self.assertFalse(value.proxy_tls)
            for change in ({'FOUNDRY_MCP_PDF_TRUSTED_GM_MCP': 'false'},
                           {'FOUNDRY_MCP_PDF_UPLOAD_TOKEN': ''},
                           {'FOUNDRY_MCP_PDF_UPLOAD_TOKEN': ENV['FOUNDRY_MCP_BRIDGE_TOKEN']}):
                with patch.dict(os.environ, {**env, **change}, clear=True), self.assertRaises(ValueError):
                    config.PDFConfig.from_env()


class ProviderTests(unittest.TestCase):
    def test_actual_discovery_fetch_and_malformed_response(self):
        issuer = 'https://discovery.auth0.com/'
        settings = configuration(FOUNDRY_MCP_OAUTH_ISSUER=issuer)
        metadata = {key: value.replace(ISSUER, issuer) if isinstance(value, str) else value
                    for key, value in DISCOVERY.items()}
        url = issuer + '.well-known/openid-configuration'
        with patch('httpx2.get', return_value=httpx.Response(200, json=metadata, request=httpx.Request('GET', url))) as fetch:
            provider = create_auth(settings)
            self.assertEqual(provider.token_verifier.verifier.audience, RESOURCE)
            fetch.assert_called_once_with(url, timeout=10)
        for index, payload in enumerate(({}, {'issuer': ISSUER}, [])):
            settings = configuration(FOUNDRY_MCP_OAUTH_ISSUER=f'https://malformed{index}.auth0.com/')
            with patch('httpx2.get', return_value=httpx.Response(200, json=payload, request=httpx.Request('GET', url))):
                with self.assertRaises((ValueError, TypeError)): create_auth(settings)

    def test_non_oauth_does_not_construct_provider_or_discover(self):
        with patch('foundry_mcp_server.auth.auth0.create_auth0') as factory:
            for mode in ('basic', 'none'): self.assertIsNone(create_auth(Settings(auth_mode=mode)))
            factory.assert_not_called()

    def test_discovery_validation(self):
        from foundry_mcp_server.auth.auth0 import validate_discovery
        validate_discovery(OIDCConfiguration(**DISCOVERY), ISSUER)
        for name, value in (('issuer', 'https://other.example/'), ('jwks_uri', 'http://tenant.auth0.com/keys'),
                            ('token_endpoint', 'https://other.example/token'), ('code_challenge_methods_supported', []),
                            ('token_endpoint_auth_methods_supported', []), ('scopes_supported', [])):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_discovery(OIDCConfiguration(**{**DISCOVERY, name: value}), ISSUER)
        with patch.object(OIDCConfiguration, 'get_oidc_configuration', side_effect=httpx.ReadTimeout('outage')):
            with self.assertRaises(httpx.ReadTimeout): create_auth(configuration())
