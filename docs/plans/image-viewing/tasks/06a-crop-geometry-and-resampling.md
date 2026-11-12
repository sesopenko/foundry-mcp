# 06a — Crop geometry and resampling

Points: **5** — exact orientation-aware geometry and aspect/alpha-safe reduction.
Split from original task 06, estimated at 13 points.

Dependencies: [05b](05b-worker-resource-supervision.md).
Intended commit: `feat(images): extract and resample display-oriented map regions`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the complete crop/encoding design and the upstream libvips extraction,
resize, orientation, color, and alpha contracts for the installed version.
Consume 05b's supervised worker interface and task 01's crop model.

## Implementation and interfaces

- Add worker rendering of the full display-oriented image or exact selected
  source rectangle. Use zero-based integer x/y, exclusive right/bottom, positive
  width/height, and full containment. Reject booleans, floats, negatives, empty
  or overflowing rectangles as `InvalidCrop`, returning valid original dimensions
  when known. Never clip or pad invalid requests. Orient before extracting, or
  prove equivalent raw-coordinate mapping for all eight EXIF orientations.
- Return a private worker region pipeline with original dimensions, original-pixel
  `region`, and selected integral output dimensions. Use lossless temporary test
  outputs for pixel verification; no public URL/artifact contract is exposed yet.
  Full image means region `(0,0,source_width,source_height)`.
- Scale the selected region by
  `min(1, 2048/max(w,h), sqrt(2359296/(w*h)))`. Choose positive integral output
  dimensions that remain within 2,048 per edge and 2,359,296 total pixels while
  preserving aspect ratio to integer rounding. Skip enlargement and native-size
  resampling. Shrink with Lanczos3; premultiply alpha before filtering and undo
  it afterward; convert to sRGB where appropriate.
- Keep a repeatable reference to the original selected region so
  [06b](06b-preview-encoding-and-byte-budget.md) can encode and retry reductions
  without resampling a previous candidate. Encoding, metadata removal, and the
  2-MiB byte budget belong to 06b, which must pass before public tool issuance.
- Document preview-to-source mapping: left/top use
  `region.x + floor(u * region.width / preview.width)` and the Y equivalent;
  right/bottom use `ceil` for exclusive edges. This also applies to nested crops.

## Tests and acceptance

Add `tests/test_image_preview_geometry.py`. Independently generate small pixel
fixtures; do not calculate expected crops through production crop helpers.
Check exact decoded pixels for lossless native crops, all eight orientations,
one-pixel/border regions, transparency edges, no enlargement, wide/square/large
region budgets, integer rounding, and source-coordinate mapping from an overview
and an earlier crop. Use lossless intermediate test outputs for exact assertions.

Test invalid rectangles, source-coordinate mapping, repeatable resampling from
the original region, and cleanup under worker cancellation. Byte-encoding
fallback tests belong to 06b; geometry must pass independently here.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_geometry.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_worker.py' -v
./scripts/test.sh
```

Accept when geometry, orientation, dimension/area limits, and independent pixels
pass. Commit region processing, tests, and coordinate/resampling documentation.
Task 12b adds the full 100-million-pixel test; this task must already prove its
own geometry on smaller diagnostic images.

## Completion record

- Implementation: complete; native RegionPipeline owns display orientation,
  exact crop, alpha/color conversion and reusable Lanczos3 candidates. Private
  worker/typed collector expose lossless intermediates only; no public tool/URL.
- Dependency commit SHA(s):05b `cc7ba71`.
- Commit: this commit.
- Focused checks outside sandbox: geometry11,worker8,probe9 passed. Full
  `./scripts/test.sh`:782 Python (1 existing skip),749 JavaScript passed.
- Independent decoded pixels pass RGB/RGBA native/border/onepixel crops and all8
  orientations. Real wide/square/thin resizes fit edge/area budgets, preserve
  uniform colors and avoid transparent-RGB bleed. Grayscale16/embedded sRGB,
  repeated original-region resampling, invalid crops with dimensions, malformed
  parent replies and cancellation/collector cleanup pass.
- Exact10000² dimension test failed1535² before equivalent integer arithmetic
  corrected floating underflow; unchanged test passed. Native repeat test failed
  with out-of-order sequential read, then passed unchanged with lazy random
  access. Exact compressed/header-limit probe regressions still pass, proving
  header probing does not decode claimed large raster bodies. Corrections0
  unsuccessful; fixture import setup was separately diagnosed/corrected.
- [Geometry contracts/API evidence](../crop-geometry.md). Encoding/2MiB public
  budget06b, additional formats07a/07b, full100MP/resource measurements12b and
  complete shipped-image acceptance13 remain separate work. No external
  prerequisite blocks this task; no game assets/documents were modified.
