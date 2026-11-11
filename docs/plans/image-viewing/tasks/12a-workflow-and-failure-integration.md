# 12a — Workflow and failure integration

Points: **8** — actual MCP/HTTP/browser boundaries and deterministic fault workflows.
Split from original task 12, estimated at 13 points.

Dependencies: [11](11-image-url-mcp-tool.md).
Intended commit: `test(images): verify complete preview workflows and fault isolation`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read all source-design acceptance checkboxes, task 01 baseline evidence, the
actual journal continuation contract, and the [budgeted evaluation process](../../../mcp-tool-evaluation.md).
Earlier tasks must already have their own passing unit tests and commits.

## Implementation and interfaces

- Add a deterministic cross-layer fixture harness using actual MCP discovery/
  invocation, the production HTTP app/store, real decoder subprocess, and
  browser-handler tests. Mock only external runtime/transport dependencies where
  necessary; do not call only Python/JS helpers and label it MCP acceptance.
- Exercise stored text-page HTML containing an `<img>` tag, including a tag
  split across `read_journal_page` fragments. Reconstruct content by following
  actual returned `next_cursor` values. From a fresh caller, issue an image URL
  directly from raw src and from an exact `browse_journal_images` image selector.
- Use small diagnostic images with independent expected pixels for workflow
  correctness, borders, one-pixel crops, transparency, mirrored/rotated regions,
  and invalid rectangles. [12b](12b-large-map-and-payload-measurements.md) owns
  full-size map generation, resource measurements, and final payload comparison.
- Route real multichunk bytes and request multiple crops after one transfer.
  Exercise ownership changes, file replacement after info, source expiry,
  cross-principal access, missing/short/out-of-order chunks, cancellation,
  reconnection, worker/resource failure, and cleanup. Demonstrate capability
  uniqueness, region immutability, and quota rejection without breaking old links.
- Bound the workflow harness to 40 MCP calls/10 minutes and expose aggregate
  actual-call/completion metrics for reuse in 12b. Keep bulk fixtures private;
  no fresh-agent benchmark is required.

## Tests and acceptance

Add `tests/test_image_preview_workflows.py` and corresponding JS workflow tests
where dispatch/handler behavior is involved. New tests must catch cross-layer
mistakes such as swapped dimensions, incorrect snapshot reuse, premature HTML
extraction, public-field leakage, or tools missing from real discovery.
Keep deterministic workflow/fault assertions in the normal suite. Large-file
and measurement-specific assertions belong to 12b's separate checkpoint.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_workflows.py' -v
node --test tests/js/image-preview-sources.test.js tests/js/image-preview-transfer.test.js
./scripts/test.sh
```

Accept when actual boundary tests and independent small-image pixel oracles
pass. Commit integration tests, reusable fixture/transport harness, and concise
fault/workflow evidence; never commit generated bulk maps or real URLs.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and bounded workflow command/result: not run.
- Workflow calls/completion, private fixture cleanup: pending.
- Runtime gaps and exact prerequisites: pending.
