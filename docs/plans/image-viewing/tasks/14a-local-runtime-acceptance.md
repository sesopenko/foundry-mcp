# 14a — Local runtime acceptance

Points: **8** — bounded real-runtime fixtures, curl checks, and evidence reconciliation.
Split from original task 14, estimated at 13 points.

Dependencies: [12b](12b-large-map-and-payload-measurements.md),
[13](13-deployment-and-packaged-verification.md).
Intended commit: `test(images): add bounded local runtime acceptance`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile all dependency commits and
test evidence. Follow the index's execution and commit protocol.

Read every source-design acceptance checkbox and task 01/12a/12b/13 evidence. Use
the repository's development-connect and development-loop skills, existing
test-world credentials/profile, and [browser guidance](../../../browser-development.md).
No new Foundry instance or ordinary-browser attachment is authorized.

## Implementation and local verification

- Add `scripts/image-preview-live-check.py` as a bounded harness using the
  project's existing authenticated MCP client patterns. Default bounds: 60 MCP
  calls/20 minutes for local acceptance, excluding separately reported target
  ChatGPT interactions. Stop once criteria pass; do not launch extra agent
  benchmarks. Keep fixture assets, source data, capability URLs, and expected
  visual answers in private ignored storage, and print aggregates only.
  [14b](14b-target-client-visual-handoff.md) separately owns the visual handoff.
- Add harness unit tests before live execution: exact fixture ownership/cleanup,
  call/time ceilings, HTTP/header/hash comparisons, missing prerequisites,
  redaction (including exceptions), and reporting that distinguishes pass,
  failure, and pending. Do not add arbitrary-command/URL/world execution to a
  trusted runner. Any new fixed runner case requires its own review and tests.
- After focused/full offline tests, reuse the dedicated root-Compose `test`
  world/browser. Refresh module code, wait for authenticated GM readiness, and
  inspect new console errors. Use safe marked temporary images and journals
  only, with exact-marker bounded cleanup on success/failure. Preserve existing
  assets and avoid repeated manual login/setup.
- Through actual current discovery and tool calls, verify bare stored journal
  src, a tag split across returned fragments, browse portrait selector, a core
  SVG, info/overview/detail flow, original snapshot reuse, and actual delivered
  image dimensions. Live S3 is a separate pending result unless configured and
  tested; mock S3 success is not live evidence.
- Against an available real HTTP listener and issued disposable derivative,
  run curl GET twice without `-L`: once with the exact issued URL and once with
  only `?probe=1`. Capture status, MIME, length, cache/nosniff headers, redirect
  count, decoded validity, and SHA-256. Require 200, zero redirects, and equal
  bytes. Check HEAD separately with matching headers and no body. No credential
  header is allowed on these reader checks. Keep tokens out of command
  transcripts/logs; feed private curl configuration through the harness.
- Reuse task 09a's injected-clock proof immediately before/exactly at 604,800
  seconds with cleanup paused. Reuse or rerun task 13's same-volume restart
  proof only if its dependencies changed; do not restart production. Do not
  launch a competing project service. If exact HTTPS-origin checks need an
  unavailable public endpoint, report that precise gap separately from local
  HTTP tests and finish independent checks.
- Include task 12b's measured 10,000-square case (RSS/scratch/time), final actual
  discovery/input/output schemas, tool-record/catalog size, response/call totals,
  and comparable paginated workflow evidence. Resolve all relevant regression
  failures. Do not call byte counts provider tokens or HTTP success visual proof.

## Tests, commit, and final report

Add `tests/test_image_preview_live_check.py`. Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_live_check.py' -v
./scripts/test.sh
```

Then run the bounded live harness outside the sandbox if prerequisites exist.
Commit harness, its unit tests, updated evidence, and task statuses even when
external prerequisites are pending. Local failures remain
failures, not pending-client results. Final reporting must list task commit
SHAs, checks and aggregate measurements, cleanup outcome, and each exact live
gap. Keep implementation, local verification, and visual acceptance separate.
No publication, release, push, tag, or changes to live game assets.

## Completion record

- Implementation: complete; [runtime acceptance evidence](../runtime-acceptance.md).
- Dependency commit SHA(s):12b `5bae8bb`,13 `a10d601`.
- Commit: this commit.
- Focused12 passed1.401s; full1032 Python (1 existing skip)/794JS passed135.075s
  outside sandbox. Native script passed20 MCP calls within60/1200s guard; wall
  time not independently captured. Actual discovery47 tools/323516B.
- Native15 curl checks passed exact HTTPS/query GET and HEAD, no credentials,
  redirects0, matching headers/hashes/decoded dimensions and empty HEAD. TLS is
  loopback-only with an explicit fixture CA. Retained injected-clock exact-expiry
  and13 same-volume packaged restart checks remain passing independent evidence.
- Source snapshots reused for3 distinct previews; stored image tag reconstructed
  across4 actual journal fragments; browse selector and core SVG pass. Resource
  peaks from12b retained without redundant benchmarks; tables in linked evidence.
- Exact marked journal/image cleanup and existing-document fingerprints passed;
  private settings restored and temporary TLS/store removed. Dedicated-browser
  refresh/readiness/console result recorded in build progress before commit.
- Target-client handoff: delegated to 14b.
- Exact unmet external prerequisites: public trusted HTTPS/target ChatGPT client
  remain14b; live S3 needs configured readable bucket/CORS; prefixed deployment
  needs an existing endpoint. No unmet local prerequisite for the completed flow.
