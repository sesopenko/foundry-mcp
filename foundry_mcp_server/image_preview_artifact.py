"""Bounded JPEG/PNG/WebP validation without decoding in the server parent.

Only generated still8bit raster artifacts are accepted. Actual pixel decoding is
also verified in the isolated worker. WebP fields follow Google's RIFF/container
and lossless bitstream specifications; all lengths are checked before slicing.
"""
import struct
import zlib

from . import image_preview_limits as limits
from .image_preview_failure import PreviewFailure


def inspect_artifact(data):
    try:
        if not isinstance(data,bytes) or not 1<=len(data)<=limits.OUTPUT_MAX_BYTES:
            raise ValueError
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            mime,width,height = _png(data)
        elif data[:4]==b'RIFF' and data[8:12]==b'WEBP':
            mime,width,height = _webp(data)
        elif data.startswith(b'\xff\xd8'):
            from .image_preview_jpeg import inspect_jpeg
            mime,width,height = inspect_jpeg(data)
        else:
            raise ValueError
        if min(width,height)<1 or max(width,height)>limits.OUTPUT_MAX_EDGE or width*height>limits.OUTPUT_MAX_PIXELS:
            raise ValueError
        return dict(mime_type=mime,width=width,height=height,size_bytes=len(data))
    except (ValueError,IndexError,struct.error):
        raise PreviewFailure('ImageProcessingFailed') from None


def _png(data):
    offset,dimensions,has_pixels = 8,None,False
    while offset<len(data):
        if offset+12>len(data):raise ValueError
        size = int.from_bytes(data[offset:offset+4],'big')
        kind = data[offset+4:offset+8]
        end = offset+12+size
        if end>len(data):raise ValueError
        payload = data[offset+8:end-4]
        if zlib.crc32(kind+payload)!=int.from_bytes(data[end-4:end],'big'):raise ValueError
        if kind==b'IHDR':
            if offset!=8 or size!=13:raise ValueError
            width,height,depth,color,compression,filtering,interlace = struct.unpack('>IIBBBBB',payload)
            if depth!=8 or color not in (2,6) or compression or filtering or interlace:raise ValueError
            dimensions = width,height
        elif kind==b'IDAT':
            if dimensions is None:raise ValueError
            has_pixels = True
        elif kind==b'IEND':
            if size or end!=len(data) or not has_pixels:raise ValueError
            return 'image/png',*dimensions
        elif kind==b'pHYs':
            # The encoder resets resolution to96DPI rather than source metadata.
            if payload!=struct.pack('>IIB',3780,3780,1):raise ValueError
        else:
            # No EXIF/GPS/ICC/XMP/comments/animation/source metadata chunks.
            raise ValueError
        offset = end
    raise ValueError


def _webp(data):
    if len(data)<20 or int.from_bytes(data[4:8],'little')+8!=len(data):raise ValueError
    offset,canvas,pixels = 12,None,None
    while offset<len(data):
        if offset+8>len(data):raise ValueError
        kind = data[offset:offset+4]
        size = int.from_bytes(data[offset+4:offset+8],'little')
        end = offset+8+size
        if end+(size%2)>len(data):raise ValueError
        payload = data[offset+8:end]
        if size%2 and data[end]!=0:raise ValueError
        if kind==b'VP8X':
            if offset!=12 or size!=10 or payload[0]&~0x10 or payload[1:4]!=b'\0\0\0':raise ValueError
            canvas = (int.from_bytes(payload[4:7],'little')+1,int.from_bytes(payload[7:10],'little')+1)
        elif kind==b'VP8 ':
            if pixels is not None or size<10 or payload[0]&1 or payload[3:6]!=b'\x9d\x01\x2a':raise ValueError
            pixels = (int.from_bytes(payload[6:8],'little')&0x3fff,int.from_bytes(payload[8:10],'little')&0x3fff)
        elif kind==b'VP8L':
            if pixels is not None or size<5 or payload[0]!=0x2f:raise ValueError
            bits = int.from_bytes(payload[1:5],'little')
            if bits>>29:raise ValueError
            pixels = ((bits&0x3fff)+1,((bits>>14)&0x3fff)+1)
        elif kind==b'ALPH':
            if canvas is None or pixels is not None or size<1:raise ValueError
        else:
            raise ValueError
        offset = end+size%2
    if pixels is None or (canvas is not None and canvas!=pixels):raise ValueError
    return 'image/webp',*pixels
