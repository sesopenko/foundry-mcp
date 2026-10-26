# Permission-checked current familiar statistics

Implemented explicit `read_actor(sections=['statistics'])` contract on a
familiar, Foundry 14.369 / PF2e 8.6.1, upstream revision
`28d9d156f252d084371d994dc359509b49eadf18`. This checkpoint does not complete
[ACT-familiar](stories/ACT-familiar.md). Live verification remains pending the
existing development GM connection; deterministic checks do not establish live
master-derived behavior.

## Master guard before serialization

Read the selected familiar's persisted `/system/master/id` and
`/system/master/ability` through the existing source selector. Resolve the ID
only to an actual readable world character, using the existing permission-aware
master relationship resolver. An ID is not a token selector; do not choose a
same-named Actor, a compendium entry or a token-current replacement.

Only a resolved, authorized master permits the familiar's public
[`toObject(false)`](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject)
call for current statistics. Missing, unassociated, denied, unsupported or
unverified master claims prevent that serializer call and all current rows.
Retain source/master relationship evidence and actionable partial reasons; no
zero statistics or source fallback is fabricated. Never use `familiar.master`,
private members, preparation methods, sheet data or locally reconstructed master
formulas. Resolving a master authorizes selected reading, not recalculation or
certification of the system's derivation.

The source master relationship remains distinct: key
`identity:familiar_master`, concept `familiar_master`, mapping
`pf2e.familiar.master.v1`, source `/system/master/id` witness and limitation
`stored_master_reference_not_current_statistics`. Resolved values identify the
actual world character and next `read_actor` call; denied/unresolved values
expose no resolved master identity. Current fields do not relabel that source
claim as transformed data.

After the asynchronous master lookup, the reader rechecks world readiness,
GM role, familiar/pack/Scene/Token permissions, source reassignment and master
access before transformed serialization. Regression tests establish zero
transformed calls when those permissions are lost during resolution.

Explicit statistics additionally emits `statistics:familiar_master` in section
`statistics`, using the existing `pf2e.familiar.master.v1` mapping, relationship
value and limitation, with **two** exact source witnesses:
`/system/master/id` and `/system/master/ability`. Both retain `basis: source`.
The ability is source configuration string/null/absent, never an independent
familiar attribute or derived modifier. The identity-section master row retains
its original single ID witness. Both statistics source-context fields participate
in revision checks independently of transformed current values.

## Selected document-data boundary

The pinned [FamiliarSystemData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts)
declares attributes, saves, Perception, movement and ordinary skills while its
source interface explicitly excludes independent skills/saves/Perception.
Selected transformed serialization is admissible independently of that source
exclusion; it does not authorize every runtime property or helper object.
Related [creature data](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts)
and [statistic traces](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/data.ts)
define the selected leaf meanings. Values must be own serialized data properties;
nonplain containers are allowed, inherited values and getters are not fallbacks.

Expose selected defenses, HP, Perception, movement and ordinary skill fields as
transformed primitives with separate owning-familiar provenance. Missing leaves
stay unavailable and explicit null remains distinct from zero. Do not calculate
AC, saves, HP or skill modifiers from master values. No independent familiar
attribute modifiers or ordinary Strikes are inferred. A declared attack trace
does not establish a normal Strike interface.

Before ordinary skill key/label/total output, inspect only its `lore` and `itemId`
claim. Skip the entire skill if `lore` is true or `itemId` is a nonempty string;
add `familiar_item_linked_skills_unsupported`. No generated key, label or totals
from that skill escape. This unit does not certify familiar Lore acquisition or
Item-linked skill relationships. Existing owned Item source navigation remains
separate.

Skill maps are bounded to 512 own keys, each 1–256 Unicode codepoints, and
24,000 selected fields overall. Escape JSON Pointer key `~` as `~0` and `/` as
`~1`; response keys are never document selectors. Empty and missing collections
must remain distinguishable. Rank, if not declared for the selected familiar
trace, must not be invented from a modifier.

## Exact selected fields and records

The pure `familiarCurrentFields` selector consumes detached serialized data only;
the integrated reader performs the master guard before obtaining that data.
Descriptors contain `{path, present, value?, concept, limitations}` with
limitation `serialized_familiar_value_not_recalculated`. Integrated records use
mapping `pf2e.familiar.current.v1`, `section: statistics`, `kind: field`, exact
familiar UUID and `basis: transformed` in their single raw witness and matching
provenance contributor. Mapped unit is null; primitives retain their values and
missing leaves map to null without a raw value.
Current record keys are `statistics:<JSON Pointer>`; no new document identities
are invented for skills or derived statistics.

| Relative path under `/system` | Type / concept |
| --- | --- |
| `attributes/ac/value`, `breakdown`, `details` | finite number, string, string / `current_armor_class`, `current_armor_class_breakdown`, `current_armor_class_exception_notes` |
| `attributes/hp/value`, `max`, `temp` | finite numbers / `current_hit_points`, `current_maximum_hit_points`, `current_temporary_hit_points` |
| `saves/{fortitude,reflex,will}/value`, `totalModifier`, `breakdown` | finite number, finite number, string / `current_<save>_save_modifier`, `_total_modifier`, `_breakdown` |
| `perception/value`, `totalModifier`, `breakdown`, `vision` | finite number, finite number, string, boolean / `current_perception_modifier`, `current_perception_total_modifier`, `current_perception_breakdown`, `current_standard_vision` |
| `movement/speeds/{land,burrow,climb,fly,swim,travel}/{value,base,type,source}` | finite number, finite number, matching literal mode, nullable string / `current_<mode>_speed`, `_base_speed`, `_movement_type`, `_movement_source_label` |
| `movement/speeds/{burrow,climb,fly,swim}` when null | explicit null root / `current_<mode>_movement`, without child records |
| `skills/<escaped key>/{slug,label,value,totalModifier,dc,breakdown}` | string, string, finite number, finite number, finite number, string / `current_skill_slug`, `_label`, `_value`, `_total_modifier`, `_dc`, `_breakdown` |
| `skills` when unavailable or empty | missing marker or present `{}` marker / `current_skill_collection`; mapped null |

No attribute, attack, proficiency-rank or resource records are admitted by this
allowlist. Descriptor reasons always include `other_statistics_pending`, with
`current_fields_unavailable` for missing selected fields and
`familiar_item_linked_skills_unsupported` for skipped skills. These are distinct
from unresolved-master reasons emitted before serialization.

## Revision, privacy and completeness

The detached revision snapshot retains persisted master ID/ability, resolved
master identity/status and selected familiar transformed values. Re-resolve
permission and relationship facts when checking continuations; changed master
claims, permissions, identity/status or current-only values invalidate stale
pages. Shared count/UTF-8 byte pagination is independent of skill-map bounds.
Default/source-only reads do not request or return current statistics.

Statistics remains partial with explicit unresolved-master or current-field gaps
and pending-statistics limitations. Reading a complete page sequence is not
proof of complete familiar mechanics, visibility, target-context rolls or active
condition application.

Deterministic coverage must establish serializer-not-called for every failed
master status, world-character type/identity guards, master permission loss,
source/derived separation, source-only exclusion, own-property admission,
missing/null/zero distinctions, skipped Item-linked skill privacy, skill bounds,
escaped keys and master/current-only stale continuations. Actual MCP discovery
descriptions and strict Python DTO validation must match the delivered fields.

Authenticated discovery passed with the reusable Actor discovery checker and
three required familiar-statistics terms. It used one discovery call and
reported `runtime_checked: false`. The existing familiar fixture runner offers
`--statistics` for later live verification using the same marked pair, exact
public serializer comparisons and guarded cleanup; that mode has not been run.
Final offline suites passed:381 Python tests (one skipped),534 JavaScript tests.

Original ACT-familiar gates remain: representative master-linked live values,
familiar/master ability identity and description, world/compendium/token context,
integrated casting/state, and complete supported effective interfaces. Familiar
action Items remain unclassified until their exact descriptions establish scope;
this statistics checkpoint does not infer master-benefit classification, pet or
companion roles, acquisition, activation or normal Strikes.
