# 05b — Worker resource supervision

Points: **8** — independent RSS/scratch/deadline enforcement and process cleanup.
Split from original task 05, estimated at 13 points.

Dependencies: [05a](05a-decoder-probe-and-packaging.md).
Intended commit: `feat(images): enforce isolated preview worker resource budgets`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read 05a's worker boundary, existing upload kill/reap lifecycle, and the design's
worker budget table. Do not change the independent Pillow upload policy.

## Implementation and interfaces

The user-requested [component refactor plan](../worker-refactor-plan.md) defines
the implementation boundaries and test migration; it was saved before refactoring.

- Complete the preview worker supervisor with one render admitted at a time,
  independent of upload concurrency. Use the same safe supervisor for probing
  and rendering; define bounded queue/cancellation behavior without holding
  orphan processes or file leases.
- Enforce 1 GiB resident memory, 2 GiB private scratch, and 90 seconds per render
  independently. Give each worker a private temp directory and point decoder
  temp settings there. Monitor per-worker RSS and scratch at bounded intervals;
  terminate on limits/deadline/cancellation and reap the process on every exit.
  An address-space limit or shared container limit alone does not prove RSS
  enforcement. Record monitoring cadence/tolerance and measured peaks.
- Keep bounded libvips thread/operation caches, bounded stdout, fixed-category
  errors, and secret-free stderr handling. Separate originals/scratch/public
  derivatives. Clean partial outputs/temp directories on failure; remove only
  the current operation's resources. Provide compact peak/time metrics privately
  to later measurement harnesses without exposing source data to MCP.
- Verify enforcement using controlled child processes plus a real decoder
  smoke. No tools are registered here. 06a/06b consume this supervised boundary;
  10 must depend on this task before exposing metadata probing.

## Tests and acceptance

Add `tests/test_image_preview_worker.py`. Test serial admission, queue
cancel/release, output overflow, RSS/scratch exhaustion, stalled/hung workers,
kill/reap after cancellation, temp removal, failure recovery, and isolation from
uploads. Use small injected test budgets while separately asserting production
defaults. Include real child resource failures; do not mock all enforcement.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_worker.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_probe.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_uploads.py' -v
./scripts/test.sh
```

Accept when every resource budget and cleanup path has independent evidence.
Commit supervisor, resource tests, and enforcement/measurement documentation.

## Completion record

- Implementation: complete; separate admission, workspace, child and resource
  components, coordinated by PreviewSupervisor; probe adapter and mocks migrated.
- Dependency commit SHA(s):05a `57123ce`.
- Commit: this commit.
- Focused checks outside sandbox: admission4,workspace3,child6,resources8,
  coordinator7,probe9; aggregate `test_image_preview_*.py`74 passed. Unchanged
  upload baseline13 passed. Full `./scripts/test.sh`:770 Python (1 existing skip),
  749 JavaScript passed.
- Real controlled children proved24MiB RSS/32KiB scratch limit failures,
  open-unlinked scratch accounting, timeout/cancellation/pipe-flood kill/reap,
  scratch cleanup and healthy replacement. Production stays1GiB/2GiB/90s/one
  operation with25ms sampled checks plus scheduler/scan latency,8 queued/90s.
- Deterministic real zombie test proved stateZ/root-owned procfd/errno13. The
  coordinator regression failed before correction and passed unchanged after
  requiring owned completion within one monitor interval; denied live workers
  still fail closed. No observation retry or fabricated zero sample. Final named
  scratch is checked after reap before accepting success. Historical three failed
  diagnosis attempts remain recorded; first correction after authorized refactor
  resolved this demonstrated defect.
- Production Docker build passed both UID10001 native/supervised smokes.
  Separate read-only/network-disabled run passed16x12 PNG80bytes/still with
  sampledRSS14,987,264 bytes,0 scratch,0.07453s/4samples. No Foundry instance,
  game volume, publication or existing-asset changes. No external prerequisite
  blocks05b; large-map measurements/codecs/fonts remain their later tasks.
- [Decoder contracts](../../../image-preview-decoder.md) and
  [exact CPython/kernel source research](../python-lifecycle-research.md).
