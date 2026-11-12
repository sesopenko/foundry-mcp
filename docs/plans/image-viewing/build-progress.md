# Image viewing build progress

- Current task: 01, [contracts and baseline](tasks/01-contracts-and-baseline.md).
- Stage: commit.
- Last completed task/commit: none. Baseline checkout: `2cd3d88`.
- Assignment preserved in [execution prompt](../../prompts/foundry-image-viewing-build-agent.md).
- Persistent goal: active; environment objective points to the attachment containing the complete persistent goal, read at kickoff.
- Baseline checks outside sandbox: `.venv/bin/python -m unittest discover -s tests -p 'test_journal_images.py' -v` passed 4 tests; `node --test tests/js/journal-images.test.js` passed 6 tests.
- Focused final commands: `.venv/bin/python -m unittest discover -s tests -p 'test_image_preview*.py' -v` passed 13; journal-image Python command passed 4; browser command passed 8. All outside sandbox.
- Full `./scripts/test.sh`: initial and final implementation runs passed both suites (717 JavaScript tests; Python retains its existing skip). Repeated full run was justified by the audit serializer/error-helper changes after the initial run started.
- Audit diagnosis: first live audit stopped after discovery/runtime guard (2 calls), AttributeError before aggregation. Pinned FastMCP CallToolResult is a dataclass, not Pydantic. The actual-SDK-type regression failed (missing runtime version); correction serializes via the MCP protocol result model. Unchanged test passed. Unsuccessful fix count 0.
- Live baseline: `.venv/bin/python -m foundry_mcp_server.image_preview_audit` passed, 25 calls including discovery/0.563s; 43 tools/262,218 bytes. Full [measurements](baseline.md). No game assets/documents changed; no fixture cleanup needed.
- Decisions: retain the existing strict ImageSelector unchanged; add internal preview-only contracts and budgets without registering placeholder tools.
- API evidence: Grounded Docs foundry-vtt@14 exists; FilePicker browse/sources/implementation searched and official page fetched. Index completed 2026-10-12T22:52:58Z, 1,978 URLs/17,801 chunks. Runtime compatibility still requires task-specific checks.
- External gaps: target ChatGPT/public HTTPS acceptance pending tasks 14a/14b; no deployment/client acceptance claimed.
- Next action: inspect/stage task 01 changes, commit, resolve SHA and start task 02.
