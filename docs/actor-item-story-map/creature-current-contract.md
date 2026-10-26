# Current creature senses, languages and IWR

Implemented integration: explicit character/NPC `read_actor(sections=['statistics'])`
on Foundry 14.369 / PF2e 8.6.1, upstream revision
`28d9d156f252d084371d994dc359509b49eadf18`. This extends selected current
statistics rather than creating a separate unused reader. Live serialization
verification remains pending the existing GM connection. No complete Actor
story, target-dependent perception or damage application is certified.

## Public document-data boundary

Select own returned data from public Actor
[`toObject(false)`](https://foundryvtt.com/api/v14/classes/foundry.documents.Actor.html#toobject).
Never call Sense/IWR getters or methods, preparation, predicate evaluation,
sheet builders or source fallbacks. Nonplain serialized containers are admissible
only through selected own data descriptors; inherited values and accessors do
not supply fields. Declared transformed fields can differ from persisted source;
retain source separately and label both bases accurately.

Pinned declarations:

- [CreatureSystemData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts)
  supplies languages and Perception; character source excludes Perception while
  NPC source can persist authored senses. Neither source constitutes a current
  serialization fallback.
- [PerceptionTraceData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/perception.ts)
  declares labelled sense arrays; [Sense](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/sense.ts)
  defines type, acuity, nullable source range and transformed numeric range.
- [ActorAttributes](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/base.ts)
  explicitly declares Immunity/Weakness/Resistance arrays. Their
  [IWR classes](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/iwr.ts)
  declare type, exceptions, source, main definition and category-specific value
  and doubleVs fields. This direct document-data type relationship permits
  selected own returned fields; it does not authorize runtime helper calls.

## Meaning and conditional boundaries

Senses retain type, acuity, range, source and declared label separately. A sense
label is not a visibility, detection or line-of-sight result. Sense construction
can convert null source range into positive Infinity; JSON's automatic conversion
of nonfinite numbers to null must not erase that distinction. Preserve positive
Infinity through the explicit JSON-safe tag `{"$number":"Infinity"}`.
Current `PerceptionTraceData.senses` uses `Required<SenseData>` with numeric
range: reject current null rather than silently interpreting it as Infinity.
NPC source SenseSchema can retain null, but that source value neither supplies
a current fallback nor independently proves unlimited current range. Do not
invoke the Sense label getter or infer range from label prose.

Languages retain ordered codes and exact `details` qualifications. Knowing a
language does not automatically establish unrestricted speech or comprehension;
the creature declaration itself describes languages it knows and probably speaks.
Explicit statistics can expose these qualifications; default/source privacy rules
are unchanged. No language notes are silently discarded as cosmetic text.

IWR entries retain type, numeric weakness/resistance value, exceptions, source
and conditional resistance doubleVs separately. Do not double a resistance
merely because doubleVs is present, apply weakness, decide immunity, or infer
effective condition suppression. Numeric declarations do not authorize imposing
an invented integer/nonnegative constraint. Exceptions may be type strings or
labelled custom predicates; dropping predicates would conceal restrictions.

The main custom IWR definition has a firm document-data declaration: Actor
attributes contain IWR objects and IWR declares an own `definition: Predicate |
null`. It is selected only for custom entries and only when returned as own
serialized data. IWR's own serializer omits this field, so absence is expected
and must report `custom_iwr_definition_unavailable`; never reconstruct it from
type, label, source, runtime predicate getters or rule elements. Likewise, IWR
labels are declared serializer display data and may be selected only when
already returned as own data, never by calling a label getter.

## Closed predicate data contract

[RawPredicate](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/predication.ts)
is an ordered array of statements. Preserve it as bounded data; never evaluate
it. Statement grammar is closed:

- String atom.
- Exactly one binary operator `eq`, `gt`, `gte`, `lt` or `lte` with two operands:
  first string, second string or finite number.
- Exactly one `and`, `or`, `xor`, `nand`, `nor` or `iff` with a statement array.
- Exactly one `not` with a statement.
- Exactly `if` and `then`, each containing a statement.

Unknown operators, extra object keys, cycles, getters, malformed operands and
unbounded nested containers are not arbitrary JSON escape hatches. Enforce
structural depth/node/array bounds before emitting data. A custom exception's
label and definition remain independent leaves with exact provenance.

## Exact selected schema and limits

`creatureSupplementFields` returns `{fields, reasons}` for character/NPC only.
Every descriptor has exact JSON Pointer `path`, `present`, optional `value`,
`concept` and limitation `serialized_creature_details_not_target_context`.
Integrated raw/contributor basis is `transformed`; missing values map to null
with no raw value. All rows belong to explicit `statistics`.
Record keys are `statistics:<path>`, mapping
`pf2e.actor.creature-current.v1`, kind `field`, mapped unit null and one exact
owning-Actor raw witness with an identical provenance contributor. Explicit
custom main-definition null remains raw null without a missing-field reason;
neither null nor an available predicate proves applicability.

| Relative `/system` path | Concept / value |
| --- | --- |
| `perception/senses` | `current_senses`; missing or empty-array marker only. |
| `perception/senses/I/{type,acuity,range,source,label}` | `current_sense_<leaf>`; type string, acuity precise/imprecise/vague, finite range or exact `{"$number":"Infinity"}` tag, nullable source/label strings. |
| `details/languages/value` | `current_languages`; missing or empty-array marker only. |
| `details/languages/value/I` | `current_language_code`; string. |
| `details/languages/details` | `current_language_details`; string. |
| `attributes/{immunities,weaknesses,resistances}` | `current_<plural>`; missing or empty-array marker only. |
| `attributes/<plural>/I/{type,source,label}` | `current_<singular>_<leaf>`; string type/label, nullable string source. |
| `attributes/{weaknesses,resistances}/I/value` | `current_<singular>_value`; finite number. |
| `attributes/<plural>/I/definition`, custom type only | `current_<singular>_definition`; missing, null or bounded RawPredicate. |
| `attributes/<plural>/I/exceptions` | `current_<singular>_exceptions`; missing or empty-array marker. |
| `attributes/<plural>/I/exceptions/J` when string | `current_<singular>_exception_type`; exact string. |
| `attributes/<plural>/I/exceptions/J/{label,definition}` when custom | `current_<singular>_exception_label` string and `_definition` bounded RawPredicate. |
| `attributes/resistances/I/doubleVs` | `current_resistance_double_vs`; missing or empty-array marker. |
| `attributes/resistances/I/doubleVs/J` when string | `current_resistance_double_vs_type`; exact string. |
| `attributes/resistances/I/doubleVs/J/{label,definition}` when custom | `current_resistance_double_vs_label` string and `_definition` bounded RawPredicate. |

No populated array/object is emitted except a cleaned predicate or exact
Infinity tag. Current null sense range rejects; negative Infinity and NaN also
reject. Only positive Infinity at a sense range path can use the tag, and the
tag has exactly one `$number` key with value `Infinity`. It is a serialization
codec, not a source value, formula or generalized arbitrary-object allowance.

Limits: 200 senses, language codes or entries per IWR category; 200 exception
or doubleVs entries per IWR entry; 24,000 total fields. Every admitted string is
at most 6,000 UTF-16 code units, without silent truncation. Each predicate has
maximum depth 8 from root-array depth zero, 512 total nodes counting every
primitive/array/object, and maximum array length 512. String atoms are nonempty;
binary right operands can be strings or finite numbers. Predicate array
subclasses may have unrelated metadata, which is not selected.

Reasons always include `other_statistics_pending`. Missing selected fields add
`current_fields_unavailable`. Any present IWR entry adds
`conditional_iwr_not_evaluated`; an omitted custom main definition additionally
adds `custom_iwr_definition_unavailable`. Empty collections alone do not invent
conditional application claims.

## Completeness and acceptance

Selected current values participate in detached revision checks, including
exceptions, doubleVs, qualification prose and Infinity tags. Shared byte/count
continuations remain distinct from snapshot bounds; source-only/default reads
must neither serialize these current fields nor expose their rows.

The statistics section remains partial. Missing current data, custom-definition
omission and unsupported conditional application must remain visible after the
last page. Empty arrays, missing arrays, explicit nullable fields and unavailable
fields are distinct. Familiar supplements require their separately guarded
contract and are not implicitly enabled by shared creature inheritance.

Focused deterministic integration must cover character/NPC boundaries, empty
and missing collections, duplicate ordered entries, sense Infinity encoding and
current-null rejection versus permitted source null,
language restrictions, custom definitions/exceptions, resistance doubleVs,
closed predicate rejection/bounds, no getter invocation, exact Python DTO checks,
escaped paths, byte pagination and current-only stale continuations. Actual MCP
discovery must describe selected support and exclusions. Existing source or
unrelated current-statistics live results do not establish this new serialization
coverage; a representative GM runtime check remains required.

Authenticated discovery passed through the reusable Actor discovery checker,
with three required supplement mapping/reason terms, one discovery call and
`runtime_checked: false`. Full offline suites passed:386 Python tests (one
skipped),547 JavaScript tests. The existing current-statistics probe now checks
core and supplemental records independently against public serialized fields;
that extended live path has only been syntax-checked, not run against the world.
