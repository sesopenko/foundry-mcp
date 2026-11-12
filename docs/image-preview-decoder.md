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

## Raster admission

`image_preview_process.probe_image(path)` is an internal async operation on a
private staged regular file. The worker selects explicit JPEG/PNG/WebP/GIF/TIFF/
AVIF operations from source signatures; it never asks libvips to guess a
loader, executes delegates, accepts URL retrieval or uses filename options.
[Raster compatibility adapters](plans/image-viewing/raster-codecs.md) cover BMP,
APNG with a separate fallback image, and AVIF timed sequences inside the same
supervised worker. Sanitized SVG belongs to07b.

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

The shared supervisor below now supplies independent resource enforcement.
Full format/large-map/font/crop acceptance remains later work.

Private [crop geometry](plans/image-viewing/crop-geometry.md) now supports
display orientation, exact native regions and alpha-safe bounded resampling.
[Bounded encoding](plans/image-viewing/preview-encoding.md) now enforces PNG/
WebP ordering and delivered byte limits on private artifacts. Tool registration
and public delivery remain later tasks.

## Resource supervision

`image_preview_supervisor.PreviewSupervisor` coordinates dedicated components:

| Component | Responsibility |
| --- | --- |
| PreviewAdmission | Active permit, bounded queue, queue timeout/cancellation |
| PreviewWorkspace | Private scratch lifetime and decoder environment |
| PreviewChild | Spawn, bounded pipe exchange, cancellation-safe kill/drain/reap |
| ResourceMonitor | Linux resource observations, budget checks and private metrics |
| PreviewSupervisor | Processing deadline and coordination/error policy |
| probe_image | Operation request/result validation and original byte count |

One operation runs per server event loop, independently from the upload lock. At most8 requests may wait,
with a90-second queue deadline. Queue overflow/deadline returns
ImageProcessingBusy. Cancelling a queued call creates no process or scratch;
callers retain their own original-file leases until their operation finishes.

Each admitted probe/render uses a700 private temporary directory. Originals
stay outside it; every decoder/cache temporary-directory setting points inside.
The parent monitors Linux procfs VmRSS/VmHWM and scratch every25ms. It compares
resident memory against1GiB and logical/allocated scratch against2GiB, separately
from the90-second processing deadline. Native caches are not treated as RSS
limits. Scratch accounting deduplicates device/inode pairs, includes open
unlinked files through procfs descriptors, and never follows directory symlinks.
A4096-entry scan ceiling also bounds monitor work; exceeding it is a scratch
limit error. These monitoring interfaces require Linux procfs; unsupported or
denied monitoring of a running child fails closed. See the [kernel procfs contract](https://www.kernel.org/doc/html/latest/filesystems/proc.html).

A real exited-but-unreaped child can have a root-owned `/proc/<pid>/fd` entry
and deny a nonroot parent with errno13. ResourceMonitor reports the unavailable
measurement without substituting zeros. The coordinator requires completion
corroborated by PreviewChild's owned wait, within one existing sampling interval;
otherwise the request fails and the child is killed/reaped. This is a bounded
lifecycle handoff, not a procfs retry. Successful results also require a final
named-scratch check after child close; no numeric PID is sampled after completed
exchange. Scratch removal occurs only after close finishes, then admission is
released. See [source research](plans/image-viewing/python-lifecycle-research.md)
and the [pre-implementation refactor plan](plans/image-viewing/worker-refactor-plan.md).

Enforcement is sampled: consumption may exceed a budget between samples by
25ms plus scheduler/scan latency. No fixed byte-overshoot bound or instantaneous
cgroup enforcement is claimed. Private WorkerMetrics records sampled peak RSS,
peak scratch, elapsed time including cleanup, and sample count, including on
failed calls. Metrics contain no source identifiers and are excluded from MCP
responses. Later large-map acceptance measures actual rendering; this task's
small native probe measured24,231,936bytes RSS,0 scratch,0.034s on the host.

Overflow/resource/deadline/cancellation kills the exact child, cancels the
single output reader, discards remaining pipe buffers in4KiB chunks, reaps,
removes scratch and releases admission. Spawn and reap retain ownership through
repeated cancellation. The paused-stdout regression proved that waiting before
draining can deadlock even after SIGKILL; the unchanged regression passes after
the cleanup-order correction. Stderr stays discarded. See Python's
[subprocess PIPE/wait contract](https://docs.python.org/3.12/library/asyncio-subprocess.html).

`python -m foundry_mcp_server.image_preview_process --smoke` runs a real
supervised16x12 PNG probe and prints only UID, technical metadata and aggregate
metrics. The Dockerfile runs it after switching toUID10001. No public tool is
registered by either worker module.

## Verification

`test_image_preview_probe.py` uses real decoder subprocesses for format detection,
all eight orientation dimensions, malformed/unsafe/misnamed inputs, exact128-MiB
sparse files,32,768-edge/128-million-pixel headers and known oversize. Small valid
headers deliberately retain small raster bodies to prove probe does not allocate
a huge raster merely to read/reject dimensions. These fixtures are not claimed
to be valid full images. Parent validation tests inject the supervisor boundary;
child/admission/workspace/resource tests exercise their own contracts separately.

The spawn-error regression failed because subprocess creation occurred outside
the fixed-error boundary. The unchanged test passed after catching that OSError
and returning ImageProcessingFailed without native paths. Unsuccessful
corrections0. Upload baseline13 tests passed unchanged. Final full-suite and
packaged UID10001 evidence are recorded in task05a's completion record.

`test_image_preview_worker.py` composes the components with real controlled children and
24MiB RSS/32KiB aggregate scratch budgets, two24KiB files (also held open after
unlink), timeout/cancellation, final-output rejection and bounded admission.
It proves exact kill/reap, scratch removal, unchanged originals, upload-lock
independence and successful recovery after failures. Production defaults are
asserted separately; test budgets do not change production policy.

Component suites are `test_image_preview_admission.py`,
`test_image_preview_workspace.py`, `test_image_preview_child.py`, and
`test_image_preview_resources.py`. They cover queue recovery, visible scratch
cleanup errors, real stdout floods, spawn/close cancellation, exact limit
boundaries, actual RSS, open-unlinked accounting and denied live observations.
The deterministic coordinator exit regression first failed with the existing
error policy, then passed unchanged with owned completion reconciliation.
The original real resource-exhaustion/healthy-replacement assertion remains.
