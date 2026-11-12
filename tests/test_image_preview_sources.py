"""Caller-bound original lifetime/quota/leases; no game assets or decoder."""
import asyncio
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from fastmcp.exceptions import ToolError

from foundry_mcp_server.auth.principal import Principal
from foundry_mcp_server.image_preview_sources import SourceSnapshots
from foundry_mcp_server.image_preview_transfer import StagedOriginal, OriginalContext
from foundry_mcp_server.mcp_server.journal_image_models import ImageSelector
from foundry_mcp_server.ws.connection import RpcError

IMAGE = ImageSelector(source='data', directory='assets', src='assets/a.png')


class Backend:
    def __init__(self):
        self.websockets = {'gm': object()}
        self.data = b'first'
        self.world = 'test'
        self.user = 'gm'
        self.transfers = self.writes = 0
        self.calls = []
        self.staged = []
        self.after_reserve = self.validate_hook = None
        self.bad_size = False

    async def transfer(self, manager, request, *, directory, admit_size, **_):
        self.transfers += 1
        socket = self.websockets.get('gm')
        await admit_size(len(self.data))
        if self.after_reserve:
            await self.after_reserve()
        folder = Path(tempfile.mkdtemp(dir=directory))
        path = folder / 'original'
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(self.data)
        self.writes += 1
        original = StagedOriginal(path, folder, hashlib.sha256(self.data).hexdigest(), len(self.data)+(1 if self.bad_size else 0),
            OriginalContext(socket, self.world, self.user, IMAGE.model_copy(deep=True), 'complete', ()))
        self.staged.append(original)
        return original

    async def call(self, client_id, method, params, timeout):
        assert method == 'validateImagePreviewSource'
        self.calls.append((self.websockets.get(client_id), params))
        if self.validate_hook:
            await self.validate_hook()
        return dict(world_id=self.world, user_id=self.user, image=IMAGE.model_dump(exclude_none=True), scope_status='complete', limitations=[])


class SourceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = Backend()
        self.time = 1000
        self.identity = Principal('oauth','https://issuer.example/','gm-one','client-one')
        self.caches = []
        self.cache = self.make_cache()

    def make_cache(self, **kwargs):
        cache = SourceSnapshots(principal=lambda:self.identity, transfer=self.backend.transfer, clock=lambda:self.time, **kwargs)
        self.caches.append(cache)
        self.addAsyncCleanup(cache.close)
        return cache

    async def stage(self, cache=None):
        return await (cache or self.cache).stage(self.backend, {'image':IMAGE.model_dump(exclude_none=True)})

    async def test_fresh_stage_and_replaced_source_keep_pinned_bytes_and_digest(self):
        first = await self.stage()
        self.assertEqual(datetime.fromisoformat(first.source_expires_at).timestamp(), 2800)
        self.backend.data = b'replacement'
        async with self.cache.lease(self.backend, first.source_id) as lease:
            self.assertEqual(lease.original.path.read_bytes(), b'first')
            self.assertEqual(lease.original.sha256, hashlib.sha256(b'first').hexdigest())
            await lease.recheck()
        self.assertEqual(self.backend.transfers, 1)
        second = await self.stage()
        self.assertNotEqual(first.source_id, second.source_id)
        async with self.cache.lease(self.backend, second.source_id) as lease:
            self.assertEqual(lease.original.path.read_bytes(), b'replacement')
        self.assertEqual(self.backend.transfers, 2)
        self.assertEqual(self.cache.used_bytes, len(b'firstreplacement'))

    async def test_principal_subject_client_and_issuer_isolation_before_membership_reads(self):
        receipt = await self.stage()
        original = self.identity
        for other in [Principal('oauth',original.issuer,'other',original.client_id),
                Principal('oauth',original.issuer,original.subject,'other'),
                Principal('oauth','https://other.example/',original.subject,original.client_id),
                Principal('basic','',original.subject,'configured-account')]:
            self.identity = other
            with self.assertRaisesRegex(ToolError,'SourceUnavailable'):
                async with self.cache.lease(self.backend,receipt.source_id):
                    self.fail('cross-principal lease')
        self.assertFalse(self.backend.calls)
        self.identity = original
        async with self.cache.lease(self.backend,receipt.source_id):
            pass

    async def test_exact_expiry_leases_protect_active_worker_file_and_block_new_use(self):
        cache = self.make_cache(max_bytes=5)
        receipt = await self.stage(cache)
        self.time = 2799.999
        async with cache.lease(self.backend,receipt.source_id) as lease:
            self.time = 2800
            await cache.prune()
            self.assertTrue(lease.original.path.exists())
            self.assertEqual(cache.used_bytes, 5)
            with self.assertRaisesRegex(ToolError,'SourceUnavailable'):
                async with cache.lease(self.backend,receipt.source_id):
                    self.fail('expired lease')
            with self.assertRaisesRegex(ToolError,'SourceCacheFull'):
                await self.stage(cache)
            with self.assertRaisesRegex(ToolError,'SourceUnavailable'):
                await lease.recheck()
        self.assertFalse(lease.original.path.exists())
        self.assertEqual(cache.used_bytes, 0)
        await self.stage(cache)

    async def test_capacity_reserves_before_file_creation_never_evicts_valid_handles(self):
        cache = self.make_cache(max_bytes=8)
        gate, started = asyncio.Event(), asyncio.Event()
        async def wait():
            started.set()
            await gate.wait()
        self.backend.after_reserve = wait
        task = asyncio.create_task(self.stage(cache))
        await started.wait()
        self.assertEqual(cache.used_bytes, 5)
        with self.assertRaisesRegex(ToolError,'SourceCacheFull'):
            await self.stage(cache)
        self.assertEqual(self.backend.writes,0)
        gate.set()
        receipt = await task
        self.assertEqual(cache.used_bytes,5)
        self.backend.after_reserve = None
        async with cache.lease(self.backend,receipt.source_id) as lease:
            self.assertEqual(lease.original.path.read_bytes(),b'first')
        self.time = 2800
        await self.stage(cache)
        self.assertEqual(cache.used_bytes,5)

    async def test_failed_transfer_admission_changed_identity_and_cancelled_staging_cleanup(self):
        self.backend.bad_size = True
        with self.assertRaisesRegex(ToolError,'InvalidFoundryResponse'):
            await self.stage()
        self.assertEqual(self.cache.used_bytes,0)
        self.assertEqual(list(self.cache.directory.iterdir()),[])
        self.backend.bad_size = False
        async def changed():
            self.identity = Principal('oauth','https://issuer.example/','other','client-one')
        self.backend.after_reserve = changed
        with self.assertRaisesRegex(ToolError,'AuthenticatedContextRequired'):
            await self.stage()
        self.assertEqual(self.cache.used_bytes,0)
        self.assertEqual(list(self.cache.directory.iterdir()),[])
        started = asyncio.Event()
        async def wait():
            started.set()
            await asyncio.Event().wait()
        self.backend.after_reserve = wait
        task=asyncio.create_task(self.stage())
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(self.cache.used_bytes,0)
        self.assertEqual(list(self.cache.directory.iterdir()),[])

    async def test_context_loss_reconnect_revalidation_and_denied_membership(self):
        receipt = await self.stage()
        self.backend.websockets['gm'] = object()
        async with self.cache.lease(self.backend,receipt.source_id):
            pass # same authorized world/GM may revalidate on a replacement socket
        for field in ('world','user'):
            old = getattr(self.backend,field)
            setattr(self.backend,field,'other')
            with self.assertRaisesRegex(ToolError,'SourceContextLost'):
                async with self.cache.lease(self.backend,receipt.source_id):self.fail('context changed')
            setattr(self.backend,field,old)
        async def denied():raise RpcError(dict(code='ImageNotFound',message='private source'))
        self.backend.validate_hook=denied
        with self.assertRaisesRegex(ToolError,'SourceContextLost'):
            async with self.cache.lease(self.backend,receipt.source_id):self.fail('denied membership')
        self.backend.validate_hook=None
        async with self.cache.lease(self.backend,receipt.source_id) as lease:
            self.backend.websockets['gm']=object()
            with self.assertRaisesRegex(ToolError,'SourceContextLost'):await lease.recheck()
            # Restore its current owner so normal context exit can complete.
            self.backend.websockets['gm']=self.backend.calls[-1][0]

    async def test_expiry_during_membership_check_never_yields_a_new_lease(self):
        receipt = await self.stage()
        async def expire():self.time=2800
        self.backend.validate_hook=expire
        with self.assertRaisesRegex(ToolError,'SourceUnavailable'):
            async with self.cache.lease(self.backend,receipt.source_id):self.fail('expired during check')
        self.assertEqual(self.cache.used_bytes,0)

    async def test_close_discard_restart_and_missing_authenticated_context(self):
        receipt = await self.stage()
        async with self.cache.lease(self.backend,receipt.source_id) as lease:
            await self.cache.close()
            self.assertTrue(lease.original.path.exists())
            with self.assertRaisesRegex(ToolError,'SourceUnavailable'):await lease.recheck()
        self.assertFalse(self.cache.directory.exists())
        restarted = self.make_cache()
        with self.assertRaisesRegex(ToolError,'SourceUnavailable'):
            async with restarted.lease(self.backend,receipt.source_id):self.fail('old process handle')
        new = await self.stage(restarted)
        await restarted.discard(new.source_id)
        self.assertEqual(restarted.used_bytes,0)
        self.identity=None
        with self.assertRaisesRegex(ToolError,'AuthenticatedContextRequired'):await self.stage(restarted)

    async def test_real_assembly_reservation_rejects_capacity_before_any_chunk_or_file(self):
        from test_image_preview_transfer import Browser
        browser=Browser()
        cache=SourceSnapshots(principal=lambda:self.identity,max_bytes=2)
        self.addAsyncCleanup(cache.close)
        with self.assertRaisesRegex(ToolError,'SourceCacheFull'):
            await cache.stage(browser,{'image':IMAGE.model_dump(exclude_none=True)})
        self.assertEqual(cache.used_bytes,0)
        self.assertEqual(list(cache.directory.iterdir()),[])
        self.assertFalse(any(method=='readImagePreviewChunk' for _,method,*_ in browser.calls))
        self.assertFalse(browser.browser_active)

    async def test_cancelled_membership_releases_lease_and_closed_cache_root(self):
        receipt=await self.stage()
        started=asyncio.Event()
        async def wait():
            started.set()
            await asyncio.Event().wait()
        self.backend.validate_hook=wait
        async def use():
            async with self.cache.lease(self.backend,receipt.source_id):self.fail('should remain pending')
        task=asyncio.create_task(use())
        await started.wait()
        await self.cache.close()
        self.assertTrue(self.backend.staged[0].path.exists())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(self.cache.directory.exists())

    async def test_private_context_factory_uses_admission_receipt_and_lifetime(self):
        @dataclass(frozen=True,repr=False)
        class Context:
            source_id: str
            expiry: str
            sentinel: str
        async def validate(original):
            self.assertTrue(original.path.exists())
            self.time=1100
            return lambda receipt:Context(receipt.source_id,receipt.source_expires_at,'private-map-sentinel')
        receipt=await self.cache.stage(self.backend,{'image':IMAGE.model_dump(exclude_none=True)},validate_original=validate)
        self.assertEqual(datetime.fromisoformat(receipt.source_expires_at).timestamp(),2900)
        self.assertEqual(set(receipt.model_dump()),{'source_id','source_expires_at'})
        async with self.cache.lease(self.backend,receipt.source_id) as lease:
            context=lease.private_context
            self.assertEqual((context.source_id,context.expiry),(receipt.source_id,receipt.source_expires_at))
            self.assertNotIn('private-map-sentinel',repr(lease))
            with self.assertRaises(AttributeError):context.source_id='other'
        self.time=2900;await self.cache.prune()
        self.assertEqual(self.cache.used_bytes,0)
        self.assertEqual(list(self.cache.directory.iterdir()),[])

    async def test_private_context_factory_failure_admits_nothing_and_cleans_staging(self):
        def fail(receipt):raise RuntimeError('deliberate private factory failure')
        async def validate(original):return fail
        with self.assertRaisesRegex(RuntimeError,'deliberate private factory failure'):
            await self.cache.stage(self.backend,{'image':IMAGE.model_dump(exclude_none=True)},validate_original=validate)
        self.assertEqual(self.cache.used_bytes,0)
        self.assertEqual(list(self.cache.directory.iterdir()),[])
        receipt=await self.stage()
        async with self.cache.lease(self.backend,receipt.source_id) as lease:
            self.assertIsNone(lease.private_context)
