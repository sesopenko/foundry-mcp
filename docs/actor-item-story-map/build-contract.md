# Actor Build contract proposal

This proposal guides CORE-build integration. It does not advertise an implemented
Actor build view or close ITEM-background or ITEM-feat acceptance gates.

## Persisted source boundary

The common `itemGrantFields(source)` selector uses PF2e 8.6.1
[ItemSourceFlagsPF2e, ItemGrantSource and ItemGranterSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts).
It accepts string Item type codes; callers must gate PF2e and supported types.
It selects only the already audited `itemGrants` and `grantedBy` fields described
in the [grant contract](feat-grant-contract.md), with neutral concepts
`grant_entries`, `grant_item_id`, `grant_delete_policy`, `grant_nested`,
`granted_by_source`, `granted_by_item_id` and `granted_by_delete_policy`.
Its limitation is `stored_grant_claim_not_active_benefit`. The feat wrapper
retains its original feat concepts and `feat_source_not_effective_benefit`.
Presence, null, empty maps, opaque escaped keys, optional undefined, declared
types, private-field exclusion and the 12,000-entry map bound are unchanged.
This selector neither resolves targets nor establishes ownership or activity.

## Proposed records

Use the existing paginated `build` section record schema. List each actual
readable owned ancestry, heritage, background, class, deity, feat and Lore Item
once with canonical owner/token context. Reuse typed source selectors, retaining
each original mapping and donor Item UUID. Preserve offered and selected choices,
feature categories, nominal/taken levels, traits and publication metadata, HP and
rank contributions, deity options and future definitions separately from totals
and actual acquired documents.

Emit a separate claim record for every persisted grant or granted-by ID. Keys
include donor UUID and escaped source path, so multiple contributors do not
duplicate the owned benefit identity or overwrite another contributor. Resolve
only exact IDs within the selected actual Actor instance; never substitute its
base Actor. Definitions, names, slugs, Lore labels and recorded selection values
cannot establish acquisitions. Missing linkage remains explicitly unknown.

Matching reciprocal claims may report agreement only after reading both sides,
with both exact raw contributors retained. Distinguish agreement, disagreement,
absence and unevaluated evidence. Agreement establishes matching stored claims;
it does not establish causality, active benefits, eligibility or effective totals.
Do not execute rules, import grants, create missing Items or replace training.

## Validation, privacy and limits

The strict Python boundary must connect every transferred source row to a matching
owned identity donor and its actual type, mapping, path, concept and source value.
A type embedded in a record key alone is insufficient. Check exact contributors,
same-owner/token identities, claim target IDs and inverse evidence for reciprocal
agreement; reject duplicate identity/claim keys, mixed donors and extra fields.
Pagination can separate donor identities from their fields. Final integration
must resolve this explicitly, for example through a bounded validated per-page
donor manifest, rather than dropping cross-record checks. This remains a contract
decision before implementation, not an existing response field.

Denied Items yield aggregate scope limitations without their identities, names,
types or fields. A readable donor may retain its own stored claim ID, but denied
target identity stays withheld. Preserve missing, denied, unsupported, empty and
incomplete states. Proposed aggregate bounds match inventory: 12,000 owner Items
and 24,000 emitted records, checked incrementally. Shared byte/count pagination
and revisions must include membership, permissions, selected source and reciprocal
evidence. Order records deterministically. Reject other systems and explicitly
report NPC/familiar Build unsupported unless separately designed and verified.

## Acceptance and evidence still required

Cover versatile heritage, duplicate training without invented replacement, one
owned Lore/feat with multiple proven contributors, class-feature categories,
future class definitions, unselected boosts and deity spell options without
acquisition. Include absent/denied/missing and disagreeing claims, scalar versus
unsupported selections, synthetic owners, stale pagination, limits and privacy.

The existing world has no populated character/grant/selection fixture establishing
the required live acquired joins. Deterministic fixtures establish logic but do
not close that live gap. ITEM-background and ITEM-feat may close with CORE-build
only when their original integration acceptance and specified verification are
met; preserve their usable source checkpoints while remaining gates are open.
