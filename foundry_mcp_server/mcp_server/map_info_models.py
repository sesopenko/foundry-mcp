"""Core14 selected Scene configuration; missing source fields remain omitted.

Public schema/API evidence and intended contracts: docs/plans/image-viewing/map-info.md.
MapSelector is shared with scene-aware image-tool requests.
"""
from typing import Annotated,Literal
import re
from urllib.parse import urlsplit,unquote

from pydantic import Field,model_validator

from .map_models import SceneUUID,FolderUUID,FolderIdentity,MapNamed,Revision,Cursor,MapSelector,LevelId
from .selective_models import Model
from .image_preview_models import ImageInfoRequest
from .map_note_models import MapNoteEntry,NoteKeys

LevelUUID=Annotated[str,Field(pattern=r'^Scene\.[A-Za-z0-9_-]{1,128}\.Level\.[A-Za-z0-9_-]{1,128}$')]
TileUUID=Annotated[str,Field(pattern=r'^Scene\.[A-Za-z0-9_-]{1,128}\.Tile\.[A-Za-z0-9_-]{1,128}$')]
Number=Annotated[int|float,Field(description='Finite stored numeric value; null and absence remain distinct.')]


class MapInfoRequest(Model):
    scene_uuid: SceneUUID
    level_id: LevelId|None=Field(default=None,description='Omitted/null means all permitted levels; choose an exact returned ID to filter. Never defaults to viewed/active level.')
    section: Literal['assets','tiles','notes']=Field(default='assets',description='Assets returns level image roles; tiles inventories files/placement; notes requires exact level_id and returns bounded aliases/identities without bodies.')
    note_keys: NoteKeys|None=None
    expected_revision: Revision|None=Field(default=None,description='Require the exact metadata revision from get_map_info; mismatch requires restarting all pages.')
    limit: int=Field(default=10,ge=1,le=100)
    max_bytes: int=Field(default=8000,ge=1024,le=48000,description='Maximum compact UTF8 JSON bytes including metadata/continuation; complete identities never clip.')
    cursor: Cursor|None=None

    @model_validator(mode='after')
    def note_scope(self):
        if self.section=='notes' and self.level_id is None:raise ValueError('Notes require an exact level_id from get_map_info assets')
        if 'note_keys' in self.model_fields_set and self.section!='notes':raise ValueError('note_keys is only valid for section=notes')
        if self.note_keys is not None:
            if len(set(self.note_keys))!=len(self.note_keys):raise ValueError('note_keys must be distinct')
            if self.expected_revision is None:raise ValueError('note_keys requires expected_revision from this exact Scene/level')
        return self


class MapSceneIdentity(MapNamed):
    scene_uuid: SceneUUID
    parent_uuid: FolderUUID|None
    ancestry: list[FolderIdentity]


class SceneRectangle(Model):
    sceneX: Number
    sceneY: Number
    sceneWidth: Number
    sceneHeight: Number


class MapGeometry(Model):
    width: Number|None=None
    height: Number|None=None
    padding: Number|None=None
    shiftX: Number|None=None
    shiftY: Number|None=None
    scene_rect: SceneRectangle=Field(description='Public getDimensions rectangle including grid-rounded padding/shift; not original file pixel size.')


class MapGrid(Model):
    type: int|None=None
    size: Number|None=None
    distance: Number|None=None
    units: str|None=Field(default=None,max_length=512)
    style: str|None=Field(default=None,max_length=512)
    thickness: Number|None=None
    color: str|None=Field(default=None,max_length=128)
    alpha: Number|None=None


class ImageSourceArguments(Model):
    request: ImageInfoRequest


class MapImageInfoNext(Model):
    tool: Literal['get_foundry_image_info']
    arguments: ImageSourceArguments


class MapImageUrlNext(Model):
    tool: Literal['get_foundry_image_url']
    arguments: ImageSourceArguments


class MapMedia(Model):
    reference: str|None=Field(max_length=4096,description='Exact safe stored source hint, never a credential-bearing/signed reference; not verified file existence.')
    reference_status: Literal['missing','empty','null','safe','sensitive','unsupported']
    media_kind: Literal['image','video','unknown','none']
    support_status: Literal['reference_only','missing','unsupported_video','unsupported_reference','map_context_required']
    info_next_call: MapImageInfoNext|None
    preview_next_call: MapImageUrlNext|None

    @model_validator(mode='after')
    def consistent_reference(self):
        if self.reference_status in ('sensitive','unsupported','missing','null') and self.reference is not None:
            raise ValueError('Unavailable reference must not expose source text')
        if self.reference_status=='empty' and self.reference!='':raise ValueError('Empty reference differs')
        if self.reference_status=='safe' and not self.reference:raise ValueError('Missing safe reference')
        if self.reference_status=='safe':
            value=self.reference;parsed=urlsplit(value)
            if (parsed.username or parsed.password or parsed.query or parsed.fragment or '?' in value or '#' in value
                    or parsed.scheme not in ('','http','https') or value.startswith('//')
                    or re.search(r'[\\\x00-\x1f\x7f]|%(?![0-9a-fA-F]{2})',value)):
                raise ValueError('Sensitive or unsupported source hint')
            for segment in parsed.path.split('/'):
                decoded=unquote(segment,errors='strict')
                if decoded in ('.','..') or re.search(r'[/\\\x00-\x1f\x7f]',decoded):raise ValueError('Invalid source path')
        map_selector=getattr(self,'map',None)
        supported=self.reference_status=='safe' and self.media_kind=='image'
        eligible=supported or map_selector is not None and self.reference_status=='sensitive' and self.media_kind!='video'
        if eligible!=(self.info_next_call is not None) or eligible!=(self.preview_next_call is not None):
            raise ValueError('Inconsistent image followups')
        for call in (self.info_next_call,self.preview_next_call):
            expected_args={'map':map_selector.model_dump()} if map_selector is not None else {'src':self.reference}
            if call and call.arguments.request.model_dump(exclude_none=True)!=expected_args:
                raise ValueError('Wrong image source followup')
        expected=('reference_only' if supported else 'map_context_required' if self.reference_status=='sensitive'
            else 'missing' if self.reference_status in ('missing','empty','null') else 'unsupported_video'
            if self.media_kind=='video' else 'unsupported_reference')
        if self.support_status!=expected:raise ValueError('Inconsistent media support')
        return self


class LevelMedia(MapMedia):
    role: Literal['background','foreground']
    map: MapSelector

    @model_validator(mode='after')
    def matching_role(self):
        if self.map.role!=self.role:raise ValueError('Wrong map role')
        return self


class LevelElevation(Model):
    bottom: Number|None=None
    top: Number|None=None


class MapLevelEntry(MapNamed):
    kind: Literal['level']
    level_id: LevelId
    level_uuid: LevelUUID
    sort: int|None
    elevation: LevelElevation|None=None
    background: LevelMedia
    foreground: LevelMedia


class TilePlacement(Model):
    x: Number|None=None
    y: Number|None=None
    width: Number|None=None
    height: Number|None=None
    rotation: Number|None=None
    elevation: Number|None=None
    anchorX: Number|None=None
    anchorY: Number|None=None
    scaleX: Number|None=None
    scaleY: Number|None=None
    fit: str|None=Field(default=None,max_length=128)


class TileLevelMembership(Model):
    declared_ids: list[LevelId]|None=Field(description='Stored exact level IDs; null/empty/absent applicability is not inferred.')
    status: Literal['explicit','not_evaluated']

    @model_validator(mode='after')
    def status_matches(self):
        if (self.status=='explicit')!=bool(self.declared_ids):raise ValueError('Inconsistent membership status')
        if self.declared_ids and len(set(self.declared_ids))!=len(self.declared_ids):raise ValueError('Duplicate level IDs')
        return self


class MapTileEntry(Model):
    kind: Literal['tile']
    tile_uuid: TileUUID
    name: str|None=Field(default=None,max_length=256)
    name_truncated: bool
    sort: Number|None
    placement: TilePlacement
    media: MapMedia
    level_membership: TileLevelMembership


class MapArtwork(Model):
    levels: int=Field(ge=0)
    tiles: int=Field(ge=0)
    background_references: int=Field(ge=0)
    foreground_references: int=Field(ge=0)


class MapInfoResult(Model):
    scene: MapSceneIdentity
    geometry: MapGeometry
    grid: MapGrid
    initial_level_id: LevelId|None=None
    level_id: LevelId|None
    section: Literal['assets','tiles','notes']
    revision: Revision
    entries: list[Annotated[MapLevelEntry|MapTileEntry|MapNoteEntry,Field(discriminator='kind')]]=Field(max_length=100)
    total: int=Field(ge=0)
    complete: bool
    next_cursor: Cursor|None
    scope_status: Literal['complete','partial']
    limitations: list[Annotated[str,Field(max_length=512)]]=Field(max_length=16)
    artwork: MapArtwork
