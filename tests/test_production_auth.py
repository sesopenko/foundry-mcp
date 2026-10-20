import asyncio
import base64
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import WebSocketDisconnect
from foundry_mcp_server import main
from foundry_mcp_server.config import Settings
from foundry_mcp_server.ws.connection import FoundryConnectionManager

AUTH = Settings(auth_mode='basic', basic_username='librechat', basic_password='p'*32, bridge_token='t'*32)

class ProductionAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_mcp_methods_require_valid_basic_and_health_is_public(self):
        good = 'Basic ' + base64.b64encode(b'librechat:' + b'p'*32).decode()
        with patch.object(main, 'settings', AUTH):
            async with main.app.router.lifespan_context(main.app), httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
                for method in ['GET','POST','DELETE','OPTIONS']:
                    for header in ['', 'Basic !!!', 'Bearer token', 'Basic '+base64.b64encode(b'librechat:wrong').decode()]:
                        response = await client.request(method, '/mcp/mcp', headers={'Authorization':header})
                        self.assertEqual(response.status_code, 401)
                        self.assertTrue(response.headers['www-authenticate'].startswith('Basic'))
                response = await client.get('/mcp/mcp', headers={'Authorization':good})
                self.assertNotEqual(response.status_code, 401)
                self.assertEqual((await client.get('/health')).status_code, 200)
                response = await client.get('/mcp/mcp', headers=[('Authorization',good),('Authorization',good)])
                self.assertEqual(response.status_code,401)

    async def test_socket_rejections_never_register(self):
        for raw, code in [(json.dumps({'type':'auth','token':'\ud800'}),1008), ('not json',1008), ('[]',1008), ('{}',1008), (json.dumps({'type':'auth','token':'wrong'}),1008), ('x'*4097,1009), (json.dumps({'token':AUTH.bridge_token}),1008)]:
            socket, manager = AsyncMock(), AsyncMock()
            socket.receive_text.return_value=raw
            with patch.object(main,'settings',AUTH),patch.object(main,'foundry_manager',manager):
                await main.foundry_ws(socket)
            manager.register.assert_not_awaited()
            manager.unregister.assert_not_awaited()
            socket.close.assert_awaited_once_with(code=code)

    async def test_timeout_disconnect_and_binary_frame(self):
        for error in [asyncio.TimeoutError(),WebSocketDisconnect(),KeyError('text')]:
            socket,manager=AsyncMock(),AsyncMock()
            socket.receive_text.side_effect=error
            with patch.object(main,'settings',AUTH),patch.object(main,'foundry_manager',manager):
                await main.foundry_ws(socket)
            manager.register.assert_not_awaited()
            socket.close.assert_awaited_once_with(code=1008)

    async def test_authenticated_socket_acknowledges_and_unregisters(self):
        socket=AsyncMock()
        socket.receive_text.side_effect=[json.dumps({'type':'auth','token':AUTH.bridge_token}), WebSocketDisconnect()]
        manager=FoundryConnectionManager()
        with patch.object(main,'settings',AUTH),patch.object(main,'foundry_manager',manager):
            await main.foundry_ws(socket)
        self.assertEqual(json.loads(socket.send_text.call_args.args[0]),{'type':'auth','status':'ok'})
        self.assertEqual(manager.websockets,{})

    async def test_ack_precedes_visibility_and_duplicate_cannot_displace_owner(self):
        manager=FoundryConnectionManager()
        socket=AsyncMock()
        async def ack(value):
            self.assertNotIn('gm',manager.websockets)
        socket.send_text.side_effect=ack
        await manager.register('gm',socket,welcome={'type':'auth','status':'ok'})
        other=AsyncMock()
        with self.assertRaises(RuntimeError):
            await manager.register('gm',other,welcome={'type':'auth','status':'ok'})
        other.send_text.assert_not_awaited()
        self.assertIs(manager.websockets['gm'],socket)

    async def test_failed_ack_does_not_register(self):
        manager=FoundryConnectionManager(); socket=AsyncMock()
        socket.send_text.side_effect=ConnectionError()
        with self.assertRaises(ConnectionError):
            await manager.register('gm',socket,welcome={'type':'auth','status':'ok'})
        self.assertEqual(manager.websockets,{})

    async def test_concurrent_admission_has_one_winner_and_no_rpc_before_ack(self):
        manager = FoundryConnectionManager()
        first, second = AsyncMock(), AsyncMock()
        entered, release = asyncio.Event(), asyncio.Event()

        async def acknowledge(value):
            entered.set()
            await release.wait()

        first.send_text.side_effect = acknowledge
        welcome = {'type': 'auth', 'status': 'ok'}
        first_task = asyncio.create_task(manager.register('gm', first, welcome=welcome))
        await asyncio.wait_for(entered.wait(), 1)
        second_task = asyncio.create_task(manager.register('gm', second, welcome=welcome))
        try:
            await asyncio.sleep(0)  # Let the second admission reach the held lock.
            self.assertEqual(manager.websockets, {})
            self.assertFalse(second_task.done())
            with self.assertRaisesRegex(RuntimeError, 'No active Foundry client'):
                await manager.call('gm', 'getPlayerNameList')
            second.send_text.assert_not_awaited()
        finally:
            release.set()
            results = await asyncio.gather(first_task, second_task, return_exceptions=True)
        self.assertIsNone(results[0])
        self.assertIsInstance(results[1], RuntimeError)
        self.assertIs(manager.websockets['gm'], first)
        second.send_text.assert_not_awaited()
        # A rejected/stale owner cannot unregister the winner.
        await manager.unregister('gm', second)
        self.assertIs(manager.websockets['gm'], first)

    async def test_cancelled_ack_releases_admission_without_leaving_a_ghost_owner(self):
        manager = FoundryConnectionManager()
        entered = asyncio.Event()
        abandoned, replacement = AsyncMock(), AsyncMock()

        async def acknowledge(value):
            entered.set()
            await asyncio.Event().wait()

        abandoned.send_text.side_effect = acknowledge
        task = asyncio.create_task(manager.register('gm', abandoned, welcome={'type': 'auth', 'status': 'ok'}))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(manager.websockets, {})
        await asyncio.wait_for(manager.register('gm', replacement, welcome={'type': 'auth', 'status': 'ok'}), 1)
        self.assertIs(manager.websockets['gm'], replacement)

    async def test_credentials_cannot_cross_authentication_roles(self):
        browser_as_basic = base64.b64encode(f'{AUTH.basic_username}:{AUTH.bridge_token}'.encode()).decode()
        basic_as_browser = base64.b64encode(f'{AUTH.basic_username}:{AUTH.basic_password}'.encode()).decode()
        manager = AsyncMock()
        with patch.object(main, 'settings', AUTH), patch.object(main, 'foundry_manager', manager):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
                for header in ['Basic ' + browser_as_basic, 'Bearer ' + AUTH.bridge_token]:
                    response = await client.post('/mcp/mcp', headers={'Authorization': header})
                    self.assertEqual(response.status_code, 401)
            for credential in [AUTH.basic_password, basic_as_browser, 'Basic ' + basic_as_browser]:
                socket = AsyncMock()
                socket.receive_text.return_value = json.dumps({'type': 'auth', 'token': credential})
                await main.foundry_ws(socket)
                socket.close.assert_awaited_once_with(code=1008)
            manager.register.assert_not_awaited()
            manager.handle_incoming.assert_not_awaited()

    async def test_server_diagnostics_and_auth_errors_do_not_echo_credentials(self):
        encoded = base64.b64encode(f'{AUTH.basic_username}:{AUTH.basic_password}'.encode()).decode()
        socket = AsyncMock()
        socket.receive_text.side_effect = [json.dumps({'type': 'auth', 'token': AUTH.bridge_token}), WebSocketDisconnect()]
        with patch.object(main, 'settings', AUTH), patch.object(main, 'foundry_manager', FoundryConnectionManager()):
            with self.assertLogs(level='INFO') as recorded:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
                    response = await client.post('/mcp/mcp', headers={'Authorization': 'Bearer ' + encoded})
                await main.foundry_ws(socket)
            diagnostic = '\n'.join(recorded.output) + response.text
            for credential in [AUTH.basic_password, AUTH.bridge_token, encoded]:
                self.assertNotIn(credential, diagnostic)
            self.assertIn('connected', diagnostic)
            self.assertEqual(response.status_code, 401)

class ProductionConfigurationTests(unittest.TestCase):
    def test_valid_and_fail_closed_configuration(self):
        env={'FOUNDRY_MCP_AUTH_MODE':'basic','FOUNDRY_MCP_BASIC_USERNAME':'librechat','FOUNDRY_MCP_BASIC_PASSWORD':'p'*32,'FOUNDRY_MCP_BRIDGE_TOKEN':'t'*32}
        with patch.dict(os.environ,env,clear=True):
            self.assertEqual(Settings.from_env().auth_mode,'basic')
        for key,value in [('FOUNDRY_MCP_AUTH_MODE','bad'),('FOUNDRY_MCP_AUTH_MODE','none'),('FOUNDRY_MCP_BASIC_USERNAME',''),('FOUNDRY_MCP_BASIC_USERNAME','bad:name'),('FOUNDRY_MCP_BASIC_PASSWORD','short'),('FOUNDRY_MCP_BRIDGE_TOKEN','p'*32),('FOUNDRY_MCP_BRIDGE_TOKEN','é'*32),('FOUNDRY_MCP_DEV_EXECUTION','true')]:
            with self.subTest(key=key,value=value),patch.dict(os.environ,{**env,key:value},clear=True):
                with self.assertRaises(ValueError): Settings.from_env()
