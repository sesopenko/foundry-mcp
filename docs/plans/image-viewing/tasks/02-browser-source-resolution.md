# 02 — Browser source resolution

Points: **8** — source ambiguity, URL/encoding safety, and fresh permission checks.

Dependencies: [01](01-contracts-and-baseline.md).
Intended commit: `feat(images): resolve exact preview sources in the GM browser`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read the source design's resolution steps, [journal image contracts](../../../journal-images.md),
and the current `foundry-module/scripts/journalImages.js`, especially
`resolveJournalImage()`. Use Grounded Docs for any added public Foundry APIs.

## Implementation and interfaces

- Add a clearly separated preview-source helper beside the existing journal
  image resolver. It accepts either the canonical ImageSelector or one bare
  stored `src`, and returns an internal canonical selection, authorized
  source/location context, and exact selected fetch target. It does not fetch
  bytes or issue public URLs. Preserve existing embedding and browse behavior.
- For canonical inputs, use the same fresh bounded membership check. For bare
  inputs, enumerate only plausible configured sources/buckets and the referenced
  parent, preserve Foundry route prefixes, then pass the exact picker-returned
  selector through the same resolver. Never crawl directories or depend on a
  preceding browse call, listing revision, or cached result.
- Support `data`, `public`, and configured S3; unrelated absolute URLs are not
  downloadable sources. Absolute URLs are only hints that must resolve to an
  allowed picker object. Multiple matches return `AmbiguousSource` with a
  bounded `browse_journal_images` recovery call, never arbitrary first-match
  behavior. Preserve existing `BrowseFailed`/unsupported/listing-bound semantics.
- Compare escaped path segments without double decoding or interpreting encoded
  separators as directory boundaries. Ignore only harmless local cache-busting
  suffixes for matching. Preserve signed S3 query data privately and never
  rewrite or publish it as a recovery example.
- Reject traversal, host paths, executable schemes, malformed/oversized inputs,
  unsupported sources, non-GM/unready access, and changed world/GM context.
  Keep returned private context out of MCP and logs.

## Tests and acceptance

Add `tests/js/image-preview-sources.test.js`. Use realistic FilePicker mocks
that assert exact calls and fresh membership checks, not just returned values.
Test duplicate names across sources, zero/one/multiple matches, local/S3 bucket
configuration, empty/failed/oversized listings, spaces, percent literals, escaped
Unicode, route prefixes, cache suffixes, encoded separators, traversal, absolute
host paths, unrelated URLs, executable schemes, and denied/changed authorization.
Verify no sibling directory scan or credential-bearing error is produced.

Run outside the sandbox:

```bash
node --test tests/js/image-preview-sources.test.js tests/js/journal-images.test.js tests/js/journal-authoring.test.js
./scripts/test.sh
```

After focused checks, use the development-loop skill to refresh and exercise
read-only local source resolution if the browser is available. Record live S3
as pending unless actually configured and tested. Accept when both selector
paths use verified current membership and all path/security tests pass. Commit
helper, tests, and updated source-resolution documentation together.

## Completion record

- Implementation: complete; private resolver only, no registered placeholder.
- Dependency commit SHA(s): 01 `b0cc01e`.
- Commit: this commit.
- Focused checks: 40 JavaScript tests passed with the listed source/journal
  command; one Python live-harness privacy test passed. Full `./scripts/test.sh`
  passed710 Python tests (1 existing skip) and728 JavaScript tests.
- API/runtime/diagnosis evidence: [source resolution](../source-resolution.md).
  Dedicated refreshed test-world browser ready on14.369, zero console errors;
  one read-only MCP invocation passed canonical/bare/absolute public SVG paths.
- Pending prerequisites: configured browser-readable S3 bucket and an existing
  deployment with nonempty route prefix for their respective live checks. Both
  have focused mock coverage; no new instance/configuration was provisioned.
