# foundry-module/scripts

Foundry loads `main.js` as an ES module. Its `init` hook registers client
settings; its `ready` hook starts the WebSocket bridge only for GM users.
`foundryBridge.js` dispatches RPC, while `exploration.js` implements the opt-in
development console and bounded result serialization.

`journals.js` implements read-only journal navigation, contents, search, and
source retrieval using documented public document APIs. It preserves stored
HTML/Markdown and bounds responses with continuations. See
[contracts and API dependencies](../../docs/journal-tools.md).

Run focused JavaScript tests when changing these modules. In the verified
local bind-mounted setup, a normal browser refresh loads changed JavaScript;
wait for Foundry readiness and bridge connectivity before checking behavior.
See [browser development](../../docs/browser-development.md) for the refresh
experiment, restart rules, and connection diagnosis.
