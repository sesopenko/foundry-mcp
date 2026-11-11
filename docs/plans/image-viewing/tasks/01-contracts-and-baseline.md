# 01 — Contracts and baseline

Points: **5** — typed contracts, characterization, and bounded baseline measurement.

Dependencies: none. Intended commit: `feat(images): define preview contracts and baseline checks`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile Git/test evidence; do not
rely on a summary. Follow the index's execution and commit protocol.

Read AGENTS.md's required files, [journal image contracts](../../../journal-images.md),
[image uploads](../../../image-uploads.md), [selective reads](../../../selective-reads.md),
[evaluation process](../../../mcp-tool-evaluation.md), and
[API research workflow](../../../foundry-api-docs.md). Trace existing registration,
ImageSelector validation, worker lifecycle, browser resolver, and socket guard.

## Implementation and interfaces

- Add preview-specific strict Pydantic request/response models in a new
  `foundry_mcp_server/mcp_server/image_preview_models.py`. Reuse ImageSelector;
  forbid extra fields and avoid changing unrelated model behavior.
- Info requires exactly one of `image` or `src`. URL requires exactly one of
  `image`, `src`, or `source_id`; only URL accepts optional `crop`. Preserve the
  existing selector's source/directory/bucket/src rules and bounds.
- Info result fields: `source_id`, `source_expires_at`, `width`, `height`,
  `mime_type`, `size_bytes`, `frame_policy` (`still` or `first_frame`). Width and
  height describe original display-oriented pixels, not a resized derivative.
- URL result fields: `url`, `expires_at`, `source_id`, `source_expires_at`,
  `source_width`, `source_height`, `region:{x,y,width,height}`, `width`, `height`,
  `mime_type`, `size_bytes`. Distinguish original, region, and delivered dimensions.
- Crop uses strict integers, top-left origin, exclusive right/bottom edges,
  positive extent, and full containment. Arrange validation so malformed crop
  inputs yield the required `InvalidCrop` category, with valid dimensions once
  safely known, rather than silently coercing booleans/floats or clipping.
- Centralize limits from the index/source design. Use existing ToolError/RPC
  conventions for actionable categories, including `AmbiguousSource`,
  `InvalidCrop`, `UnsupportedImage`, `ImageTooLarge`, and `PreviewNotConfigured`.
  Freeze expiry/lost-context/quota recovery wording with the implementing tasks;
  never reflect raw native errors or signed URLs. Do not register stub tools.
- Before changing existing tools, capture actual discovery plus representative
  browse and journal results with a deterministic bounded harness. Limit the
  baseline to 40 calls/120 seconds; record unavailable scenarios explicitly.
  Include default, filtered/selective, expanded, and complete-pagination cases
  on reusable exact fixtures/locations. Record calls, compact UTF-8 JSON bytes,
  completion, and catalog size; keep bulk results private.
- Add characterization assertions for the selector/resolver behavior being
  extended. Record runtime major/build, indexed API version/freshness, official
  FilePicker API links and public visibility. New dependencies need Grounded
  Docs evidence before adoption; runtime observations alone are insufficient.

## Tests and acceptance

Add `tests/test_image_preview_models.py` and characterization coverage alongside
existing journal image tests. Test every selector combination, forbidden extras,
strict numeric fields, empty/malformed selectors, timestamp/metadata response
validation, and a complete valid info/URL example. Verify existing browse and
upload schemas retain their behavior. Unit-test baseline aggregation so totals,
completion, and redaction do not rely on an agent's estimates.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_models.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_journal_images.py' -v
node --test tests/js/journal-images.test.js
./scripts/test.sh
```

Accept when strict internal contracts and characterization tests pass, the
bounded baseline is recorded or precisely marked unavailable, and the API
research record distinguishes verified facts from gaps. No production feature
discovery is added yet. Commit models, tests, baseline harness, and evidence.

## Completion record

- Implementation: not started.
- Commit: pending; use `this commit` in the completing commit, resolved by successor.
- Focused/full checks: not run.
- Baseline calls/bytes/completion/catalog and API evidence: pending.
- Pending external evidence and exact prerequisites: none assessed yet.
