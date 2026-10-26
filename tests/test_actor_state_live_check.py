"""PF2e-specific state harness source identity versus prepared display labels."""
import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('state_live_check', ROOT / 'scripts/actor-state-live-check.py')
HARNESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HARNESS)


class StateFixtureAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_token_state_adapter_follows_instances_and_rejects_identity_or_fingerprint_changes(self):
        actor, token, item = 'Scene.s.Token.t.Actor.a', 'Scene.s.Token.t', 'Scene.s.Token.t.Actor.a.Item.e'
        sample = dict(uuid=actor, selector={'token_uuid': token}, scene_uuid='Scene.s', base_uuid='Actor.a',
                      items=[dict(uuid=item, type='effect')], source_hash='source', current_hash='current', coverage=['effect', 'effect_expiry'])
        selected = dict(stats={'scenes': 1, 'tokens': 1, 'readable_unlinked_actors': 1, 'unlinked_with_state': 1},
                        samples=[sample], coverage=['effect', 'effect_expiry'], coverage_gaps=[])
        value = dict(status='resolved', target_uuid=item, document_name='Item', type='effect', name='Stored',
                     name_truncated=False, token_uuid=token, application='unknown')

        def record(key, kind, raw, value, mapping):
            return dict(key=key, section='state', kind=kind, raw=raw, mapped={'value': value},
                        provenance=dict(mapping=mapping, contributors=[{k: r[k] for k in ('document_uuid', 'path', 'basis')} for r in raw]))

        records = [record('state:item:' + item, 'relationship',
                          [dict(document_uuid=item, path='/' + key, present=True, value=v, basis='source') for key, v in [('name', 'Stored'), ('type', 'effect')]],
                          value, 'pf2e.actor.state-source.v1'),
                   record('state:current:' + item + ':/system/expired', 'field',
                          [dict(document_uuid=item, path='/system/expired', present=True, value=False, basis='transformed')], False, 'pf2e.effect.current.v1'),
                   record('state:capability:affliction', 'field', [],
                          dict(status='unsupported', reason='pf2e_8_6_1_affliction_disabled'), 'pf2e.actor.state-capability.v1')]
        for failure in (None, 'wrong_token', 'changed_current', 'false_context', 'missing_checks'):
            calls, selections = [], 0

            class Client:
                async def call_tool(self, name, arguments):
                    nonlocal selections
                    calls.append((name, arguments))
                    if name == 'execute_javascript':
                        code = arguments['code']
                        if 'const claims=' in code:
                            claims = json.loads(code.split('const claims=', 1)[1].split(';', 1)[0])
                            if 'basis' in claims[0]:
                                result = [] if failure == 'missing_checks' else [{key: raw[key] for key in ('present', 'value') if key in raw} for raw in claims]
                            elif 'source_identity' in claims[0] and 'selectedName' in code:
                                result = [{key: claim[key] for key in ('target_uuid', 'document_name', 'name', 'name_truncated', 'type') if key in claim} for claim in claims]
                            else:
                                result = [failure != 'false_context'] * len(claims)
                        else:
                            selections += 1
                            result = json.loads(json.dumps(selected))
                            if failure == 'changed_current' and selections > 1:
                                result['samples'][0]['current_hash'] = 'changed'
                        return SimpleNamespace(structured_content={'value': json.dumps(result)})
                    identity = dict(uuid=actor, type='npc', source_kind='token',
                                    instance=dict(token_uuid='Scene.s.Token.wrong' if failure == 'wrong_token' else token,
                                                  scene_uuid='Scene.s', actor_link=False, base_actor={'uuid': 'Actor.a'}))
                    if name == 'read_item':
                        return SimpleNamespace(structured_content={'identity': {**identity, 'uuid': item, 'actor': {'uuid': actor}}})
                    current = arguments.get('sections') == ['state']
                    index = int(arguments.get('cursor', 0))
                    return SimpleNamespace(structured_content=dict(identity=identity, runtime=dict(core_version='14.369', system_id='pf2e', system_version='8.6.1'),
                            revision='stable', sections=[dict(name='state', status='partial', reasons=['effective_application_not_evaluated', 'affliction_reading_unsupported'])],
                            records=records[index:index + 1] if current else [],
                            pagination={'next_cursor': str(index + 1) if current and index < 2 else None}))

            with self.subTest(failure=failure):
                report = await HARNESS.run_token_state(Client(), 'test')
                self.assertEqual(report['passed'], failure is None, report)
                if failure is None:
                    self.assertEqual(report['item_followups'], 1)
                    self.assertEqual(report['expired_false'], 1)
                    self.assertEqual(report['mcp_calls'], len(calls))
                    self.assertTrue(any(args.get('cursor') for _, args in calls))
                else:
                    self.assertIn('failure_stage', report)

    async def test_no_existing_token_candidate_reports_gap_without_reader_calls(self):
        calls = []

        class Client:
            async def call_tool(self, name, arguments):
                calls.append(name)
                if name != 'execute_javascript':
                    raise AssertionError('No token reader without an eligible instance')
                return SimpleNamespace(structured_content={'value': json.dumps(dict(
                    stats={'scenes': 3, 'tokens': 9, 'readable_unlinked_actors': 2, 'unlinked_with_state': 0},
                    samples=[], coverage=[], coverage_gaps=['existing_readable_unlinked_token_with_owned_condition_or_effect']))})

        report = await HARNESS.run_token_state(Client(), 'test')
        self.assertFalse(report['passed'])
        self.assertTrue(report['coverage_gaps'])
        self.assertEqual(calls, ['execute_javascript'])
        self.assertEqual(report['mcp_calls'], 1)

    async def test_invalid_token_flags_reject_before_credentials_or_client(self):
        for arguments in [dict(token_state=True), dict(token_state=True, world_id='campaign'),
                          dict(token_state=True, state_fixture=True, world_id='test'),
                          dict(token_state=True, discovery_only=True, world_id='test')]:
            with self.subTest(arguments=arguments), \
                 patch.object(HARNESS.Path, 'read_text', side_effect=AssertionError('Credentials prohibited')), \
                 patch.object(HARNESS, 'Client', side_effect=AssertionError('Client prohibited')):
                with self.assertRaises(ValueError):
                    await HARNESS.main(**arguments)

    async def test_invalid_fixture_flags_reject_before_credentials_or_client(self):
        for arguments in [dict(state_fixture=True), dict(world_id='test'),
                          dict(state_fixture=True, world_id='campaign'),
                          dict(state_fixture=True, world_id='test', discovery_only=True)]:
            with self.subTest(arguments=arguments), \
                 patch.object(HARNESS.Path, 'read_text', side_effect=AssertionError('Credentials prohibited')), \
                 patch.object(HARNESS, 'Client', side_effect=AssertionError('Client prohibited')):
                with self.assertRaises(ValueError):
                    await HARNESS.main(**arguments)


class StateLiveCheckTests(unittest.TestCase):
    def test_actual_token_census_uses_existing_owners_without_canvas_or_writes(self):
        script = r"""
import {webcrypto} from 'node:crypto';Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
const [code,scenario]=JSON.parse(process.argv[1]);let canvasReads=0,writes=0,getters=0;
Object.defineProperty(globalThis,'canvas',{get(){canvasReads++;throw Error('canvas prohibited');}});
const write=()=>{writes++;throw Error('write prohibited');};
const scene={uuid:'Scene.s',tokens:new Map(),testUserPermission:()=>true,update:write};
const base={uuid:'Actor.base',testUserPermission:()=>true};
function add(id,type){const actor={uuid:'Scene.s.Token.'+id+'.Actor.base',type:'npc',items:new Map(),testUserPermission:()=>true,toObject:()=>({name:'Actor',type:'npc',system:{}}),update:write};
 const item={uuid:actor.uuid+'.Item.state',type,parent:actor,system:{expired:false},testUserPermission:()=>true,toObject:()=>({name:'Stored state',type,system:{}}),update:write};actor.items.set('state',item);
 const token={uuid:'Scene.s.Token.'+id,isLinked:scenario==='linkedOnly',actor,baseActor:base,parent:scene,testUserPermission:()=>true,toObject:()=>({name:'Token',actorLink:false}),update:write};scene.tokens.set(id,token);
 if(scenario==='denied')item.testUserPermission=()=>false;
 if(scenario==='accessor')Object.defineProperty(item.system,'expired',{get(){getters++;throw Error('expiry getter prohibited');}});
 return token;}
add('first','condition');add('second','effect');
globalThis.game={ready:true,user:{isGM:true},version:'14.369',system:{id:'pf2e',version:'8.6.1'},world:{id:'test'},scenes:new Map([['s',scene]])};globalThis.location={origin:'http://localhost:30000'};
let result=null,error=null;try{const chunks=await new Function('return (async()=>{'+code+'})()')();result=JSON.parse(chunks.join(''));}catch(e){error=e.message;}
console.log(JSON.stringify({result,error,canvasReads,writes,getters}));
"""
        for scenario in ('present', 'linkedOnly', 'denied', 'accessor'):
            with self.subTest(scenario=scenario):
                process = subprocess.run(['node', '--input-type=module', '-e', script,
                                          json.dumps([HARNESS.GUARD + HARNESS.TOKEN_SELECT + HARNESS.CHUNKS, scenario])],
                                         cwd=ROOT, capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 0, process.stderr)
                observation = json.loads(process.stdout)
                self.assertIsNone(observation['error'])
                self.assertEqual((observation['canvasReads'], observation['writes'], observation['getters']), (0, 0, 0))
                result = observation['result']
                self.assertEqual(result['stats']['tokens'], 2)
                if scenario in ('linkedOnly', 'denied'):
                    self.assertEqual(result['samples'], [])
                    self.assertEqual(result['coverage_gaps'], ['existing_readable_unlinked_token_with_owned_condition_or_effect'])
                else:
                    self.assertEqual(len(result['samples']), 2)
                    self.assertEqual(result['coverage_gaps'], [])
                    self.assertTrue({'condition', 'effect'} <= set(result['coverage']))
                    self.assertEqual('effect_expiry' in result['coverage'], scenario == 'present')
                    for sample in result['samples']:
                        self.assertTrue(sample['uuid'].startswith(sample['selector']['token_uuid'] + '.Actor.'))
                        self.assertTrue(all(item['uuid'].startswith(sample['uuid'] + '.Item.') for item in sample['items']))
                        self.assertEqual(sample['base_uuid'], 'Actor.base')
                        self.assertEqual(len(sample['source_hash']), 64)

    def test_actual_fixture_setup_uses_only_marked_owner_and_unevaluated_formula(self):
        script = r"""
const code=JSON.parse(process.argv[1]),writes=[],created=[];let deleted=0;
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},version:'14.369',system:{id:'pf2e',version:'8.6.1'},world:{id:'test'},time:{worldTime:1000},actors:[]};
const actor={uuid:'Actor.fixture',type:'character',items:new Map(),getFlag:()=> 'offline-state-run',async delete(){deleted++;},async createEmbeddedDocuments(type,inputs){writes.push('createOwned');return inputs.map((source,index)=>{const id='i'+this.items.size,item={id,uuid:this.uuid+'.Item.'+id,type:source.type,parent:this,source};this.items.set(id,item);created.push(item);return item;});},async updateEmbeddedDocuments(type,updates){writes.push('updateOwned');for(const update of updates){const item=this.items.get(update._id);if(!item)throw Error('Nonfixture Item update');item.source.system.start={value:update['system.start.value'],initiative:update['system.start.initiative']};}return updates;}};
globalThis.Actor={implementation:{create:async source=>{writes.push('createActor');if(source.type!=='character'||source.flags['foundry-mcp'].stateVerificationRun!=='offline-state-run')throw Error('Unsafe create');game.actors.push(actor);return actor;}}};
const chunks=await new Function('return (async()=>{'+code+'})()')();
const result=JSON.parse(chunks.join(''));
console.log(JSON.stringify({writes,deleted,count:actor.items.size,result,items:created.map(item=>({uuid:item.uuid,type:item.type,source:item.source}))}));
"""
        process = subprocess.run(['node', '--input-type=module', '-e', script,
                                  json.dumps(HARNESS.fixture_code(HARNESS.CREATE_STATE, 'offline-state-run'))],
                                 cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        observation = json.loads(process.stdout)
        self.assertEqual(observation['writes'], ['createActor', 'createOwned', 'createOwned', 'updateOwned'])
        self.assertEqual(observation['deleted'], 0)
        self.assertEqual(observation['count'], 8)
        effects = [item for item in observation['items'] if item['type'] == 'effect']
        self.assertEqual(len(effects), 3)
        self.assertEqual(effects[0]['source']['name'], effects[1]['source']['name'])
        self.assertNotEqual(effects[0]['source']['system']['context']['origin']['item'], effects[1]['source']['system']['context']['origin']['item'])
        self.assertEqual(effects[1]['source']['system']['start'], {'value': 400, 'initiative': None})
        self.assertEqual(effects[2]['source']['system']['badge'], {'type': 'formula', 'value': '1d4', 'evaluate': False, 'reevaluate': None})
        self.assertEqual(effects[2]['source']['system']['duration']['unit'], 'encounter')
        self.assertTrue(all(item['source']['system']['rules'] == [] for item in observation['items']))

    def test_actual_expiry_check_reads_public_own_data_without_serialization_or_getters(self):
        script = """
let serializations=0,getters=0;
const source={system:{duration:{unit:'unlimited'}}};
const item={documentName:'Item',type:'effect',testUserPermission:()=>true,system:{expired:false},toObject:sourceOnly=>{serializations++;if(!sourceOnly)return {system:{}};return structuredClone(source);}};
const before=JSON.stringify(source);
globalThis.game={user:{}};
globalThis.foundry={utils:{fromUuid:async()=>item}};
const claims=[{document_uuid:'Item.test',path:'/system/expired',basis:'transformed'}];
const probe=async()=>{CHECK;return result;};
const negative=await probe();item.system.expired=true;const positive=await probe();
delete item.system.expired;const missing=await probe();
Object.defineProperty(item.system,'expired',{get(){getters++;throw Error('Getter forbidden');},configurable:true});const accessor=await probe();
delete item.system.expired;Object.defineProperty(item,'system',{get(){getters++;throw Error('System getter forbidden');},configurable:true});const systemAccessor=await probe();
console.log(JSON.stringify({negative,positive,missing,accessor,systemAccessor,serializations,getters,unchanged:before===JSON.stringify(source)}));
""".replace('CHECK', HARNESS.WITNESS_CHECK)
        completed = subprocess.run(['node', '--input-type=module'], input=script, text=True, capture_output=True, cwd=ROOT, check=True)
        result = json.loads(completed.stdout)
        self.assertEqual(result['negative'], [dict(present=True,value=False)])
        self.assertEqual(result['positive'], [dict(present=True,value=True)])
        for key in ('missing','accessor','systemAccessor'):
            self.assertEqual(result[key], [dict(present=False)])
        self.assertEqual(result['serializations'],0)
        self.assertEqual(result['getters'],0)
        self.assertTrue(result['unchanged'])

    def test_actual_source_witness_still_uses_selected_source_serialization(self):
        script = """
let sourceCalls=0;
const item={documentName:'Item',testUserPermission:()=>true,toObject:source=>{if(source!==true)throw Error('Source required');sourceCalls++;return {system:{duration:{unit:'encounter'}}};}};
globalThis.game={user:{}};globalThis.foundry={utils:{fromUuid:async()=>item}};
const claims=[{document_uuid:'Item.test',path:'/system/duration/unit',basis:'source'},{document_uuid:'Item.test',path:'/system/absent',basis:'source'}];
""" + HARNESS.WITNESS_CHECK + '\nconsole.log(JSON.stringify({result,sourceCalls}));'
        completed = subprocess.run(['node', '--input-type=module'], input=script, text=True, capture_output=True, cwd=ROOT, check=True)
        result=json.loads(completed.stdout)
        self.assertEqual(result['result'], [dict(present=True,value='encounter'),dict(present=False)])
        self.assertEqual(result['sourceCalls'],2)

    def test_actual_target_check_preserves_source_identity_and_context_display(self):
        script = """
const doc={uuid:'Actor.test.Item.condition',documentName:'Item',type:'condition',name:'Frightened 2',testUserPermission:()=>true,toObject:source=>{if(source!==true)throw Error('Source required');return {name:'Frightened'};}};
globalThis.game={user:{}};
globalThis.foundry={utils:{fromUuid:async()=>doc}};
const claims=[{target_uuid:doc.uuid,type:doc.type,source_identity:true},{target_uuid:doc.uuid,type:doc.type,source_identity:false}];
""" + HARNESS.TARGET_CHECK + '\nconsole.log(JSON.stringify(result));'
        completed = subprocess.run(['node', '--input-type=module'], input=script, text=True, capture_output=True, cwd=ROOT, check=True)
        rows = json.loads(completed.stdout)
        self.assertEqual([row['name'] for row in rows], ['Frightened', 'Frightened 2'])
        self.assertTrue(all(not row['name_truncated'] for row in rows))
