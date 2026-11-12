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
from fastmcp.exceptions import ToolError


@mcp.tool(annotations={'readOnlyHint':True,'destructiveHint':False,'idempotentHint':False,'openWorldHint':False})
async def get_foundry_image_info(request: ImageInfoRequest) -> ImageInfoResult:
    """Read original image dimensions and pin its bytes for later overview/crops.

    Authenticated MCP GM capability requiring the connected ready Foundry14 GM;
    independent of PF2e, active Scene and public preview origin. Provide exactly
    one request.image (exact image record from browse_journal_images/upload_image)
    or request.src (stored journal img src or portrait reference). No prior browse
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

    Next use get_foundry_image_url with source_id for an overview or integer crop
    in these original display coordinates. SourceUnavailable/SourceContextLost
    requires fresh info after restoring the same authorized ready GM. AmbiguousSource
    requires browse_journal_images on the referenced parent and an exact image;
    denied/unavailable listings establish no absence. UnsupportedImage/ImageTooLarge
    requires another supported/smaller source. Processing busy/timeout/resource
    errors permit retry after current work or choosing a smaller original.
    """
    from . import tools
    manager = tools._foundry_manager
    metadata = None

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

    try:
        receipt = await source_runtime.require_cache().stage(manager,request,
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
    reference), or source_id (get_foundry_image_info/this tool). No prior browse
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

    Returns exactly url,expires_at,source_id,source_expires_at,source_width,
    source_height,region:{x,y,width,height},width,height,mime_type,size_bytes.
    Expiries are absolute UTC; original and public lifetimes are independent.
    Final dimensions/bytes describe the actual PNG/WebP fetch: at most2048 per
    edge,2359296 pixels,2MiB, no enlargement, aspect preserved. Original limits
    are128MiB,32768 per edge,128000000 pixels. PNG preferred, then WebP90/82 and
    smaller output as necessary. JPEG/PNG/APNG/WebP/AVIF/BMP/GIF/TIFF/safe SVG;
    animations/multipage sources use first displayable frame/page only. This is
    a file preview, not a composed Scene (no fog/lights/tokens/walls/tiles).

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
        if request.source_id is None:
            info = await get_foundry_image_info(ImageInfoRequest.model_validate(
                request.model_dump(exclude={'source_id','crop'},exclude_none=True)))
            source_id = info.source_id
        else:source_id = request.source_id
        async with source_runtime.require_cache().lease(manager,source_id) as lease:
            rendered = await render_preview(lease.original.path,request.crop)
            if not isinstance(rendered,RenderedPreview):raise PreviewFailure('ImageProcessingFailed')
            geometry = EncodedGeometry.model_validate(rendered.geometry.model_dump())
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
            await lease.recheck()
            receipt = await preview_runtime.publish(rendered.data,geometry.mime_type)
            await lease.recheck()
            return ImageUrlResult(**lease.receipt.model_dump(),url=preview_runtime.url(receipt),
                expires_at=datetime.fromtimestamp(receipt.expires_at,timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z'),
                source_width=geometry.source.width,source_height=geometry.source.height,
                region=geometry.region,width=geometry.width,height=geometry.height,
                mime_type=receipt.mime_type,size_bytes=receipt.size_bytes)
    except StoreFailure as failure:
        code = 'PreviewQuotaExceeded' if failure.code=='PreviewQuotaExceeded' else 'PreviewStorageUnavailable'
        raise preview_error(code) from None
    except PreviewFailure as failure:
        raise preview_error(failure.code,width=failure.width,height=failure.height) from None
    except (ValueError,TypeError,OSError,AttributeError):
        raise preview_error('ImageProcessingFailed') from None
