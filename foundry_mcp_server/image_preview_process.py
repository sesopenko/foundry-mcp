"""Internal validated preview subprocess operations with resource supervision."""
import asyncio
from dataclasses import asdict,dataclass,field
import json
from pathlib import Path
import sys
import tempfile
import struct
from typing import Literal

from pydantic import Field, model_validator

from . import image_preview_limits as limits
from .image_preview_failure import PreviewFailure
from .image_preview_supervisor import current_supervisor
from .image_preview_resources import WorkerMetrics
from .image_preview_artifact import inspect_artifact
from .mcp_server.selective_models import Model
from .mcp_server.image_preview_models import Crop

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
    error_code: Literal['UnsupportedImage','ImageTooLarge','ImageProcessingFailed','InvalidOperation','InvalidCrop']
    width: int | None = Field(default=None,ge=1,le=2**32-1)
    height: int | None = Field(default=None,ge=1,le=2**32-1)

    @model_validator(mode='after')
    def known_dimensions(self):
        if (self.width is None) != (self.height is None):
            raise ValueError('Incomplete dimensions')
        return self


class RegionGeometry(Model):
    source: ProbeMetadata
    region: Crop
    width: int = Field(ge=1,le=limits.OUTPUT_MAX_EDGE)
    height: int = Field(ge=1,le=limits.OUTPUT_MAX_EDGE)

    @model_validator(mode='after')
    def contained(self):
        if (self.region.x+self.region.width>self.source.width
                or self.region.y+self.region.height>self.source.height
                or self.width>self.region.width or self.height>self.region.height
                or self.width*self.height>limits.OUTPUT_MAX_PIXELS):
            raise ValueError('Invalid region geometry')
        return self


class RegionReply(Model):
    geometry: RegionGeometry


class EncodedGeometry(RegionGeometry):
    mime_type: Literal['image/png','image/webp']
    size_bytes: int = Field(ge=1,le=limits.OUTPUT_MAX_BYTES)


class EncodedReply(Model):
    artifact: EncodedGeometry


@dataclass
class RenderedPreview:
    geometry: EncodedGeometry
    data: bytes = field(repr=False)


@dataclass
class RegionPixels:
    geometry: RegionGeometry
    png: bytes = field(repr=False)


def worker_reply(raw):
    """Validate allowlisted worker failures before any operation-specific result."""
    reply = json.loads(raw)
    if isinstance(reply,dict) and 'error_code' in reply:
        failure = FailureReply.model_validate(reply)
        raise PreviewFailure(failure.error_code,failure.width,failure.height)
    return reply


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
        reply = worker_reply(raw)
        result = ProbeReply.model_validate(reply).metadata
        if result.size_bytes != path.stat().st_size:
            raise PreviewFailure('ImageProcessingFailed')
        return result
    except (ValueError,TypeError,OSError):
        raise PreviewFailure('ImageProcessingFailed') from None


async def render_region(path, crop=None, *, supervisor=None,metrics=None,timeout=limits.WORKER_TIMEOUT_SECONDS):
    """Private lossless geometry intermediate; no public2MiB encoding promise yet.

    A trusted collector reads only fixed region.png after worker close, inside
    the owned scratch lifetime. Returned pixels never cross MCP or debug repr.
    Parent checks technical geometry and PNG header without decoding pixels.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PreviewFailure('UnsupportedImage')
    if isinstance(crop,Crop):
        crop = crop.model_dump()
    payload = json.dumps(dict(operation='region',source=str(path),crop=crop)).encode()
    def collect(workspace, raw):
        geometry = RegionReply.model_validate(worker_reply(raw)).geometry
        if geometry.source.size_bytes!=path.stat().st_size:
            raise PreviewFailure('ImageProcessingFailed')
        artifact = workspace.path/'region.png'
        if artifact.is_symlink() or not artifact.is_file():
            raise PreviewFailure('ImageProcessingFailed')
        # Private8bit RGBA intermediate, bounded by raster size plus PNG overhead.
        maximum = limits.OUTPUT_MAX_PIXELS*4+65536
        with artifact.open('rb') as stream:
            data = stream.read(maximum+1)
        if (len(data)>maximum or len(data)<33 or data[:8]!=b'\x89PNG\r\n\x1a\n'
                or data[12:16]!=b'IHDR' or struct.unpack('>II',data[16:24])!=(geometry.width,geometry.height)):
            raise PreviewFailure('ImageProcessingFailed')
        return RegionPixels(geometry,data)
    try:
        return await (supervisor or current_supervisor()).run(payload,metrics=metrics,timeout=timeout,collect=collect)
    except (ValueError,TypeError,OSError):
        raise PreviewFailure('ImageProcessingFailed') from None


async def render_preview(path, crop=None, *, supervisor=None,metrics=None,timeout=limits.WORKER_TIMEOUT_SECONDS):
    """Return a fully bounded private PNG/WebP artifact; publication is separate.

    Worker forces pixel decoding and verifies format/geometry/size. Parent repeats
    strict metadata and bounded container checks without loading a raster.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PreviewFailure('UnsupportedImage')
    if isinstance(crop,Crop):crop = crop.model_dump()
    payload = json.dumps(dict(operation='render',source=str(path),crop=crop)).encode()
    def collect(workspace,raw):
        geometry = EncodedReply.model_validate(worker_reply(raw)).artifact
        if geometry.source.size_bytes!=path.stat().st_size:
            raise PreviewFailure('ImageProcessingFailed')
        artifact = workspace.path/'preview.bin'
        if artifact.is_symlink() or not artifact.is_file():
            raise PreviewFailure('ImageProcessingFailed')
        with artifact.open('rb') as stream:
            data = stream.read(limits.OUTPUT_MAX_BYTES+1)
        actual = inspect_artifact(data)
        if actual!={key:getattr(geometry,key) for key in ('width','height','mime_type','size_bytes')}:
            raise PreviewFailure('ImageProcessingFailed')
        return RenderedPreview(geometry,data)
    try:
        return await (supervisor or current_supervisor()).run(payload,metrics=metrics,timeout=timeout,collect=collect)
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
