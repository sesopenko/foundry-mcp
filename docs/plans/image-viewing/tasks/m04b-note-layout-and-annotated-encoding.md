# M04b — Note layout and annotated encoding

Points: **8** — collision/coverage policy coupled to crop and byte-budget retries.
Split from the 13-point note-rendering/layout addition; M04a owns glyphs/fonts.
Dependencies: [M04a](m04a-bundled-font-and-note-glyphs.md),
[M03b](m03b-map-coordinate-and-revision-binding.md).
Intended commit: `feat(images): lay out bounded readable map-note keys on previews`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
Consume verified M03b source positions, M04a measured glyphs, and 06b encoding.

## Implementation and interfaces

- Project in-region pin centers to final output pixels and place whole generated
  keys by numeric alias ordinal (N1, N2, ...). Try NE/NW/SE/SW/E/W/N/S with 4-pixel gaps, small
  pin/leader marks, and 16-pixel glyph sizing. Include stroke/leader extents in
  bounds/collision checks; no clipped/wrapped keys, opaque label boxes, or
  movement to a different location without a leader.
- Require disjoint label boxes and aggregate label-box area <=5% of delivered
  area; render at most 100 keys. Deterministically omit unplaceable/dense/edge/
  tiny-image keys with explicit reason counts. Keep labels readable rather than
  shrinking them silently. A small crop with zero placed keys remains an honest
  incomplete annotation, not a success claim for all requested notes.
- Return private annotated artifact plus rendered keys/counts/reason/status
  metadata for M05. Expose denied/unsupported note scope separately. Full raw
  identities are retrieved through M03a's bounded legend, not painted in pixels.
- Composite only after cropping/resizing. On PNG/WebP/15%-reduction retries,
  regenerate layout and glyph composition at the new final dimensions from the
  original selected region; never downsample a previously annotated candidate.
  Validate final MIME/dimensions/bytes and actual annotation metadata against
  <=2048 edges, <=2359296 pixels, <=2 MiB and the single 90-second deadline.
  Keep original sources unchanged; all partial derivatives require cleanup.

## Tests and acceptance

Add `tests/test_map_note_layout.py`: independently predicted padded map/crop
positions, known glyph masks and changed pixel bounds, all edge/corner cases,
overlapping pins, long keys, >100 notes, 5% coverage ceiling, one-pixel crops,
zero notes, dark/light/transparent maps, incomplete reasons, and deterministic
ordering. Force real byte-budget retries and verify legible recomposition at
each delivered size. Include cancellation/resource-failure cleanup.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_map_note_layout.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_map_note_glyphs.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_render.py' -v
./scripts/test.sh
```

Accept when geometry, size/coverage bounds, legibility target, truthful omission
metadata, and retry behavior pass. Inspect overview/detail annotated artifacts
to judge obstruction; numeric bounds alone do not prove visual usability.
Commit layout/composition, tests, visual examples without private assets, and
documented limitations together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, pixel/coverage/byte/resource metrics: not run.
- Visual obstruction review and exact pending prerequisites: pending.
