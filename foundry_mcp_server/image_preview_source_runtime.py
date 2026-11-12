"""Process-local original cache lifecycle, independent of public preview storage."""
import asyncio

from .image_preview_sources import SourceSnapshots, unavailable
from .image_preview_child import settle


class SourceRuntime:
    def __init__(self, *, factory=SourceSnapshots, prune_seconds=60):
        self._factory = factory
        self._prune_seconds = prune_seconds
        self.cache = None
        self._pruner = None
        self._closing = None

    async def start(self):
        if self.cache is not None:
            raise RuntimeError('Original cache already started')
        self.cache = self._factory()
        self._closing = None
        self._pruner = asyncio.create_task(self._prune())

    def require_cache(self):
        if self.cache is None or self._closing is not None:
            raise unavailable()
        return self.cache

    async def _prune(self):
        while True:
            await asyncio.sleep(self._prune_seconds)
            await self.cache.prune()

    async def _close(self):
        if self._pruner is not None:
            self._pruner.cancel()
            await asyncio.gather(self._pruner, return_exceptions=True)
            self._pruner = None
        if self.cache is not None:
            await self.cache.close()
            self.cache = None

    async def close(self):
        if self._closing is None:
            self._closing = asyncio.create_task(self._close())
        _,cancelled = await settle(self._closing)
        if cancelled:
            raise asyncio.CancelledError


source_runtime = SourceRuntime()
