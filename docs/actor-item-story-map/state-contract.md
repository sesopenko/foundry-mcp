# Integrated Actor state source contract

Implementation target for explicit `read_actor(sections=['state'])`, baseline
Foundry 14.369 / PF2e 8.6.1, pinned upstream revision
`28d9d156f252d084371d994dc359509b49eadf18`. This document does not itself establish
shipped behavior, live verification or completion of [CORE-state](stories/CORE-state.md).

## Reader outcome

`actorStateSnapshot` joins the selected actual Actor/token's owned condition and
effect records into one bounded state view. It reuses the existing public
document/identity/permission boundaries and typed [condition](condition-fields.md)
and [effect](effect-fields.md) source readers and immediate relationship helpers.
No preparation, activity getter, suppression calculation, formula evaluation,
expiration calculation, recovery, roll, chat or document write is performed.

Each actual readable condition/effect contributes its canonical Item identity,
typed selected source and immediate relationships. Repeated names, overlapping
effects and multiple origins remain separate Items. A tracking effect and its
granting ability remain distinguishable identities; joining them does not turn
them into duplicate copies of one ability or prove either is active.

Condition references resolve owner-local parent/children/overrides/overriddenBy
claims using actual membership and type checks. Override slugs remain named
unverified claims, rather than fabricated local Item IDs. Effect context resolves
immediate external origin/target Actors, Tokens and Items under existing target,
owner, Scene and pack permission checks. A supplied token must retain the selected
instance; never substitute its base Actor. Relationship reads do not recursively
read target source.

## Source, unknown and unsupported state

Raw and mapped data preserve existing typed-source mappings, selected paths,
`present` flags and `basis: source` contributor provenance. Preserve condition
valued/unvalued configuration, persistent-damage formulas/DC/metadata, effect
duration unit/value/expiry/sustained/start timing, badge discriminator and exact
formula text. Missing values stay missing; do not invent durations, zero counters,
active flags or unlimited resources. An origin roll total is historical source,
not a new check modifier or roll.

Condition activity, suppression, effect applicability and computed expiration
remain unsupported. Recorded override links do not prove suppression. A present
condition/effect does not establish active application. An absent optional
origin/target role is an ordinary absent relationship, not an unresolved-gap
reason. Nonempty claimed references that cannot resolve remain explicitly
missing, denied, unsupported or unverified under the existing relationship
contract; they must not be confused with an omitted optional role.

Affliction source/mapped/effective support remains explicitly unsupported in
every result, including an Actor with no affliction Items. PF2e 8.6.1's
[AfflictionPF2e constructor](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/affliction/document.ts)
throws in production. Do not bypass the constructor, hydrate through another
class or treat offline stage fixtures as a live reading. An empty supported
condition/effect collection establishes only that no such readable owned records
were found; it does not prove the Actor has no affliction or other effective state.

## Exact detached record contract

All rows have `section: state`, `mapped: {concept, value, unit: null}` and
`provenance: {contributors, mapping, limitations}`. Each contributor exactly
matches a raw witness's `document_uuid`, `path` and `basis: source`; raw witnesses
add `present` and, only when present, `value`. No fabricated document selectors
or unbounded nested source objects are returned.

| Key | Kind / concept | Mapping / value |
| --- | --- | --- |
| `state:item:<Item UUID>` | relationship / `state_item` | `pf2e.actor.state-source.v1`; resolved Item identity with `application: unknown`, actual type, name bounded to 256 Unicode codepoints, truncation flag and optional selected `token_uuid`. Raw `/name` and `/type` witnesses. |
| `state:source:<Item UUID>:<path>` | field / existing typed concept | `pf2e.condition.source.v1` or `pf2e.effect.source.v1`; existing typed mapped value, limitations and one exact source witness. |
| `state:condition:<Item UUID>:<path>` | relationship / existing condition reference concept | `pf2e.condition.reference.v1`; existing owner-local relationship value and exact ID/type or slug witnesses. |
| `state:effect:<Item UUID>:<role>` | relationship / `effect_<role>_reference` | `pf2e.effect.context-reference.v1`; existing immediate context relationship value. Each role retains all five source UUID witnesses. |
| `state:capability:affliction` | field / `state_affliction_support` | `pf2e.actor.state-capability.v1`; `{status: unsupported, reason: pf2e_8_6_1_affliction_disabled}`, empty raw/contributors, limitation `no_effective_state_inference`. Always present. |
| `state:denied` | relationship / `state_item` | Aggregate `{status: denied, target_uuid: null}`, empty raw/contributors, mapping `pf2e.actor.state-source.v1`. Present only when scoped condition/effect Items are denied. |

Identity and denied records use limitation `stored_state_not_effective_application`.
Relationship limitations remain identical to their existing condition/effect
contracts. Effect roles are `origin_actor`, `origin_token`, `origin_item`,
`target_actor` and `target_token`. Missing and denied values disclose no resolved
metadata; resolved values retain the existing canonical identity contract.
The capability record occurs once in the complete selected snapshot; pagination
can place it on another page. Its unsupported-section reason remains on every
page. Follow Item `target_uuid` using `read_item(item_uuid=...)`, retaining a
returned `token_uuid` for linked or synthetic instance context.

The section is always partial. Reasons always include
`effective_application_not_evaluated` and `affliction_reading_unsupported`.
Add `state_items_denied` for the aggregate denial marker and
`unresolved_state_references` for nonempty unresolved claims only. Shared
pagination may additionally add `pagination`; optional absent roles do not add
an unresolved reason.

## Bounds, continuation and revision

Reject snapshots exceeding 12,000 owned Items, 24,000 selected records or 200
nonempty external relationship claims. Count and preflight external claims
before any external hydration; page size does not relax snapshot bounds.
Empty/null optional relationship roles do not consume the nonempty-claim bound.
Use shared record-count and UTF-8-byte pagination separately from these bounds.

The detached revision snapshot includes selected owned source and resolved
external identities, permission and membership facts. Changes to either source
or relationship targets invalidate stale continuations. Pass
`pagination.next_cursor` unchanged as `cursor` with the same selectors, sections
and bounds; null means traversal is finished. `revision` is response evidence,
not a separate read_actor input. Never construct cursors or assume one page is
exhaustive. Denied targets expose no resolved name/type/UUID metadata.

## Original acceptance and verification gates

Deterministic integrated tests must cover valued/unvalued conditions, persistent
damage, separate overlapping Items and multiple origins, formula badges,
encounter durations, owner-local override claims, optional absent roles versus
nonempty unresolved claims, denied targets, synthetic token identity, byte/count
continuations, permission changes, stale external targets and preflight limits.
Check actual MCP discovery descriptions and strict Python DTO validation too.

Existing-world live verification must consume all selected state pages, compare
selected source and relationship identities with public document reads, preserve
complete source fingerprints and exercise at least representative existing
conditions/effects without gameplay writes. Unit coverage alone does not close
the runtime gate.

Authenticated `--discovery-only` verification passed after the server restart
with one MCP discovery call and `runtime_checked: false`. The reusable runner is
`scripts/actor-state-live-check.py`; its full read-only mode remains pending the
existing GM browser connection.

The full story still requires supported evidence for suppressed-but-present
effective state, expiration/application and affliction tracked/out-of-range
stages. This source join delivers useful state navigation while those capabilities
remain explicitly unsupported. Do not mark CORE-state complete, erase its
original acceptance criteria or count unsupported affliction absence as success.
