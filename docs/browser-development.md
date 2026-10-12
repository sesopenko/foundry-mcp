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
account in this profile. Because this is a new profile, its Foundry client
settings initially need browser credential and execution opt-in setup once;
those settings and login state persist across refreshes and browser restarts.
The agent can perform the client-setting setup through browser evaluation once
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

## Checks

`./scripts/test.sh` runs all offline tests, including development opt-in,
profile endpoint validation, and credential-loading tests. Live verification
uses Chrome MCP to list the Foundry tab, evaluate a diagnostic console message,
read it back, and reload the page. No world data needs to change for these
checks.
