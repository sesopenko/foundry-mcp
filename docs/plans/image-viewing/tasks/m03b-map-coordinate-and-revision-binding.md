# M03b — Map coordinates and revision binding

Points: **8** — verified Scene-to-image mapping and context-safe snapshot reuse.
Split from the 13-point map-note extraction/mapping addition; M03a owns reading.
Dependencies: [M03a](m03a-map-note-identities-and-legend.md),
[06a](06a-crop-geometry-and-resampling.md).
Intended commit: `feat(maps): bind note geometry and revisions to map image snapshots`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
Verify SceneDimensions/Level/texture/Note public contracts with Grounded Docs.
Observed legacy serialization and internal mesh matrices are not supported APIs.

## Implementation and interfaces

- Add a private immutable map-context record: Scene UUID, level identity, asset
  role/reference, authorized caller/world/GM, metadata/note revision, alias
  snapshot, and proven source-coordinate mapping. The image service supplies
  actual original display-oriented dimensions. M05 attaches the context to its
  existing caller-bound source handles; this task defines/test-drives the record
  and revalidation helpers without changing public image-tool signatures.
- Verify a normal background map's coordinates using public `getDimensions()`:
  subtract grid-rounded scene origin, scale Scene width/height to original image
  dimensions, then use 06a's crop/output mapping. Preserve display orientation,
  shift and source/Scene size distinctions. Independently test the measured
  origin (1800,2400), note (1900,2500) → image (100,100).
- Establish an explicit public-contract-backed supported transform subset before
  production use. Baseline is unrotated, unshifted texture placement in the Scene
  rectangle; support scene padding/shift and source/Scene size scaling. Do not
  adopt undocumented texture properties merely to detect compatibility. If a
  mapping cannot be established safely through public contracts, return typed
  `UnsupportedMapMapping`; retain ordinary raw-image reading. Record precisely
  which level/texture/orientation combinations are verified. Tile composition,
  foreground annotation and arbitrary unverified transforms are outside v1.
- Pin annotation identity/aliases/revision with staged originals; recheck caller,
  permissions, exact scene/level/asset reference and relevant note/mapping
  revision before new annotation issuance. Return `MapContextChanged` with
  fresh-map-info/image-info recovery when changed. Pinned bytes at an unchanged
  path remain pinned; file-list revisions do not detect replacement contents.
- Filter notes by pin center within the exclusive source crop without changing
  keys. Request only bounded in-region candidates for M04b, retaining total/scope
  status and explicit over-limit counts. No unbounded JSON or private identity
  record may reach public responses/logs.

## Tests and acceptance

Add `tests/js/map-geometry.test.js` and `tests/test_map_context.py`. Cover padding
rounding, scene shifts, differing source sizes, crop edges/orientation, duplicate
image paths across Scenes, wrong level/role, mutation across awaits, missing/
denied/moved notes, revised aliases, expired/lost caller context, and unchanged
path with pinned replacement bytes. Use independent geometry oracles; test
supported combinations and explicit unsupported transforms, never guessed ones.

Run outside the sandbox:

```bash
node --test tests/js/map-geometry.test.js tests/js/map-notes.test.js
.venv/bin/python -m unittest discover -s tests -p 'test_map_context.py' -v
./scripts/test.sh
```

Accept when mapping support has official evidence plus focused runtime tests,
and stale/wrong context demonstrably cannot produce a misplaced annotation.
Commit mapping/revalidation helpers, tests, and support matrix together. Missing
runtime evidence remains a precise gap; it is not verified map support.

## Completion record

- Implementation: complete; [private contract/support matrix/evidence](../map-context.md).
- Dependency commit SHA(s): M03a `26bb4e6`,06a `49e8aaf`.
- Commit: this commit.
- Focused context21 pass11.904s, private geometry/notes JS17 pass. Full
  `./scripts/test.sh` passes961 Python (1 existing skip)/794 JS before two final
  context-mutation tests; required commit hook checks the final staged revision.
  Native independent pixel oracles cover all8 display orientations. Actual
  SourceSnapshots and production Node dispatch cover identity/expiry, one-transfer
  crops, replacement bytes, stale mappings/aliases and2000-byte private frames.
- Baseline2 calls: all50 Level textures match public cleaned defaults; normal,
  shifted and differently sized public Scene instances corroborate rectangles,
  with unchanged active Scene/collection and0 persisted fixtures.
- Native verifier6 calls under600s passes actual6800×9000/4405816B source probe,
  25 region candidates and one-pixel detail alias preservation. Module dispatch
  context1034B/full candidates4298B/detail1357B; these are handler-result bytes,
  not a claim of direct private live GM frame measurements. Browser readyGM
  14.369/test,console0; module ZIP packaging passes.
- Verified mapping:14.369 default whole-schema background placement, public
  rectangle padding/shift and source-size/display-axis conversion. Arbitrary
  nondefault transforms, other builds and foreground annotation explicitly fail;
  ordinary image access remains available. Public image-tool map inputs and
  source-cache attachment remain M05's integration responsibility. Live S3 and
  external target-client prerequisites retain later gates.
