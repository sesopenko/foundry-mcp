"""Worker-only fixed note-key typography; no placement or journal text input.

libvips8.18 text uses Pango points at explicit DPI.12pt at96DPI targets16px
em, not16px ink. Real outlined ink must fit20px; keys are never scaled to fit.
See docs/plans/image-viewing/note-glyphs.md for measured output and licensing.
"""
from dataclasses import dataclass,field
import hashlib
import os
from pathlib import Path
import re

from .image_preview_failure import PreviewFailure

FONT_DIR=Path(__file__).resolve().parent/'fonts'
FONT_FILE=FONT_DIR/'DejaVuSans.ttf'
FONT_SHA256='57f73e11f51999432bf7ab22ce55b6f945d5eca1bf824404cfa9ec2e3718c84e'
MAX_GLYPH_WIDTH=192
MAX_INK_HEIGHT=20
MAX_KEYS=100
KEY=re.compile(r'N[1-9][0-9]{0,14}',re.ASCII)


def validate_keys(keys):
    """Validate the complete bounded batch before font/native work."""
    if (not isinstance(keys,(list,tuple)) or not 1<=len(keys)<=MAX_KEYS
            or any(type(key) is not str or KEY.fullmatch(key) is None for key in keys)
            or len(set(keys))!=len(keys)):
        raise PreviewFailure('InvalidOperation')
    return tuple(keys)


def verified_font():
    """Fail closed instead of libvips' warn-and-fallback fontfile behavior."""
    try:
        if FONT_FILE.is_symlink() or not FONT_FILE.is_file() or FONT_FILE.stat().st_size!=759720:
            raise ValueError('Font unavailable')
        if hashlib.sha256(FONT_FILE.read_bytes()).hexdigest()!=FONT_SHA256:
            raise ValueError('Font changed')
    except (OSError,ValueError):
        raise PreviewFailure('ImageProcessingFailed') from None
    return FONT_FILE


@dataclass(frozen=True,repr=False)
class NoteGlyph:
    key: str
    width: int
    height: int
    image: object=field(repr=False)


def rasterize_keys(keys):
    """Return at most100 measured, nonpremultiplied8bit sRGB RGBA glyphs.

    No caller-selectable font, DPI or path. Only generated ASCII aliases enter
    Pango. A3x3 maximum filter expands antialiased fill by exactly one output
    pixel in Chebyshev distance; white fill is composited over dark outline.
    Native images remain inside the supervised worker for layout/encoding.
    """
    keys=validate_keys(keys)
    font=verified_font()
    # Production workspace sets this before process/native initialization.
    os.environ['FONTCONFIG_FILE']=str(FONT_DIR/'fonts.conf')
    from .image_preview_worker import initialise
    vips=initialise()
    result=[]
    try:
        for key in keys:
            mask=vips.Image.text(key,font='DejaVu Sans 12',fontfile=str(font),dpi=96,wrap='none')
            if mask.bands!=1 or mask.format!='uchar' or not (1<=mask.width<=MAX_GLYPH_WIDTH-2 and 1<=mask.height<=MAX_INK_HEIGHT-2):
                raise PreviewFailure('ImageProcessingFailed')
            fill=mask.embed(1,1,mask.width+2,mask.height+2,extend='black')
            outline=fill.rank(3,3,8)
            white=(fill*0+255).cast('uchar')
            dark=(fill*0+24).cast('uchar')
            front=white.bandjoin([white,white,fill]).copy(interpretation='srgb')
            back=dark.bandjoin([dark,dark,outline]).copy(interpretation='srgb')
            image=back.composite2(front,'over',compositing_space='srgb').cast('uchar').copy_memory()
            result.append(NoteGlyph(key,image.width,image.height,image))
    except (vips.Error,OSError,ValueError):
        raise PreviewFailure('ImageProcessingFailed') from None
    return tuple(result)


def glyph_atlas(keys,scratch):
    """Bounded private verification artifact; no Scene/source-image dependency."""
    glyphs=rasterize_keys(keys)
    from .image_preview_worker import initialise
    vips=initialise()
    width=max(g.width for g in glyphs);height=sum(g.height for g in glyphs)
    atlas=vips.Image.black(width,height,bands=4).copy(interpretation='srgb')
    y=0
    for glyph in glyphs:
        atlas=atlas.insert(glyph.image,0,y,expand=False);y+=glyph.height
    path=Path(scratch)/'glyphs.png'
    from .image_preview_encode import write_candidate
    write_candidate(atlas,path,'image/png',None)
    return dict(sizes=[[g.width,g.height] for g in glyphs],width=width,height=height,size_bytes=path.stat().st_size)
