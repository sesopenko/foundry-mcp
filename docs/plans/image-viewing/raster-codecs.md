# Raster codecs and first-frame policy

The private preview worker admits formats from bytes, irrespective of filename.
It selects explicit operations, never general loader guessing, ImageMagick,
network retrieval or document delegates. SVG remains a separate safety task.

| Source | Decode boundary | Frame selection |
| --- | --- | --- |
| JPEG | libvips jpegload | Still; shared EXIF orientation |
| PNG | libvips pngload | Still |
| APNG | PNG header plus Pillow13 APNG metadata | First animation frame; separate fallback is skipped |
| WebP | libvips webpload | page0/n1 |
| GIF | libvips gifload | page0/n1 |
| TIFF/BigTIFF | libvips tiffload | page0/n1; autorotate false, then shared orientation |
| AVIF | libvips heifload, AVIF-only ftyp brands | page0/n1 for image items; Pillow13 first timed sequence frame |
| BMP | Pillow13 BMP-only decoder | Still |

Multiframe sources report `frame_policy:first_frame`; single-frame sources
report `still`. Output is a single bounded PNG/WebP, never animated source bytes.
GIF/TIFF/WebP explicitly request one page, preventing vertical frame stacks.
AVIF admission checks a complete ftyp brand table bounded to4096 bytes; extended
size or larger brand tables are unsupported. HEIC-only brands are rejected.

The pinned binary libvips has no built-in BMP loader or ImageMagick operation.
The BMP adapter opens only `formats=['BMP']`, checks declared dimensions before
pixel allocation, then uses Pillow only for decoding. APNG with a separate
default/fallback image requires Pillow's documented `seek(1)` to get the first
animation frame. libheif image-item counts do not describe timed AVIF sequence
frames: the real two-frame regression initially reported `still`. Pillow's
documented sequence count and first-frame decode resolve that distinction.

These three compatibility cases normalize an admitted first frame to a private
600-mode PNG in the supervised scratch directory. ICC/EXIF are preserved only
through that intermediate so the common libvips orientation/sRGB pipeline can
interpret them. Final encoding strips metadata. Cropping, resampling, output
encoding and candidate verification remain libvips operations for every format.
There is no Pillow decoder in the parent MCP process.

Info skips normalization/pixel decode. AVIF header parsing can read the bounded
compressed source into memory; it does not promise constant-memory header reads.
The128-MiB source,32768-edge/128-million-pixel admission and1-GiB RSS/2-GiB scratch/
90-second supervision apply throughout. Pillow's existing bomb protection is
retained, and upload validation remains in its separate worker unchanged.
The pinned Pillow AVIF decoder thread option is set to2 and restored afterward.
Native codec protections are retained too: libheif defaults to16384 per edge;
libtiff4.7 limits decoder allocation per file to50MB. These codec-specific guards
can reject variants below the project-wide upper limits; no unlimited loader
option is enabled.

## Public contracts and source evidence

- [libvips8.18 GIF](https://www.libvips.org/API/current/ctor.Image.gifload.html),
  [TIFF](https://www.libvips.org/API/current/ctor.Image.tiffload.html), and
  [HEIF](https://www.libvips.org/API/current/ctor.Image.heifload.html): page/n,
  TIFF orientation and decoder guards.
- [Pillow13 format documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html):
  BMP, APNG default-image/seek semantics, AVIF sequence support.
- [Pinned AVIF plugin source](https://github.com/python-pillow/Pillow/blob/13.0.0/src/PIL/AvifImagePlugin.py),
  fetched through GitHub MCP: decoder module options, compressed-source read,
  header count versus get_frame pixel decode. DEFAULT_MAX_THREADS is the exposed
  decoder option until Image.open supports per-call decoder parameters.

## Verification

`test_image_preview_formats.py` creates tiny real sources and invokes production
subprocess probe/render. It compares first-frame pixels, dimensions, alpha,
native-size crops and actual PNG output for every advertised raster. TIFF/AVIF
all8 orientation cases use independent Pillow display-pixel oracles. Truncated
bodies, malformed headers, unrelated loaders and BMP source-limit boundaries
are covered. A focused adapter test proves header probing never normalizes
pixels, and another verifies/restores the AVIF thread budget.

Final host/full and production UID10001 matrix results are recorded in
[task07a](tasks/07a-raster-codecs-and-frame-policy.md). The matrix prints only
technical UID/library/loader inventory; no game data or private pixel answers.
