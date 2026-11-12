"""Derivative-store lifecycle, threaded operations and trusted issuance policy.

Independent of browser snapshots/rendering. Anonymous lookup has no GM dependency.
No issuance MCP tool is registered here; task11 composes authenticated issuance.
"""
import asyncio
import logging

from .image_preview_child import settle
from .image_preview_failure import PreviewFailure
from .image_preview_store import PreviewStore,StoreFailure

logger = logging.getLogger('foundry_mcp.image_previews')


class PreviewRuntime:
    def __init__(self,*,store_factory=PreviewStore,prune_interval=60):
        self.store_factory,self.prune_interval = store_factory,prune_interval
        self.store = self.pruner = self._closing = None
        self.pending = set()
        self.origin = ''
        self.issuance_enabled = False
        self.closing = True

    async def start(self,settings):
        if self.store is not None:raise StoreFailure()
        self._closing = None
        self.closing = False
        self.origin = settings.image_preview_origin
        self.issuance_enabled = settings.image_preview_issuance_enabled
        if not self.origin:return
        # Assign ownership before propagating cancellation of threaded setup.
        task = asyncio.create_task(asyncio.to_thread(self.store_factory,settings.image_preview_data_dir))
        self.store,cancelled = await settle(task)
        if cancelled:
            await self.close()
            raise asyncio.CancelledError
        self.pruner = asyncio.create_task(self._prune_periodically())

    async def _call(self,operation,*args):
        if self.closing or self.store is None:raise StoreFailure()
        task = asyncio.create_task(asyncio.to_thread(operation,*args))
        self.pending.add(task)
        try:
            result,cancelled = await settle(task)
            if cancelled:raise asyncio.CancelledError
            return result
        finally:self.pending.discard(task)

    async def _prune_periodically(self):
        while True:
            await asyncio.sleep(self.prune_interval)
            try:await self._call(self.store.prune)
            except StoreFailure:
                # Lookup still independently enforces expiry. Report a fixed
                # storage failure; no exception text, token, origin or path.
                logger.error('PreviewStorageUnavailable: periodic preview cleanup failed')

    async def lookup(self,token,extension):
        if self.store is None or self.closing:return None
        return await self._call(self.store.lookup,token,extension)

    def require_issuance(self):
        if not self.issuance_enabled:raise PreviewFailure('PreviewNotConfigured')
        if self.store is None or self.closing:raise StoreFailure()

    async def publish(self,data,mime_type):
        """Internal trusted artifact publication; caller authorization is external."""
        self.require_issuance()
        return await self._call(self.store.publish,data,mime_type)

    def url(self,receipt):
        """Only trusted configured origin and store-created canonical path."""
        self.require_issuance()
        return f'{self.origin}/image-previews/{receipt.token}.{receipt.extension}'

    async def _close(self):
        self.closing = True
        if self.pruner is not None:
            self.pruner.cancel()
            await asyncio.gather(self.pruner,return_exceptions=True)
        if self.pending:
            await asyncio.gather(*tuple(self.pending),return_exceptions=True)
        if self.store is not None:self.store.close()
        self.store = self.pruner = None

    async def close(self):
        if self._closing is None:self._closing = asyncio.create_task(self._close())
        _,cancelled = await settle(self._closing)
        if cancelled:raise asyncio.CancelledError
