"""Offline execution of the read-only token check's actual selection guards."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/actor-token-live-check.py'
SPEC = importlib.util.spec_from_file_location('actor_token_live_check', SCRIPT)
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)

NODE_FIXTURE = r"""
import {webcrypto} from 'node:crypto';
Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
const [code,scenario]=JSON.parse(process.argv[1]);let reads=0,writes=0,canvasReads=0;
Object.defineProperty(globalThis,'canvas',{get(){canvasReads++;throw Error('canvas prohibited');}});
const write=()=>{writes++;throw Error('write prohibited');};
const scenes=[];const scene={uuid:'Scene.inactive',active:false,tokens:[],testUserPermission:()=>true,update:write,activate:write};scenes.push(scene);
function actor(uuid,hp,label){
 const type=scenario==='character'?'character':'npc';
 const source={_id:'base',name:'Creature',type,system:{attributes:{hp:{value:hp}}}};
 const itemSource={_id:scenario==='cosmeticOnly'?uuid:'shared',flags:{cosmetic:uuid},name:label,type:'action',system:{description:{value:'<p>'+label+'</p>'},actionType:{value:'passive'}}};
 const owner={uuid,type,items:new Map(),testUserPermission:()=>true,toObject:flag=>{reads++;return structuredClone(source);},update:write,prepareData:write};
 const item={id:'shared',uuid:uuid+'.Item.shared',type:'action',testUserPermission:()=>true,toObject:flag=>{reads++;return structuredClone(itemSource);},update:write};owner.items.set(item.id,item);return owner;
}
const base=actor('Actor.base',30,'Base');
const a=actor('Scene.inactive.Token.first.Actor.base',7,'First');
const b=actor('Scene.inactive.Token.second.Actor.base',19,['sameItems','cosmeticOnly'].includes(scenario)?'First':'Second');
if(scenario==='sameHP')b.toObject=()=>({...a.toObject(true)});
const token=(id,owner,linked=false)=>({uuid:'Scene.inactive.Token.'+id,actor:owner,baseActor:base,isLinked:linked,testUserPermission:()=>true,toObject:()=>({_id:id,actorLink:linked}),update:write,delete:write});
scene.tokens.push(token('first',a),token('second',b));
if(scenario!=='noLinked')scene.tokens.push(token('linked',base,true));
if(scenario==='activeOnly')scene.active=true;
if(scenario==='separateInactive'){scene.active=true;scenes.push({uuid:'Scene.other',active:false,tokens:[],testUserPermission:()=>true});}
globalThis.location={origin:'http://localhost:30000'};
globalThis.game={ready:true,user:{isGM:true},world:{id:scenario==='wrongWorld'?'campaign':'test'},version:scenario==='wrongVersion'?'14.999':'14.369',system:{id:'pf2e',version:'8.6.1'},scenes};
globalThis.foundry={utils:{fromUuid:async uuid=>[base,a,b].flatMap(owner=>[...owner.items.values()]).find(item=>item.uuid===uuid)}};
let result=null,error=null;try{result=await new Function('return (async()=>{'+code+'})()')();}catch(e){error=e.message;}
console.log(JSON.stringify({result,error,reads,writes,canvasReads}));
"""


class TokenSelectionTests(unittest.TestCase):
    def run_selection(self, scenario):
        code = harness.GUARD + harness.SELECT + '\nreturn result;'
        process = subprocess.run(['node', '--input-type=module', '-e', NODE_FIXTURE,
                                  json.dumps([code, scenario])], capture_output=True, text=True,
                                 cwd=SCRIPT.parents[1])
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_actual_selection_proves_same_base_distinct_hp_items_linked_and_inactive(self):
        observation = self.run_selection('valid')
        self.assertIsNone(observation['error'])
        result = observation['result']
        self.assertEqual(result['gaps'], [])
        a, b, linked = result['samples']
        self.assertEqual(a['base'], b['base'])
        self.assertNotEqual(a['actor'], b['actor'])
        self.assertNotEqual(a['hp'], b['hp'])
        self.assertNotEqual(a['itemsHash'], b['itemsHash'])
        self.assertEqual(a['items'][0]['id'], b['items'][0]['id'])
        self.assertNotEqual(a['items'][0]['uuid'], b['items'][0]['uuid'])
        self.assertTrue(linked['linked'])
        self.assertEqual(linked['actor'], linked['base'])
        self.assertTrue(any(row['inactive'] for row in result['samples']))
        self.assertEqual(observation['writes'], 0)
        self.assertEqual(observation['canvasReads'], 0)

    def test_uuid_prefix_difference_alone_and_hp_or_items_only_do_not_close_gate(self):
        for scenario in ('sameItems', 'cosmeticOnly', 'sameHP', 'noLinked', 'activeOnly'):
            with self.subTest(scenario=scenario):
                observation = self.run_selection(scenario)
                self.assertIsNone(observation['error'])
                self.assertTrue(observation['result']['gaps'])
                self.assertEqual(observation['result']['samples'], [])
                self.assertEqual(observation['writes'], 0)
                self.assertEqual(observation['canvasReads'], 0)

    def test_inactive_scene_can_be_independent_of_selected_token_pair(self):
        observation = self.run_selection('separateInactive')
        self.assertEqual(observation['result']['gaps'], [])
        self.assertEqual(observation['result']['inactive_scene'], 'Scene.other')
        self.assertTrue(all(not row['inactive'] for row in observation['result']['samples']))

    def test_character_pair_uses_same_source_and_current_hp_identity_contract(self):
        observation = self.run_selection('character')
        self.assertIsNone(observation['error'])
        self.assertEqual(observation['result']['gaps'], [])
        first, second, linked = observation['result']['samples']
        self.assertEqual((first['hp'], second['hp']), (7, 19))
        self.assertEqual((first['currentHP'], second['currentHP']), (7, 19))
        self.assertEqual(first['base'], second['base'])
        self.assertNotEqual(first['actor'], second['actor'])
        self.assertNotEqual(first['itemsHash'], second['itemsHash'])
        self.assertEqual(linked['actor'], linked['base'])
        self.assertEqual(observation['writes'], 0)
        self.assertEqual(observation['canvasReads'], 0)

    def test_wrong_runtime_world_guard_precedes_any_document_serialization(self):
        for scenario in ('wrongWorld', 'wrongVersion'):
            with self.subTest(scenario=scenario):
                observation = self.run_selection(scenario)
                self.assertEqual(observation['error'], 'Wrong development runtime')
                self.assertEqual(observation['reads'], 0)
                self.assertEqual(observation['writes'], 0)


class TokenVerifyTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_orchestration_consumes_cursors_rejects_cross_token_and_detects_changes(self):
        selection = TokenSelectionTests().run_selection('valid')['result']
        for failure in (None, 'fingerprint', 'cross_token', 'empty_checks'):
            calls = []
            selection_reads = 0

            class Client:
                async def list_tools(self):
                    calls.append(('list_tools', {}))
                    return [SimpleNamespace(name=name, annotations=SimpleNamespace(readOnlyHint=True),
                                            inputSchema={'additionalProperties': False, 'properties': {'token_uuid': {}}},
                                            description='next_cursor base_actor')
                            for name in ('list_scene_actors', 'read_actor', 'list_actor_items', 'read_item')]

                async def call_tool(self, name, arguments, **options):
                    nonlocal selection_reads
                    calls.append((name, arguments))
                    if name == 'execute_javascript':
                        code = arguments['code']
                        if 'const claims=' in code:
                            claims = json.loads(code.split('const claims=', 1)[1].split(';', 1)[0])
                            value = [] if failure == 'empty_checks' else [True] * len(claims)
                        else:
                            selection_reads += 1
                            value = json.loads(json.dumps(selection))
                            if failure == 'fingerprint' and selection_reads > 1:
                                value['samples'][0]['actorHash'] = 'changed'
                        return SimpleNamespace(structured_content={'value': json.dumps(value)})
                    if options.get('raise_on_error') is False:
                        return SimpleNamespace(is_error=failure != 'cross_token',
                                               content=[SimpleNamespace(text='DocumentNotFound')])
                    if name == 'list_scene_actors':
                        if 'scene_uuid' not in arguments:
                            rows = [{'uuid': scene} for scene in {s['scene'] for s in selection['samples']}]
                        else:
                            rows = [dict(uuid=s['token'], actor_link=s['linked'], identity={'uuid': s['actor']},
                                         base_actor={'uuid': s['base']}) for s in selection['samples']
                                    if s['scene'] == arguments['scene_uuid']]
                        key, identity = 'nodes', None
                    else:
                        sample = next(s for s in selection['samples'] if s['token'] == arguments['token_uuid'])
                        identity = dict(uuid=sample['actor'], instance={'token_uuid': sample['token'],
                                                                       'base_actor': {'uuid': sample['base']}})
                        key = 'records'
                        if name == 'list_actor_items':
                            key = 'nodes'
                            rows = [dict(identity=item, next_call={'arguments': {'token_uuid': sample['token']}})
                                    for item in sample['items']]
                        elif name == 'read_actor':
                            source = arguments['sections'] == ['source']
                            rows = [dict(raw=[dict(path='/system/attributes/hp/value', basis='source' if source else 'transformed',
                                                   value=sample['hp'] if source else sample['currentHP'])])]
                        else:
                            identity = dict(uuid=sample['item']['uuid'], actor={'uuid': sample['actor']})
                            description = arguments['sections'] == ['description']
                            raw = dict(document_uuid=sample['item']['uuid'], path='/system/description/value' if description else '/name',
                                       basis='source', present=True, value='Exact prose' if description else 'Name')
                            rows = [dict(kind='text' if description else 'field', raw=[raw])]
                            if description:
                                rows[0]['text'] = dict(start=0, end=11, total=11)
                    # Force the three-token selected-scene result through real
                    # returned cursors instead of pretending one page is complete.
                    start = int(arguments.get('cursor', '0'))
                    page = dict(revision='stable', pagination={'next_cursor': str(start + 1) if start + 1 < len(rows) else None},
                                **{key: rows[start:start + 1]})
                    if identity is not None:
                        page['identity'] = identity
                    return SimpleNamespace(structured_content=page)

            with self.subTest(failure=failure):
                report = await harness.verify(Client(), 'test')
                if failure is None:
                    self.assertTrue(report['passed'], report)
                    self.assertEqual(report['item_followups'], 3)
                    self.assertTrue(any(args.get('cursor') for _, args in calls))
                    self.assertEqual(report['mcp_calls'], len(calls))
                else:
                    self.assertFalse(report['passed'])
                    self.assertEqual(report['failure_stage'], {'fingerprint': 'unchanged_source_fingerprints',
                                                               'cross_token': 'cross_token_rejection',
                                                               'empty_checks': 'item_reads'}[failure])

    async def test_wrong_world_rejects_before_client_operations(self):
        class Client:
            async def list_tools(self):
                raise AssertionError('No calls allowed')

            async def call_tool(self, *args, **kwargs):
                raise AssertionError('No calls allowed')

        with self.assertRaises(ValueError):
            await harness.verify(Client(), 'campaign')

    async def test_missing_existing_pair_is_coverage_gap_without_reader_or_write_calls(self):
        calls = []

        class Client:
            async def list_tools(self):
                calls.append('list_tools')
                return [SimpleNamespace(name=name, annotations=SimpleNamespace(readOnlyHint=True),
                                        inputSchema={'additionalProperties': False, 'properties': {'token_uuid': {}}},
                                        description='next_cursor base_actor')
                        for name in ('list_scene_actors', 'read_actor', 'list_actor_items', 'read_item')]

            async def call_tool(self, name, arguments):
                calls.append(name)
                if name != 'execute_javascript':
                    raise AssertionError('No reader call when selection gate is unmet')
                return SimpleNamespace(structured_content={'value': json.dumps(dict(
                    gaps=['same_base_unlinked_pair_with_distinct_hp_items_and_inactive_scene'], samples=[]))})

        report = await harness.verify(Client(), 'test')
        self.assertFalse(report['passed'])
        self.assertTrue(report['coverage_gaps'])
        self.assertEqual(report['mcp_calls'], 2)
        self.assertEqual(calls, ['list_tools', 'execute_javascript'])
