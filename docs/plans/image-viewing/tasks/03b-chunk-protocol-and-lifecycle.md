# 03b — Browser chunk protocol and lifecycle

Points: **5** — bounded RPC framing and lifecycle over the tested fetch service.
Split from original task 03, estimated at 13 points.

Dependencies: [03a](03a-browser-source-fetch.md).
Intended commit: `feat(images): expose private bounded transfer RPCs`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the existing bridge socket guard/dispatch, Python frame enforcement, and
03a's private fetch interface. PDF chunking is a precedent with separate auth.

## Implementation and interfaces

- Register private `beginImagePreviewTransfer`, `readImagePreviewChunk`, and
  `releaseImagePreviewTransfer` in `foundryBridge.js`; pass `isCurrent` to each
  async handler. These RPCs must not become MCP tools. Begin calls 03a once and
  retains at most one immutable original; return opaque transfer ID, size,
  chunk layout, and canonical selection/context privately, without source bytes.
- Indexed replies carry transfer ID, index, offset, raw length, and base64
  data. Limit raw chunks to 32 KiB and in-flight window to at most 16. Fit the
  configured response ceiling, including actual JSON/RPC-ID/base64 overhead
  (65,536-byte default); reject ceilings too small for a valid frame.
- Validate ownership, indices, offsets, and lengths. Freeze begin/chunk/release
  wire contracts in tests for 04a. Same socket/world/GM must own each operation
  across awaits. Hold the 5-minute total deadline from begin, including fetch;
  use 15-second stalled-read bounds. Release idempotently on explicit release,
  success, error, timeout, cancellation, disconnect, or world/owner change.
- Stale callbacks/releases must not touch a replacement owner's state. Abort
  the fetch through 03a's owner signal; drop timers and buffers on every exit.
  Keep bytes, credentials, paths, and signed URLs out of diagnostics.

## Tests and acceptance

Add `tests/js/image-preview-transfer.test.js` with actual bridge dispatch tests:
real multichunk reconstruction, exact frame sizes at configurable ceilings,
malformed indices/offsets/lengths, window bounds, non-GM access, concurrent begin,
frozen bytes, socket/world/GM changes during awaits, disconnect, expiry, repeated
release, and stale callbacks. Assert buffers/timers/readers are cleaned and no
private information is logged. Reuse fetch tests rather than retesting all codecs.

Run outside the sandbox:

```bash
node --test tests/js/image-preview-transfer.test.js tests/js/image-preview-fetch.test.js tests/js/bridge.test.js tests/js/authentication.test.js tests/js/main.test.js
./scripts/test.sh
```

Accept when the private protocol is documented and dispatch/framing/cleanup
tests pass. Refresh the dedicated browser and inspect readiness/console per
the development-loop skill when available. Commit RPCs, tests, and wire docs.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, frame/window measurements: not run.
- Browser evidence and exact pending prerequisites: pending.
