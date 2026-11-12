# M05 — Map-aware image tools and note-overlay flag

Points: **8** — strict map inputs, snapshot context, and annotation/legend orchestration.
Dependencies: [M04b](m04b-note-layout-and-annotated-encoding.md),
[11](11-image-url-mcp-tool.md).
Intended commit: `feat(maps): issue scene-aware annotated image previews through MCP`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
The existing image tools are complete base contracts at this point; this task
owns the additional public inputs/output rather than silently expanding task 10.

## Implementation and interfaces

- Extend strict info inputs to exactly one of image/src/map, URL inputs to
  exactly one of image/src/source_id/map, and URL-only `map_notes: bool=false`.
  `map` is `{scene_uuid,level_id,role:background|foreground}`. Explicit levels
  come from M02; reject mismatched ownership or silently selected active levels.
  Update actual MCP schemas, response validation and OAuth discovery prose.
- Resolve the declared file privately and then reuse existing fresh picker
  membership, browser transfer, worker probe and caller-bound source cache.
  Map references do not grant arbitrary URL access or bypass auth/limits.
  Bind M03b's map record to staged handles; info still returns compact original
  metadata with no public URL. Do not transfer again for repeated bound crops.
- With flag false, retain original URL fields/behavior and omit `map_notes` from
  results. With true, require explicit map or a map-bound source handle, support
  only verified background mappings, revalidate authority/mapping/note revision
  across awaits, and feed bounded in-region candidates into M04b. Use source
  design errors `MapContextRequired`, `MapContextChanged`, `UnsupportedMapMapping`
  and existing expiry/configuration/permission errors with concrete recovery.
- Add the exact typed `map_notes` response fields from the source design. Return
  counts, <=100 rendered keys, honest complete/scope status and omission reasons,
  plus revision-bound `get_map_info(section=notes,note_keys=...)` legend next call.
  Never include an unbounded full legend in every URL result. Empty notes are
  explicit; do not equate successful publication with complete annotation.
- Replace M02 file follow-ups with exact scene-aware map info/URL calls. Retain
  safe paths for user understanding but keep signed/credential-bearing sources
  private. Update journal/image/map guidance and explain immutable seven-day
  annotated pixels plus the separate original/annotation snapshot semantics.
- Preserve `PreviewNotConfigured` before source work, source isolation, exact
  crop/output fields, immutable UUID issuance, quotas and anonymous GET/HEAD.
  Annotation state never becomes URL query parameters or log data.

## Tests and acceptance

Add `tests/test_map_image_tools.py` through actual list/call and production app
boundaries: every exclusive input/flag combination, bare-file annotation error,
bound/unbound handles, wrong level/role, foreground/raw fallback, revoked/stale
map context, replacement bytes, selector forgery, signed-reference redaction,
partial/zero notes, legend cursor/revision, repeated crops/one transfer, omission
of default fields, publication/quota/cancellation failures, and schema leakage.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_map_image_tools.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_tools.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_map_context.py' -v
./scripts/test.sh
```

Accept when a fresh client can use only returned map selectors and next calls
to issue valid annotated pixels and retrieve their exact legend. Commit public
model/tool changes, integration tests, and discoverable map workflow together.

## Completion record

- Implementation: complete; see [contracts and verification](../map-image-tools.md).
- Dependency commit SHA(s): M04b `722a120`,11 `f5d04c3`.
- Commit: this commit.
- Focused checks: map-image17/26.716s, existing image-tool24/3.722s,
  context23/13.017s, source12, model9, map-info17 and JS33 passed outside sandbox.
  Full1007 Python (1 existing skip)/794JS passed before four final verifier/schema
  tests; required commit hook checks the final staged revision.
- Measurements: fixture7 MCP calls/1 transfer/3 chunks, exact rendered-key legends
  complete; info193B, annotated overview937B, crop941B, legend1121B structured
  JSON. Native catalog47 tools/323516B, info6219B/URL15834B discovery records.
- Packaged UID10001 build/smokes, map-contract3/native-layout15 and module ZIP
  checks passed. Native7-call audit passed map-bound6800x9000/4405816B info and
  matching initial legend; active Scene unchanged, browser console0, no fixtures.
- Runtime support: Foundry14.369 default background placement; unsupported
  transforms/foreground annotations fail explicitly, raw previews remain available.
  Native URL correctly returns PreviewNotConfigured while origin is unset;
  configured trusted HTTPS/store and real delivery belong to14a, target-client
  acceptance to14b. Configured S3 mock passed; live bucket/CORS remains unavailable.
