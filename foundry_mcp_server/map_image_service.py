"""Map annotation result assembly, separate from cache/render/publication owners."""
from fastmcp.exceptions import ToolError

from .image_preview_failure import PreviewFailure
from .map_context import BoundMapContext
from .mcp_server.map_image_models import MapNotesResult,NoteRenderSummary


def context_required():
    return ToolError('MapContextRequired: annotation needs an exact map or map-bound source_id. Call browse_maps, get_map_info(scene_uuid=..., section="assets"), then get_foundry_image_info with the returned map selector.')


def annotation_result(record,candidates,summary):
    """Only rendered keys enter bounded legend selection; private IDs stay out."""
    if not isinstance(record,BoundMapContext):raise context_required()
    summary=NoteRenderSummary.model_validate(summary)
    if (summary.total_in_region!=candidates.total_in_region or not set(summary.keys)<={pin.key for pin in candidates.pins}
            or summary.omission_reasons.get('limit',0)!=candidates.omitted_for_limit):
        raise PreviewFailure('ImageProcessingFailed')
    identity=record.resolved.map_request()
    limitations=list(candidates.limitations)
    if summary.omitted_count and len(limitations)<16:
        limitations.append('Some note keys were omitted; request a tighter/detail crop. Fixed glyph size is never reduced to hide density or edge failures.')
    legend=None
    if summary.keys:
        legend=dict(tool='get_map_info',arguments=dict(scene_uuid=identity['scene_uuid'],level_id=identity['level_id'],section='notes',
            expected_revision=record.resolved.revision,note_keys=summary.keys))
    return MapNotesResult(**summary.model_dump(),map=identity,revision=record.resolved.revision,
        scope_status=candidates.scope_status,limitations=limitations,legend_next_call=legend)
