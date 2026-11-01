"""PF2e-specific stash: real browser DTOs through actual typed MCP discovery."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager

SCRIPT = r"""
import {getPartyStash} from './foundry-module/scripts/actorParty.js';
import {readItemSelected} from './foundry-module/scripts/actors.js';
const actors=new Map(),docs=new Map();
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors,items:new Map()};
globalThis.foundry={utils:{fromUuid:async uuid=>docs.get(uuid)}};
function party(id){const actor={id,uuid:'Actor.'+id,type:'party',documentName:'Actor',name:'Party',items:new Map(),testUserPermission:()=>true};actors.set(id,actor);docs.set(actor.uuid,actor);return actor;}
const owner=party('p');
for(const [id,type,quantity,containerId]of [['bag','backpack',1,null],['coin','treasure',0,'bag'],['other','equipment',2,null]]){
 const source={name:'Stored '+id,type,system:{quantity,containerId,description:{value:'<p>Source</p>'}}};
 const item={id,uuid:owner.uuid+'.Item.'+id,type,name:source.name,documentName:'Item',parent:owner,compendium:null,folder:null,testUserPermission:()=>true,toObject:()=>structuredClone(source)};
 owner.items.set(id,item);docs.set(item.uuid,item);
}
const result={summary:await getPartyStash(),selected:await getPartyStash({select:{quantity:false,container:true,follow_up:false}}),page:await getPartyStash({limit:1}),
 detail:await readItemSelected({item_uuid:'Actor.p.Item.coin',select:{details:['source.physical'],evidence:true},limit:10,max_bytes:48000})};
party('other');result.candidates=await getPartyStash();
console.log(JSON.stringify(result));
"""


class PartyStashTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        process = subprocess.run(['node', '--input-type=module'], input=SCRIPT, text=True,
            capture_output=True, check=True, cwd=Path(__file__).resolve().parents[1])
        cls.data = json.loads(process.stdout)

    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_discovery_and_default_selective_complete_workflows(self):
        async with Client(mcp) as client:
            tools = {t.name: t for t in await client.list_tools()}
            self.assertTrue('get_party_stash' in tools)
            tool = tools['get_party_stash']
            self.assertFalse(tool.input_schema['additionalProperties'])
            self.assertTrue(tool.annotations.read_only_hint)
            self.assertIsNotNone(tool.output_schema)
            for term in ('PF2e-specific', 'read_item', 'get_party_members', 'scope_status', 'next_cursor', 'ContentChanged', 'container', '12000'):
                self.assertIn(term, tool.description)
            for scenario, args in [('summary', {}), ('selected', {'select': {'quantity': False, 'container': True, 'follow_up': False}}),
                                  ('page', {'limit': 1}), ('candidates', {})]:
                self.manager.call.return_value = self.data[scenario]
                result = await client.call_tool('get_party_stash', args)
                self.assertEqual(result.structured_content, self.data[scenario])
                self.assertEqual(self.manager.call.await_args.args[:2], ('gm', 'getPartyStash'))

    async def test_followup_accepts_only_real_world_party_physical_ownership(self):
        async with Client(mcp) as client:
            self.manager.call.return_value = self.data['detail']
            result = await client.call_tool('read_item', {'item_uuid': 'Actor.p.Item.coin', 'max_bytes': 48000, 'select': {'details': ['source.physical'], 'evidence': True}})
            self.assertEqual(result.structured_content['identity']['actor']['type'], 'party')
            for modify in ('pack', 'token', 'type', 'uuid'):
                data = copy.deepcopy(self.data['detail'])
                identity = data['proof']['identity']
                if modify == 'pack': identity['source_kind'] = 'compendium'
                elif modify == 'token': identity['instance'] = {'token_uuid': 'Scene.s.Token.t'}
                elif modify == 'type': identity['type'] = 'feat'
                else: identity['actor']['uuid'] = 'Actor.wrong'
                self.manager.call.return_value = data
                result = await client.call_tool('read_item', {'item_uuid': 'Actor.p.Item.coin', 'max_bytes': 48000, 'select': {'details': ['source.physical'], 'evidence': True}}, raise_on_error=False)
                self.assertTrue(result.is_error, modify)
                self.assertIn('InvalidFoundryResponse', str(result.content))

    async def test_invalid_requests_fail_before_rpc(self):
        async with Client(mcp) as client:
            for args in [{'party_uuid': 'Name'}, {'party_uuid': 'Actor.p\n'}, {'unknown': True}, {'limit': True}, {'select': {'evidence': True}}, {'select': {'quantity': 1}}]:
                self.assertTrue((await client.call_tool('get_party_stash', args, raise_on_error=False)).is_error, args)
        self.manager.call.assert_not_awaited()

    async def test_forged_response_scope_selection_and_ownership_rejected(self):
        async with Client(mcp) as client:
            for change in ('owner', 'follow', 'quantity', 'missing', 'pagination', 'runtime', 'scope', 'unknown', 'selection', 'limit', 'party'):
                data = copy.deepcopy(self.data['summary']); args = {}
                if change == 'owner': data['entries'][0]['identity']['uuid'] = 'Actor.wrong.Item.bag'
                elif change == 'follow': data['entries'][0]['next_call']['arguments']['item_uuid'] = 'Actor.p.Item.wrong'
                elif change == 'quantity': data['entries'][0]['quantity']['value'] = -1
                elif change == 'missing': data['entries'][0]['quantity']['present'] = False
                elif change == 'pagination': data['pagination']['returned'] = 99
                elif change == 'runtime': data['runtime']['system_id'] = 'other'
                elif change == 'scope': data['scope_status'] = 'partial'
                elif change == 'unknown': data['secret'] = 'do not expose'
                elif change == 'selection': args = {'select': {'quantity': False}}
                elif change == 'limit': args = {'limit': 1}
                else: args = {'party_uuid': 'Actor.wrong'}
                self.manager.call.return_value = data
                self.assertTrue((await client.call_tool('get_party_stash', args, raise_on_error=False)).is_error, change)

    async def test_disconnect_is_actionable(self):
        self.manager.call.side_effect = ConnectionError()
        async with Client(mcp) as client:
            result = await client.call_tool('get_party_stash', {}, raise_on_error=False)
            self.assertTrue(result.is_error)
            self.assertIn('BridgeUnavailable', str(result.content))
