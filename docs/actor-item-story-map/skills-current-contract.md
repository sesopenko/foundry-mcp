# Integrated current skills contract

Explicit `read_actor(sections=['skills'])` combines selected current
character/NPC skill document data with the independent owned-Lore source
listing. Target: Foundry 14.369 / PF2e 8.6.1, upstream revision
`28d9d156f252d084371d994dc359509b49eadf18`. Deterministic implementation and
runtime evidence are separate. Representative world character/NPC current
values and owner-local Lore joins are now verified below. This component
checkpoint alone does not complete an Actor story.

## Public boundary and selected fields

`actorSkillsSnapshot` selects own data properties from public Actor
[`toObject(false)`](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject),
without source fallback, runtime statistic getters, preparation or roll calls.
Nonplain serialized containers are allowed; inherited properties and accessors
are not. Schema meaning comes from pinned
[creature SkillData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts),
[character document data](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts),
[NPC document data](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/npc/data.ts)
and [statistic traces](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/data.ts).

Paths are `/system/skills/<escaped skill key>/<leaf>`. Escape JSON Pointer `~`
as `~0` and `/` as `~1`; response keys and paths never become document selectors.
Preserve each actual skill key rather than assuming a closed standard list.

| Scope | Selected leaves and validation |
| --- | --- |
| Character and NPC | `slug`, `label`, `breakdown`: strings; `attribute`: str/dex/con/int/wis/cha; `value`, `totalModifier`, `dc`: finite numbers; `lore`: boolean; `itemId`: string or null. |
| Character | `rank`: integer 0–4; `armor`: boolean. |
| NPC | `base`, `mod`: finite numbers; `visible`: boolean; optional `note`: string containing restrictions or qualifications. |

`rank` maps to `{rank, label}` with Untrained/Trained/Expert/Master/Legendary;
modifiers and DC remain independent numbers. Do not calculate one from another
or interpret a DC as a modifier. Missing selected fields retain `present: false`,
no raw value and mapped null; zero, false, null and absent remain distinct.
Character and NPC subtype contracts must not be interchanged.
An absent NPC `note` emits its missing-field record without adding
`current_skill_fields_unavailable`, because the schema explicitly makes it
optional. Preserve a present note as text; do not reinterpret its qualifications
as automatically applied conditional modifiers.

Familiar current skills are unsupported and do not request transformed
serialization. Existing familiar owned-Lore references remain readable where
permitted; they do not establish familiar current skill totals or master-derived
statistics.

## Record, mapping and provenance contract

All current rows have `section: skills`, `mapped.unit: null`, exact owning Actor
`document_uuid`, `basis: transformed` in raw witnesses and matching provenance
contributors. Mapping `pf2e.actor.skills-current.v1` uses limitation
`serialized_current_skill_not_target_context`.

| Key | Kind / concept / mapped value |
| --- | --- |
| `skills:current:<JSON Pointer>` | field / `current_skill_<leaf>` / selected primitive, rank mapping or null. Leaf `itemId` becomes concept suffix `item_id`; `totalModifier` becomes `total_modifier`. |
| `skills:current:/system/skills` | field / `current_skill_collection` / null; raw absent map marker or present empty `{}` marker. An empty map differs from unavailable map. |
| `skills:current-lore:<escaped skill key>` | relationship / `current_skill_lore_reference` / resolved, missing or unsupported owner-local Lore claim. Mapping `pf2e.actor.skills-lore.v1`, limitation `serialized_lore_claim_not_exhaustive_owned_lore`. Exact raw witnesses are that skill's `lore` and `itemId`. |
| `skills:current:denied` | relationship / `current_skill_item_reference` / `{status: denied, target_uuid: null}`; empty raw/contributors. One aggregate marker, without leaked skill keys or totals. |

Resolved current Lore claims expose actual Item UUID, `document_name: Item`,
`type: lore`, bounded name/truncation flag and selected `token_uuid` when present.
Follow `read_item` with that UUID and token context. Missing or unsupported
claims return null target UUID without resolved target metadata.

The independent source listing retains keys `skills:lore:<Item UUID>`, concept
`lore_specialty`, mapping `pf2e.lore.specialty.v1` and exact source `/name` and
`/type` witnesses. Its existing aggregate denial key is `skills:lore:denied`.
Source and current provenance are never combined or silently substituted.

## Lore identity, collisions and privacy

Join current Lore only when serialized `lore` is true and nonempty `itemId`
matches an actual owner-local Item. Require type Lore and exact selected owner;
never fabricate a UUID from an ID or join by name, slug or generated skill key.
Retain a missing/wrong-type claim as such.

Before reading or emitting ordinary skill key, label, breakdown or totals, check
permission on an actual Item named by a Lore claim. If that Item is unreadable,
withhold the whole current skill and emit only the aggregate denial marker.
The selected actor being readable does not authorize denied Lore metadata.

Multiple owned Lore Items can collapse into one prepared skill-map key. Therefore
the source listing must continue to enumerate every actual readable owned Lore
Item independently. A current itemId join identifies one contributor; it is not
an exhaustive list of all Lore possessions. Conversely, an owned Lore Item does
not automatically establish a separate current total.

## Limits, completeness and verification

Bounds are 512 own skill keys, 1–256 Unicode codepoints per key, 12,000 total owned
Items and 24,000 selected rows. Shared record/UTF-8 byte pagination remains
independent. All selected current values and Lore target identity/permission facts
participate in revision checks; current-only changes invalidate continuations.
Source-only/default Actor reads do not request or return these current records.

The section remains partial with `other_skills_pending`. Missing selected leaves
add `current_skill_fields_unavailable`; denied linked Items add
`current_skill_items_denied`. NPC reads additionally report
`conditional_skill_variants_not_evaluated`: special variants and predicates are
excluded, and presented totals are not target-context rolls. Shared pagination
can add `pagination`. Do not claim all conditional modifiers, familiar derivation
or Actor acceptance are complete after exhausting pages.

Focused deterministic integration must cover both Actor subtypes, optional NPC
data, ranks versus modifiers/DCs, zero/null/absent leaves, empty/missing maps,
escaped/nonstandard keys, duplicate Lore source collisions, actual itemId joins,
missing/wrong-type/denied targets, key/label/total privacy, synthetic identities,
bounds, continuation and current-only stale revisions. Validate actual published
MCP descriptions/input schemas and strict Python DTO validation. Existing owned
Lore source evidence alone does not establish current-skill serialization;
the independent current-skill checks below supply that separate proof.

Authenticated discovery passed using `scripts/actor-discovery-check.py` with
section `skills` and required mapping/concept/denial terms. It checked the
published description, input schema and read-only annotation with one MCP call,
explicitly reporting `runtime_checked: false`.

## Representative current Skills verification — October 28, 2026

`actor-tools.sh skills-live` verified an existing world NPC: 221 current records
across 23 pages, one source Lore identity and its actual current owner-local
`itemId` join, in 36 requested/completed calls. The bounded census found 172
readable NPCs with current skills and 12 with resolved Lore; only one was
selected for the verification, without changing any documents.

`actor-tools.sh character-current-live` then reused that NPC and one marked
character with one inert Lore Item. Its nested Skills check passed 408 current
records across 42 pages, two source Lore identities and two resolved current
joins in 64 requested/completed calls. Each returned current/source witness
matched an independent public serialization read; exact path coverage, labels,
rank mappings, contributor ownership and canonical Item follow-ups passed.
Source and selected current fingerprints remained unchanged. The enclosing
78-call run also checked character statistics and confirmed exact fixture cleanup.

The checker requires present numeric current values, ordinary skills and a
resolved owner-local Lore join for each Actor; missing coverage cannot pass.
Offline actual-reader tests reject forged totals, incomplete witness checks,
missing samples and substituted character selection. These are world-sample
results, not live pack/token current-skill verification or target-context rolls.
Duplicate/colliding Lore and denied-Item privacy retain deterministic coverage.
