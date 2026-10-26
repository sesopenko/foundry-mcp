"""Offline proof for deferred-affliction discovery and schema rejection checks."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('affliction_interface_check', Path(__file__).resolve().parents[1] / 'scripts/affliction-interface-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class Client:
    def __init__(self, failure=None):
        self.failure, self.calls = failure, []

    async def list_tools(self):
        self.calls.append(('list_tools', {}))
        descriptions = {
            'get_actor_types': 'no dedicated affliction reader; in_scope false',
            'read_actor': 'affliction_reading_unsupported; dedicated affliction Items have no reader',
            'read_item': 'affliction Items deferred outside current delivery scope',
            'list_actor_items': 'dedicated affliction Items have no reader and cannot be selected in types',
            'search_compendium_actors': 'dedicated affliction Items have no reader and excluded from filters',
        }
        tools = [SimpleNamespace(name=name, description=description,
                                 inputSchema={'properties': {'types': {'items': {'enum': ['spell', 'effect']}}}})
                 for name, description in descriptions.items()]
        if self.failure in ('enum', 'const'):
            tools.append(SimpleNamespace(name='other_tool', description='Unknown tool',
                                         inputSchema={'$defs': {'nested': {'anyOf': [{self.failure: ['affliction'] if self.failure == 'enum' else 'affliction'}]}}}))
        if self.failure == 'description':
            tools[3].description = 'All Item types are supported'
        return tools

    async def call_tool(self, name, arguments, **kwargs):
        self.calls.append((name, arguments))
        if self.failure == 'transport':
            raise RuntimeError('private credential or campaign text')
        if name == 'get_actor_types':
            row = dict(type='affliction', in_scope=False, source_supported=False, mapped_supported=False,
                       effective_supported=False, limitations=['Deferred pending upstream support; PF2e8.6.1 production disabled.'])
            if self.failure in ('in_scope', 'source_supported', 'mapped_supported', 'effective_supported'):
                row[self.failure] = True
            return SimpleNamespace(structured_content={'item_types': [row]})
        if name not in ('list_actor_items', 'search_compendium_actors'):
            raise AssertionError('Unexpected operation')
        assert kwargs == {'raise_on_error': False}
        assert arguments['types'] == ['affliction']
        if self.failure == 'accepted':
            return SimpleNamespace(is_error=False, content=[])
        code = 'DocumentNotFound' if self.failure == 'wrong_error' else 'InvalidRequest'
        return SimpleNamespace(is_error=True, content=[SimpleNamespace(text=json.dumps({'code': code, 'message': 'private error body'}))])


class AfflictionInterfaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_uses_only_four_metadata_and_invalid_filter_calls(self):
        client = Client()
        result = await HARNESS.verify(client)
        self.assertTrue(result['passed'], result)
        self.assertEqual([name for name, _ in client.calls], ['list_tools', 'get_actor_types', 'list_actor_items', 'search_compendium_actors'])
        self.assertEqual(result['requested_calls'], 4)
        self.assertEqual(result['completed_calls'], 4)
        self.assertEqual(result['documents_read'], 0)

    async def test_hidden_enum_const_and_description_teases_reject_before_registry(self):
        for failure in ('enum', 'const', 'description'):
            with self.subTest(failure=failure):
                client = Client(failure)
                result = await HARNESS.verify(client)
                self.assertFalse(result['passed'])
                self.assertEqual(result['failure_stage'], 'discovery')
                self.assertEqual(len(client.calls), 1)

    async def test_registry_cannot_advertise_any_deferred_capability(self):
        for failure in ('in_scope', 'source_supported', 'mapped_supported', 'effective_supported'):
            with self.subTest(failure=failure):
                result = await HARNESS.verify(Client(failure))
                self.assertFalse(result['passed'])
                self.assertEqual(result['failure_stage'], 'registry')
                self.assertEqual(result['completed_calls'], 2)

    async def test_accepted_filters_or_backend_not_found_are_not_validation_proof(self):
        for failure in ('accepted', 'wrong_error'):
            with self.subTest(failure=failure):
                result = await HARNESS.verify(Client(failure))
                self.assertFalse(result['passed'])
                self.assertEqual(result['failure_stage'], 'owned_item_filter_rejection')
                self.assertEqual(result['completed_calls'], 3)

    async def test_failed_requests_are_counted_separately_without_private_diagnostics(self):
        result = await HARNESS.verify(Client('transport'))
        self.assertFalse(result['passed'])
        self.assertEqual((result['requested_calls'], result['completed_calls']), (2, 1))
        self.assertNotIn('private', json.dumps(result))

    def test_schema_rejection_accepts_literal_validation_but_not_unrelated_errors(self):
        response = SimpleNamespace(is_error=True, content=[SimpleNamespace(text="Input validation error: types.0 expected readable type; got 'affliction'")])
        self.assertTrue(HARNESS.invalid_filter_response(response))
        response.content[0].text = 'Bridge unavailable: affliction'
        self.assertFalse(HARNESS.invalid_filter_response(response))
        self.assertFalse(HARNESS.has_affliction_selector({'description': 'affliction is deferred'}))

    async def test_main_has_bounded_client_and_sanitized_failure(self):
        class Session:
            async def __aenter__(self):
                raise RuntimeError('private token and text')

            async def __aexit__(self, *args):
                return False

        output = io.StringIO()
        with patch.object(HARNESS.Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(HARNESS, 'StreamableHttpTransport', return_value=object()), \
             patch.object(HARNESS, 'Client', return_value=Session()) as client, contextlib.redirect_stdout(output):
            code = await HARNESS.main()
        self.assertEqual(code, 1)
        self.assertEqual(client.call_args.kwargs, {'timeout': 30, 'init_timeout': 10})
        self.assertEqual(HARNESS.SESSION_TIMEOUT_SECONDS, 180)
        self.assertFalse(json.loads(output.getvalue())['passed'])
        self.assertNotIn('private', output.getvalue())
