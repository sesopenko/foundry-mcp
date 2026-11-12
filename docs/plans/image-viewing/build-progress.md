# Image viewing build progress

- Current task: 05a, [decoder probe and packaging](tasks/05a-decoder-probe-and-packaging.md).
- Stage: commit.
- Last completed task: 04b, commit `a045d08`.
- Persistent goal remains active. Its environment objective points to the attachment containing the full goal, read at kickoff; the complete assignment is preserved in the [execution prompt](../../prompts/foundry-image-viewing-build-agent.md).
- Next action: commit05a, then read/baseline05b worker resource supervision. No active failure or mandatory stop condition.

## Completed checkpoints

| Task | Local commit | Full/hook outcome |
| --- | --- | --- |
|01 contracts/baseline | b0cc01e |709 Python (1 existing skip),717 JS passed |
|02 source resolution |141ede6 |710 Python (1 skip),728 JS passed |
|03a browser fetch |e4121a4 |710 Python (1 skip),739 JS passed |
|03b private RPC protocol |647c42b |710 Python (1 skip),748 JS passed |
|04a Python assembly |fe47d21 |720 Python (1 skip),749 JS passed |
|04b snapshots/identity |a045d08 |733 Python (1 skip),749 JS passed |

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
