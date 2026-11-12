# 03a — Bounded browser source fetch

Points: **8** — streaming limits, credential/redirect policy, and ownership across awaits.
Split from original task 03, estimated at 13 points.

Dependencies: [02](02-browser-source-resolution.md).
Intended commit: `feat(images): fetch bounded immutable preview sources in the browser`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the transfer requirements and current bridge dispatch/socket-owner guard,
`imageUploads.js`, `pdfChannel.js`, and Python connection frame enforcement.
The PDF channel is a protocol precedent, not reusable authorization.

## Implementation and interfaces

- Add a dedicated internal browser source-fetch service. Consume task 02's
  resolver and the bridge's `isCurrent` owner guard; return immutable private
  bytes plus canonical source/world/GM context. Do not register transfer RPCs
  yet: [03b](03b-chunk-protocol-and-lifecycle.md) owns the wire protocol.
- Begin resolves task 02's selector/reference, streams selected bytes with a
  128-MiB compressed limit, and holds at most one bounded immutable transfer
  original in the browser. Count received bytes even without Content-Length;
  reject an excessive declared size early and excessive actual bytes always.
  Retain size, selector, and world/GM context privately. Bytes remain inside
  this internal service and never enter MCP results or logs.
- Local assets use same-origin browser credentials; configured S3 uses exact
  picker-selected objects, CORS, and omitted Foundry credentials. Do not fetch
  unrelated URLs or follow off-source redirects. Use standard browser APIs;
  do not read Foundry's host filesystem or private publisher state.
- Recheck same socket/world/GM across every await. Bound stalled reads to
  15 seconds and the fetch to the 5-minute total transfer deadline. Accept an
  owner cancellation signal so 03b can release state on socket closure or
  explicit release. Abort readers/remove partial buffers on error, timeout,
  cancellation, world or owner change. Never log private source information.

## Tests and acceptance

Add `tests/js/image-preview-fetch.test.js`. Test streamed bytes, absent/dishonest
Content-Length, streamed overflow, same-origin and S3 credentials, off-source
redirects, concurrent fetch admission, immutable bytes, non-GM access, changed
socket/world/GM during fetch, owner cancellation, and stalled/total timers.
Assert readers/partial buffers/timers are released on failure and private source
information is absent from captured errors/logs. Use controlled deadlines.

Run outside the sandbox:

```bash
node --test tests/js/image-preview-fetch.test.js tests/js/journal-images.test.js
./scripts/test.sh
```

Accept when fetch limits, credentials, and cancellation are independently tested
and the private result/owner-signal interface is documented for 03b. Commit the
service, tests, and source-fetch documentation. Refresh/console-check the module
using the development-loop skill when the dedicated browser is available.

## Completion record

- Implementation: complete; internal private lease service only, no transfer RPCs.
- Dependency commit SHA(s): 02 `141ede6`.
- Commit: this commit.
- Focused checks:19 JavaScript fetch/journal tests,3 Python packaging tests and1
  Python probe-privacy test passed outside sandbox. Full final `./scripts/test.sh`
  passed710 Python tests (1existing skip) and739 JavaScript tests.
- Interface/stream/deadline/diagnosis evidence: [source fetch](../source-fetch.md).
- Browser evidence: refreshed dedicated ready GM14.369/test, console errors0;
  actual SVG stream/copy-isolation/release passed in one MCP development call.
  No fixtures/mutations/cleanup. Live S3 needs a configured readable bucket/CORS;
  exact credential policy has mock coverage. No external visual claim.
