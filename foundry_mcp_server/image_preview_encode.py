"""Native encoding candidates and verification, independent from process ownership."""
from pathlib import Path
import os
import time

from . import image_preview_limits as limits
from .image_preview_artifact import inspect_artifact
from .image_preview_failure import PreviewFailure
from .image_preview_geometry import output_dimensions,prepare_region


def write_candidate(image, path, mime, quality):
    descriptor = os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(descriptor)
    # Generated artifacts carry a fixed technical resolution, never source DPI.
    image = image.copy(xres=96/25.4,yres=96/25.4)
    if mime=='image/png':
        image.pngsave(str(path),strip=True,compression=6,filter='all')
    elif mime=='image/webp':
        image.webpsave(str(path),strip=True,Q=quality,alpha_q=100,effort=4,exact=True)
    elif mime=='image/jpeg':
        if image.hasalpha():image=image.flatten(background=[255,255,255],max_alpha=255)
        # strip=True removes JFIF resolution as well as source metadata.
        # Add only our fixed technical header, never copy a source segment.
        data=image.jpegsave_buffer(strip=True,Q=quality,interlace=False,
                                   subsample_mode='off',optimize_coding=True)
        if data[:2]!=b'\xff\xd8' or data[2:4]==b'\xff\xe0':
            raise PreviewFailure('ImageProcessingFailed')
        with path.open('wb') as stream:
            stream.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\0\x01\x01\x01\x00\x60\x00\x60\0\0')
            stream.write(memoryview(data)[2:])
    else:
        raise PreviewFailure('ImageProcessingFailed')


def verify_candidate(path, width, height, mime):
    from .image_preview_worker import initialise,open_original
    pyvips = initialise()
    try:
        image,metadata = open_original(path)
        if (metadata['width'],metadata['height'],metadata['mime_type'])!=(width,height,mime):
            raise PreviewFailure('ImageProcessingFailed')
        # Force full isolated decoding; a valid header alone does not prove pixels.
        image.avg()
        with path.open('rb') as stream:
            data = stream.read(limits.OUTPUT_MAX_BYTES+1)
        actual = inspect_artifact(data)
        if (actual['width'],actual['height'],actual['mime_type'])!=(width,height,mime):
            raise PreviewFailure('ImageProcessingFailed')
        return actual
    except (PreviewFailure,pyvips.Error,OSError,ValueError):
        raise PreviewFailure('ImageProcessingFailed') from None


def encode_region(region, scratch, *, max_bytes=limits.OUTPUT_MAX_BYTES,
                  writer=write_candidate,verify=verify_candidate,
                  clock=time.monotonic,deadline=None,compose=None,jpeg=False):
    """JPEG80 or PNG→WebP90→WebP82, then15% reductions from original region.

    The server passes its configured JPEG policy explicitly. Private callers
    default to the legacy lossless-first policy for geometry/fidelity checks.
    Injected budgets/encoder/clock are internal unit-test seams, never RPC inputs.
    Every candidate and the final verification stay in one supervised process.
    Optional trusted compose(image) returns final-size pixels and private notes
    for each encoding attempt; it always receives an unannotated resample.
    """
    if type(jpeg) is not bool:raise PreviewFailure('InvalidOperation')
    choices=(('image/jpeg',80),) if jpeg else (('image/png',None),('image/webp',90),('image/webp',82))
    scratch = Path(scratch)
    candidate = scratch/'candidate.bin'
    target = scratch/'preview.bin'
    deadline = clock()+limits.WORKER_TIMEOUT_SECONDS if deadline is None else deadline
    width,height = output_dimensions(region.width,region.height)
    while True:
        if clock()>=deadline:raise PreviewFailure('ImageProcessingTimeout')
        image = region.resample(width,height)
        for mime,quality in choices:
            try:
                if clock()>=deadline:raise PreviewFailure('ImageProcessingTimeout')
                annotated,notes=compose(image) if compose is not None else (image,None)
                writer(annotated,candidate,mime,quality)
                size = candidate.stat().st_size
                if size<1:
                    raise PreviewFailure('ImageProcessingFailed')
                if size>max_bytes:
                    continue
                actual = verify(candidate,width,height,mime)
                if actual!=dict(width=width,height=height,mime_type=mime,size_bytes=size):
                    raise PreviewFailure('ImageProcessingFailed')
                if clock()>=deadline:raise PreviewFailure('ImageProcessingTimeout')
                candidate.rename(target)
                return {**actual,'map_notes':notes} if compose is not None else actual
            finally:
                candidate.unlink(missing_ok=True)
        if (width,height)==(1,1):raise PreviewFailure('ImageProcessingFailed')
        width,height = max(1,width*85//100),max(1,height*85//100)


def render_preview(path, crop, scratch, *, jpeg=False):
    from .image_preview_worker import open_original
    image,metadata = open_original(path)
    region = prepare_region(image,metadata,crop)
    artifact = encode_region(region,scratch,jpeg=jpeg)
    return dict(source=metadata,region=region.bounds,**artifact)
