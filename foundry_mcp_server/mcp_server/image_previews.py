"""Authenticated image metadata composition; originals never enter MCP results."""
from .server import mcp
from .image_preview_models import ImageInfoRequest, ImageInfoResult
from foundry_mcp_server.config import settings
from foundry_mcp_server.image_preview_errors import preview_error
from foundry_mcp_server.image_preview_failure import PreviewFailure
from foundry_mcp_server.image_preview_process import ProbeMetadata, probe_image
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
