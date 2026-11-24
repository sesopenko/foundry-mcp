"""Actual FastMCP discovery and calls backed by browser handlers on synthetic documents."""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastmcp import Client

from foundry_mcp_server.mcp_server.selective import size
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.ws.connection import RpcError
from foundry_mcp_server.mcp_server.item_sheet import Receipt
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect


class ItemEditingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.process = await asyncio.create_subprocess_exec(
            'node', 'tests/js/fixtures/item-editing.mjs', stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, limit=1_000_000)
        self.calls = 0
        register_foundry_manager(self)

    async def asyncTearDown(self):
        self.process.stdin.close()
        await asyncio.wait_for(self.process.wait(), 5)

    async def call(self, role, method, params, timeout):
        self.assertEqual(role, 'gm')
        self.calls += 1
        self.assertLessEqual(self.calls, 40)
        message = dict(id=self.calls, method=method, params=params)
        self.process.stdin.write(json.dumps(message).encode() + b'\n')
        reply = json.loads(await asyncio.wait_for(self.process.stdout.readline(), timeout))
        if 'error' in reply:
            raise RpcError(reply['error'])
        return reply['result']

    async def test_existing_reader_budget(self):
        async with asyncio.timeout(60), Client(mcp) as client:
            tools = await client.list_tools()
            item = next(t for t in tools if t.name == 'read_item')
            measures = {'catalog': size([t.model_dump(mode='json') for t in tools]),
                        'count': len(tools), 'schema': size(item.model_dump(mode='json')),
                        'input': size(item.input_schema), 'output': size(item.output_schema),
                        'description_bytes': len(item.description.encode())}
            for label, extra in [
                ('identity', {}), ('damage', {'select': {'details': ['source.damage']}}),
                ('evidence', {'select': {'details': ['source.damage'], 'evidence': True}, 'max_bytes': 48000}),
                ('description', {'select': {'details': ['description']}, 'limit': 1}),
            ]:
                args = dict(item_uuid='Item.blade', **extra)
                pages, total = 0, 0
                while True:
                    data = (await client.call_tool('read_item', args)).structured_content
                    pages += 1
                    total += size(data)
                    self.assertLessEqual(size(data), args.get('max_bytes', 8000))
                    if data['pagination']['complete']:
                        break
                    args['cursor'] = data['pagination']['next_cursor']
                measures[label] = [pages, total]
            print('Item reader budget', json.dumps(measures, sort_keys=True))

    async def test_discovery_and_rejections_before_rpc(self):
        async with Client(mcp) as client:
            catalog = {t.name: t for t in await client.list_tools()}
            self.assertFalse(catalog['edit_item'].annotations.read_only_hint)
            self.assertTrue(catalog['get_item_field_options'].annotations.read_only_hint)
            self.assertIn('sheet', catalog['read_item'].input_schema['properties'])
            for name, args in [
                ('read_item', {'sheet': {}, 'sections': ['source']}),
                ('read_item', {'sheet': {'fields': ['rules.0']}}),
                ('get_item_field_options', {'field': 'damage.base.type', 'slot': 1}),
                ('edit_item', {'changes': {'flags': {}}}),
                ('edit_item', {'changes': {'damage': {'base': {'rules': []}}}}),
                ('edit_item', {'changes': {'publication': {'remaster': 1}}}),
                ('edit_item', {'changes': {'weapon_summary': {'bulk': 0.5}}}),
                ('edit_item', {'changes': {'details': {'range': 11}}}),
                ('edit_item', {'changes': {'damage': {'base': {'type': 'bleed'}}}}),
                ('edit_item', {'changes': {'description': {'text': '@Check[flat]'}}}),
                ('edit_item', {'changes': {'header': {'name': 'Blade'}}, 'mode': 'apply'}),
            ]:
                with self.subTest(name=name,args=args):
                    response = await client.call_tool(name, {'item_uuid': 'Item.blade', **args}, raise_on_error=False)
                    self.assertTrue(response.is_error)
            self.assertEqual(self.calls, 0)
            with self.assertRaises(ValidationError):
                Receipt.model_validate({'status': 'applied', 'secret': True})

    async def test_lost_acknowledgment_and_malformed_receipt_require_fresh_read(self):
        args={'item_uuid':'Item.blade','changes':{'header':{'name':'Changed'}}}
        async with Client(mcp) as client:
            preview=(await client.call_tool('edit_item',args)).structured_content
            mismatched=dict(preview,status='applied',next_call={'tool':'read_item','arguments':{
                'item_uuid':'Item.blade','sheet':{'fields':['publication.title']}}})
            for response in [AsyncMock(side_effect=TimeoutError()), AsyncMock(side_effect=WebSocketDisconnect()),
                             AsyncMock(side_effect=RpcError({'type':'RpcTransportError','message':'Malformed browser error'})),
                             AsyncMock(return_value=mismatched), AsyncMock(return_value={'identity':None})]:
                with patch.object(self,'call',response):
                    receipt=await client.call_tool('edit_item',dict(args,mode='apply',expected_revision=preview['revision']),raise_on_error=False)
                    self.assertTrue(receipt.is_error)
                    self.assertIn('WriteOutcomeUnknown',receipt.content[0].text)
                    response.assert_awaited_once()
                fresh=(await client.call_tool('read_item',preview['next_call']['arguments'])).structured_content
                self.assertEqual(fresh['records'][0]['source'],'Dogslicer')

    async def test_sheet_complete_catalog_and_preview_apply_read(self):
        async with asyncio.timeout(60), Client(mcp) as client:
            counts = {}
            async def traverse(label,name,**params):
                args = dict(item_uuid='Item.blade', **params)
                records, total, pages = [], 0, 0
                while True:
                    data = (await client.call_tool(name, args)).structured_content
                    total += size(data)
                    pages += 1
                    self.assertLessEqual(size(data), args.get('max_bytes', 8000))
                    records.extend(data['records'])
                    if data['pagination']['complete']:
                        counts[label] = [pages,total]
                        return records
                    args['cursor'] = data['pagination']['next_cursor']
            default = await traverse('default_sheet','read_item',sheet={})
            self.assertTrue(default)
            self.assertNotIn('description.text',[r['field'] for r in default])
            groups = list(dict.fromkeys(r['group'] for r in default)) + ['description']
            all_fields = await traverse('all_fields','read_item',sheet={'groups':groups})
            self.assertIn('description.text',[r['field'] for r in all_fields])
            rune = 'material_and_runes.property_runes'
            one = await traverse('one_field','read_item',sheet={'fields':[rune]})
            options = one[0]['options']['arguments']
            self.assertEqual(options.pop('item_uuid'),'Item.blade')
            matches = await traverse('filtered','get_item_field_options',**options,query='wound')
            self.assertEqual([c['value'] for c in matches], ['wounding'])
            full = await traverse('catalog','get_item_field_options',**options)
            self.assertGreater(len(full),80)
            args = dict(item_uuid='Item.blade',changes={'material_and_runes':{'property_runes':[{'slot':1,'value':'flaming'}]}})
            preview = (await client.call_tool('edit_item',args)).structured_content
            receipt = (await client.call_tool('edit_item',dict(args,mode='apply',expected_revision=preview['revision']))).structured_content
            fresh = (await client.call_tool('read_item',receipt['next_call']['arguments'])).structured_content
            self.assertEqual(fresh['records'][0]['source'],'flaming')
            self.assertEqual(receipt['status'],'applied')
            counts['preview_apply_read'] = [3,sum(size(page) for page in (preview,receipt,fresh))]
            print('Item form budget',json.dumps(counts,sort_keys=True))
