# 10 — Image info MCP tool

Points: **1** — the smallest remaining wiring task: expose already-tested
staging/probing through established typed MCP registration and test patterns.

Dependencies: [04b](04b-private-snapshots-and-caller-isolation.md),
[05b](05b-worker-resource-supervision.md).
Intended commit: `feat(images): expose authenticated Foundry image metadata`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the tool-contract table and registration patterns in `mcp_server/tools.py`,
typed image-upload tools, OAuth discovery middleware, and actual FastMCP tests.
Consume 04b's authenticated staging/handle service and 05b's supervised real probe.

## Implementation and interfaces

- Add `get_foundry_image_info` with task 01's strict typed inputs and output,
  registering through the existing tools import boundary. Use actual FastMCP
  validation in both directions; do not return unchecked browser/worker payloads.
  Keep the tool in discovery even when preview URL issuance is not configured.
- Accept exactly one canonical `image` or bare stored `src`; neither requires a
  previous browse. Require authorized MCP caller context and authenticated ready
  GM connection. Resolve, transfer once, stage privately, and probe the immutable
  bytes. This tool needs no public preview origin and issues no public URL.
- Return exactly the required `source_id`, `source_expires_at`, `width`, `height`,
  `mime_type`, `size_bytes`, and `frame_policy`. Dimensions describe original
  display-oriented pixels; size is compressed source size. Source handle is
  private/caller-bound and expires 30 minutes after staging.
- On probe failure/cancellation release staging resources and handle state;
  never leave invalid handles in the cache. Sanitize browser/decoder failures
  into actionable errors without paths, original bytes, source digests, signed
  URLs, credentials, or arbitrary source text in results or logs.
- Discovery prose and schema field descriptions must stand alone: state input
  provenance from `browse_journal_images` or stored journal/portrait references,
  exact fields, units/limits, GM/authentication scope, snapshot meaning, frame
  policy, and next call `get_foundry_image_url`. For fragmented journal HTML,
  explain following `next_cursor` before extracting a complete tag. Include a
  minimal map example; do not claim visual analysis occurs inside this tool.
- Confirm the OAuth discovery middleware adds the required security metadata
  for the new tool without special casing away existing auth protections.

## Tests and acceptance

Add `tests/test_image_preview_tools.py` with actual MCP list/call tests. Exercise
schema rejection, exclusive inputs, canonical/bare success, no mandatory prior
browse, absent public origin, missing authenticated caller or GM, non-GM/wrong
world/socket, original orientation metadata, malformed worker/browser responses,
probe failure cleanup, source expiry, and bounded compact results.
Assert discovery includes strict input/output schemas, next-tool guidance, and
OAuth metadata. Test response validation rejects extra/private fields rather
than letting them reach the caller. Use trusted context for in-memory tests and
HTTP-auth tests for authority; never add a production test bypass.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_tools.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_sources.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_oauth*.py' -v
./scripts/test.sh
```

Restart/reconnect only as the developer restart matrix requires and check actual
discovery on the current client when available. Accept when both public inputs
work through MCP, all outputs validate, and no origin is required. Commit tool,
registration, tests, discovery prose, and metadata guidance together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks, discovery record bytes and response bytes: not run.
- Current-client/runtime evidence and exact prerequisites: pending.
