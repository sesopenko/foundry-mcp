# 13 — Deployment and packaged verification

Points: **8** — final service-user image checks, persistence, and deployment examples.

Dependencies: [M05](m05-map-aware-image-tool-integration.md).
Intended commit: `build(images): verify packaged previews and persistent deployment storage`.

## Context recovery and reading

Before work and after **every context compression, resume, or handoff**, reread
in full the [assignment snapshot](../../../prompts/foundry-image-viewing-task-breakdown-plan.md),
[source design](../../../prompts/foundry-image-previews-plan.md),
[plan index](../README.md), and this task. Reconcile dependency commits and test
evidence. Follow the index's execution and commit protocol.

Read current Dockerfile, deployment Compose and environment examples,
[operations](../../../operations.md), [Docker Hub overview](../../../docker-repository-overview.md),
and existing packaging tests. Tasks 05a–05b and 07a–07b supply dependency/codec
implementation; M04a adds verified packaged fonts. This task verifies the
complete production artifact and setup after all map/image inputs are wired.

## Implementation and interfaces

- Complete final production-image packaging for pinned pyvips/libvips and every
  advertised loader, including safe SVG rasterization and the bundled map-note
  font/Pango support. Test a real annotated crop and font metrics as service UID
  10001 with no source mount or host-native decoder dependency. Preserve locked
  unrelated dependencies, existing upload behavior, build identities, and
  current release version; do not bump, tag, push, or publish.
- Wire `FOUNDRY_MCP_IMAGE_PREVIEW_ORIGIN` and
  `FOUNDRY_MCP_IMAGE_PREVIEW_DATA_DIR` into opt-in Basic/OAuth deployment
  examples and environment templates. The private default `/data/image-previews`
  must be writable by UID 10001 and backed by a named volume. Keep source cache
  and decoder scratch private and separate from public derivative lookup.
- Exercise initialization with the named volume, store/query a derivative,
  recreate the isolated MCP container using the same volume, and prove an
  unexpired capability still serves identical bytes. No additional Foundry
  instance, world setup, license activation, or package installation is needed.
  Never remove existing development or production volumes during this check.
- Update operator/image-viewing documentation with trusted origin configuration,
  externally reachable HTTPS, persistent storage, exact seven-day expiry,
  30-minute snapshots, resource/format limits, crop coordinates/recovery, and
  simultaneous server/module upgrade plus browser refresh. Show generic hosts
  and placeholders only. Do not misstate pending target-client acceptance.
- Include folder-to-map browsing, duplicate-name ancestry, level/background/
  foreground/Tile inventory, grid/file versus original-image dimensions, the
  map selector, `map_notes` defaults, compact keys and bounded legend follow-ups,
  mapping support limits, and honest dense-layout omissions. M04a already owns
  font implementation/packaged glyph tests; M06 owns complete live map workflow
  acceptance. Keep this task focused on final artifact/configuration integration.
- Document direct uncached proxy routing for `/image-previews/`, no redirects
  or authentication added to that route, and suppression/redaction of capability
  paths/query strings in proxy access/error logs. Preserve protection of MCP,
  bridge, and PDF routes and exclusive Basic/OAuth modes. Never repurpose the
  OAuth resource origin as a Basic preview configuration shortcut.
- Update the Docker Hub overview in the same change with self-contained absolute
  public links and working examples, but do not publish it. Revise existing
  README summaries to one or two short sentences per affected topic and link to
  details. Review the whole affected rendered Markdown section for repetition.

## Tests and acceptance

Add `tests/test_image_preview_packaging.py` to check packaging/configuration
contracts and example consistency, with real packaged behavior covered by a
bounded container smoke harness. Verify every codec and an unsafe SVG rejection
inside the shipped image as UID 10001, deterministic font/annotated output,
private permissions, successful writes,
restart persistence, missing-origin behavior, malformed origin/data-directory
configuration, and unprivileged health. Verify named-volume examples using
Compose config validation with placeholders, not private environment values.
Do not claim static Dockerfile string checks establish runtime codec support.

Run outside the sandbox:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_image_preview_packaging.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_image_uploads.py' -v
./scripts/test.sh
```

Run the bounded image build/codec/restart harness and record its exact command,
image identity, runtime UID, versions, and outcomes without capabilities. Accept
when production packaging and volume persistence pass, examples validate, and
public documentation matches actual discovery. If Docker execution is denied
or unavailable, record the exact packaged verification gap and prerequisite.
Commit packaging/deployment changes, tests, and operator/public docs together.

## Completion record

- Implementation: not started.
- Dependency commit SHA(s): pending.
- Commit: pending (`this commit` when completed).
- Focused/full checks and Compose example validation: not run.
- Image identity, UID, codec matrix, restart/persistence results: pending.
- Pending deployment/client prerequisites: pending.
