# Actor Build source contract

`read_actor(actor_uuid=..., sections=["build"])` returns the implemented,
GM-only PF2e character Build source section on Foundry14.369/PF2e8.6.1. Use
`token_uuid` for a selected token instance; claims stay within that actual owner
without substituting its base Actor. Other systems are rejected; NPC and familiar
Build sections are `unsupported`. No effective benefits or totals are computed.

## Owned identities and source

Each actual readable owned ancestry, heritage, background, class, deity, feat
and Lore Item appears once as a `build_item` relationship keyed
`build:item:<Item UUID>`. Multiple contributors retain separate claims rather
than duplicate the owned benefit identity. Direct persisted claims may introduce
identities of other supported owned Item types except afflictions; their typed
source is not expanded, and grants are not traversed recursively.

Records retain `key`, `section`, `kind`, `raw`, `mapped` and `provenance`.
`section` is `build`; `mapped` contains `concept`, `value`, `unit:null`.
`provenance` contains exact `contributors`, `mapping`, `limitations`. Raw entries
contain `document_uuid`, JSON-pointer `path`, `present`, `basis:"source"`, and
`value` only when present. Identity records retain `/name` and `/type`; resolved
values contain `status:"resolved"`, `target_uuid`, `document_name:"Item"`,
`type`, `name`, `name_truncated` and, in token context, `token_uuid`. Names are
bounded to 256 code points. Follow `read_item` with the returned instance context.

Fields use `build:source:<donor UUID>:<escaped source path>`, `kind:"field"`
and the original `pf2e.<type>.source.v1` mappings. Offered/selected/alternate
choices, feature categories, nominal/taken levels, metadata, HP/rank
contributions, deity options and future definitions remain source. Recorded
feat selections preserve string/finite-number leaves; unsupported values are
withheld and diagnosed. Definition UUIDs, names, slugs, Lore labels and recorded
selections never establish acquisitions. Duplicate training does not create
replacement training or another Item.

## Persisted grant claims

The common `itemGrantFields(source)` selector uses PF2e8.6.1
[ItemSourceFlagsPF2e, ItemGrantSource and ItemGranterSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts)
and the audited [grant contract](feat-grant-contract.md). Build selects neutral
`grant_entries`, `grant_item_id`, `grant_delete_policy`, `grant_nested`,
`granted_by_source`, `granted_by_item_id`, `granted_by_delete_policy` concepts,
mapping `pf2e.build.grants.v1`, and limitation
`stored_grant_claim_not_active_benefit`. Presence, null, empty maps and escaped
opaque keys remain distinct. The selector retains its 12,000-entry map bound.

Every selected grant-ID field also produces a relationship keyed
`build:claim:<donor UUID>:<escaped source path>` with concept `build_grant_claim`
or `build_granted_by_claim`, mapping `pf2e.build.claim.v1`, and limitation
`persisted_claim_not_causality_or_active_benefit`. Only exact IDs in the actual
owner's Item collection resolve. Unresolved values have `status:"missing"`,
`"denied"` or `"unsupported"` and `target_uuid:null`; validation also admits
`"unverified"`. A readable donor's stored ID remains visible while denied
target metadata stays withheld.

Claim values include `reciprocity`. A resolved outgoing claim reports `agree`
when the target's stored `grantedBy.id` equals the donor ID, `disagree` for a
different string ID, or `absent` for an absent inverse field or absent/null
parent. Exact inverse raw evidence accompanies the donor claim. Incoming and
unresolved claims report `not_evaluated`. Agreement establishes matching stored
claims only, without causality, eligibility or active benefits. No rules execute,
grants import, missing Items appear or effective totals are calculated.

## Validation, privacy and continuation

Every source/claim row carries its own donor `/type` raw witness before the
selected field. Python validates donor source type, owner-local UUID, mapping,
concept, path, value and exact contributors independently on every page. A type
embedded in a record key is insufficient. Claim validation also checks target
IDs and inverse evidence. Identity and field records can appear on different
pages; no top-level donor manifest or earlier-page identity is required.
Repeated donor/path witnesses, donor types and resolved target names/types must
also agree within each page. Cross-page consistency uses the browser's
revalidated snapshot revision rather than Python session memory.

Denied selected Items emit an aggregate `build_scope` relationship with
`{status:"denied",target_uuid:null}` and reason `build_items_denied`, without
their names, identities, types or fields. An empty selected set emits
`build_scope` with `{status:"empty",target_uuid:null}`. Other partial reasons
are `unsupported_selection_values` and `build_grant_target_missing`,
`build_grant_target_denied`, `build_grant_target_unsupported` (validation also
admits `build_grant_target_unverified`). Without reasons the source section is
`complete`, describing selected source coverage only.

More than 12,000 owner Items or 24,000 selected records yields `ReadFailed`;
narrow the investigation with `list_actor_items` and targeted `read_item` reads.
Records have deterministic ordering. Shared pagination independently bounds
records with `limit=50` (1–100) and UTF-8 JSON bytes with `max_bytes=48000`
(8,000–48,000). Responses retain `contract_version`, `runtime`, `identity`,
`revision`, `sections`, `records`, `pagination`, `limitations`. `pagination` has
`complete`, `next_cursor`, `returned`. Pass the returned cursor unchanged with
all original inputs until null; paged sections are partial with `pagination`.
Revisions recheck membership, permissions, selected source and inverse evidence.
On `ContentChanged`, discard accumulated pages and restart without a cursor;
on `InvalidCursor` or `CursorMismatch`, restart without a cursor.

## Verification boundary

Deterministic coverage lives in `tests/js/actor-build.test.js`,
`tests/js/actor-build-readers.test.js` and `tests/test_actor_build.py`.
See the separately maintained [verification record](build-verification.md) for
live evidence and acceptance status; source coverage never proves effective
benefits.
