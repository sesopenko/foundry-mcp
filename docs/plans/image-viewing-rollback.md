# Image viewing rollback execution plan

After automatic compaction, reread this entire plan before further work,
inspect Git status/diff and this progress record, and resume the first
incomplete phase. Execute sequentially; deliver tests with each phase and run
its targeted unit tests before proceeding. All tests run outside the sandbox.

Remove preview work after `5188fbe` through `7923d09`. Retain earlier journal
image browsing, embedding and uploads; preserve discovery fix `bd600bd`, its
tests/documentation and current testing guidance/approval rules. Keep all
versions at 4.0.0. Preserve existing preview disk data and Docker volumes.
Create one local rollback commit after all checks pass; no push, tags,
publication, history rewriting or existing release changes.

## Phases (34 points total, maximum 8)

1. **Public interfaces — 5 points.** Capture bounded actual MCP discovery and
   representative response baselines. Remove four preview/map tools and HTTP
   delivery routes, disconnect preview lifecycle services. Add absent-tool,
   retained-tool and HTTP 404 regression tests. Run discovery, HTTP/lifecycle
   and retained-image tests.
2. **Browser support — 5 points.** Remove preview transfer/map RPCs and bridge
   lifecycle integration; restore pre-preview shared journal image code.
   Remove obsolete fixtures/tests, retain handler/dispatch regression coverage.
   Run journal image, upload, authentication and bridge JS tests. Refresh the
   dedicated browser and check connectivity, console and read-only browsing.
3. **Server internals — 8 points.** Remove preview transfer, snapshots, workers,
   rendering, maps, capabilities, fonts, feature-only helpers/tests/harnesses.
   Update shared app/auth/evaluation tests as needed; run these and uploads.
   Audit remaining imports for deleted modules.
4. **Packaging — 5 points.** Remove preview-only dependencies, Docker probes,
   storage setup, environment and volume declarations. Restore pre-feature
   module compatibility. Preserve synchronized 4.0.0 identities. Deliver/run
   packaging/configuration tests, dependency and Compose checks, archive validation.
5. **Documentation — 3 points.** Remove preview plans/prompts/operating docs;
   reconcile README, architecture, journal images, operations, Docker overview.
   Preserve discovery evidence and testing guidance. Check links, examples,
   whitespace and stale references; run discovery/packaging tests.
6. **Runtime acceptance — 5 points.** Finish regression coverage; run discovery,
   HTTP, bridge and retained-image tests. Restart local server, refresh dedicated
   browser, verify real discovery, route removal, connectivity and retained reads.
   Account for every difference from `5188fbe`.
7. **Full suite and commit — 3 points.** Run `./scripts/test.sh` successfully for
   both suites. After any correction run targeted tests and the full suite again.
   Review/stage changes and make one local rollback commit.

Record exact runtime gaps; do not equate mocks with live verification. Full
suite failures block completion. ChatGPT fetching diagnosis is out of scope.

## Progress and evidence

- Initial worktree clean. Local service started through `scripts/server.sh`.
- Before changes: discovery protocol tests passed (3 tests), including actual
  negotiated HTTP sessions. No feature changes made yet.
- Phase 1 complete: rollback audit (2), discovery protocol (3), application (6),
  journal images (4), uploads/retrieval (13) passed. Two-call bounded audit:
  catalog 46 tools/320,730 compact UTF-8 JSON bytes before, 42/259,324 after;
  retained complete browsing response 434 bytes both times. Embedding is a
  write_journal operation, not a standalone tool; corrected new test assertions.
- Phase 2 complete: 34 targeted JS tests passed (journal images, uploads,
  authentication, bridge, main), including removed-RPC rejection. Dedicated
  browser refreshed: ready GM, Foundry 14.369, zero console errors. Retained
  browse_journal_images live call returned one bounded entry (8 total).
- Phase 3 complete: removed preview/map server internals, native font and
  obsolete feature tests/harnesses; restored shared config/evaluation code.
  Targeted application (6), production auth (13), evaluation (7), uploads (13)
  and rollback (2) tests passed. Remaining references are confined to packaging
  files scheduled for phase 4 and explicit removal regression assertions.
- Phase 4 complete: packaging tests (5) passed with new archive/dependency/
  deployment removal coverage. Module archive validated for v4.0.0. Locked
  environment sync removed only pyvips and pyvips-binary; Pillow retained.
  Basic and OAuth Compose configurations validated using placeholder values.
- Phase 5 complete: removed obsolete feature docs/plans/prompts and reconciled
  public/operator guides. Discovery history and current test rules preserved.
  Added source-only deployment clarification: published v4.0.0 assets unchanged.
  No links to deleted feature docs remain; whitespace check passed. Discovery
  protocol (3) and packaging (5) tests passed again.
- Phase 6 complete: final targeted rollback (3), discovery (3), journal images
  (4), uploads (13), journal authoring (18), and JS bridge/images/uploads (28)
  tests passed. Restarted existing server and refreshed dedicated browser:
  ready GM, Foundry 14.369, zero console errors. The eight-request read-only
  live verifier passed: 43 tools (includes development console), connected
  matching 4.0.0 source builds, one bounded browsing entry and four HTTP 404s.
  No fixtures, existing documents, deployment or stored preview data changed.
  Compared to 5188fbe, production implementation differs only by synchronized
  version metadata and the preserved two union-schema discovery fixes. Other
  differences are preserved test guidance, discovery evidence, current-version
  documentation and rollback tests/acceptance tooling/progress record.
- First full-suite run: 704 Python tests, two failures (one existing skip);
  JavaScript not reached. Root cause reproduced with the unchanged focused
  release-helper tests: the new archive-removal test introduced a second
  hard-coded tag marker in test_packaging.py, violating the helper's deliberate
  single-marker guard. Removed only the redundant tag argument from that new
  test; archive-content assertions and the release helper remain unchanged.
- Phase 7 validation complete: release-helper (4) and packaging (5) focused
  tests passed after the correction. Full `./scripts/test.sh` passed: 704 Python
  tests in 46.830s (one existing skip), all 716 JavaScript tests in 6.946s.
  Whitespace checks passed. This local rollback commit delivers all seven
  phases; publication and changes to existing release assets remain excluded.
