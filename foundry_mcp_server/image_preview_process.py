"""Internal bounded preview subprocess wrapper;05b adds RSS/scratch admission."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Literal

from pydantic import Field, model_validator

from . import image_preview_limits as limits
from .image_preview_worker import PreviewFailure
from .mcp_server.selective_models import Model

MAX_OUTPUT_BYTES = 4096


class ProbeMetadata(Model):
    width: int = Field(ge=1,le=limits.SOURCE_MAX_EDGE)
    height: int = Field(ge=1,le=limits.SOURCE_MAX_EDGE)
    mime_type: Literal['image/jpeg','image/png','image/webp']
    size_bytes: int = Field(ge=1,le=limits.SOURCE_MAX_BYTES)
    frame_policy: Literal['still','first_frame']

    @model_validator(mode='after')
    def area(self):
        if self.width*self.height > limits.SOURCE_MAX_PIXELS:
            raise ValueError('Source pixel budget exceeded')
        return self


class ProbeReply(Model):
    metadata: ProbeMetadata


class FailureReply(Model):
    error_code: Literal['UnsupportedImage','ImageTooLarge','ImageProcessingFailed','InvalidOperation']
    width: int | None = Field(default=None,ge=1,le=2**32-1)
    height: int | None = Field(default=None,ge=1,le=2**32-1)

    @model_validator(mode='after')
    def known_dimensions(self):
        if (self.width is None) != (self.height is None):
            raise ValueError('Incomplete dimensions')
        return self


async def probe_image(path, *, timeout=limits.WORKER_TIMEOUT_SECONDS):
    """Return validated header metadata, or a fixed-category PreviewFailure.

    Private staged input only. Stdout is limited while reading, stderr discarded,
    deadline enforced and child killed/reaped on every exit including cancellation.
    Native scratch is private and separate from the original. No public tools.
    """
    path = Path(path)
    payload = json.dumps({'operation':'probe','source':str(path)}).encode()
    if len(payload) > 8192 or path.is_symlink() or not path.is_file():
        raise PreviewFailure('UnsupportedImage')
    with tempfile.TemporaryDirectory(prefix='foundry-preview-worker-') as scratch:
        environment = {**{key:value for key,value in os.environ.items() if not key.startswith(('FOUNDRY_MCP_','AUTH0_','AWS_'))},
            'VIPS_CONCURRENCY':'2','TMPDIR':scratch,'VIPS_TMPDIR':scratch,
            'VIPS_DISC_THRESHOLD':str(16*1024*1024),'XDG_CACHE_HOME':scratch}
        try:
            process = await asyncio.create_subprocess_exec(sys.executable,'-m','foundry_mcp_server.image_preview_worker',
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=environment)
        except OSError:
            raise PreviewFailure('ImageProcessingFailed') from None
        try:
            async with asyncio.timeout(timeout):
                process.stdin.write(payload)
                await process.stdin.drain()
                process.stdin.close()
                chunks, count = [], 0
                while chunk := await process.stdout.read(min(1024,MAX_OUTPUT_BYTES+1-count)):
                    count += len(chunk)
                    if count > MAX_OUTPUT_BYTES:
                        raise PreviewFailure('ImageProcessingFailed')
                    chunks.append(chunk)
                await process.wait()
            if process.returncode != 0:
                raise PreviewFailure('ImageProcessingFailed')
            reply = json.loads(b''.join(chunks))
            if isinstance(reply,dict) and 'error_code' in reply:
                failure = FailureReply.model_validate(reply)
                raise PreviewFailure(failure.error_code,failure.width,failure.height)
            result = ProbeReply.model_validate(reply).metadata
            if result.size_bytes != path.stat().st_size:
                raise PreviewFailure('ImageProcessingFailed')
            return result
        except asyncio.TimeoutError:
            raise PreviewFailure('ImageProcessingTimeout') from None
        except (ValueError,TypeError,OSError):
            raise PreviewFailure('ImageProcessingFailed') from None
        finally:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()
