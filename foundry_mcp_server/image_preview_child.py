"""Own one preview subprocess, its pipes and its complete termination lifecycle."""
import asyncio
import sys

from .image_preview_worker import PreviewFailure

MAX_OUTPUT_BYTES = 4096
MAX_REQUEST_BYTES = 8192


async def settle(task):
    """Finish owned work despite repeated cancellation, then report cancellation."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    return task.result(),cancelled


class PreviewChild:
    def __init__(self, environment, *, spawn=None):
        self.environment = environment
        self._spawn = spawn or asyncio.create_subprocess_exec
        self.process = None
        self._exchange = self._completion = self._closing = None

    @property
    def pid(self):
        return self.process.pid

    async def start(self):
        """Retain ownership even when cancellation arrives during OS spawn."""
        if self.process is not None:
            raise PreviewFailure('InvalidOperation')
        self.process,cancelled = await settle(asyncio.create_task(self._spawn(
            sys.executable,'-m','foundry_mcp_server.image_preview_worker',
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,env=self.environment,limit=MAX_OUTPUT_BYTES)))
        self._completion = asyncio.create_task(self.process.wait())
        if cancelled:
            raise asyncio.CancelledError

    def exchange(self, payload):
        """Start the sole bounded reader; ownership remains with this child."""
        if self.process is None or self._exchange is not None:
            raise PreviewFailure('InvalidOperation')
        if not isinstance(payload,bytes) or len(payload)>MAX_REQUEST_BYTES:
            raise PreviewFailure('InvalidOperation')
        self._exchange = asyncio.create_task(self._communicate(payload))
        return self._exchange

    async def _communicate(self, payload):
        self.process.stdin.write(payload)
        await self.process.stdin.drain()
        self.process.stdin.close()
        chunks,count = [],0
        while chunk := await self.process.stdout.read(min(1024,MAX_OUTPUT_BYTES+1-count)):
            count += len(chunk)
            if count>MAX_OUTPUT_BYTES:
                raise PreviewFailure('ImageProcessingFailed')
            chunks.append(chunk)
        await asyncio.shield(self._completion)
        if self.process.returncode != 0:
            raise PreviewFailure('ImageProcessingFailed')
        return b''.join(chunks)

    async def wait_finished(self, timeout):
        """Confirm owned wait completion without cancelling it on observation timeout."""
        done,_ = await asyncio.wait({self._completion},timeout=timeout)
        if done:
            self._completion.result()
        return bool(done)

    async def _close(self):
        if self.process.returncode is None:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
        if self._exchange is not None:
            self._exchange.cancel()
            await asyncio.gather(self._exchange,return_exceptions=True)
        # A paused PIPE can keep asyncio's pending Process.wait unresolved even
        # after SIGKILL. Cancel its sole reader, drain, then finish owned wait.
        while await self.process.stdout.read(4096):
            pass
        await self._completion

    async def close(self):
        """Idempotent kill/drain/reap, completed before propagating cancellation."""
        if self.process is None:
            return
        if self._closing is None:
            self._closing = asyncio.create_task(self._close())
        _,cancelled = await settle(self._closing)
        if cancelled:
            raise asyncio.CancelledError
