# 04a — Python transfer assembly

Points: **8** — concurrent chunk validation, socket correlation, and failure cleanup.
Split from original task 04, estimated at 13 points.

Dependencies: [03b](03b-chunk-protocol-and-lifecycle.md).
Intended commit: `feat(images): assemble bounded browser transfers in private files`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read 03b's wire contract, `ws/connection.py`, and current image-upload RPC owner
checks. This task produces complete private files; 04b adds persistent handles
within the process and caller identity policy.

## Implementation and interfaces

- Add an internal transfer service that captures the exact GM socket/world/user
  before begin and verifies ownership across every await. Pull indexed chunks
  with at most 16 in flight, at most 32 KiB raw each, fitting configured frames.
  Enforce 15 seconds per stalled read and 5 minutes for the full transfer.
- Validate base64, transfer identity, index, offset, declared/raw length,
  source size <=128 MiB, uniqueness, and exact final coverage. Accept verified
  out-of-order replies; reject gaps, overlap, duplicate or short data. Assemble
  into a private temporary file and hash the verified complete source.
- Return only an internal complete file, digest, canonical selector, and captured
  world/GM/socket context with explicit file-ownership handoff to 04b. It is not
  a public response, source handle, or MCP tool.
- Cancel/drain pending calls and release browser state on success, failure,
  timeout, cancellation, or connection change. Remove partial files; cleanup
  must not use the replacement GM socket. Bound errors and never log bytes,
  credentials, private paths, signed source URLs, or source digests.

## Tests and acceptance

Add `tests/test_image_preview_transfer.py`. Use real bytes across multiple
chunks and controlled sockets/timers. Cover bounded in-flight calls, correct
hash/reconstruction, out-of-order success, short/missing/duplicate/overlap data,
invalid base64/size/envelope fields, timeout, cancellation, reconnect, changed
world/GM, and every cleanup path. Prove incomplete files cannot be handed off
and stale cleanup cannot release a new transfer. No decoder or source-cache
implementation is needed to pass these tests.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_transfer.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_connection.py' -v
./scripts/test.sh
```

Accept when complete-byte/file ownership and faults are independently verified.
Commit service, tests, and private transfer contract together.

## Completion record

- Implementation: complete; strict private packet validation, bounded verified
  file/hash assembly, explicit ownership and pre-begin identity/reservation.
- Dependency commit SHA(s):03b `647c42b`.
- Commit: this commit.
- Focused outside sandbox:10 assembly Python tests,6 connection tests,10 JS
  transfer tests and1 probe-privacy test passed. Full `./scripts/test.sh` passed
 720 Python tests (1existing skip) and749 JavaScript tests.
- Contract/diagnosis evidence: [Python assembly](../python-assembly.md); cancelled
  cleanup regression failed before correction, passed unchanged afterwards.
- Runtime: refreshed ready14.369 test-world GM, consoleerrors0; browser context/
  reservation and5-chunk reverse dispatch passed (max534 bytes under1024).
  Actual Python assembly through the running GM socket awaits task10's production
  entry point and12a integration; no test-only public endpoint was introduced.
  Live S3 requires a configured readable bucket/CORS. No game mutations.
