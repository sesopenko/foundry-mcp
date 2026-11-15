"""Version admission through actual MCP invocation and typed output validation."""
import unittest
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

from fastmcp import Client
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from test_actor_current import current
from test_selective_reads import SCRIPT
from test_actor_discovery import response as discovery_response
from test_actor_compendiums import result as pack_response
from test_party_tools import SCRIPT as PARTY_SCRIPT
from foundry_mcp_server.mcp_server.runtime_compatibility import supported_runtime
from foundry_mcp_server.development_runtime import development_runtime_check


def browser(script):
    return json.loads(subprocess.run(['node', '--input-type=module'], input=script,
        text=True, capture_output=True, check=True, timeout=15,
        cwd=Path(__file__).resolve().parents[1]).stdout)


class RuntimeCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    def test_standalone_verifier_can_show_help_without_package_install(self):
        result = subprocess.run([sys.executable, 'scripts/actor-character-current-live-check.py', '--help'],
            capture_output=True, text=True, timeout=10, cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--world-id', result.stdout)

    async def test_new_runtime_through_inline_and_selected_actor_mcp(self):
        manager = AsyncMock()
        register_foundry_manager(manager)
        runtime = dict(core_version='14.370', system_id='pf2e', system_version='8.7.0')
        async with Client(mcp) as client:
            manager.call.return_value = dict(text='@Check[reflex]', runtime=runtime)
            result = await client.call_tool('create_pf2e_inline_check', dict(statistic='reflex'))
            self.assertEqual(result.structured_content['runtime'], runtime)
            tools = {tool.name: tool for tool in await client.list_tools()}
            runtime_schema = tools['create_pf2e_inline_check'].output_schema['$defs']['Runtime']
            self.assertNotIn('const', runtime_schema['properties']['core_version'])
            self.assertIn('>=14.369,<15', tools['create_pf2e_inline_check'].description)
            for case in browser(SCRIPT.replace("'14.369'", "'14.370'").replace("'8.6.1'", "'8.7.0'")):
                manager.call.return_value = case['packet']
                data = (await client.call_tool('read_' + case['kind'], case['args'])).structured_content
                self.assertEqual(data['runtime'], runtime)
                self.assertEqual(data, case['packet']['result'])
            for name, args, packet in [
                ('get_actor_tree', {}, discovery_response()),
                ('search_compendium_actors', dict(pack_ids=['test.pack'], query='Duplicate'), pack_response(True)),
                ('get_party_members', {}, browser(PARTY_SCRIPT.replace("'14.369'", "'14.370'").replace("'8.6.1'", "'8.7.0'"))[0]),
            ]:
                packet['runtime'] = runtime
                manager.call.return_value = packet
                data = (await client.call_tool(name, args)).structured_content
                self.assertEqual(data['runtime'], runtime)

    def test_python_and_embedded_javascript_have_identical_range_semantics(self):
        versions = [
            ('14.369', '8.6.1', True), ('14.370', '8.7.0', True),
            ('14.999', '8.99.12', True), ('14.369', '8.7.0', True),
            ('14.370', '8.6.1', True), ('14.369.0', '8.6.1', True),
            ('14.368', '8.7.0', False), ('15.0', '8.7.0', False),
            ('14.370', '8.6.0', False), ('14.370', '9.0.0', False),
            ('14.370-beta', '8.7.0', False), ('014.370', '8.7.0', False),
            ('14.370', '8.07.0', False), ('14.370', '8.7.0\n', False),
            ('14.370', None, False), (None, '8.7.0', False),
            ('14.99999999999999999999', '8.7.0', False),
        ]
        packets = [dict(core_version=c, system_id='pf2e', system_version=s) for c,s,_ in versions]
        packets.append(dict(core_version='14.370', system_id='other', system_version='8.7.0'))
        expected = [v[2] for v in versions] + [False]
        self.assertEqual([supported_runtime(p) for p in packets], expected)
        script = 'const packets=' + json.dumps(packets) + ';console.log(JSON.stringify(packets.map(p=>{globalThis.game={version:p.core_version,system:{id:p.system_id,version:p.system_version}};return ' + development_runtime_check() + ';})));'
        self.assertEqual(browser(script), expected)

    async def test_unsupported_runtime_cannot_pass_typed_inline_validation(self):
        manager = AsyncMock(); register_foundry_manager(manager)
        async with Client(mcp) as client:
            for core, system in [('14.368','8.7.0'), ('15.0','8.7.0'), ('14.370','9.0.0'), ('14.370','8.6.0')]:
                manager.call.return_value = dict(text='@Check[reflex]', runtime=dict(core_version=core,system_id='pf2e',system_version=system))
                result = await client.call_tool('create_pf2e_inline_check', dict(statistic='reflex'), raise_on_error=False)
                self.assertTrue(result.is_error)

    async def test_null_land_speed_is_preserved(self):
        manager = AsyncMock()
        register_foundry_manager(manager)
        manager.call.return_value = current('/system/movement/speeds/land', None)
        from foundry_mcp_server.mcp_server.actors import read_actor
        page = await read_actor.fn(actor_uuid='Actor.a', sections=['statistics'])
        self.assertIsNone(page['records'][0]['raw'][0]['value'])
