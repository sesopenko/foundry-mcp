# 07a — Raster codecs and frame policy

Points: **5** — real codec fixtures, first-frame semantics, and shipped-image coverage.
Split from original task 07, estimated at 13 points.

Dependencies: [06b](06b-preview-encoding-and-byte-budget.md).
Intended commit: `feat(images): support advertised raster codecs and first frames`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read existing picker extension contracts, worker loader admission, and official
libvips documentation for shipped versions. SVG remains rejected until
[07b](07b-safe-svg-rasterization.md) completes its separate safety boundary.

## Implementation and interfaces

- Complete allowlisted JPEG, PNG/APNG, WebP, AVIF, BMP, GIF, and TIFF
  probing/rendering in the isolated worker. Package codec dependencies now;
  task 13 verifies the final deployment image rather than introducing support
  after tools already promise it. Do not enable unrelated document/network loaders.
- For multiframe/animated/multipage inputs use the first displayable frame/page,
  with correct first-frame dimensions and `frame_policy: first_frame`; still
  inputs report `still`. Do not accidentally treat a vertical frame stack as
  original dimensions. Preserve orientation/crop behavior from 05a–06b.
- Render to PNG/WebP only; never serve original animated bytes.
  Enforce the same original/delivered/worker budgets and strip source metadata.
  Map unsupported or malformed content to `UnsupportedImage`; oversized content
  to `ImageTooLarge` with only safely known dimensions. No decoder diagnostics,
  source text, or external references may leak into tool errors/logs.

## Tests and acceptance

Add `tests/test_image_preview_formats.py` with real tiny codec fixtures, including
animation/multipage cases, plus generated malformed files. Verify first-frame
pixels/policy, dimensions, MIME, alpha, and output encoding for every advertised
format. Test malformed headers, excessive dimensions, and rejected unsupported
loaders. SVG attack fixtures and external-access assertions belong to 07b.
Tests execute outside the sandbox.

Run:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_formats.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_render.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_uploads.py' -v
./scripts/test.sh
```

Run the fixture codec matrix inside the production image as UID 10001 and
record library/loader versions. Accept only verified shipped codec support and
raster frame correctness; document any exact unresolved platform gap. Commit
loader admission, codecs/image updates, fixtures/tests, and format limitations.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and packaged codec matrix: not run.
- Raster/frame evidence, tested versions, and gaps: pending.
