"""Shared canonical file-location/image selector contracts for browsing and writing."""
import re
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic import Field, model_validator

from .selective_models import Model

Source = Literal['data', 'public', 's3']


def valid_directory(value):
    if len(value) > 2048 or re.search(r'[\\\x00-\x1f\x7f*?#]', value) or value.startswith('/') or re.match(r'^[a-zA-Z][\w+.-]*:', value):
        return False
    if re.search(r'%(?![0-9a-fA-F]{2})', value):
        return False
    decoded = unquote(value)
    return not re.search(r'[\\\x00-\x1f\x7f]', decoded) and not any(part in ('.', '..') for part in decoded.split('/'))


class ImageLocation(Model):
    source: Source = 'data'
    directory: str = Field(default='', max_length=2048, description='Source-relative directory from a returned next_call; empty means source root. Not a journal folder or host path.')
    bucket: str | None = Field(default=None, min_length=2, max_length=255, pattern=r'^[A-Za-z0-9][A-Za-z0-9.-]+$', description='Required for configured s3 only; forbidden for data/public.')

    @model_validator(mode='after')
    def location_valid(self):
        if not valid_directory(self.directory):
            raise ValueError('directory must be a source-relative path without traversal, controls or globs')
        if (self.source == 's3') != (self.bucket is not None):
            raise ValueError('bucket is required for s3 and forbidden for other sources')
        return self



class ImageSelector(ImageLocation):
    source: Source
    directory: str = Field(max_length=2048)
    src: str = Field(min_length=1, max_length=4096, description='Exact browser-returned image source. Preserve this whole record for later embedding; never reconstruct from display name.')

    @model_validator(mode='after')
    def source_valid(self):
        if 'bucket' in self.model_fields_set and self.bucket is None:
            raise ValueError('omit an inapplicable bucket rather than null')
        if re.search(r'[\x00-\x1f\x7f\\]', self.src):
            raise ValueError('invalid image source')
        parsed = urlsplit(self.src)
        if parsed.scheme and parsed.scheme.lower() not in ('http', 'https'):
            raise ValueError('unsupported image URL protocol')
        if not parsed.path.lower().endswith(('.apng', '.avif', '.bmp', '.gif', '.jpeg', '.jpg', '.png', '.svg', '.tiff', '.webp')):
            raise ValueError('unsupported image extension')
        return self
