"""Offline admission, time-budget and cleanup safety for familiar fixtures."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/actor-familiar-live-check.py'
SPEC = importlib.util.spec_from_file_location('actor_familiar_live_check', SCRIPT)
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


class FamiliarClient:
    def __init__(self, failure='master_creation', pending=0):
        self.failure = failure
        self.pending = pending
        self.creation_codes = []
        self.cleanup_codes = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def list_tools(self):
        if self.failure == 'discovery':
            raise RuntimeError('private discovery detail')
        return [SimpleNamespace(name=name, annotations=SimpleNamespace(readOnlyHint=True), description='familiar')
                for name in ('read_actor', 'read_item', 'execute_javascript', 'get_actor_types')]

    async def call_tool(self, name, arguments):
        if name == 'get_actor_types':
            value = {'actor_types': [dict(type='familiar', source_supported=True, mapped_supported=True,
                                          effective_supported=True, limitations=['full integrated views remain unsupported; live verification is pending'])]}
            return SimpleNamespace(structured_content=value)
        if name != 'execute_javascript':
            raise RuntimeError('private reader failure')
        code = arguments['code']
        if 'const matches=' in code:
            self.cleanup_codes.append(code)
            value = {'clean': True, 'pending': self.pending}
        elif 'Actor.implementation.create' in code:
            self.creation_codes.append(code)
            master = "type:'character'" in code
            if self.failure == 'master_creation' or not master:
                raise RuntimeError('creation response lost after document committed')
            value = {'uuid': 'Actor.master'}
        else:
            raise RuntimeError('private source and model detail')
        return SimpleNamespace(structured_content={'value': json.dumps(value)})


class FamiliarHarnessSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_unassociated_statistics_preserve_actual_normalized_source_context(self):
        raw = [dict(document_uuid='Actor.familiar', path='/system/master/' + key,
                    present=True, value=None, basis='source') for key in ('id', 'ability')]
        row = dict(key='statistics:familiar_master', section='statistics', kind='relationship', raw=raw,
                   mapped=dict(concept='familiar_master', value={'status': 'unassociated', 'target_uuid': None}, unit=None),
                   provenance=dict(mapping='pf2e.familiar.master.v1', contributors=[{k: witness[k] for k in ('document_uuid', 'path', 'basis')} for witness in raw], limitations=[]))
        page = dict(identity={'uuid': 'Actor.familiar'}, sections=[dict(name='statistics', status='partial', reasons=['familiar_master_unassociated'])])
        # The previous literal-cha assertion rejects a valid public-update result.
        with self.assertRaises(AssertionError):
            assert row['raw'][1]['value'] == 'cha'
        harness.verify_unassociated_statistics([row], page, {'id': None, 'ability': None})
        for mutate in [lambda r, p: r['raw'][1].update(value='cha'),
                       lambda r, p: r['raw'][0].update(document_uuid='Actor.other'),
                       lambda r, p: r['raw'][0].update(path='/system/master/private'),
                       lambda r, p: r['raw'][1].update(basis='transformed'),
                       lambda r, p: p['sections'][0].update(status='complete'),
                       lambda r, p: p['sections'][0].update(reasons=[]),
                       lambda r, p: r['mapped']['value'].update(status='resolved')]:
            bad, bad_page = copy.deepcopy(row), copy.deepcopy(page)
            mutate(bad, bad_page)
            with self.subTest(mutation=mutate), self.assertRaises(AssertionError):
                harness.verify_unassociated_statistics([bad], bad_page, {'id': None, 'ability': None})
        with self.assertRaises(AssertionError):
            harness.verify_unassociated_statistics([row, copy.deepcopy(row)], page, {'id': None, 'ability': None})

    def test_current_acceptance_requires_finite_ac_save_skill_and_land_speed(self):
        paths = ['/system/attributes/ac/value', '/system/saves/fortitude/value',
                 '/system/skills/acrobatics/totalModifier', '/system/movement/speeds/land/value']
        fields = [dict(path=path, present=True, value=value) for path, value in zip(paths, (19, 7, 5, 25))]
        harness.require_representative_current(fields)
        for index in range(len(fields)):
            for invalid in (None, True, float('nan'), float('inf'), '19'):
                bad = [dict(field) for field in fields]
                bad[index]['value'] = invalid
                with self.subTest(path=paths[index], invalid=invalid), self.assertRaises(AssertionError):
                    harness.require_representative_current(bad)
            bad = [dict(field) for field in fields]
            bad[index] = dict(path=paths[index], present=False)
            with self.subTest(missing=paths[index]), self.assertRaises(AssertionError):
                harness.require_representative_current(bad)

    def test_current_witness_reads_public_model_when_serialization_omits_derived_fields(self):
        paths = ['/system/attributes/ac/value', '/system/saves/fortitude/value',
                 '/system/skills/acrobatics/totalModifier', '/system/movement/speeds/land/value']
        script = r"""
const [code,paths,scenario]=JSON.parse(process.argv[1]);let getters=0,transformedReads=0,sourceReads=0;
const master={id:'master'};
const actor={system:{attributes:{ac:{value:19}},saves:{fortitude:{value:7}},skills:{acrobatics:{totalModifier:5}},movement:{speeds:{land:{value:25}}}},toObject(source){if(!source){transformedReads++;throw Error('transformed serialization prohibited');}sourceReads++;return {system:{master:{id:'master',ability:'cha'}}};}};
if(scenario==='getter')Object.defineProperty(actor.system.attributes.ac,'value',{get(){getters++;return 999;}});
if(scenario==='missing')delete actor.system.attributes.ac.value;
if(scenario==='wrongMaster')master.id='other';
let result=null,error=null;
try{const report=await new Function('actor','master','paths','return (async()=>{'+code+';return report;})()')(actor,master,paths);result=JSON.parse(report);}catch(e){error=e.message;}
console.log(JSON.stringify({result,error,getters,transformedReads,sourceReads}));
"""
        for scenario in ('present', 'getter', 'missing', 'wrongMaster'):
            with self.subTest(scenario=scenario):
                observation = self.node(script, [harness.CURRENT_WITNESS, paths, scenario])
                self.assertEqual(observation['getters'], 0)
                self.assertEqual(observation['transformedReads'], 0)
                self.assertEqual(observation['sourceReads'], 1)
                if scenario == 'wrongMaster':
                    self.assertEqual(observation['error'], 'Current master mismatch')
                    self.assertIsNone(observation['result'])
                else:
                    self.assertIsNone(observation['error'])
                    fields = observation['result']['fields']
                    self.assertEqual([field['path'] for field in fields], paths)
                    if scenario == 'present':
                        self.assertEqual([field['value'] for field in fields], [19, 7, 5, 25])
                        self.assertTrue(all(field['present'] for field in fields))
                    else:
                        self.assertEqual(fields[0], {'path': paths[0], 'present': False})

    async def run_client(self, client):
        output = io.StringIO()
        with patch.object(harness.Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(harness, 'StreamableHttpTransport', return_value=object()), \
             patch.object(harness, 'Client', return_value=client), \
             patch.object(harness, 'uuid4', return_value='offline-familiar-run'), \
             patch.object(harness.asyncio, 'sleep', new_callable=AsyncMock), contextlib.redirect_stdout(output):
            code = await harness.main('test')
        return code, json.loads(output.getvalue()), output.getvalue()

    async def test_discovery_and_lost_creation_responses_still_cleanup_with_safe_diagnostics(self):
        for failure in ('discovery', 'master_creation', 'familiar_creation'):
            with self.subTest(failure=failure):
                client = FamiliarClient(failure)
                code, report, output = await self.run_client(client)
                self.assertEqual(code, 1)
                self.assertFalse(report['passed'])
                self.assertTrue(report['cleanup_confirmed'])
                self.assertEqual(report['failure_stage'], failure)
                self.assertTrue(client.cleanup_codes)
                self.assertNotIn('private', output)
                self.assertNotIn('document committed', output)

    async def test_pending_creation_prevents_cleanup_confirmation(self):
        code, report, _ = await self.run_client(FamiliarClient(pending=1))
        self.assertEqual(code, 1)
        self.assertFalse(report['passed'])
        self.assertFalse(report['cleanup_confirmed'])

    async def test_actual_cleanup_deletes_only_marked_pair_familiar_before_master(self):
        client = FamiliarClient()
        await self.run_client(client)
        script = r"""
const code=JSON.parse(process.argv[1]),actors=[],deleted=[];
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={actors,ready:true,user:{isGM:true},version:'14.369',system:{id:'pf2e',version:'8.6.1'},world:{id:'test'}};
for(const [id,type,marker]of [['master','character','offline-familiar-run'],['other','character','other-run'],['familiar','familiar','offline-familiar-run']]){
 const actor={uuid:'Actor.'+id,type,getFlag:()=>marker,async delete(){deleted.push(id);actors.splice(actors.indexOf(this),1);}};actors.push(actor);
}
const chunks=await new Function('return (async()=>{'+code+'})()')();
console.log(JSON.stringify({deleted,remaining:actors.map(a=>a.uuid),result:JSON.parse(chunks.join(''))}));
"""
        observation = self.node(script, client.cleanup_codes[0])
        self.assertEqual(observation['deleted'], ['familiar', 'master'])
        self.assertEqual(observation['remaining'], ['Actor.other'])
        self.assertEqual(observation['result'], {'pending': 0, 'clean': True})

    async def test_actual_deferred_creation_closes_and_late_actor_self_deletes(self):
        first, second = FamiliarClient(), FamiliarClient('familiar_creation')
        await self.run_client(first)
        await self.run_client(second)
        script = r"""
const [create,cleanup,nextCreate]=JSON.parse(process.argv[1]);let resolveCreate,creates=0;const actors=[],deleted=[];
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={actors,ready:true,user:{isGM:true},version:'14.369',system:{id:'pf2e',version:'8.6.1'},world:{id:'test'}};
globalThis.Actor={implementation:{create:async data=>{creates++;return new Promise(resolve=>{resolveCreate=()=>{const actor={uuid:'Actor.late',type:data.type,getFlag:()=>data.flags['foundry-mcp'].familiarVerificationRun,async delete(){deleted.push(this.uuid);actors.splice(actors.indexOf(this),1);}};actors.push(actor);resolve(actor);};});}}};
const execute=code=>new Function('return (async()=>{'+code+'})()')();
const pending=execute(create).then(()=>false,()=>true);for(let n=0;!resolveCreate&&n<20;n++)await Promise.resolve();if(!resolveCreate)throw Error('No deferred creation');
globalThis.setTimeout=callback=>{callback();return 0;};
const early=JSON.parse((await execute(cleanup)).join(''));resolveCreate();const closed=await pending;
let nextRejected=false;try{await execute(nextCreate);}catch{nextRejected=true;}
const final=JSON.parse((await execute(cleanup)).join(''));
console.log(JSON.stringify({early,closed,nextRejected,creates,deleted,final}));
"""
        observation = self.node(script, [first.creation_codes[0], first.cleanup_codes[0], second.creation_codes[-1]])
        self.assertEqual(observation['early']['pending'], 1)
        self.assertTrue(observation['closed'])
        self.assertTrue(observation['nextRejected'])
        self.assertEqual(observation['creates'], 1)
        self.assertEqual(observation['deleted'], ['Actor.late'])
        self.assertEqual(observation['final'], {'pending': 0, 'clean': True})

    def node(self, script, argument):
        process = subprocess.run(['node', '--input-type=module', '-e', script, json.dumps(argument)],
                                 capture_output=True, text=True, cwd=SCRIPT.parents[1])
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    async def test_wrong_world_rejects_before_credentials_or_client_operations(self):
        with patch.object(harness.Path, 'read_text', side_effect=AssertionError('credentials must not be read')), \
             patch.object(harness, 'Client', side_effect=AssertionError('client must not start')):
            with self.assertRaises(ValueError):
                await harness.main('campaign')

    async def test_main_supplies_request_and_initialization_deadlines_and_sanitizes_failure(self):
        class Session:
            async def __aenter__(self):
                raise RuntimeError('private token and familiar prose')

            async def __aexit__(self, *args):
                return False

        output = io.StringIO()
        timeout = harness.asyncio.timeout
        with patch.object(harness.Path, 'read_text', return_value='FOUNDRY_MCP_CALLER_TOKEN=private-token'), \
             patch.object(harness, 'StreamableHttpTransport', return_value=object()), \
             patch.object(harness, 'Client', return_value=Session()) as client, \
             patch.object(harness.asyncio, 'timeout', wraps=timeout) as deadline, contextlib.redirect_stdout(output):
            code = await harness.main('test')
        self.assertEqual(code, 1)
        self.assertEqual(client.call_args.kwargs['timeout'], 30)
        self.assertEqual(client.call_args.kwargs['init_timeout'], 10)
        self.assertLessEqual(harness.SESSION_TIMEOUT_SECONDS, 180)
        deadline.assert_any_call(harness.SESSION_TIMEOUT_SECONDS)
        report = json.loads(output.getvalue())
        self.assertFalse(report['passed'])
        self.assertNotIn('private', output.getvalue())
