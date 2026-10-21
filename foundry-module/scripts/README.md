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

`actors.js` provides the read-only Actor/Item extraction handlers; `actorDocuments.js`
resolves public documents, permissions and canonical world/pack/token context,
and `actorReadUtils.js` provides detached revision/text/pagination utilities.
Only common source metadata and explicit Item descriptions are delivered by the
foundation; type-specific mappings/effective values remain staged. See
[the contract and version boundary](../../docs/actor-tools.md).

Actor discovery modules `actorWorld.js`, `actorScenes.js` and `actorPacks.js` use public document relationships and selected pack indexes. Python discovery adapters validate their bounded DTOs and expose self-contained tool contracts. Scene navigation retains current token Actor identity; effective token state remains a separate acceptance gate.

`actorAction.js` selects persisted PF2e action fields. `actors.js` maps their activation discriminator and resolves immediate self-effect references only for explicit relationship requests, preserving synthetic target context and rechecking authorization. It never applies an effect or evaluates an action.

`actorMelee.js` selects authored NPC attack source and additional-effect labels. Null source range does not rule out thrown traits; source damage and bonuses never come from carried gear or preparation. `actors.js` emits named unresolved relationships without guessing selectors.

`actorLore.js` selects persisted PF2e Lore source. Actual owner type controls
modifier/rank terminology; rank labels never become calculated totals. `actors.js`
exposes owned specialties as canonical references in a partial Skills section,
retaining duplicate identities, permissions and selected token context.

`actorNpc.js` selects authored NPC stat-block source and retained exception
notes without applying elite/weak math. Biography requires explicit `description` selection with separate blurb/public/private paths;
source responses remain partial and effective sections unsupported.

NPC explicit `strikes`/`abilities` select actual owned melee/action references,
with source-name/type provenance and preserved linked/synthetic token selectors.
Denied Items are not read or named; effective completeness remains unsupported.

`actorEffect.js` selects persisted PF2e effect source with discriminated badge
branches and primitive context leaves. It never evaluates formulas, applies
source defaults, reads prepared expiry or resolves source UUID references.
