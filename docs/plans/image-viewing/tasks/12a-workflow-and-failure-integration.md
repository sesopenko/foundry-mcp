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

- Implementation: complete; [workflow boundaries and measurements](../workflow-integration.md).
- Dependency commit SHA(s):11 `f5d04c3`.
- Commit: this commit.
- Focused: workflow8 passed3.996s including canonical URL and EOF assertions.
  JS workflow/source/transfer22 and
  actual HTTP identity3 passed outside sandbox. The normal focused Python
  command above exercises the whole bounded harness; no separate live command
  or model benchmark is required for this synthetic boundary checkpoint.
- Full `./scripts/test.sh`:893 Python (1 existing skip),750 JavaScript passed,
  including the final EOF assertion. No production behavior changed.
- Measured main workflow:10 actual MCP calls,3 HTML fragments,3 original
  transfers/12 reversed private chunks,4 anonymous HTTP reads, all complete.
  The linked table records actual structured/protocol bytes without paths,
  capabilities, expected visual answers or billed-token claims.
- Cleanup: source/store private roots deleted, Node subprocesses reaped,
  pending RPCs and browser transfer/worker leases empty. Only temporary synthetic
  fixture data was used; no game asset/document/instance mutation.
- Pending scope/gates: large-map/resources/equal-content replay12b; packaged
  release verification13; live local runtime14a; configured S3/CORS and external
  public HTTPS/target-client14b. This test-only checkpoint changes no production
  API/runtime and does not claim those separate checks passed.
