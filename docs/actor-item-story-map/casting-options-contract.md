# Contextual casting configuration options

Implemented configuration presentation for CORE-casting; this document does
not establish live verification or a complete availability claim. Baseline: Foundry 14.369 / PF2e 8.6.1, upstream
revision `28d9d156f252d084371d994dc359509b49eadf18`. Existing
[source joins](casting-fields.md) and [current resources](casting-current-contract.md)
remain independent. [Canonical rulebook evidence](casting-verification.md#canonical-contextual-rank-reads--october-25-2026)
supports the distinctions below. Deterministic reader/boundary tests verify the
declared shapes; live contextual-option verification remains pending.
Actual authenticated MCP discovery also passed via
`scripts/actor-casting-current-live-check.py --discovery-only` after the server
restart. That check uses one discovery call, verifies descriptions/input bounds
and read-only annotation, and explicitly reports `runtime_checked: false`.

## Record boundary

Add mapping `pf2e.actor.casting-options.v1` with concept `casting_contextual_option` to the
explicit Actor `spellcasting` section. Keep `availability: not_evaluated` and
the section partial. An option is contextual presentation of recorded claims,
not proof of castability. Response-local keys never become UUIDs or mutation
selectors. Never call casting, preparation, rank getters or sheet builders.

Value fields:

| Field | Meaning |
| --- | --- |
| `spell`, `entry` | Existing canonical relationship objects, preserving unresolved status and token context. No cross-owner repairs. |
| `mode` | Recorded entry mode; no inference from spell traits. |
| `context` | `prepared_use`, `spontaneous_repertoire`, `innate_spell`, `focus_spell`, `listed_spell`, or `unsupported_mode`. |
| `preparation_index` | Null or preparation array index; repeated prepared uses remain separate. |
| `expended` | Recorded preparation expenditure boolean or null; never default false. |
| `base_rank` | Recorded spell definition rank, not rank zero for cantrips. |
| `configured_rank` | Recorded heightened rank or null; null does not invent a default. |
| `slot_rank` | Ordinary ranked preparation/resource rank, or null; slot0 is cantrip context, slot11 remains opaque. |
| `cast_rank` | Null in this configuration-only unit; future evaluation must identify its rule and contributors explicitly. |
| `spell_auto_heighten_rank`, `entry_auto_heighten_rank` | Separate recorded auto-heightening overrides or null; not evaluated cast ranks. |
| `signature` | Recorded boolean or null; not feature entitlement. |
| `cantrip` | Recorded cantrip context boolean or null. |
| `uses` | Innate `{value: number|null, max: number|null}` or null; absent values stay unknown. |
| `resource_scope` | `individual_preparation`, `shared_entry_slots`, `individual_spell_uses`, `shared_actor_focus`, or `not_evaluated`. |
| `availability` | Always `not_evaluated`. |

All option contributors retain `basis: source`; separate current-resource
records retain `basis: transformed`. Do not label copied source
fields as effective. Exact raw witnesses and provenance contributors carry
resource relationships; there is no separate per-option reasons or resource-key
array. Limitations are `availability_not_evaluated` and
`configured_rank_not_final_cast_rank`; the section additionally retains
`signature_alternatives_not_evaluated`. Include all option contributors in the detached revision
snapshot, preserving existing continuation/byte limits and stale-read behavior.

## Mode boundaries

Prepared: emit one context per preparation position, including repeated spell
IDs. Resolve only an actual owned spell whose assignment agrees with the entry.
Unresolved preparation claims remain in existing `casting_preparation` records;
do not fabricate a resolved option for them.
Preserve expended true/false/absent independently. Generic slot value zero cannot
cancel preparations. Rank0 is a cantrip context, not a rank0 spell. Do not
normalize legacy malformed preparation containers or infer available uses.

Spontaneous: emit recorded repertoire context at the configured rank, linked
to shared slot records. Preserve signature configuration without expanding
alternative ranks. Player Core 298 allows spending a higher slot without
heightening, so resource slot rank and cast rank must remain independent.
Player Core 99 establishes Bard signature entitlement; applying that entitlement
requires explicit evidence beyond a stored flag. Do not generate signature
alternatives or presume all higher slots heighten the spell in this unit.

Innate: emit individual spell-use context with independent configured rank.
Absent uses mean unknown. Innate cantrips preserve cantrip context separately.
Player Core 299 permits granting abilities to specify rank exceptions; do not
infer ordinary spontaneous heightening from available shared slots.

Focus: emit spell context linked to the shared Actor pool and independently
selected transformed spell focus-point cost. An entry's focus mode does not
invent a focus trait or cost. Keep spell/entry auto-heighten overrides as source
configuration until their evaluated rule mapping is established. Cantrip and
focus automatic-heightening rules are distinct from ordinary slot ranks.
Familiar Actor focus remains outside the current-resource contract.

Flexible, ritual, item and unknown modes: preserve readable spell/entry identities
and source with explicit unsupported contextual interpretation. Unassigned,
denied, missing, wrong-type or mismatched relationships remain unresolved.
Non-null ritual data contributes only the declared scalar witnesses
`/system/ritual/primary/check`, `/system/ritual/secondary/checks` and
`/system/ritual/secondary/casters`; malformed ritual data rejects the snapshot.
No arbitrary ritual object is exposed or interpreted as a supported mode.

Snapshot bounds: 12,000 owned Items, 24,000 options, 200 traits per spell,
6,000 preparation positions per slot and 24,000 preparation positions total.
Preparation traversal is cached once per entry; page limits do not relax these
snapshot limits.

## Acceptance and remaining gates

Focused deterministic checks must cover repeated preparations, zero generic
slots, missing expenditure flags, slot0/slot11, configured/base/slot distinctions,
signature true/false/absent without generated alternatives, innate unknown uses,
shared focus across entries, focus-mode/trait/cost disagreement, denied targets,
token identity, current-only stale continuations and unsupported modes. Verify
actual MCP discovery contracts and Python validation against the final schema.

Later evaluated-rank work must separately establish entitlement, permitted rank
alternatives, automatic-heightening overrides and spending a higher slot without
heightening. Resource sufficiency alone never establishes actions, requirements,
targets or legal casting. Original mode-specific live acceptance remains in
force before claiming complete current availability; no casts or expenditure
writes are authorized by this document.
