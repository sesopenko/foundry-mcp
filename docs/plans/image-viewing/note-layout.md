# Bounded note layout and annotated encoding

M04b composes the [fixed glyphs](note-glyphs.md) at delivered resolution, using
only M03b's generated-key/source-position triples. It creates no public tool;
M05 supplies map context, authorization/revision checks and bounded legend
follow-ups. Denied scope is distinct from the private render completeness here.

## Boundaries and deterministic policy

- `map_note_layout` is pure geometry: at most100 distinct numeric aliases,
  original display-oriented positions, exact crop, final dimensions and measured
  glyph sizes. It sorts by numeric ordinal, projects by floor, and tries
  NE/NW/SE/SW/E/W/N/S in that order.
- A radius2 pin has five-pixel extents. Four blank output pixels separate those
  extents from the outlined key in the corresponding direction. A leader always
  connects the pin to the nearest point on the label box. Right/bottom bounds
  are exclusive. Every candidate's conservative rectangular footprint includes
  its outlined glyph, pin and leader. Footprints must fit and be disjoint.
- The sum of outlined label-box areas satisfies `20 * area <= width * height`.
  Footprint collision checks are conservative; they can omit keys even when a
  more elaborate layout might find room. Keys are never shrunk, wrapped or cut.
- `map_note_composition` builds a transparent overlay with dark1px leaders,
  dark radius2/white radius1 pins and white outlined glyphs. No opaque label
  boxes or journal text are painted. Source images remain unchanged.
- The encoder's optional trusted `compose` callback receives the unannotated
  original-region resampling for **each** PNG/WebP90/WebP82 attempt. Reductions
  remain15% from the original region; no annotated candidate is downsampled.
  The successful attempt's metadata accompanies its verified bytes.
- `map_note_render` owns strict private worker request/reply validation and the
  after-reaping/before-cleanup artifact collector. No source paths, UUIDs, raw
  journals or capability URLs appear in its returned metadata or repr.

Private render summary fields: `total_in_region`, `rendered_count`,
`omitted_count`, `complete`, numeric-ordered `keys`, and `omission_reasons`.
Every omitted pin is counted exactly once: `limit` (beyond supplied bounded
candidates), `tiny_image` (fixed glyph cannot fit), `density` (5% ceiling),
`edge` (no complete footprint fits), or `collision` (bounded footprints collide).
Zero pins returns explicit zero counts and complete=true. Render completeness
does not establish exhaustive permissions or a complete legend.

The worker shares one1GiB-RSS/2GiB-scratch/90s operation, one admitted render and
existing8KiB request/4KiB stdout bounds. The output retains2048-edge/2359296-area/
2MiB limits. The private parent checks source length, exact crop, candidate key
membership, totals/limit accounting and final container/MIME/dimensions/bytes.
New request validation rejects nonfinite positions before JSON serialization.

Native operations use official libvips8.18
[one-pixel lines](https://www.libvips.org/API/current/method.Image.draw_line.html),
[filled circles](https://www.libvips.org/API/current/method.Image.draw_circle.html)
and [source-over composition](https://www.libvips.org/API/current/method.Image.composite2.html).
No native operation receives arbitrary markup or fonts.

## Verification and visual review

Focused layout15, glyph12 and existing encoding15 tests pass. Initial full
`./scripts/test.sh > /tmp/foundry-map-m04b-tests.log 2>&1` passes988 Python
(1 existing skip)/794 JavaScript, before the final forged-reply/audit cases.
The final commit hook covers those cases too. A production-image build passes
all native/supervised/glyph smokes; final packaged layout15 passes6.877s asUID10001
without network, with read-only application and only a read-only tests mount.

Tests independently predict crop positions, all eight placement coordinates,
outline/leader extents, exclusive edges and exact5% accounting. They verify
disjoint footprints, numeric ordering, long-key font bounds, zero/one-pixel
cases, collision/density/limit omissions, changed pixels on dark/light/alpha
maps, immutable sources and deterministic renders. Per-format policy tests
prove recomposition receives original resamples and returns only the accepted
attempt's metadata. Actual1536² alpha-noise bytes require reduction; an
independent final-coordinate glyph-alpha mask confirms the14px key was
recomposed intact. Forged keys/counts/regions and truncated bytes are rejected.
Actual cancellation after child spawn, RSS/scratch rejection and timeout leave
no child or owned scratch. A timeout test setup originally used a supervisor
limit overridden by the operation's explicit default; the corrected setup
passes the intended injected limit, retaining the same rejection assertion.

One production defect was reproduced first: a nonfinite pin escaped as raw
JSON ValueError. Validation before serialization now returns fixed
InvalidOperation; the unchanged focused test passes. No failed correction or
relaxed resource/artifact assertion.

The bounded, unit-tested synthetic visual harness performs three renders in
120s, without Foundry data:

```bash
.venv/bin/python -m foundry_mcp_server.map_note_layout_audit --output /tmp/foundry-m04b-visual
```

It refuses existing output files. Agent inspected all three generated PNGs:

| Case | Output | Bytes | Rendered/total | Sampled RSS | Scratch | Seconds |
| --- | --- | --- | --- | --- | --- | --- |
| Overview |1717×1373|97754|20/20|86974464|98304|0.25989|
| Detail |800×800|9101|4/4|61759488|12288|0.11748|
| Dense |800×800|6741|1/100|58494976|8192|0.25465|

Keys are legible on alternating light/dark rooms at overview and detail; each
short leader retains the pin's location. Detail retains N1/N2/N6/N7. The dense
case honestly reports99 collision omissions rather than overpainting a stack.
Labels can cover a few pixels of nearby map symbols; the5% ceiling does not
prove feature preservation. A tighter crop is the recovery for omitted keys.
These are synthetic obstruction observations, not target-ChatGPT acceptance or
proof on every map. Runtime/package/map workflow gates remain13/M05/M06/14b.
No live game fixtures, assets, public URLs or extra Foundry instances were used.
