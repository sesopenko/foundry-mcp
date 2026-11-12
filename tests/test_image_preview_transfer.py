"""Real multichunk bytes and bounded private-file ownership/fault checks."""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import unittest

from fastmcp.exceptions import ToolError

from foundry_mcp_server.image_preview_transfer import stage_original, TransferBounds
from foundry_mcp_server.ws.connection import FoundryConnectionManager, RpcError

IMAGE = dict(source='data', directory='assets', src='assets/a.png')


class Browser:
    def __init__(self, data=bytes(range(251))*600):
        self.data = data
        self.socket = object()
        self.websockets = {'gm': self.socket}
        self.calls = []
        self.active = self.peak = 0
        self.context = dict(world_id='test', user_id='gm')
        self.begin_patch = self.chunk_patch = None
        self.read_hook = self.begin_hook = self.release_hook = None
        self.browser_active = False
        self.finished = []

    async def result(self, method, params):
        if method == 'getImagePreviewContext':
            return self.context.copy()
        if method == 'beginImagePreviewTransfer':
            self.reservation = params['transfer_id']
            self.browser_active = True
            if self.begin_hook:
                await self.begin_hook(params)
            result = dict(transfer_id=self.reservation, size_bytes=len(self.data), chunk_bytes=32768,
                chunk_count=(len(self.data)+32767)//32768, max_in_flight=16, image=IMAGE,
                **self.context, scope_status='complete', limitations=[])
            return {**result, **(self.begin_patch or {})}
        if method == 'readImagePreviewChunk':
            self.active += 1
            self.peak = max(self.peak, self.active)
            try:
                if self.read_hook:
                    await self.read_hook(params)
                else:
                    await asyncio.sleep((3-params['index'] % 3)*0.001)
                self.finished.append(params['index'])
                data = self.data[params['offset']:params['offset']+params['length']]
                return {**params, 'data_base64': base64.b64encode(data).decode(), **(self.chunk_patch or {})}
            finally:
                self.active -= 1
        if method == 'releaseImagePreviewTransfer':
            if self.release_hook:
                await self.release_hook(params)
            self.browser_active = False
            return dict(released=True)
        raise AssertionError('Unexpected private method')

    async def call(self, client_id, method, params, timeout):
        self.calls.append((self.websockets.get(client_id), method, params, timeout))
        async with asyncio.timeout(timeout):
            return await self.result(method, params)


class TransferTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.browser = Browser()

    async def stage(self, **kwargs):
        return await stage_original(self.browser, {'image': IMAGE}, directory=self.directory, **kwargs)

    def assert_empty(self):
        self.assertEqual(list(self.directory.iterdir()), [])
        self.assertEqual(self.browser.active, 0)

    async def test_complete_private_file_hash_out_of_order_bytes_and_ownership_handoff(self):
        original = await self.stage()
        self.addCleanup(original.close)
        self.assertEqual(original.path.read_bytes(), self.browser.data)
        self.assertEqual(original.sha256, hashlib.sha256(self.browser.data).hexdigest())
        self.assertEqual(original.size_bytes, len(self.browser.data))
        self.assertIs(original.context.socket, self.browser.socket)
        self.assertEqual((original.context.world_id, original.context.user_id), ('test', 'gm'))
        self.assertEqual(original.context.image.model_dump(exclude_none=True), IMAGE)
        self.assertEqual(stat.S_IMODE(original.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(original.directory.stat().st_mode), 0o700)
        self.assertNotEqual(self.browser.finished, sorted(self.browser.finished))
        self.assertLessEqual(self.browser.peak, 16)
        self.assertFalse(self.browser.browser_active)
        begin = self.browser.calls[1]
        self.assertEqual(begin[2]['expected_context'], self.browser.context)
        self.assertEqual(self.browser.calls[-1][2]['transfer_id'], begin[2]['transfer_id'])
        original.close()
        original.close()
        self.assert_empty()

    async def test_sixteen_read_window_across_multiple_batches(self):
        self.browser = Browser(bytes(range(251))*3000)
        original = await self.stage()
        self.addCleanup(original.close)
        self.assertEqual(self.browser.peak, 16)
        self.assertEqual(original.path.read_bytes(), self.browser.data)
        self.assertEqual(len(self.browser.finished), (len(self.browser.data)+32767)//32768)

    async def test_invalid_begin_witnesses_release_known_reservation_without_partial_files(self):
        patches = [dict(size_bytes=True), dict(size_bytes=0), dict(size_bytes=134217729), dict(chunk_bytes=32769),
            dict(chunk_bytes=True), dict(chunk_count=2), dict(max_in_flight=17), dict(user_id='another'),
            dict(world_id='another'), dict(transfer_id='bad'), dict(extra='private'), dict(image={**IMAGE, 'src':'assets/other.png'}),
            dict(scope_status='partial', limitations=[])]
        for patch in patches:
            with self.subTest(fields=list(patch)):
                self.browser = Browser()
                self.browser.begin_patch = patch
                with self.assertRaisesRegex(ToolError, 'InvalidFoundryResponse'):
                    await self.stage()
                self.assertFalse(self.browser.browser_active)
                self.assertEqual(self.browser.calls[-1][1], 'releaseImagePreviewTransfer')
                self.assert_empty()

    async def test_missing_short_duplicate_overlap_invalid_base64_and_extra_chunk_fields_fail_closed(self):
        for patch in [dict(index=99), dict(index=True), dict(offset=1), dict(length=1), dict(data_base64='!'),
                dict(data_base64='AQ=='), dict(data_base64='é'), dict(data_base64=''), dict(extra='private'), dict(transfer_id='bad')]:
            with self.subTest(fields=list(patch)):
                self.browser = Browser()
                self.browser.chunk_patch = patch
                with self.assertRaisesRegex(ToolError, 'InvalidFoundryResponse'):
                    await self.stage()
                self.assertFalse(self.browser.browser_active)
                self.assert_empty()

    async def test_stalled_read_total_begin_timeout_and_cancellation_cleanup(self):
        for phase in ('read', 'begin', 'cancel'):
            with self.subTest(phase=phase):
                self.browser = Browser()
                started = asyncio.Event()

                async def wait(_):
                    started.set()
                    await asyncio.Event().wait()

                self.browser.read_hook = wait if phase != 'begin' else None
                self.browser.begin_hook = wait if phase == 'begin' else None
                bounds = TransferBounds(read_seconds=0.02 if phase == 'read' else 1, total_seconds=0.03 if phase == 'begin' else 2, cleanup_seconds=0.1)
                task = asyncio.create_task(self.stage(bounds=bounds))
                await started.wait()
                if phase == 'cancel':
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                else:
                    with self.assertRaisesRegex(ToolError, 'ImageTransferTimeout'):
                        await task
                self.assertFalse(self.browser.browser_active)
                self.assert_empty()

    async def test_replacement_socket_never_receives_stale_cleanup(self):
        async def replace(_):
            self.browser.websockets['gm'] = object()
        self.browser.read_hook = replace
        with self.assertRaisesRegex(ToolError, 'ContextChanged'):
            await self.stage()
        self.assertTrue(all(socket is self.browser.socket for socket, *_ in self.browser.calls))
        self.assertFalse(any(method == 'releaseImagePreviewTransfer' for _, method, *_ in self.browser.calls))
        self.assert_empty()

    async def test_browser_context_change_and_native_errors_are_sanitized(self):
        for kind in ('ContextChanged', 'unrecognized', {'private': 'secret'}):
            async def reject(_):
                raise RpcError(dict(code=kind, message='private path https://private.example/?signature=secret'))
            self.browser = Browser()
            self.browser.read_hook = reject
            with self.assertRaises(ToolError) as caught:
                await self.stage()
            self.assertNotIn('secret', str(caught.exception))
            self.assertNotIn('private.example', str(caught.exception))
            self.assert_empty()

    async def test_invalid_input_and_unavailable_bridge_fail_before_transfer(self):
        with self.assertRaisesRegex(ToolError, 'InvalidRequest') as caught:
            await stage_original(self.browser, {'image': IMAGE, 'private-secret': 'https://private.example/'}, directory=self.directory)
        self.assertNotIn('secret', str(caught.exception))
        self.assertFalse(self.browser.calls)
        self.browser.websockets.clear()
        with self.assertRaisesRegex(ToolError, 'BridgeUnavailable'):
            await self.stage()
        self.assert_empty()

    async def test_real_connection_manager_correlates_out_of_order_private_chunks(self):
        manager = FoundryConnectionManager()
        backend = self.browser
        responses = set()

        class Socket:
            async def send_text(socket, message):
                request = json.loads(message)

                async def respond():
                    try:
                        result = await backend.result(request['method'], request['params'])
                        await manager.handle_incoming(json.dumps({'id': request['id'], 'result': result}), socket)
                    finally:
                        responses.discard(asyncio.current_task())
                task = asyncio.create_task(respond())
                responses.add(task)
        socket = Socket()
        await manager.register('gm', socket)
        original = await stage_original(manager, {'image': IMAGE}, directory=self.directory)
        self.addCleanup(original.close)
        self.assertEqual(original.path.read_bytes(), backend.data)
        self.assertFalse(manager.pending)
        await asyncio.gather(*responses)
        self.assertFalse(responses)

    async def test_cancellation_during_release_does_not_swallow_cancellation_or_leak_unreturned_file(self):
        started = asyncio.Event()

        async def release(_):
            started.set()
            await asyncio.Event().wait()
        self.browser.release_hook = release
        task = asyncio.create_task(self.stage())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assert_empty()
