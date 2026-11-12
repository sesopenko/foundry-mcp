# Task 01 baseline — 2026-11-11

Source checkout: `2cd3d88`, before any tool changes. Server and existing dedicated
GM browser healthy. Read-only audit on Foundry **14.369**, no fixtures/mutations.
Run: `.venv/bin/python -m foundry_mcp_server.image_preview_audit` outside sandbox.
Fixed cap: 40 calls including discovery / 120 seconds. Successful run: **25 calls,
0.563 seconds**, including one discovery and one development-runtime guard.
Catalog: **43 tools / 262,218 compact UTF-8 JSON bytes**.

| Scenario | Calls | Structured JSON bytes | MCP result bytes | Complete |
| --- | ---: | ---: | ---: | --- |
| Data root default | 1 | 3,106 | 6,760 | Yes |
| Public icons/svg default | 1 | 2,096 | 4,676 | No |
| Literal anchor selection | 1 | 751 | 1,764 | Yes |
| Explicit 100-entry/48,000-byte expansion | 1 | 15,051 | 32,746 | No |
| Complete icons/svg default traversal | 12 | 25,373 | 56,524 | Yes |
| Journal navigation | 2 | 6,989 | 15,192 | Yes for last page |
| Journal contents default | 1 | 911 | 2,118 | Yes |
| Journal contents expanded | 1 | 1,605 | 3,584 | Yes |
| Journal page default | 1 | 590 | 1,428 | Yes |
| Journal page expanded | 1 | 902 | 2,088 | Yes |
| Complete journal page default traversal | 1 | 590 | 1,428 | Yes |

The selected existing journal/page selectors are retained privately in ignored
`.local/image-preview-baseline-selection.json` for later equal-content replay.
No content or identifiers are in this report. The small page is not evidence for
large/fragmented-page performance; integration tasks own synthetic heavy cases.
Byte counts are not tokens. MCP result counts serialize the protocol content,
structuredContent, isError and metadata fields, excluding transport framing;
they capture text/structured duplication. Completion applies to that stream,
not world-wide exhaustiveness. The runtime guard returned 62 structured bytes /
328 MCP bytes and is not a retrieval scenario. The full catalog remains unchanged.

## API evidence

Grounded Docs `list_libraries`, `find_version(foundry-vtt,14)`, bounded
`search_docs(FilePicker browse implementation sources, limit=2)` and a fresh
`fetch_url` of the official
[FilePicker page](https://foundryvtt.com/api/v14/classes/foundry.applications.apps.FilePicker.html)
confirm public `implementation`, `sources`, `extensions` and static
`browse(source,target,{bucket?,extensions?,wildcard?}): Promise<object>`.
These have no protected/private annotations; underscore/protected members on
the same page are excluded. Task 01 adds no new Foundry dependency or calls.

Index status: completed; source `https://foundryvtt.com/api/v14/`, indexed
2026-10-12T22:52:58Z, 1,978 URLs / 17,801 chunks. Runtime build is 14.369;
matching major and a fresh official fetch do not establish exact-build behavior
for later dependencies. Actual public data/public browsing passed here. S3 is
not configured/verified by this audit; task 02 owns mocks and task 14a records
the configured-S3 prerequisite for live evidence.

## Harness diagnosis

The first attempt stopped after two calls with AttributeError, before browsing.
Cause: pinned FastMCP `CallToolResult` is a dataclass; the initial harness called
Pydantic `model_dump` on it. A focused test using the actual SDK type failed
(runtime version missing) before the correction. Serializing through the MCP
protocol result model corrected the cause; the unchanged test passed and the
successful bounded live audit above followed. No project runtime behavior or
assertion was weakened. Unsuccessful correction attempts: zero.
