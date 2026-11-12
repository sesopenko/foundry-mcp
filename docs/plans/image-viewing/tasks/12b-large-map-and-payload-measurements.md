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

- Implementation: complete; [full-size and payload evidence](../large-map-measurements.md).
- Dependency commit SHA(s):12a `d5fe0de`.
- Commit: this commit.
- Focused outside-sandbox checks: measurements6 passed1.461s, workflows8 passed
  4.087s; unchanged failure-accounting regression separately passed0.251s after
  reproducing0-versus2 dispatched calls. Full `./scripts/test.sh`:899 Python
  (1 existing skip),750 JavaScript passed. No production code changed.
- `.venv/bin/python scripts/image-preview-measurements.py` passed actual10000²
  and10000x5000 maps:17 MCP calls,11 HTTP fetches,361/181 private chunks, one
  transfer/map. All independent native crop pixels, overview/reduced dimensions,
  decoded MIME/length/budgets and expected invalid-crop rejections passed.
- Measured square overview:1536² PNG1638691B,351961088 peakRSS bytes,
  301645824 scratch bytes,0.445672s/19 samples. Wide overview:2048x1024 PNG
  921407B,200380416 RSS/150925312 scratch,0.299555s/13 samples. Defaults
  remain1GiB/2GiB/90s; details distinguish render sampling from total client time.
- Live `.venv/bin/python -m foundry_mcp_server.image_preview_audit` passed23
  read-only calls/0.947s. Comparable defaults/filter/expanded/complete journal/
  browse rows match baseline byte counts. Development discovery45/275617B,
  versus43/262218B (+13399 for2 tools). Linked tables distinguish representations,
  first pages/full workflows/synthetic data and bytes from unmeasured tokens.
- All private maps/cache/store/processes cleaned. No game assets/documents or
  live public capabilities changed. Final large+live evaluation40 calls; earlier
  large verification adds17, remaining below80. Each large command enforces1200s;
  the independent live audit enforces120s. No additional passing runs needed.
- Exact remaining gates: map/font integration and final packaging13; existing
  authorized local runtime14a; configured live S3/CORS and prefixed deployment;
  public HTTPS and target-client14b. No fresh Foundry instance or operator action
  is required to finish this independently verified test checkpoint.
