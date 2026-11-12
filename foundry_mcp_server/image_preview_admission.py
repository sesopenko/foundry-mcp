"""Preview-only bounded admission; no worker or filesystem dependencies."""
import asyncio
from contextlib import asynccontextmanager

from . import image_preview_limits as limits
from .image_preview_worker import PreviewFailure

MAX_QUEUED = 8


class PreviewAdmission:
    def __init__(self, *, max_queued=MAX_QUEUED, queue_timeout=limits.WORKER_TIMEOUT_SECONDS):
        self.max_queued = max_queued
        self.queue_timeout = queue_timeout
        self.queued = 0
        self._gate = asyncio.Semaphore(limits.WORKER_CONCURRENCY)

    @asynccontextmanager
    async def permit(self):
        """Release only an acquired permit; queued cancellation owns nothing."""
        if self._gate.locked() and self.queued >= self.max_queued:
            raise PreviewFailure('ImageProcessingBusy')
        self.queued += 1
        try:
            try:
                async with asyncio.timeout(self.queue_timeout):
                    await self._gate.acquire()
            except TimeoutError:
                raise PreviewFailure('ImageProcessingBusy') from None
        finally:
            self.queued -= 1
        try:
            yield
        finally:
            self._gate.release()
