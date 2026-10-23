# Candidate contract for transformed current statistics

Targeted audit: October 23, 2026. Contract target: Foundry **14.369**, PF2e
**8.6.1**, upstream revision
`28d9d156f252d084371d994dc359509b49eadf18`.

**Proposal, not implementation or runtime verification.** This audit identifies
a bounded extraction route for the effective/current checkpoints in
[ACT-character](stories/ACT-character.md), [ACT-npc](stories/ACT-npc.md), and
[ACT-familiar](stories/ACT-familiar.md). It does not close those checkpoints or
replace their original acceptance criteria with source-only delivery.

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
rendering-related structures. The bounded allowlist below needs serialization
verification and exact version constraints before production adoption.

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
| `skills.*.value`, `.totalModifier`, `.breakdown` | `number`, `number`, `string`: skill/Lore modifier and explanation. Preserve the original skill key; a generated key is not a document selector. |
| `skills.*.lore`, `.itemId` | Shared `SkillData`: optional `boolean`, optional `string or null`. Preserve an available Lore Item relationship within the same actor context; do not invent one. Character `Required<SkillData>` requires these properties but retains `itemId` nullability. |
| `skills.*.rank` | Character: required integer `0..4`. Do not assume the same rank contract for every actor type. |
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

Next implementation work should establish focused source-versus-transformed
tests, verify exactly which allowed leaves survive `toObject(false)` on the
installed 14.369/8.6.1 runtime, and preserve missing/null distinctions. Verify
representative character, master-linked familiar, elite/weak or affected NPC,
and synthetic token contexts using existing authorized development fixtures.
The absent persistent PC/familiar fixtures remain a live-verification gap;
this audit performs no game writes or runtime probes. Keep generated Strikes
and current-state acceptance open until their independent contracts and checks
are satisfied. No v13 or future-version compatibility is established here.
