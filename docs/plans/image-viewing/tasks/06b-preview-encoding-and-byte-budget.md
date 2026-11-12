# 06b — Preview encoding and byte budget

Points: **5** — bounded encoding fallback and independently verified artifacts.
Split from original task 06, estimated at 13 points.

Dependencies: [06a](06a-crop-geometry-and-resampling.md).
Intended commit: `feat(images): encode compliant PNG and WebP preview artifacts`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the encoding sequence and 06a's region/resampling pipeline. Keep all attempts
inside 05b's supervisor and the 90-second per-render deadline.

## Implementation and interfaces

- Encode lossless PNG first. If >2 MiB, try alpha-preserving WebP quality 90,
  then 82. If still oversized, reduce target dimensions by 15%, restart format
  choices, and resample from the original selected region each time. Stop at
  the first compliant encoding and guarantee progress near one-pixel sizes.
- Preserve 06a's aspect, alpha, orientation, and dimension/area budgets:
  <=2,048 pixels per edge, <=2,359,296 pixels total, no enlargement. Strip EXIF,
  GPS, comments, embedded thumbnails, and other source metadata.
- Validate actual encoded MIME, dimensions, and byte count before returning a
  complete private artifact plus original dimensions, region, and delivered
  metadata. Parent validates the worker result; partial or inconsistent files
  cannot be published. Clean artifacts on failure/cancellation and enforce the
  worker deadline across all attempts. No MCP tool is registered here.

## Tests and acceptance

Add `tests/test_image_preview_render.py` covering real PNG preference, high-entropy
WebP fallback, both quality choices, repeated reduction from the original,
progress/deadline limits, metadata removal, MIME/dimension/size verification,
lossless pixel equality, lossy tolerance, alpha, and cleanup. Combine controlled
encoder tests for exact ordering with real encoded-byte decoding assertions.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_render.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_geometry.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_worker.py' -v
./scripts/test.sh
```

Accept when every artifact fits all budgets and fallback is independently tested.
Commit encoding/validation, tests, and delivered-image metadata documentation.

## Completion record

- Implementation: complete; native encoder policy, full isolated decode
  verification, bounded parent container validation and typed private artifacts.
- Dependency commit SHA(s):06a `49e8aaf`.
- Commit: this commit.
- Focused checks outside sandbox: render15,geometry11,worker8 passed. Full
  `./scripts/test.sh`:797 Python (1 existing skip),749 JavaScript passed.
- Production image built successfully; render15 also passed as UID10001 with
  read-only filesystem/test mount, no network and128MiB temporary scratch. No
  Foundry/game volumes, publication or existing-asset changes.
- Exact ordering, both WebP qualities, first-compliant stop, repeated15%
  reductions from original, onepixel progress, deadlines, partial cleanup and
  forged metadata/container rejection pass. Real independent Pillow decoding
  passed lossless pixels, lossy mean error<7, alpha mean error<2, metadata removal.
- Synthetic artifacts: PNG22x18/127bytes; WebP1536²/1,664,334bytes;
  WebP1109²/1,968,390bytes reduced from random-alpha1536²; PNG19x11/107bytes.
  The two WebP measurements match inside the production service-user image.
- Empty-file and corrupt-generated-artifact regressions each failed before
  correction and passed unchanged after correction; unsuccessful corrections0.
  [Encoding contracts/evidence](../preview-encoding.md). More input codecs/SVG,
  complete font/package/runtime workflows and MCP issuance remain later tasks;
  no external prerequisite blocks06b and no public tools are registered here.
