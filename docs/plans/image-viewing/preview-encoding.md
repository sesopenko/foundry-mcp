# Bounded preview artifacts

Task06b implements private PNG/WebP artifacts after the selected original region
pipeline. No MCP tool, capability URL or public route is registered by this task.

## Candidate policy

Start at06a's integral aspect-preserving dimensions, capped at2048 per edge and
2,359,296 total pixels, without enlargement. Try these in order at each size:

1. Lossless PNG, compression6/all row filters, no palette quantization.
2. WebP quality90, effort4, alpha quality100, exact transparent-pixel option.
3. WebP quality82 with the same alpha/effort settings.

Stop at the first valid file of at most2,097,152 bytes. Otherwise floor both
current target axes to85%, at least1, and restart the format choices. Each size
resamples06a's original selected region, not an earlier output. A1x1 candidate
that cannot fit fails explicitly; the loop always makes dimensional progress.
The90-second isolated-worker deadline covers all candidates and verification.
An internal monotonic check also brackets policy stages. No budget, encoder or
clock override is accepted through private RPC inputs or MCP requests.

The [PNG](https://www.libvips.org/API/current/method.Image.pngsave.html) and
[WebP](https://www.libvips.org/API/current/method.Image.webpsave.html) operations
are explicit allowlisted native encoders on pinned libvips8.18.7. strip removes
source metadata, including EXIF/GPS/thumbnails, ICC/XMP and comments. Pixels are
already converted to sRGB by06a. Resolution is reset to a generated96DPI rather
than copied from source metadata. Existing geometry/alpha rules remain intact.

## Verification and ownership

Native encode policy lives separately from geometry and lifecycle. Each
candidate uses fixed candidate.bin, mode0600, in owned scratch. Oversized files
are removed before another attempt; encoder failures/empty files are errors,
not alternative-format retries. Only a verified complete candidate is renamed
to fixed preview.bin. All files remain private and are removed on failure,
deadline or cancellation by the existing component lifecycle.

For an accepted candidate the worker reopens through the allowlisted loader,
checks actual MIME/dimensions, forces full pixel evaluation, and validates
container structure and byte length. The parent repeats strict typed metadata,
containment/source-byte-count and bounded container checks before returning
RenderedPreview. Parent validation never decompresses image pixels. Neither
private filenames nor original source paths appear in the returned metadata;
artifact bytes are excluded from debug repr and are never MCP output here.

PNG validation checks signature, bounded chunks/CRC,8bit RGB/RGBA IHDR,
IDAT/IEND and optional generated resolution. Metadata/animation chunks are
rejected. WebP validation checks RIFF length/padding, still VP8/VP8L and optional
VP8X/alpha dimensions, and rejects metadata/animation. Source specifications:
[WebP container](https://developers.google.com/speed/webp/docs/riff_container),
[lossless header](https://developers.google.com/speed/webp/docs/webp_lossless_bitstream_specification).
These are container checks alongside, not a substitute for, worker pixel decoding.

## Evidence

Controlled encoders prove exact ordering, both quality choices, stop-at-first,
two15% reductions, original-region reuse, deadline/progress bounds and partial
cleanup. Real supervised workers independently decoded with Pillow prove PNG
lossless equality, high-entropy WebP, random-alpha reductions, metadata removal,
lossy mean absolute error<7 and alpha mean error<2. Forged MIME/dimensions/size
and truncated files are rejected by the parent. Live game content is not used.

Measured synthetic fixtures on the current pinned decoder:

| Case | Delivered format | Dimensions | Encoded bytes |
| --- | --- | --- | --- |
| Native RGBA detail |PNG |22x18 |127 |
| High-entropy grayscale/RGB |WebP |1536x1536 |1,664,334 |
| Random RGBA, reduced from1536² |WebP |1109x1109 |1,968,390 |
| Metadata-bearing RGB |PNG |19x11 |107 |

Empty output initially triggered fallback instead of failing; a focused test
failed, then passed unchanged after rejecting zero-byte candidates. A corrupt
generated file was initially reported as UnsupportedImage; its regression failed
then passed unchanged after generated-artifact verification mapped the failure
to ImageProcessingFailed. Unsuccessful corrections0 for both. No source failure
was hidden or public byte budget increased. Full suite evidence is in task06b.

Additional input codecs/SVG, persistent storage, actual MCP tools, full100MP
measurements and final service-user packaging remain their later task gates.
