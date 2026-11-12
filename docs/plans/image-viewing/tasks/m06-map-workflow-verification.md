# M06 — Complete map workflow verification

Points: **8** — independent workflow/pixel/legend evidence and bounded live acceptance.
Dependencies: [14a](14a-local-runtime-acceptance.md).
Intended commit: `test(maps): verify folder-to-annotated-crop workflows and budgets`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
M05 and the font-aware final package are ancestors through task 13. Reuse 14a's
safe fixtures, cleanup/redaction, and existing development browser/world.

## Implementation and interfaces

- Extend the existing verification harness with a map workflow, not a second
  ad-hoc service. First add unit tests for bounded calls/time, next-call following,
  revision-aware legends, pixel/alias assertions, cleanup and truthful statuses.
  Cap map evaluation at 60 MCP calls/15 minutes, and stop when criteria pass.
- In actual discovery/calls, browse root → adventure/chapter folder → selected
  map, read all relevant level/file/grid pages, select the exact map asset, get
  original metadata, issue an overview and annotated crop, then paginate the
  returned rendered-key legend. Verify UUID/ancestry, source file, coordinates,
  aliases and journal/page targets against independent fixture expectations.
- Cover duplicate names/images under different folders, manual sorting,
  non-PF2e mocks, inactive Scenes, multiple levels, complete grid fields, missing/
  video/foreground/Tile assets, unknown membership/transform rejection, denial,
  metadata changes during pagination, changed notes between info/issuance, one
  transfer/multiple crops, stale legends, dense/edge/tiny-image omissions, and
  byte-reduction recomposition. Include a large-map annotated case using 12b's
  generator and resource metrics; do not silently raise worker/output budgets.
- Compare overview/detail artifacts on dark/light features and record measured
  glyph sizes, label-box coverage, rendered/omitted counts and visual obstruction
  assessment. Use permitted marked fixtures after offline tests; never alter
  existing adventure assets or their journals/notes to manufacture evidence.
- Report M01 baseline/final discovery/input/output schema sizes and full map,
  asset/Tile, and legend-pagination call/byte/completion workflows. Keep bulk
  assets, signed refs, capabilities, and hidden expected answers private. HTTP
  exact/query behavior remains task 14a evidence unless dependencies changed.
- Prepare the new map-selection/key-following target-client scenario for 14b,
  preserving its separate hidden-pixel-answer test. Annotated key/legend data
  must not reveal that separate answer. Public client/HTTPS gaps remain pending
  with exact prompts/prerequisites; mocks do not establish visual acceptance.

## Tests and acceptance

Add `tests/test_map_workflows.py` and `tests/js/map-workflows.test.js`, plus
focused existing harness tests. Use real worker bytes and actual MCP/app
boundaries where available, independent geometry/pixel/identity oracles, and
mock only missing external dependencies. Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_map_workflows.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_live_check.py' -v
node --test tests/js/map-workflows.test.js
./scripts/test.sh
```

Then run the bounded map mode against the existing local test world when ready.
Accept when offline workflows pass and available live/package evidence is
recorded accurately. Commit tests, harness extension, aggregate evidence, exact
gaps and refreshed task statuses. Pass this evidence to 14b for final handoff.

## Completion record

- Implementation: complete; [workflow/pixel/payload evidence](../map-workflows.md).
- Dependency commit SHA(s):14a `2d24dd6`.
- Commit: this commit.
- Focused map-workflow10/13.749s, original map-image17/26.881s, helper12/1.340s,
  JS map33 plus new workflow1 and archive5/1.294s passed outside sandbox.
  Final full1043 Python (1 existing skip)/795JS passed148.561s after the proven
  module-manifest correction; same failing ZIP test passes unchanged.
- Native `scripts/image-preview-live-check.py --map`:35 MCP calls under60/900s,
  all18 folders/50 maps/16 duplicate names, selected levels/3Tiles, complete
  25-key overview and2-key detail, four legend pages/27 identities independently
  matched. Actual wall time not separately captured. Catalog47/323516B.
- Large `scripts/map-preview-measurements.py` passes actual10000-square annotated
  overview/native-detail independent pixels and unchanged1GiB/2GiB/90s budgets;
  sampled peakRSS394256384B/scratch301494272B/.505164s. Native overview1335x1767
  WebP633428B/detail800x600 PNG508560B; ink14px and box coverage.427903%/.160417%.
- Agent inspected both private derivatives, then exact cleanup removed2 review
  files/marker; no game documents/assets created or changed. Private settings
  restored, TLS/store removed; browser refresh readyGM14.369/test/console0.
- Non-PF2e mocks and unrestricted packaged core-tool manifest pass; existing
  PF2e Actor/Item guards remain intact. No other-system world provisioned.
  Public HTTPS/actual target ChatGPT hidden-pixel and key-followup acceptance
  remain14b; configured S3/CORS, prefixed deployment and real OAuth login/refresh
  retain explicit external prerequisites. Local image inspection is separate.
