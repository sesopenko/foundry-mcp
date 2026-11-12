"""Strict private annotated-render request/result boundary; M05 owns publication."""
from dataclasses import dataclass,field
import json
from pathlib import Path

from . import image_preview_limits as limits
from .image_preview_artifact import inspect_artifact
from .image_preview_failure import PreviewFailure
from .image_preview_geometry import crop_bounds
from .image_preview_process import EncodedGeometry,worker_reply
from .image_preview_supervisor import current_supervisor
from .map_note_layout import validate_pins
from .mcp_server.image_preview_models import Crop
from .mcp_server.map_image_models import NoteRenderSummary
from .mcp_server.selective_models import Model


class AnnotatedGeometry(EncodedGeometry):
    map_notes: NoteRenderSummary


class AnnotatedReply(Model):
    artifact: AnnotatedGeometry


@dataclass(frozen=True,repr=False)
class RenderedNotes:
    geometry: EncodedGeometry
    notes: NoteRenderSummary
    data: bytes=field(repr=False)


async def render_annotated(path,crop,pins,total,*,supervisor=None,metrics=None,timeout=limits.WORKER_TIMEOUT_SECONDS):
    """Generated aliases/positions only; same budgets, scratch and child lifecycle."""
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise PreviewFailure('UnsupportedImage')
    if isinstance(crop,Crop):crop=crop.model_dump()
    pins=validate_pins(pins,total,dict(x=0,y=0,width=limits.SOURCE_MAX_EDGE,height=limits.SOURCE_MAX_EDGE))
    try:
        payload=json.dumps(dict(operation='annotated',source=str(path),crop=crop,pins=pins,total=total),allow_nan=False,separators=(',',':')).encode()
    except (ValueError,TypeError):raise PreviewFailure('InvalidOperation') from None
    def collect(workspace,raw):
        artifact=AnnotatedReply.model_validate(worker_reply(raw)).artifact
        notes=artifact.map_notes
        if (artifact.source.size_bytes!=path.stat().st_size or notes.total_in_region!=total
                or not set(notes.keys)<={p[0] for p in pins}
                or notes.omission_reasons.get('limit',0)!=total-len(pins)
                or artifact.region.model_dump()!=crop_bounds(crop,artifact.source.width,artifact.source.height)):
            raise PreviewFailure('ImageProcessingFailed')
        file=workspace.path/'preview.bin'
        if file.is_symlink() or not file.is_file():raise PreviewFailure('ImageProcessingFailed')
        with file.open('rb') as stream:data=stream.read(limits.OUTPUT_MAX_BYTES+1)
        if inspect_artifact(data)!={key:getattr(artifact,key) for key in ('width','height','mime_type','size_bytes')}:
            raise PreviewFailure('ImageProcessingFailed')
        geometry=EncodedGeometry.model_validate(artifact.model_dump(exclude={'map_notes'}))
        return RenderedNotes(geometry,notes,data)
    try:
        return await (supervisor or current_supervisor()).run(payload,metrics=metrics,timeout=timeout,collect=collect)
    except (ValueError,TypeError,OSError):raise PreviewFailure('ImageProcessingFailed') from None
