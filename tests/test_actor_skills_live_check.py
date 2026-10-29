"""Offline actual-reader and independent-browser checks for current Skills."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('skills_live_check', ROOT / 'scripts/actor-skills-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)

NODE = r"""
import {integratedFixture} from './tests/js/fixtures/actor-integrated.js';
import {readActor,readItem} from './foundry-module/scripts/actors.js';
import {webcrypto} from 'node:crypto';Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
const f=integratedFixture('npc');game.world={id:'test'};globalThis.location={origin:'http://localhost:30000'};
const [name,args]=JSON.parse(process.argv[1]);let result;
if(name==='execute_javascript'){const chunks=await new Function('return (async()=>{'+args.code+'})()')();result={value:chunks.join('')};}
else result=await(name==='read_actor'?readActor(args):readItem(args));
console.log(JSON.stringify(result));
"""


class Client:
    def __init__(self, failure=None):
        self.failure, self.calls = failure, []

    async def list_tools(self):
        self.calls.append('list_tools')
        return [SimpleNamespace(name='read_actor', annotations=SimpleNamespace(readOnlyHint=True),
                                description='skills transformed itemId')]

    async def call_tool(self, name, args):
        self.calls.append(name)
        if self.failure == 'transport':
            raise RuntimeError('private credential and prose')
        process = subprocess.run(['node', '--input-type=module', '-e', NODE, json.dumps([name, args])],
                                 cwd=ROOT, capture_output=True, text=True, timeout=10)
        if process.returncode:
            raise AssertionError(process.stderr)
        value = json.loads(process.stdout)
        if name == 'execute_javascript':
            decoded = json.loads(value['value'])
            if isinstance(decoded, dict) and 'samples' in decoded and self.failure == 'missing_coverage':
                decoded.update(samples=[], coverage_gaps=['existing_npc_with_current_owner_local_lore'])
            if isinstance(decoded, dict) and decoded.get('samples') and self.failure == 'no_ordinary':
                decoded['samples'][0]['ordinary_skills'] = 0
            if isinstance(decoded, list) and self.failure == 'short_checks':
                decoded = []
            value['value'] = json.dumps(decoded)
        if name == 'read_actor' and self.failure == 'forged_total':
            for row in value['records']:
                if row['mapped']['concept'] == 'current_skill_total_modifier' and row['raw'][0]['present']:
                    row['raw'][0]['value'] = 999
                    row['mapped']['value'] = 999
        return SimpleNamespace(structured_content=value)


class SkillsLiveCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_reader_pages_match_independent_serialization_and_lore_owner(self):
        client = Client()
        report = await HARNESS.verify(client)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['actor_types'], ['npc'])
        self.assertEqual(report['resolved_lore'], 1)
        self.assertEqual(report['source_lore'], 1)
        self.assertFalse(report['character_checked'])
        self.assertEqual(report['completed_calls'], len(client.calls))

    async def test_forged_values_short_checks_and_coverage_absence_fail(self):
        for failure in ('forged_total', 'short_checks', 'missing_coverage', 'no_ordinary'):
            with self.subTest(failure=failure):
                report = await HARNESS.verify(Client(failure))
                self.assertFalse(report['passed'])
                self.assertNotIn('private', json.dumps(report))
                if failure == 'no_ordinary':
                    self.assertIn('npc_ordinary_current_skills_unavailable', report['coverage_gaps'])

    async def test_missing_explicit_character_never_substitutes_another_actor(self):
        report = await HARNESS.verify(Client(), character_uuid='Actor.requested')
        self.assertFalse(report['passed'])
        self.assertIn('requested_character_unavailable', report['coverage_gaps'])

    async def test_requested_completed_counts_distinguish_failed_calls(self):
        report = await HARNESS.verify(Client('transport'))
        self.assertEqual((report['requested_calls'], report['completed_calls']), (2, 1))
        self.assertFalse(report['passed'])
        self.assertNotIn('private', json.dumps(report))

    async def test_world_guard_precedes_credentials_and_connection_errors_are_safe(self):
        with patch.object(HARNESS.Path, 'read_text', side_effect=AssertionError('credential read')):
            with self.assertRaises(ValueError):
                await HARNESS.main('campaign')

        class Session:
            async def __aenter__(self):
                raise RuntimeError('private token')

            async def __aexit__(self, *args):
                return False

        output = io.StringIO()
        with patch.object(HARNESS.Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(HARNESS, 'StreamableHttpTransport', return_value=object()), \
             patch.object(HARNESS, 'Client', return_value=Session()) as client, contextlib.redirect_stdout(output):
            self.assertEqual(await HARNESS.main('test'), 1)
        self.assertEqual(client.call_args.kwargs, dict(timeout=30, init_timeout=10))
        self.assertEqual(HARNESS.SESSION_TIMEOUT_SECONDS, 180)
        self.assertNotIn('private', output.getvalue())
