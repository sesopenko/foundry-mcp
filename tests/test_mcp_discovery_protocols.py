"""Exercise the full application catalog using real negotiated HTTP sessions.

Codex CLI 0.169.0 negotiates 2025-06-18. A newer SDK client's default
protocol can accept a catalog that fails serialization for that client.
"""
import json
import unittest
from unittest.mock import patch

import httpx2 as httpx
from fastmcp import Client
from mcp_types.methods import SERVER_RESULTS, serialize_server_result
from pydantic import ValidationError

from foundry_mcp_server import main
from foundry_mcp_server.config import Settings
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.journal_authoring import MutationResult
from foundry_mcp_server.mcp_server.image_uploads import UploadResult


class DiscoveryProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_catalog_serializes_for_every_sdk_supported_version(self):
        async with Client(mcp, timeout=10, init_timeout=5) as client:
            # Retain the real result envelope, including modern cache metadata.
            result = await client.session.list_tools()
            catalog = result.model_dump(mode='json', by_alias=True, exclude_none=True)
        versions = sorted(version for method, version in SERVER_RESULTS if method == 'tools/list')
        self.assertIn('2025-06-18', versions)
        for version in versions:
            with self.subTest(version=version):
                serialized = serialize_server_result('tools/list', version, catalog)
                self.assertEqual({tool['name'] for tool in serialized['tools']},
                                 {tool['name'] for tool in catalog['tools']})

    def test_union_schemas_retain_object_alternatives_and_validation(self):
        for model, keyword in ((MutationResult, 'anyOf'), (UploadResult, 'oneOf')):
            with self.subTest(model=model.__name__):
                schema = model.model_json_schema()
                self.assertEqual(schema['type'], 'object')
                self.assertEqual(len(schema[keyword]), 2)
                for alternative in schema[keyword]:
                    definition = schema['$defs'][alternative['$ref'].rsplit('/', 1)[1]]
                    self.assertEqual(definition['type'], 'object')
                    self.assertFalse(definition['additionalProperties'])
                    self.assertIn('status', definition['required'])
                for invalid in ([], None, 'receipt', {'status': 'invented'},
                                {'status': 'uploaded', 'unexpected': True}):
                    with self.assertRaises(ValidationError):
                        model.model_validate(invalid)
        self.assertEqual(UploadResult.model_json_schema()['discriminator']['propertyName'], 'status')

    async def test_entire_catalog_is_discoverable_with_codex_protocol(self):
        settings = Settings(auth_mode='basic', basic_username='user',
                            basic_password='pass', bridge_token='bridge')
        with patch.object(main, 'settings', settings):
            async with main.app.router.lifespan_context(main.app), httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app), base_url='http://test',
                headers={'Accept': 'application/json, text/event-stream',
                         'Authorization': 'Basic dXNlcjpwYXNz'}, timeout=10,
            ) as client:
                initialized = await client.post('/mcp/mcp', json={
                    'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
                        'protocolVersion': '2025-06-18', 'capabilities': {},
                        'clientInfo': {'name': 'codex-protocol-regression', 'version': '1'},
                    },
                })
                self.assertEqual(initialized.status_code, 200)
                initialization = self.message(initialized)
                self.assertEqual(initialization['result']['protocolVersion'], '2025-06-18')
                client.headers.update({'MCP-Protocol-Version': '2025-06-18',
                                       'Mcp-Session-Id': initialized.headers['mcp-session-id']})
                try:
                    notification = await client.post('/mcp/mcp', json={
                        'jsonrpc': '2.0', 'method': 'notifications/initialized',
                    })
                    self.assertEqual(notification.status_code, 202)
                    response = await client.post('/mcp/mcp', json={
                        'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {},
                    })
                    self.assertEqual(response.status_code, 200)
                    catalog = self.message(response)
                    self.assertNotIn('error', catalog, catalog.get('error'))
                    tools = {tool['name']: tool for tool in catalog['result']['tools']}
                    self.assertTrue({'write_journal', 'upload_image',
                                     'browse_journal_images',
                                     'create_image_directory'} <= tools.keys())
                    self.assertTrue({'browse_maps', 'get_map_info',
                                     'get_foundry_image_info',
                                     'get_foundry_image_url'}.isdisjoint(tools))
                    for name, tool in tools.items():
                        if 'outputSchema' in tool:
                            self.assertEqual(tool['outputSchema']['type'], 'object', name)
                finally:
                    await client.delete('/mcp/mcp')

    @staticmethod
    def message(response):
        if response.headers['content-type'].startswith('application/json'):
            return response.json()
        messages = [json.loads(line[5:].strip()) for line in response.text.splitlines()
                    if line.startswith('data:')]
        return next(message for message in messages if 'id' in message)
