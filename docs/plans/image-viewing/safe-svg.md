# Guarded static SVG previews

The preview worker admits a bounded static SVG subset, reconstructs its XML,
and passes only that reconstructed private file to the explicit libvips SVG
loader. Original assets are never changed. Metadata reports `image/svg+xml`,
`frame_policy:still`, and the original compressed byte count; output is PNG/WebP.

Supported elements are svg, g, defs, path, rect, circle, ellipse, line, polyline,
polygon, linearGradient, radialGradient, stop, clipPath, mask, use, symbol, title,
and desc. Presentation attributes and conservative inline presentation styles
support fills/strokes, opacity, gradients, clipping and masks. Local fragment
references must name an existing unique ID. The complete containment/reference
graph must be acyclic and fit the bounded expansion budget.

The guard rejects DTD/entity declarations, processing instructions, scripts,
events, external image/font/CSS resources, text rendering, style sheets,
foreignObject/foreign namespaces, animation, XML base URLs and unknown attributes
or elements. CSS escapes/comments/imports/variables are unsupported. Only exact
local `url(#id)` paint references and local href/xlink:href references are accepted.
No file, HTTP, data, signed, or other external reference reaches the decoder.
UTF8 (optional BOM) is required; UTF16/NUL input is rejected. Harmless comments
and title/description text are removed during reconstruction.

Core icons' inert `class` attributes and exact `touch-action: none` inline
declarations are removed as well; neither reaches the raster document. Style
sheets remain forbidden, presentation declarations retain the existing
validation, and other unknown or unsafe interaction values are rejected.
Task10's real anchor-icon check exposed this admission gap. Its regression
asserts unchanged crop pixels and removal of both hints before native decoding.

Limits apply during parsing:10,000,000 XML bytes (the native SVG loader's existing
10MB guard remains enabled),10,000 elements,64 nesting levels,64 attributes per
element and100,000 expanded containment/reference nodes. Numeric tokens are
bounded in length/magnitude; nonzero magnitudes below1e-12 or above1e12 are
unsupported. The ordinary128MiB compressed/32768-edge/128-million-pixel source
limits and1GiB RSS/2GiB scratch/90-second supervision remain active too.
Safe-subset limits return UnsupportedImage. Oversized source viewports return
ImageTooLarge with safely known dimensions; integer error dimensions may exceed
raster uint32 but must remain exact JSON integers (<=2^53-1). Larger derived
viewports fail without publishing inexact dimensions.

## Coordinate sizing

CSS physical units use96 pixels per inch (px, in, cm, mm, pt, pc, q). The guard
derives a missing dimension using viewBox aspect ratio; both missing dimensions
require a positive viewBox. Relative root sizes require a viewBox. Missing size
without a viewBox is unsupported. Integral raster dimensions round upward.
The reconstructed root has explicit pixel dimensions and retains its viewBox/
preserveAspectRatio. Region/crop/output limits use the same raster contract as
other formats, including native-size crops and transparent backgrounds.

libvips8.18.7 sets `total_scale = scale*dpi/72` independently of librsvg's CSS
DPI. Merely setting dpi96 produced32x21 instead of24x16 in the real fixture,
causing the required dimension assertion to fail. The explicit loader now uses
`dpi=96,scale=72/96`: physical-unit interpretation remains96DPI while cancelling
the additional global enlargement. The same unchanged pixel/physical/viewBox
tests pass, including physical-unit shape placement within the viewport.

## Evidence and versions

- [libvips8.18 SVG contract](https://www.libvips.org/API/current/ctor.Image.svgload.html):
  lazy header read, dpi/scale interaction and native10MB guard.
- [Pinned native implementation](https://github.com/libvips/libvips/blob/v8.18.7/libvips/foreign/svgload.c):
  total_scale, CSS DPI and viewport logic, fetched through GitHub MCP.
- [librsvg security guidance](https://gnome.pages.gitlab.gnome.org/librsvg/devel-docs/security.html):
  external-reference handling and native structural limits do not themselves
  establish our stricter no-external-access policy. The guard is required.
- [W3C SVG coordinates/units](https://www.w3.org/TR/SVG2/coords.html) and
  [Python XML parser callbacks](https://docs.python.org/3.12/library/xml.etree.elementtree.html):
  coordinate sizing and pre-render declaration/structure rejection.
- pyvips3.2.0/libvips8.18.7 verified at runtime. The pinned binary wheel's
  [download script](https://github.com/kleisauke/pyvips-binary/blob/v8.18.7/scripts/download-vips.py)
  selects the matching native release; its
  [build manifest](https://github.com/kleisauke/libvips-packaging/blob/v8.18.7/versions.properties)
  specifies librsvg2.63.2/Cairo1.18.6. These are upstream build identities, not
  independently exported runtime version symbols; the wheel hides rsvg symbols.

`test_image_preview_svg.py` exercises actual subprocess metadata/pixels/crops,
transparency, gradients/use, physical/viewBox sizing, forbidden constructs,
escaped/namespaced references, limits/cycles/expansion and worker cleanup. Its
HTTP listener is positively checked before proving zero external requests.
Its private-file inotify watch is positively checked before proving zero native
opens. Another test rejects before native initialization. No network absence
or Python-only file mock substitutes for these assertions.

Task07b records full/package results. The production image uses the existing
locked binary dependency; no extra Foundry instance, game volume or publication
is needed. Other platforms and SVG constructs outside this exact subset remain
unsupported/unverified rather than silently stripped into a different picture.
