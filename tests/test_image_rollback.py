"""Bounded catalog and retained image workflow audit through actual MCP calls."""
import json
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import httpx2 as httpx
from fastmcp import Client

from foundry_mcp_server import main
from foundry_mcp_server.mcp_server.server import mcp
from foundry_mcp_server.mcp_server.tools import register_foundry_manager


class ImageRollbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_audit_is_bounded_and_checks_removed_routes(self):
        spec = importlib.util.spec_from_file_location('rollback_check',
            Path(__file__).resolve().parent.parent / 'scripts/image-rollback-check.py')
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        client, http = AsyncMock(), AsyncMock()
        client.list_tools.return_value = [SimpleNamespace(name=name) for name in
            ('browse_journal_images', 'write_journal', 'upload_image', 'create_image_directory')]
        client.call_tool.side_effect = [
            SimpleNamespace(structured_content=dict(module_status='connected',
                server=dict(version=checker.VERSION), module=dict(version=checker.VERSION))),
            SimpleNamespace(structured_content=dict(entries=[], complete=True)),
            SimpleNamespace(is_error=False)]
        http.request.return_value = SimpleNamespace(status_code=404)
        self.assertEqual((await checker.check(client, http))['requests'], 8)
        self.assertEqual(client.list_tools.await_count + client.call_tool.await_count +
                         http.request.await_count, 8)
        self.assertEqual(client.call_tool.await_args_list[1].args,
                         ('browse_journal_images', {'limit': 1}))
        client.list_tools.return_value.append(SimpleNamespace(name='get_foundry_image_url'))
        client.call_tool.reset_mock()
        with self.assertRaises(AssertionError):
            await checker.check(client, http)
        client.call_tool.assert_not_awaited()

    async def test_bounded_discovery_and_retained_image_workflow(self):
        manager = AsyncMock()
        register_foundry_manager(manager)
        image = dict(kind='image', name='map.png', name_truncated=False,
                     image=dict(source='data', directory='assets', src='assets/map.png'))
        manager.call.return_value = dict(
            location=dict(source='data', directory='assets'),
            sources=[dict(source='data'), dict(source='public')],
            capabilities=dict(can_upload=True, can_create_directory=True, reasons=[]),
            revision='audit', entries=[image], total=1, unfiltered_total=1,
            complete=True, next_cursor=None, limitations=['One directory.'])
        async with Client(mcp, timeout=10, init_timeout=5) as client:
            catalog = (await client.session.list_tools()).model_dump(
                mode='json', by_alias=True, exclude_none=True)
            names = {tool['name'] for tool in catalog['tools']}
            self.assertTrue({'get_foundry_image_info', 'get_foundry_image_url',
                             'browse_maps', 'get_map_info'}.isdisjoint(names))
            self.assertTrue({'browse_journal_images', 'write_journal',
                             'upload_image', 'create_image_directory'} <= names)
            result = await client.call_tool('browse_journal_images', dict(directory='assets'))
        compact = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())
        self.assertEqual(result.structured_content, manager.call.return_value)
        manager.call.assert_awaited_once()
        print(json.dumps(dict(audit='image-rollback', tool_count=len(catalog['tools']),
                              catalog_bytes=compact(catalog), calls=2,
                              response_bytes=compact(result.structured_content),
                              complete=result.structured_content['complete'])))

    async def test_preview_delivery_routes_are_removed(self):
        async with main.app.router.lifespan_context(main.app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url='http://test', timeout=10,
        ) as client:
            for path in ('/image-previews', '/image-previews/00000000-0000-4000-8000-000000000000.png'):
                for method in ('GET', 'HEAD'):
                    with self.subTest(path=path, method=method):
                        response = await client.request(method, path)
                        self.assertEqual(response.status_code, 404)
