# Foundry image viewing: unattended implementation plan

Implement the image tools, map browsing, note overlays, and private preview service in the
[source design](../../prompts/foundry-image-previews-plan.md). This directory
breaks that design into independently tested local commits. No feature work has
been completed merely by creating this plan.

## Start and recover context

Before starting, and **immediately after every context compression, session
resume, or handoff**, reopen and read these files **in full** before selecting
the next action:

1. [Execution assignment](../../prompts/foundry-image-viewing-build-agent.md) and
   [durable build progress](build-progress.md).
2. [Planning assignment snapshot](../../prompts/foundry-image-viewing-task-breakdown-plan.md)
3. [Authoritative feature design](../../prompts/foundry-image-previews-plan.md)
4. [Map browsing and note research](map-browsing-notes-research.md), including its verification gaps.
5. This index and the current task file, including its dependencies' evidence.
6. [Repository instructions](../../../AGENTS.md) and their required reading.

This rule applies both to the agent maintaining these planning documents and
the agent implementing the feature. A compressed summary is not a substitute.
Reconcile the current diff, Git history, test evidence, and task records before
resuming. The design's reviewed commit is a reference, not a reset instruction;
start from the current checkout and preserve unrelated changes.

Use this kickoff instruction for the implementation agent:

> Implement `docs/plans/image-viewing/README.md`. Read its context-recovery
> instructions, both referenced prompts, and the map research in full before starting. Complete
> ready tasks with their unit tests and separate local commits. After every
> context compression or resume, reread those files and the current task from
> disk before continuing. Record unavailable external checks precisely and
> continue independent authorized work.

## Dependency graph and checkpoints

```mermaid
flowchart TD
    T01["01 Contracts and baseline · 5"]
    T02["02 Browser source resolution · 8"]
    T03a["03a Browser source fetch · 8"]
    T03b["03b Chunk protocol and lifecycle · 5"]
    T04a["04a Python transfer assembly · 8"]
    T04b["04b Snapshots and caller isolation · 8"]
    T05a["05a Decoder probe and packaging · 5"]
    T05b["05b Worker resource supervision · 8"]
    T06a["06a Crop geometry and resampling · 5"]
    T06b["06b Encoding and byte budget · 5"]
    T07a["07a Raster codecs and frame policy · 5"]
    T07b["07b Safe SVG rasterization · 8"]
    T08["08 Persistent preview store · 8"]
    T09a["09a HTTP delivery and configuration · 5"]
    T09b["09b Auth boundaries and privacy · 5"]
    T10["10 Image info MCP tool · 1"]
    T11["11 Image URL MCP tool · 8"]
    T12a["12a Workflow and failure integration · 8"]
    T12b["12b Large-map and payload measurement · 8"]
    T13["13 Deployment and packaged verification · 8"]
    T14a["14a Local runtime acceptance · 8"]
    T14b["14b Target-client visual handoff · 5"]
    M01["M01 Map folder browsing · 8"]
    M02["M02 Grid and image files · 8"]
    M03a["M03a Note identities and legend · 5"]
    M03b["M03b Coordinates and revision binding · 8"]
    M04a["M04a Bundled font and glyphs · 5"]
    M04b["M04b Label layout and encoding · 8"]
    M05["M05 Map-aware image tools · 8"]
    M06["M06 Complete map workflow verification · 8"]
    VISUAL["External gate: ChatGPT visual acceptance"]

    T01 --> T02
    T02 --> T03a
    T03a --> T03b
    T03b --> T04a
    T04a --> T04b
    T01 --> T05a
    T05a --> T05b
    T05b --> T06a
    T06a --> T06b
    T06b --> T07a
    T07a --> T07b
    T01 --> T08
    T08 --> T09a
    T09a --> T09b
    T04b --> T10
    T05b --> T10
    T10 --> T11
    T07b --> T11
    T09b --> T11
    T11 --> T12a
    T12a --> T12b
    M05 --> T13
    T12b --> T14a
    T13 --> T14a
    T14a --> M06
    M06 --> T14b
    T14b --> VISUAL
    T01 --> M01
    M01 --> M02
    T02 --> M02
    M02 --> M03a
    M03a --> M03b
    T06a --> M03b
    T06b --> M04a
    M04a --> M04b
    M03b --> M04b
    M04b --> M05
    T11 --> M05
```

Direct dependencies are listed below; their ancestors are also prerequisites.
Default execution is a single agent: choose the first unfinished task in table
order whose dependency commits are complete. Lettered tasks are separate commits;
M tasks implement the map extension. Skip a task awaiting an independent branch
and continue ready work, preserving precise external gaps. The graph does not authorize
spawning agents or concurrent writes to this checkout.

| ID and task | Points | Direct dependencies | Implementation status | Commit |
| --- | --- | --- | --- | --- |
| [01 Contracts and baseline](tasks/01-contracts-and-baseline.md) | 5 | None | Complete | b0cc01e |
| [02 Browser source resolution](tasks/02-browser-source-resolution.md) | 8 | 01 | Complete | 141ede6 |
| [03a Browser source fetch](tasks/03a-browser-source-fetch.md) | 8 | 02 | Complete | e4121a4 |
| [03b Chunk protocol and lifecycle](tasks/03b-chunk-protocol-and-lifecycle.md) | 5 | 03a | Complete | 647c42b |
| [04a Python transfer assembly](tasks/04a-python-transfer-assembly.md) | 8 | 03b | Complete | fe47d21 |
| [04b Snapshots and caller isolation](tasks/04b-private-snapshots-and-caller-isolation.md) | 8 | 04a | Complete | a045d08 |
| [05a Decoder probe and packaging](tasks/05a-decoder-probe-and-packaging.md) | 5 | 01 | Complete | 57123ce |
| [05b Worker resource supervision](tasks/05b-worker-resource-supervision.md) | 8 | 05a | Complete | cc7ba71 |
| [06a Crop geometry and resampling](tasks/06a-crop-geometry-and-resampling.md) | 5 | 05b | Complete | 49e8aaf |
| [06b Encoding and byte budget](tasks/06b-preview-encoding-and-byte-budget.md) | 5 | 06a | Complete | 4740720 |
| [07a Raster codecs and frame policy](tasks/07a-raster-codecs-and-frame-policy.md) | 5 | 06b | Complete | 02d0d8f |
| [07b Safe SVG rasterization](tasks/07b-safe-svg-rasterization.md) | 8 | 07a | Complete | b144211 |
| [08 Persistent preview store](tasks/08-persistent-preview-store.md) | 8 | 01 | Complete | 089b14f |
| [09a HTTP delivery and configuration](tasks/09a-http-delivery-and-configuration.md) | 5 | 08 | Complete | 37977ee |
| [09b Auth boundaries and capability privacy](tasks/09b-auth-boundaries-and-capability-privacy.md) | 5 | 09a | Complete | 4023ed2 |
| [10 Image info MCP tool](tasks/10-image-info-mcp-tool.md) | 1 | 04b, 05b | Complete | 85236ce |
| [11 Image URL MCP tool](tasks/11-image-url-mcp-tool.md) | 8 | 07b, 09b, 10 | Complete | f5d04c3 |
| [12a Workflow and failure integration](tasks/12a-workflow-and-failure-integration.md) | 8 | 11 | Complete | d5fe0de |
| [12b Large-map and payload measurements](tasks/12b-large-map-and-payload-measurements.md) | 8 | 12a | Complete | 5bae8bb |
| [M01 Map folder browsing](tasks/m01-map-folder-browsing.md) | 8 | 01 | Complete | e9ea43e |
| [M02 Grid and image files](tasks/m02-map-grid-and-image-files.md) | 8 | M01, 02 | Complete | af58e0d |
| [M03a Note identities and legend](tasks/m03a-map-note-identities-and-legend.md) | 5 | M02 | Complete | 26bb4e6 |
| [M03b Coordinates and revision binding](tasks/m03b-map-coordinate-and-revision-binding.md) | 8 | M03a, 06a | Complete | 8155684 |
| [M04a Bundled font and glyphs](tasks/m04a-bundled-font-and-note-glyphs.md) | 5 | 06b | Complete | a07630f |
| [M04b Label layout and encoding](tasks/m04b-note-layout-and-annotated-encoding.md) | 8 | M04a, M03b | Complete | 722a120 |
| [M05 Map-aware image tools](tasks/m05-map-aware-image-tool-integration.md) | 8 | M04b, 11 | Complete | 823cb3b |
| [13 Deployment and packaged verification](tasks/13-deployment-and-packaged-verification.md) | 8 | M05 | Complete | this commit |
| [14a Local runtime acceptance](tasks/14a-local-runtime-acceptance.md) | 8 | 12b, 13 | Not started | — |
| [M06 Complete map workflow verification](tasks/m06-map-workflow-verification.md) | 8 | 14a | Not started | — |
| [14b Target-client visual handoff](tasks/14b-target-client-visual-handoff.md) | 5 | M06 | Not started | — |

Task files name intended local commit subjects. Each task's implementation,
unit tests, relevant documentation, and evidence must be committed together;
never defer its tests to task 12a. Foundation code may remain internal until the
tool tasks register it; do not publish placeholder MCP tools.

## Relative estimates and splits

Current plan: **30 executable tasks / 200 points**, maximum **8**, with no
13-point tasks. Compared with the committed 22-task/140-point plan, the map
extension adds 8 tasks/58 points and expands final visual handoff from 3 to 5.
Existing base contracts remain staged work: M05 owns map inputs/annotations;
do not silently grow tasks 01/10/11 with that integration. Final packaging stays
8 because font implementation/tests and full map workflows have separate owners.

| Map addition or affected task | First augmented estimate | Final task sizes |
| --- | --- | --- |
| Map folder browsing | 8 | M01: 8 |
| Grid/level image file reading | 8 | M02: 8 |
| Note extraction plus coordinate/revision mapping | 13 | M03a: 5; M03b: 8 |
| Note text rasterization plus collision/layout/retries | 13 | M04a: 5; M04b: 8 |
| Map-aware image tool integration | 8 | M05: 8 |
| Complete map workflow verification | 8 | M06: 8 |
| Final target-client handoff (previously 3) | 5 | 14b: 5 |

The augmented draft had 28 tasks/200 points and two 13s; splitting them produces
30 tasks/200 points with maximum 8. Each child owns its tests and local commit.
All other existing task estimates stay unchanged. IDs such as task 13 are not
point values. The earlier before/after sizing below is retained as history.

Points combine implementation effort, test/verification effort, and technical
uncertainty relative to this task set; they are not hours. Allowed values are
1 (small isolated change), 3 (bounded addition), 5 (moderate subsystem change),
8 (substantial change with one cohesive boundary), and 13 (too broad for one
checkpoint). Task 10 is the 1-point anchor because its source/probe/auth services
and registration/testing patterns are supplied by completed dependencies.
The external client's availability is recorded as a prerequisite, not estimated
waiting time. The external visual gate itself is not an implementation task.

The initial sizing found eight 13-point tasks. Each has been replaced by two
smaller tasks with its own tests and local commit; the parent ID is retained only
for this before/after mapping. No executable 13-point parent remains. Task IDs
such as 13 are identifiers, separate from point values.

| Original task | Before | After, with points |
| --- | --- | --- |
| 01 Contracts and baseline | 5 | 01: 5 |
| 02 Browser source resolution | 8 | 02: 8 |
| 03 Browser byte transfer | 13 | 03a Fetch: 8; 03b Chunk protocol: 5 |
| 04 Snapshots and caller isolation | 13 | 04a Assembly: 8; 04b Snapshots: 8 |
| 05 Isolated decoder and metadata | 13 | 05a Probe/packaging: 5; 05b Supervision: 8 |
| 06 Crop geometry and encoding | 13 | 06a Geometry: 5; 06b Encoding: 5 |
| 07 Formats and SVG safety | 13 | 07a Raster codecs: 5; 07b SVG safety: 8 |
| 08 Persistent preview store | 8 | 08: 8 |
| 09 HTTP and capability privacy | 13 | 09a HTTP/configuration: 5; 09b Auth/privacy: 5 |
| 10 Image info tool | 1 | 10: 1 |
| 11 Image URL tool | 8 | 11: 8 |
| 12 Workflow/failure integration | 13 | 12a Workflows: 8; 12b Large-map/measurements: 8 |
| 13 Deployment/package verification | 8 | 13: 8 |
| 14 Local acceptance/handoff | 13 | 14a Local acceptance: 8; 14b Visual handoff: 3 |

Historical first pass: **14 tasks / 142 points before; 22 tasks / 140 points after**. Maximum
task size falls from 13 to 8. Split estimates are made independently rather than
forced to sum to the parent's estimate; the slight total change is estimation
refinement, not a claim of reduced feature scope or guaranteed time savings.

## Per-task execution protocol

1. Perform context recovery above. Inspect status/diff and verify dependency
   commits. Use the code graph for local structure, current source for truth,
   and versioned Grounded Docs for Foundry public contracts.
2. Read the task's linked sections and implement its smallest complete boundary.
   Establish tests for behavior being extended before changing it. Reproduce
   unexpected behavior with a failing unit test before fixing it.
3. Run listed focused checks after meaningful edits. All tests, including
   test-running hooks and verification harnesses, require the command tool's
   `sandbox_permissions: "require_escalated"` from their first invocation.
   Preserve approval protections; report denied execution rather than weakening
   assertions. Provision dependencies separately with `uv sync --locked`.
4. Run `./scripts/test.sh` before every implementation commit. Resolve relevant
   failures before dependent work. Markdown-only evidence commits follow the
   repository's staged-path exception and still need link/consistency checks.
5. Use the development-loop skill for module changes: after focused tests,
   refresh only the dedicated development tab, wait for bridge readiness, and
   inspect console/live behavior. Use connection guidance if needed. If runtime
   access is missing, record the precise check and continue independent work;
   mocks do not prove Foundry compatibility.
6. Stage explicit task paths with plain `git add`, inspect the staged diff and
   whitespace, then run plain `git commit`. Do not push, tag, release, bypass
   hooks, or include unrelated edits. The task request authorizes these local
   implementation commits. This plan does not authorize publication.
7. Record implementation status, checks, measurements, and gaps in the task and
   index. In its own commit, identify the task commit as `this commit`; the next
   task resolves that reference to its SHA using Git history. A commit cannot
   contain its own final SHA. Record literal SHAs for predecessors and resolve
   the final task in the final report without an endless amend cycle.

After three unsuccessful diagnosis/fix attempts on one issue, stop and report
the evidence and required input per AGENTS.md. Do not switch tasks to evade that
stop requirement. Otherwise continue until all independent authorized work is
complete. Do not invent passing results when services are unavailable.

Keep command approvals easy to review: use short, plain commands and existing
fixed runners where available. Put necessary reusable verification logic in
readable, tested harness files with documented bounds. Avoid large inline
Python or shell programs in approval requests, and keep file edits separate
from verification commands.

## Interfaces and fixed budgets

The source design owns exact public fields and semantics. Tasks 01/10/11 define
and expose the base file/handle tools; M01/M02 add `browse_maps`/`get_map_info`,
M03a adds the bounded note legend, and M05 extends image tools with explicit
scene/level/role `map` selectors. Only the URL tool accepts `source_id`, `crop`,
and opt-in `map_notes`. Private byte-transfer RPCs are not MCP tools.

The intended map workflow is returned folder next calls → exact map/level/file
metadata and grid → image info using `map` → URL using bound `source_id` with
`map_notes:true` and optional crop → revision-bound, paginated key/UUID legend.
Map browsing requires no active canvas or PF2e semantics. Raw image/portrait
workflows retain their original behavior. A single background is explicitly
distinct from foreground/Tile assets or a fully composed Scene.

| Boundary | Required budget or lifetime | Owner |
| --- | --- | --- |
| Original source | 128 MiB compressed; 32,768 pixels/edge; 128,000,000 pixels | 03a, 04a, 05a |
| Transfer | At most 32 KiB raw/chunk; at most 16 in flight; fit configured frames including envelope/base64 (65,536-byte default) | 03b, 04a |
| Transfer deadlines | 15 seconds per stalled read; 5 minutes total | 03a–03b, 04a |
| Private source snapshots | 30 minutes from staging; 512 MiB total | 04b |
| Delivered raster | 2,048 pixels/edge; 2,359,296 pixels; 2 MiB encoded; no enlargement | 06a–06b, 07a–07b |
| Preview worker | One render at a time; 1 GiB resident memory; 2 GiB private scratch; 90 seconds/render | 05b |
| Public derivative | Exactly 604,800 seconds from publication; fresh UUIDv4 per issuance | 08, 09a |
| Live derivative store | 1 GiB and 4,096 rows; prune expired records before rejecting issuance | 08 |
| Map browsing/info/legend | 10 entries and 8,000 JSON bytes by default; 100 entries and 48,000 bytes max | M01–M03a |
| Rendered note keys | 16-pixel final-output target; <=20-pixel outlined ink height; <=100 keys; <=5% label-box area | M04a–M04b |

Keep quotas and clocks injectable for tests without weakening production
defaults. Plain unauthenticated mode cannot issue links. Authenticated image
info works without a preview origin. Already-issued public images remain
readable without a connected GM until their own expiry.

## Requirement coverage and final gates

| Source-design requirement | Implementation | Acceptance evidence |
| --- | --- | --- |
| Strict inputs, exact outputs, discoverable recovery, OAuth metadata | 01, 10–11 | Actual MCP tests in 10–11, 12a |
| Exact selectors, bare references, bounded parent search, escaping and S3 boundary | 02, 03a | Resolver/bridge tests; live local paths in 14a; live S3 only if configured |
| Immutable bounded transfer, socket/world/GM checks, private bytes | 03a–03b, 04a | Fault/cancellation/concurrency tests; real multichunk workflow in 12a |
| Caller-bound snapshots, replacement bytes, expiry, membership recheck | 04b, 10–11 | Identity and replacement workflows in 12a |
| libvips isolation, format/size probe, resource enforcement | 05a–05b | Worker tests; measured large map in 12b; packaged checks in 13 |
| Exact crop coordinates, orientation, resizing/encoding, alpha and metadata | 06a–06b | Independent pixel assertions, all orientations, both large-map shapes in 12b |
| Safe SVG, advertised codecs, first-frame policy | 07a–07b | Fixtures in worker and shipped service-user image in 13 |
| Immutable anonymous seven-day GET/HEAD, expiry, quota, persistence | 08, 09a | App tests in 09a/12a; real curl and restart in 13/14a |
| Authenticated issuance, trusted origin, private storage, secret-free logs | 04b, 09a–09b, 10–11 | Auth matrix/log assertions in 09b/12a; proxy examples in 13 |
| Fresh journal fragment reconstruction and browse portrait workflow | 10–11, 12a | Actual MCP workflow and development runtime in 14a |
| Discovery/payload baseline and comparable final measurements | 01, 12b, 14a | Bounded scripts, calls/bytes/completion, catalog delta |
| Public/operator guidance and synchronized module upgrade instructions | 10–11, 13 | Examples, links, discovery prose, packaged checks |
| Target ChatGPT reads pixels and controlled query comparison | 14b external gate | Only a demonstrated target-client result qualifies |
| Scene folder hierarchy, duplicate names, correct ordering and inactive maps | M01 | Actual MCP, non-PF2e and live catalog checks in M06 |
| Grid, dimensions, level background/foreground and Tile files | M02 | Screenshot-field fixtures, paginated assets and exact selector workflow in M06 |
| Note UUID/journal/page identity, level applicability and revision-bound aliases | M03a | Bounded legend, denial/changed revision and key follow-up in M06 |
| Verified padding/shift/size/orientation and annotation snapshot mapping | M03b | Independent geometry, mutation/isolation and supported-transform gates |
| Bundled legible glyphs, safe markup, dense/edge layouts and byte retries | M04a–M04b | Glyph/pixel/coverage tests; service-user package in 13; visual review in M06 |
| Strict map selectors/flag with backwards-compatible raw-image paths | M05 | Actual discovery/invocation, one-transfer repeated crops and immutable HTTP bytes |
| Fresh folder-to-map-to-annotated-crop-to-journal workflow | M06, 14b | Bounded local evidence and separate target-client acceptance |

Local completion requires all task implementations committed, required offline
checks passing, and available local/package evidence recorded. Keep three facts
separate: implementation completion, local verification, and target ChatGPT
visual acceptance. A missing live prerequisite leaves that evidence pending;
it does not turn an unverified implementation into verified support.

For visual acceptance, a public HTTPS deployment and the target ChatGPT client
must be available. The client must identify information present only in a crop,
with expected answers held privately, and run the exact-link/query-variant
comparison in equivalent fresh contexts. If unavailable, task 14b supplies the
precise prerequisite and prompt and leaves this external gate pending. HTTP
success alone is not visual acceptance.

Reuse the root development instance, dedicated profile, and `test` world.
Create only safe marked temporary assets/documents with bounded cleanup after
offline checks; preserve existing game assets. Do not create another Foundry
instance, alter Auth0 tenants, publish deployments, or bump release versions.
Keep raw game data, capability tokens, signed URLs, private expected answers,
and bulk fixtures outside transcripts and tracked evidence.
