# Private browser source fetch — task 03a

`imagePreviewFetch.js` exports the production `previewSourceFetch` singleton and
`createPreviewFetchService` for deterministic tests. It adds no RPC or MCP tool.
Task03b consumes this lease interface and wires cancellation to socket teardown.

`begin({image}|{src}, {isCurrent,signal})` reserves the sole browser-original
slot before awaiting the existing source resolver. It captures the original
world/GM object and rechecks it, readiness and exact socket ownership across
every await. Local fetch uses `mode:same-origin, credentials:same-origin`; S3
uses `mode:cors, credentials:omit`. Both use `redirect:error, cache:no-store`.
Any redirect, foreign final URL, non200 response or missing stream is rejected.
No arbitrary URL or extra Foundry API is introduced; source/API evidence remains
in [source resolution](source-resolution.md).

The service rejects declared sizes above128 MiB, counts every streamed byte,
and always enforces the actual128-MiB limit, including without Content-Length.
For identity HTTP encoding it also requires exact declared length. Browser fetch
decompresses HTTP content encoding, so gzip/br wire length is not compared with
the exposed file bytes. The actual exposed-byte cap applies regardless. HTTP
header hints never establish image MIME or dimensions; task05a owns probing.

Each source read/await is bounded to15 seconds. The total300-second lifetime
starts before resolution and includes fetch and retained lease time. Owner
abort, failure, timeout or explicit release drops the Blob/buffers, cancels the
reader, aborts fetch, removes abort listeners and clears timers. Native messages,
URLs, credentials, bytes and stacks never enter diagnostic errors.

Successful begin returns a frozen private lease:

- `context`: frozen exact selected image, fetch target/credential policy and
  world/GM identity, with source-coverage limitations where applicable. This
  object is private; task03b publishes only its selected protocol fields.
- `size_bytes`: actual snapshot length; `deadline`: absolute transfer deadline
  in browser clock milliseconds, not public preview/source-handle expiry.
- `read(offset,length)`: asynchronous copied Uint8Array, integer contained range,
  positive length<=32,768. Invalid reads release the original. The private Blob
  snapshots stream buffers, including streams that later reuse their arrays.
- `release()`: idempotent; stale leases cannot release replacement owners.

Only the boolean service `busy` status is exposed for admission/cleanup checks.
Resource bounds/clocks/timers are injectable at factory creation for tests;
production defaults are frozen and independent of upload/PDF services. Codecs,
frame layout, hashing and caller handles belong to later tasks.

## Verification

Focused `node --test tests/js/image-preview-fetch.test.js tests/js/journal-images.test.js`
passed19 tests. Tests cover immutable copied reads, stream-buffer reuse, absent/
dishonest lengths, overflow, local/S3 credential policy, redirect rejection,
concurrent admission, authorization changes, abort at each phase, exact timeout
boundaries, invalid bounds, secret-free errors and timer/reader cleanup.

The explicit module allowlist includes the service. A real ZIP assertion first
failed because the new file was absent; adding its allowlist entry made the
unchanged assertion pass. `.venv/bin/python -m unittest discover -s tests -p
'test_packaging.py' -v` passed3 tests. A focused HTTP-gzip fixture also failed
before correcting wire-length comparison, then passed unchanged afterwards.
No assertions/limits were weakened; unsuccessful correction counts are zero.

After offline checks and dedicated refresh, the existing test-world GM on
Foundry14.369 reported ready and zero console errors. The extended bounded
`scripts/image-preview-sources-live-check.py` passed in one MCP development
invocation: canonical/bare/absolute public SVG selection, real browser streaming,
copy-mutation isolation and release (`busy:false`). No game assets or documents
were modified; no fixtures or cleanup remain. Its Python privacy test passed.
The first full run overlapped addition of the failing HTTP-encoding regression
and reported one JavaScript failure; final regression evidence is recorded in
the task completion/progress record after all corrections.

Live S3 is pending a configured readable bucket with appropriate CORS; mock
coverage establishes credential and selection policy only. Public HTTPS/target
ChatGPT acceptance and large-map resource measurements remain downstream gates.
