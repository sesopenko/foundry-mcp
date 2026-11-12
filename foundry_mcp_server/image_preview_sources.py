"""Ephemeral caller-bound original snapshots, separate from public derivatives."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
from pathlib import Path
import re
import tempfile
import time
from uuid import uuid4

from fastmcp.exceptions import ToolError
from pydantic import Field

from . import image_preview_limits as limits
from .auth.principal import Principal, current_principal, denied
from .image_preview_transfer import BrowserContext, StagedOriginal, stage_original
from .mcp_server.image_preview_models import SourceReceipt
from .mcp_server.journal_image_models import ImageSelector
from .ws.connection import RpcError


class Membership(BrowserContext):
    image: ImageSelector
    scope_status: str = Field(pattern=r'^(complete|partial)$')
    limitations: list[str] = Field(max_length=16)


def unavailable():
    return ToolError('SourceUnavailable: original snapshot expired, is missing or belongs to another caller. Call get_foundry_image_info again using the original image/src selector.')


def context_lost():
    return ToolError('SourceContextLost: current GM/world/source membership could not be revalidated. Reconnect the ready authorized GM and call get_foundry_image_info again.')


@dataclass
class _Snapshot:
    source_id: str
    expiry: float
    principal: Principal
    original: StagedOriginal
    leases: int = 0
    retired: bool = False


@dataclass(frozen=True)
class SourceLease:
    """Private input-file lease; recheck() immediately before new publication.

    Protects the original file during async worker use. Never serialize path,
    digest or context. Public receipt contains only source_id/source_expires_at.
    """
    receipt: SourceReceipt
    original: StagedOriginal
    recheck: object


class SourceSnapshots:
    """512-MiB,30-minute process-local cache; no eviction of valid handles.

    Identity/transfer/clock injection is trusted constructor-only test support.
    stage(manager,request) returns a compact source receipt. lease(manager,id)
    yields a protected immutable original after fresh authorization/membership.
    close retires all entries but never deletes an actively leased worker input;
    the last returning lease removes it and the owned temporary root.
    """
    def __init__(self, *, principal=current_principal, transfer=stage_original,
            clock=time.time, max_bytes=limits.SNAPSHOT_MAX_BYTES, directory=None):
        self._principal_provider = principal
        self._transfer = transfer
        self._clock = clock
        self._max_bytes = max_bytes
        self._temp = tempfile.TemporaryDirectory(prefix='foundry-image-snapshots-', dir=directory)
        self.directory = Path(self._temp.name)
        self._entries = {}
        self._reserved = 0
        self._staging = 0
        self._closed = False
        self._root_closed = False
        self._lock = asyncio.Lock()

    def _principal(self):
        principal = self._principal_provider()
        if not isinstance(principal, Principal):
            raise denied()
        return principal

    def _owned(self, original):
        return (isinstance(original, StagedOriginal) and isinstance(original.directory, Path) and isinstance(original.path, Path)
            and original.directory.parent == self.directory
            and original.path.parent == original.directory and not original.directory.is_symlink())

    def _receipt(self, record):
        expiry = datetime.fromtimestamp(record.expiry, timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
        return SourceReceipt(source_id=record.source_id, source_expires_at=expiry)

    def _prune(self):
        for key, record in list(self._entries.items()):
            if record.leases == 0 and (record.retired or self._clock() >= record.expiry):
                record.original.close()
                del self._entries[key]
        if self._closed and not self._entries and not self._staging and not self._root_closed:
            self._temp.cleanup()
            self._root_closed = True

    async def prune(self):
        async with self._lock:
            self._prune()

    @property
    def used_bytes(self):
        return self._reserved + sum(record.original.size_bytes for record in self._entries.values())

    async def stage(self, manager, request, *, frame_bytes=65536, validate_original=None):
        """Admit only a complete original accepted by an optional trusted validator.

        Validation runs while staging still owns the file/reservation, before
        any handle exists. Failure or cancellation cleans the original even if
        the caller's authorization changes while a decoder is running.
        """
        principal = self._principal()
        original = None
        admitted = False
        finalized = False
        reserved = 0
        async with self._lock:
            if self._closed:
                raise unavailable()
            self._staging += 1

        async def reserve(size):
            nonlocal reserved
            async with self._lock:
                if self._closed or self._principal() != principal:
                    raise denied()
                self._prune()
                if type(size) is not int or not 1 <= size <= limits.SOURCE_MAX_BYTES or reserved:
                    raise ToolError('InvalidFoundryResponse: source cache received an invalid reservation.')
                if self.used_bytes + size > self._max_bytes:
                    raise ToolError('SourceCacheFull: private originals exceed the512 MiB quota after expired snapshots were pruned. Wait for snapshot expiry and retry get_foundry_image_info; valid handles are not evicted.')
                self._reserved += size
                reserved = size

        try:
            original = await self._transfer(manager, request, frame_bytes=frame_bytes,
                directory=self.directory, admit_size=reserve)
            if (not self._owned(original) or original._closed or not original.path.is_file()
                    or original.path.is_symlink() or type(original.size_bytes) is not int or not isinstance(original.sha256,str)
                    or original.path.stat().st_size != original.size_bytes or reserved != original.size_bytes
                    or not re.fullmatch(r'[0-9a-f]{64}', original.sha256)):
                raise ToolError('InvalidFoundryResponse: source transfer did not hand off a complete private file.')
            if validate_original is not None:
                await validate_original(original)
            if manager.websockets.get('gm') is not original.context.socket:
                raise context_lost()
            if self._principal() != principal:
                raise denied()
            async with self._lock:
                if self._closed:
                    raise unavailable()
                if self._principal() != principal:
                    raise denied()
                if manager.websockets.get('gm') is not original.context.socket:
                    raise context_lost()
                record = _Snapshot(str(uuid4()), self._clock()+limits.SNAPSHOT_TTL_SECONDS, principal, original)
                receipt = self._receipt(record)
                self._entries[record.source_id] = record
                self._reserved -= reserved
                reserved = 0
                admitted = True
                self._staging -= 1
                finalized = True
                return receipt
        finally:
            if not admitted and self._owned(original):
                original.close()
            if not finalized:
                async with self._lock:
                    self._reserved -= reserved
                    self._staging -= 1
                    self._prune()

    @asynccontextmanager
    async def lease(self, manager, source_id):
        principal = self._principal()
        async with self._lock:
            self._prune()
            record = self._entries.get(source_id) if isinstance(source_id, str) else None
            if (self._closed or record is None or record.principal != principal or record.retired or self._clock() >= record.expiry):
                raise unavailable()
            record.leases += 1
        socket = manager.websockets.get('gm')

        async def recheck():
            if self._principal() != principal:
                raise denied()
            if record.retired or self._clock() >= record.expiry:
                raise unavailable()
            if socket is None or manager.websockets.get('gm') is not socket:
                raise context_lost()
            try:
                result = Membership.model_validate(await manager.call('gm','validateImagePreviewSource',
                    {'image': record.original.context.image.model_dump(exclude_none=True)}, timeout=limits.READ_TIMEOUT_SECONDS))
            except (RpcError, ToolError, ValueError, TypeError, ConnectionError, RuntimeError, TimeoutError):
                raise context_lost() from None
            if (manager.websockets.get('gm') is not socket or result.world_id != record.original.context.world_id
                    or result.user_id != record.original.context.user_id or result.image != record.original.context.image):
                raise context_lost()
            if self._principal() != principal:
                raise denied()
            if record.retired or self._clock() >= record.expiry:
                raise unavailable()

        try:
            await recheck()
            yield SourceLease(self._receipt(record), record.original, recheck)
            if manager.websockets.get('gm') is not socket:
                raise context_lost()
            if self._principal() != principal:
                raise denied()
        finally:
            async with self._lock:
                record.leases -= 1
                self._prune()

    async def discard(self, source_id):
        principal = self._principal()
        async with self._lock:
            record = self._entries.get(source_id)
            if record is None or record.principal != principal:
                raise unavailable()
            record.retired = True
            self._prune()

    async def close(self):
        async with self._lock:
            self._closed = True
            for record in self._entries.values():
                record.retired = True
            self._prune()
