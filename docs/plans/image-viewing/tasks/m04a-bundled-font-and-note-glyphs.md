# M04a — Bundled font and note glyphs

Points: **5** — deterministic worker typography, safe glyphs, and packaged fonts.
Split from the 13-point note-rendering/layout addition; M04b owns placement.
Dependencies: [06b](06b-preview-encoding-and-byte-budget.md).
Intended commit: `feat(images): render deterministic compact map-note glyphs`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
Read installed-version libvips text/alpha/compositing docs, font licensing and
the renderer's resource isolation. Pango font points/DPI are not assumed pixels.

## Implementation and interfaces

- Add a worker-only glyph rasterizer for generated keys N1/N2/..., with a fixed
  packaged redistributable sans-serif font (DejaVu Sans), explicit fontfile and
  controlled DPI. Render at 16-pixel final-output scale with white fill/1-pixel
  dark outline, capping ink height including outline at 20 pixels. Measure real
  glyph extents; do not rely on browser sans-serif metrics from research.
- Treat keys as generated ASCII, with strict key validation. No raw UUIDs,
  journal body text, arbitrary fonts/paths, external resources or untrusted
  Pango markup enters rendering. Return bounded RGBA glyph masks and measured
  boxes privately to M04b; do not implement collision/layout here.
- Package fonts/Pango text support in the existing production image, record
  licensing/version requirements and test as UID 10001. Keep all font work
  within preview worker RSS/scratch/time/thread/cache bounds and independent of
  upload decoding. Pin any added Python dependency without unrelated upgrades.

## Tests and acceptance

Add `tests/test_map_note_glyphs.py`: native glyph metrics and anti-alias/outline
alpha, deterministic repeated results, key widths, invalid/malicious keys,
font-file absence, bounded dimensions/output, worker limits and cleanup. Verify
real glyph generation in the service-user production image, not just a host font.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_map_note_glyphs.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_worker.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_uploads.py' -v
./scripts/test.sh
```

Accept when glyph size is measured in delivered pixels and packaged output is
repeatable without host fonts. Commit rasterizer, font packaging/licenses,
focused tests, and typography metrics together.

## Completion record

- Implementation: complete; [typography contract and evidence](../note-glyphs.md).
- Dependency commit SHA(s): 06b `4740720`.
- Commit: this commit.
- Focused glyph12, worker8, upload13 and baseline encoding15 pass. Full
  `./scripts/test.sh > /tmp/foundry-map-m04a-tests.log 2>&1` passes975 Python
  (1 existing skip)/794 JavaScript. Commit hook verifies final staged revision.
- Bundled unmodified DejaVu Sans2.37, Debian2.37-8 binary with fixed SHA256 and
  Bitstream/Arev notices. Isolated Fontconfig excludes host/user font discovery;
  missing/corrupt/symlink font fails before Pango instead of native fallback.
- Actual12pt/96DPI (16px em) outlined boxes: N1=22×14,N12=32×14,N100=43×14,
  maximum-length sample163×14. No shrink/clipping, no arbitrary text or markup.
  Independent scalar outline/alpha oracle and real antialias/contrast pass.
- Docker build plus12 packaged tests pass asUID10001 (0.960s). Standalone
  read-only/no-network smoke matches host2374B PNG SHA256 exactly, sampled
  RSS37384192B/scratch4096B/0.13532s. Runtime has no/usr/share/fonts and mounts
  no host fonts. Tests-only read-only mount; no app override/game data/fixtures.
- No local prerequisite or cleanup remains. Placement/retry composition and
  actual annotated map workflows retain M04b/M05/M06 and external14b gates.
