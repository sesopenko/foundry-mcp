# Actor spellcasting source joins

This is a source-reading checkpoint for CORE-casting, audited against PF2e **8.6.1** and Foundry **14.369**. It does not establish current spell availability; contextual option presentation and the story's conditional availability verification remain separate work.

The public document boundary reads the selected Actor's actual owned Item collection and each readable spell or spellcastingEntry's `toObject(true)` source. It retains real Item UUIDs and the selected token context. No UUID is synthesized for a nonexistent relationship; another Actor's matching local ID cannot supply a target. No casting, preparation, expenditure, statistic getter, sheet state or recursive hydration is used.

| Record | Selected source and meaning |
| --- | --- |
| `casting_entry`, `casting_spell` | Actual readable immediate Item identity; source `/name` and `/type` contributors. Follow its returned `target_uuid` with `read_item`, retaining returned `token_uuid`. |
| Entry source fields | Existing `pf2e.spellcasting-entry.source.v1` scalar mappings, now in `spellcasting`: mode, flexible/items configuration, tradition, ability, proficiency, authored attack/DC, auto-heighten configuration, per-slot counters and individually indexed preparations. |
| Spell source fields | Existing `pf2e.spell.source.v1` mappings for base rank, ordered traits and location assignment, signature flag, configured heightening and innate uses. No descriptions, overlays or damage expansion here. |
| `casting_spell_assignment` | `/system/location/value` source local ID resolves only to an owned casting entry. Null/absent/empty stays missing; it does not imply an unlimited spell. |
| `casting_preparation` | Every valid preparation position has its own `/system/slots/slotN/prepared/I/id` contributor and record key, including repeated spell IDs. Resolution also requires that spell's location assignment identify the same entry. |
| `casting_focus_value`, `casting_focus_max` | Actor `/system/resources/focus/value` and optional creature source `max`. Character source explicitly excludes `max`; no prepared capacity is substituted. Zero and absent remain distinct. |
| `casting_item` | Generic denied marker with empty raw/contributor arrays; unreadable Item metadata is withheld. |

All new join/focus records use `pf2e.actor.casting-source.v1`, with limitations `source_configuration_only` and `availability_not_evaluated`. Existing typed source fields retain their original mappings and limitations. Resolved relationship values contain `status`, `target_uuid`, `type`, `name`, `name_truncated`, and optional `token_uuid`. Unresolved values contain only `status` and null `target_uuid`: `missing`, `denied`, `unsupported`, or `mismatched_assignment`.

Every result remains partial with `availability_not_evaluated`. Flexible, ritual, items and unknown modes additionally report `unsupported_casting_mode`. Malformed legacy preparations retain the entry selector's exact incomplete reasons, preserving valid siblings instead of fabricating normalized arrays. Shared reader continuation and byte limits apply to the detached records; the complete selected snapshot participates in revision checks.

A prepared slot's generic value of zero does not cancel unexpended preparation records. An innate cantrip's use counter is preserved without declaring exhaustion or unlimited use. Signature flags and configured heightened ranks are separate source facts, never calculated rank choices. Focus pools are shared Actor source records; their presence does not evaluate whether a particular spell can currently be cast. Slot11 remains an opaque upstream template key with no invented spell-rank semantics.

Source contracts: [spell source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts), [entry source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts), [character source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts), [creature source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts).

Deterministic coverage: `tests/js/actor-casting.test.js` verifies repeated preparations, zero and expended counters, separate configured ranks, absent focus, character exclusion of max, wrong-type/missing/denied/mismatched joins, malformed legacy containers, unsupported modes, synthetic token context and rejection of unrelated-field evaluation. Runtime evidence and remaining acceptance gates belong in the separate casting verification record; these deterministic cases do not prove current castability.

Snapshot complexity is bounded separately from pages: over 12,000 owned Items
or 24,000 selected records rejects with ReadFailed. Required focus value rejects
explicit undefined; only an optional creature focus maximum may treat undefined
as absent. No missing value is replaced with prepared state.
