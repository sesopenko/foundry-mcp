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

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, resource peaks/cadence/tolerance: not run.
- Exact pending packaged/runtime prerequisites: pending.
