"""Fresh-process tests of the actual application mount and startup selection."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx2 as httpx
from fastmcp.server.auth.oidc_proxy import OIDCConfiguration
from fastmcp.server.auth.providers.jwt import JWTVerifier
from test_oauth import DISCOVERY, ENV, KEY, ISSUER, RESOURCE, token


class ActualApplicationTests(unittest.TestCase):
    def test_deployment_templates_are_separate(self):
        import yaml
        basic = yaml.safe_load((ROOT / 'deploy/compose.yaml').read_text())['services']['foundry-mcp']['environment']
        oauth = yaml.safe_load((ROOT / 'deploy/compose.oauth.yaml').read_text())['services']['foundry-mcp']['environment']
        self.assertEqual(oauth['FOUNDRY_MCP_AUTH_MODE'], 'oauth')
        self.assertFalse(any('BASIC_' in key for key in oauth))
        self.assertFalse(any('OAUTH_' in key for key in basic))
        self.assertNotIn('FOUNDRY_MCP_PUBLIC_URL', basic)

    def test_fresh_mode_selection_discovery_and_contract_parity(self):
        results = {}
        for mode in ('basic', 'oauth', 'none'):
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(('FOUNDRY_MCP_', 'FASTMCP_'))}
            if mode == 'oauth': env.update(ENV)
            if mode == 'basic': env.update(FOUNDRY_MCP_AUTH_MODE='basic',
                FOUNDRY_MCP_BASIC_USERNAME='user', FOUNDRY_MCP_BASIC_PASSWORD='pass', FOUNDRY_MCP_BRIDGE_TOKEN='bridge')
            completed = subprocess.run([sys.executable, __file__, '--probe', mode], cwd=ROOT,
                env=env, text=True, capture_output=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stderr[-3000:])
            results[mode] = json.loads(completed.stdout)
        for mode in ('oauth', 'none'):
            self.assertEqual(results[mode]['contract_sha256'], results['basic']['contract_sha256'])
            self.assertEqual(results[mode]['diagnostic_bytes'], results['basic']['diagnostic_bytes'])


async def probe(mode):
    import hashlib
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={'keys': [KEY.as_dict(private=False)]}))) as jwks:
        def verifier(**kwargs): return JWTVerifier(**kwargs, http_client=jwks)
        with patch.object(OIDCConfiguration, 'get_oidc_configuration', return_value=OIDCConfiguration(**DISCOVERY)) as discovery, \
             patch('foundry_mcp_server.auth.auth0.JWTVerifier', side_effect=verifier):
            from foundry_mcp_server import main
        if mode != 'oauth': discovery.assert_not_called()
        headers = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2026-07-28'}
        if mode == 'oauth': headers['Authorization'] = 'Bearer ' + token()
        if mode == 'basic': headers['Authorization'] = 'Basic dXNlcjpwYXNz'
        async with main.app.router.lifespan_context(main.app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url='https://mcp.example.com') as client:
            assert (await client.get('/health')).status_code == 200
            metadata = await client.get('/.well-known/oauth-protected-resource/mcp/mcp')
            assert metadata.status_code == (200 if mode == 'oauth' else 404)
            async def call(method, params):
                params['_meta'] = {'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                    'io.modelcontextprotocol/clientCapabilities': {}}
                response = await client.post('/mcp/mcp', headers={**headers, 'MCP-Method': method,
                    **({'MCP-Name': params['name']} if 'name' in params else {})},
                    json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
                assert response.status_code == 200, response.text
                return response.json()['result']
            catalog = (await call('tools/list', {}))['tools']
            encoded = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
            catalog_bytes = len(encoded(catalog))
            for tool in catalog:
                if mode == 'oauth':
                    assert tool['_meta'].pop('securitySchemes') == [{'type': 'oauth2', 'scopes': ['foundry:gm']}]
                else: assert 'securitySchemes' not in tool.get('_meta', {})
            result = await call('tools/call', {'name': 'get_bridge_versions', 'arguments': {}})
            assert not result.get('isError')
            print(json.dumps({'mode': mode, 'tools': len(catalog), 'catalog_bytes': catalog_bytes,
                'contract_sha256': hashlib.sha256(encoded(catalog)).hexdigest(),
                'diagnostic_bytes': len(encoded(result)), 'calls': 2, 'complete': True}))


class ValidatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_bounded_validation_and_mismatches(self):
        spec = importlib.util.spec_from_file_location('oauth_validate', ROOT / 'scripts/oauth-validate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        requests = []
        resource_metadata = {'resource': RESOURCE, 'authorization_servers': [ISSUER], 'scopes_supported': ['foundry:gm']}
        discovery = {**DISCOVERY, 'authorization_response_iss_parameter_supported': True}
        def respond(request):
            requests.append(request)
            if request.url.path == '/mcp/mcp':
                return httpx.Response(401, headers={'WWW-Authenticate': 'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp/mcp"'})
            return httpx.Response(200, json=resource_metadata if 'oauth-protected-resource' in request.url.path else discovery)
        transport = httpx.MockTransport(respond)
        report = await module.validate('https://mcp.example.com', ISSUER, transport)
        self.assertEqual(report['errors'], [])
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(r.method == 'GET' and 'authorization' not in r.headers for r in requests))
        resource_metadata['resource'] = 'wrong'
        self.assertIn('resource metadata: resource', (await module.validate('https://mcp.example.com', ISSUER, transport))['errors'])
        with self.assertRaises(ValueError):
            await module.validate('https://mcp.example.com', ISSUER,
                httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 65537)))


if __name__ == '__main__' and '--probe' in sys.argv:
    asyncio.run(asyncio.wait_for(probe(sys.argv[-1]), 20))
