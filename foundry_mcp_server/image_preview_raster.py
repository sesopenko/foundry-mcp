"""Explicit raster compatibility adapters inside the supervised preview worker.

libvips8.18 has no built-in BMP decoder. Pillow13's BMP decoder, APNG frame
composition and timed AVIF frames normalize to a private PNG; libvips still owns
orientation, crops, colour conversion, resampling and final encoding. No general
loader/delegate guessing. Probe paths do not allocate these pixel buffers.
https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
"""
import os
from pathlib import Path
import struct

from .image_preview_failure import PreviewFailure


def avif_brand(path,size):
    """Bounded BMFF ftyp brand admission; never admit unrelated HEIC containers."""
    with path.open('rb') as stream:
        header = stream.read(16)
        if len(header)!=16 or header[4:8]!=b'ftyp':return False
        length = int.from_bytes(header[:4],'big')
        # Extended-size/large brand tables are unsupported, not arbitrary reads.
        if not 16<=length<=min(size,4096) or length%4:return False
        brands = [header[8:12]] + [stream.read(4) for _ in range((length-16)//4)]
    return bool(set(brands)&{b'avif',b'avis'})


def normalize(image):
    """Decode an already admitted/bounded first frame into owned disk storage."""
    from .image_preview_worker import initialise
    target = Path(os.environ['TMPDIR'])/'normalized.png'
    descriptor = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(descriptor,'wb') as stream:
        # Palette transparency must survive normalization. Carry ICC/EXIF into
        # the private intermediate only, for the shared sRGB/orientation stage.
        image.convert('RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB').save(
            stream,format='PNG',icc_profile=image.info.get('icc_profile'),exif=image.info.get('exif',b''))
    return initialise().Image.pngload(str(target),access='random',fail_on='warning')


def bitmap(path,size,*,header_only):
    from PIL import Image
    from .image_preview_worker import dimensions
    # Admit dimension limits before Pillow's own bomb check or any pixel decode.
    with path.open('rb') as stream:header = stream.read(30)
    if len(header)<26:raise PreviewFailure('UnsupportedImage')
    dib = int.from_bytes(header[14:18],'little')
    if dib==12:width,height = struct.unpack('<HH',header[18:22])
    elif dib>=40 and len(header)>=26:
        width,height = struct.unpack('<ii',header[18:26])
        height = abs(height)
    else:raise PreviewFailure('UnsupportedImage')
    dimensions(width,height)
    with Image.open(path,formats=['BMP']) as image:
        if image.size!=(width,height):raise PreviewFailure('UnsupportedImage')
        native = None if header_only else normalize(image)
    return native,dict(width=width,height=height,mime_type='image/bmp',size_bytes=size,frame_policy='still')


def png_frame(path,native,*,header_only):
    """Read APNG header policy; optional fallback is not an animation frame.

    Pillow's documented default_image flag requires seek(1) to select the first
    animation frame. Ordinary PNG and APNG without fallback stay native/lazy.
    """
    from PIL import Image
    with Image.open(path,formats=['PNG']) as image:
        pages = image.n_frames
        if image.info.get('default_image') and not header_only:
            image.seek(1)
            native = normalize(image)
        return native,pages


def avif_frames(path,native,*,header_only):
    """libheif enumerates image items, not timed AVIF sequence frames.

    Read Pillow's documented sequence count and normalize its first frame only
    for sequences. Still AVIF retains libvips' demand-driven loader.
    """
    from PIL import Image,AvifImagePlugin
    # Pinned Pillow13 upstream exposes this decoder option as a module global:
    # github.com/python-pillow/Pillow/blob/13.0.0/src/PIL/AvifImagePlugin.py
    # Restore it for in-process unit use; production runs in its own worker PID.
    previous = AvifImagePlugin.DEFAULT_MAX_THREADS
    AvifImagePlugin.DEFAULT_MAX_THREADS = 2
    try:
        with Image.open(path,formats=['AVIF']) as image:
            pages = image.n_frames
            if pages>1 and not header_only:
                native = normalize(image)
            return native,pages
    finally:
        AvifImagePlugin.DEFAULT_MAX_THREADS = previous
