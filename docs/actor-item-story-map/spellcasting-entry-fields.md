# Spellcasting-entry selected-source fields

PF2e-specific, audited against [SpellcastingEntrySystemSource 8.6.1](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts) and [the same revision's source template](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/static/template.json#L571-L632). Detached `Item.toObject(true)` source only; no prepared statistics, sheet collections, casts or resource changes.

| Source paths under `system` | Meaning |
| --- | --- |
| `tradition.value`, `prepared.value` | Exact tradition and casting-mode codes, including unknown codes |
| `prepared.flexible`, `prepared.validItems` | Optional stored configuration; missing and null remain distinct |
| `ability.value`, `proficiency.value` | Stored ability code and proficiency rank; no effective statistic calculation |
| `spelldc.value`, `spelldc.dc` | Authored attack/DC source numbers, never advertised as final PC statistics |
| `autoHeightenLevel.value` | Configured rank or explicit null, never applied to spells |
| `slots.slot0` through `slots.slot11`: `value`, `max` | Exact independent stored numbers; zero does not prove exhaustion |
| `slots.slotN.prepared.<index>.id`, `.expended` | Nullable local spell-ID claim and independently stored flag; repeats retain original indexes |
| `traits.otherTags`, `slug`, `publication.{title,authors,license,remaster}` | Exact source metadata; tags preserve order |

The TypeScript interface declares slot0 through slot10; the official pinned template also declares slot11. The selector retains slot11 as an opaque template slot with the explicit limitation `template_slot11_no_spell_rank_semantics`. It does not infer an 11th spell rank. Keys outside slot0 through slot11 are omitted and reported as `unsupported_slot_key` issues with JSON Pointer escaped source paths.

Prepared arrays are not normalized: absent preparations remain absent, empty arrays remain empty, nullable IDs remain null and repeated IDs remain separate. Absent `id` or `expended` leaves remain absent; notably absent expenditure flags are not converted to false. Invalid legacy containers, array members or member leaves generate structured issues (`malformed_preparations`, `malformed_preparation`, `malformed_slot`) and omit only invalid values, retaining safe sibling fields. No arbitrary malformed source object is dumped and no synthetic absent marker replaces a present invalid value. Callers must report source as partial whenever issues are returned.

`spellcastingEntryFields(source)` returns descriptors or null for other Item types. `spellcastingEntryIssues(source)` returns `{path, reason}` gaps or an empty array. Non-preparation invalid selected scalars reject with an actionable source path rather than coerce. Selection rejects more than 12,000 descriptors, 6,000 preparations in an array or 64 issues rather than truncate silently. Descriptions remain a separate explicit bounded read; rules, flags, migration records, unrelated fields and UI state are excluded. Casting-mode codes remain distinct but no current castability, remaining-use inference, focus-pool total, prepared spell join or resource application is computed here.
