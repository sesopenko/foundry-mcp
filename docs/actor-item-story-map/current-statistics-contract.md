# Transformed statistics contract and remaining candidates

Targeted audit: October 23, 2026. Contract target: Foundry **14.369**, PF2e
**8.6.1**, upstream revision
`28d9d156f252d084371d994dc359509b49eadf18`.

The `statistics` section now implements the character/NPC subset documented
below and in [verification](current-statistics-verification.md). Skills, familiar
derivation and the other listed future views remain candidates, not delivered
support. This contract identifies a bounded extraction route for checkpoints in
[ACT-character](stories/ACT-character.md), [ACT-npc](stories/ACT-npc.md), and
[ACT-familiar](stories/ACT-familiar.md). It does not close those checkpoints or
replace their original acceptance criteria with a narrower delivered subset.

## Implemented section contract

Explicit `read_actor(..., sections=["statistics"])` selects character/NPC
attributes, AC, HP, saves, Perception/vision and movement from public
`toObject(false)`. Familiar statistics remains unsupported with reason
`master_current_contract_pending`, pending permission-aware master verification.
Default source reads do not request transformed serialization.

Each field record has `key: "statistics:<JSON Pointer>"`, `section: "statistics"`,
`kind: "field"`, one exact owning-Actor raw contributor and matching provenance.
Both `raw[].basis` and `provenance.contributors[].basis` are `transformed`.
Mapping is `pf2e.actor.current.v1`; limitation is
`serialized_current_value_not_target_context`. Mapped concepts name book
statistics, including `current_armor_class`, `current_hit_points`,
`current_maximum_hit_points`, `current_fortitude_save_modifier`,
`current_perception_modifier` and per-mode `current_<mode>_speed`.
`mapped.unit` is null; `mapped.value` retains the serialized primitive except
proficiency ranks, which use `{rank,label}` with exact TEML labels.

Missing fields retain `present:false`, no raw value and mapped null. Optional
movement roots retain explicit null rather than inventing zero speed. Own
declared data properties are read even on nonplain serialized containers;
inherited properties, getters and methods are never used as fallbacks. Malformed
admitted fields produce actionable `ReadFailed`. Python admits transformed basis
only for this exact allowlist and rejects contradictory null movement parents
and present descendants on the same page. Source at the same path can legitimately
differ; it stays in a separate source record with source basis.

The section is always partial with `other_statistics_pending`, additionally
`current_fields_unavailable` when selected leaves are unavailable and
`pagination` while more section records remain. Senses, languages, IWR, skill
totals, generated Strikes, target-dependent modifiers and full current-state
views remain outside this initial section. A true registry effective-support
flag indicates these selected delivered values, not a complete current sheet.

Existing count/byte limits and unchanged cursor inputs apply: default 50 records,
maximum 100; default/max 48,000 UTF-8 bytes, minimum 8,000. Continue only with
returned cursors until null; partial scope can remain after pagination completes.
Current selected values participate in revision checks even when persisted
source has not changed. On `ContentChanged`, discard accumulated pages and restart.

## Public extraction boundary and system data evidence

Grounded Docs `foundry-vtt`, version `14`, was checked with `list_libraries`,
`find_version`, `search_docs`, and `fetch_url`. The official public
[DataModel.toObject(source)](https://foundryvtt.com/api/v14/classes/foundry.abstract.DataModel.html#toobject)
accepts `source = true` by default; `false` selects transformed values rather
than underlying source values. It returns an extracted primitive object. This
is a public extraction boundary, not a promise that every runtime getter or
prepared property appears in the serialized result. Matching major-version
documentation still requires checking behavior on the installed build.

PF2e-specific field meaning comes from upstream **Actor system document-data
definitions**, rather than community Foundry declarations or sheet classes:

- [CreatureSystemData and related types](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts)
  declare attributes, saves, skills, Perception, and movement.
- [CharacterSystemData and overrides](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts)
  declare character attributes, saves, skills, Perception, and proficiency ranks.
- [Actor base data](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/data/base.ts)
  defines HP and attribute-based statistic trace semantics.
- [Statistic trace data](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/data.ts)
  explicitly describes data merged into Actor data. It separately defines
  `StatisticChatData` as rendering data; that rendering interface is not the
  proposed extraction contract.
- [FamiliarSystemData and source exclusions](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts)
  declare derived document data while excluding ordinary independent
  saves/skills/Perception from familiar persisted source.

Under the repository's explicit permission to use PF2e document schemas,
selected primitive document-data leaves are admissible candidates. Their
derived origin alone does not make them private or sheet preparation state.
Conversely, a TypeScript interface containing a property does not authorize an
unrestricted dump: document-data interfaces also contain helper objects and
rendering-related structures. The bounded allowlist below needs field-specific
serialization verification and exact version constraints before production
adoption; the evidence below covers the delivered NPC statistics subset,
excluding skills.

## Candidate primitive allowlist

Paths are relative to `actor.toObject(false).system`, not persisted source.
Unless marked optional or nullable, the upstream transformed type declares the
leaf required and non-null. Missing or malformed serialized leaves must remain
unavailable; never substitute zero, source values, or a runtime getter silently.

| Paths | Declared type and interpretation |
| --- | --- |
| `attributes.ac.value` | `number`: AC DC, through `CreatureACData` / `ArmorClassTraceData`. Do not interpret it as a check modifier. |
| `attributes.ac.breakdown`, `attributes.ac.details` | `string`: calculation explanation and exceptional prose, respectively. |
| `attributes.hp.value`, `attributes.hp.max`, `attributes.hp.temp` | `number`: current, maximum, and temporary HP, kept distinct. Creature data declares `ActorHitPoints`; character data instead declares `CharacterHitPoints extends HitPointsStatistic`, whose three selected values are explicit numeric fields. Serialization coverage must be checked for that object representation. |
| `saves.{fortitude,reflex,will}.value`, `.totalModifier` | `number`: save modifier, through `SaveData` / `AttributeBasedTraceData`. These are not proficiency ranks. |
| `saves.{fortitude,reflex,will}.breakdown` | `string`: explanation of the corresponding statistic. |
| `saves.{fortitude,reflex,will}.rank` | Character only: integer `0..4`, the declared TEML proficiency rank. No familiar/NPC rank assumption. |
| `perception.value`, `perception.totalModifier`, `perception.breakdown` | `number`, `number`, `string`: Perception modifier and its explanation, through `CreaturePerceptionData` / `PerceptionTraceData`. |
| `perception.vision` | `boolean`: whether the creature has standard vision. Not a complete visibility/line-of-sight result. |
| `perception.rank` | Character: required integer `0..4`; shared creature declaration: optional integer `0..4`. Missing does not mean untrained. |
| `skills.*.value`, `.totalModifier`, `.breakdown` | **Future candidate, not delivered:** `number`, `number`, `string`: skill/Lore modifier and explanation. Preserve the original skill key; a generated key is not a document selector. |
| `skills.*.lore`, `.itemId` | **Future candidate, not delivered:** shared `SkillData`: optional `boolean`, optional `string or null`. Preserve an available Lore Item relationship within the same actor context; do not invent one. Character `Required<SkillData>` requires these properties but retains `itemId` nullability. |
| `skills.*.rank` | **Future candidate, not delivered:** character required integer `0..4`. Do not assume the same rank contract for every actor type. |
| `movement.speeds.land.{value,base,type,source}` | `number`, `number`, literal `"land"`, `string or null`: transformed movement total, base, mode, and recorded source. |
| `movement.speeds.{burrow,climb,fly,swim}` | Each mode is a trace object or `null`; on an object, `value`/`base` are numbers, `type` identifies the mode, and `source` is `string or null`. Null is not a zero-speed mode. |
| `movement.speeds.travel.{value,base,type,source}` | `number`, `number`, literal `"travel"`, `string or null`: travel statistic; present it separately from encounter land Speed. |
| `abilities.{str,dex,con,int,wis,cha}.mod` | `number` when the optional creature `abilities` record exists; character requires the record. Do not fabricate independent familiar attributes. |
| `abilities.{str,dex,con,int,wis,cha}.base` | Character only: `number`, the attribute modifier before Item modification. Keep it separate from transformed `mod`. |

Movement contracts are defined in
[SpeedStatisticTraceData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/speed.ts),
AC in
[ArmorClassTraceData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/armor-class.ts),
Perception in
[PerceptionTraceData](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/perception.ts),
and character HP numeric fields in
[HitPointsStatistic](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/system/statistic/hit-points.ts).

`StatisticTraceData.value` is explicitly context-dependent. Use the declaring
statistic's semantics rather than treating all `value`, `dc`, and
`totalModifier` leaves interchangeably. Retain selected source beside the
transformed view and identify its extraction basis. These transformed snapshots
do not promise every target-dependent roll modifier or conditional exception.

## Exclusions and remaining acceptance work

- Do not adopt private `CharacterPF2e.prepareStrike`, invoke preparation methods,
  or read `system.actions` merely because it appears in a type. Generated PC
  Strikes, alternate usages, and final damage retain a separate supported
  read-only interface gate. An owned weapon remains different from a Strike.
- This proposal does not establish condition active/suppressed state or effect
  expiry. Stored condition/effect presence is not current application. Runtime
  `Condition.active`, prepared `system.expired`, and candidate system query
  methods need their own supported-contract review.
- `getRollData()` returning an Actor reference does not authorize every nested
  prepared property. System methods such as `getStatistic` are not necessary
  for the bounded serialization proposal and are not certified here.
- `source?: never` establishes a source-versus-transformed distinction; it does
  not itself prohibit a declared transformed document-data field. Familiar
  master-derived values still require a valid, permission-checked master and
  representative verification. Missing/deleted/denied master responses must
  remain partial. Do not infer normal familiar Strikes or independent attributes.

Remaining acceptance work must preserve focused source-versus-transformed tests
and missing/null distinctions. The evidence below verifies selected NPC leaves
on installed 14.369/8.6.1, including an elite and a synthetic context. Verify
representative character and master-linked familiar contexts and remaining
allowed fields using existing authorized development fixtures.
The absent persistent PC/familiar fixtures remain a live-verification gap.
The read-only probe below does not close those gaps. Keep generated Strikes
and current-state acceptance open until their independent contracts and checks
are satisfied. No v13 or future-version compatibility is established here.

## Observed bounded serialization evidence

On October 23, 2026, `.venv/bin/python scripts/actor-current-probe.py` completed
two read-only MCP calls in the existing GM development world (the second also
verified every present movement `type` equals its selected mode key), guarded to
Foundry **14.369**, PF2e **8.6.1**, `http://localhost:30000`, world `test`.
It compared public `toObject(true)` and `toObject(false)` selected leaves on
one existing elite world NPC and one existing unlinked synthetic NPC. Finding
the elite sample inspected only the persisted adjustment field of 43 already
loaded, readable world NPCs (hard bound 200); no packs were hydrated. No Actor,
Item, Token, Scene or other game document was created or changed.

Each sample checked 56 fixed coverage paths: six ability modifiers; three AC
fields; three HP fields; nine save fields; five Perception fields; and each of
six movement mode roots plus four selected leaves. Object roots report type
only; string leaves report length and source/transformed equality without
disclosing text, names or IDs. Numbers and booleans retain their actual values.
Character-only ability bases/save ranks were not applicable to these samples.
Skills were outside this probe and the initial current-statistics helper.

| Observed selected fields | Elite world NPC | Synthetic NPC |
| --- | --- | --- |
| Six ability `.mod` leaves | All numeric; source and transformed equal | All numeric; source and transformed equal |
| AC | `value` 22 → 24; transformed-only string `breakdown`; empty string `details` unchanged | `value` 29 → 29; transformed-only string `breakdown`; empty string `details` unchanged |
| HP | `value` 85 → 85; `max` 65 → 85; `temp` 0 → 0 | `value`/`max` 160 → 160; `temp` 0 → 0 |
| Save `.value` | Fortitude 10 → 12, Reflex 13 → 15, Will 10 → 12 | Fortitude 22 → 22, Reflex 17 → 17, Will 19 → 19 |
| Save `.totalModifier` / `.breakdown` | All transformed-only; numeric totals match corresponding transformed `.value`; string breakdowns | Same coverage/types; totals match `.value` |
| Perception | Transformed-only numeric `value`/`totalModifier` 10 and string `breakdown`; `vision` true unchanged; `rank` absent in both | Transformed-only numeric `value`/`totalModifier` 21 and string `breakdown`; `vision` true unchanged; `rank` absent in both |
| Land/travel movement | Both transformed-only objects; numeric `value`/`base` 20, string mode type, null `source` | Both transformed-only objects; numeric `value`/`base` 25, string mode type, null `source` |
| Other movement modes | Burrow/climb/fly/swim explicitly null transformed roots; subordinate leaves absent | Burrow/climb null; fly numeric `value`/`base` 20 and swim 30, string mode types, null `source` |

The elite sample has 39 present transformed coverage paths (including two
object roots), versus 15 present source paths. The synthetic sample has 47
present transformed paths (including four object roots), versus 15 source
paths. After replacing optional null movement modes with their root marker and
excluding object roots, these correspond to 38 and 44 helper descriptors,
respectively; only optional NPC `perception.rank` is missing. Null movement
sources and unavailable modes remain distinct from missing fields and zero.
All observed AC/save/Perception breakdowns survived transformed serialization;
this does not prove their presence on other Actor types or configurations.

This evidence verifies the selected serialization route, not production MCP
integration, target-dependent roll results, all elite/weak behavior, or complete
Actor stories. Persistent character and familiar/master samples remain absent;
character HP object serialization, character ranks/bases, familiar dependencies,
missing-master behavior, non-null movement source strings, and additional
conditional effects still need representative checks. No runtime getter,
preparation method, sheet data, or private implementation member was adopted.

`scripts/actor-current-probe.py --verify` is the separate read-only integration
check. It discovers the actual MCP schema/description and statistics support
flags, independently selects expected transformed primitives without importing
the extraction helper, and exhausts `read_actor` continuations at `limit=7`,
`max_bytes=8000` for the existing elite world/synthetic samples. It checks exact
raw paths, presence, values, transformed basis, canonical identity/token context,
partial reasons and unchanged public source hashes before/after. It prints only
sample/page/record counts.

The first integration run after server restart/browser refresh passed actual
MCP discovery, registry flags and the independent serializer snapshot, then
failed at the first elite-world-NPC `read_actor` call with `ReadFailed`:
"Selected transformed statistics do not match the verified schema or cannot
be serialized." No page was returned, so paginated MCP integration and the
after-read hash comparison were not established by that run. The bounded
serialization evidence above remains distinct from production integration.

A single `--diagnose` call reproduced the failure through this repository's
exported `currentStatisticFields` helper and inspected only selected public
serialization paths. In both samples the failure was
`/system/attributes/hp/value`: the serialized HP container was an object with a
non-plain prototype, while `value`, `max` and `temp` each had an own data
descriptor. Other selected non-null containers passed the plain/own-data checks;
missing Perception rank and null optional movement modes were expected. This
identifies an overly strict container-admission assumption, without establishing
any contract for the HP object's prototype, methods or getters. The diagnostic
did not inspect private keys, invoke getters, or disclose object values.

After the HP container admission fix and development-browser refresh, one
`--verify` rerun passed: **2 existing NPC samples, 13 `read_actor` pages and
82 records** (elite world: 6 pages/38 records; synthetic: 7 pages/44 records).
Every page used `limit=7`, `max_bytes=8000`; returned continuations were passed
unchanged until null. Exact independently selected raw path/presence/value and
transformed basis matched across all records, canonical world/token identity
and synthetic context were retained, and every page remained partial with
`other_statistics_pending` and applicable `current_fields_unavailable`.
Actual MCP discovery descriptions/input schemas and registry flags passed;
public source SHA-256 hashes and selected transformed snapshots were unchanged
before/after the complete read. Values, hashes, names and identifiers were kept
out of the printed integration summary. It does not close the
character/familiar or complete-current-state gaps recorded above.

The subsequent marked-character check passed **47 statistics records across
seven pages**, matching independently selected serialized values and retaining
source fingerprints, followed by confirmed fixture cleanup. See the
[verification record](current-statistics-verification.md) for the full delivered
scope, regression evidence and remaining limitations.
