"""Private libvips subprocess operations; no network or public path interface.

Explicit JPEG/PNG/WebP/GIF/TIFF/AVIF loaders and narrow BMP/APNG/AVIF-sequence
adapters, plus guarded static SVG. Header probing does not fully validate raster bodies.
No native error text or source metadata beyond compact technical values leaves
the worker. Resource supervision is completed in05b before any MCP exposure.
"""
import json
import logging
import os
from pathlib import Path
import sys
import tempfile

from . import image_preview_limits as limits
from .image_preview_failure import PreviewFailure

MAX_REQUEST_BYTES = 8192


def initialise():
    """Bound native threads/operation caches before opening any source file.

    https://libvips.github.io/pyvips/voperation.html and libvips8.18 loader docs.
    Explicit loaders avoid general loader guessing/delegates/filename options.
    """
    os.environ['VIPS_CONCURRENCY'] = '2'
    logging.getLogger('pyvips').disabled = True
    try:
        import pyvips
    except (ImportError, OSError):
        raise PreviewFailure('ImageProcessingFailed') from None
    pyvips.cache_set_max(0)
    pyvips.cache_set_max_mem(16*1024*1024)
    pyvips.cache_set_max_files(16)
    return pyvips


def dimensions(width, height):
    if (type(width) is not int or type(height) is not int or width < 1 or height < 1):
        raise PreviewFailure('UnsupportedImage')
    if (width > limits.SOURCE_MAX_EDGE or height > limits.SOURCE_MAX_EDGE or width*height > limits.SOURCE_MAX_PIXELS):
        raise PreviewFailure('ImageTooLarge', width, height)


def open_original(path, *, header_only=False):
    """File-backed demand-driven safe raster header boundary for later rendering.

    The caller supplies a private staged regular file, not a browser URL or host
    path from MCP. Returns native pipeline plus compact display-oriented metadata.
    JPEG autorotate is explicitly false; later extraction must orient the same
    original. Multiframe inputs select a single first frame/page. Compatibility
    adapters never decode pixels when header_only is true (the info operation).
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise PreviewFailure('UnsupportedImage')
    size = path.stat().st_size
    if size > limits.SOURCE_MAX_BYTES:
        raise PreviewFailure('ImageTooLarge')
    if size < 1:
        raise PreviewFailure('UnsupportedImage')
    with path.open('rb') as stream:
        header = stream.read(32)
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        loader, mime = 'pngload', 'image/png'
    elif header.startswith(b'\xff\xd8\xff'):
        loader, mime = 'jpegload', 'image/jpeg'
    elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        loader, mime = 'webpload', 'image/webp'
    elif header.startswith((b'GIF87a',b'GIF89a')):
        loader, mime = 'gifload', 'image/gif'
    elif header.startswith((b'II*\0',b'MM\0*',b'II+\0',b'MM\0+')):
        loader, mime = 'tiffload', 'image/tiff'
    elif header.startswith(b'BM'):
        from .image_preview_raster import bitmap
        return bitmap(path,size,header_only=header_only)
    elif header[4:8] == b'ftyp':
        from .image_preview_raster import avif_brand
        if not avif_brand(path,size):
            raise PreviewFailure('UnsupportedImage')
        loader, mime = 'heifload', 'image/avif'
    else:
        from .image_preview_svg import open_svg
        return open_svg(path,size)
    pyvips = initialise()
    # A region must support multiple independent encoding/resampling attempts.
    # Sequential-only decoders cannot rewind after evaluating the first one.
    # Random access stays lazy at header probe; native spill uses owned scratch.
    options = dict(access='random', fail_on='warning')
    if loader == 'jpegload':
        options['autorotate'] = False
    if loader in ('webpload','gifload','tiffload','heifload'):
        options.update(page=0, n=1)
    if loader == 'tiffload':
        options['autorotate'] = False
    try:
        image = pyvips.Operation.call(loader, str(path), **options)
        width, height = image.width, image.height
        orientation = image.get('orientation') if image.get_typeof('orientation') else 1
        pages = image.get('n-pages') if image.get_typeof('n-pages') else 1
        if type(orientation) is not int or not 1 <= orientation <= 8 or type(pages) is not int or pages < 1:
            raise PreviewFailure('UnsupportedImage')
        if orientation >= 5:
            width, height = height, width
        dimensions(width, height)
        if loader == 'pngload':
            from .image_preview_raster import png_frame
            image, pages = png_frame(path,image,header_only=header_only)
        if loader == 'heifload':
            from .image_preview_raster import avif_frames
            image, sequence_pages = avif_frames(path,image,header_only=header_only)
            pages = max(pages,sequence_pages)
        return image, dict(width=width, height=height, mime_type=mime, size_bytes=size,
            frame_policy='first_frame' if pages > 1 else 'still')
    except PreviewFailure:
        raise
    except pyvips.Error:
        raise PreviewFailure('UnsupportedImage') from None


def probe(path):
    _, metadata = open_original(path,header_only=True)
    return metadata


def region_pixels(path, crop):
    """Private lossless geometry intermediate;06b owns public encoding budgets."""
    from .image_preview_geometry import prepare_region,output_dimensions
    image,metadata = open_original(path)
    region = prepare_region(image,metadata,crop)
    width,height = output_dimensions(region.width,region.height)
    output = region.resample(width,height)
    target = Path(os.environ['TMPDIR'])/'region.png'
    descriptor = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(descriptor)
    output.pngsave(str(target),strip=True)
    return dict(source=metadata,region=region.bounds,width=width,height=height)


def encoded_pixels(path, crop):
    from .image_preview_encode import render_preview
    return render_preview(path,crop,Path(os.environ['TMPDIR']))


def smoke():
    """Small deterministic packaged-image probe, including actual effective UID."""
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix='preview-package-check-') as directory:
        path = Path(directory)/'original'
        Image.new('RGB',(16,12),(20,50,100)).save(path,format='PNG')
        metadata = probe(path)
    pyvips = initialise()
    return dict(uid=os.getuid(),pyvips=pyvips.__version__,libvips='.'.join(str(pyvips.version(i)) for i in range(3)),probe=metadata)


def main():
    try:
        if sys.argv[1:] == ['--smoke']:
            result = smoke()
        else:
            raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES+1)
            request = json.loads(raw) if len(raw) <= MAX_REQUEST_BYTES else None
            if isinstance(request,dict) and request.get('operation')=='glyphs':
                if set(request)!={'operation','keys'}:raise PreviewFailure('InvalidOperation')
                from .map_note_glyphs import glyph_atlas
                result={'glyphs':glyph_atlas(request['keys'],Path(os.environ['TMPDIR']))}
            elif (not isinstance(request,dict) or request.get('operation') not in ('probe','region','render')
                    or set(request) != ({'operation','source'} if request.get('operation')=='probe' else {'operation','source','crop'})
                    or not isinstance(request['source'],str) or not 1 <= len(request['source']) <= 4096):
                raise PreviewFailure('InvalidOperation')
            elif request['operation']=='probe':
                result = {'metadata':probe(request['source'])}
            elif request['operation']=='region':
                result = {'geometry':region_pixels(request['source'],request['crop'])}
            else:
                result = {'artifact':encoded_pixels(request['source'],request['crop'])}
    except PreviewFailure as failure:
        result = {'error_code':failure.code}
        if failure.width is not None and failure.height is not None:
            result.update(width=failure.width,height=failure.height)
    except Exception:
        result = {'error_code':'UnsupportedImage'}
    print(json.dumps(result,separators=(',',':'),allow_nan=False))


if __name__ == '__main__':
    main()
