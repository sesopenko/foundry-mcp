"""PF2e-specific loot8.7.0 world/token packets through actual typed MCP.

Uses real JS extraction, including synthetic owners, not invented responses.
"""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server import selective as S


SCRIPT = r"""
import {lootFixture} from './tests/js/helpers/loot-fixture.js';
import {readActorSelected,readItemSelected,getActorTypes,listActorItems} from './foundry-module/scripts/actors.js';
import {searchActors} from './foundry-module/scripts/actorWorld.js';
import {listSceneActors} from './foundry-module/scripts/actorScenes.js';
const f=lootFixture(),cases=[];
const add=async(tool,args,handler)=>cases.push({tool,args,packet:await handler(args)});
await add('get_actor_types',{},getActorTypes);
await add('search_actors',{query:'Chest',types:['loot']},searchActors);
await add('list_scene_actors',{scene_uuid:'Scene.s',types:['loot']},listSceneActors);
for(const selector of [{actor_uuid:f.base.uuid},...Array.from(f.scene.tokens.values(),t=>({token_uuid:t.uuid}))]){
 for(const details of [[],['inventory.summary'],['inventory'],['source','statistics','spellcasting','wealth','bulk','state','build','skills','strikes','abilities','description','effective']])
  await add('read_actor',{...selector,select:{details,evidence:true},limit:100,max_bytes:48000},readActorSelected);
 await add('list_actor_items',{...selector,select:{context:true,relationships:true,follow_up:true,limitations:true},limit:10,max_bytes:8000},listActorItems);
 const owner=selector.token_uuid?f.scene.tokens.get(selector.token_uuid.split('.').at(-1)).actor:f.base;
 await add('read_item',{item_uuid:owner.items.get('coins').uuid,...(selector.token_uuid?{token_uuid:selector.token_uuid}:{}),select:{details:['source.physical','description'],evidence:true},limit:10,max_bytes:48000},readItemSelected);
}
for(const owner of [f.base,f.scene.tokens.get('t0').actor])for(const type of ['weapon','armor','shield','equipment','consumable','ammo','backpack','book','treasure','kit']){
 const item=f.add(owner,'family-'+type,type,{quantity:0,description:{value:'<p>Stored source.</p>'}});
 await add('read_item',{item_uuid:item.uuid,...(owner===f.base?{}:{token_uuid:'Scene.s.Token.t0'}),select:{details:['source.physical','description'],evidence:true},limit:10,max_bytes:48000},readItemSelected);
}
console.log(JSON.stringify(cases));
"""


class ActorLootTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        process = subprocess.run(['node', '--input-type=module'], input=SCRIPT, text=True,
                                 capture_output=True, cwd=Path(__file__).resolve().parents[1], timeout=30, check=True)
        cls.cases = json.loads(process.stdout)

    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_actual_loot_discovery_reads_and_owner_packets_cross_mcp(self):
        async with Client(mcp) as client:
            for case in self.cases:
                with self.subTest(tool=case['tool'], args=case['args']):
                    self.manager.call.return_value = case['packet']
                    result = await client.call_tool(case['tool'], case['args'])
                    if case['tool'] in ('read_actor', 'read_item'):
                        self.assertEqual(result.structured_content, case['packet']['result'])

    async def test_discovery_documents_scopes_and_typed_contracts(self):
        async with Client(mcp) as client:
            tools = {t.name: t for t in await client.list_tools()}
            self.assertIn('loot', json.dumps(tools['search_actors'].input_schema))
            self.assertIn('loot', json.dumps(tools['list_scene_actors'].input_schema))
            self.assertNotIn('loot', json.dumps(tools['search_compendium_actors'].input_schema))
            for name in ('read_actor', 'read_item', 'list_actor_items', 'get_actor_types'):
                self.assertIn('loot', tools[name].description.lower())
                self.assertIsNotNone(tools[name].output_schema)
            for tool,args in [('search_actors',{'query':'x','types':['hazard']}),
                              ('search_compendium_actors',{'pack_ids':['example.pack'],'query':'x','types':['loot']}),
                              ('read_actor',{'actor_uuid':'Actor.base','select':{'details':['loot.config']}})]:
                self.assertTrue((await client.call_tool(tool,args,raise_on_error=False)).is_error)
        self.manager.call.assert_not_awaited()

    async def test_forged_unsupported_sections_and_pack_owners_rejected(self):
        case=next(c for c in self.cases if c['tool']=='read_actor' and 'source' in c['args']['select']['details'])
        packet=copy.deepcopy(case['packet'])
        packet['proof']['sections'][0]['status']='complete'
        packet['result']['sections'][0]['status']='complete'
        self.manager.call.return_value=packet
        from fastmcp.exceptions import ToolError
        with self.assertRaises(ToolError):
            await S.read(S.M.ActorRequest.model_validate(case['args']))
        from foundry_mcp_server.mcp_server.actors import _identity
        identity=copy.deepcopy(self.cases[3]['packet']['result']['identity'])
        identity.update(source_kind='compendium',uuid='Compendium.test.loot.Actor.base',pack={'id':'test.loot','title':'Loot'})
        self.assertFalse(_identity(identity))

    async def test_loot_token_identity_cannot_claim_another_instance_or_world_scope(self):
        from foundry_mcp_server.mcp_server.actors import _identity
        case=next(c for c in self.cases if c['tool']=='read_actor' and c['args'].get('token_uuid')=='Scene.s.Token.t0')
        identity=copy.deepcopy(case['packet']['result']['identity'])
        self.assertTrue(_identity(identity))
        for change in ('token','scene','linked','world'):
            forged=copy.deepcopy(identity)
            if change=='token':forged['instance']['token_uuid']='Scene.s.Token.other'
            elif change=='scene':forged['instance']['scene_uuid']='Scene.other'
            elif change=='linked':forged['instance']['actor_link']=True
            else:forged.update(source_kind='world',instance=None)
            with self.subTest(change=change):self.assertFalse(_identity(forged))


if __name__ == '__main__':
    unittest.main()
