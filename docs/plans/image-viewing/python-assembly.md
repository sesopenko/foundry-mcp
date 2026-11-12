# Private Python original assembly — task 04a

`image_preview_transfer.stage_original(manager,request,...)` accepts the strict
base image/src request and returns a complete `StagedOriginal`. It registers no
MCP tool and retains no source-handle cache. Task04b owns caller-bound handles.

The service captures the current GM socket, calls the private ready-GM context
RPC before begin, and supplies its own cryptographic UUIDv4 reservation plus
expected world/GM IDs. This [protocol extension](transfer-protocol.md) is needed
because existing version metadata carries no world/GM identity, and cleanup
must know a transfer ID even if begin is pending or its response is malformed.
The browser captures and checks the same identity before/after fetch; Python
rejects mismatched context, reservation or canonical selector.

The configured frame ceiling is passed to begin. Strict Pydantic models validate
private metadata and every chunk; bounds are128 MiB source,32 KiB raw/chunk,
at most16 in flight,15 seconds per read and300 seconds total. Begin may stream
for the total deadline while individual source reads remain browser-bounded.
Each packet must match its originating index/offset/exact length/reservation;
base64 must be valid and canonical and decode to exactly that length. Count and
layout must agree. Extra fields and booleans/floats are rejected.

Responses may arrive out of order. Each batch holds at most16 chunks; verified
bytes are written/hashed in index order without a whole-source Python buffer.
The service creates a unique700 directory and600 original file, validates final
coverage/length, and returns:

- `path`, `directory`, `sha256`, `size_bytes`: private owned file/digest metadata.
- `context`: exact socket, world/GM IDs, canonical ImageSelector, and source
  coverage status/limitations. None of these are public tool output.
- `close()` and context-manager support: caller-owned deletion, idempotent.

The caller must close the object or explicitly transfer ownership to the04b
cache. Incomplete files never hand off. Failure/cancellation cancels and drains
pending reads, removes partial files and attempts a bounded3-second release on
the original socket only. A replacement socket is never used for cleanup.
Remote cleanup may be impossible after disconnect; browser close/complete
coverage/absolute deadline independently release its original. Native errors,
private paths, signed URLs, base64 and digests are not logged or reflected.

## Verification and diagnoses

Focused outside-sandbox checks:

- `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_transfer.py' -v`:10 passed, covering actual multichunk bytes/hash,16-read batches,
  out-of-order responses, real FoundryConnectionManager correlation, malformed
  metadata/base64/short/duplicate/overlap fields, exact permissions, timeout,
  cancellation at read/begin/release, source context errors and replacement socket.
- `.venv/bin/python -m unittest discover -s tests -p 'test_connection.py' -v`:6 passed.
- `node --test tests/js/image-preview-transfer.test.js`:10 passed including
  pre-begin context, known reservation and cancellation while begin is pending.

The cancellation-during-release test first failed because cleanup swallowed
CancelledError after marking the file handed off. Propagating cancellation and
removing the unreturned file made that same test pass. Unsuccessful corrections0.
Two test-harness mistakes were separate: selector comparison used default
model_dump rather than the established exclude_none representation; responder
accounting relied on a queued done callback. A gather of already-finished tasks
did not drain that callback (one unsuccessful harness adjustment). Moving registry
removal into the responder's finally made the unchanged empty-registry assertion
pass. Production correlation was unchanged; no retry/limit increase/assertion
weakening was used. No active diagnosis remains.

The extended existing browser probe verifies the context/reservation handshake
and browser-side multichunk reconstruction after module refresh, without sending
bytes through MCP. Actual Python assembly against the running browser socket is
pending the first production image-tool entry point in task10 and end-to-end
integration in12a; no temporary public test endpoint/stub was introduced.
Unit tests already exercise the real connection manager with correlated socket
responses. S3 requires a configured readable bucket/CORS; external visual
acceptance remains downstream. Final full-suite/runtime results are recorded in
the task completion/progress record.
