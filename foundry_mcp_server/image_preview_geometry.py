"""Native display-oriented region pipelines, independent from worker lifecycle.

libvips8.18.7 contracts: autorot, extract_area, resize, premultiply/unpremultiply,
colourspace and icc_transform. Processing remains file-backed and demand-driven.
Each resampling candidate starts from the selected original, never a prior resize.
"""
from dataclasses import dataclass
import math

from . import image_preview_limits as limits
from .image_preview_failure import PreviewFailure


def crop_bounds(crop, width, height):
    """Exact zero-based contained rectangle; right/bottom are exclusive."""
    if crop is None:
        return dict(x=0,y=0,width=width,height=height)
    keys = {'x','y','width','height'}
    if (not isinstance(crop,dict) or set(crop)!=keys
            or any(type(crop[key]) is not int for key in keys)
            or crop['x']<0 or crop['y']<0 or crop['width']<1 or crop['height']<1
            or crop['x']+crop['width']>width or crop['y']+crop['height']>height):
        raise PreviewFailure('InvalidCrop',width,height)
    return dict(crop)


def output_dimensions(width, height):
    """One aspect scale, floored integral axes (minimum1px), no enlargement."""
    if type(width) is not int or type(height) is not int or min(width,height)<1:
        raise PreviewFailure('InvalidCrop')
    # Exact integer equivalents of floor(axis * min(1, edge/max_axis,
    # sqrt(area/(w*h)))). Avoid a binary-float underflow at exact1536².
    edge = max(width,height)
    return (max(1,min(width,width*limits.OUTPUT_MAX_EDGE//edge,
                     math.isqrt(limits.OUTPUT_MAX_PIXELS*width//height))),
            max(1,min(height,height*limits.OUTPUT_MAX_EDGE//edge,
                      math.isqrt(limits.OUTPUT_MAX_PIXELS*height//width))))


@dataclass
class RegionPipeline:
    original: object
    bounds: dict

    @property
    def width(self):return self.bounds['width']

    @property
    def height(self):return self.bounds['height']

    def resample(self, width, height):
        """Lanczos3 with alpha premultiplication; only integer rounding differs by axis."""
        if (type(width) is not int or type(height) is not int
                or not 1<=width<=self.width or not 1<=height<=self.height
                or max(width,height)>limits.OUTPUT_MAX_EDGE or width*height>limits.OUTPUT_MAX_PIXELS):
            raise PreviewFailure('ImageProcessingFailed')
        if (width,height)==(self.width,self.height):
            return self.original
        alpha = self.original.hasalpha()
        image = self.original.premultiply(max_alpha=255) if alpha else self.original
        image = image.resize(width/self.width,vscale=height/self.height,kernel='lanczos3')
        if alpha:
            image = image.unpremultiply(max_alpha=255).cast('uchar')
        if (image.width,image.height)!=(width,height):
            raise PreviewFailure('ImageProcessingFailed')
        return image


def prepare_region(image, metadata, crop=None):
    """Validate against display dimensions before extracting or allocating pixels.

    The image/metadata pair comes only from the allowlisted native source loader.
    Embedded ICC uses LCMS to built-in sRGB at8bit; otherwise declared native
    interpretation converts to sRGB. Extra alpha survives color conversion.
    """
    bounds = crop_bounds(crop,metadata['width'],metadata['height'])
    image = image.autorot()
    if (image.width,image.height)!=(metadata['width'],metadata['height']):
        raise PreviewFailure('ImageProcessingFailed')
    image = image.extract_area(bounds['x'],bounds['y'],bounds['width'],bounds['height'])
    if image.get_typeof('icc-profile-data'):
        image = image.icc_transform('srgb',embedded=True,depth=8)
    else:
        image = image.colourspace('srgb')
    return RegionPipeline(image,bounds)


def preview_to_source(region, preview_width, preview_height, selection):
    """Map preview pixels back conservatively: floor left/top, ceil exclusive ends."""
    selected = crop_bounds(selection,preview_width,preview_height)
    left = region['x']+(selected['x']*region['width'])//preview_width
    top = region['y']+(selected['y']*region['height'])//preview_height
    right = region['x']+math.ceil((selected['x']+selected['width'])*region['width']/preview_width)
    bottom = region['y']+math.ceil((selected['y']+selected['height'])*region['height']/preview_height)
    return dict(x=left,y=top,width=right-left,height=bottom-top)
