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

- Implementation: complete; [guarded subset, limits and evidence](../safe-svg.md).
- Dependency commit SHA:07a `02d0d8f`.
- Commit: this commit.
- Focused commands above: SVG13,raster11,uploads13 passed outside sandbox.
  Final `./scripts/test.sh`:821 Python (1 existing skip),749 JavaScript passed.
- `docker build --pull=false -t foundry-mcp-image-preview-check:local .` passed
  native/supervised UID10001 smokes. Final
  `docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m --user 10001:10001 --volume /home/sean/src/github.com/sesopenko/foundry-mcp/tests:/checks:ro --entrypoint python foundry-mcp-image-preview-check:local -m unittest discover -s /checks -p test_image_preview_svg.py -v`
  passed13/3.755s. No source override, game volume or publication.
- Native runtime libvips8.18.7/pyvips3.2.0; pinned upstream binary build manifest
  specifies librsvg2.63.2/Cairo1.18.6. Hidden rsvg version symbols are not presented
  as independently measured; actual shipped rendering/rejection is tested.
- Physical/viewBox/pixel sizing, local gradient/use, alpha/native crops,
  malformed/unsafe/escaped/namespaced inputs, parser/expansion bounds and
  deadline cleanup pass. Positively tested HTTP listener sees no external
  requests; positively tested private-file inotify watch sees no native opens.
- dpi global enlargement, safely known large error dimensions and named-colour
  false-positive regressions each failed before correction, then passed unchanged.
  No active defect, unavailable local safety check or failed correction attempt.
  Other SVG constructs/platforms are explicit unsupported/unverified scope.
