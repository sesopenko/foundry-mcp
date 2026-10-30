"""PF2e-specific exact notation and actual typed MCP boundary tests."""
import unittest
from unittest.mock import AsyncMock

from fastmcp import Client
from foundry_mcp_server.mcp_server import inline as I, inline_models as M
from foundry_mcp_server.mcp_server.tools import register_foundry_manager
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.ws.connection import RpcError

RUNTIME = dict(core_version='14.369', system_id='pf2e', system_version='8.6.1')
UUID = 'Compendium.pf2e.feats-srd.Item.39CqlOzlHjEhh0E4'


class InlineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = AsyncMock()
        async def verify(role, method, params, **kwargs):
            self.assertEqual(role, 'gm')
            return dict(text=params['text'], runtime=RUNTIME)
        self.manager.call.side_effect = verify
        register_foundry_manager(self.manager)

    async def test_exact_notation_and_real_mcp_text(self):
        cases = [
            ('roll', {'roll': {'kind': 'damage', 'damage': [{'type': 'fire', 'amount': {'dice': [{'count': 2, 'faces': 6}], 'modifier': 3}}], 'label': 'Flaming burst'}}, '@Damage[(2d6+3)[fire]]{Flaming burst}'),
            ('roll', {'roll': {'kind': 'non_damage', 'amount': {'modifier': 0}}}, '[[/r 0]]'),
            ('roll', {'roll': {'kind': 'non_damage', 'amount': {'dice': [{'count': 1, 'faces': 20}, {'count': 2, 'faces': 4}], 'modifier': -3}, 'visibility': 'gm', 'flavor': 'Recharge', 'label': 'Now'}}, '[[/gmr 1d20+2d4-3 #Recharge]]{Now}'),
            ('check', {'statistic': 'reflex', 'dc': 20, 'basic': True}, '@Check[reflex|dc:20|basic]'),
            ('check', {'statistic': 'engineering-lore', 'label': 'Engineering'}, '@Check[engineering-lore]{Engineering}'),
            ('check', {'statistic': 'perception', 'against': 'deception', 'roller_role': 'target', 'show_dc': 'gm', 'adjustment': -2, 'immutable': True, 'name': 'Notice', 'traits': ['secret'], 'options': ['action:seek'], 'override_traits': True}, '@Check[perception|against:deception|rollerRole:target|showDC:gm|adjustment:-2|immutable|name:Notice|traits:secret|options:action:seek|overrideTraits]'),
            ('embed', {'item_uuid': UUID}, f'@Embed[{UUID} inline]'),
            ('embed', {'item_uuid': UUID, 'suppress_hr': True}, f'@Embed[{UUID} inline hr=false]'),
        ]
        async with Client(mcp) as client:
            for kind, args, expected in cases:
                with self.subTest(args=args):
                    result = await client.call_tool('create_pf2e_inline_' + kind, args)
                    self.assertEqual(len(result.content), 1)
                    self.assertEqual(result.content[0].text, expected)
                    self.assertEqual(result.structured_content, dict(text=expected, runtime=RUNTIME))

    def test_damage_categories_constants_and_signed_modifiers(self):
        request = M.RollRequest(roll=M.Damage(kind='damage', damage=[
            M.DamageInstance(type='slashing', amount=M.Amount(dice=[M.Die(count=2, faces=6)], modifier=4), precision=M.Amount(dice=[M.Die(count=1, faces=6)]), splash=M.Amount(modifier=2)),
            M.DamageInstance(type='fire', amount=M.Amount(modifier=-1), persistent=True)], options=['damage:material:silver']))
        self.assertEqual(I.format_source(request)[0], '@Damage[(2d6+4+(1d6[precision])+(2[splash]))[slashing],(-1)[persistent,fire]|options:damage:material:silver]')
        for mode, command in [('public', 'r'), ('gm', 'gmr'), ('blind', 'br'), ('self', 'sr')]:
            self.assertEqual(I.format_source(M.RollRequest(roll=M.NonDamage(kind='non_damage', amount=M.Amount(modifier=-2), visibility=mode)))[0], f'[[/{command} -2]]')

    async def test_invalid_input_rejected_before_rpc(self):
        invalid = {
            'roll': [{}, {'roll': {'kind': 'damage', 'damage': []}}, {'roll': {'kind': 'non_damage', 'amount': {'formula': '@actor.level'}}},
                     {'roll': {'kind': 'non_damage', 'amount': {'modifier': True}}}, {'roll': {'kind': 'non_damage', 'amount': {'dice': [{'count': '2', 'faces': 6}]}}},
                     {'roll': {'kind': 'non_damage', 'amount': {}, 'label': 'x]{bad}'}}, {'roll': {'kind': 'non_damage', 'amount': {}, 'flavor': '<b>x</b>'}},
                     {'roll': {'kind': 'damage', 'damage': [{'type': 'fire', 'amount': {}, 'persistent': True, 'precision': {}}]}},
                     {'roll': {'kind': 'damage', 'damage': [{'type': 'fire', 'amount': {}}], 'visibility': 'gm'}},
                     {'roll': {'kind': 'damage', 'damage': [{'type': 'fire', 'amount': {'dice': [{'count': 1, 'faces': 20}]}}]}}],
            'check': [{'statistic': 'reflex', 'dc': 20, 'against': 'class-spell'}, {'statistic': 'athletics', 'basic': True}, {'statistic': 'will', 'roller_role': 'target'}, {'statistic': 'kineticist'}, {'statistic': 'reflex', 'dc': '20'}, {'statistic': 'flat', 'traits': ['secret|dc:0']}, {'statistic': 'flat', 'adjustment': 10001}, {'statistic': 'flat', 'options': ['x'] * 33}, {'statistic': 'flat', 'label': 'a' * 201}],
            'embed': [{'item_uuid': 'Item.foo'}, {'item_uuid': UUID + '#x'}, {'item_uuid': UUID, 'suppress_hr': 'false'}, {'item_uuid': UUID, 'unknown': 0}],
        }
        async with Client(mcp) as client:
            for kind, cases in invalid.items():
                for args in cases:
                    with self.subTest(kind=kind, args=args):
                        result = await client.call_tool('create_pf2e_inline_' + kind, args, raise_on_error=False)
                        self.assertTrue(result.is_error)
        self.manager.call.assert_not_awaited()

    def test_bounds_and_byte_limit(self):
        from pydantic import ValidationError
        for amount in ({'dice': [{'count': 0, 'faces': 6}]}, {'dice': [{'count': 101, 'faces': 6}]}, {'dice': [{'count': 1, 'faces': 3}]}, {'dice': [{'count': 1, 'faces': 6.0}]}, {'dice': [{'count': 1, 'faces': 6}] * 17}, {'modifier': -10001}):
            with self.assertRaises(ValidationError): M.Amount.model_validate(amount)
        with self.assertRaises(ValidationError): M.Damage.model_validate({'kind': 'damage', 'damage': [{'type': 'fire', 'amount': {}}] * 17})
        # Bounded individual strings still cannot exceed the total source budget.
        request = M.CheckRequest(statistic='flat', traits=['a' * 200] * 32, options=['b' * 200] * 32)
        with self.assertRaisesRegex(Exception, 'SourceTooLarge'): I.format_source(request)

    async def test_discovery_and_output_validation(self):
        async with Client(mcp) as client:
            catalog = {t.name: t for t in await client.list_tools()}
        schema = catalog['create_pf2e_inline_roll'].inputSchema
        self.assertIn('discriminator', schema['properties']['roll'])
        self.assertIn('examples', schema['properties']['roll'])
        self.assertIn('Die', schema['$defs'])
        for suffix in ('roll', 'check', 'embed'):
            tool = catalog['create_pf2e_inline_' + suffix]
            self.assertFalse(tool.inputSchema['additionalProperties'])
            self.assertIsNotNone(tool.outputSchema)
            self.assertTrue(tool.annotations.readOnlyHint)
        for result in [dict(text='forged', runtime=RUNTIME), dict(text='@Check[flat]', runtime={**RUNTIME, 'system_id': 'other'}), dict(text='@Check[flat]', runtime=RUNTIME, body='leak')]:
            self.manager.call.side_effect = None
            self.manager.call.return_value = result
            async with Client(mcp) as client:
                actual = await client.call_tool('create_pf2e_inline_check', {'statistic': 'flat'}, raise_on_error=False)
                self.assertTrue(actual.is_error)

    async def test_bridge_and_rpc_errors(self):
        for error in [ConnectionError(), TimeoutError(), RpcError({'type': 'PermissionDenied', 'message': 'Denied', 'recovery': 'Connect GM'})]:
            self.manager.call.side_effect = error
            async with Client(mcp) as client:
                result = await client.call_tool('create_pf2e_inline_check', {'statistic': 'flat'}, raise_on_error=False)
                self.assertTrue(result.is_error)
