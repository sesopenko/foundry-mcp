# Display-oriented crop geometry

Task06a supplies private raster-region processing;06b adds the public encoding/
byte-budget sequence, and later tasks register MCP tools. No URL is minted here.

## Native pipeline and ownership

The allowlisted source loader reads/validates source header, dimensions and
orientation before any pixel evaluation. A RegionPipeline then uses documented
[autorot](https://www.libvips.org/API/current/method.Image.autorot.html) followed by
[extract_area](https://www.libvips.org/API/current/method.Image.extract_area.html).
Coordinates are display-oriented original pixels: zero-based x/y, positive
integer width/height, exclusive right/bottom. Boolean/float/negative/empty,
unknown-field and overflowing crops return InvalidCrop with safely known original
dimensions. No clipping or padding. Missing crop selects the full original.

Source access is random, allowing rotation/mirroring and repeated independent
resampling candidates. Header-only probes remain lazy: actual raster evaluation
starts on pixel access, and native temporary conversion uses the configured
16MiB disc threshold and private scratch. See [file-opening strategies](https://www.libvips.org/API/current/how-it-opens-files.html).
The regression proved sequential access cannot rewind a PNG after the first
evaluation; the unchanged repeated-resampling test passes with random access.

Geometry has its own module, separate from child/admission/resource components.
The worker's private region operation writes only fixed region.png, mode0600,
inside its owned scratch. The supervisor's trusted synchronous collect hook runs
after child close and final scratch validation, before workspace deletion.
The operation adapter validates typed geometry, containment, pixel budgets,
original byte count, PNG header/dimensions and bounded file length; symlink
artifacts are rejected. No parent raster decode. Private RegionPixels excludes
bytes from repr and is not an MCP response. Cancellation/error deletes scratch
without deleting the source snapshot owned by the caller.

The lossless private intermediate has a separate bound of4*2,359,296+65,536 bytes
(8bit RGBA plus PNG overhead), not a public2MiB delivery promise.06b will enforce
the actual public format/byte budget before any tool can issue a URL.

## Sizing, color and alpha

The continuous aspect scale is
`min(1,2048/max(w,h),sqrt(2359296/(w*h)))`. Integral axes are floors, at least1.
Implementation uses mathematically equivalent integer division/isqrt to avoid
floating underflow at exact1536² boundaries. Native-size regions are never
resampled or enlarged. Both integer axes are derived from the same scale;
native resize ratios account only for that integer quantization. Examples:

| Region | Output |
| --- | --- |
|10000x10000 |1536x1536 |
|10000x5000 |2048x1024 |
|32768x1 |2048x1 |
|2500x2000 |1717x1373 |
|19x11 |19x11 |

Shrinking uses [resize](https://www.libvips.org/API/current/method.Image.resize.html)
with Lanczos3 and native centre convention. Alpha is
[premultiplied](https://www.libvips.org/API/current/method.Image.premultiply.html)
before filtering and [unpremultiplied](https://www.libvips.org/API/current/method.Image.unpremultiply.html)
afterward, with explicit255 alpha range and8bit output. Native-size RGBA pixels,
including transparent RGB values, remain untouched by resampling. Every retry
starts from the selected original pipeline rather than a previous candidate.

Embedded profiles use [icc_transform](https://www.libvips.org/API/current/method.Image.icc_transform.html)
to built-in sRGB/8bit; otherwise the image's declared interpretation uses
[colourspace](https://www.libvips.org/API/current/method.Image.colourspace.html)
to sRGB. Real tests cover grayscale,16bit grayscale and embedded sRGB. All native
operations are supervised by the existing1GiB RSS/2GiB scratch/90s budgets.
Documentation reports libvips8.18; pinned8.18.7 source/actual signatures were
checked, including resize vscale/kernel/gap behavior. No future-version promise.

## Preview coordinate recovery

For preview selection `[u0,u1)` in an output of width `pw` covering original
region `r`, recover left `r.x+floor(u0*r.width/pw)` and exclusive right
`r.x+ceil(u1*r.width/pw)`. Apply the same rule to Y. The result remains in
original coordinates even when selecting inside a prior crop.

For example, a640x480 preview of original region(7200,3100,1280,960), selected
at(10,20,100,80), maps to(7220,3140,200,160). Use returned delivered dimensions,
not a presumed scale or Scene dimensions. These are image pixels, not map-note
canvas coordinates; map transforms belong to M03b.

## Verification and demonstrated corrections

Real supervised native tests compare against independent Pillow pixels for
RGB/RGBA whole/border/onepixel/native crops and all8 EXIF orientations. Real
large-enough-to-shrink fixtures prove dimensions, uniform-color retention,
transparent-edge color without hidden-RGB bleed, and repeated original-region
evaluation. Pure coordinate tests cover both large-map shapes and rounding.
Malformed worker geometry, mismatched PNG dimensions/signatures, symlink outputs,
collector failure and worker cancellation prove private-artifact boundaries.
The100-million-pixel measurement remains12b's separate task.

Two defects had failing tests before correction and identical tests passed:
floating underflow at exact1536², corrected with equivalent exact arithmetic;
and native sequential reread, corrected with random access. Unsuccessful
corrections0 each. A fixture import-path error was independently identified and
corrected in test setup, not production. Tests use Pillow13's documented
get_flattened_data rather than deprecated getdata.
