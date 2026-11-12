"""Bounded private browser-to-file assembly; no public tool or caller cache.

The browser remains authoritative for file membership. The returned original
owns its private directory until close() or explicit handoff to the snapshot
service. Digests, selectors and filesystem paths must never enter MCP/logs.
"""
import asyncio
import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Literal
from uuid import uuid4

from fastmcp.exceptions import ToolError
from pydantic import Field, model_validator

from . import image_preview_limits as limits
from .mcp_server.image_preview_models import ImageInfoRequest
from .mcp_server.journal_image_models import ImageSelector
from .mcp_server.selective_models import Model
from .ws.connection import RpcError

UUID4 = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'


class BrowserContext(Model):
    world_id: str = Field(min_length=1, max_length=256)
    user_id: str = Field(min_length=1, max_length=256)


class BeginResult(BrowserContext):
    transfer_id: str = Field(pattern=UUID4)
    size_bytes: int = Field(ge=1, le=limits.SOURCE_MAX_BYTES)
    chunk_bytes: int = Field(ge=1, le=limits.CHUNK_MAX_BYTES)
    chunk_count: int = Field(ge=1, le=limits.SOURCE_MAX_BYTES)
    max_in_flight: int = Field(ge=1, le=limits.TRANSFER_WINDOW)
    image: ImageSelector
    scope_status: Literal['complete', 'partial']
    limitations: list[str] = Field(max_length=16)

    @model_validator(mode='after')
    def layout(self):
        if self.chunk_count != (self.size_bytes + self.chunk_bytes - 1) // self.chunk_bytes:
            raise ValueError('Invalid chunk coverage')
        if any(len(value) > 512 for value in self.limitations) or (self.scope_status == 'partial' and not self.limitations):
            raise ValueError('Invalid source coverage')
        return self


class ChunkResult(Model):
    transfer_id: str = Field(pattern=UUID4)
    index: int = Field(ge=0, le=limits.SOURCE_MAX_BYTES)
    offset: int = Field(ge=0, le=limits.SOURCE_MAX_BYTES)
    length: int = Field(ge=1, le=limits.CHUNK_MAX_BYTES)
    data_base64: str = Field(max_length=4*((limits.CHUNK_MAX_BYTES+2)//3))


@dataclass(frozen=True)
class TransferBounds:
    """Trusted test injection only; production defaults mirror browser limits."""
    read_seconds: float = limits.READ_TIMEOUT_SECONDS
    total_seconds: float = limits.TRANSFER_TIMEOUT_SECONDS
    cleanup_seconds: float = 3


@dataclass(frozen=True)
class OriginalContext:
    socket: object
    world_id: str
    user_id: str
    image: ImageSelector
    scope_status: str
    limitations: tuple[str, ...]


@dataclass
class StagedOriginal:
    """Private complete-file ownership. close() is idempotent; never serialize."""
    path: Path
    directory: Path
    sha256: str
    size_bytes: int
    context: OriginalContext
    _closed: bool = False

    def close(self):
        if not self._closed:
            shutil.rmtree(self.directory)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def failure(code):
    messages = {
        'BridgeUnavailable': 'Connect the existing ready GM browser and retry.',
        'ContextChanged': 'GM socket, world or user changed; start a fresh image request.',
        'ImageTransferTimeout': 'Private source transfer timed out; choose an available image and retry.',
        'InvalidFoundryResponse': 'Invalid private transfer response; check matching module/server versions and retry.',
        'ImageTooLarge': 'Original exceeds the128 MiB compressed limit; choose a smaller source.',
        'ImageUnavailable': 'Source is unavailable; browse_journal_images and choose a readable configured image.',
        'AmbiguousSource': 'Reference matches multiple readable sources; browse_journal_images on the parent and pass one exact image.',
        'BrowseFailed': 'Referenced parent is missing, denied or unavailable; no absence established. Use an exact image from browse_journal_images.',
        'ImageNotFound': 'Image no longer matches its parent listing; browse_journal_images again.',
        'PermissionDenied': 'Private source transfer requires the ready connected GM.',
        'NotReady': 'Wait for the existing connected GM world to become ready.',
        'InvalidRequest': 'Use exactly one supported image selector or stored src; check the published input schema.',
        'UnsupportedVersion': 'Private source transfer requires matching server/module on Foundry14.',
        'UnsupportedCapability': 'Check the public FilePicker API and matching module/core versions.',
        'DirectoryTooLarge': 'Choose a narrower known directory below10000 paths/2MiB of native listing data.',
        'SourceTooLarge': 'Reconcile configured S3 metadata below100 buckets or select an exact configured image.',
        'ResponseTooLarge': 'Private response exceeds the configured frame ceiling; check bridge response-size configuration.',
        'InvalidFrameLimit': 'Configure a supported bridge frame ceiling of1024–16777216 bytes.',
        'ImageTransferFailed': 'Private source staging failed; check local private-storage availability and retry.',
    }
    if not isinstance(code, str) or code not in messages:
        code = 'ImageTransferFailed'
    return ToolError(f'{code}: {messages[code]}')


def compact_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8'))


async def stage_original(manager, request, *, frame_bytes=65536, directory=None, bounds=TransferBounds(), admit_size=None):
    """Own one complete verified file, or leave no partial file/pending RPC.

    Capture the exact GM socket, obtain ready-world/GM identity before begin,
    and send a known random reservation so even lost/malformed begin responses
    can be released on that same socket. At most16 reads/32KiB each are active.
    Out-of-order responses are validated against their originating request;
    each bounded batch is written/hashed in index order. The caller MUST close
    the returned StagedOriginal, or transfer its ownership to a snapshot cache.
    admit_size, when supplied by that cache, reserves the validated byte count
    before any Python original file is created. It is never a client callback.
    """
    try:
        request = ImageInfoRequest.model_validate(request)
    except (ValueError, TypeError):
        raise failure('InvalidRequest') from None
    if type(frame_bytes) is not int or not 1024 <= frame_bytes <= 16777216:
        raise failure('InvalidFoundryResponse')
    socket = manager.websockets.get('gm')
    if socket is None:
        raise failure('BridgeUnavailable')
    reservation = str(uuid4())
    partial = None
    handed_off = False
    begun = False
    tasks = []

    def current():
        if manager.websockets.get('gm') is not socket:
            raise failure('ContextChanged')

    async def call(method, params, timeout):
        current()
        # No await between ownership check and manager.call capturing its socket.
        result = await manager.call('gm', method, params, timeout=timeout)
        current()
        return result

    async def release():
        if not begun or manager.websockets.get('gm') is not socket:
            return
        try:
            async with asyncio.timeout(bounds.cleanup_seconds):
                await call('releaseImagePreviewTransfer', {'transfer_id': reservation}, bounds.cleanup_seconds)
        except (TimeoutError, RpcError, ToolError, ConnectionError, RuntimeError, OSError):
            # Expected best-effort cleanup of an already-expired/disconnected
            # browser owner. Never contact a replacement socket or print errors.
            # The browser also releases on full coverage/owner close/5min expiry.
            return

    try:
        async with asyncio.timeout(bounds.total_seconds):
            context = BrowserContext.model_validate(await call('getImagePreviewContext', {}, bounds.read_seconds))
            begun = True
            raw = await call('beginImagePreviewTransfer', {**request.model_dump(exclude_none=True),
                'transfer_id': reservation, 'expected_context': context.model_dump(), 'max_frame_bytes': frame_bytes}, bounds.total_seconds)
            begin = BeginResult.model_validate(raw)
            if (begin.transfer_id != reservation or begin.world_id != context.world_id or begin.user_id != context.user_id
                    or compact_bytes({'id': 'x'*36, 'result': raw}) > frame_bytes):
                raise ValueError('Invalid begin witness')
            if request.image is not None and begin.image != request.image:
                raise ValueError('Canonical selector changed')
            if admit_size is not None:
                await admit_size(begin.size_bytes)
                current()
            partial = Path(tempfile.mkdtemp(prefix='foundry-image-source-', dir=directory))
            path = partial / 'original'
            digest = hashlib.sha256()
            written = 0

            async def read(index):
                offset = index*begin.chunk_bytes
                length = min(begin.chunk_bytes, begin.size_bytes-offset)
                args = dict(transfer_id=reservation, index=index, offset=offset, length=length)
                raw = await call('readImagePreviewChunk', args, bounds.read_seconds)
                part = ChunkResult.model_validate(raw)
                if (part.transfer_id != reservation or part.index != index or part.offset != offset or part.length != length
                        or compact_bytes({'id': 'x'*36, 'result': raw}) > frame_bytes):
                    raise ValueError('Invalid chunk witness')
                data = base64.b64decode(part.data_base64, validate=True)
                if len(data) != length or base64.b64encode(data).decode('ascii') != part.data_base64:
                    raise ValueError('Invalid chunk bytes')
                return data

            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as output:
                window = min(begin.max_in_flight, limits.TRANSFER_WINDOW)
                for start in range(0, begin.chunk_count, window):
                    tasks = [asyncio.create_task(read(index)) for index in range(start, min(start+window, begin.chunk_count))]
                    batch = await asyncio.gather(*tasks)
                    current()
                    for data in batch:
                        output.write(data)
                        digest.update(data)
                        written += len(data)
                    tasks = []
                if written != begin.size_bytes or output.tell() != begin.size_bytes:
                    raise ValueError('Incomplete source')
            current()
            result = StagedOriginal(path, partial, digest.hexdigest(), written,
                OriginalContext(socket, context.world_id, context.user_id, begin.image, begin.scope_status, tuple(begin.limitations)))
        handed_off = True
        return result
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        raise failure('ImageTransferTimeout') from None
    except RpcError as error:
        raise failure(error.error.get('code', error.error.get('type'))) from None
    except ToolError:
        raise
    except (ValueError, TypeError, UnicodeError):
        raise failure('InvalidFoundryResponse') from None
    except (ConnectionError, RuntimeError):
        raise failure('BridgeUnavailable') from None
    except OSError:
        raise failure('ImageTransferFailed') from None
    finally:
        try:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await release()
        except BaseException:
            # Cancellation during cleanup must propagate, and a file which
            # never reached its caller has not actually transferred ownership.
            handed_off = False
            raise
        finally:
            if partial is not None and not handed_off:
                shutil.rmtree(partial)
