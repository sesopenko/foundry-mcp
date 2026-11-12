"""Immutable source-bound map context and private bounded region-note retrieval.

M05 owns source-cache attachment. Nothing here registers a public MCP tool or
changes existing image-tool inputs. See docs/plans/image-viewing/map-context.md.
"""
import asyncio
from dataclasses import asdict,dataclass
from datetime import datetime
import hashlib
import json
import math
import time

from fastmcp.exceptions import ToolError

from . import image_preview_limits as limits
from .auth.principal import Principal,current_principal,denied
from .image_preview_sources import SourceLease,unavailable,context_lost
from .image_preview_process import ProbeMetadata
from .map_context_models import MapContextReply,MapCandidatesReply
from .map_geometry import SceneImageMapping,unsupported_mapping
from .mcp_server.image_preview_models import Crop
from .mcp_server.map_info_models import MapSelector
from .mcp_server.map_models import decode_cursor
from .mcp_server.selective import size
from .ws.connection import RpcError


def changed():
    return ToolError('MapContextChanged: selected Scene/level/asset, mapping, Notes or permissions changed. Refresh get_map_info for this exact Scene/level and get_foundry_image_info with its map selector before annotating again.')


def invalid_response():
    return ToolError('InvalidFoundryResponse: invalid private map context/candidates; check matching server/module/core versions.')


@dataclass(frozen=True,repr=False)
class ResolvedMapContext:
    principal: Principal
    socket: object
    world_id: str
    user_id: str
    map_identity: tuple[str,str,str]
    image: tuple[tuple[str,str],...]
    reference_digest: str
    revision: str
    alias_digest: str
    alias_total: int
    rectangle: tuple[float,float,float,float]
    mapping_status: str
    mapping_reason: str|None
    placement_digest: str
    core_version: str
    scope_status: str
    limitations: tuple[str,...]

    def map_request(self):
        return dict(zip(('scene_uuid','level_id','role'),self.map_identity))


@dataclass(frozen=True,repr=False)
class BoundMapContext:
    resolved: ResolvedMapContext
    source_id: str
    source_expires_at: str
    source_digest: str
    source_width: int
    source_height: int

    def mapping(self):
        if self.resolved.mapping_status!='supported':raise unsupported_mapping()
        return SceneImageMapping(*self.resolved.rectangle,self.source_width,self.source_height)


@dataclass(frozen=True,repr=False)
class MapPin:
    key: str
    note_uuid: str
    source_x: float
    source_y: float


@dataclass(frozen=True,repr=False)
class RegionMapPins:
    pins: tuple[MapPin,...]
    total_in_region: int
    omitted_for_limit: int
    scope_status: str
    limitations: tuple[str,...]

    def worker_pins(self):
        """Bounded generated-key/source-position triples, excluding identities."""
        if len(self.pins)>100:raise invalid_response()
        return tuple((pin.key,pin.source_x,pin.source_y) for pin in self.pins)


class MapContextService:
    """Trusted dependencies only; each private page fits the configured frame.

    Metadata RPCs have15s per-call deadlines; one region retrieval has300s total
    and at most100 pages, collecting at most100 pins. Render supervision remains
    independently90s/1GiB/2GiB and is not implemented by this coordinator.
    """
    def __init__(self,*,principal=current_principal,clock=time.time,frame_bytes=65536):
        if type(frame_bytes) is not int or not 1024<=frame_bytes<=16777216:raise ValueError('Invalid map frame budget')
        self.principal=principal;self.clock=clock;self.frame_bytes=frame_bytes

    def _identity(self):
        principal=self.principal()
        if not isinstance(principal,Principal):raise denied()
        return principal

    def _budget(self):
        budget=min(48000,self.frame_bytes-(size({'id':'x'*36,'result':None})-4))
        if budget<1024:raise ToolError('ResponseTooLarge: bridge frame cannot fit a complete map identity; increase the configured response ceiling.')
        return budget

    async def _rpc(self,manager,method,args,model):
        principal=self._identity();socket=manager.websockets.get('gm')
        if socket is None:raise context_lost()
        caller=hashlib.sha256(json.dumps(asdict(principal),sort_keys=True,separators=(',',':')).encode()).hexdigest()
        budget=self._budget()
        try:
            raw=await manager.call('gm',method,{**args,'caller_key':caller,'max_bytes':budget},timeout=limits.READ_TIMEOUT_SECONDS)
            if self._identity()!=principal or manager.websockets.get('gm') is not socket:raise context_lost()
            if size(raw)>budget or size({'id':'x'*36,'result':raw})>self.frame_bytes:raise ValueError('Oversize private frame')
            value=model.model_validate(raw)
            context=value if isinstance(value,MapContextReply) else value.context
            if context.map.model_dump()!=args['map']:raise ValueError('Wrong map selection')
            if args.get('expected_revision') is not None and context.revision!=args['expected_revision']:raise changed()
            if args.get('expected_reference_digest') is not None and context.reference_digest!=args['expected_reference_digest']:raise changed()
            return value,principal,socket
        except RpcError as error:
            code=error.error.get('code',error.error.get('type'))
            if code=='UnsupportedMapMapping':raise unsupported_mapping() from None
            if code=='ResponseTooLarge':raise ToolError('ResponseTooLarge: a complete private map identity/candidate cannot fit the configured frame.') from None
            if code in ('ImageNotFound','UnsupportedSource','AmbiguousSource','BrowseFailed'):
                raise ToolError(code+': selected map asset could not be resolved; use get_map_info assets or browse_journal_images for an exact readable source.') from None
            raise changed() from None
        except (TimeoutError,ConnectionError,RuntimeError):raise context_lost() from None
        except (ValueError,TypeError):raise invalid_response() from None

    @staticmethod
    def _resolved(value,principal,socket):
        r=value.rectangle
        return ResolvedMapContext(principal,socket,value.world_id,value.user_id,
            (value.map.scene_uuid,value.map.level_id,value.map.role),tuple(sorted(value.image.model_dump(exclude_none=True).items())),
            value.reference_digest,value.revision,value.alias_digest,value.alias_total,
            (r.sceneX,r.sceneY,r.sceneWidth,r.sceneHeight),value.mapping.status,value.mapping.reason,
            value.placement_digest,value.core_version,value.scope_status,tuple(value.limitations))

    async def resolve(self,manager,map_selector,*,expected_revision=None,expected_reference_digest=None):
        selected=MapSelector.model_validate(map_selector)
        args={'map':selected.model_dump()}
        if expected_revision is not None:args['expected_revision']=expected_revision
        if expected_reference_digest is not None:args['expected_reference_digest']=expected_reference_digest
        value,principal,socket=await self._rpc(manager,'getMapImageContext',args,MapContextReply)
        return self._resolved(value,principal,socket)

    def _lease(self,manager,resolved,lease):
        if not isinstance(lease,SourceLease) or self._identity()!=resolved.principal:raise unavailable()
        original=lease.original;context=original.context
        if (manager.websockets.get('gm') is not resolved.socket or context.socket is not resolved.socket
                or context.world_id!=resolved.world_id or context.user_id!=resolved.user_id):raise context_lost()
        if tuple(sorted(context.image.model_dump(exclude_none=True).items()))!=resolved.image:raise changed()
        expiry=datetime.fromisoformat(lease.receipt.source_expires_at).timestamp()
        if not self.clock()<expiry:raise unavailable()

    async def bind(self,manager,resolved,lease,metadata):
        """Pin an admitted source lease/probe to the immutable metadata snapshot."""
        metadata=ProbeMetadata.model_validate(metadata)
        self._lease(manager,resolved,lease)
        if metadata.size_bytes!=lease.original.size_bytes:raise invalid_response()
        await lease.recheck()
        fresh=await self.resolve(manager,resolved.map_request(),expected_revision=resolved.revision)
        if fresh!=resolved:raise changed()
        self._lease(manager,resolved,lease)
        return BoundMapContext(resolved,lease.receipt.source_id,lease.receipt.source_expires_at,
            lease.original.sha256,metadata.width,metadata.height)

    def _bound_lease(self,manager,record,lease):
        self._lease(manager,record.resolved,lease)
        if (lease.receipt.source_id!=record.source_id or lease.receipt.source_expires_at!=record.source_expires_at
                or lease.original.sha256!=record.source_digest):raise unavailable()

    async def revalidate(self,manager,record,lease,*,annotated=True):
        self._bound_lease(manager,record,lease);await lease.recheck()
        fresh=await self.resolve(manager,record.resolved.map_request(),
            expected_revision=record.resolved.revision if annotated else None,expected_reference_digest=record.resolved.reference_digest)
        prior=record.resolved
        if (fresh.principal!=prior.principal or fresh.socket is not prior.socket or fresh.world_id!=prior.world_id
                or fresh.user_id!=prior.user_id or fresh.map_identity!=prior.map_identity or fresh.image!=prior.image
                or fresh.reference_digest!=prior.reference_digest):raise changed()
        if annotated:
            if fresh!=prior:raise changed()
            record.mapping()
        self._bound_lease(manager,record,lease)
        return fresh

    async def region_pins(self,manager,record,lease,crop=None):
        """First100 numeric aliases in the exact crop, with honest over-limit count."""
        mapping=record.mapping()
        crop=Crop.model_validate(dict(x=0,y=0,width=record.source_width,height=record.source_height) if crop is None else crop)
        crop.check_containment(record.source_width,record.source_height)
        await self.revalidate(manager,record,lease,annotated=True)
        source_scope=hashlib.sha256((record.source_id+':'+record.source_digest).encode()).hexdigest()
        args=dict(map=record.resolved.map_request(),expected_revision=record.resolved.revision,
            source_size=dict(width=record.source_width,height=record.source_height),crop=crop.model_dump(),source_scope=source_scope)
        pins=[];seen=set();keys=set();total=None;cursor=None;previous=None
        async with asyncio.timeout(limits.TRANSFER_TIMEOUT_SECONDS):
            for _ in range(100):
                request={**args,'limit':100-len(pins),**({'cursor':cursor} if cursor is not None else {})}
                value,principal,socket=await self._rpc(manager,'getMapRegionCandidates',request,MapCandidatesReply)
                context=self._resolved(value.context,principal,socket)
                if context!=record.resolved or value.crop!=crop or value.source_size.model_dump()!=args['source_size']:raise changed()
                if total is None:total=value.total_in_region
                if total!=value.total_in_region or len(value.entries)>request['limit']:raise invalid_response()
                try:incoming=decode_cursor(cursor);outgoing=decode_cursor(value.next_cursor)
                except (ValueError,TypeError):raise invalid_response() from None
                end=(incoming.offset if incoming else 0)+len(value.entries)
                if (end>total or value.complete!=(end==total) or value.complete!=(outgoing is None)
                    or (incoming and incoming.revision!=record.resolved.revision)
                    or (outgoing and (not value.entries or outgoing.offset!=end or outgoing.revision!=record.resolved.revision
                        or (incoming and incoming.scope!=outgoing.scope)))):raise invalid_response()
                for note in value.entries:
                    order=(int(note.key[1:]),note.note_uuid)
                    if (note.note_uuid in seen or note.key in keys or not note.note_uuid.startswith(record.resolved.map_identity[0]+'.Note.')
                            or (previous is not None and (order<=previous or note.note_uuid<=previous[1]))
                            or not mapping.contains(note.x,note.y,crop)):raise invalid_response()
                    expected=mapping.source_point(note.x,note.y)
                    if any(not math.isclose(actual,required,rel_tol=0,abs_tol=1e-9)
                        for actual,required in zip((note.source_x,note.source_y),expected)):raise invalid_response()
                    seen.add(note.note_uuid);keys.add(note.key);previous=order
                    pins.append(MapPin(note.key,note.note_uuid,*expected))
                self._bound_lease(manager,record,lease)
                if value.complete or len(pins)==100:break
                cursor=value.next_cursor
            else:raise invalid_response()
        await self.revalidate(manager,record,lease,annotated=True)
        return RegionMapPins(tuple(pins),total,total-len(pins),record.resolved.scope_status,record.resolved.limitations)
