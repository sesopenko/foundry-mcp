# 05a — Decoder probe and initial packaging

Points: **5** — libvips dependency packaging and bounded metadata probing.
Split from original task 05, estimated at 13 points.

Dependencies: [01](01-contracts-and-baseline.md).
Intended commit: `feat(images): add isolated libvips preview probing`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read current `foundry_mcp_server/image_worker.py`, the image-upload subprocess
wrapper, Dockerfile, locked dependencies, and the design's linked upstream
pyvips/libvips documentation. Research current official dependency/codec
documentation before selecting the exact pin; preserve unrelated lock entries.

## Implementation and interfaces

- Add a separate preview subprocess entry point and a basic async wrapper,
  reusing the existing kill/reap pattern rather than replacing upload decoding.
  Accept only private staged-file inputs and bounded structured operations;
  never download arbitrary URLs or expose paths through the public tools.
- Pin pyvips with a synchronized lockfile. Install required native libvips
  runtime support in the production image and document/provision local preview
  prerequisites through the existing dependency workflow. Start with safe raster
  probe support; 07a completes raster codecs and 07b enables safe SVG admission.
  Reject unknown/unsafe loaders rather than allowing libvips to guess freely.
- Probe actual format and headers before raster allocation where possible.
  Enforce compressed size <=128 MiB, each original edge <=32,768, and total
  pixels <=128,000,000. Return display-oriented width/height, actual MIME,
  compressed byte count, and `still`/`first_frame` policy. Validate all metadata
  again in the parent; filename/HTTP MIME is not proof of format.
- Provide a file-backed, demand-driven operation boundary for 05b and rendering.
  Limit libvips threads/caches explicitly, bound subprocess output, and kill/reap
  on cancellation/error. [05b](05b-worker-resource-supervision.md) adds complete
  RSS/scratch/concurrency enforcement before any tool exposes this worker.
- Keep original files separate from scratch and public derivatives. Worker
  results contain compact metadata/error categories only. Surface
  `ImageTooLarge` with safely known dimensions and `UnsupportedImage` for
  malformed/unsupported content. Preserve the upload worker's 32-million-pixel
  Pillow policy and existing behavior unchanged.

## Tests and acceptance

Add `tests/test_image_preview_probe.py`. Test real file probing, misleading
extensions, oversized compressed/header dimensions, exact source limits, all
eight EXIF orientation dimension outcomes, malformed input, unsupported loaders,
bounded output, basic worker failure/cancellation and kill/reap.
Use real decoder subprocesses for probe assertions. Detailed resource-monitor
tests belong to 05b; large-map measurements belong to 12b.
Build the production image and run a minimal probe as its UID 10001; this is an
MCP-image check and requires no new Foundry instance.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_probe.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_uploads.py' -v
./scripts/test.sh
```

Accept when metadata/source-limit tests pass, packaging loads libvips as the
service user, and upload regressions remain green. Keep the internal probe
unexposed until 05b's resource enforcement passes. Commit probe, dependencies,
initial image changes, tests, and metadata docs; record tested library versions.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and UID-10001 image probe: not run.
- pyvips/libvips versions, metadata results, and gaps: pending.
