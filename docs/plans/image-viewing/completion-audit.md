# Image-viewing completion audit

This audit keeps implementation/local verification separate from external client
acceptance. The [30-task commit ledger](README.md#dependency-graph-and-checkpoints)
and [durable execution record](build-progress.md) own task-by-task evidence.
The [original execution assignment](../../prompts/foundry-image-viewing-build-agent.md)
and [source design](../../prompts/foundry-image-previews-plan.md) remain intact.

## Requirement reconciliation

| Design requirement | Authoritative implementation and evidence |
| --- | --- |
| Strict exclusive image/src/map inputs; URL-only source_id/crop/map_notes; exact technical results/default omissions | Typed image/map models; actual MCP tests in `test_image_preview_tools.py`,`test_map_image_tools.py`; native14a/M06 discovery/calls |
| Canonical/bare selectors without prior browse; fresh bounded parent membership, encoding/prefix/local/S3 boundary |02 source resolver and03a browser fetch; source/fetch/transfer tests; native journal/browse/core SVG; live S3/prefix gaps below |
| Immutable transfer,32KiB chunks/16 window/frame overhead,15s stalled/300s total, exact socket/world/GM cleanup |03a/03b/04a components and browser/Python protocol tests; real multichunk actual-MCP integration and native source staging |
| Caller-bound originals,30min/512MiB, replacement bytes and expiry/permission isolation |04b cache/identity tests, M05 atomic private map attachment; actual Basic/OAuth boundary and replacement/cancel workflows |
| pyvips/libvips metadata and original128MiB/32768-edge/128mpx limits |05a probe and format tests, all8 display orientations, service-user package smokes; Pillow upload13 regressions preserved |
| One worker,1GiB RSS/2GiB scratch/90s, bounded native caches, abort/reap/cleanup |05b separate admission/workspace/child/monitor/coordinator tests and real exhaustion/recovery; measured12b/M06 large maps. RSS is sampled25ms plus scan/scheduling latency, not an instantaneous hard cap |
| Strict contained original-pixel crop, half-open edges, orientation, Lanczos3/alpha/sRGB/no enlargement |06a independent pixel/orientation/alpha tests;12a/12b native borders/onepixel/wide/map-region oracles; M06 independent annotated pin/corner pixels |
| PNG then WebP90/82,15% reductions from original region;2048-edge/2359296px/2MiB; metadata removed |06b real encoding/container tests and M04b per-attempt annotation recomposition; native exact MIME/dimensions/length/curl decoding |
| JPEG,PNG/APNG,WebP,AVIF,BMP,GIF,TIFF first-frame/page,96-DPI safe SVG |07a/07b real format/pixel and external-resource rejection tests; all9 advertised families in UID10001 shipped image; core SVG native path |
| UUID4 immutable derivative, seven-day exact expiry, digest-only SQLite,1GiB/4096 quotas/atomic publication |08 store tests and real SQLite workflows; exact604800 boundary with pruning paused; distinct issuances and quota retention |
| Anonymous exact GET/HEAD path only, query ignored, raw MIME/length/no-store/nosniff/no redirects/cookies/wrapper |09a production-app tests;14a15 native curl checks plus M06 annotated fetches;13 real packaged listener and same-volume recreation |
| Authenticated issuance/ready GM, disabled-origin-first, Basic/OAuth/dev policy, no plain-none minting |09b actual four-mode HTTP/JWT/WS/PDF matrix;10/11/M05 actual discovery/call validation and native configured/unconfigured flows |
| Trusted independent HTTPS origin, private UID10001 store/volume, durable restart, preserve originals outside route |13 Basic/OAuth/templates/README/Docker overview validated in10 synthetic Compose cases; shipped container recreation retained identical bytes |
| Capability-safe access/evaluation/proxy logs and bounded model-visible metadata |09b privacy/evaluation tests including actual Uvicorn formatter;14a curl uses private stdin config; operator proxy guidance linked below |
| Fresh stored journal image tag across fragments; direct bare-src and browse portrait workflows |12a actual MCP/Node/app workflows;14a native4-fragment reconstruction, source-handle repeated crops, browse selector and SVG |
| Real10000-square and10000x5000 independent geometry/resources/payloads |12b17-call/11-fetch large workflow; M06 real10000-square annotated overview/detail; resource values below |
| Scene-folder browse, duplicates/manual order/readability/inactive/non-PF2e | M01 and M06 actual MCP/JS tests; native complete18-folder/50-map navigation with16 duplicate names and unchanged active Scene |
| Exact Scene/grid/levels/background/foreground/missing/video/Tile metadata, scene/file dimension distinction | M02 typed/public schema tests and screenshot fixtures; M06 full3-level/Tile workflow and native grid/public-document comparison |
| Bounded10/8000 defaults,100/48000 maxima, typed responses, revision/caller/scope-bound continuations and actionable errors | M01–M03a/M05 model/RPC/MCP tests; full native catalog and rendered-key legends paginated to completion |
| No private Foundry internals, public relationship/Note applicability/rectangle/default-texture contracts | Versioned Grounded Docs and installed/runtime reconciliation in map-context/map-note docs; no protected tooltip/mesh/DOM dependency |
| Stable complete-level Note aliases, permitted label/journal/page identity without journal bodies, denied/missing/unlinked scope | M03a permission getter traps, duplicate pins and exact legend tests; M06 independently matches27 returned Note/journal/page identities |
| Source-bound map geometry/revision/aliases, default14.369 mapping, source-size/orientation/padding/shift, stale rechecks | M03b23 context/geometry tests; M05 source-cache attachment and mutation checks before/after publication; unsupported mappings preserve raw previews |
| Fixed bundled licensed font,16px final target/<=20px ink, generated ASCII only, recompose each retry | M04a deterministic fontfile/SHA/isolated Fontconfig tests, M04b native retry pixels; UID10001 package; measured native ink14px |
| Numeric alias priority, disjoint label/leader/pin extents,4px gaps,<=100 keys/5% boxes, crop centers and explicit omissions | M04b15 layout/encoding tests; M05 dense/collision legends; M06 one-pixel omission/detail recovery and native coverage review |
| Optional exact map selector/strict flag, default field omission, foreground/raw fallback, private signed references | M05 actual discovery/invocation and HTTP/S3-mock/isolation/cancellation tests; M06 shared-source Scene ownership |
| Full folder→level→annotated crop→exact key legend workflow and complete byte/call measurements | M0611-call fixture with1 transfer; native35-call workflow/4 legend pages; detailed stream tables in map-workflows.md |
| Core tools not blocked by a PF2e-only module manifest | M06 actual ZIP regression failed before removing system restriction and passed unchanged; PF2e Actor/Item guards/full regressions retained |
| Hidden private pixel answer, separate fresh exact/query trials, separate map/key target prompt, cleanup and honest status |14b private challenge/report/preparation modes and handoff tests; no real target-client observations available, explicitly pending |
| Every task meaningful unit tests, full regressions and its own authorized local commit |30-task ledger, task records and Git history; all tests/hooks outside sandbox; final14b checkpoint records final totals |
| Preserve instructions/recovery/progress; diagnose then unchanged test; no push/release/new Foundry/existing asset writes | Saved execution prompt and amended supervisor refactor; progress/root-cause records and local commits; scoped fixture owners/cleanup; no publication performed |

## Material measurements and demonstrated workflows

- 12b10000-square overview:1536² PNG1638691B; sampledRSS351961088B,
  scratch301645824B,0.445672s. Wide10000x5000:2048x1024 PNG921407B,
  RSS200380416B/scratch150925312B/0.299555s. Independent native crops pass.
- M06 annotated10000-square overview:1536² PNG1487372B with2keys;
  RSS394256384B/scratch301494272B/0.505164s; native150² detail1546B with
  independently verified corner/pin pixels. Limits were not raised.
- Native map:6800x9000 source,1335x1767 WebP633428B overview25/25 pins and
  800x600 PNG508560B detail2/2. Complete rendered-key legends:4 pages/27 rows,
  independently matching journal/page identities. Ink14px; label boxes occupy
  .427903%/.160417% respectively. Agent visual review does not prove target-client
  readability or guarantee zero obstruction.
- Development catalog47 tools/323516 compact SDK-model bytes; entire catalog
  navigation21 calls/46260 JSON/101532 MCP bytes, exactly matching M01's measured
  complete-navigation sizes. These are bytes, not billed tokens.
- Shipped image UID10001 with pyvips3.2.0/libvips8.18.7/Pillow13.0.0 passes
  codec/font/annotation/unsafe-SVG/private-store and same-volume recreation.
  Native14a exact/query/HEAD uses anonymous curl through local TLS with explicit
  fixture CA, no redirect following or reader credentials.

Detailed records: [large maps](large-map-measurements.md),
[runtime acceptance](runtime-acceptance.md), [map workflows](map-workflows.md),
[packaging/operations](../../image-viewing.md), [visual handoff](visual-handoff.md).

## Explicit remaining external gates

Final full suites pass1053 Python tests (1 existing skip)/795JS; focused
handoff10 passes0.157s and helper12 passes1.387s. The final production-image
build and complete UID10001 codec/annotation/listener/same-volume recreation
probe pass for
`sha256:0809b39f1da3dab32fb33ee33839d59ce825504c5f0ad84af2160cdff70054ad`,
with exact owned-container/volume cleanup. Compose10 and module ZIP checks pass.
Native handoff preparation/exact cleanup passes without issuing any URL.
The final required commit hook verifies the same staged implementation.

| Unavailable check | Exact prerequisite and handoff |
| --- | --- |
| Real target ChatGPT journal-pixel workflow, exact/query controlled host comparison and map/key workflow | Actual target ChatGPT with refreshed tools, matching authorized GM bridge/test world and an operator-provided public trusted HTTPS preview origin on authenticated Basic/OAuth MCP. Use14b private prompts in four distinct contexts and retain reviewed actual-client traces. Status remains pending; local TLS/curl/image inspection is not substituted |
| Live configured S3 byte reads | An existing readable configured bucket with correct browser CORS. Signed S3 mocks pass; no live bucket is claimed |
| Nonempty Foundry route-prefix runtime | An existing prefixed development deployment; escaping/prefix mocks pass. No extra Foundry instance is provisioned |
| Real Auth0 login/refresh | Existing authorized operator/client setup under the separate OAuth verification runbook. Offline signed-JWT/HTTP policy passes; no tenant mutation or login claim |
| Additional non-PF2e live world/core builds | Existing authorized world/build when available. Non-PF2e mocks and unrestricted manifest pass; annotations are explicitly supported only for verified default14.369 placement |

All independently available local/package/MCP/runtime work is required before
task completion. The external gates above are precise unavailable acceptance
checks, not unfinished code or failing tests. Temporary game/TLS/review fixtures
are removed; the ignored private14b handoff bundle is deliberately retained,
with fixture readiness false until an operator prepares the actual external trial.
