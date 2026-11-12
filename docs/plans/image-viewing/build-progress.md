# Image viewing build progress

- Current task: M03b, [coordinates and revision binding](tasks/m03b-map-coordinate-and-revision-binding.md).
- Stage: commit.
- Last completed task: M03a, commit `26bb4e6`.
- Persistent goal remains active. Its environment objective points to the attachment containing the full goal, read at kickoff; the complete assignment is preserved in the [execution prompt](../../prompts/foundry-image-viewing-build-agent.md).
- Next action: commit verified M03b with required hook, then read M04a and establish bundled-font/text baselines. No active failure; historical failed-attempt count3 is preserved, resolved by the authorized refactor.

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
|09a HTTP/config/lifecycle |37977ee |Both full suites/hook passed;749JS |
|09b auth/privacy |4023ed2 |859 Python (1 existing skip)/749JS full passed; hook passed both |
|10 image info |85236ce |871 Python (1 existing skip)/749JS full passed; hook passed both |
|11 image URL |f5d04c3 |885 Python (1 existing skip)/749JS full passed; hook passed both |
|12a cross-layer workflows |d5fe0de |893 Python (1 existing skip)/750JS full passed; hook passed both |
|12b large maps/payloads |5bae8bb |899 Python (1 existing skip)/750JS full passed; hook passed both |
|M01 map browsing |e9ea43e |912 Python (1 existing skip)/761JS full passed; hook passed both |
|M02 grid/image files |af58e0d |928 Python (1 existing skip)/777JS full passed; hook passed both after final declarations/test |
|M03a note identities |26bb4e6 |942 Python (1 existing skip)/783JS full and hook passed |

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
- Commit37977ee completed after hook passed both suites,exit0; clean working tree
  afterward. Final HTTP15 and prior836-test baseline imply851 Python tests;
  verbose hook summary was truncated, so no measured exact hook count is claimed.

## Current09b checkpoint

- Task read fully after09a commit.14/30 tasks complete,91/200 points (45.5%).
  Actual reader auth matrix, emitted Uvicorn/application logs, evaluation traces
  and capability-safe proxy guidance are required before task11 registration.
  No09b implementation yet. Existing auth13/OAuth19/JS17 passed in09a; HTTP15
  baseline is committed. No new Foundry API, tenant/login or fixture prerequisite.
- Read pinned installed Uvicorn0.40.0 h11/logging implementation and current
  evaluation/principal/provider code. Code graph/source audit covers shared
  TraceRecorder.emit and MCPAccessControl. Initial captured access/application/
  evaluation tests each failed by finding the fixture nonce in emitted output.
  Narrow logging filter plus trace fingerprint redaction makes those unchanged
  tests pass, preserving status/method/ordinary health logs and payload metrics.
- Two redactor robustness regressions failed before correction and passed
  unchanged: encoded malformed IPv6 URL classification raised ValueError;
  unpaired-surrogate JSON string hashing raised UnicodeEncodeError. Fixed URL
  classification boundary and surrogate-safe fingerprint encoding. No failed
  production correction attempts; no active diagnosis.
- Fresh actual-app fixture bounds4 processes/30s each/<=16 calls per mode.
  Matrix initially failed development DuplicateCredentialsAccepted: previous
  dictionary header collapse accepted duplicate Authorization. Explicit one-
  header/8192-byte guard fixes it; same unchanged denial now passes. Exception
  group diagnostics were flattened to fixed enum reasons only (no secrets).
- Current privacy8 passed. Matrix results: Basic8calls,OAuth12,development8,
  none3; all complete. Anonymous pixels work in all4 configured read stores;
  only authenticated modes can issue, invalid/duplicate MCP and PDF access is
  denied, valid offline JWTs pass, invalid key/subject/scope and Basic-in-OAuth
  fail, and image capabilities cannot authenticate the actual GM WS route.
- Real Uvicorn H11 protocol + production ASGI app + memory transport emitted
  redacted200/query200/404/503 access records; health remains visible. No second
  listening server or Foundry instance. Signed/encoded URL, idempotent install,
  exception and evaluation aggregate tests pass; existing evaluation7 also pass.
  Full focused regressions/package/full suites and final documentation next.
- Final discovery-inclusive auth matrix adds1 call/mode: Basic9/42tools/259253B,
  OAuth13/42/261857B,development9/43/259741B,none4/42/259253B. Compact raw
  result.tools JSON, distinct from older whole-response baseline; no savings or
  token-billing claim. No URL issuance stub registered. Privacy8 passed after
  adding discovery assertions, and in production UID10001 image8/8.950s with
  read-only/no-network/128MiB tmpfs/tests-only mount; no source override/game data.
- Focused HTTP15/evaluation7/production-auth13/OAuth19 passed. Full
  `./scripts/test.sh > /tmp/foundry-image-preview-09b-tests.log 2>&1` passed859
  Python (1 existing skip)/749JS. Only test-log output was redirected; no code
  edits or Git commands used command-driven writes. Hook repeats final staged
  tests after the discovery-only fixture assertion addition.
- Recovery confirmed stored runtime journal evidence: restart completed,
  Application startup complete, one redacted preview-path record and zero raw
  invalid-path/query probe records. Health is ready with GM connected. Final
  diff/whitespace reviewed; no valid live capability, game fixture or cleanup.
- Commit4023ed2 completed with both required hook suites passing,exit0.

## Current10 checkpoint

- Task read fully; dependencies04b a045d08 and05b cc7ba71 committed.15/30
  tasks complete,96/200 points (48%). Source/probe/registration/auth current
  source and code graph inspected; no new Foundry API dependency is required.
- Planned composition: lifecycle-owned snapshot cache independent of public
  origin, stage/probe validation before admitting a handle, strict response
  boundary and existing OAuth metadata. Invalid/probe-canceled originals must
  be cleaned without publishing a handle. Baseline and implementation next.
- Baseline source10/probe9 passed outside sandbox. Added lifecycle-owned cache
  and strict image/src info registration. Trusted validation callback probes and
  rechecks membership before cache admission; invalid/canceled work creates no
  handle. No public origin or new Foundry API is needed.
- Initial9 actual MCP tests passed. Added repeated-cancellation close regression
  failed because cancellation interrupted cache cleanup; owned close task using
  existing settle fixes it, same unchanged test passes. No unsuccessful fixes.
- Current focused tools11/source10/OAuth19 passed. Discovery record4867 compact
  UTF8 bytes, synthetic results below512B. Unit-tested live checker bounds4 calls/
  60s, prints only technical aggregates and rejects private extra output fields.
  Full regression and actual localhost evidence pending.
- Full first run870 tests: only container-smoke catalog equality failed because
  its fixed expected tool set lacked the newly registered image-info tool.
  Updated that verification usage point; equality assertion remains unchanged.
  No production behavioral correction or unsuccessful diagnosis attempt.
- After full870 Python (1 skip)/749JS passed and packaged tools11 passed1.708s,
  actual localhost info returned UnsupportedImage for the core anchor SVG.
  Read-only stock-icon inspection found inert class and touch-action:none hints
  rejected by the conservative guard. New independent-pixel SVG regression failed
  before correction; sanitizer now removes class and only that exact interaction
  declaration before native loading. Same test passes, unsafe touch-action URL
  remains rejected. This is a real decoder-admission defect, not a test change;
  no unsuccessful production corrections. SVG14/tools11 pass; repeating full/
  packaged verification for the demonstrated correction.
- Checker error reporting now exposes only fixed allowlisted failure categories
  so live diagnosis does not print native/browser messages or private selectors.
- Final full `./scripts/test.sh > /tmp/foundry-image-preview-10-tests.log 2>&1`
  passed871 Python (1 existing skip)/749JS. Rebuilt image passed smokes and tools11/
  1.697s,SVG14/4.280s asUID10001, read-only/no-network/tests-only mount.
- Existing service restart and actual fresh HTTP checker pass4 MCP calls:
  canonical and bare core SVG512x512/1136 source bytes/still,196B result each,
  distinct private handles,44 development tools and4874B tool record. No public
  URLs or game fixture/assets were created. Product cache owns staged originals
  for1800s; normal expiry/pruning applies. External gates unchanged.
- Browser inspection found4 transport-error records at the reconnect handler
  after service restarts. Refreshed only the dedicated development tab; ready GM
  14.369 with0 console errors and health gm restored. No continuing runtime error.
- Final diff and whitespace reviewed; ready for task10 local commit.
- Commit85236ce completed after both hook suites passed,exit0.

## Current11 checkpoint

- Task read fully; dependencies07b b144211,09b4023ed2,1085236ce committed.
  16/30 tasks,97/200 points (48.5%) complete. Tool11 accepts base image/src/
  source_id and crop only; map context/notes remain M05. Current info/HTTP/
  store/render interfaces and structural references read; committed baseline
  tools11/HTTP15/full871+749 passed. No new Foundry API dependency.
- Plan: configuration check first, stage/probe selector inputs, lease originals,
  render/validate exact artifact, recheck membership/authority around publication,
  then return strict result and release lease. Atomically completed but canceled
  publication may leave an unreturned immutable row until normal expiry; no
  partial bytes or invented retry/idempotency contract. Tests must prove this.
- Base URL composition implemented; initial actual tools20 pass in3.249s. Real
  native crops match independent original-region pixels, handles reuse transfers,
  distinct immutable links/query-independent HTTP reads, snapshot replacement,
  quota retention, strict discovery/auth/expiry/context and canceled-render lease
  cleanup pass. No live public capability or game mutation performed.
- Actual HTTP client logging in these tests exposed URL-object arguments that
  become strings only during formatter interpolation. New privacy URL-object
  regression failed (nonce emitted) before correction. Filter now classifies
  nonprimitive diagnostic objects' string forms before formatting while retaining
  safe original values. Same unchanged test verification pending; attempts0.
- URL-object regression passed unchanged; privacy9 and actual four-mode matrix
  pass (10/14/10/5 calls, including disabled URL-tool invocation). HTTP15/OAuth19
  pass. Added publication-cancellation and real Basic HTTP issuance; tools22 pass.
- Forged valid render reply could substitute the overview for a requested crop.
  Focused worker-region regression failed before correction; final publication
  compares exact requested region with validated geometry, same test passes.
  Final tools23 pass3.541s, URL discovery8516B, source-info4867B; no unsuccessful
  fixes or active failure. Captured HTTP-client logs now contain no raw UUID paths.
- Full and packaged tools/privacy verification running. Current branch runtime
  still needs restart/discovery check; no new game assets or public links minted.
- Final tools24 (including bounded disabled-runtime checker) passed; final full
  `./scripts/test.sh > /tmp/foundry-image-preview-11-tests.log 2>&1` passed885
  Python (1 existing skip)/749JS. Docker rebuild passed smokes; packaged tools24
  passed7.514s, privacy9 passed9.563s,UID10001/read-only/no-network/tests-only.
- Existing service restarted. Actual fresh HTTP disabled-URL checker passed2
  calls/45 development tools/8523B live tool record. Local origin remains unset;
  no live bearer issued. Auth fixture39 total calls across4 modes verifies real
  disabled URL invocation, unchanged protection and discoverability.
- One restart transport-error record at known reconnect handler; dedicated tab
  refreshed for clean readiness/console check before commit. No JS/game changes.
- Dedicated browser now readyGM14.369/console0; health gm connected. Final
  diff/whitespace reviewed and task11 evidence ready for its local commit.
- Commitf5d04c3 completed with both hook suites passing,exit0.

## Current12a checkpoint

- Task/source acceptance, baseline and budgeted-evaluation reading complete.
  Dependency11 f5d04c3 committed;17/30 tasks,105/200 points (52.5%) complete.
- Planned fixture: real production Foundry bridge dispatch in a Node subprocess,
  mocked external Foundry public documents/FilePicker/fetch only; real Python
  RPC manager/correlation and HTTP-authenticated MCP app/cache/store/decoder.
  Reconstruct actual paged journal HTML before extracting src, browse an exact
  image selector, transfer multichunk bytes, request repeated independent crops,
  verify anonymous HTTP bytes and deterministic faults/ownership/cleanup.
  Harness cap40 MCP calls/600s; aggregate output only, private small synthetic
  images. Full-size generation/resources/comparable final measurements remain12b.
- Baseline browser sources/transfer21 passed. Added Node fixture that runs real
  journal/image bridge dispatch and returns each negotiated chunk window in
  deterministic reverse order; real Python correlation reconstructs correct bytes.
  New JS workflow test passed; focused JS sources/transfer/workflow22 passed.
- Initial JS test assumed two HTML fragments when the stored text requires3.
  Followed actual returned cursors until complete; unchanged full-content equality
  passes. This was a fixture expectation mistake, not a production defect/fix.
- Python workflows7 pass: actual Basic-auth MCP discovery/invocation, real Node
  handlers/private multichunk bytes/native subprocess/SQLite/anonymous HTTP,
  journal and browse input paths, mirrored/rotated transparency, missing/short
  replies, cancellation/new socket, pinned replacement bytes, expiry/permission,
  worker-error propagation and quota retention. Private roots removed on exit;
  call/time guards exercised. Existing actual OAuth cross-principal tests rerun
  separately; no fresh-agent benchmark or live game fixtures needed.
- Final focused/full checks running after deterministic out-of-order transport
  and whole-image pixel assertions. No production code changed or active defect.
- Full ./scripts/test.sh passed892 Python (1 existing skip)/750JS,exit0.
  Actual identity3 passed; final canonical-prefixed-fetch assertion passes in
  focused workflows7 and JS workflow1 (combined JS22 already passed). Hook will
  repeat both suites with the final assertion. No production files changed.
- Complete small workflow measured10 MCP calls/3 fragments/3 source transfers/
  12 reversed chunks/4 anonymous reads; linked workflow table records compact
  bytes and completion. Private roots/processes/pending RPCs/leases cleaned.
  No external client/runtime claim or new game fixture was introduced.
- Final simulated-browser EOF test failed promptly-required behavior with2s
  TimeoutError. Root was test transport receive() lacking the production
  WebSocket route's unregister-on-close finally callback. Added that exact
  callback to the fixture only; same unchanged test/full suite now verifying.
  No production defect/correction or unsuccessful fix attempt; no scope reduction.
- Same unchanged EOF test passes; final workflows8 pass3.996s. Final full
  ./scripts/test.sh passed893 Python (1 existing skip)/750JS,exit0, after the
  fixture callback correction. Final whitespace/diff review passed; ready12a.
- Commitd5fe0de completed with both hook suites passing,exit0.

## Current12b checkpoint

- Task read fully; dependency12a d5fe0de committed.18/30 tasks,113/200 points
  (56.5%) complete. Current workflow harness, resource metrics and baseline audit
  read. W3C PNG third-edition primary specification inspected for bounded row
  streaming (IHDR/IDAT/zlib/CRC), avoiding a giant parent raster for generation.
- Plan: streaming deterministic synthetic RGB maps with small distinct center/
  far-edge marks, independent small-region oracle, real10000-square/wide workflows
  through12a authenticated MCP/JS/RPC/native/store/HTTP harness. Capture private
  WorkerMetrics aggregates at trusted render boundary. Bound combined integration
  to80 MCP calls/1200s; live equal-content baseline replay stays separate from
  synthetic data. Keep filenames/mark values/capabilities private.
- Added bounded RGB PNG streaming writer (16 cached rows), center/far-edge marks,
  independent scalar region oracle, resource evidence aggregation, actual MCP
  measurement command and4 small tests. Small workflow first failed a privacy
  assertion matching the substring url in the safe tool name get_foundry_image_url;
  corrected the test to forbid actual URL values/private field keys. No production
  change or hidden-data relaxation. Focused4 now pass; real large command running.
- Separate expected InvalidCrop measurement label keeps intentional negative
  calls distinct from complete successful URL streams. Shared workflow harness
  gains trusted optional measurement labels; production tools unchanged.
- Real full-size command passed twice (second adds independent HTTP decode and
  per-map resource evidence),17 MCP calls each; final data:10000-square PNG
  overview1536²/1638691B,351961088 RSS/301645824 scratch/0.44567s;10000x5000
  overview2048x1024/921407B,200380416 RSS/150925312 scratch/0.29956s. Exact
  detail/center/onepixel/wide1280x960 oracles pass, reduced3000² crops pass,
  one transfer/map (361/181 chunks),11 successful measured renders. No limit raised.
- Live read-only audit passed23 calls/0.947s. All comparable browse/journal rows
  exactly match01 baseline structured/protocol bytes; catalog45/275617B versus
  baseline43/262218B (+13399B for2 tools), no response savings/token claim.
  Final large+live evaluation40 calls; including the earlier large verification,
  57 calls total, within80/20min. No live source/game fixture mutation.
- Added failure-accounting regression: failed info after discovery reported0
  instead of2 actual calls. Test failed first, aggregator now includes active
  workflow's dispatched calls/partial metrics, same unchanged test verifying.
  This is measurement harness behavior only; production unchanged, failed fixes0.
- Focused measurement6/workflow8/full regression checks now running. No need to
  repeat successful full-size/native or equal-content replay for error-accounting
  changes; small failure unit proves that branch and full hook will verify it.
- Final focused measurements6 pass1.461s/workflows8 pass4.087s, unchanged counter
  regression passes0.251s. Full ./scripts/test.sh passed899 Python (1 existing
  skip)/750JS,exit0. Full-size/native and live evidence retained in linked tables.
  No production change, game fixture or uncleaned temporary process/data remains.
- Commit5bae8bb completed after both hook suites passed,exit0.

## CurrentM01 checkpoint

- Task read fully; dependency01 b0cc01e committed.19/30 tasks,121/200 points
  (60.5%) complete. Map research and documentation workflow recovered; existing
  public journal hierarchy patterns and code graph read. Grounded Docs libraries
  foundry-vtt/pf2e-schema/pf2e-wiki available; find_version14 matches runtime14.369.
- Version14 searches and fresh official Folder/Scene/SceneData pages confirm
  public uuid, testUserPermission, toObject and schema folder/name/sort/sorting.
  Collection docs establish game.scenes. Finish field/collection/API evidence
  and bounded read-only pre-tool Scene baseline before changing production.
- Proposed boundary: authenticated core-only folder browse, separate module and
  strict models, public metadata relationships, no activation/canvas/PF2e logic.
  Bind pagination to trusted caller/world/GM plus metadata/permission revisions;
  budget10/8000B default,1–100/1024–48000B. Exact contract/tests next.
- Bounded baseline helper2 tests passed; actual read-only baseline2 MCP calls
  passed:50 Scenes/18 folders, root3 entries/367B, first-folder2/285B,45-tool/
  275617B catalog. Source parent relationships match6 serialized samples;
  active Scene unchanged. Doc index metadata refreshed by read-only CLI listing.
- Contract frozen in map-browsing.md. Production uses documented authorized
  toObject(true) metadata extraction to preserve unresolved stored parent IDs
  for orphan detection, discarding other fields; no linked body/file hydration.
  Added strict models, authenticated adapter, guarded browser RPC and initial
  hierarchy/filter/order/cursor/budget/denial tests. No live module refresh yet.
- Initial JS9:8 passed; shrinking catalog returned InvalidCursor instead of
  required ContentChanged because offset range was checked before revision.
  Move range check after unchanged-revision check; same regression now verifying.
  No unsuccessful correction attempts. Added permission-change-during-hash case.
- Public collection invalidDocumentIds was verified in fresh official docs.
  New empty-world omission test failed scope complete vs required partial;
  include invalid-record availability in revision/scope without exposing IDs.
  Same test passes; JS11/Python10 actual MCP+Node tests pass. No failed fixes.
- First full909 failed4 packaging checks: new mapBrowse.js import was absent
  from the explicit module archive allowlist. Root is packaging configuration,
  not Foundry behavior. Add focused archive assertion, observe failure, update
  allowlist, then rerun unchanged tests/full suite before browser verification.
- Focused archive test reproduced Unpackaged/external import failure; allowlist
  now includes mapBrowse.js. Same unchanged test and packaging4 verifying;
  required full suites repeated. No release/tag/push or new Foundry instance.
- Packaging4 passed. Next full910 exposed2 release-fixture guard failures:
  the new archive test added an unrelated hardcoded version tag outside the
  release helper's deliberate fixed-pin count. Removed that unnecessary new
  test argument (same archive assertions), preserving the release guard and all
  existing release expectations. No release helper/versions changed. Focused
  release/package and full tests verifying; this was test configuration, not a
  production versioning change or speculative behavior correction.
- Recovery reread all saved instructions/design/research/index/current task and
  required repository files. Previous goal turn made progress; the brief user
  strategy answer itself made no implementation progress. Existing full run is
  terminal:912 Python (1 existing skip)/761 JS passed; no process was restarted.
- Restarted existing Python service and refreshed dedicated development tab;
  readyGM14.369/console0. Actual `map_browse_audit --browse` passed26 calls within
  30/120s,46 tools/286687B catalog,50 Scenes/18 folders,4/12 duplicate names,
  complete scope and active Scene unchanged. No game writes/fixtures/cleanup.
- Actual `.venv/bin/python scripts/package-module.py` passed module3.3.1; no
  version bump/tag/publication. Contract/task include response-byte table and
  public API evidence. Final diff review and task commit next; no active defect
  or unsuccessful correction attempts.

## CurrentM02 checkpoint

- M01 e9ea43e and02 141ede6 dependencies committed;20/30 tasks,129/200 points
  (64.5%) complete. M01 hook passed both suites and the worktree was clean.
- Read complete M02 requirements. Grounded Docs list/find version14 and search
  plus fresh official Scene/Level/Grid/Tile/Dimensions and Base schema pages
  confirm adopted public serialization, getDimensions, embedded collections,
  Level background/foreground and Tile levels. No private transform helper or
  legacy Scene background is authorized as a substitute for explicit levels.
- Code graph module overviews read; CLI executable is absent but MCP works.
  Next bounded baseline will corroborate metadata shapes in14.369/test without
  exposing paths or altering active Scene. No M02 production implementation yet.
- Baseline helper `map_info_audit` tests2 passed; existing JS browse11 passed.
  Actual bounded baseline2 calls/120s passed:50 Scenes/50 levels/78 Tiles,
  48 backgrounds/14 foregrounds/2 empty levels; public source/embedded identities
  and finite scene rectangles agree; all8 grid/texture keys and Tile levels
  observed, active Scene unchanged,46 tools/286687B. No writes/raw identities.
- Frozen selected-map contract/API evidence saved in map-info.md before reader
  implementation. Tile null/empty membership stays explicitly unevaluated until
  M03 semantics are verified; no silent selected-level omissions/composition.
  Next action implement typed contracts and detached browser reader with tests.
- Added internal strict selected-map models and initial detached browser reader;
  no public registration yet. Python baseline/contracts6 pass. JS initial10:
  9 passed; signed-reference replacement expected ContentChanged but succeeded.
  Root: redacted public projection erased distinct authorized source metadata
  before hashing. Added private selected-source revision witnesses, never public
  response/log content; rerunning the same unchanged regression plus browse tests.
  Unsuccessful correction count0. Next adapter/actual MCP tests, packaging and
  full/runtime verification before M02 commit; task is not complete.
- Same signed-reference revision regression passes unchanged; JS21 combined.
  Added authenticated adapter/actual RPC registration and fixed packaging/smoke
  usage points; actual MCP+Node tests12 pass1.887s (discovery23489B).
  Initial fixture setup lacked main's manager registration and an edit misplaced
  baseline tests under MCP class; corrected fixture organization/import, leaving
  expectations unchanged. No production workaround or unsuccessful fix attempt.
- Two further focused failures demonstrated: encoded dot segments normalized
  away before source-hint checks; forged browser safe status admitted signed/
  credential-bearing source hints in Python. Correct raw-segment checks before
  normalization and independent typed-response path/privacy validation, then
  rerun unchanged tests. No raw references should enter public diagnostics.
- Those unchanged regressions pass; Python13/JS22 passed. First full925 Python
  (1 existing skip)/772 JS passed; two new runtime-verifier tests later pass,
  Python15. Existing service restart/refresh readinessGM14.369/console0.
- Actual selected-map verifier failed at first read (call3), public MapReadFailed.
  Diagnostic allowlist first lacked that category (one unsuccessful diagnostic
  adjustment); fixed categorization identifies browser layer. Deeper fixed
  handler diagnostic initially had JS newline escaping error, corrected and
  unit-tested parser/privacy before invocation. It then captured TypeError at
  mapInfo.js110/mapBrowse.js13, exactly reproduced by own undefined optional
  Tile name. Same focused test fails Array.from(undefined), matching live stack.
- Correct Tile name omission and optional primitive pick for own undefined;
  unchanged regression and JS25 now verifying. Production correction first
  attempt; no swallowed errors, guessed defaults or changed assertions. Refresh
  dedicated tab and retry bounded read to verify this demonstrated cause.
- Live retry passed7 calls/2 representative maps: assets1/tiles2 and assets1/
  tiles1, every stream complete, same revision across sections, active Scene
  unchanged. Catalog47/310184B, tool23496B. No game writes. Final review also
  proved merged texture.rotation overwrote Tile rotation: new unchanged test
  failed90 vs15; separate texture_rotation projection/model corrects it.
  JS26 combined passes, Python16/full suites verifying. No unsuccessful fix.
- Public TextureData page documents SchemaField/fields/keys rather than named
  transform semantics. A bounded public-schema diagnostic checks exact declared
  Tile texture keys without adopting a transform algorithm; M03 mapping gates
  remain separate. Final refresh/live/package/diff/commit still outstanding.
- Optional own-undefined media src shared the absence distinction: focused test
  failed unsupported vs missing and inflated reference count; skip undefined
  before classification, same unchanged test passes in JS27 combined. Final
  full/hook will include this correction. Python16 passes, concrete recovery
  now correctly names get_map_info rather than sibling browse_maps.
- Final native read7 calls passes after restart/readyGM/console0:47 tools/
  310520B catalog and23832B tool record (before narrowing unsupported Tile fields).
  Diagnostic full-result JSON initially hit the existing exploration1000-char
  per-string clip, identified in exploration.js; compact success summary now
  passes its unit/privacy/parser checks and actual1-call handler/schema probe.
- Public TileDocument.schema.getField('texture').keys() confirms only anchors,
  scale,fit,src among proposed fields; Tile texture rotation/offsets are NOT
  declared. Removed those public fields rather than depend on unsupported data.
  Placement rotation remains15 in the proven collision regression; expected
  texture output changed explicitly due to newly verified public schema contract,
  not to make a failing correction pass. M03 Level transforms remain gated.
- Final full runner passed928 Python (1 existing skip)/777 JS before schema
  narrowing; final focused/hook will verify final declarations. No game fixtures
  or asset writes; existing browse/selected-map native workflows passed.
- Final Python17/JS27 focused passes; module packaging3.3.1 passes. Existing
  service restarted, dedicated tab refreshed and readiness/console0 confirmed.
  Final actual selected-map read7 calls passes,47/309786B catalog,23098B tool
  record. Assets/Tile result bytes unchanged by schema narrowing. All native
  streams complete, metadata revisions agree, active Scene unchanged.
- Public/operator/module architecture/task evidence updated; final diff review
  and required two-suite hook/local commit next. No active diagnosis/cleanup.
- M02 af58e0d committed after both hook suites passed,777 JS. Working tree
  clean before next-task checkpoints; no publication or game mutation.

## CurrentM03a checkpoint

- Dependency M02 af58e0d committed;21/30 tasks,137/200 points (68.5%) complete.
  Read current task fully. Grounded Docs fresh NoteDocument/BaseNote pages
  establish public label/entry/page getters, permissions/serialization and the
  levels schema field. SceneLevelsSetField describes nullable specific-level
  references but not empty/null applicability. No unsupported internal helper
  will be adopted. Official Scene knowledge-base page is older than level
  implementation; matching runtime major docs alone do not settle semantics.
- Need bounded baseline and exact note projection/legend contract. Aliases
  must use complete authorized applicable-level UUID order before filtering;
  permissions must precede labels and linked body reads remain excluded.
  No M03a production change yet; baseline/research is next.
- Added unit-tested bounded note baseline helper; focused test_map_notes.py2
  pass. Actual2-call/120s baseline passed:47 tools/309786B,483 authorized notes
  across50 Scenes, all483 source levels empty, all finite coordinates and linked
  readable entries,208 text overrides. No null/omitted/explicit membership, denied
  or missing linked entries. Static public schema label/hint absent. Active Scene
  unchanged; no raw labels/IDs/body content returned or game mutations.
- Empty-set applicability is therefore a substantive normal-workflow gate,
  not an edge case to dismiss. Investigate authoritative field semantics and
  focused runtime evidence before choosing production behavior. No failed
  diagnosis/fix attempt or M03a production edit; remaining index/progress docs
  and baseline helper/tests are uncommitted M03a work.
- Root public applicability API found: official CanvasDocumentMixin returns
  foundry.CanvasDocument, whose public includedInLevel(level|string) is documented
  without private/protected/internal annotations. NoteDocument generated page
  incorrectly advertises only ClientDocumentMixin; installed note.mjs explicitly
  extends CanvasDocumentMixin(BaseNote). Public API plus installed source reconcile
  this documentation omission; do not call viewed/private canvas internals.
- Read-only installed CanvasDocument source explains empty levels return true,
  explicit levels use selected ID; no production dependency on its internals.
  Added bounded1-call public-constructor/member verifier with3 unit tests total.
  Actual14.369 check passes: unpersisted marked Note documents for empty/null/
  explicit-own level all included, foreign level excluded. Supplied null cleans
  to non-null source.10 existing empty-set notes in sampled owning Scene all
  included. Collection size/active Scene unchanged;0 persisted fixtures.
- Next: freeze exact legend DTO/label-target permission/revision contract, then
  implement public includedInLevel admission and bounded candidates. Normal empty
  membership is now supported by a documented public query, not inferred rules.
- Froze DTO/key filters/selected-level revisions and internal candidate limits
  in map-note-identities.md before implementation. Independent Note projection
  JS6 passes, including denied getter traps, missing/unlinked/page identities,
  clipped malicious labels and duplicate pins. Integrated notes into typed
  selected-map boundary and shared metadata revisions; existing info17/JS33
  regression checks pass. M02 tests intentionally update revision expectations
  for exact-level identity binding documented in the new contract.
- Actual MCP+production Node legend tests pass (initial17 included8 imported
  helper tests already owned by M02; removed duplicate test discovery). New tests
  exercise complete20-note pagination, filtered aliases, changed labels/levels,
  denied targets, typed discovery and exact configured3000-byte candidate frames.
  Normal candidate pages never exceed100/48000 and insufficient1024 frame fails
  before RPC. No M03 runtime refresh/full suite/commit yet.
- Added focused forged-alias ordinal regression for a one-entry unfiltered
  page; observing expected failure before enforcing ordinal/offset consistency.
  Current diagnosis stage, unsuccessful correction count0.
- Forged unfiltered alias N999 at offset0 was accepted on a one-entry page;
  focused unit failed before correction. Exact offset+row ordinal validation
  now makes the unchanged test pass. Final focused notes13 pass3.885s, existing
  info17 and JS33 pass. First full939 Python (1 existing skip)/783 JS passes;
  later tests add internal missing-revision guard/model/privacy/legend checks.
- Bounded unit-tested native legend harness follows actual notes pagination,
  exact-key lookup and expanded equal-content reading without printing IDs or
  labels; focused harness exercises the actual MCP/production Node reader.
  Existing service restart/module packaging/native refresh verification next.
- Final full942 Python (1 existing skip)/783 JS passes, notes13/info17/JS33
  focused pass. Module packaging passes. Existing-service restart/dedicated
  refresh readinessGM14.369/console0; actual native legend9 calls passes21 notes/
  3 pages, exact2-key identity lookup and equal-content expanded page. Active
  Scene unchanged and complete scope;47 tools/314317B catalog,27629B record.
  All stream bytes/table and public applicability evidence in identity guide.
- Installed package version14.369.0 confirms source/browser match despite older
  container image label. Public method avoids guessing empty/null membership.
  No persisted runtime fixtures or game assets/documents changed; no cleanup.
- Code graph get_map_info impact/reference review confirms internal candidate
  entry point and dynamic MCP registry; exact RPC searches and Node/mock usages
  updated. Final diff/whitespace and commit hook next; no active failure or
  unsuccessful correction attempt. Geometry/overlays remain separate tasks.
- Commit26bb4e6 completed after both hook suites passed; clean worktree before
  next-task checkpoint. No publication or uncleaned persisted game fixture.

## CurrentM03b checkpoint

- Dependencies M03a26bb4e6/06a49e8aaf committed;22/30 tasks,142/200 points
  (71%) complete. Current task read fully. Source snapshots currently pin only
  original bytes/principal/browser context; M05 attaches map state, so this task
  defines immutable private geometry/context/revalidation helpers first.
- Grounded Docs official LevelData/LevelTexture/TextureData and SceneDimensions/
  public getDimensions revisited. Level page incorrectly says BaseTile in prose,
  but hierarchy shows BaseLevel. Do not infer arbitrary image transforms from
  mesh/private configuration or field-name intuition.
- Installed14.369 public getDimensions implementation corroborates sceneX/Y
  already subtract Scene shiftX/Y after grid padding calculation; production
  must consume its returned rectangle and never apply shift twice.
- Investigate public DataField getInitialValue(source)/clean and declared
  Level.textures source schema defaults to establish a default-placement subset
  without adopting undocumented individual texture properties just for guards.
  No M03b source implementation or new runtime probe yet. Next freeze supported
  mapping/immutable alias-witness/candidate interface with independent tests.
- Added baseline helper/tests2 pass. Actual2 calls/120s:47 tools/314317B,
  all50 Level.textures values match public schema cleaned defaults. Public
  unpersisted Scene constructors confirm normal6800x9000 origin1800/2400,
  shift120/-80 moves origin1680/2480, smaller3400x4500 origin1000/1200.
  Active Scene/collection unchanged,0 persisted fixtures. All initial/cleaned
  values are objects; no arbitrary texture-field detection is required.
- Saved map-context.md before implementation: default whole-schema placement
  subset on14.369, private reference/canonical-source+revision/alias proofs,
  frozen source-bound context and crop-filtered bounded candidate RPCs. M05
  owns cache attachment/public selectors; no public image signature change here.
- Pure Python mapping4/baseline2 and JS geometry4/notes6 pass. Added private
  context/crop-candidate readers, frozen Python resolution/source-bound records,
  revalidation coordinator and private typed DTOs; no public image API changes.
- Initial private JS6 failed because new external fixture omitted documented
  FilePicker.implementation wrapper used by existing resolver. Corrected the
  fixture to the established public API shape, not production behavior; unchanged
  tests now verifying. Source/reference mutation, typed unsupported placement,
  exact crop/frame bounds and async final-hash mutation are covered.
- Next add SourceSnapshots/real-byte/native-orientation context tests, validate
  private protocol/schema/error behavior, run full/package/runtime checks and
  commit M03b. Current stage implementation; no production defect/fix attempts.
- JS private geometry/context16 passed after fixture correction. Python context
  initial13:12 pass, changed bound asset reference to a missing new file returns
  ImageNotFound instead of MapContextChanged. Failing unit proves resolver runs
  before original reference comparison on ordinary revalidation. Add pinned
  expected_reference_digest to private request and compare before picker lookup;
  same unchanged unit rerunning. No unsuccessful correction attempts.
- Existing SourceSnapshots/actual file tests cover one-transfer crop reuse,
  caller/socket/expiry rejection before metadata reads, unchanged-path replacement
  bytes,150-pin limit reporting and N101 detail aliases. Native independent Pillow
  oracle plus real worker probes/crops pass all8 display orientations. No public
  image signature, game assets or persisted fixture changes.
- Expected-reference guard fixes the unchanged bound-asset test; Python13 pass
  6.570s. JS17 passes including before-picker expected-reference rejection.
- Two further focused failures proved: empty crop{} wrongly selected full image
  via truthiness fallback, and malformed private cursor escaped as raw binascii
  error. Use None-only default and fixed InvalidFoundryResponse cursor boundary;
  same unchanged tests now rerun with full context/regression suites. Both first
  corrections, unsuccessful count0. Added forged pose and actual2000-byte frame
  reply checks; no arbitrary payload-limit increase or weakened assertion.
- Same regressions pass; context17 passed9.246s, private JS17 passed. First full
  runner959 Python (1 existing skip)/794 JS passed. Native eight-orientation
  pixels and actual2000-byte browser replies are included in these tests.
- Added a bounded6-call/600s native verifier using authenticated development
  RPC + real module dispatch, public assets follow-up and existing source-info
  staging/probe. It measures context/region geometry against actual decoded
  dimensions and a one-pixel detail without publishing private context or URLs.
  Source-cache attachment to public map image inputs remains M05 by design.
  Verifier unit assertions/final native refresh/readiness execution next.
- Final focused context21 passes11.904s; JS geometry/context11+notes6 passes17.
  Direct final full961 Python (1 existing skip)/794 JS passes; two subsequent
  moved/missing/denied/renumbered-note and duplicate-path/changed-socket cases
  pass in focused21, and final commit hook will check both full suites.
- Actual native verifier6 calls/600s passes real6800x9000 source4405816B,25
  candidates, independently mapped coordinates and one-pixel detail same alias.
  Context1034B/candidates4298B/detail1357B handler-result sizes, not direct live
  private GM frame measurements. Catalog unchanged47/314317B; browser readyGM
  14.369/test/console0, active Scene unchanged. Module packaging3.3.1 passes.
- Native info staged one normal private original retained for1800s by SourceRuntime;
  no game fixtures/assets/public URLs or extra instances. M05 owns actual public
  map-source attachment; no foundation stub/tool signature change here. Final
  support matrix and evidence in map-context.md; diff/commit next, no active
  failure or unsuccessful correction attempts.
