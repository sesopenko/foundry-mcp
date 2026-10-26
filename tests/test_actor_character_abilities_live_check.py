"""Offline safety and orchestration for the marked character ability fixture."""
import contextlib
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/actor-character-abilities-live-check.py'
SPEC = importlib.util.spec_from_file_location('character_abilities_live_check', SCRIPT)
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class Client:
    def __init__(self, failure=None):
        self.failure, self.calls, self.cleanup = failure, [], False
        self.items = [dict(uuid='Actor.fixture.Item.' + key, type=kind, name='Same ability')
                      for key, kind in [('a', 'action'), ('f', 'feat'), ('c', 'feat')]]
        self.items[1]['category'] = 'general'
        self.items[2]['category'] = 'classfeature'
        self.description = HARNESS.DESCRIPTION.replace('</p><p>', '</p>\n<p>') if failure == 'normalized' else HARNESS.DESCRIPTION
        for item in self.items:
            item.update(description_sha256=hashlib.sha256(self.description.encode()).hexdigest(),
                        description_utf16_length=len(self.description.encode('utf-16-le')) // 2,
                        authored_input_unchanged=self.description == HARNESS.DESCRIPTION)

    async def list_tools(self):
        self.calls.append(('list_tools', {}))
        if self.failure == 'discovery':
            raise RuntimeError('private credential')
        return [SimpleNamespace(name='read_actor', annotations=SimpleNamespace(readOnlyHint=True),
                                description='character_ability_item other_abilities_not_enumerated ability_items_denied')]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == 'execute_javascript':
            code = arguments['code']
            if 'const matches=' in code:
                self.cleanup = True
                value = dict(pending=1 if self.failure == 'pending' else 0, remaining=0)
            elif 'Actor.implementation.create' in code:
                if self.failure == 'lost_creation':
                    raise RuntimeError('creation response lost after commit; private')
                value = dict(uuid='Actor.fixture', items=self.items)
            elif 'const claims=' in code:
                claims = json.loads(code.split('const claims=', 1)[1].split(';', 1)[0])
                value = dict(checks=[self.failure != 'witness'] * len(claims), schema_undefined_absences=0,
                             failed_paths=[claims[0]['path']] if self.failure == 'witness' else [])
            else:
                value = 'unchanged'
            return SimpleNamespace(structured_content={'value': json.dumps(value)})
        if self.failure == 'read':
            raise RuntimeError('private source prose')
        if name == 'read_actor':
            rows = []
            for item in self.items:
                raw = [dict(document_uuid=item['uuid'], path='/' + key, present=True, value=item[key], basis='source') for key in ('name', 'type')]
                rows.append(dict(key='abilities:item:' + item['uuid'], kind='relationship', raw=raw,
                                 mapped=dict(concept='character_ability_item', value=dict(status='resolved', target_uuid=item['uuid'], type=item['type'], name=item['name'], name_truncated=False), unit=None),
                                 provenance=dict(mapping='pf2e.character.ability-reference.v1', contributors=[{k: r[k] for k in ('document_uuid', 'path', 'basis')} for r in raw], limitations=['owned_item_reference_not_complete_or_active_ability'])))
            sections = [dict(status='partial', reasons=['other_abilities_not_enumerated'])]
            identity = dict(uuid='Actor.fixture')
        else:
            item = next(row for row in self.items if row['uuid'] == arguments['item_uuid'])
            rows = [dict(kind='field', raw=[dict(document_uuid=item['uuid'], path='/name', present=True, value=item['name'], basis='source')])]
            if item['type'] == 'feat':
                rows.append(dict(kind='field', raw=[dict(document_uuid=item['uuid'], path='/system/category', present=True, value=item['category'], basis='source')]))
            text = self.description + ('tampered' if self.failure == 'corrupt_description' else '')
            # Small UTF-16-safe fragments, each inside the same byte bounds as live.
            for index in range(0, len(text), 100):
                value = text[index:index + 100]
                start = len(text[:index].encode('utf-16-le')) // 2
                end = start + len(value.encode('utf-16-le')) // 2
                total = len(text.encode('utf-16-le')) // 2
                rows.append(dict(kind='text', raw=[dict(value=value)], text=dict(path='/system/description/value', start=start, end=end, total=total, complete=end == total)))
            sections = [dict(status='complete'), dict(status='complete')]
            identity = dict(uuid=item['uuid'], actor={'uuid': 'Actor.fixture'})
        start = int(arguments.get('cursor', 0))
        count = 1 if name == 'read_actor' else 5
        return SimpleNamespace(structured_content=dict(identity=identity, revision='stable',
            runtime=dict(core_version='14.369', system_id='pf2e', system_version='8.6.1'), sections=sections,
            records=rows[start:start + count], pagination={'next_cursor': str(start + count) if start + count < len(rows) else None}))


class CharacterAbilityHarnessTests(unittest.IsolatedAsyncioTestCase):
    def test_actual_action_optional_undefined_matches_serialized_source_absence(self):
        script = r"""
import {actionFields} from './foundry-module/scripts/actorAction.js';
const code=JSON.parse(process.argv[1]);
const source={name:'Action',type:'action',system:{actionType:{value:'passive'},deathNote:undefined,frequency:undefined,selfEffect:undefined}};
const fields=actionFields(source).filter(field=>['/system/deathNote','/system/frequency','/system/selfEffect'].includes(field.path));
const actor={items:new Map([['a',{uuid:'Item.a',toObject:()=>source}]])};
const claims=fields.map(({path,present,value})=>({document_uuid:'Item.a',path,present,...(present?{value}:{}),basis:'source'}));
if(process.argv[2]==='forge')claims.push({document_uuid:'Item.a',path:'/system/actionType/value',present:true,value:'reaction',basis:'source'});
const result=await new Function('actor','claims','return (async()=>{'+code+';return result;})()')(actor,claims);
console.log(JSON.stringify(result));
"""
        process = subprocess.run(['node', '--input-type=module', '-e', script, json.dumps(HARNESS.SOURCE_WITNESS_CHECK)],
                                 capture_output=True, text=True, cwd=SCRIPT.parents[1], timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['checks'], [True, True, True])
        self.assertEqual(result['schema_undefined_absences'], 3)
        self.assertEqual(result['failed_paths'], [])
        forged = subprocess.run(['node', '--input-type=module', '-e', script, json.dumps(HARNESS.SOURCE_WITNESS_CHECK), 'forge'],
                                capture_output=True, text=True, cwd=SCRIPT.parents[1], timeout=10)
        self.assertEqual(forged.returncode, 0, forged.stderr)
        result = json.loads(forged.stdout)
        self.assertEqual(result['checks'], [True, True, True, False])
        self.assertEqual(result['failed_paths'], ['/system/actionType/value'])

    async def test_normalized_persisted_description_is_verified_exactly_not_against_input_literal(self):
        report = await HARNESS.verify(Client('normalized'), 'test', 'offline-ability-run')
        self.assertTrue(report['passed'], report)
        self.assertTrue(report['description_setup_normalized'])
        self.assertTrue(report['cleanup_verified'])

    async def test_changed_returned_description_still_fails_exact_source_hash(self):
        report = await HARNESS.verify(Client('corrupt_description'), 'test', 'offline-ability-run')
        self.assertFalse(report['passed'])
        self.assertEqual(report['failure_stage'], 'item_description_reconstruction')
        self.assertTrue(report['cleanup_verified'])

    async def test_success_consumes_pages_and_cleans_exact_fixture(self):
        client = Client()
        report = await HARNESS.verify(client, 'test', 'offline-ability-run')
        self.assertTrue(report['passed'], report)
        self.assertTrue(report['cleanup_verified'])
        self.assertEqual(report['ability_items'], 3)
        self.assertTrue(any(args.get('cursor') for _, args in client.calls))
        self.assertEqual(report['completed_calls'], len(client.calls))

    async def test_failures_cleanup_and_pending_never_claims_clean(self):
        for failure in ('discovery', 'lost_creation', 'read', 'witness', 'pending'):
            with self.subTest(failure=failure):
                client = Client(failure)
                report = await HARNESS.verify(client, 'test', 'offline-ability-run')
                self.assertFalse(report['passed'])
                self.assertTrue(client.cleanup)
                self.assertEqual(report['cleanup_verified'], failure != 'pending')
                self.assertNotIn('private', json.dumps(report))
                if failure == 'lost_creation':
                    self.assertEqual(report['requested_calls'] - report['completed_calls'], 1)

    async def test_wrong_world_before_credentials_and_bounded_secret_free_connection(self):
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

    def test_actual_deferred_creation_and_cleanup_preserve_unrelated_actor(self):
        script = r"""
const [create,cleanup]=JSON.parse(process.argv[1]);const actors=[],deleted=[];let resolveCreate,creates=0,ownedCalls=0;
globalThis.location={origin:'http://localhost:30000'};globalThis.game={actors,ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
const unrelated={uuid:'Actor.other',type:'character',getFlag:()=> 'other-run',async delete(){throw Error('unrelated deletion');}};actors.push(unrelated);
globalThis.Actor={implementation:{create:async data=>{creates++;return new Promise(resolve=>{resolveCreate=()=>{const actor={uuid:'Actor.late',type:'character',getFlag:()=>data.flags['foundry-mcp'].characterAbilityProbe,async delete(){deleted.push(this.uuid);actors.splice(actors.indexOf(this),1);},async createEmbeddedDocuments(){ownedCalls++;throw Error('closed run cannot create owned Items');}};actors.push(actor);resolve(actor);};});}}};
const execute=code=>new Function('return (async()=>{'+code+'})()')();
const pending=execute(create).then(()=>false,()=>true);for(let n=0;!resolveCreate&&n<20;n++)await Promise.resolve();if(!resolveCreate)throw Error('deferred create missing');globalThis.setTimeout=callback=>{callback();return 0;};
const early=JSON.parse((await execute(cleanup)).join(''));resolveCreate();const rejected=await pending;const final=JSON.parse((await execute(cleanup)).join(''));
console.log(JSON.stringify({early,final,rejected,creates,ownedCalls,deleted,unrelatedSurvived:actors.length===1&&actors[0]===unrelated}));
"""
        code = [HARNESS.fixture_code(HARNESS.CREATE_CHARACTER, 'offline-ability-run'),
                HARNESS.fixture_code(HARNESS.CLEANUP_CHARACTER, 'offline-ability-run')]
        process = subprocess.run(['node', '--input-type=module', '-e', script, json.dumps(code)], capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['early']['pending'], 1)
        self.assertEqual(result['final'], dict(pending=0, remaining=0))
        self.assertTrue(result['rejected'])
        self.assertEqual(result['creates'], 1)
        self.assertEqual(result['ownedCalls'], 0)
        self.assertEqual(result['deleted'], ['Actor.late'])
        self.assertTrue(result['unrelatedSurvived'])

    def test_actual_cleanup_rejects_wrong_uuid_and_type_before_deleting(self):
        script = r"""
const [code,type]=JSON.parse(process.argv[1]);let deleted=0;
const actor={uuid:'Actor.actual',type,getFlag:()=> 'offline-ability-run',async delete(){deleted++;}};
globalThis.location={origin:'http://localhost:30000'};globalThis.game={actors:[actor],ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
let rejected=false;try{await new Function('return (async()=>{'+code+'})()')();}catch{rejected=true;}
console.log(JSON.stringify({rejected,deleted}));
"""
        for actor_type, expected in [('character', 'Actor.wrong'), ('npc', None)]:
            with self.subTest(actor_type=actor_type):
                code = HARNESS.fixture_code(HARNESS.CLEANUP_CHARACTER, 'offline-ability-run', expected)
                process = subprocess.run(['node', '--input-type=module', '-e', script, json.dumps([code, actor_type])],
                                         capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout), {'rejected': True, 'deleted': 0})
