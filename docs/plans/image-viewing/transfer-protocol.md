# Private image transfer protocol — task 03b

These are browser WebSocket RPCs, **not MCP tools**. Python issues them through
the existing authenticated, exact-socket-correlated connection manager. Bytes,
selectors, signed URLs and native diagnostics must never enter MCP output/logs.
No PDF credentials/channel authorization are reused. Foundry public dependencies
are unchanged from [source resolution](source-resolution.md); processing uses
standard browser APIs and the [private fetch lease](source-fetch.md).

## Begin

`beginImagePreviewTransfer` takes exactly one `image` or `src`, plus optional
`max_frame_bytes` (default65,536; integer1,024–16,777,216). This is the configured
server response ceiling, not an arbitrary enlargement of the server's limit.
RPC IDs must be nonempty strings of at most512 serialized JSON UTF-8 bytes.

Task04a adds `getImagePreviewContext({})` (private, no MCP tool), returning
`world_id,user_id` for the ready current GM before begin. Python always supplies
these as begin `expected_context:{world_id,user_id}`, checked before fetch and
against the resulting lease. It also supplies a fresh UUIDv4 `transfer_id`
reservation; browser-generated IDs remain the default for internal callers
omitting it. A known reservation permits release during a pending begin or after
a lost/malformed begin result. Never reuse reservation IDs. These additions use
public game world/user identity only and preserve socket/world/GM guards.

The private result fields are:

- `transfer_id`: fresh cryptographic UUIDv4; not a caller-bound source handle.
- `size_bytes`: actual original snapshot bytes,1–134,217,728.
- `chunk_bytes`: negotiated raw chunk extent,1–32,768.
- `chunk_count`: ceiling(size_bytes/chunk_bytes).
- `max_in_flight`:16, maximum simultaneous reads.
- `world_id`, `user_id`, `image`: exact private source context for Python's checks.
- `scope_status`, `limitations`: complete/partial listing coverage from resolution,
  never a claim that unavailable sources contain no matching file.

One transfer reserves the slot before its initial await. Busy prevents another
begin. The original is fetched once, snapshot bytes are immutable, and the
five-minute deadline includes begin/resolution/fetch/retention. The service
negotiates chunk size using worst-case index/offset/length, base64, UUID and
512-byte serialized RPC-ID overhead, then checks every actual response envelope.
If even begin metadata exceeds the ceiling, ResponseTooLarge releases the lease.

## Read and release

`readImagePreviewChunk` requires `transfer_id`, zero-based integer `index`,
integer `offset=index*chunk_bytes` and exact positive `length` (chunk_bytes except
the final remainder). No duplicates, floats, booleans or extra fields. Response:
`{transfer_id,index,offset,length,data_base64}`. Decoding must yield exactly length
bytes. Python must validate all fields, complete coverage and final digest; it
must never construct offsets from an unvalidated response.

Requests may complete out of order. At most16 are in flight; the17th fails and
releases the identified original. Successful coverage of every chunk releases
the original automatically. Cancellation and15-second source/read stalls are
handled by the fetch service. A five-minute timer also clears protocol state.

`releaseImagePreviewTransfer({transfer_id})` returns `{released:true}` for a live
owned transfer, `{released:false}` for an already-released/stale ID. Cleanup is
idempotent. Malformed commands release only an exactly identified owner transfer;
foreign IDs/owners cannot clear another owner's state. InvalidChunk, changed
context, timeouts and processing failures release retained state.

The bridge passes its exact socket object and `isCurrent` guard through dispatch.
Close, manual disconnect, replacement and reconnect abort only that socket's
transfer. Old close callbacks, replies and releases cannot affect a replacement.
World/GM/readiness are rechecked across awaits. A late begin completion must
release its own lease even if its protocol state was already closed. No new
Foundry instance, world mutation or authentication relaxation is involved.

## Verification

Focused command:
`node --test tests/js/image-preview-transfer.test.js tests/js/image-preview-fetch.test.js tests/js/bridge.test.js tests/js/authentication.test.js tests/js/main.test.js`
passed37 tests outside sandbox. Protocol tests reconstruct100,000 deterministic
bytes in four default chunks out of order; check every actual frame at1,024,
2,048,4,096 and65,536-byte ceilings with512-byte serialized IDs; and exercise
the16-read window, malformed fields, concurrency, owner isolation, expiry,
repeated release and actual mock-socket disconnect/stale-event integration.
Python packaging/probe-privacy checks also passed.

Two cleanup defects were demonstrated before correction with failing assertions:
late returned leases skipped release after an earlier close; malformed fields
were rejected before entering identified-transfer cleanup. Their unchanged tests
passed after correcting cleanup. No retry, weakened expectation or limit change
was used. Unsuccessful correction counts are zero.

After focused tests and dedicated refresh, the existing14.369 test-world GM
browser passed the read-only probe. Core SVG bytes were dispatched in **5 chunks**
in reverse order at a1,024-byte negotiated ceiling; maximum actual envelope was
**534 bytes**, and reconstructed SHA-256 matched the independent immutable lease.
The probe ran inside the browser via one MCP development invocation; only fixed
summary/aggregate metrics crossed MCP. This is live browser/dispatch evidence,
not yet actual Python source assembly over the socket (04a and tool integration
own that evidence). Console errors were0 before and after. No game assets or
documents were modified, and no fixture/cleanup remains.

Live S3 requires a configured browser-readable bucket/CORS; external HTTPS/target
client acceptance remains downstream. Full-suite/commit evidence is recorded in
the task and durable progress record.
