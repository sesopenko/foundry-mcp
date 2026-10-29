"""Actual MCP discovery/invocation against browser-generated party DTOs."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client

from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.server import mcp


SCRIPT = r"""
import {getPartyMembers} from './foundry-module/scripts/actorParty.js';
const actors = new Map();
function add(id,type,members=[]) {
 const actor={id,uuid:'Actor.'+id,type,name:'Example',testUserPermission:()=>true,
 toObject:()=>({type,system:{details:{members:members.map(uuid=>({uuid}))}}})};
 actors.set(id,actor); return actor;
}
globalThis.game={ready:true,version:'14.369',system:{id:'pf2e',version:'8.6.1'},user:{isGM:true},actors,items:new Map()};
add('one','character');add('two','character');add('party','party',['Actor.one','Actor.two']);
const results=[await getPartyMembers(),await getPartyMembers({limit:1})];
add('other','party');results.push(await getPartyMembers());
console.log(JSON.stringify(results));
"""


class PartyToolTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        output = subprocess.run(['node', '--input-type=module'], input=SCRIPT, text=True,
                                capture_output=True, check=True, cwd=Path(__file__).resolve().parents[1])
        cls.roster, cls.page, cls.candidates = json.loads(output.stdout)

    async def asyncSetUp(self):
        self.manager = AsyncMock()
        register_foundry_manager(self.manager)

    async def test_actual_discovery_and_browser_interoperability(self):
        async with Client(mcp) as client:
            tool = next(t for t in await client.list_tools() if t.name == 'get_party_members')
            self.assertFalse(tool.inputSchema['additionalProperties'])
            self.assertIsNotNone(tool.outputSchema)
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertEqual(tool.inputSchema['properties']['limit']['default'], 10)
            self.assertEqual(tool.inputSchema['properties']['max_bytes']['default'], 8000)
            for term in ('PF2e-specific', 'read_actor', 'scope_status', 'next_cursor', 'ContentChanged', 'wealth'):
                self.assertIn(term, tool.description)
            for data, args in [(self.roster, {}), (self.page, {'limit': 1}), (self.candidates, {})]:
                self.manager.call.return_value = data
                result = await client.call_tool('get_party_members', args)
                self.assertEqual(result.structured_content, data)
                self.manager.call.assert_awaited_with('gm', 'getPartyMembers',
                    dict(limit=args.get('limit', 10), max_bytes=8000), timeout=15.0)

    async def test_invalid_input_rejected_before_bridge(self):
        async with Client(mcp) as client:
            for args in [{'party_uuid': 'Name'}, {'party_uuid': 'Scene.s.Token.t'}, {'party_uuid': 'Actor.a\n'},
                         {'unknown': True}, {'limit': True}, {'max_bytes': 48001}, {'select': {'wealth': True}}]:
                result = await client.call_tool('get_party_members', args, raise_on_error=False)
                self.assertTrue(result.is_error, args)
            self.manager.call.assert_not_awaited()

    async def test_malformed_or_wrong_scope_responses_rejected(self):
        async with Client(mcp) as client:
            for change in ('scope', 'follow', 'denied', 'count', 'runtime', 'unknown', 'duplicate', 'wrong-party', 'bound'):
                data = copy.deepcopy(self.roster); args = {}
                if change == 'scope': data['scope_status'] = 'partial'
                elif change == 'follow': data['entries'][0]['next_call']['arguments']['actor_uuid'] = 'Actor.wrong'
                elif change == 'denied': data['entries'][0]['status'] = 'denied'
                elif change == 'count': data['pagination']['returned'] = 99
                elif change == 'runtime': data['runtime']['system_id'] = 'other'
                elif change == 'unknown': data['secret'] = 'must not escape'
                elif change == 'duplicate': data['entries'][1] = copy.deepcopy(data['entries'][0])
                elif change == 'wrong-party': args = {'party_uuid': 'Actor.other'}
                elif change == 'bound': args = {'limit': 1}
                self.manager.call.return_value = data
                result = await client.call_tool('get_party_members', args, raise_on_error=False)
                self.assertTrue(result.is_error, change)

    async def test_bridge_disconnect_is_actionable(self):
        self.manager.call.side_effect = ConnectionError()
        async with Client(mcp) as client:
            result = await client.call_tool('get_party_members', {}, raise_on_error=False)
            self.assertTrue(result.is_error)
            self.assertIn('BridgeUnavailable', str(result.content))


if __name__ == '__main__':
    unittest.main()
