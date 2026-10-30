---
name: foundry-dev-loop
description: Run the edit, test, browser-refresh, console-inspection, and live-RPC feedback loop for Foundry module or bridge development in this repository. Use when implementing or verifying developer changes, not during game sessions.
---

Use the repository's AGENTS.md testing and development-browser guidance.
Read [browser development](../../../docs/browser-development.md) for restart
rules and [architecture](../../../docs/mcp_foundry_architecture.md) when choosing
between Chrome control and Foundry RPC.

## Establish evidence before editing

Confirm the dedicated development tab is ready, logged in as GM, and connected
to Foundry MCP. Preserve unrelated edits. Capture a compact read-only baseline
relevant to the intended change; do not infer live behavior from mocks alone.
If connectivity is the issue, follow the browser guide's diagnosis rather than
expanding the code change to compensate for a stale MCP session.

## Test continuously

Cover relevant existing behavior before extending it. Add regression tests
alongside new behavior and run focused checks after meaningful edits:

- Python: `.venv/bin/python -m unittest discover -s tests -p 'test_<area>.py' -v`
- JavaScript: `node --test tests/js/<area>.test.js`
- Full offline suite before committing: `./scripts/test.sh`, except for commits
  with at least one staged change and only case-sensitive `.md` paths (both
  sides of renames). These need no local tests or confirmation; retain applicable
  documentation link, example, consistency and whitespace checks. Unstaged files
  do not affect this exception; GitHub Actions still runs tests. See the
  [commit hook policy](../../../README.md#unit-tests-and-commit-hook).

These commands use installed dependencies without uv cache/network access.
Resolve failures before continuing dependent work. Provision dependencies
separately only when needed.

## Verify the running change

- For browser JavaScript, use Chrome MCP to reload the selected development
  page after focused tests pass. A normal refresh loaded bind-mounted module
  changes in the verified local setup; avoid restarting Foundry or MCP unless
  evidence or the changed component calls for it.
- Wait for Foundry readiness and the authenticated GM socket after refresh.
  Chrome's reload completion does not mean `game.ready` is true.
- Inspect new console errors and relevant failed script/network requests.
  Probe the intended behavior through Foundry MCP when validating bridge tools;
  use Chrome evaluation for UI state and browser diagnosis. Read-only probes
  are the default; mutations must belong to the requested test-world task.
- For Python/configuration changes, apply the browser guide's restart matrix
  and reconnect stale MCP HTTP sessions. Verify changed tool registration in
  the current client, not just in configuration files.
- If cache behavior is uncertain, use a unique temporary response marker:
  confirm the old tab lacks it before refresh and the refreshed tab returns
  it afterward. Remove the marker and restore test state when finished.

Report the observed before/after behavior, focused/full test results, and any
remaining live verification gap. Do not claim success from server health or a
page reload alone. Commit only when requested or otherwise authorized by the
current task; follow the commit hook policy above for required checks.
