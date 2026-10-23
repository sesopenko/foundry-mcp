# Feat grant relationship audit — October 22, 2026

This is an audited persisted representation and implemented selected-source
contract. It does not establish live-verified acquired-document joins.

PF2e8.6.1 [ItemSourceFlagsPF2e and grant source types](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts)
declare the following selected fields:

| Stored path | Meaning and boundary |
| --- | --- |
| `flags.pf2e.itemGrants.<key>.id` | String ID of a granted Item; the map key is an opaque source key, not an Item ID or UUID. |
| `flags.pf2e.itemGrants.<key>.onDelete` | Optional deletion policy. The pinned schema declares `cascade`, `detach` or `restrict`; preserve unknown string source codes and never execute them during reading. |
| `flags.pf2e.itemGrants.<key>.nested` | Optional boolean or null controlling visual nesting of feats/features; not ownership or acquisition proof. |
| `flags.pf2e.grantedBy` | Optional nullable granting-Item record. |
| `flags.pf2e.grantedBy.id` | String granting-Item ID; preserve the claim separately from verified resolution. |
| `flags.pf2e.grantedBy.onDelete` | Optional deletion policy, as above. |

No other flags are approved by this audit. The declared `rulesSelections`
record permits arbitrary object values; copying that record would disclose an
unbounded and uninterpreted contract. A future selection reader needs an explicit
primitive/structured allowlist and unsupported-value behavior before adoption.
Rule elements and stored selection text must never be executed or guessed to be
UUIDs, Item acquisitions or evaluated eligibility.

## Exact selected-source contract

`featGrantFields(source)` selects detached feat Item source only and returns
`null` for non-feat types; the caller checks the `pf2e` system ID. Its descriptors
join the existing `pf2e.feat.source.v1` mapping. Each descriptor has `path`
(JSON Pointer), `present`, `concept` and
`limitations: ["feat_source_not_effective_benefit"]`; `value` exists only when
present. No prepared defaults or effective benefits are inferred.

| Selected path | Concept and shape |
| --- | --- |
| `/flags/pf2e/itemGrants` | `feat_grant_entries` marker when absent or the explicit empty object `{}` |
| `/flags/pf2e/itemGrants/<key>/id` | `feat_grant_item_id`, string |
| `/flags/pf2e/itemGrants/<key>/onDelete` | `feat_grant_delete_policy`, optional string |
| `/flags/pf2e/itemGrants/<key>/nested` | `feat_grant_nested`, optional boolean or null |
| `/flags/pf2e/grantedBy` | `feat_granted_by_source` marker when absent or explicitly null |
| `/flags/pf2e/grantedBy/id` | `feat_granted_by_item_id`, string |
| `/flags/pf2e/grantedBy/onDelete` | `feat_granted_by_delete_policy`, optional string |

Only own source properties are selected. Optional own `undefined` becomes absent;
explicit null is accepted only for `grantedBy` and `nested`. Empty grant records
emit missing `id`, `onDelete` and `nested` descriptors rather than disappearing.
The map allows at most 12,000 own entries; wrong containers or scalar types throw.
Missing required IDs remain missing descriptors; explicit undefined required IDs
are invalid. Map keys remain opaque and use JSON Pointer `~0`/`~1` escaping.
No other entry properties, flags or rule selections are copied. These deterministic
selector tests establish extraction behavior, not acquired-document runtime
resolution or active-benefit semantics.

Proposed resolution must use the actual selected Item's supported Actor owner
and its documented embedded Items relationship. Resolve owner-local IDs only
within that exact Actor instance, retaining synthetic token context. No fallback
to a base Actor, compendium lookup by name, imported Item or source-ID match is
valid. Actual target identity and permissions must be checked independently.
A reciprocal claim can be reported only when both persisted sides were read and
agree; source claims alone do not establish causality or active benefits.

Missing, null and empty source flags must remain distinct. Unowned definitions,
missing local targets, denied targets and disagreeing reciprocal claims need
explicit outcomes. Continuations must revalidate both source and target evidence.
Multiple claims to the same actual benefit retain their own provenance while an
integrated Actor view lists the acquired document once.

The existing world audit found no owned feat or nonempty persisted grant examples
on its readable world Actors. This is a fixture limitation, not proof that the
schema or runtime cannot store grants. Deterministic coverage and a focused live
gate remain necessary before advertising acquired-grant support. See
[ITEM-feat](stories/ITEM-feat.md) and [CORE-build](stories/CORE-build.md).

## Implemented reference checkpoint

The selected source fields and explicit immediate references are now implemented.
Resolution checks actual same-owner Item identity, permissions and membership
before/after awaits, preserving each claim's source path. It never reads reciprocal
flags or claims causality. Self-effect and suppressed-feature UUIDs are independently
restricted to actual effect and feat targets. Maximum200 aggregate references,
missing/null/empty/unowned states and stale continuations have deterministic
coverage. An empty opaque map key is valid source, including its escaped path.

Acquired multi-contributor integration and selection interpretation remain future
work. The populated owned-grant live fixture gap above remains open; compendium
absence/empty checks establish only the observed cases, not populated runtime grants.
