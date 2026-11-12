# Cross-layer synthetic preview workflows

Task12a runs production JavaScript journal/image handlers in a Node subprocess,
the real Python RPC correlation manager, authenticated production ASGI MCP app,
private source cache, isolated native decoder, SQLite store and anonymous HTTP
reader in one deterministic harness. Only external Foundry documents/FilePicker/
fetch and the physical browser socket are fixtures. This is offline integration
evidence; it does not represent a live Foundry/client deployment.

The fixture carries a stored img tag across three actual journal fragments.
The caller follows returned next_cursor values to completion before extracting
src, issues from that raw reference, browses an exact image and issues directly,
then calls info and reuses one handle for two crops. Unicode/escaped paths and a
route prefix pass through actual resolution. Mock fetch checks the precise
canonical prefixed URL and credential policy. Private RPC chunks are delivered
in deterministic reverse-window order, exercising real correlation/assembly
rather than relying on scheduler timing. No original bytes cross MCP results.

Whole images and bottom-right/one-pixel crops are decoded and compared with an
independent Pillow original-region oracle. Separate cases cover mirrored/rotated
EXIF and transparency. Snapshot reuse preserves replaced bytes; fresh info sees
the new file. All four issued capabilities are distinct and anonymous reads
return their exact immutable derivative pixels.

Fault cases verify short/missing chunks, cancellation, a genuinely new Node
process/socket revalidating the same authorized world/GM snapshot, changed world,
denied membership, expiry, real malformed decoder input, non-GM access, worker
resource-error propagation and quota rejection retaining existing links.
Injected read-timeout bounds accelerate the missing-response test; production
15s/300s transfer defaults are unchanged. Real resource-limit enforcement remains
covered by05b; a mocked ImageMemoryLimit here proves orchestration propagation.
Actual two-principal offline-JWT HTTP isolation from04b is rerun separately.

The harness enforces40 MCP requests/600 seconds, with40 anonymous fetches maximum;
unit cases exercise exhaustion before reads and verify private source/store roots
are deleted on exit. It closes/reaps every owned Node process and leaves no
pending Python RPCs or browser transfer leases. No game assets, live fixtures,
external model calls or new Foundry instances are involved.

A final EOF test caught the simulated socket missing the production endpoint's
unregister-on-close callback: pending transfer calls timed out instead of failing
promptly. The fixture now mirrors that callback in receive-finally. The same
unchanged EOF test passes; no production WebSocket behavior was changed.

## Measured complete small-image workflow

Ten actual HTTP MCP requests include one discovery, three journal fragments and
the six discovery/info/URL operations below. Four anonymous derivative GETs are
counted separately. Three original transfers produce12 private chunks; repeated
handle crops add no transfer. Every selected stream completes, with zero errors.

| Tool | Calls | Structured JSON bytes | MCP result bytes | Complete |
| --- | ---: | ---: | ---: | --- |
| read_journal_page |3|2430|5612|Yes|
| browse_journal_images |1|811|1884|Yes|
| get_foundry_image_info |1|193|596|Yes|
| get_foundry_image_url |4|1564|4040|Yes|

MCP result bytes serialize the actual tools/call result object, excluding HTTP/
JSON-RPC framing. Structured bytes are compact UTF8 JSON, not billed tokens.
These synthetic fixtures are separate from the retained live-world baseline;
task12b owns full-size maps, measured worker resources and equal-content replay.

Focused commands and final full results are recorded in
[task12a](tasks/12a-workflow-and-failure-integration.md). The implementation is
unchanged by this test checkpoint; packaged component evidence remains task11,
with final packaging13 and actual local/public-client acceptance14a/14b pending.
