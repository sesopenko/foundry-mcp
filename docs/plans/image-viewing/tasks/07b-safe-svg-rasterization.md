# 07b — Safe SVG rasterization

Points: **8** — SVG admission/security, sizing, and verified resource isolation.
Split from original task 07, estimated at 13 points.

Dependencies: [07a](07a-raster-codecs-and-frame-policy.md).
Intended commit: `feat(images): rasterize bounded self-contained SVG sources safely`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read official libvips/librsvg security/resource documentation for shipped
versions. Observed rendering alone does not prove external resources are blocked.

## Implementation and interfaces

- Admit common self-contained Foundry SVG icons through a bounded non-interactive
  loader, such as libvips/librsvg, only after validation against an explicit
  safe SVG subset. Enable the loader only through this guarded boundary.
- Use 96 CSS pixels per inch, derive dimensions from viewBox where needed,
  and permit local fragment references. Preserve original/delivered/worker
  budgets, frame-policy consistency, crop coordinates, and raster-only output.
- Reject DTD/entities, scripts, event handlers, foreign content, external hrefs,
  CSS imports/external URLs, file access, and unsupported constructs; cover
  namespace/escaped variants. Do not rely on incidental lack of network access
  as the safety mechanism. If safety cannot be established, reject the construct.
- Keep limits active in parsing and rendering. Return `UnsupportedImage` for
  unsupported/malformed content and `ImageTooLarge` with safely known dimensions
  for excess sizes. No source SVG, external references, or native diagnostics
  may enter tool output/logs. Package librsvg dependencies in the image now.

## Tests and acceptance

Add `tests/test_image_preview_svg.py`. Test a real core-style icon, explicit,
viewBox, physical-unit and missing-size cases, local fragments, transparency,
crops, every forbidden construct including escaped/namespaced variants, extreme
sizes, and worker limits. Prove external reads are blocked with private sentinel
file and local resource-listener fixtures; keep contents out of diagnostics.
Run the SVG suite inside the production image as UID 10001, including rejection
cases, and record loader versions. Maintain 07a's raster codec regressions.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_svg.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_formats.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_uploads.py' -v
./scripts/test.sh
```

Accept only verified guarded SVG support and negative external-access evidence.
Commit loader admission, package updates, tests, and exact SVG limitations.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and packaged SVG safety cases: not run.
- Loader versions and exact pending prerequisites: pending.
