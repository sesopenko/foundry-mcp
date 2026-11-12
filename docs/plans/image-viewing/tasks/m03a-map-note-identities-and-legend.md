# M03a — Map note identities and bounded legend

Points: **5** — public note projection, stable aliases, and a paged identity legend.
Split from the 13-point map-note extraction/mapping addition; M03b owns mapping.
Dependencies: [M02](m02-map-grid-and-image-files.md).
Intended commit: `feat(maps): expose revision-bound note identities and legend pages`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design including map extension](../../../prompts/foundry-image-previews-plan.md),
[map research](../map-browsing-notes-research.md), [index](../README.md), and this
task. Reconcile dependency commits/test evidence and follow the index protocol.
Read public NoteDocument label/entry/page, BaseNote schema, and level-membership
contracts. Resolve empty/null semantics from authoritative evidence and focused
runtime checks; if unavailable, report unsupported applicability explicitly.

## Implementation and interfaces

- Add `section=notes` to typed `get_map_info` requests/responses and discovery.
  Require exact `level_id`, accept at most 100 distinct exact `note_keys`, and
  reject note-only arguments on assets/tiles. Use existing bounds/cursors and
  `expected_revision`; never return a different revision as an agreeing legend.
- Read public authorized scene/level notes and label/linked identities without
  hydrating journal bodies. Preserve Note UUID, journal/page UUID or explicit
  unavailable/unlinked state, named label with clipping marker, and source
  coordinates/level context. Denied targets must not leak names or labels.
  Check linked-target permissions before evaluating label getters that may
  fall back to a target title. Retain safe note identity and explicit denial.
- Within the complete authorized applicable level snapshot, sort by canonical
  Note UUID and assign N1/N2/... before filtering or pagination. Repeated pins
  linking the same journal stay distinct. Revisions include note content,
  membership, permissions, and mapping-relevant scene/level references. Later
  crop filtering must not renumber aliases.
  Share the selected-level revision across assets/notes views and key filters
  so M05's exact legend next call can be checked without silently joining a
  different snapshot. Include scene/level identity in that next call.
- Keep all source/label material out of arbitrary errors and logs; cap display
  labels at 256 codepoints with explicit truncation, never truncate identifiers.
  Return `scope_status`/limitations separately from stream `complete`, preserving
  zero notes versus denied/unsupported applicability. Fix public field names and
  standalone recovery prose alongside actual MCP tests.
- Expose an internal revision-checked candidate reader for M03b/M05, bounded to
  100 candidates per response and 48,000 bytes including JSON. Its actual frame
  must fit the configured bridge ceiling. Do not export whole scene note data
  in one unbounded RPC; share projection and revision logic with the public reader.

## Tests and acceptance

Add `tests/js/map-notes.test.js` and `tests/test_map_notes.py`: aliases across
pages/filtering, distinct duplicate pins, linked/unlinked/missing/denied targets,
label override/fallback, long/malicious labels, level membership including empty/
null, unavailable semantics, expected-revision mismatch, changed permissions,
keys from another scene/level, pagination and byte bounds. Use actual MCP calls.

Run outside the sandbox:

```bash
node --test tests/js/map-notes.test.js
.venv/bin/python -m unittest discover -s tests -p 'test_map_notes.py' -v
./scripts/test.sh
```

Accept when identities/aliases/legend pages are reliable without renderer or
source-byte access. Record applicability evidence/gaps. Commit projection,
typed section, tests, and legend recovery documentation together.

## Completion record

- Implementation: complete; [identity contract/API/measurements](../map-note-identities.md).
- Dependency commit SHA(s): M02 `af58e0d`.
- Commit: this commit.
- Focused notes13, selected-map17 and combined JS33 pass outside sandbox.
  Final `./scripts/test.sh`:942 Python (1 existing skip)/783 JS passed.
  Actual local module ZIP packaging passes; no version bump/publication.
- Baseline2 calls:483 notes, all empty membership sets,208 text overrides;
  47 tools/309786B. Public-member/unpersisted-constructor1-call verification
  proves normal membership via documented includedInLevel, unchanged collection
  and active Scene,zero persisted fixtures. Runtime/source version14.369.
- Native legend9 calls/120s budget:21 notes,3 default pages,2 exact-key identity
  lookups and1 equal-content expanded page, complete scope/stream and unchanged
  active Scene.47 tools/314317B,27629B live get_map_info record; detail table linked.
  Refreshed dedicated browser readyGM14.369/test,console0.
- No M03a local applicability prerequisite remains. Source-pixel mapping,
  original-byte context binding and rendered keys remain M03b–M05 work; no
  overlay or target-client acceptance is claimed here.
