"""Offline safety and orchestration checks for the genuine-book live harness."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/actor-book-live-check.py'
SPEC = importlib.util.spec_from_file_location('actor_book_live_check', SCRIPT)
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


def result(value):
    return SimpleNamespace(structured_content=value)


class BookClient:
    """Model MCP observations; record mutation requests without a real service."""
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []
        self.cleanup_code = None
        self.creation_code = None
        self.created = False
        self.description = getattr(harness, 'DESCRIPTION', 'Exact 😀 source text')
        self.fixtures = [dict(uuid='Item.' + category, category=category,
                              target=dict(uuid='Compendium.test.definitions.Item.' + category,
                                          name='Definition ' + category,
                                          type='equipment' if category == 'formula' else 'spell'),
                              description=self.description, description_matches=True, hash='unchanged')
                         for category in ('formula', 'spell')]

    async def list_tools(self):
        self.calls.append(('list_tools', {}))
        if self.failure == 'discovery':
            raise RuntimeError('private credential must never be logged')
        return [SimpleNamespace(name='read_item', annotations=SimpleNamespace(readOnlyHint=True),
                                inputSchema={'additionalProperties': False},
                                description='book Items expose book_content_reference /system/contents/N next_cursor')]

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == 'get_actor_types':
            return result({'item_types': [dict(type='book', source_supported=True,
                                               mapped_supported=True, effective_supported=False,
                                               verification={'live': {'status': 'not_run' if self.failure == 'advertised_status' else 'passed'}})]})
        if name == 'execute_javascript':
            code = arguments['code']
            if 'const marked=' in code:
                self.cleanup_code = code
                if self.failure == 'cleanup':
                    raise RuntimeError('private cleanup failure detail')
                return result({'value': json.dumps({'deleted': 2 if self.created else 0,
                                                    'pending': 1 if self.failure == 'pending' else 0,
                                                    'remaining': 1 if self.failure == 'remaining' else 0})})
            if 'const selected=' in code:
                self.creation_code = code
                self.created = True
                if self.failure == 'lost_creation':
                    raise RuntimeError('creation response lost after fixture committed')
                return result({'value': json.dumps(self.fixtures)})
            if 'const claims=' in code:
                claims = json.loads(code.split('const claims=', 1)[1].split(';', 1)[0])
                checks = [{key: claim[key] for key in ('present', 'value') if key in claim}
                          for claim in claims]
                return result({'value': json.dumps(checks)})
            if "item.toObject(true)" in code:
                return result({'value': json.dumps('unchanged')})
            raise AssertionError('Unexpected JavaScript stage')
        if name != 'read_item':
            raise AssertionError('Unexpected MCP operation')
        if self.failure == 'read':
            raise RuntimeError('private source body must not be logged')
        if arguments['sections'] == ['identity']:
            fixture = next(row for row in self.fixtures if row['target']['uuid'] == arguments['item_uuid'])
            return result({'identity': {'uuid': fixture['target']['uuid'], 'type': fixture['target']['type']}})
        if arguments['sections'] == ['effective']:
            return result({'sections': [{'name': 'effective', 'status': 'unsupported'}]})
        fixture = next(row for row in self.fixtures if row['uuid'] == arguments['item_uuid'])
        section = arguments['sections'][0]
        uuid = fixture['uuid']
        if section == 'source':
            rows = [dict(key='category', raw=[dict(document_uuid=uuid, path='/system/category',
                                                   present=True, value=fixture['category'], basis='source')])]
            rows.extend(dict(key=path, raw=[dict(document_uuid=uuid, path=path, present=True, value=value, basis='source')])
                        for path, value in [('/system/capacity', 100),
                                            ('/system/contents/0', fixture['target']['uuid']),
                                            ('/system/contents/1', fixture['target']['uuid']),
                                            ('/system/contents/2', 'Item.MCPMissingBook00')])
        elif section == 'description':
            midpoint = len(self.description) // 2
            # Use normal bounded source fragments rather than one oversized
            # fake page when the real expected description is intentionally long.
            parts = [self.description[:midpoint], self.description[midpoint:]]
            if any(len(part.encode()) > 3000 for part in parts):
                parts = [self.description[index:index + 400] for index in range(0, len(self.description), 400)]
            rows = [dict(key='text:' + str(index), kind='text', raw=[dict(path='/system/description/value', value=value)])
                    for index, value in enumerate(parts)]
        elif section == 'relationships':
            rows = [dict(key='relationships:book:contents:' + str(index),
                         raw=[dict(path='/system/contents/' + str(index))],
                         mapped=dict(concept='book_content_reference',
                                     value=dict(status='resolved', target_uuid=fixture['target']['uuid'],
                                                type=fixture['target']['type'], name=fixture['target']['name'])
                                     if index < 2 else dict(status='missing', target_uuid=None)))
                    for index in range(3)]
        else:
            raise AssertionError('Unexpected section')
        start = int(arguments.get('cursor', '0'))
        next_cursor = str(start + 7) if start + 7 < len(rows) else None
        rows = rows[start:start + 7]
        return result(dict(identity=dict(uuid=uuid, id=uuid.split('.')[-1], type='book', source_kind='world', actor=None),
                           runtime=dict(core_version='14.369', system_id='pf2e', system_version='8.6.1'),
                           sections=[dict(name=section, status='complete')],
                           revision='stable', records=rows, pagination=dict(next_cursor=next_cursor)))


class BookLiveHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_creation_metadata_survives_actual_exploration_string_budget(self):
        client = BookClient()
        await harness.verify(client, 'test', 'offline-book-probe')
        script = r"""
import {serializeForRpc} from './foundry-module/scripts/exploration.js';
import {webcrypto} from 'node:crypto';
Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
globalThis.location={origin:'http://localhost:30000'};
const definitions=['equipment','spell'].map(type=>({uuid:'Compendium.test.Item.'+type,type,name:type,testUserPermission:()=>true}));
const pack={documentName:'Item',testUserPermission:()=>true,getIndex:async()=>definitions.map(d=>({_id:d.type,type:d.type})),getUuid:id=>'Compendium.test.Item.'+id};
globalThis.game={items:[],packs:[pack],ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
globalThis.foundry={utils:{fromUuid:async uuid=>definitions.find(d=>d.uuid===uuid)}};
globalThis.Item={implementation:{create:async data=>({uuid:'Item.'+data.system.category,type:data.type,getFlag:()=>data.flags['foundry-mcp'].bookProbe,toObject:()=>structuredClone(data)})}};
const code=JSON.parse(process.argv[1]);
const chunks=await new Function('return (async()=>{'+code+'})()')();
const snapshot=serializeForRpc(chunks);
let report=null,parseError=null;try{report=JSON.parse(snapshot.values.join(''));}catch(error){parseError=error.name;}
// Reproduce the original failure with the old full-description metadata shape:
// element count is within bounds while the shared UTF-8 string budget is not.
const legacy=JSON.stringify(['formula','spell'].map(category=>({category,description:'<p>'+('界😀 é &amp; '.repeat(1400))+'</p>'})));
const legacySnapshot=serializeForRpc(Array.from({length:Math.ceil(legacy.length/800)},(_,i)=>legacy.slice(i*800,(i+1)*800)));
let legacyParseError=null;try{JSON.parse(legacySnapshot.values.join(''));}catch(error){legacyParseError=error.name;}
console.log(JSON.stringify({snapshot,report,parseError,legacySnapshot,legacyParseError}));
"""
        process = subprocess.run(['node', '--input-type=module', '-e', script,
                                  json.dumps(client.creation_code)], capture_output=True, text=True,
                                 cwd=SCRIPT.parents[1])
        self.assertEqual(process.returncode, 0, process.stderr)
        observation = json.loads(process.stdout)
        self.assertFalse(observation['snapshot']['truncated'])
        self.assertNotIn('[String budget exceeded]', json.dumps(observation['snapshot']))
        self.assertIsNone(observation['parseError'])
        self.assertEqual(len(observation['report']), 2)
        self.assertTrue(all(row['description_matches'] for row in observation['report']))
        self.assertTrue(all('description' not in row for row in observation['report']))
        self.assertFalse(observation['legacySnapshot']['truncated'])
        self.assertIn('[String budget exceeded]', json.dumps(observation['legacySnapshot']))
        self.assertEqual(observation['legacyParseError'], 'SyntaxError')

    async def test_success_verifies_both_categories_and_cleanup(self):
        client = BookClient()
        report = await harness.verify(client, 'test', 'offline-book-probe')
        self.assertTrue(report['passed'])
        self.assertTrue(report['cleanup_verified'])
        self.assertEqual(report['books'], 2)
        self.assertEqual(report['relationships'], 6)
        self.assertGreaterEqual(report['description_fragments'], 4)
        self.assertEqual(report['mcp_calls'], len(client.calls))
        self.assertIsNotNone(client.cleanup_code)

    async def test_discovery_and_read_failure_still_attempt_cleanup(self):
        for failure in ('discovery', 'read'):
            client = BookClient(failure)
            with self.subTest(failure=failure):
                report = await harness.verify(client, 'test', 'offline-book-probe')
                self.assertFalse(report['passed'])
                self.assertTrue(report['cleanup_verified'])
                self.assertEqual(report['exception_type'], 'RuntimeError')
                self.assertEqual(report['failure_stage'], 'discovery' if failure == 'discovery' else 'source_read')
            self.assertIsNotNone(client.cleanup_code)
            self.assertEqual(client.calls[-1][0], 'execute_javascript')

    async def test_lost_creation_response_cleanup_finds_marker_without_returned_ids(self):
        client = BookClient('lost_creation')
        report = await harness.verify(client, 'test', 'offline-book-probe')
        self.assertFalse(report['passed'])
        self.assertTrue(report['cleanup_verified'])
        self.assertEqual(report['failure_stage'], 'fixture_creation')
        self.assertEqual(report['exception_type'], 'RuntimeError')
        self.assertTrue(client.created)
        self.assertIsNotNone(client.cleanup_code)
        # Execute the actual cleanup code against inert JavaScript documents.
        # A different marker, even with the same type/name, must survive.
        script = r"""
const code=JSON.parse(process.argv[1]);
globalThis.location={origin:'http://localhost:30000'};
const items=[];const deleted=[];
for(const [id,marker,type]of [['ours','offline-book-probe','book'],['other','other-run','book'],['otherType','offline-book-probe','equipment']]){
 const item={id,type,getFlag:()=>marker,async delete(){deleted.push(id);items.splice(items.indexOf(this),1);}};items.push(item);
}
globalThis.game={items,ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
const value=await new Function('return (async()=>{'+code+'})()')();
console.log(JSON.stringify({deleted,remaining:items.map(i=>i.id),result:JSON.parse(value.join(''))}));
"""
        process = subprocess.run(['node', '--input-type=module', '-e', script,
                                  json.dumps(client.cleanup_code)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        observation = json.loads(process.stdout)
        self.assertEqual(observation['deleted'], ['ours'])
        self.assertEqual(observation['remaining'], ['other', 'otherType'])
        # Non-book documents bearing the marker cause remaining != 0 instead
        # of being deleted by an overly broad cleanup operation.
        self.assertEqual(observation['result']['remaining'], 1)

    async def test_cleanup_exception_or_remaining_fixture_cannot_report_success(self):
        for failure, error in [('cleanup', 'RuntimeError'), ('remaining', 'AssertionError'), ('pending', 'AssertionError')]:
            with self.subTest(failure=failure):
                report = await harness.verify(BookClient(failure), 'test', 'offline-book-probe')
                self.assertFalse(report['passed'])
                self.assertFalse(report['cleanup_verified'])
                self.assertEqual(report['cleanup_exception_type'], error)
                self.assertEqual(report['failure_stage'], 'cleanup')

    async def test_cleanup_closes_deferred_creation_and_late_item_self_deletes(self):
        client = BookClient()
        await harness.verify(client, 'test', 'offline-book-probe')
        script = r"""
const [creation,cleanup]=JSON.parse(process.argv[1]);
globalThis.location={origin:'http://localhost:30000'};
const items=[],deleted=[];let creates=0,resolveCreate;
const definitions=['equipment','spell'].map(type=>({uuid:'Compendium.test.Item.'+type,type,name:type,testUserPermission:()=>true}));
const pack={documentName:'Item',testUserPermission:()=>true,getIndex:async()=>definitions.map(d=>({_id:d.type,type:d.type})),getUuid:id=>'Compendium.test.Item.'+id};
globalThis.game={items,packs:[pack],ready:true,user:{isGM:true},world:{id:'test'},version:'14.369',system:{id:'pf2e',version:'8.6.1'}};
globalThis.foundry={utils:{fromUuid:async uuid=>definitions.find(d=>d.uuid===uuid)}};
globalThis.Item={implementation:{create:async data=>{creates++;return new Promise(resolve=>{resolveCreate=()=>{
 const item={type:data.type,getFlag:()=>data.flags['foundry-mcp'].bookProbe,async delete(){deleted.push('late');items.splice(items.indexOf(this),1);},toObject(){throw Error('closed creation must not read source');}};
 items.push(item);resolve(item);
};});}}};
const other={type:'book',getFlag:()=> 'other-run',async delete(){throw Error('unrelated deletion');}};items.push(other);
const execute=code=>new Function('return (async()=>{'+code+'})()')();
const creationResult=execute(creation).then(()=>({succeeded:true}),error=>({succeeded:false,error:error.message}));
for(let n=0;!resolveCreate&&n<30;n++)await Promise.resolve();
if(!resolveCreate)throw Error('creation never reached deferred public create');
// Exhaust only the harness's bounded cleanup wait without sleeping ten seconds.
globalThis.setTimeout=callback=>{callback();return 0;};
const early=JSON.parse((await execute(cleanup)).join(''));
resolveCreate();const creationOutcome=await creationResult;
const final=JSON.parse((await execute(cleanup)).join(''));
console.log(JSON.stringify({early,final,creationOutcome,creates,deleted,otherSurvived:items.length===1&&items[0]===other}));
"""
        process = subprocess.run(['node', '--input-type=module', '-e', script,
                                  json.dumps([client.creation_code, client.cleanup_code])],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        observation = json.loads(process.stdout)
        self.assertEqual(observation['early']['pending'], 1)
        self.assertFalse(observation['creationOutcome']['succeeded'])
        self.assertEqual(observation['creates'], 1)
        self.assertEqual(observation['deleted'], ['late'])
        self.assertTrue(observation['otherSurvived'])
        self.assertEqual(observation['final']['pending'], 0)
        self.assertEqual(observation['final']['remaining'], 0)

    async def test_wrong_world_and_unsafe_marker_reject_before_any_client_call(self):
        for world, marker in [('campaign', 'safe'), ('test', 'unsafe marker')]:
            client = BookClient()
            with self.subTest(world=world), self.assertRaises(ValueError):
                await harness.verify(client, world, marker)
            self.assertEqual(client.calls, [])

    async def test_main_failure_report_excludes_secret_and_source_details(self):
        class Session:
            async def __aenter__(self):
                return BookClient('cleanup')

            async def __aexit__(self, *args):
                return False

        output = io.StringIO()
        with patch.object(harness.Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(harness, 'StreamableHttpTransport', return_value=object()), \
             patch.object(harness, 'Client', return_value=Session()), contextlib.redirect_stdout(output):
            code = await harness.main('test')
        report = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(report['passed'])
        self.assertFalse(report['cleanup_verified'])
        self.assertNotIn('private', output.getvalue())
        self.assertNotIn('Exact', output.getvalue())

    async def test_discovery_only_checks_published_support_without_fixture_operations(self):
        for failure in (None, 'advertised_status'):
            client = BookClient(failure)

            class Session:
                async def __aenter__(self):
                    return client

                async def __aexit__(self, *args):
                    return False

            output = io.StringIO()
            with self.subTest(failure=failure), \
                 patch.object(harness.Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
                 patch.object(harness, 'StreamableHttpTransport', return_value=object()), \
                 patch.object(harness, 'Client', return_value=Session()), \
                 patch.object(harness, 'verify', side_effect=AssertionError('fixture verification forbidden')) as verify, \
                 contextlib.redirect_stdout(output):
                code = await harness.main('test', discovery_only=True)
            report = json.loads(output.getvalue())
            verify.assert_not_called()
            self.assertEqual([name for name, _ in client.calls], ['list_tools', 'get_actor_types'])
            self.assertIsNone(client.creation_code)
            self.assertIsNone(client.cleanup_code)
            if failure is None:
                self.assertEqual(code, 0)
                self.assertEqual(report, dict(passed=True, discovery_verified=True, runtime_checked=False,
                                             fixtures_created=False, mcp_calls=2))
            else:
                self.assertEqual(code, 1)
                self.assertFalse(report['passed'])
                self.assertEqual(report['exception_type'], 'AssertionError')
            self.assertNotIn('private-token', output.getvalue())
