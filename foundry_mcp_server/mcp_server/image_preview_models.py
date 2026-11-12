"""Strict file/map preview contracts, with optional bounded annotation metadata.

No tools are registered here. Coordinates always describe the display-oriented
original. Public results contain neither source paths nor private transfer data.
"""
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
import re

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

from foundry_mcp_server import image_preview_limits as limits
from foundry_mcp_server.image_preview_errors import preview_error
from .journal_image_models import ImageSelector
from .selective_models import Model
from .map_models import MapSelector
from .map_image_models import MapNotesResult

SourceId = Annotated[str, Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$',
    description='Opaque caller-bound original snapshot handle returned by get_foundry_image_info or get_foundry_image_url; valid for 30 minutes from staging.')]
SourceEdge = Annotated[int, Field(ge=1, le=limits.SOURCE_MAX_EDGE)]
OutputEdge = Annotated[int, Field(ge=1, le=limits.OUTPUT_MAX_EDGE)]
Mime = Literal['image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/bmp', 'image/gif', 'image/tiff', 'image/svg+xml']


class Crop(Model):
    """Exact original-pixel rectangle with exclusive right/bottom edges."""

    x: int = Field(ge=0, le=limits.SOURCE_MAX_EDGE, description='Zero-based left edge in display-oriented original pixels.')
    y: int = Field(ge=0, le=limits.SOURCE_MAX_EDGE, description='Zero-based top edge in display-oriented original pixels.')
    width: SourceEdge = Field(description='Positive extent; right edge x+width is exclusive. No clipping or padding.')
    height: SourceEdge = Field(description='Positive extent; bottom edge y+height is exclusive. No clipping or padding.')

    @model_validator(mode='wrap')
    @classmethod
    def invalid_crop(cls, value, handler):
        try:
            return handler(value)
        except ValidationError:
            raise PydanticCustomError('InvalidCrop', 'InvalidCrop: use integer x/y >=0 and positive integer width/height, fully inside the original image; no extra fields.') from None

    def check_containment(self, width: int, height: int):
        """Call once original display dimensions are safely known; never clip."""
        if self.x + self.width > width or self.y + self.height > height:
            raise preview_error('InvalidCrop', width=width, height=height)
        return self


class ImageInfoRequest(Model):
    image: ImageSelector | None = Field(default=None, description='Exact image record from browse_journal_images or upload_image; mutually exclusive with src/map.')
    src: str | None = Field(default=None, min_length=1, max_length=4096,
        description='Stored journal img src or portrait reference. Selection hint only; fresh bounded parent listing must establish configured-source membership.')
    map: MapSelector|None=Field(default=None,description='Exact Scene/level/role from get_map_info assets; pins file bytes plus map/note context. Never defaults to active Scene or viewed level.')

    @field_validator('src')
    @classmethod
    def source_syntax(cls, value):
        if value is not None:
            ImageSelector(source='data', directory='', src=value)
        return value

    @model_validator(mode='after')
    def exclusive_source(self):
        names = ('image', 'src', 'map', 'source_id') if 'source_id' in type(self).model_fields else ('image', 'src', 'map')
        if any(name in self.model_fields_set and getattr(self, name) is None for name in names):
            raise ValueError('Omit unused input selectors rather than null')
        if sum(getattr(self, name) is not None for name in names) != 1:
            raise ValueError('Provide exactly one of ' + ', '.join(names))
        return self


class ImageUrlRequest(ImageInfoRequest):
    source_id: SourceId | None = None
    crop: Crop | None = Field(default=None, description='Optional exact rectangle in original display pixels; omit for the full image. InvalidCrop rejects malformed or out-of-bounds rectangles.')
    map_notes: bool=Field(default=False,description='Opt-in compact readable note keys. Requires map or a map-bound source_id and verified background placement; false omits annotation metadata entirely.')


def utc_timestamp(value: str):
    """Keep public ISO timestamps as JSON strings, strictly UTC and timezone-aware."""
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        raise ValueError('Use an absolute UTC ISO timestamp ending in Z')
    datetime.fromisoformat(value)
    return value


class SourceReceipt(Model):
    source_id: SourceId
    source_expires_at: str = Field(description='Absolute UTC expiry of this private original snapshot, 30 minutes from staging; independent of any public derivative.')

    _source_expiry = field_validator('source_expires_at')(utc_timestamp)


class ImageInfoResult(SourceReceipt):
    width: SourceEdge = Field(description='Original display-oriented width, before crop or resize.')
    height: SourceEdge = Field(description='Original display-oriented height, before crop or resize.')
    mime_type: Mime = Field(description='Actual detected source format, not an extension or HTTP hint.')
    size_bytes: int = Field(ge=1, le=limits.SOURCE_MAX_BYTES, description='Compressed original byte length.')
    frame_policy: Literal['still', 'first_frame'] = Field(description='Still source or first displayable frame/page of multiframe content.')

    @model_validator(mode='after')
    def source_area(self):
        if self.width * self.height > limits.SOURCE_MAX_PIXELS:
            raise ValueError('Original exceeds source pixel budget')
        return self


class ImageUrlResult(SourceReceipt):
    url: str = Field(max_length=2048, description='Public HTTPS capability URL; anyone holding it can read these pixels for seven days. No credentials required.')
    expires_at: str = Field(description='Absolute UTC expiry of this immutable derivative, exactly seven days from publication.')
    source_width: SourceEdge
    source_height: SourceEdge
    region: Crop = Field(description='Exact rectangle covered in original display-oriented pixels; independent of delivered dimensions.')
    width: OutputEdge = Field(description='Actual delivered raster width; never enlarged.')
    height: OutputEdge = Field(description='Actual delivered raster height; never enlarged.')
    mime_type: Literal['image/png', 'image/webp']
    size_bytes: int = Field(ge=1, le=limits.OUTPUT_MAX_BYTES, description='Exact encoded public derivative byte length.')
    map_notes: MapNotesResult|None=Field(default=None,exclude_if=lambda value:value is None,description='Present only for map_notes=true; bounded rendered keys/counts and exact legend next call, never a full legend.')

    _expiry = field_validator('expires_at')(utc_timestamp)

    @model_validator(mode='after')
    def derivative_valid(self):
        parsed = urlsplit(self.url)
        extension = 'png' if self.mime_type == 'image/png' else 'webp'
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or '?' in self.url or '#' in self.url
                or re.search(r'[\s\\\x00-\x1f\x7f]', self.url)
                or not re.fullmatch(r'/image-previews/[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.' + extension, parsed.path)):
            raise ValueError('Expected a canonical HTTPS UUIDv4 capability path matching MIME, without credentials, query or fragment')
        if self.source_width * self.source_height > limits.SOURCE_MAX_PIXELS:
            raise ValueError('Original exceeds source pixel budget')
        if self.region.x + self.region.width > self.source_width or self.region.y + self.region.height > self.source_height:
            raise ValueError('Region exceeds original dimensions')
        if self.width > self.region.width or self.height > self.region.height or self.width * self.height > limits.OUTPUT_MAX_PIXELS:
            raise ValueError('Derivative exceeds region or output pixel budget')
        return self
