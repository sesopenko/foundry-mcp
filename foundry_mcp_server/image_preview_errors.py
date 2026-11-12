"""Fixed actionable preview errors; native messages and source URLs stay private."""
from fastmcp.exceptions import ToolError

MESSAGES = {
    'ImageMemoryLimit': 'Preview decoder exceeded its resident-memory budget. Request a smaller source or crop through get_foundry_image_url.',
    'ImageScratchLimit': 'Preview decoder exceeded its private scratch budget. Choose a smaller source through browse_journal_images.',
    'ImageProcessingTimeout': 'Preview decoder exceeded its time budget. Choose a smaller source or a tighter crop through get_foundry_image_url.',
    'ImageProcessingBusy': 'Preview processing queue is full or its wait deadline elapsed. Retry this request after the current preview completes.',
    'AmbiguousSource': 'Reference matches multiple configured sources. Use browse_journal_images on the referenced parent and pass one exact image record.',
    'InvalidCrop': 'Use integer x/y >=0 and positive integer width/height fully contained in the original dimensions from get_foundry_image_info; no clipping or padding.',
    'UnsupportedImage': 'Use a supported self-contained image; browse_journal_images to choose another file. Executable or externally referenced SVG content is unsupported.',
    'ImageTooLarge': 'Original exceeds 128 MiB, 32768 pixels per edge or 128000000 pixels. Choose a smaller original through browse_journal_images.',
    'PreviewNotConfigured': 'Preview issuance requires an authenticated MCP endpoint and FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN set to its public HTTPS origin. get_foundry_image_info needs no public origin.',
}


def preview_error(code, *, width=None, height=None):
    """Allowlisted code and optional safely known dimensions only; no raw details."""
    if code not in MESSAGES:
        return ToolError('ImageProcessingFailed: preview processing failed; check matching server/module versions and choose a supported image.')
    dimensions = ''
    if type(width) is int and width > 0 and type(height) is int and height > 0:
        dimensions = f' Original width={width}, height={height}.'
    return ToolError(f'{code}: {MESSAGES[code]}{dimensions}')
