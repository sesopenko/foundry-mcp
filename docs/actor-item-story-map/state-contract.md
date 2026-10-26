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

Condition activity, suppression and effect applicability remain unsupported.
For actual readable owned effects only, the reader selects the own data property
`Item.system.expired`. Public core
[ItemData.system](https://foundryvtt.com/api/v14/interfaces/foundry.documents.types.ItemData.html#system)
is the system-data boundary; pinned PF2e `effect/document.ts:212` declares
`EffectPF2e.system: EffectSystemData` and `effect/data.ts:110` declares its
`expired: boolean`. This model field can be omitted by `toObject(false)`.
No remaining-duration getter, preparation or local expiry calculation is used.
Own data descriptors prevent invocation of selected getters. `false` does not
prove active application. Missing declared expiry remains unknown, with no
source or serialization fallback. A present false flag is live-verified below;
true has deterministic coverage only.
Recorded override links do not prove suppression. A present
condition/effect does not establish active application. An absent optional
origin/target role is an ordinary absent relationship, not an unresolved-gap
reason. Nonempty claimed references that cannot resolve remain explicitly
missing, denied, unsupported or unverified under the existing relationship
contract; they must not be confused with an omitted optional role.

`ConditionPF2e.active` is a different evidence case: the exported class declares
a default-public boolean, but neither the condition system-data schema nor an
independently established external API contract documents it. It is not adopted
by this reader pending clearer support evidence; it is not labelled private or
unsupported by upstream. Stored override references alone still cannot establish
current condition inactivity or general rule suppression.

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
matches a raw witness's `document_uuid`, `path` and `basis`; raw witnesses
add `present` and, only when present, `value`. No fabricated document selectors
or unbounded nested source objects are returned.

| Key | Kind / concept | Mapping / value |
| --- | --- | --- |
| `state:item:<Item UUID>` | relationship / `state_item` | `pf2e.actor.state-source.v1`; resolved Item identity with `application: unknown`, actual type, name bounded to 256 Unicode codepoints, truncation flag and optional selected `token_uuid`. Raw `/name` and `/type` witnesses. |
| `state:source:<Item UUID>:<path>` | field / existing typed concept | `pf2e.condition.source.v1` or `pf2e.effect.source.v1`; existing typed mapped value, limitations and one exact source witness. |
| `state:current:<Item UUID>:/system/expired` | field / `current_effect_expired` | `pf2e.effect.current.v1`; boolean or null when absent. One declared public model `/system/expired` witness with `basis: transformed`, matching contributors and limitation `effect_expiry_not_application`. Effects only. Missing witness has `present: false` and no value. |
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
`current_effect_expiry_unavailable` when an owned readable effect lacks its
declared current expiry flag. Add
`unresolved_state_references` for nonempty unresolved claims only. Shared
pagination may additionally add `pagination`; optional absent roles do not add
an unresolved reason.

## Bounds, continuation and revision

Reject snapshots exceeding 12,000 owned Items, 24,000 selected records or 200
nonempty external relationship claims. Count and preflight external claims
before any external hydration; page size does not relax snapshot bounds.
Empty/null optional relationship roles do not consume the nonempty-claim bound.
Use shared record-count and UTF-8-byte pagination separately from these bounds.

The detached revision snapshot includes selected owned source, current effect
expiry and resolved
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

The initial October 25 serialization-only existing-world verification passed through
`scripts/actor-state-live-check.py`: two existing NPCs, condition/effect coverage,
10 state pages, 56 state records, 36 source/default pages, 76 raw witnesses and
two resolved relationship checks across 54 MCP calls. Full source fingerprints
were unchanged. The one effect omitted serialized expiry: zero present flags,
one absent flag. The unavailable result was verified independently against
public serialization; no current expiry value was live-verified at that checkpoint. Character,
familiar, synthetic-token state, effective application and afflictions remain
unverified. These results do not close the original story requirements.

The subsequent public-model audit corrected that narrower boundary. The same
two existing NPCs now pass the independent check with **one present expiry flag
(`false`), zero absent flags**, 10 state pages, 56 records, 36 source/default
pages, 76 raw witnesses and two resolved relationships in 54 MCP calls. Complete
source fingerprints were unchanged. The check reads the declared own model
property independently; it never invokes an expiry getter or recalculates time.
Character/familiar/token state and an expired-true runtime fixture remain
unverified. Condition activity and effect application are still unsupported.

The independent verifier distinguishes source identity names from PF2e display
labels; an offline failing-then-passing test reproduces their difference. It
uses source names for `state_item`, and display names for context relationships.

The full story still requires supported evidence for suppressed-but-present
effective state, live expiration verification/application and affliction tracked/out-of-range
stages. This source join delivers useful state navigation while those capabilities
remain explicitly unsupported. Do not mark CORE-state complete, erase its
original acceptance criteria or count unsupported affliction absence as success.
