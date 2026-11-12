"""Authenticated image metadata composition; originals never enter MCP results."""
from .server import mcp
from .image_preview_models import Crop, ImageInfoRequest, ImageInfoResult, ImageUrlRequest, ImageUrlResult
from datetime import datetime, timezone
from foundry_mcp_server.config import settings
from foundry_mcp_server.image_preview_errors import preview_error
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.image_preview_process import ProbeMetadata, probe_image
from foundry_mcp_server.image_preview_process import RenderedPreview, EncodedGeometry, render_preview
from foundry_mcp_server.image_preview_artifact import inspect_artifact
from foundry_mcp_server.image_preview_runtime import preview_runtime
from foundry_mcp_server.image_preview_store import StoreFailure
from foundry_mcp_server.image_preview_source_runtime import source_runtime
from foundry_mcp_server.image_preview_sources import Membership, context_lost
from foundry_mcp_server.ws.connection import RpcError
from foundry_mcp_server.map_context import MapContextService,BoundMapContext,invalid_response
from foundry_mcp_server.map_image_service import context_required,annotation_result
from foundry_mcp_server.map_note_render import render_annotated,RenderedNotes
from fastmcp.exceptions import ToolError


@mcp.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'idempotentHint':False,'openWorldHint':False})
async def get_foundry_image_info(request: ImageInfoRequest) -> ImageInfoResult:
    """Read original image dimensions and pin its bytes for later overview/crops.

    Authenticated MCP GM capability requiring the connected ready Foundry14 GM;
    independent of PF2e, active Scene and public preview origin. Provide exactly
    one request.image (exact image record from browse_journal_images/upload_image)
    or request.src (stored journal img src or portrait reference), or request.map
    {scene_uuid,level_id,role:background|foreground} from get_map_info assets.
    Explicit Level IDs belong to that Scene; names, viewed/active levels and
    compendium Scenes are not substituted. No prior browse
    is required. For fragmented read_journal_page HTML, follow next_cursor until
    the entire img tag is reconstructed before extracting src. Example:
    {"request":{"src":"worlds/test/maps/floor.webp"}}.

    Only configured data/public/readable S3 source membership is accepted through
    a fresh bounded parent listing; arbitrary URLs/host paths are not fetched.
    Returns exactly source_id, source_expires_at (UTC), width/height (original
    display-oriented pixels), mime_type (detected format), size_bytes (compressed
    original), frame_policy (still or first_frame, also first page). Supports
    JPEG, PNG/APNG, WebP, AVIF, BMP, GIF, TIFF and safe self-contained SVG.
    Limits:128 MiB compressed,32768 pixels/edge,128000000 pixels. No pixels,
    private source paths or public URLs are returned; this performs no visual
    interpretation. A caller-bound source_id pins these exact bytes for 30 minutes
    from staging even if that file is replaced. It cannot be shared across
    principals, GM/world context or server restarts.

    A map selector privately binds this source_id to its exact Scene/level/role,
    source reference and note/mapping revision. Signed source references stay
    private and still require fresh configured-source membership. Repeated crops
    reuse one transfer. An image/src handle has no inferred map context.

    Next use get_foundry_image_url with source_id for an overview or integer crop
    in these original display coordinates. SourceUnavailable/SourceContextLost
    requires fresh info after restoring the same authorized ready GM. AmbiguousSource
    requires browse_journal_images on the referenced parent and an exact image;
    denied/unavailable listings establish no absence. UnsupportedImage/ImageTooLarge
    requires another supported/smaller source. Processing busy/timeout/resource
    errors permit retry after current work or choosing a smaller original.
    MapContextChanged: refresh get_map_info and info with the returned map selector.
    """
    from . import tools
    manager = tools._foundry_manager
    metadata = None
    resolved = None
    maps = MapContextService(frame_bytes=settings.max_response_bytes)

    async def validate(original):
        nonlocal metadata
        metadata = ProbeMetadata.model_validate(await probe_image(original.path))
        if metadata.size_bytes != original.size_bytes:
            raise PreviewFailure('ImageProcessingFailed')
        try:
            current = Membership.model_validate(await manager.call('gm','validateImagePreviewSource',
                {'image':original.context.image.model_dump(exclude_none=True)},timeout=15))
        except (RpcError,ToolError,ValueError,TypeError,ConnectionError,RuntimeError,TimeoutError):
            raise context_lost() from None
        if (manager.websockets.get('gm') is not original.context.socket
                or current.world_id!=original.context.world_id or current.user_id!=original.context.user_id
                or current.image!=original.context.image):
            raise context_lost()
        if resolved is not None:
            return await maps.prepare_binding(manager,resolved,original,metadata)

    try:
        selected=request
        if request.map is not None:
            resolved=await maps.resolve(manager,request.map)
            selected=ImageInfoRequest(image=dict(resolved.image))
        receipt = await source_runtime.require_cache().stage(manager,selected,
            frame_bytes=settings.max_response_bytes,validate_original=validate)
        return ImageInfoResult(**receipt.model_dump(),**metadata.model_dump())
    except PreviewFailure as failure:
        raise preview_error(failure.code,width=failure.width,height=failure.height) from None
    except (ValueError,TypeError,OSError):
        raise preview_error('ImageProcessingFailed') from None


@mcp.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'idempotentHint':False,'openWorldHint':False})
async def get_foundry_image_url(request: ImageUrlRequest) -> ImageUrlResult:
    """Issue an immutable HTTPS image overview/crop, readable by anyone with its link.

    Anyone holding url can read exactly those selected pixels for seven days
    (604800 seconds) without credentials or a connected GM. Each successful call
    gets a fresh UUID URL, even for identical pixels; treat it as a bearer secret.
    Authenticated MCP Basic/OAuth/development and a ready connected Foundry14 GM
    are required to issue. No PF2e or active Scene required. Public origin must be
    configured; PreviewNotConfigured is returned before source processing when
    disabled. Plain unauthenticated mode cannot issue. No game asset is modified.

    Provide exactly one under request: image (exact browse_journal_images or
    upload_image image record), src (complete stored journal img/portrait
    reference), source_id (get_foundry_image_info/this tool), or map
    {scene_uuid,level_id,role:background|foreground} from get_map_info assets.
    Explicit level_id is an embedded Level ID belonging to scene_uuid, not a
    name/UUID or implicitly viewed level. No prior browse
    required. Follow read_journal_page.next_cursor to reconstruct fragmented img
    tags. Only configured data/public/readable S3 sources are allowed. A source_id
    pins the original bytes for30 minutes from staging, bound to caller/world/GM;
    repeated crops reuse one transfer even if path contents change. Current file
    membership is rechecked; denied/missing paths cannot be bypassed with a handle.

    Omit crop for the whole image, or provide integer x,y,width,height in original
    display-oriented pixels: top-left origin, x right/y down, exclusive right/
    bottom, positive extent, fully contained; no clipping/padding. Floats/booleans,
    zero/negative/overflow rectangles fail InvalidCrop. Use get_foundry_image_info
    for source dimensions. Example request:{source_id:"<returned handle>",
    crop:{x:7200,y:3100,width:1280,height:960}} for a10000x5000 source.
    From an earlier preview, source left=region.x+floor(u*region.width/width),
    exclusive right uses ceil; apply the analogous Y rule. Coordinates always
    reference the original, including when zooming into a previous crop.

    Without annotations returns exactly url,expires_at,source_id,source_expires_at,source_width,
    source_height,region:{x,y,width,height},width,height,mime_type,size_bytes.
    Expiries are absolute UTC; original and public lifetimes are independent.
    Final dimensions/bytes describe the actual PNG/WebP fetch: at most2048 per
    edge,2359296 pixels,2MiB, no enlargement, aspect preserved. Original limits
    are128MiB,32768 per edge,128000000 pixels. PNG preferred, then WebP90/82 and
    smaller output as necessary. JPEG/PNG/APNG/WebP/AVIF/BMP/GIF/TIFF/safe SVG;
    animations/multipage sources use first displayable frame/page only. This is
    a file preview, not a composed Scene (no fog/lights/tokens/walls/tiles).

    Optional request.map_notes is strictly boolean, default false. True requires
    a map selector or map-bound source_id, and adds only the typed map_notes
    result. False omits that section entirely. V1 annotations support Foundry
    14.369 default background texture placement in the public Scene rectangle,
    including padding/shift and source-size/display-orientation conversion.
    Foregrounds remain fetchable without annotations; foreground/tile composition,
    nondefault texture transforms and other unverified builds cannot be annotated.
    MapContextRequired: browse_maps then get_map_info assets and stage its exact
    map selector. UnsupportedMapMapping: choose a verified background or omit
    map_notes. MapContextChanged: refresh get_map_info and stage fresh map info;
    note/mapping/permission/reference changes reject new annotation, while bytes
    at an unchanged path stay pinned. Issued annotated pixels remain immutable.

    Keys N1/N2/... follow complete authorized level Note UUID order before crop
    filtering. Only pin centers inside the crop are considered. Generated ASCII
    keys target16px final em with white fill/dark1px outline (ink<=20px), never
    full UUIDs/journal labels/bodies. At most100 disjoint labels use<=5% image
    area; edge/tiny/collision/density/limit omissions remain explicit. Tighter
    detail crops recover omitted keys; font size never shrinks to hide crowding.
    map_notes contains map{scene_uuid,level_id,role},revision,total_in_region,
    rendered_count,omitted_count,complete,keys,omission_reasons,scope_status,
    limitations,legend_next_call. complete concerns rendered pins, independently
    of partial permission scope or legend pagination. Zero notes returns zeros.
    Follow legend_next_call verbatim: get_map_info with exact Scene/level,
    section=notes,expected_revision,note_keys for rendered keys only. Paginate
    returned cursors to completion with the same selection/revision. No keys
    means null follow-up. Legend returns full Note/journal/page identities;
    follow a readable page.page_uuid with read_journal_page. No journal bodies
    are read to render annotations. A successful URL never proves all notes fit.

    SourceUnavailable: fresh info using original image/src. SourceContextLost:
    restore intended ready GM/world then fresh info. AmbiguousSource: browse the
    parent and use exact image. InvalidCrop: correct bounds using info dimensions.
    UnsupportedImage/ImageTooLarge: choose supported/smaller source. Resource/
    timeout/busy errors: retry after current work or choose smaller source/crop.
    PreviewQuotaExceeded: wait for expiry/operator capacity check; existing links
    remain valid. PreviewStorageUnavailable: operator checks private persistence.
    URLs contain no source path/crop/credential/query; direct GET/HEAD require no
    login and expire exactly at expires_at. Keep link disclosure intentional.
    """
    from . import tools
    manager = tools._foundry_manager
    try:
        preview_runtime.require_issuance()
        if request.map_notes and request.map is None and request.source_id is None:
            raise context_required()
        if request.source_id is None:
            info = await get_foundry_image_info(ImageInfoRequest.model_validate(
                request.model_dump(exclude={'source_id','crop','map_notes'},exclude_none=True)))
            source_id = info.source_id
        else:source_id = request.source_id
        async with source_runtime.require_cache().lease(manager,source_id) as lease:
            maps=MapContextService(frame_bytes=settings.max_response_bytes)
            record=lease.private_context
            if record is not None and not isinstance(record,BoundMapContext):raise invalid_response()
            if request.map_notes and record is None:raise context_required()
            if record is not None:await maps.revalidate(manager,record,lease,annotated=request.map_notes)
            notes=None
            if request.map_notes:
                candidates=await maps.region_pins(manager,record,lease,request.crop)
                rendered=await render_annotated(lease.original.path,request.crop,candidates.worker_pins(),candidates.total_in_region)
                if not isinstance(rendered,RenderedNotes):raise PreviewFailure('ImageProcessingFailed')
                notes=annotation_result(record,candidates,rendered.notes)
            else:
                rendered = await render_preview(lease.original.path,request.crop)
                if not isinstance(rendered,RenderedPreview):raise PreviewFailure('ImageProcessingFailed')
            geometry = EncodedGeometry.model_validate(rendered.geometry.model_dump())
            if record is not None and (geometry.source.width,geometry.source.height)!=(record.source_width,record.source_height):
                raise PreviewFailure('ImageProcessingFailed')
            region = request.crop or Crop(x=0,y=0,width=geometry.source.width,height=geometry.source.height)
            region.check_containment(geometry.source.width,geometry.source.height)
            if geometry.region!=region:
                raise PreviewFailure('ImageProcessingFailed')
            actual = inspect_artifact(rendered.data)
            expected = {name:getattr(geometry,name) for name in ('width','height','mime_type','size_bytes')}
            if actual!=expected or geometry.source.size_bytes!=lease.original.size_bytes:
                raise PreviewFailure('ImageProcessingFailed')
            # Across rendering and publication awaits, revalidate the exact
            # principal/GM/world/selector, never a replacement file's bytes.
            if record is not None:await maps.revalidate(manager,record,lease,annotated=request.map_notes)
            else:await lease.recheck()
            receipt = await preview_runtime.publish(rendered.data,geometry.mime_type)
            if record is not None:await maps.revalidate(manager,record,lease,annotated=request.map_notes)
            else:await lease.recheck()
            return ImageUrlResult(**lease.receipt.model_dump(),url=preview_runtime.url(receipt),
                expires_at=datetime.fromtimestamp(receipt.expires_at,timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z'),
                source_width=geometry.source.width,source_height=geometry.source.height,
                region=geometry.region,width=geometry.width,height=geometry.height,
                mime_type=receipt.mime_type,size_bytes=receipt.size_bytes,map_notes=notes)
    except StoreFailure as failure:
        code = 'PreviewQuotaExceeded' if failure.code=='PreviewQuotaExceeded' else 'PreviewStorageUnavailable'
        raise preview_error(code) from None
    except PreviewFailure as failure:
        raise preview_error(failure.code,width=failure.width,height=failure.height) from None
    except (ValueError,TypeError,OSError,AttributeError):
        raise preview_error('ImageProcessingFailed') from None
