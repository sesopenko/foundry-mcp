"""Strict core Foundry map navigation contracts, independent of PF2e."""
from typing import Annotated,Literal
import base64
import json

from pydantic import Field,model_validator

from .selective_models import Model

FolderUUID=Annotated[str,Field(pattern=r'^Folder\.[A-Za-z0-9_-]{1,128}$',description='Canonical world Folder UUID from browse_maps, never a folder name, path or Scene UUID.')]
SceneUUID=Annotated[str,Field(pattern=r'^Scene\.[A-Za-z0-9_-]{1,128}$',description='Canonical world Scene UUID from browse_maps; excludes compendium UUIDs and names.')]
Revision=Annotated[str,Field(max_length=128,pattern=r'^(?:[0-9a-f]{64}|http-[0-9]+-[0-9a-f]+-[0-9a-f]+)$')]
Cursor=Annotated[str,Field(min_length=1,max_length=4096,description='Opaque returned next_cursor. Return unchanged with the same folder/filter; count/byte bounds may change.')]


class BrowseMapsRequest(Model):
    folder_uuid: FolderUUID|None=Field(default=None,description='Null/omitted means world Scene root. Use a returned folder next_call to descend.')
    name_contains: str=Field(default='',max_length=256,description='Literal case-insensitive substring of immediate folder/map names only; no recursive or image-content search.')
    limit: int=Field(default=10,ge=1,le=100,description='Maximum returned immediate child entries, folders before maps.')
    max_bytes: int=Field(default=8000,ge=1024,le=48000,description='Maximum compact UTF8 JSON response bytes, including identity, entries and continuation.')
    cursor: Cursor|None=None


class MapCursor(Model):
    offset: int=Field(ge=0)
    revision: Revision
    scope: Revision


def decode_cursor(value):
    if value is None:return None
    return MapCursor.model_validate(json.loads(base64.b64decode(value,validate=True).decode('utf-8')))


class MapNamed(Model):
    name: str=Field(max_length=256)
    name_truncated: bool

    @model_validator(mode='after')
    def truncation_marker(self):
        if self.name_truncated and len(self.name)!=256:raise ValueError('Inconsistent clipped name')
        return self


class FolderIdentity(MapNamed):
    folder_uuid: FolderUUID


class MapLocation(MapNamed):
    folder_uuid: FolderUUID|None
    ancestry: list[FolderIdentity]=Field(description='Named ancestors from root to parent, excluding this folder.')
    sorting: Literal['a','m']
    locale: str=Field(min_length=1,max_length=128,description='Standard browser collation locale, bound to the metadata revision.')


class BrowseFolderArguments(Model):
    folder_uuid: FolderUUID


class ReadMapArguments(Model):
    scene_uuid: SceneUUID


class BrowseFolderNext(Model):
    tool: Literal['browse_maps']
    arguments: BrowseFolderArguments


class ReadMapNext(Model):
    tool: Literal['get_map_info']
    arguments: ReadMapArguments


class MapChild(MapNamed):
    parent_uuid: FolderUUID|None
    ancestry: list[FolderIdentity]
    sort: int|None=Field(description='Stored manual sort value; null means unavailable, ordered as zero with UUID tie-breaks.')


class MapFolderNode(MapChild):
    kind: Literal['folder']
    folder_uuid: FolderUUID
    sorting: Literal['a','m']
    next_call: BrowseFolderNext


class MapSceneNode(MapChild):
    kind: Literal['map']
    scene_uuid: SceneUUID
    image_status: Literal['not_checked']=Field(description='Every readable Scene is included; inspect get_map_info assets for missing/video/background/foreground availability.')
    next_call: ReadMapNext


MapNode=Annotated[MapFolderNode|MapSceneNode,Field(discriminator='kind')]


class BrowseMapsResult(Model):
    location: MapLocation
    revision: Revision=Field(description='Observed catalog metadata/permission revision, not original image bytes or get_map_info revision.')
    entries: list[MapNode]=Field(max_length=100)
    total: int=Field(ge=0,description='Authorized immediate entries matching this local name filter.')
    complete: bool=Field(description='Completion of this selected page stream; partial scope does not establish exhaustive availability.')
    next_cursor: Cursor|None
    scope_status: Literal['complete','partial']
    limitations: list[Annotated[str,Field(max_length=512)]]=Field(max_length=16)
