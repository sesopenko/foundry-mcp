"""Private supervised typography/package verification; never an MCP tool."""
import asyncio
from dataclasses import dataclass,field,asdict
import hashlib
import json
import os
import sys
from typing import Annotated

from pydantic import Field,model_validator

from .image_preview_artifact import inspect_artifact
from .image_preview_failure import PreviewFailure
from .image_preview_process import worker_reply
from .image_preview_resources import WorkerMetrics
from .image_preview_supervisor import current_supervisor
from .map_note_glyphs import MAX_GLYPH_WIDTH,MAX_INK_HEIGHT,MAX_KEYS,validate_keys
from .mcp_server.selective_models import Model

Width=Annotated[int,Field(ge=1,le=MAX_GLYPH_WIDTH)]
MAX_ATLAS_BYTES=MAX_GLYPH_WIDTH*MAX_INK_HEIGHT*MAX_KEYS*4+65536


class AtlasMetadata(Model):
    sizes: list[Annotated[list[int],Field(min_length=2,max_length=2)]]=Field(min_length=1,max_length=MAX_KEYS)
    width: Width
    height: int=Field(ge=1,le=MAX_INK_HEIGHT*MAX_KEYS)
    size_bytes: int=Field(ge=1,le=MAX_ATLAS_BYTES)

    @model_validator(mode='after')
    def dimensions(self):
        if any(not 1<=w<=MAX_GLYPH_WIDTH or not 1<=h<=MAX_INK_HEIGHT for w,h in self.sizes):
            raise ValueError('Invalid glyph geometry')
        if self.width!=max(w for w,h in self.sizes) or self.height!=sum(h for w,h in self.sizes):
            raise ValueError('Inconsistent atlas geometry')
        return self


class AtlasReply(Model):
    glyphs: AtlasMetadata


@dataclass(frozen=True,repr=False)
class GlyphAtlas:
    keys: tuple[str,...]
    sizes: tuple[tuple[int,int],...]
    png: bytes=field(repr=False)


async def probe_glyphs(keys,*,supervisor=None,metrics=None,timeout=None):
    """Verify bounded private atlas bytes after child reaping, before cleanup."""
    keys=validate_keys(keys)
    payload=json.dumps(dict(operation='glyphs',keys=keys),separators=(',',':')).encode()
    def collect(workspace,raw):
        metadata=AtlasReply.model_validate(worker_reply(raw)).glyphs
        if len(metadata.sizes)!=len(keys):raise PreviewFailure('ImageProcessingFailed')
        path=workspace.path/'glyphs.png'
        if path.is_symlink() or not path.is_file():raise PreviewFailure('ImageProcessingFailed')
        with path.open('rb') as stream:png=stream.read(MAX_ATLAS_BYTES+1)
        if len(png)>MAX_ATLAS_BYTES or inspect_artifact(png)!=dict(width=metadata.width,height=metadata.height,mime_type='image/png',size_bytes=metadata.size_bytes):
            raise PreviewFailure('ImageProcessingFailed')
        return GlyphAtlas(keys,tuple(tuple(pair) for pair in metadata.sizes),png)
    try:
        return await (supervisor or current_supervisor()).run(payload,collect=collect,metrics=metrics,timeout=timeout)
    except (ValueError,TypeError,OSError):raise PreviewFailure('ImageProcessingFailed') from None


async def smoke():
    metrics=WorkerMetrics()
    atlas=await probe_glyphs(['N1','N12','N100','N999999999999999'],metrics=metrics)
    return dict(uid=os.getuid(),sizes=atlas.sizes,png_bytes=len(atlas.png),
        sha256=hashlib.sha256(atlas.png).hexdigest(),metrics=asdict(metrics))


if __name__=='__main__':
    if sys.argv[1:]!=['--smoke']:raise SystemExit('Use --smoke for private glyph verification')
    print(json.dumps(asyncio.run(smoke()),separators=(',',':')))
