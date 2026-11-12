# 14b — Target-client visual handoff

Points: **5** — journal and map-browsing handoffs with separate pixel/key evidence.
Re-estimated from 3 after adding map selection and annotation/legend acceptance.
Split from original task 14, estimated at 13 points. External availability is
recorded as a prerequisite rather than estimated as agent implementation effort.

Dependencies: [M06](m06-map-workflow-verification.md).
Intended commit: `test(images): prepare private-answer ChatGPT visual acceptance`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read source-design visual acceptance, [map research](../map-browsing-notes-research.md),
and M06/14a harness results. Reuse their bounded fixture setup, redaction, and
cleanup; do not implement another live harness.

## Implementation and unit tests

- Add a handoff mode/report to the existing harness that produces a nonrevealing
  target-client prompt, exact prerequisites, and separate local/visual statuses.
  Keep randomized expected symbol/label/colors in private ignored storage.
- Add `tests/test_image_preview_visual_handoff.py` covering prompt construction
  without private answers, opaque filenames/captions/alt text/tool results,
  redacted report fields, pending versus demonstrated pass, equivalent exact-link
  and query-variant trials, and cleanup delegation. Use deterministic fixtures;
  these tests do not prove ChatGPT can read pixels.
- Add a separate map-browsing prompt and unit assertions: choose an exact folder/
  map/level using only discovered next calls, request `map_notes=true`, identify
  a rendered key and follow the revision-bound legend to the right journal/page.
  Test prompt/report construction, omission visibility and separate pending/pass
  states. Do not count a legend lookup as proof of reading hidden map pixels.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_visual_handoff.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_live_check.py' -v
./scripts/test.sh
```

## External gate and acceptance procedure

This gate requires a reachable configured public HTTPS origin and the actual
target ChatGPT client with updated tools. Do not publish a deployment to create
prerequisites without separate authorization. If missing, finish and commit the
tested handoff/report, record exact prerequisites, and leave visual acceptance
pending. A successful HTTP test cannot satisfy this gate.

1. Use the authorized test world's marked temporary journal/map with an opaque
   filename and randomized information present only in a selected source region.
   Keep the answer outside prompt, prose, caption, filename, alt text, tool output,
   and tracked files. Reuse 14a's fixtures and exact-marker cleanup.
2. Supply the actual journal selector and original coordinates in this prompt:
   “Read journal `<journal selector>`. Inspect the image region with original
   top-left coordinates `<x>,<y>` and extent `<width>,<height>`. Tell me the
   short label or symbol and its colors visible there. Determine the answer
   from image pixels.” Do not supply the answer or a revealing filename.
3. Record observed info call, correct rectangle request, image-capable URL fetch,
   and answer from pixels. Record client-fetch failure separately from proven
   HTTP behavior. Do not leak the answer into another attempt or substitute
   intended/self-reported calls for actual observed calls.
4. Separately compare the exact capability and only its `?probe=1` variant in
   equivalent fresh contexts using the same nonrevealing prompt. Record each
   fetch/visual outcome independently with private traces and redacted evidence.
5. Clean only marked temporary fixtures. Source deletion does not revoke a
   published derivative; report its remaining seven-day lifetime honestly.

Commit handoff mode, unit tests, documentation, task statuses, and final aggregate
evidence. Report all task commit SHAs, verification results, exact gaps, and
cleanup outcome. Implementation completion, local verification, and demonstrated
visual acceptance remain distinct. No release, publication, push, or tag.

In a separate fresh target-client context, run M06's folder-to-annotated-crop
scenario. Supply the desired map's name and named folder ancestry, not its
preselected file or source handle. Observe actual map browsing, level/file
selection, annotated image fetch, rendered key identification, and journal/page
follow-up. Record complete/partial annotation and whether placement obscures
relevant features. Keep the hidden answer from the original pixel test absent
from every note label, caption, legend, filename and tool result. Both scenarios
retain explicit pending status when client/public HTTPS prerequisites are absent.

## Completion record

- Implementation: complete; [private-answer handoff](../visual-handoff.md) and
  [whole-design audit](../completion-audit.md).
- Dependency commit SHA(s):M06 `9ad2e1a`.
- Commit: this commit (resolve through final Git history/report).
- Focused handoff10/0.157s and helper12/1.387s pass; final full1053 Python
  (1 existing skip)/795JS passes148.844s. Reused-preparation regression failed
  before fresh lifecycle operation IDs and passed unchanged after correction.
  No journal-writer/idempotency or authentication semantics were weakened.
- Private0700/0600 challenge bundle and four distinct nonrevealing prompts are
  generated by the shared verifier. Native preparation5 calls/cleanup1 passes,
  including reuse after cleanup; no public URL issued. Actual label/color answers
  stay out of prompts, captions, alt, names, metadata and public reports.
- Actual target-client journal/hidden-pixel, exact/query controlled comparison
  and map/key/journal-page scenarios remain **pending**, not passed by unit or
  local image inspection. Exact prerequisite: operator-provided public trusted
  preview HTTPS origin on authenticated Basic/OAuth MCP, actual target ChatGPT
  with refreshed discovery, authorized same-world GM bridge and reviewed traces.
  The current loopback development endpoint is not that public deployment.
- Exact marked game image/journal fixtures cleaned; private handoff bundle
  retained for future operator preparation with ready=false/templates restored.
  Browser readyGM14.369/test/console0; no existing game assets/documents changed.
- Final current-image codec/font/annotation/private permissions/listener/recreation
  probe and owned cleanup passUID10001 at
  `sha256:0809b39f1da3dab32fb33ee33839d59ce825504c5f0ad84af2160cdff70054ad`.
  Compose10/moduleZIP3.3.1 pass; no push, tag, release, publication or new Foundry.
