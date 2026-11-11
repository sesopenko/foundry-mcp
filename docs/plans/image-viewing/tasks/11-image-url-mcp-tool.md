# 11 — Image URL MCP tool

Points: **8** — authorization across orchestration, handle reuse, and atomic issuance.

Dependencies: [07b](07b-safe-svg-rasterization.md),
[09b](09b-auth-boundaries-and-capability-privacy.md),
[10](10-image-info-mcp-tool.md).
Intended commit: `feat(images): issue immutable overview and crop URLs through MCP`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the full public contract, snapshot/coordinate semantics, publication rules,
and task 10's actual registration/tests. Consume private staging, worker,
store, issuance policy, and trusted origin interfaces from dependencies.

## Implementation and interfaces

- Deliver base file/handle previews here. The source design's map selector,
  `map_notes` flag, map-context revision checks and legend output are explicitly
  deferred to [M05](m05-map-aware-image-tool-integration.md), which depends on
  this complete base tool and the separately tested map renderer.
- Register `get_foundry_image_url` through actual FastMCP with strict typed
  request/response validation and OAuth metadata. Require exactly one of
  canonical `image`, bare `src`, or `source_id`, plus optional `crop`.
- After input validation, check issuance configuration before any browser read,
  staging, probe, or render. Disabled issuance returns `PreviewNotConfigured`.
  Authenticated Basic/OAuth or existing authenticated development plus a ready
  authorized GM are required; plain unauthenticated mode never mints links.
- Selector/reference inputs stage and probe a new snapshot. A handle reuses its
  exact bytes without another source transfer; recheck authenticated caller,
  GM/world and current exact selector membership before each new issuance,
  including across awaits and before publication. Changed path contents do not
  change an existing snapshot. Expiry or lost authority gives typed recovery;
  a missing/denied path cannot be bypassed by retaining its handle.
- Lease the snapshot, validate the source-oriented crop, render through the
  isolated worker, verify actual artifact properties, then publish atomically.
  Return exactly the source design's URL fields. Use source dimensions for
  `source_width/source_height`, selected original pixels for `region`, actual
  raster dimensions for `width/height`, and separate snapshot/public expiries.
- Every successful issuance gets a distinct UUIDv4 and its actual png/webp
  extension. Public HTTPS origin comes only from trusted configuration. No
  source, crop, credentials, timestamp, query, or fragment is encoded in the URL.
  Never return worker paths, source bytes, digests, or signed S3 information.
- Release leases and delete temporary derivatives after success or failure;
  preserve valid snapshots for reuse. Quota rejection must leave issued links
  usable. Cancellation must not report a successful publication with partial
  state; do not introduce undocumented idempotency or shared-capability behavior.
- Discovery must explain that anyone holding the link can read its selected
  pixels for exactly seven days, even without a connected GM. Include all input
  provenance, limits, coordinates, preview-to-source mapping, snapshot semantics,
  frame limitations, recovery steps, and info/browse follow-ups. Add minimal
  journal/browse guidance rather than duplicating the full contract in README.

## Tests and acceptance

Extend `tests/test_image_preview_tools.py` through actual list/call boundaries.
Cover all three inputs without prior browsing, omitted crop, strict invalid
rectangles, valid region and actual dimensions, distinct issuances, no-origin
early rejection with zero source calls, nonauthenticated rejection, OAuth
metadata, repeated crops after one transfer, replacement bytes with old/new
handles, expired/cross-principal/denied membership, changed socket/world/GM at
each await boundary, invalid worker output, storage/quota failure, cancellation,
and lease/temp cleanup. Fetch an issued derivative through the production app;
assert the capability cannot select another region or expose original bytes.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_tools.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_http.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_oauth*.py' -v
./scripts/test.sh
```

Accept when discovery and invocation describe and deliver both portrait and map
paths using validated compact results, preserving auth, immutable pixels, and
expiry. Commit orchestration, tests, and public tool guidance together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, discovery/response bytes, transfer counts: not run.
- Runtime/client evidence and exact outstanding prerequisites: pending.
