# Official party membership and stash

`get_party_members` is a GM-only, read-only tool on Foundry 14.369/PF2e 8.6.1.
It discovers world parties and reads their persisted membership. The separate
unreleased `get_party_stash` interface below reads shared possessions. Neither
party tool computes Bulk, currency value or wealth.

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
familiar `read_actor` scope. Generic party Actor reading remains unsupported.

## Party stash (unreleased)

`get_party_stash` reads actual physical Items embedded in a world party Actor,
separately from members' inventories and Kingmaker campaign data. Use the party
UUID returned by `get_party_members`, or call without a selector to auto-select
the sole readable party. Multiple parties produce `mode: "parties"` candidates
with `get_party_stash` follow-ups. Names are never selectors. Offline players,
ownership and the UI's active party do not determine stash identity.

Selected reads return `mode: "stash"`, `basis: "source"`, a named `party`,
`revision`, `scope_status`, `reasons`, `entries` and `pagination`, plus
`contract_version: 2` and `runtime`. Each `kind: "item"` entry has an `identity`
with canonical `uuid`, persisted `name`, `name_truncated` and physical Item `type`.
Default `quantity` is `{present: true, value: ...}` when stored, or
`{present: false}` when missing; zero remains zero. Quantity is stock, not a
currency amount, effective value or derived benefit.

Use `select.quantity: false` to omit stock, `select.container: true` to add a
`container` source-presence record, and `select.follow_up: false` to omit the
default `next_call`. A stored container value is an owner-local Item ID, not a
UUID or verified containment edge; null means no container, and absence remains
explicit. Selection happens before pagination. Denied Items expose no identity
or source and add `stash_items_denied`; nonphysical Items are excluded with
`stash_nonphysical_excluded`. Either makes scope partial. An empty complete stash
means no physical possessions; an empty partial response does not.

Copy `next_call` to `read_item`, then select `source.physical`, other source
groups, exact `description` or explicit `evidence` as needed. These reads preserve
the party owner in `identity.actor`. Only actual world-party physical Items are
newly admitted: generic party `read_actor`/`list_actor_items`, token/compendium
parties and nonphysical campaign Items remain unsupported. The nine physical
types are weapon, armor, shield, equipment, consumable, ammo, backpack, book and
treasure. Serialized attachments are not extra owned Item documents.

Defaults and bounds match membership: ten entries (1–100), 8,000 compact UTF-8
JSON bytes (maximum 48,000), revision-bound cursors. Copy `pagination.next_cursor`
with all original selector, selection and bounds inputs until complete. Stash
entries sort by UUID. Revisions cover selected source values, identities and
permission outcomes, not unrequested descriptions. A subsequent `read_item` is
a separate observation; never claim an atomic snapshot across calls.

`ContentChanged` requires discarding prior pages and restarting. Restore original
inputs or restart on `CursorMismatch`/`InvalidCursor`; rediscover a missing party
on `DocumentNotFound`. Invalid selections, unknown fields and invalid selectors
fail before RPC. `ReadFailed` includes malformed stock/container source, owner
identity mismatches and the bounds of 12,000 world Actors, 200 parties and 12,000
owned Items. Ready GM, version and OBSERVER permission checks match membership.

Public core `Actor.items`, Item `parent`/`uuid`/`testUserPermission` and
`toObject(true)` supply identity and source, using the pinned PF2e8.6.1
[physical schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts).
The [party definition](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/party/document.ts)
and existing installed party template confirm correspondence to the Stash tab;
production code does not use sheet preparation, template structure or prepared
party/inventory getters. Runtime admission stays Foundry14.369/PF2e8.6.1.

Roster and stash now share world-party selection and page invariants; source
extraction remains separate. This refactoring preserves roster behavior and
avoids separate permission/auto-selection policies.

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
exact marker. The current extended verifier adds two inert party-owned Items
and stash checks. Limit: 32 calls/180 seconds plus one reserved cleanup call (30
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

## Stash verification — 2026-10-31

Implemented in source after v2.5.0; not released. Full offline checks passed
627 Python tests (one existing skip) and 652 JavaScript tests before live fixture
verification. A subsequent focused check adds heavy Unicode identity pagination
coverage and confirms exact UTF-8 byte bounds without dropped/duplicate Items.
All test execution used the host environment outside the agent sandbox.

The extended `scripts/party-live-check.py` used the existing Foundry14.369/
PF2e8.6.1 localhost `test` world and GM, with two temporary characters and one
marked party owning an inert backpack and treasure stack. Its 21 tool calls
plus one discovery call verified roster selection, default/selected stash,
two-page reconstruction, physical-source evidence and exact HTML description
through `read_item`, with actual party ownership preserved. Stock zero remained
zero. Read-time fingerprints were unchanged; deliberate fixture changes rejected
both roster and stash continuations. Cleanup confirmed zero remaining marked
documents and zero pending creations. Browser console errors were zero before
and after the check. No existing game documents were changed.

| Scenario | Calls | Compact UTF-8 JSON bytes | Completion |
| --- | ---: | ---: | --- |
| Default two-Item stash | 1 | 1,058 | Complete |
| Containers, without quantity/follow-ups | 1 | 868 | Complete |
| Same stash, one Item per page | 2 | 1,739 | Complete |
| Selected treasure physical source with evidence | 1 | 10,308 | Complete |
| Exact treasure description | 1 | 1,438 | Complete |

Default stash already supplies stock and useful follow-ups; its smaller selected
response returns different content, not equal-content savings. The two-page
workflow has greater total bytes than the default complete read. Evidence is an
explicit `read_item` expansion with a 48,000-byte requested limit. No broad
inventory or member source is required to enumerate the shared possessions.

Before the change, actual localhost discovery contained 35 tools/174,131 bytes
and party membership's tool/schema record was 8,060 bytes. Afterward it contained
36 tools/185,158 bytes; the new stash record was 10,471 bytes and the revised
membership record was 8,135 bytes. Other catalog wording also changed to explain
party-owned Item reading. This is added capability and catalog cost, not a
token-saving claim. Bytes are not billed tokens; provider usage was not measured.
