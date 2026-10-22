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

`actorEffectRelationships.js` resolves explicit immediate effect context through
existing authorized Actor/Item public-API boundaries. Actor/token mismatches never
fall back to base templates; unresolved targets return no resolved metadata.

`actorCondition.js` selects persisted condition/value, persistent damage and local
reference source. Override slugs remain distinct from local Item IDs. No prepared
activity, suppression, persistent-damage roll or effective duration is read.

`actorConditionRelationships.js` follows local IDs through the actual owner Item
collection and public identity/permission boundary. Override slugs remain named
unverified claims; no target source or active/suppressed state is read.

`actorAffliction.js` is an offline schema-research selector, excluded from the
runtime package. PF2e8.6.1 production disables afflictions; public reader admission
rejects them before source access and discovery reports support false. No guard
is bypassed and no fixture constructor is invoked.

`actorWeapon.js` selects weapon definition/configuration fields alongside shared
physical source without duplicate paths. It never generates Strikes, recalculates
NPC attacks, hydrates selected ammunition or prepares alternate-use results.

`actorWeaponRelationships.js` resolves explicit stored selectedAmmoId through
actual owner membership and public identities. It does not use prepared ammo,
loaded subitems, compatibility checks, consumption or effective attack values.

`actorAmmo.js` selects persisted ammo use/crafting/metadata fields alongside
shared stock source. No consumption, rule application, attack calculation or
reverse weapon selection occurs; weapon references remain explicit reads.

`actorArmor.js` selects stored armor constraints/runes/baselines beside shared
physical source. No Actor AC, saves, Speed, worn benefits or prepared usage is
read or calculated; attachments retain serialized source paths.

`actorShield.js` selects shield/rune/integrated source alongside physical HP and
hardness. It preserves HP above source max without clamping, never infers raised
state, Shield Block access, effective reinforcement or generated attacks.

`actorEquipment.js` selects equipment traits and publication alongside shared
usage, investment and attachment metadata. Explicit bounded description retains
prose abilities; no active benefits or activation resources are inferred.

`actorConsumable.js` selects category, uses, healing/damage and contained spell
metadata alongside common stock source. It reuses the full spell source/prose
allowlist with consumable provenance and separate source paths; no nested entry
resolution, consumption, formula roll or castability calculation occurs.

`actorSpell.js` selects spell definitions, partial heightening/overlay patches and
explicit source prose without preparing variants. `actorSpellRelationships.js`
follows stored owner-local entry IDs through actual Item identities; no casting,
slot evaluation or target entry source is read.

`actorSpellcastingEntry.js` selects stored casting modes and individual resource
records. Legacy/malformed preparations remain explicit partial source with safe
siblings retained; no exhaustion, focus pool, innate uses or effective castability
is inferred from slot counters. Template slot11 has no spell-rank semantics.

`actorCasting.js` builds Actor source-only casting joins from actual readable
Items, preserving individual preparations and focus-source provenance. Every
casting section remains partial with availability_not_evaluated; character focus
max, effective options, casting and resource use are not inferred.

`actorContainer.js` selects backpack/container Bulk configuration and metadata.
`actorContainerRelationships.js` builds explicit same-owner containment claims
from persisted containerId without prepared contents or Bulk calculations. Each
readable descendant appears once; cycles, invalid parents, denial and unowned
scope are explicit, with public canonical identities and token context.

`actorTreasure.js` selects nullable valuables categories and metadata alongside
shared quantity/denomination/price-per source. It never uses derived asset values,
stackGroup, synthesized usage or investment, conversion or sale arithmetic.
