---
name: foundry-dev-connect
description: Establish or diagnose this repository's local Foundry development browser, authenticated MCP discovery, and GM bridge connectivity. Use for development setup or failed connections, not game sessions or Foundry upgrades.
---

Work from the repository root with its AGENTS.md guidance. Read
[shared browser setup](../../../docs/browser-development.md) and, when
credentials or execution settings need attention,
[exploration configuration](../../../docs/js-exploration.md).

## Establish the connection

- Check `curl -fsS --max-time 3 http://127.0.0.1:8000/health`; use the existing
  user-service launcher if it is unavailable. Do not create another Python
  server. A sandbox-localhost failure alone does not establish host downtime;
  retry through the command tool's approved escalation when needed.
- Check which MCP tools are actually available. A session launched with
  `./scripts/codex-dev.sh` should have Chrome tools; Foundry exploration also
  needs the caller credential loaded by the underlying Codex launcher. If
  tools are missing, complete independent setup and report the exact relaunch
  command. Do not imply that registration adds tools to an existing session.
- For an authorized development setup, `./scripts/browser-dev.sh` opens or
  reuses the dedicated profile. Native Chrome tools are preferred when present.
  Enumerate pages and select the Foundry development tab by URL; never assume
  page ID 1 or attach to the ordinary browser.
- Wait for `game.ready` and GM status after navigation. Read only credential
  presence and execution-setting booleans for diagnosis. Save credentials and
  opt-in once in this profile/site when setup is authorized; setting changes
  reload the page, so wait for readiness between them. Never print token values
  or record them in tracked files or tool-result summaries.
- Only one authenticated GM socket is admitted. Identify the owning test-world
  tab before switching; disconnect its bridge or close that development tab
  within the user's task scope. Do not close unrelated browsing tabs.
- Verify authenticated discovery, then call `execute_javascript` with
  `return { version: game.version, world: game.world.title, isGM: game.user.isGM };`.
  Report the actual world/version and whether browser control and Foundry RPC
  both work. Health alone is not end-to-end verification.

## Diagnose the failing layer

Use the connection-diagnosis section of the browser guide. Distinguish no GM
socket, caller HTTP 401, browser UnauthorizedExecution, missing tool discovery,
and stale HTTP session IDs after server restart. Repair the failed layer once
and verify; do not repeatedly restart a healthy server or rotate working
credentials to compensate for an unconnected browser. If GM login or a fresh
Codex session is required and unavailable to the current tools, report that
specific remaining action after completing independent setup.
