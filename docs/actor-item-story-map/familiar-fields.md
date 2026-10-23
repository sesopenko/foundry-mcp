# Familiar selected-source field audit

This PF2e-specific ACT-familiar source checkpoint targets PF2e **8.6.1**, pinned
commit `28d9d156f252d084371d994dc359509b49eadf18`. The authoritative
[familiar schema and source interface](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/familiar/data.ts)
separates `defineSchema` persisted fields from prepared declarations. Pure helpers
receive detached source; they do not call Foundry APIs, preparation methods or
the familiar master getter. Shared readers own system/GM/permission admission,
canonical identity, extraction and bounds. No future-version support is claimed.

| Path relative to `/system` | Selected source contract | Meaning and exclusions |
| --- | --- | --- |
| `master/id` | Required nullable `ForeignDocumentField(CharacterPF2e)`, `idOnly: true`, initial null | Stored world Character Actor ID claim; never NPC, pack UUID or token master. Resolve separately with permission checks. Missing source stays missing rather than default null. |
| `master/ability` | Required nullable string, initial null; schema choices `str`, `dex`, `con`, `int`, `wis`, `cha` | Recorded attribute code; preserve unknown stored strings without interpreting them as a recognized attribute. No derived modifier. |
| `attributes/hp/value` | Required nonnullable integer >=0, initial 5 | Stored current HP; no master-derived maximum or clamp. Missing source does not become 5. |
| `attributes/hp/temp` | Required nonnullable integer >=0, initial 0 | Stored temporary HP; absence differs from zero. |
| `attributes/hp/tempSource` | Optional nonblank string, initial undefined | Stored owner-local Item ID claim; no verified Item identity or automatic hydration. Undefined remains absent. |
| `details/creature/value` | Required nonnullable string allowing blank, initial empty string | Exact original creature description, including HTML. Explicit bounded description read only; no enrichment, execution or prose parsing. |

`familiarFields` returns only the first five leaves; `familiarNoteFields` returns
only the description leaf. `familiarMasterField` returns just the `master/id`
descriptor for an explicit identity join. Other Actor types return null. Each
descriptor preserves path, own source presence and exact primitive value;
malformed selected values fail rather than becoming defaults. Mapping boundaries
are `pf2e.familiar.source.v1` and `pf2e.familiar.notes.v1`, with limitation
`familiar_source_not_master_derived_statistics`. Description continuation/count/
byte bounds belong to the existing shared extraction layer, not this selector.

The source interface explicitly excludes ordinary traits, perception, saves,
skills, resources and custom modifiers. Familiar source also excludes creature
IWR, alliance, languages and level. Do not admit inherited creature fields,
independent attributes, prepared attack/movement or `hp.max` even if an unexpected
property exists in a fixture. Stored master linkage and HP do not establish
effective saves, skills, selected-ability benefits or complete familiar state.
Actual owned action Items retain their own identities through existing readers;
this selector neither discovers nor applies abilities.

Reuse the [canonical complete rulebook reads](evidence.md#rulebook-source-reads):
Player Core Remaster printed **212–213 and 259** (physical 213–214 and 260), revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
The ledger records `next_offset=null` for every page, distinguishing familiar
master relationships and familiar/master abilities from pet/companion roles.
No duplicate PDF read or new rule arithmetic is needed for these source leaves.
Reading order/table structure remains unverified; no private extracted text is
copied here. G-FAMILIAR effective derivation and representative live familiar/
master verification remain separate gates, not established by these helpers.
