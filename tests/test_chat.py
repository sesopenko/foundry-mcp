"""Actual in-memory MCP discovery and validation for chat."""
import json
import unittest
from unittest.mock import AsyncMock
from fastmcp import Client
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.chat import STYLE_GUIDE


class ChatTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_invocation_validation_and_guide(self):
        manager=AsyncMock()
        register_foundry_manager(manager)
        manager.call.return_value={'messages':[], 'cursor':'cursor','has_more':False,'scope':'loaded_visible_history'}
        async with Client(mcp) as client:
            tools={t.name:t for t in await client.list_tools()}
            for name in ('read_chat_messages','read_chat_message_content','send_chat_message'):
                self.assertTrue(tools[name].output_schema)
                self.assertFalse(tools[name].input_schema['additionalProperties'])
            result=await client.call_tool('read_chat_messages',{'request':{}})
            self.assertEqual(result.structured_content['messages'],[])
            bad=await client.call_tool('read_chat_messages',{'request':{'after_id':'a','cursor':'b'}},raise_on_error=False)
            self.assertTrue(bad.is_error)
            guide=await client.call_tool('get_pathfinder_writing_style_guide',{})
            self.assertEqual(guide.structured_content['text'],STYLE_GUIDE)
            from pathlib import Path
            root=Path(__file__).resolve().parents[1]
            wishlist='\n'.join((root/'docs'/name).read_text() for name in ('feature-wishlist.md','feature-wishlist-finished.md'))
            expected=wishlist.split('## WISH-007',1)[1].split('```text\n',1)[1].split('\n```',1)[0]
            self.assertEqual(guide.structured_content['text'],expected)
            print('chat discovery bytes:',len(json.dumps([tools[n].model_dump(mode='json') for n in tools if 'chat_message' in n or 'writing_style' in n],separators=(',',':')).encode()))

    async def test_all_send_modes_and_invalid_requests_at_actual_boundary(self):
        manager=AsyncMock()
        register_foundry_manager(manager)
        modes=['Public as User','private to game masters','blind to game masters','self only','public as character']
        base={'id':'created','timestamp':1,'author':{'id':'gm','name':'GM'},'speaker':{'actor':None,'alias':'GM','scene':None,'token':None},'whisper':[],'blind':False,'names_truncated':False}
        async with Client(mcp) as client:
            for i,mode in enumerate(modes):
                request=dict(request_id=f'chat-test-request-{i}',mode=mode,content='<p>Test</p>')
                if i==4: request['actor_id']='character'
                manager.call.return_value={**base,'mode':mode,'request_id':request['request_id']}
                result=await client.call_tool('send_chat_message',{'request':request})
                self.assertEqual(result.structured_content['mode'],mode)
                self.assertEqual(manager.call.call_args.args[1],'sendChatMessage')
            manager.call.reset_mock()
            invalid=[
                ('read_chat_messages',{'request':{'limit':True}}),
                ('read_chat_messages',{'request':{'limit':'10'}}),
                ('read_chat_messages',{'request':{'limit':0}}),
                ('read_chat_messages',{'request':{'max_bytes':48001}}),
                ('read_chat_messages',{'request':{'cursor':''}}),
                ('read_chat_messages',{'request':{'delete':True}}),
                ('read_chat_messages',{'delete':True}),
                ('read_chat_message_content',{'message_id':'m','offset':1}),
                ('read_chat_message_content',{'message_id':'m','revision':'bad'}),
                ('send_chat_message',{'request':dict(request_id='chat-invalid-test',mode='Clear chat log',content='x')}),
                ('send_chat_message',{'request':dict(request_id='chat-invalid-test',mode=modes[4],content='x')}),
                ('send_chat_message',{'request':dict(request_id='chat-invalid-test',mode=modes[0],actor_id='x',content='x')}),
                ('send_chat_message',{'request':dict(request_id='chat-invalid-test',mode=modes[0],content='😀'*4001)}),
                ('get_pathfinder_writing_style_guide',{'extra':True}),
            ]
            for name,args in invalid:
                with self.subTest(name=name,args=str(args)[:100]):
                    result=await client.call_tool(name,args,raise_on_error=False)
                    self.assertTrue(result.is_error)
            manager.call.assert_not_awaited()

    async def test_response_validation_and_budget(self):
        manager=AsyncMock()
        register_foundry_manager(manager)
        async with Client(mcp) as client:
            for response in ({},dict(messages=[],cursor='c',has_more=False,scope='loaded_visible_history',extra='leak'),dict(messages=[],cursor='c'*9000,has_more=False,scope='loaded_visible_history')):
                manager.call.return_value=response
                result=await client.call_tool('read_chat_messages',{'request':{}},raise_on_error=False)
                self.assertTrue(result.is_error)
