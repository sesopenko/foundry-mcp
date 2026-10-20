# Shared Foundry development browser

Chrome DevTools MCP is registered in this repository but disabled by default.
Use the development launcher to open a visible Chrome window and enable its
MCP tools for that Codex session:

```bash
./scripts/codex-dev.sh
# Or resume the current conversation with the new tools:
./scripts/codex-dev.sh resume --last
```

Install Python dependencies with `uv sync --locked` and browser tooling with
`npm ci` once. Browser tooling uses pinned chrome-devtools-mcp 1.10.1 and
requires Node 20.19+, 22.12+, or a newer supported Node version, plus Google
Chrome installed as `google-chrome`. Enable exploration in `.env.mcp` as
explained in [JavaScript exploration](js-exploration.md).

The launcher opens `http://localhost:30000/` in a separate persistent profile
under the gitignored `.browser-dev/chrome-profile/`. You can use this browser
normally while the agent controls the same tabs. Log into the test world's GM
account in this profile. Configure the test world's browser credential and
execution opt-in once; world settings persist across profiles and refreshes.
Browser login state persists in the dedicated profile.
The agent can perform the world-setting setup through browser evaluation once
Foundry is ready. Close the old GM tab's bridge connection before enabling the
new one: the bridge deliberately authorizes only one connected GM socket.

`./scripts/browser-dev.sh` opens the development browser by itself.
`./scripts/chrome-devtools.sh` starts the stdio MCP adapter and automatically
opens that browser if necessary. The adapter attaches to the Chrome instance
identified by this profile's DevToolsActivePort, so it reuses the same browser
across Codex connections. Chrome stays open when the adapter disconnects.
Close the development browser window when finished.

The browser debugging port is selected dynamically and accessed through
loopback. The browser profile is private (0700), and its logs and browser data
are gitignored. Usage statistics, update checks, and performance CrUX requests
are disabled in the MCP adapter. The Chromium sandbox remains enabled.
Browser debugging can access everything in this development profile; keep it
for the test world and use your ordinary browser for game sessions.

## Feedback loop

Run local tests before browser validation. Then use Chrome MCP to reload the
Foundry tab, wait for the GM bridge to reconnect, inspect console errors and
network failures, and run read-only probes through Foundry MCP. Chrome MCP can
also inspect the UI, take screenshots, and evaluate JavaScript in the page.

A new or resumed Codex session must load the configuration before native Chrome
MCP tools appear. Merely editing the config does not add tools to an already
running session. Normal `./scripts/codex.sh` sessions keep Chrome MCP disabled.
For game sessions, turn off exploration execution as described in its setup
guide and use the ordinary browser.

## Verified module refresh behavior

In the local Compose setup, `./foundry-module` is bind-mounted into Foundry.
During the October 12, 2026 test on Foundry 14.369 and world `test`, an unchanged
module successfully returned the version and world through exploration RPC.
Adding a temporary response marker left the running tab unchanged. A normal
browser refresh then returned the marker without restarting Foundry or MCP.
The marker was removed after the test; browser credentials and execution
settings also survived refresh. This establishes the behavior for this setup,
not for every proxy/cache or Foundry deployment.

| Changed component | Next action |
| --- | --- |
| Browser module JavaScript | Run focused tests, refresh the development tab, wait for `game.ready` and the GM bridge, then probe the changed behavior. |
| Python bridge code or `.env.mcp` | Run focused tests and restart the user service; reconnect the MCP client if its session is stale. |
| User service template | Run `./scripts/server.sh install`, then restart. |
| Codex MCP configuration | Start or resume through `./scripts/codex-dev.sh` so the tool catalog and credentials are reloaded. |
| Compose environment or mounts | Recreate the relevant service with `docker compose up -d`; a browser refresh does not apply these changes. |

Chrome's reload operation can finish before Foundry initialization. Wait for
`game.ready === true` and `game.user.isGM === true` before calling game APIs.
If a normal refresh fails to load a known marker, inspect the requested script
and network/cache behavior before trying a cache-bypassing reload or server
restart. Keep temporary markers local and remove them after verification.

## Connection diagnosis

Check the health endpoint first, then authenticated MCP discovery, then a
read-only runtime probe. Each confirms a different layer:

- `foundry_clients: []`: the server is healthy, but no authenticated GM socket
  is registered. Check the development tab, GM login, saved credential, and
  whether another GM tab owns the single allowed connection.
- HTTP 401: the MCP caller credential is absent or wrong; check the launcher
  and `.env.mcp` without printing secrets.
- `UnauthorizedExecution`: the browser is reachable, but its GM status,
  execution setting, or browser credential check failed.
- HTTP 400 with `No valid session ID provided` after restarting MCP: reconnect
  the MCP client. The browser can be healthy while the old HTTP session is stale.
- Chrome tools absent from the current session: relaunch via the development
  launcher. `codex mcp list` checks registration, not usable live tools.

Module settings are world-scoped as of 1.2. Configure them once per test world.
A rotated browser credential requires updating the world setting; browser login
state remains profile-specific. Avoid repeatedly pasting credentials
on ordinary refreshes. Local `.env.mcp` and browser state are deliberately
gitignored; preserve them when clearing chat context, and never copy their
secrets into developer docs.

## Validation

`./scripts/test.sh` runs all offline tests, including development opt-in,
profile endpoint validation, and credential-loading tests. Live verification
uses Chrome MCP to list the Foundry tab, evaluate a diagnostic console message,
read it back, and reload the page. No world data needs to change for these
checks.
