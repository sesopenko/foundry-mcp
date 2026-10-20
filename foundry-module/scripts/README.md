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

`connectionConfig.js` validates browser-reachable WS/WSS endpoints. World-scoped
settings preserve existing keys and reconnect on change rather than reloading.
The bridge emits deduplicated status notifications using documented public
`ui.notifications.info`, `warn`, and `error` methods. Settings registration,
retrieval, and `onChange` use public `ClientSettings` APIs in v13/v14; see
[operations and API references](../../docs/operations.md).

Production authentication uses a separate world-scoped bridge credential and
an explicit server acknowledgment before RPC dispatch. World settings restrict
editing but are not a confidential GM-only store. Client-scoped 1.1 settings
are not automatically copied into the world; enter intended world values once.

`buildInfo.js` contains the loaded source identity; release packaging replaces
its constant inside the ZIP with tag/commit metadata. `versionStatus.js` validates
server metadata and issues deduplicated, nonblocking operator notifications.
The read-only `getModuleBuildInfo` RPC returns the imported identity, never a
manifest fetched after installation. See [version diagnostics](../../docs/bridge-version-diagnostics.md).

PDF management uses `pdfManager.js` (GM-only registered DialogV2 settings menu),
`pdfUpload.js` (bounded acknowledged transfer), and `pdfChannel.js` (separate
request correlation on the existing authenticated bridge). The PDF upload password is visible in module configuration beside the production
bridge credential and is world-scoped. Players can read world settings; possession
of this password authorizes PDF management independently of UI role checks.
No player-facing documents, assets or chat messages contain PDFs.
