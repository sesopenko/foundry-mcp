# 12b — Large-map and payload measurements

Points: **8** — independent large-map oracles, measured resources, and comparable workflows.
Split from original task 12, estimated at 13 points.

Dependencies: [12a](12a-workflow-and-failure-integration.md).
Intended commit: `test(images): measure large-map fidelity resources and MCP payloads`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read task 01's baseline, 12a's fixture/transport harness, and the source design's
map and measurement acceptance. Reuse tested resource metrics from 05b.

## Implementation and interfaces

- Generate real 10,000×10,000 and 10,000×5,000 maps in private temporary storage.
  Include distinct small symbols/labels at center and far edges, opaque filenames,
  and independent expected pixels kept out of captions/tool results. Generate
  and compare without a giant parent-memory raster solely for a small region.
- Through actual MCP, verify square-map info, compliant overview, and native
  bottom-right detail against independently generated source-region pixels.
  For the wide map verify the 2,048×1,024 overview when encoding permits and
  the `(7200,3100,1280,960)` crop. Include border/one-pixel, reduced large,
  transparent, rotated/mirrored, and invalid regions. Lossless pixels compare
  exactly; state tolerances for lossy inputs. Reuse one transfer for multiple crops.
- Record peak worker RSS, scratch, and elapsed time on the 100-million-pixel
  case against 1 GiB/2 GiB/90 seconds. Keep measured peaks distinct from limit
  declarations/enforcement evidence and do not raise budgets silently.
- Rerun baseline default, selective/filter, expanded, and complete paginated
  browse/journal scenarios plus info, overview, crop, and browse-to-fetch flows.
  Bound this evaluation to 80 MCP calls/20 minutes. Report actual call counts,
  compact UTF-8 JSON bytes, completion, per-tool/catalog sizes, and transfer
  counts. Separate first-page/pagination effects from equal-content comparisons;
  bytes are not provider tokens. No fresh-agent benchmark is required.
- Keep bulk data, source paths, capabilities, and visual answers private. Add
  small deterministic unit cases for map generation/oracle independence,
  aggregation/completion, resource reporting, and private-output cleanup.

## Tests and acceptance

Add `tests/test_image_preview_measurements.py` for the harness logic; run large
files through a bounded separate integration command if unsuitable for the fast
suite. Correctness and resource assertions remain mandatory local acceptance.
Record the exact integration command and results without real capability tokens.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_measurements.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_workflows.py' -v
./scripts/test.sh
```

Accept when independent large-map pixels, bounded resource evidence, and the
comparable payload table pass. Commit generators, measurement tests/harness,
and aggregate evidence; preserve exact unmet environment prerequisites.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and large-map command/result: not run.
- Worker peaks/time, baseline/final call/byte/completion/catalog table: pending.
- Exact pending runtime prerequisites: pending.
