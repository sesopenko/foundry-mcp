# Image viewing build progress

- Current task: 09a, [HTTP delivery and configuration](tasks/09a-http-delivery-and-configuration.md).
- Stage: commit.
- Last completed task: 08, commit `089b14f`.
- Persistent goal remains active. Its environment objective points to the attachment containing the full goal, read at kickoff; the complete assignment is preserved in the [execution prompt](../../prompts/foundry-image-viewing-build-agent.md).
- Next action: finalize09a package/runtime verification and commit; then09b privacy/auth matrix before any public issuance registration. No active failure; historical failed-attempt count3 is preserved, resolved by the authorized refactor.

## Completed checkpoints

| Task | Local commit | Full/hook outcome |
| --- | --- | --- |
|01 contracts/baseline | b0cc01e |709 Python (1 existing skip),717 JS passed |
|02 source resolution |141ede6 |710 Python (1 skip),728 JS passed |
|03a browser fetch |e4121a4 |710 Python (1 skip),739 JS passed |
|03b private RPC protocol |647c42b |710 Python (1 skip),748 JS passed |
|04a Python assembly |fe47d21 |720 Python (1 skip),749 JS passed |
|04b snapshots/identity |a045d08 |733 Python (1 skip),749 JS passed |
|05a decoder probe/package |57123ce |741 Python (1 skip),749 JS passed |
|05b resource components/refactor |cc7ba71 |770 Python (1 skip),749 JS passed |
|06a geometry/resampling |49e8aaf |782 Python (1 skip),749 JS passed |
|06b bounded encoding |4740720 |797 Python (1 skip),749 JS passed |
|07a raster codecs |02d0d8f |808 Python (1 skip),749 JS passed |
|07b guarded SVG |b144211 |821 Python (1 skip),749 JS passed |
|08 persistent derivative store |089b14f |836 Python (1 skip),749 JS passed |

Every task's tests/evidence are in its task file and linked detail page. Baseline
checkout was `2cd3d88`; no push, tag, publication, release or version bump.

## Current task04b evidence

All tests ran outside sandbox. Exact focused commands/outcomes:

- `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_sources.py' -v`:10 passed.
- `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_identity.py' -v`:3 actual HTTP/FastMCP auth-isolation tests passed.
- `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_transfer.py' -v`:10 passed.
- `.venv/bin/python -m unittest discover -s tests -p 'test_connection.py' -v`:6 passed.
- `.venv/bin/python -m unittest discover -s tests -p 'test_production_auth.py' -v`:13 passed.
- `.venv/bin/python -m unittest discover -s tests -p 'test_oauth*.py' -v`:19 passed.
- `node --test tests/js/image-preview-transfer.test.js tests/js/authentication.test.js tests/js/bridge.test.js tests/js/main.test.js`:27 passed.
- `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_sources_live.py' -v`:1 passed.
- `./scripts/test.sh`:733 Python (1 existing skip),749 JavaScript passed.

Restarted only the existing service and refreshed only the dedicated browser.
`./scripts/actor-tools.sh browser` reports readyGM14.369/test, consoleerrors0.
`.venv/bin/python scripts/image-preview-sources-live-check.py` passed canonical/
bare/absolute selection, immutable fetch, context/reservation, byte-free
membership and browser-only5-chunk reconstruction; max envelope534 bytes under
1024 ceiling. Only summaries cross MCP. No fixtures/game mutations/cleanup remain.

`.venv/bin/python -m foundry_mcp_server.image_preview_audit` passed23 calls/0.522s;
catalog remains43 tools/262,218 bytes. All equal-content cases match the original
[baseline](baseline.md). Two initial journal-navigation calls are omitted because
the exact private selectors were reused from ignored `.local/` storage. No billed
token measurement or new public tool is claimed.

## Decisions, API evidence and remaining gates

- [Source resolution](source-resolution.md): retain exact ImageSelector; a sole positively verified readable match may coexist with unavailable other parents, with private partial coverage. Zero matches plus unavailable remains BrowseFailed; multiple readable matches remain AmbiguousSource.
- [Fetch](source-fetch.md) and [protocol](transfer-protocol.md): immutable originals,128-MiB compressed,32-KiB chunks,16 in flight,15s stalls/300s total; exact socket cleanup and known pre-begin reservations.
- [Assembly](python-assembly.md): private700/600 directories/files, validated complete bytes/hash, explicit ownership, no replacement-socket cleanup.
- [Snapshot cache](snapshot-cache.md):1800s TTL,512-MiB files plus staging reservations, active worker leases, no valid-handle eviction, verified principal identity and fresh byte-free membership. Basic/dev scope proofs and OAuth issuer/sub/client verified via public FastMCP4.1.4 APIs and actual offline-JWT HTTP tests. No real Auth0 login/refresh acceptance claim.
- Grounded Docs foundry-vtt@14: completed2026-10-12T22:52:58Z,1,978 URLs/17,801 chunks. Official FilePicker/getRoute pages fetched and public status checked. FastMCP authorization/context docs fetched2026-11-11 and compared with pinned source.
- Actual Python assembly/cache over the running GM socket awaits task10's production entry point and12a integration; do not add a temporary public stub for evidence. Snapshot prune/close runtime wiring also belongs to10.
- Live S3 needs a configured readable bucket/CORS. Nonempty route-prefix live checks need an existing prefixed deployment; mocks cover both. External public HTTPS/target-ChatGPT visual acceptance remains14b. Real Auth0 login/refresh retains existing OAuth operator gates.
- The user closed the development browser after03b; it was reopened and the existing test-world GM restored via saved local credential, then readiness/RPC/console verified. Never provision another instance or reset existing data.

## Resolved failure history and attempt counts

No active failure. Every production correction below had a failing unit test
before correction and the same unchanged test passed afterward. Details live in
the linked evidence pages; Git history retains prior milestone records.

- 01 SDK-result dataclass serialization: corrected; unsuccessful corrections0.
- 02 mixed source availability policy: corrected with explicit partial coverage; unsuccessful corrections0.
- 03a packaging omission and HTTP wire/content encoding length distinction: corrected; unsuccessful corrections0 each. An initial full run overlapped the intentionally failing encoding test; final suites passed.
- 03b late lease release and malformed identified-command cleanup: corrected; unsuccessful corrections0 each.
- 04a cancellation during cleanup swallowed cancellation/unreturned-file ownership: corrected; unsuccessful corrections0.
- 04a harness-only responder registry used queued done callbacks. Gathering already-finished tasks failed to drain callbacks (one unsuccessful harness adjustment); moving registry removal into responder finally preserved/passed the empty-registry assertion. Raw selector fixture comparison also switched to established exclude_none serialization without changing expected selector. Production correlation remained unchanged.
- 04b: no unexpected behavior/fix attempts; all focused and full checks passed.

## Current05a checkpoint

- Selected official binary distribution: pyvips[binary]3.2.0 plus pyvips-binary8.18.7. `uv lock` added only those packages; `uv sync --locked` installed them. Native runtime8.18.7/API mode verified. No host libvips was installed; passwordless sudo is unavailable, but the supported self-contained wheel avoids that prerequisite.
- Internal worker uses explicit JPEG/PNG/WebP loaders, header-only display dimensions/all8 orientations,128MiB/32768-edge/128m-pixel bounds, fixed errors. Parent bounds4096-byte stdout during reads, suppresses stderr, private scratch, deadline/kill/reap. Still unexposed pending05b resource supervision.
- `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_probe.py' -v` passed8. Real subprocess tests passed exact128MiB sparse source, exact32768 edge/128m area, oversize known dimensions,8 JPEG orientations and malformed/unsupported sources. Upload baseline `test_image_uploads.py` passed13.
- Spawn-error regression first failed (raw OSError escaped before try), then passed unchanged after fixed-category handling. Unsuccessful corrections0. No active diagnosis.
- Local `docker build --pull=false -t foundry-mcp-image-preview-check:local .` passed. Dockerfile native PNG smoke after USER10001 passed. Separate `docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --user 10001:10001 --entrypoint python foundry-mcp-image-preview-check:local -m foundry_mcp_server.image_preview_worker --smoke` passed: UID10001,pyvips3.2.0/libvips8.18.7,16x12 PNG80bytes/still. No Foundry instance/volumes/publication.
- Full `./scripts/test.sh` passed741 Python (1 existing skip),749 JS; exit0. Documentation/prerequisites in docs/image-preview-decoder.md; README dependency paragraph links there.
- Latest browser request: dedicated browser reopened/reused; already logged in at /game, so join helper correctly refused a non-login page. Inspection and `./scripts/actor-tools.sh browser` confirmed ready GM14.369/test,zero console errors; health lists gm. No code defect or failed fix attempt.

## Current05b checkpoint

- Baseline05a probe8 passed. New supervisor8 tests passed real controlled RSS/scratch/open-unlinked-file failures, timeout/overflow/exit/cancel cleanup, serial/bounded queue admission, repeated spawn/reap cancellation, fail-closed monitor and upload independence. Probe8/upload13 regression checks also run.
- Root-cause investigation: asyncio Process.wait can deadlock after SIGKILL when stdout transport is paused on unconsumed oversized output. Focused `test_stdout_flood_reaps_without_waiting_for_a_paused_pipe` failed with the expected cleanup-deadlock assertion against an8MiB-flood child; test rescue drained the pipe to avoid hanging the suite. Production correction cancels the sole exchange reader, discards pipe bytes in4KiB chunks, then reaps. Same unchanged test passed, supervisor9/probe8/upload13 passed; unsuccessful corrections0.
- Real supervised native smoke on host:16x12 PNG80bytes/still,24,231,936 peakRSS bytes,0 scratch,0.03383s/3samples. Production defaults1GiB/2GiB/90s/oneoperation,25ms sampled checks plus scan/scheduler latency (no instantaneous hard-byte guarantee); eight queue waiters/90s queue timeout. Details/docs in docs/image-preview-decoder.md. Full suite55021 and Docker build84119 terminated with failures, detailed below.

### Mandatory diagnosis stop

- Full05b `./scripts/test.sh` failed:750 Python tests,1 error/1existing skip; JS not reached. Failure: real RSS/scratch recovery case, good child after exhausted child, sanitized ImageProcessingFailed.
- Initial container build84119 failed in supervised smoke with the same fixed error. Native header-only smoke passed. Subsequent build3334 passed after the demonstrated ESRCH race correction; packaged supervisor UID10001,15,269,888 sampledRSS bytes,0 scratch,0.07326s/4samples. This does not prove the remaining denial fixed.
- Proven separate race: opening a live proc status file then killing/reaping before reading produces actual ProcessLookupError/ESRCH. `test_process_exit_after_opening_proc_status_is_normal_completion` failed before correction and passed unchanged after narrowly handling exited-process exceptions. Permission failures remain fail-closed.
- Three unsuccessful attempts to resolve the intermittent recovery failure: (1) instrumented container native-probe reproduction,30 bounded calls all passed without capturing the error; (2) proved/fixed ESRCH race but recovery still failed; (3) instrumented30 short-child probes all passed without reproducing the recovery failure. Stop requirement applies; count3 persists across resume.
- Already-running diagnostic result40067 then captured the remaining cause: PermissionError/errno13 while scanning `/proc/<child>/fd`, after the real memory-exhaustion test and during its good-child recovery. Supervisor suite11 tests:1 failure; successful recovery assertion remains required. No raw native error leaves production output. Likely procfs/exec credential-access race, but exact causal mechanism and safe correction remain unproved. Do not swallow permission errors or retry speculatively.
- Focused commands: `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_worker.py' -v` (latest11/1failure); `-k process_exit_after` failed then passed unchanged; `-k stdout_flood` failed then passed unchanged; probe8/upload13 passed. All outside sandbox.
- Required input: user response authorizing continuation after this mandatory report. Then establish the exact denied-procfd lifecycle mechanism with a deterministic failing unit test before correction, preserve fail-closed behavior for genuine monitoring denial, and rerun focused/full/package checks. No task05b commit or dependent implementation yet.
- Temporary diagnosis helper `/tmp/preview-supervisor-diagnose.py` contains only controlled probe instrumentation; no game data/secrets. It is outside tracked changes. Docker checks mounted only repository code read-only and used no game volumes/network/publication.

### User-requested source research after stop

- The user explicitly requested GitHub MCP inspection of the exact Python
  version and supervisor dependencies. Completed that read-only research;
  [source evidence and lifecycle analysis](python-lifecycle-research.md).
- CPython3.12.12 tag fetched;9 installed stdlib files match upstream blob
  hashes exactly. Actual host watcher is ThreadedChildWatcher. TemporaryDirectory
  synchronously removes scratch on exit and can propagate cleanup failures;
  it never manages child/procfs lifecycle. No production correction/tests rerun.
- Matching base Linux6.12.116 source shows restricted procfs entries can become
  root-owned when task->mm becomesNULL during exit, before file teardown/exit
  notification. This gives a source-backed exit/ownership explanation to prove
  for errno13; the recorded failing child's kernel state remains unmeasured.
  Do not present research as a fixed or passing recovery test.
- User authorized this specific research after the mandatory stop. Persistent
  goal remains blocked; implementation resumption/next focused diagnostic is
  outstanding. Historical unsuccessful-attempt count3 is retained.

### User-authorized component refactor

- User explicitly requested a saved plan followed by separation, tests for each
  component, correction and usage/mock migration; user set persistent goal active.
  Assignment amendment saved verbatim; refactor plan written before code edits.
- Baselines outside sandbox: worker11/1failure (same recovery errno13),probe8/
  upload13 passed. Split admission/workspace/child/resource/coordinator boundaries;
  component tests passed4/3/6/7 before composition; probe9/coordinator7 now pass.
- Deterministic real process evidence: waitid(WEXITED|WNOWAIT) retains a child in
  stateZ; `/proc/<pid>/fd` becomes owned by UID0 and ResourceMonitor gets errno13.
  Focused `test_unavailable_proc_observation_of_exited_child_requires_owned_completion`
  failed against the mechanically extracted old coordinator with ImageProcessingFailed.
  Same unchanged test passed after requiring owned child completion within one
  existing monitor interval on PermissionError. No proc observation is retried
  or invented; denied live worker still fails closed, final named scratch is
  checked after reaping, no post-completion numeric PID measurement.
- This identifies resource/lifecycle composition as the faulty layer, not scratch
  deletion, memory budget or resource measurement. Real RSS/scratch/unlinked
  exhaustion then healthy-worker recovery passes. Historical count3 retained;
  correction after resumption succeeded first time. Separate test setup issue
  retained a100ms timeout for a100ms good fixture during the final-scratch phase;
  restored production timeout for that phase only, keeping expected rejection.
- Exact focused commands use `.venv/bin/python -m unittest discover -s tests -p
  'test_image_preview_<admission|workspace|child|resources|worker|probe>.py' -v`
  (each invoked separately; this notation is documentation, not a shell command).
  Final aggregate results/full/package evidence pending below.

### Final05b verification before commit

- `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_*.py' -v`:
  74 passed (admission4/workspace3/child6/resources8/coordinator7/probe9 plus
  contracts/identity/snapshot/transfer regressions).
- `./scripts/test.sh`:770 Python tests passed (1 existing skip),749 JavaScript
  passed, exit0. Previous failing recovery requirement retained and passing.
- `docker build --pull=false -t foundry-mcp-image-preview-check:local .`:passed,
  both native and supervised probes run as UID10001. Image digest recorded only
  in command output; no release/publication. Separate read-only/no-network run:
  `docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m --user 10001:10001 --entrypoint python foundry-mcp-image-preview-check:local -m foundry_mcp_server.image_preview_process --smoke`
  passed UID10001,PNG16x12/80bytes/still,14,987,264 sampled peakRSS bytes,
  0 scratch,0.07453s/4samples. No game resources were used or modified.
- `git diff --check` passed; exact usage search finds no supervisor subclass,
  supervisor-private gate/queue mock or unrelated process.asyncio patch. No
  additional broad benchmarks or automatic retries were run.

## Current06a checkpoint

- Baseline worker7 passed. Official libvips8.18 autorot/extract_area/resize/
  premultiply/unpremultiply/colourspace/ICC docs and pinned8.18.7 resize source
  read; random-access file opening docs confirm headers stay lazy and native
  full decompression spills under configured threshold/scratch settings.
- Geometry module owns exact crop, display orientation, source-region pipeline,
  integer output sizes, alpha-safe Lanczos3 and ICC/declared-space sRGB conversion.
  Worker region operation writes fixed private region.png; trusted operation
  collector reads it only after close/final scratch and before cleanup. No new
  public tool or public2MiB promise until06b. Shared lightweight PreviewFailure
  avoids duplicate exception identities when the worker runs as __main__.
- First geometry10 run:8 passed, exact10000-square sizing failed1535 vs1536,
  and repeat-evaluation fixture failed. Integer arithmetic equivalent to the
  specified scale corrected floating underflow; same exact-output test passed.
- Repeat fixture first had a missing repository import path (proved by direct
  fixture invocation); fixed trusted test PYTHONPATH without changing production.
  Then focused assertion failed with classified native out-of-order sequential
  read. Random native access corrected reusable-pipeline evaluation; identical
  test passed. No unsuccessful production corrections for either issue.
- Real supervised tests already pass native RGB/RGBA crops/edges/onepixel, all8
  PNG orientations vs independent Pillow oracle, invalid rectangles with known
  dimensions, alpha edge colors, grayscale16 and embedded-sRGB conversion.
- Exact focused commands: `.venv/bin/python -m unittest discover -s tests -p
  'test_image_preview_geometry.py' -v`; `-k exact_output` and `-k repeated` used
  for demonstrated corrections, expected assertions unchanged. Probe regression
  session65380 passed9. Geometry final11/worker8 passed; collector order/failure
  and malformed parent result checks included. New tests use current Pillow13
  get_flattened_data; official API/deprecation reference checked.
- `./scripts/test.sh` passed782 Python (1 existing skip),749 JS,exit0.
  `git diff --check` passed. Details/API evidence in crop-geometry.md. No new
  MCP registration, runtime game mutations or external prerequisites for06a.

## Current06b checkpoint

- Added separate native encoding policy and lightweight container-validation
  modules; worker render operation and typed parent collector reuse06a geometry.
  PNG first, WebP90/82,15% dimension reduction from original, one supervised
  deadline, fixed private candidate/preview files with partial cleanup.
- Official libvips8.18 pngsave/webpsave and Google WebP RIFF/lossless specs read.
  Native verification forces full pixel decode; parent verifies bounded actual
  PNG/WebP chunks/MIME/dimensions/size without raster allocation. Source metadata
  removed, generated resolution96DPI, alpha preserved.
- Initial render11 tests passed real high-entropy WebP and random-alpha reduction,
  lossless crops, independent lossy/alpha tolerance and metadata removal. Added
  empty-output regression failed (fallback wrongly accepted later file), then
  passed unchanged after rejecting zero-byte candidates. Corrupt-generated-file
  regression failed with UnsupportedImage, passed unchanged after verification
  maps generated failures to ImageProcessingFailed. Unsuccessful corrections0.
- Final focused render15,geometry11,worker8 passed outside sandbox. Partial
  writer failure and hard worker deadline cleanup preserve original files.
  Added synthetic technical byte/dimension output for final measurement record;
  no game images, pixel answers or capability information are printed.
- Next: final focused/full suites, record artifact measurements/docs, commit06b.
- Final focused render15 passed with bounded synthetic evidence: PNG22x18/127B,
  WebP1536²/1,664,334B, WebP1109²/1,968,390B, metadata-freePNG19x11/107B.
  Native/policy/container docs in preview-encoding.md.
- Full `./scripts/test.sh` passed797 Python (1 existing skip),749 JS,exit0.
- `docker build --pull=false -t foundry-mcp-image-preview-check:local .` passed,
  including UID10001 native/supervised smokes. Then
  `docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m --user 10001:10001 --volume /home/sean/src/github.com/sesopenko/foundry-mcp/tests:/checks:ro --entrypoint python foundry-mcp-image-preview-check:local -m unittest discover -s /checks -p test_image_preview_render.py -v`
  passed15 as UID10001 against shipped application/native code. Only tests were
  mounted read-only; no source override/game volume/network/publication. Both
  real WebP sizes matched host measurements. No new external prerequisite.
- Diff/whitespace reviewed; no MCP tool/discovery or Foundry browser changes.

## Current07a checkpoint

- Recovery reread all required assignment/design/index/research/current task and
  repository reading. Goal active; healthy existing service lists GM. Previous
  goal turn was progress (06b committed and verified). Probe9 baseline passes.
- Added explicit GIF/TIFF/AVIF admission and expanded private typed MIME contract.
  Native page0/n1 prevents frame stacks; TIFF retains shared EXIF orientation.
  Narrow Pillow13 adapters handle BMP (no built-in libvips loader), APNG with
  separate fallback, and AVIF timed sequences; final rendering remains libvips.
  These adapters do not normalize pixels during info/header probing. Source,
  scratch/RSS/deadline and final artifact limits remain enforced; uploads unchanged.
- New real format tests first failed for absent format admission and APNG policy.
  After native admission, timed AVIF test alone failed: native page count was1
  while the fixture contains2 timed frames. Pinned Pillow13 sequence count/frame
  selection corrected that boundary; same unchanged first-frame test passes.
  No unsuccessful corrections; no active diagnosis. Upstream GitHub MCP fetched
  Pillow13 AvifImagePlugin.py; decoder's public DEFAULT_MAX_THREADS is explicitly
  set2 and restored, with a focused test. It reads compressed source to memory,
  still bounded128MiB plus supervised RSS; no header-only pixel allocation claim.
- Current focused formats10 pass: all still/animated/page pixel cases, APNG
  fallback, TIFF/AVIF all8 orientations vs independent oracle, alpha, malformed
  bodies, BMP exact/oversize bounds and no-normalization info checks. Next final
  matrix includes loader/version inventory; full/package evidence pending.
- Final formats matrix11 passed in production image asUID10001,9.787s with
  pyvips3.2.0/libvips8.18.7/Pillow13.0.0 and all6 explicit native loaders present.
  Exact read-only/no-network Docker command is in task07a. Build/smokes passed.
  Only tests mounted read-only; no app override/game resource/publication.
- Focused render15/upload13/geometry11 passed. `./scripts/test.sh` completed
  exit0, both suites passed,749JS and1 existing Python skip. Initial verbose
  command output truncated across polling chunks; no unsupported exact Python
  count is claimed here. All new11 tests are covered by full runner discovery.
- Documentation and whitespace reviewed. No new runtime/browser/public-tool
  boundary changed; all temporary fixtures are unit-owned and cleaned.07a
  completion commit is this commit; resolve SHA at next task checkpoint.
- Commit02d0d8f completed; pre-commit hook provided exact count808 Python
  (1 existing skip)/749JS, both passed. Working tree clean afterward.

## Current07b checkpoint

- Task read fully; dependency07a committed. Official libvips8.18 svgload docs
  establish explicit dpi (native default72, set96), lazy header loading, native
  10MB security guard and librsvg dependency. Official librsvg security guide
  fetched; raw source must never reach loader before a bounded subset admission.
- Planned boundary: UTF8 XML with DTD/entities/PIs rejected; bounded node/depth/
  attribute counts, explicit SVG elements/presentation attributes, local fragment
  refs only with cycle/expansion checks, conservative inline style declarations.
  Reconstruct admitted document at fixed96-DPI dimensions, then explicit native
  svgload. No external image/font/CSS/script/foreign constructs. Test private
  sentinel/local listener and native-loader noninvocation on rejected input.
  No07b implementation yet; existing raster matrix is baseline.
- Implemented bounded UTF8 XML guard/reconstruction, exact local references,
  structure/expansion bounds,96-DPI/viewBox sizing and explicit native loader.
  Added private MIME admission. No public tool or Foundry API change.
- Two defects proved with failing tests before correction, same tests unchanged
  afterward: (1) dpi96 globally enlarged SVG through libvips dpi/72 scaling;
  pinned GitHub native source confirms cause, explicit scale72/96 compensates;
  (2) uint32-only error DTO rejected safely known SVG width10billion; exact-JSON
  integer error bound now2^53-1, admitted source limits unchanged. Unsuccessful
  corrections0; no active diagnosis. Parser rejects extreme numeric magnitudes.
- Focused SVG12, raster11,upload13 pass outside sandbox. File sentinel IN_OPEN
  and local HTTP listener positive controls pass, then no native file open or
  resource HTTP request for rejected source. Timeout cleans owned scratch and
  retains original. Full ./scripts/test.sh passed both suites exit0,749JS;
  exact Python count will also be captured from commit hook.
- Production Docker build passed native/supervised UID10001 smokes; SVG12 passed
  asUID10001/3.585s with --network none, read-only app/test mount and128MiB tmpfs.
  Exact command matches07a with test_image_preview_svg.py. No game assets,
  other Foundry instance, source override or publication. Upstream pinned build
  manifest specifies rsvg2.63.2/Cairo1.18.6; runtime exposes libvips8.18.7 and
  actual SVG decode, but rsvg version symbols are hidden (documented distinction).
- Final review found a conservative paint check mistaking the letters `url` in
  named colour `burlywood` for a URL function. New pixel test failed before the
  correction; matching the actual url(...) function keeps external references
  rejected and the unchanged named-colour test passes. Unsuccessful corrections0.
- Final focused SVG13 passes; rebuilt production image and reran SVG13 asUID10001,
  passed3.755s including both external-resource positive/negative controls.
  Full suite repeated for this demonstrated correction; awaiting final result
  before commit. No unrelated code changes or active failure.
- Final ./scripts/test.sh passed821 Python (1 existing skip),749JS,exit0.
  Diff/whitespace and subset documentation reviewed. Ready for task07b local
  commit; no remaining fixture cleanup or external prerequisite for this task.
- Commitb144211 completed after required hook passed both suites; clean working
  tree afterward. Exact full pre-commit run821 Python/749JS already recorded.

## Current08 checkpoint

- Task read fully after07b commit; dependency01 is b0cc01e. Publication design
  requires private SQLite BLOB transactions, UUID4 digest-only storage,
 604800-second expiry enforced on every lookup,1GiB/4096 live quotas, atomic
  prune/admit and restart persistence. No browser/public route needed yet.
- Baseline next action: inspect existing private SQLite lifecycle conventions
  and test store-independent behavior; no task08 source implementation yet.
- Read current pdf/library.py connection/setup/private-path/BEGIN IMMEDIATE
  patterns, pdf/runtime.py and Docker UID/storage conventions; no PDF changes.
  New store owns only complete derivative BLOBs and digest lookup, with per-call
  SQLite connections, explicit writer transaction, FULL/DELETE durability and
  fixed failures. Clock/quota injection never enters MCP inputs.
- Focused `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_store.py' -v`
  passed15 outside sandbox: realPNG/WebP, UUID4/digest/repr privacy, exact expiry
  without prune, restart, quotas/bounded concurrent writers, SQL rollback,
  invalid artifacts, active600 journal, symlinks/corruption/closed state.
  No unexpected behavior, diagnosis or unsuccessful attempts. Full suite running.
- Full ./scripts/test.sh passed both suites exit0,749JS and1 existing Python
  skip; exact Python count to be captured from hook. Docker rebuild passed,
  then store15 passed0.071s asUID10001/read-only/no-network/128MiB tmpfs using
  shipped application and SQLite. Only tests mounted read-only; no app override,
  Foundry resources or publication. Task08 records exact command.
- Diff/whitespace and store invariants reviewed; no fixture cleanup or
  unavailable local evidence. Ready to commit08 and continue09a.
- Commit089b14f completed after hook passed836 Python (1 existing skip)/749JS;
  clean working tree afterward. No unfinished implementation remains in08.

## Current09a checkpoint

- Task read fully after08 commit. Current dependency is089b14f;13 of30 tasks
  complete,86/200 points (43%). No09a implementation yet. Next read main.py,
  config.py HTTPS origin helper, evaluation logging/auth tests and OAuth operations;
  retain unregistered issuance until09b privacy/auth matrix is complete.
- Resumed full assignment/design/index/research/task/repository reading. Previous
  goal turn was progress:07a/07b/08 committed. Health confirms existing GM;
  goal remains active. Only index/progress checkpoint docs initially modified.
- Read current main/config/evaluation/auth tests and OAuth runbook/verification.
  Baseline app6 and production-auth13 passed outside sandbox before edits.
  Used code graph lifespan/settings impact and current source; no Foundry API
  or module behavior change. Pinned Starlette1.10 public Response/lifespan docs
  fetched via GitHub after old documentation-domain fetch returned502.
- Added independent preview origin/data-dir settings, server issuance policy,
  owned threaded store runtime/prune/drain, and exact GET/HEAD prefix handlers
  before MCP mount. No public issuance tool. Plain-none issuance disabled;
  configured read store remains independent of GM/authentication lifetime.
- Unwritable-store test failed: local storage failure wrapped by MCP TaskGroup.
  Moved store setup before framework context while retaining outer close;
  same unchanged test now passes. No failed production correction attempts.
  Two test setup mistakes: POSIX environ rejects NUL before Settings, and MCP's
  lifespan property is read-only. Used controlled getenv/dependency seams;
  expected configuration/cleanup assertions unchanged, no production workaround.
- Focused HTTP14,production-auth13,OAuth19 and JS authentication/bridge/main17
  passed. Full ./scripts/test.sh passed both suites exit0 (749JS, existing Python
  skip); exact count to be captured from hook. Package HTTP matrix running.
- Initial package HTTP14 passed asUID10001 against shipped application with
  read-only/no-network/128MiB tmpfs and tests-only mount. Restarted existing
  service after offline suites; healthy GM reconnects and real curl HEAD of
  /image-previews/invalid returns404,zero body,no-store,nosniff,no redirect.
- Final review found shared root handler's default filename was interpreted by
  FastAPI as a query selector. Added root filename-query test, observed200 vs
  required404; handler now reads only request.path_params. Same unchanged test
  passes, final HTTP15 passes. No unsuccessful corrections. Repeated full/package
  checks for that correction are running; no public capability/tool was issued.
- Final HTTP15 passed in rebuilt UID10001 production image0.167s; full
  ./scripts/test.sh again passed both suites exit0,749JS/1 existing Python skip.
  Diff/whitespace reviewed. Ready to commit09a; no game fixture cleanup, valid
  public URL issuance or auth/proxy deployment change.09b is next.
