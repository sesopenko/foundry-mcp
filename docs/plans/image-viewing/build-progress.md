# Image viewing build progress

- Current task: 05b, [worker resource supervision](tasks/05b-worker-resource-supervision.md).
- Stage: commit.
- Last completed task: 05a, commit `57123ce`.
- Persistent goal remains active. Its environment objective points to the attachment containing the full goal, read at kickoff; the complete assignment is preserved in the [execution prompt](../../prompts/foundry-image-viewing-build-agent.md).
- Next action: commit verified05b with its hook, then resume06a geometry from its complete task file. No active failure; historical failed-attempt count3 is preserved. No unsuccessful production correction since user authorized resumption.

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
