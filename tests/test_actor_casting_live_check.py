"""Sanitized casting probe diagnostics and actual SDK call accounting."""
import importlib.util
import copy
import json
from pathlib import Path
import unittest
import subprocess

from fastmcp.exceptions import ToolError


SPEC = importlib.util.spec_from_file_location('casting_live_check', Path(__file__).resolve().parents[1] / 'scripts/actor-casting-current-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)

OPTION_FIXTURE = r"""
import {actorCastingOptions} from './foundry-module/scripts/actorCastingOptions.js';
import {webcrypto} from 'node:crypto';
Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
const source={name:'Caster',type:'npc',system:{resources:{focus:{value:1,max:2}}}};
const actor={id:'a',uuid:'Actor.a',type:'npc',items:new Map(),testUserPermission:()=>true,toObject:()=>structuredClone(source)};
function add(id,type,system){const stored={name:id,type,system},doc={id,uuid:actor.uuid+'.Item.'+id,type,parent:actor,testUserPermission:()=>true,toObject:()=>structuredClone(stored)};actor.items.set(id,doc);return {identity:{id,uuid:doc.uuid,type,actor:{uuid:actor.uuid}},source:stored};}
const snapshots=[];
for(const mode of ['prepared','spontaneous','innate','focus']){
 const entry=add(mode,'spellcastingEntry',{prepared:{value:mode,flexible:false},autoHeightenLevel:{value:null},slots:mode==='prepared'?{slot1:{value:0,max:2,prepared:[{id:'spell-prepared',expended:false},{id:'spell-prepared',expended:true}]}}:{}});
 const spell=add('spell-'+mode,'spell',{level:{value:1},traits:{value:mode==='innate'?['cantrip']:[]},location:{value:mode,heightenedLevel:3,autoHeightenLevel:null,signature:mode==='spontaneous',...(mode==='innate'?{uses:{value:0,max:1}}:{})},ritual:null});snapshots.push(entry,spell);
}
const unassigned=add('unassigned','spell',{level:{value:1},traits:{value:[]},location:{value:null,heightenedLevel:1,autoHeightenLevel:null,signature:false},ritual:null});snapshots.push(unassigned);
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},version:'14.369',system:{id:'pf2e',version:'8.6.1'},world:{id:'test'},actors:new Map([['a',actor]])};
const code=JSON.parse(process.argv[1]);
if(code===null){const rows=actorCastingOptions({uuid:actor.uuid,type:'npc',instance:null},snapshots,source,[{key:'spellcasting:assignment:'+unassigned.identity.uuid,mapped:{value:{status:'missing',target_uuid:null}}}]).records;console.log(JSON.stringify(rows));}
else{const chunks=await new Function('return (async()=>{'+code+'})()')();console.log(chunks.join(''));}
"""


class CastingLiveCheckTests(unittest.IsolatedAsyncioTestCase):
    def option_fixture(self, code=None):
        process = subprocess.run(['node', '--input-type=module', '-e', OPTION_FIXTURE, json.dumps(code)],
                                 cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    async def test_actual_option_dtos_match_independent_browser_source_and_all_four_modes(self):
        rows = self.option_fixture()
        calls = []

        async def browser(code):
            self.assertLessEqual(len(code.encode()), 32768)
            calls.append(code)
            return self.option_fixture(code)

        result = await HARNESS.verify_contextual_options(browser, 'Actor.a', rows)
        self.assertEqual(result['options'], 6)
        self.assertEqual(result['modes'], ['focus', 'innate', 'prepared', 'spontaneous'])
        self.assertTrue({'repeated_preparations', 'zero_generic_slot_counter', 'signature_recorded',
                         'innate_cantrip', 'unresolved_entry', 'expended_preparation', 'unexpended_preparation'} <= set(result['observed']))
        self.assertGreater(result['unique_source_witnesses'], 20)
        self.assertGreaterEqual(len(calls), 3)

    async def test_option_regressions_missing_keys_ranks_witnesses_and_short_checks_reject(self):
        original = self.option_fixture()
        for change in ('missing', 'duplicate_key', 'misbound_key', 'rank', 'source_lie', 'false_checks', 'short_checks'):
            rows = copy.deepcopy(original)
            if change == 'missing': rows.pop()
            if change == 'duplicate_key': rows[0]['key'] = rows[1]['key']
            if change == 'misbound_key': rows[0]['key'] += ':invented'
            if change == 'rank': rows[0]['mapped']['value']['configured_rank'] = 99
            if change == 'source_lie':
                for witness in rows[-1]['raw']:
                    if witness['path'] == '/system/level/value': witness['value'] = 99

            async def browser(code):
                result = self.option_fixture(code)
                if isinstance(result, list) and change == 'false_checks': return [False] * len(result)
                if isinstance(result, list) and change == 'short_checks': return []
                return result

            with self.subTest(change=change), self.assertRaises(AssertionError):
                await HARNESS.verify_contextual_options(browser, 'Actor.a', rows)

    async def test_contextual_option_validation_cannot_silently_ignore_missing_options(self):
        async def browser(code):
            return {'expected_options': 1, 'modes': ['prepared'], 'observed': []}
        with self.assertRaises(AssertionError):
            await HARNESS.verify_contextual_options(browser, 'Actor.a', [])

    def test_only_allowlisted_structured_tool_codes_escape(self):
        secret = 'private credential and campaign prose'
        for code in ('InvalidFoundryResponse', 'ReadFailed', 'ContentChanged'):
            error = ToolError(json.dumps({'code': code, 'message': secret, 'recovery': secret, 'selector': secret}))
            self.assertEqual(HARNESS.structured_error_code(error), code)
            self.assertNotIn(secret, json.dumps({'code': HARNESS.structured_error_code(error)}))
        for error in (ToolError(secret), ToolError(json.dumps({'code': secret})), ToolError(json.dumps({'code': {'message': secret}})), ToolError('[]'), RuntimeError(json.dumps({'code': 'ReadFailed'}))):
            self.assertIsNone(HARNESS.structured_error_code(error))

    async def test_requested_and_completed_include_failed_call_separately(self):
        progress = HARNESS.CallProgress()

        async def success(value):
            return value

        async def failure():
            raise ToolError('{"code":"ReadFailed","message":"private"}')

        self.assertEqual(await progress.call(success, 7), 7)
        self.assertEqual((progress.requested, progress.completed), (1, 1))
        with self.assertRaises(ToolError):
            await progress.call(failure)
        self.assertEqual((progress.requested, progress.completed), (2, 1))

    async def test_oversize_restarts_section_without_old_rows_cursor_or_revision(self):
        calls, progress = [], HARNESS.CallProgress()

        async def request(budget, cursor, ordinal):
            calls.append((budget, cursor, ordinal))
            if budget == 8000:
                if cursor:
                    raise ToolError('{"code":"ResponseTooLarge"}')
                return {'revision': 'old', 'records': ['discarded'], 'pagination': {'next_cursor': 'old-cursor'}}
            return {'revision': 'new', 'records': ['retained'], 'pagination': {'next_cursor': None}}

        async def counted(*args):
            return await progress.call(request, *args)

        rows, pages, restarts, discarded = await HARNESS.bounded_pages(counted, lambda page: None)
        self.assertEqual((rows, pages, restarts, discarded), (['retained'], 1, 1, 1))
        self.assertEqual(calls, [(8000, None, 1), (8000, 'old-cursor', 2), (48000, None, 1)])
        self.assertEqual((progress.requested, progress.completed), (3, 2))

    async def test_large_budget_failure_and_unrelated_error_are_not_retried(self):
        for code, expected in [('ResponseTooLarge', 2), ('ReadFailed', 1)]:
            calls = []
            error = ToolError(json.dumps({'code': code, 'message': 'private'}))

            async def request(budget, cursor, ordinal):
                calls.append(budget)
                raise error

            with self.assertRaises(ToolError) as caught:
                await HARNESS.bounded_pages(request, lambda page: None)
            self.assertIs(caught.exception, error)
            self.assertEqual(len(calls), expected)

    async def test_actual_utf8_budget_and_revision_checks_remain_strict(self):
        async def oversize(budget, cursor, ordinal):
            return {'revision': 'one', 'records': ['😀' * 2100], 'pagination': {'next_cursor': None}}

        with self.assertRaises(AssertionError):
            await HARNESS.bounded_pages(oversize, lambda page: None)

        async def unstable(budget, cursor, ordinal):
            return {'revision': str(ordinal), 'records': [], 'pagination': {'next_cursor': 'next' if ordinal == 1 else None}}

        with self.assertRaises(AssertionError):
            await HARNESS.bounded_pages(unstable, lambda page: None)
