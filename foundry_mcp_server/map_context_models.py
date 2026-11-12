"""Private browser map DTOs; never register these as public MCP results."""
from typing import Annotated,Literal
from pydantic import Field,model_validator

from .mcp_server.selective_models import Model
from .mcp_server.map_models import Revision,Cursor
from .mcp_server.map_info_models import MapSelector,SceneRectangle
from .mcp_server.map_note_models import NoteKey,NoteUUID
from .mcp_server.journal_image_models import ImageSelector
from .mcp_server.image_preview_models import Crop,SourceEdge


class MappingSupport(Model):
    status: Literal['supported','unsupported']
    reason: Literal['foreground_role','unverified_build','invalid_rectangle','default_schema_unavailable','nondefault_placement']|None

    @model_validator(mode='after')
    def consistent(self):
        if (self.status=='supported')!=(self.reason is None):raise ValueError('Inconsistent mapping support')
        return self


class MapContextReply(Model):
    protocol: Literal['map_context.v1']
    world_id: str=Field(min_length=1,max_length=256)
    user_id: str=Field(min_length=1,max_length=256)
    map: MapSelector
    level_uuid: str=Field(max_length=300)
    image: ImageSelector=Field(repr=False)
    reference_digest: Revision
    revision: Revision
    alias_digest: Revision
    alias_total: int=Field(ge=0,le=2**53-1)
    rectangle: SceneRectangle
    mapping: MappingSupport
    placement_digest: Revision
    core_version: str=Field(min_length=1,max_length=64)
    scope_status: Literal['complete','partial']
    source_scope_status: Literal['complete','partial']
    limitations: list[Annotated[str,Field(max_length=512)]]=Field(max_length=16)

    @model_validator(mode='after')
    def context_identity(self):
        if self.level_uuid!=self.map.scene_uuid+'.Level.'+self.map.level_id:raise ValueError('Wrong level owner')
        if self.mapping.status=='supported' and (self.map.role!='background' or self.core_version!='14.369'
                or self.rectangle.sceneWidth<=0 or self.rectangle.sceneHeight<=0):raise ValueError('Unverified mapping claim')
        if self.scope_status=='partial' and not self.limitations:raise ValueError('Missing scope limitation')
        return self


class MapSourceSize(Model):
    width: SourceEdge
    height: SourceEdge

    @model_validator(mode='after')
    def area(self):
        if self.width*self.height>128000000:raise ValueError('Source pixel limit')
        return self


class MapRegionCandidate(Model):
    key: NoteKey
    note_uuid: NoteUUID
    x: int|float
    y: int|float
    source_x: int|float
    source_y: int|float


class MapCandidatesReply(Model):
    protocol: Literal['map_candidates.v1']
    context: MapContextReply=Field(repr=False)
    source_size: MapSourceSize
    crop: Crop
    entries: list[MapRegionCandidate]=Field(max_length=100,repr=False)
    total_in_region: int=Field(ge=0,le=2**53-1)
    complete: bool
    next_cursor: Cursor|None

    @model_validator(mode='after')
    def region(self):
        if (self.crop.x+self.crop.width>self.source_size.width or self.crop.y+self.crop.height>self.source_size.height
                or self.total_in_region>self.context.alias_total):raise ValueError('Invalid candidate region/count')
        return self
