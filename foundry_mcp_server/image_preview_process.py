"""Internal validated preview subprocess operations with resource supervision."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
from typing import Literal

from pydantic import Field, model_validator

from . import image_preview_limits as limits
from .image_preview_worker import PreviewFailure
from .image_preview_supervisor import current_supervisor
from .image_preview_resources import WorkerMetrics
from .mcp_server.selective_models import Model

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


async def probe_image(path, *, timeout=limits.WORKER_TIMEOUT_SECONDS, supervisor=None, metrics=None):
    """Return validated header metadata, or a fixed-category PreviewFailure.

    Private staged input only. Stdout is limited while reading, stderr discarded,
    deadline enforced and child killed/reaped on every exit including cancellation.
    Native scratch is private and separate from the original. No public tools.
    """
    path = Path(path)
    payload = json.dumps({'operation':'probe','source':str(path)}).encode()
    if len(payload) > 8192 or path.is_symlink() or not path.is_file():
        raise PreviewFailure('UnsupportedImage')
    try:
        raw = await (supervisor or current_supervisor()).run(payload,timeout=timeout,metrics=metrics)
        reply = json.loads(raw)
        if isinstance(reply,dict) and 'error_code' in reply:
            failure = FailureReply.model_validate(reply)
            raise PreviewFailure(failure.error_code,failure.width,failure.height)
        result = ProbeReply.model_validate(reply).metadata
        if result.size_bytes != path.stat().st_size:
            raise PreviewFailure('ImageProcessingFailed')
        return result
    except (ValueError,TypeError,OSError):
        raise PreviewFailure('ImageProcessingFailed') from None


async def smoke():
    """Trusted package smoke: actual supervised probe and private measurements."""
    import os
    from PIL import Image
    metrics = WorkerMetrics()
    with tempfile.TemporaryDirectory(prefix='preview-supervisor-smoke-') as directory:
        path = Path(directory)/'original'
        Image.new('RGB',(16,12),(20,50,100)).save(path,format='PNG')
        metadata = await probe_image(path,metrics=metrics)
    return dict(uid=os.getuid(),probe=metadata.model_dump(),metrics=asdict(metrics))


if __name__ == '__main__':
    if sys.argv[1:] != ['--smoke']:
        raise SystemExit('Use --smoke for a private package verification')
    print(json.dumps(asyncio.run(smoke()),separators=(',',':')))
