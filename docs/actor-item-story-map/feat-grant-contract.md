# Feat grant relationship audit — October 22, 2026

This is an audited persisted representation and a proposed reader contract,
not a claim that acquired-document joins are implemented or live verified.

PF2e8.6.1 [ItemSourceFlagsPF2e and grant source types](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts)
declare the following selected fields:

| Stored path | Meaning and boundary |
| --- | --- |
| `flags.pf2e.itemGrants.<key>.id` | String ID of a granted Item; the map key is an opaque source key, not an Item ID or UUID. |
| `flags.pf2e.itemGrants.<key>.onDelete` | Optional `cascade`, `detach` or `restrict` deletion policy; never execute it during reading. |
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
