# Preview decoder development

The internal preview worker is separate from the existing Pillow upload
validator. It has no MCP registration until the image-tool integration tasks.
Upload behavior and its32-million-pixel/8,192-edge limits remain unchanged.

## Dependencies and packaging

Use the standard repository workflow: `uv sync --locked`. Exact direct pins are
`pyvips[binary]==3.2.0` and `pyvips-binary==8.18.7`; the latter supplies native
libvips/codecs inside the virtual environment copied into the production image.
No host libvips installation, compiler or sudo is needed on the tested Linux
amd64 platform. Other wheel platforms exist upstream but are unverified here.
Unrelated dependency versions/hashes were retained.

The upstream [binding](https://pypi.org/project/pyvips/) documents the binary
installation option; [native packaging](https://pypi.org/project/pyvips-binary/)
tracks the libvips version. Research/installation on2026-11-11 verified pyvips
3.2.0/libvips8.18.7 in CFFI API mode. The bundled runtime reports jpeg/png/webp,
gif/tiff/heif/svg and text operations; Magick is absent. Operation presence is
not acceptance of unimplemented formats or proof of later font/render behavior.

Dockerfile runs `python -m foundry_mcp_server.image_preview_worker --smoke` after
switching to UID10001. This creates/removes its own tiny PNG, loads the native
runtime and probes real bytes. A local production-image build/run requires no
Foundry instance, ports, game data volumes, publication or release.

## Initial05a boundary

`image_preview_process.probe_image(path)` is an internal async operation on a
private staged regular file. The worker selects explicit jpegload/pngload/
webpload operations from source signatures; it never asks libvips to guess a
loader, executes delegates, accepts URL retrieval or uses filename options.
Additional raster formats belong to07a and sanitized SVG to07b.

Metadata fields are `width,height,mime_type,size_bytes,frame_policy`. Width and
height describe original display-oriented pixels; EXIF orientations5–8 swap
axes. JPEG autorotate is explicitly false at load; later extraction must orient
the same source. Multi-frame WebP loads page0/n1 and reports first_frame when
the native header declares multiple pages. Header probing need not decode the
full raster body; a later render can reject corrupt pixel data.

The worker enforces128-MiB compressed,32,768 per-edge and128,000,000-pixel source
limits. ImageTooLarge includes safely known display dimensions when available;
UnsupportedImage covers malformed headers and unsupported loaders. Native
messages/paths/metadata never leave the worker. Parent Pydantic validation repeats
metadata type/area/size checks and checks the staged byte length.

This uses documented demand-driven [file loading](https://www.libvips.org/API/current/ctor.Image.new_from_file.html),
explicit [JPEG orientation](https://www.libvips.org/API/current/ctor.Image.jpegload.html),
[WebP page selection](https://www.libvips.org/API/current/ctor.Image.webpload.html)
and [operation cache controls](https://libvips.github.io/pyvips/voperation.html).
Online pyvips reference pages label3.1.0; operation signatures/behavior were
checked with installed3.2.0/libvips8.18.7 rather than assuming docs match.

Native threads are capped through VIPS_CONCURRENCY=2 before import, operation
cache disabled, cache memory16 MiB and cached files16. The parent bounds stdout
while reading to4,096 bytes, discards stderr, enforces a deadline and kills/reaps
on overflow/error/timeout/cancellation. Temporary scratch and codec/cache temp
environment point to a private directory separate from originals. Known server,
Auth0 and AWS credential environment variables are not forwarded.

Task05b must add independent RSS/scratch/concurrency supervision before any
production MCP tool exposes this boundary. A native cache limit alone is not an
RSS limit. Full format/large-map/font/crop acceptance remains later work.

## Verification

`test_image_preview_probe.py` uses real decoder subprocesses for format detection,
all eight orientation dimensions, malformed/unsafe/misnamed inputs, exact128-MiB
sparse files,32,768-edge/128-million-pixel headers and known oversize. Small valid
headers deliberately retain small raster bodies to prove probe does not allocate
a huge raster merely to read/reject dimensions. These fixtures are not claimed
to be valid full images. Mocked child failures separately prove bounded output,
timeout/cancellation kill/reap, private scratch cleanup and parent validation.

The spawn-error regression failed because subprocess creation occurred outside
the fixed-error boundary. The unchanged test passed after catching that OSError
and returning ImageProcessingFailed without native paths. Unsuccessful
corrections0. Upload baseline13 tests passed unchanged. Final full-suite and
packaged UID10001 evidence are recorded in task05a's completion record.
