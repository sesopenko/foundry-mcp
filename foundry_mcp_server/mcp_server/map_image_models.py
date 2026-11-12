"""Strict rendered-key summaries and exact revision-bound legend followups."""
from typing import Annotated,Literal
from pydantic import Field,model_validator
from .selective_models import Model
from .map_models import SceneUUID,LevelId,MapSelector,Revision
from .map_note_models import NoteKey,NoteKeys


class NoteRenderSummary(Model):
    total_in_region: int=Field(ge=0,le=2**53-1,description='Applicable authorized pin centers inside the exclusive source crop, before render limits.')
    rendered_count: int=Field(ge=0,le=100)
    omitted_count: int=Field(ge=0,le=2**53-1)
    complete: bool=Field(description='All applicable in-region pins rendered; independent of permission scope and legend pagination.')
    keys: list[NoteKey]=Field(max_length=100,description='Rendered aliases in numeric order, stable within this exact Scene/level revision.')
    omission_reasons: dict[Literal['limit','density','collision','edge','tiny_image'],int]=Field(description='Positive counts sum to omitted_count. Request a tighter/detail crop for missing keys; glyphs never shrink.')

    @model_validator(mode='after')
    def consistency(self):
        if (self.rendered_count!=len(self.keys) or len(set(self.keys))!=len(self.keys)
                or self.keys!=sorted(self.keys,key=lambda key:int(key[1:]))
                or self.total_in_region!=self.rendered_count+self.omitted_count
                or self.complete!=(self.omitted_count==0)
                or any(count<=0 for count in self.omission_reasons.values())
                or sum(self.omission_reasons.values())!=self.omitted_count):
            raise ValueError('Inconsistent annotation counts')
        return self


class NoteLegendArguments(Model):
    scene_uuid: SceneUUID
    level_id: LevelId
    section: Literal['notes']
    expected_revision: Revision
    note_keys: NoteKeys


class NoteLegendNext(Model):
    tool: Literal['get_map_info']
    arguments: NoteLegendArguments


class MapNotesResult(NoteRenderSummary):
    map: MapSelector=Field(description='Exact owning Scene/level/background identity; not inferred from an image path.')
    revision: Revision=Field(description='Selected map/note snapshot; use the exact legend next call and paginate it to completion.')
    scope_status: Literal['complete','partial']=Field(description='Partial exposes unavailable/denied note scope separately from rendered counts.')
    limitations: list[Annotated[str,Field(max_length=512)]]=Field(max_length=16)
    legend_next_call: NoteLegendNext|None=Field(description='Exact rendered-key lookup; null when no key rendered. Follow returned legend cursors with identical selection/revision.')

    @model_validator(mode='after')
    def matching_legend(self):
        if self.map.role!='background':raise ValueError('Unsupported annotated role')
        if self.scope_status=='partial' and not self.limitations:raise ValueError('Missing scope limitation')
        expected=dict(scene_uuid=self.map.scene_uuid,level_id=self.map.level_id,section='notes',expected_revision=self.revision,note_keys=self.keys)
        if bool(self.keys)!=(self.legend_next_call is not None):raise ValueError('Wrong legend availability')
        if self.legend_next_call and self.legend_next_call.arguments.model_dump()!=expected:raise ValueError('Wrong legend identity/revision/keys')
        return self
