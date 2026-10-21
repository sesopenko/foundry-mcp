# Affliction source field audit

Implementation boundary: PF2e **8.6.1**, Foundry **14.369**. The pure selector `actorAffliction.js` accepts only detached `toObject(true)` source for `type: affliction`. This is an offline schema selector, excluded from runtime reader packaging. PF2e8.6.1 production rejects affliction construction; the actual MCP reader reports UnsupportedType. See [verification evidence](affliction-verification.md). No integrated/live reading is claimed.

The full [affliction schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/affliction/data.ts) and [shared effect context schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/abstract-effect/data.ts) were read at the pinned revision. Runtime observations alone do not establish these contracts.

| Source paths under `/system` | Meaning and selection |
| --- | --- |
| `level/value`, `save/type`, `save/value` | Stored level, save category and DC. Save type is fortitude/reflex/will; no saving throw is rolled. |
| `status/onset`, `status/stage`, `status/progress` | Stored onset flag, one-based stage ordinal and recovery progress. No effective current state is inferred. |
| `onset` or `onset/value`, `onset/unit` | Explicit missing/null marker or onset duration primitive leaves. |
| `stages/{i}/damage/{j}/{formula,damageType,category}` | Exact formula and damage code; optional nullable category. Never evaluate formulas. |
| `stages/{i}/conditions/{j}/{slug,value,linked}` | Condition slug, optional nullable stored value and optional linked flag. These describe stage consequences, not current owned conditions. |
| `stages/{i}/effects/{j}/uuid` | Exact authored effect UUID; selection does not resolve or apply it. |
| `stages/{i}/duration/{value,unit}` | Per-stage interval. Preserve array order, including empty consequence arrays. |
| `duration/{value,unit,expiry}`, `start/{value,initiative}` | Overall maximum duration and stored start information, including nullable initiative/expiry. No current clock, remaining time or expiry calculation. |
| `context/origin/{actor,token,item,rollOptions}` | Exact shared effect origin values and roll-option strings. Nullable optional references remain distinct from absent. |
| `context/origin/spellcasting/{attribute/{type,mod},tradition}` | Stored origin spellcasting context, or null/missing container marker. |
| `context/target/{actor,token}`, `context/roll/{total,degreeOfSuccess}` | Stored target and prior-roll context, or null/missing markers. No reroll or targeting inference. |
| `fromSpell`, `traits/{value,otherTags}`, `slug`, `publication/{title,authors,license,remaster}` | Explicit provenance and code fields. No localized or reconstructed mechanical values. |

Each selected primitive uses `{path,present,value?,concept,limitations}`. Empty arrays have their own exact source marker; object containers are not returned wholesale. Unknown siblings, descriptions, rule elements, flags and prepared properties are excluded. Missing fields receive no schema defaults. Explicit undefined is missing only on schema-optional paths: onset, context, optional origin/target reference or spellcasting fields, optional roll degree, damage category and condition value/linked. Selected malformed types fail with an actionable schema error.

`status.stage` has concept `affliction_source_stage`. Its present numeric descriptor adds:

```json
{"source_stage":1,"stage_index":0,"status":"resolved","stage_count":2}
```

`stage_count` is selected-array structure metadata, not a fabricated raw schema field. Resolution requires an integer ordinal between one and the actual source array length. Outside that range, including fractional numeric ordinals and an empty stage array, retain the exact source number and return `stage_index: null`, `status: out_of_range`. An absent stages array produces `stage_count: null`, `stage_index: null`, `status: unverified`. An absent stage has no mapped object. The system's `prepareBaseData` clamps stage numbers; the source reader deliberately preserves the source number instead. No replacement stage is created for an empty array.

Pure tests in `tests/js/actor-affliction.test.js` cover exact formulas/references, zero/false/null, one-based to zero-based correspondence, multiple-stage order, malformed/out-of-range stage ordinals, missing versus empty arrays, optional undefined, malformed selected source, non-affliction dispatch and exclusion of throwing prepared getters. These tests establish selection behavior, not current affliction application or expiry support.
