# Actor/Item development progress

[Story map](index.md) · [Reviewed contracts](../actor-tools.md)

The 39 stories retain the full agreed scope. Source checkpoints, integrated Actor views and advanced/live evidence gates are separate. Individual story headers are authoritative; regenerate a dependency-aware status report with:

```bash
./scripts/actor-tools.sh status
./scripts/actor-tools.sh check
./scripts/actor-tools.sh focused
./scripts/actor-tools.sh full
./scripts/actor-tools.sh live
./scripts/actor-tools.sh browser
```

The fixed runner accepts only those commands. `live` exercises the existing development MCP server using its caller credential from `.env.mcp`, with read-only selectors and no secret/document-ID output. `browser` inspects readiness and console-error counts in the dedicated development profile; neither command creates worlds or changes game documents. It uses installed Python/Node dependencies, performs no network setup or release, and can be approved by its script prefix for unattended checks. The full runner uses the existing repository test script. PDF subprocess tests need host execution when sandboxed child-process waiting stalls; do not repeatedly run them in the known-failing sandbox environment.

## Verified increments

### 1. Contract and dependency tracking — October 20, 2026

- CORE-contract design reviewed: canonical identities, linked/synthetic token context, explicit source/mapped/effective separation, permissions, limits, continuations, errors and version support.
- The reusable tracker validates all 39 stories, the three integrated checkpoints, direct prerequisite sets and Mermaid edges. It rejects cycles, unknown states, premature dependent completion and closing an Actor story before integration.
- Focused tracker tests cover ready transitions, graph drift, completion ordering and source/integrated status separation. Existing journal baseline passed 4 Python tests and the JavaScript journal suite before extension.
- Live availability probe: ready GM in existing test world, Foundry 14.369/PF2e 8.6.1; 172 NPCs, no character/familiar Actors. No game documents were changed. This establishes availability, not new reader verification.
- Next dependency: CORE-extract; independently delivered world/pack/token navigation and type readers follow after its focused/full checks pass.

### 2. Common source extraction — October 20, 2026

- CORE-extract delivered safe world/pack/token document resolution and permissions, common selected metadata and explicit Item description reads. Type-specific PF2e fields remain pending their stories.
- Four real MCP tools are registered: get_actor_types, read_actor, read_item and list_actor_items. Strict input/schema checks reject unknown arguments; Python validates actual JavaScript DTO fixtures and response byte/count/identity boundaries.
- Focused and full offline suites passed. Live HTTP discovery and two-page NPC, owned Item and token-instance reads passed on the existing test world after refresh/restart. No game documents changed. Independent console audit found no reader-module errors; cached errors were a core window-size warning and reconnect-period socket errors.
- Root cause of the first live attempt was connection timing after refresh/service restart; health later showed GM admission. The fixed live runner now waits for the existing bridge rather than starting another server or requesting another login.
- Next ready tasks are independent world/pack/token discovery, physical source helpers and individual Actor/Item source readers. Complete source checkpoints do not close effective/live gates.

## Open acceptance evidence

Full effective PC/familiar values, mode-specific casting resources, condition suppression/expiry and specialized Item behavior retain their named gates in the [evidence ledger](evidence.md#open-verification-gates). Do not close those gates with source-only fallback or unit mocks. The existing development session can support live NPC checks; missing populated PC/familiar fixtures remain a distinct gap.

Each implementation increment must record focused/full results and a local commit after review. No version bump, release, tag or push is authorized by this development run.
