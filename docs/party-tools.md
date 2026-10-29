# Official party membership (v2.1.0)

`get_party_members` is a GM-only, read-only tool on Foundry 14.369/PF2e 8.6.1.
It discovers world parties and reads their persisted membership. It does not
read the stash or compute character Bulk, currency or wealth.

## Workflow and response

Start with `get_party_members({})`. A sole readable party auto-selects. Multiple
readable parties return `mode: "parties"` and named candidates; select one by
copying its `next_call`. The tool does not choose the UI's active party.

`party_uuid` accepts a canonical world `Actor.<id>` UUID supplied by this tool,
not a name, local ID, compendium or token UUID. With a selected party the response
has `mode: "members"`, a named `party`, and member `entries` in stored order.
Each member entry has `index` (first zero-based stored position), `status`,
`identity` and `next_call`. Resolved identities contain `uuid`, `name`,
`name_truncated`, and `type`. Names clip at 256 code points; UUIDs are intact.

For “the PCs,” select resolved members with `identity.type: "character"` and
follow `next_call` into `read_actor`. This is an explicit working definition:
character-type party members, not an inference of human control. NPCs and
familiars also have reader follow-ups. Other types have `unsupported` status.
Only world Actor references resolve; pack/token references remain unsupported.
Duplicate references appear once, retaining their first index and a
`duplicate_member_references` reason. Duplicate names remain distinct identities.

Denied and missing member identities are null. Readable unsupported Actor types
retain named identity but no follow-up. Unresolved members supply a
`member_missing`, `member_denied` or `member_unsupported` scope reason. No member
Actor source, inventory, player account, stash or campaign data is returned.

Responses contain `contract_version: 2`, `runtime`, `revision`, `mode`, `party`,
`scope_status`, `reasons`, `entries` and `pagination`.
`scope_status: "complete"` means the selected roster/candidate scope is readable;
`pagination.complete` only means its enumeration has finished. An empty complete
`members` scope is an empty party; an empty complete `parties` scope means no world
parties. An empty partial candidates scope with `parties_denied` means parties
exist but cannot be read. Auto-selection is scoped to the sole readable party
and makes no claim that inaccessible parties do not exist.

## Bounds, consistency and errors

Defaults are ten entries and 8,000 compact UTF-8 JSON bytes; limits are 1–100
entries and 8,000–48,000 bytes. Copy `pagination.next_cursor` with all original
inputs, including an originally omitted `party_uuid`. Switching an automatically
selected call to an explicit selector starts a new traversal. Candidates order
by UUID; members by first source position.

Revisions cover source membership claims and current readable identity/permission
outcomes. On `ContentChanged`, discard accumulated pages and restart.
`InvalidCursor`/`CursorMismatch` require restarting without the cursor or restoring
its original inputs. Recheck the selected party revision after a multi-character
investigation. Character reads are sequential, not an atomic group snapshot.
Incomplete membership or values cannot support a whole-party ranking.

`DocumentNotFound`: rediscover parties. `UnsupportedType`: choose a party
candidate. `PermissionDenied`: use the authorized GM/document access.
`UnsupportedSystem`/`UnsupportedVersion`: inspect `get_actor_types` and use the
verified pairing. `BridgeUnavailable`: reconnect the existing ready GM browser.
`ResponseTooLarge`: raise `max_bytes`. `ReadFailed` can indicate malformed source
membership or snapshot limits: 12,000 world Actors, 200 parties, 200 member
claims. Missing membership source is never treated as an empty list.

Requests and responses are validated through the typed FastMCP boundary. Unknown
fields, invalid selectors and bounds fail before bridge reads. Python also checks
follow-up identity, mode, scope, runtime and pagination consistency. This is a
narrow separate interface: `get_actor_types` still describes the character/NPC/
familiar `read_actor` scope. Generic party reading and stash remain unsupported.

## API evidence and remaining calculation gate

Audit: October 28, 2026. The pinned PF2e schema declares
`PartySystemSchema.details.members` as an array of `{uuid}` records:
[party schema at 8.6.1](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/party/data.ts).
Production reads that persisted schema via public `Actor.toObject(true)` and
resolves world references through `game.actors`, with `testUserPermission`.
[Official Foundry Actor documentation](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html)
was checked with Grounded Docs. Neither `PartyPF2e.members` nor the system's
`game.actors.party` accessor is used.

The wealth/Bulk plan requires matching PF2e's current calculations, not source
price/Bulk arithmetic. Source inspection found these candidate dependencies:

| Capability | Candidate dependency | Evidence |
| --- | --- | --- |
| Currency and wealth | `ActorInventory.currency`, `totalWealth` | Implementation getters; external support not established |
| Stack/attachment valuation | `PhysicalItemPF2e.assetValue` | Implementation getter; external support not established |
| Bulk and carrying status | `InventoryBulk.value`, `encumberedAfter`, `max`, `isEncumbered`, `isOverMax` | Implementation getters; external support not established |

Pinned sources:
[inventory](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/inventory/index.ts),
[Bulk](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/inventory/bulk.ts),
[physical Item](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/document.ts).
These getters are outside the declared Actor document-data fields inspected.
Their source visibility alone does not meet the repository's externally supported
API requirement. Upstream user-facing inventory documentation describes UI
behavior, not an external calculation contract. This is an unresolved support
boundary, not a claim that these getters are marked private.

This gate describes the released v2.1.0 decision. Later on October 28 the user
explicitly authorized bypassing this evidence requirement for wealth/Bulk with
defensive access and potentially missing fields. Version 2.2.0
implements `wealth`/`bulk` and optional `.items` selections under that exception;
it does not claim these getters have become supported public APIs. See the
[metric contract and verification](character-inventory-metrics.md).

## Verification

Offline checks cover official membership, multiple/empty/missing/denied parties,
non-character members, duplicates, source preservation, runtime admission, typed
MCP discovery/invocation, response validation, bounds and stale revisions.

`scripts/party-live-check.py` creates two marked inert characters and one marked
party in the existing localhost test world; it measures actual discovery,
summaries, full pagination and reader follow-ups, verifies unchanged read-time
source, tests a stale continuation by changing only the fixture, and cleans the
exact marker. Limit: 20 calls/180 seconds plus one reserved cleanup call (30
seconds). `--catalog-only` performs read-only discovery. It prints aggregate
sizes/counts, never private game data or credentials. Fixture safety tests check
the test-world guard and exact-marker cleanup without touching unrelated Actors.

October 28 live verification passed on Foundry 14.369/PF2e 8.6.1 source builds,
using 12 tool calls plus one discovery call. Both fixture members resolved to
their canonical `read_actor` identities, read-time source fingerprints were
unchanged, a changed fixture roster rejected its stale cursor, and cleanup
confirmed zero remaining marked documents and zero pending creations. No
existing game documents were modified. Console inspection before/after showed
only the existing window-size notification, with no new module errors.

| Scenario | Calls | Compact UTF-8 JSON bytes | Completion |
| --- | ---: | ---: | --- |
| Default party candidates (existing party plus fixture) | 1 | 777 | Complete |
| Selected two-character roster | 1 | 978 | Complete |
| Same roster, one member per page | 2 | 1,644 | Complete |

Actual localhost discovery grew from 22 tools/96,131 bytes before the change to
23 tools/104,170 bytes afterward. The new tool's description and input/output
schema record accounted for 8,038 bytes. The baseline had no membership tool,
so this is added capability/catalog cost, not a response-saving claim. Party
discovery has no separate evidence expansion; character inventory expansion and
the four group-calculation workflows remain blocked by the calculation gate.
Bytes are not billed tokens; provider token usage was not measured.

The final `./scripts/test.sh` passed both suites, including 611 JavaScript tests.
Packaging/import validation and the production smoke catalog include the new
module/tool. Tests for the four wealth/encumbrance answers remain future work;
party checks do not establish that those answers can currently be produced.
