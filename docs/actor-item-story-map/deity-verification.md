# Deity verification — October 22, 2026

This ledger separates rulebook evidence, pinned schema and read-only runtime
observations for [ITEM-deity](stories/ITEM-deity.md). It establishes selected
definition-source support, never active devotee benefits or actor acquisition.

## Rules actually read

Read through `list_pdf_documents`, `locate_pdf_entry` and `read_pdf_pages` in
the existing private library: **Player Core Remaster**, SHA-256/revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
All following pages returned complete text (`next_offset: null`); physical
pages were respectively 36, 89, 111, 112 and 218. Printed labels are cited below.
Extraction warns that reading order and table structure are unverified; these
conclusions use prose, not inferred table adjacency. No PDF paths or selectors
are needed in published documentation.

| Printed page | Read evidence and consequence |
| --- | --- |
| 35 | Religion distinguishes ordinary worship, pantheons, non-deific religion and philosophy. Devotee benefits require cleric status or a specific granting rule. Divine Attribute relates to Raised by Belief. Definition options therefore do not establish benefits on an Actor. |
| 88 | Raised by Belief explicitly uses the deity's Divine Attribute and Divine Skill, plus related Lore and Assurance. A deity definition does not establish that the background was acquired or its choices applied. |
| 110 | Cleric Deity adds spells to the cleric list, with preparation conditional on available rank. It grants training/access under cleric rules. Sanctification distinguishes optional choice from mandatory trait. Definition spells are neither prepared slots nor an observed character's sanctification choice. Anathema adjudication is not evaluated. |
| 111 | Divine Font describes choosing the available font and preparing additional restricted slots. The definition's font list is separate from selected font, current slots and expenditure. |
| 217 | Cleric Dedication grants specified skill/sanctification benefits and excludes other deity benefits; Basic Cleric Spellcasting separately permits deity spells in appropriate archetype slots. A generic deity-to-all-benefits join would be incorrect. |

## Schema contract

The local research checkout resolves to PF2e **8.6.1** commit
`28d9d156f252d084371d994dc359509b49eadf18`. Its
[deity/data.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/deity/data.ts),
[types.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/deity/types.ts)
and [values.ts](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/deity/values.ts)
define category deity/pantheon/covenant/philosophy, nullable sanctification,
primary/alternate domains, font, attributes, nullable skill, favored weapons
and spell UUID map. See the [field audit](deity-fields.md) for exact extraction.
Schema establishes representation for that version; it does not prove runtime
behavior or justify computing effective benefits.

## Runtime observations

Used the existing authenticated GM browser, **Foundry 14.369 / PF2e 8.6.1**.
`list_actor_compendiums(document_type="Item", query="deit")` located the
readable Deities pack. Three explicit literal index queries selected Abadar,
Asmodeus and Green Faith; each completed with one match. Only those three
definitions were hydrated. No bulk `getDocuments`, import, creation, update,
roll, activation or chat operation was performed.

A bounded development probe read each selected document using public async
`foundry.utils.fromUuid`, `testUserPermission` and `toObject(true)`. Grounded
Docs found the official v14 index and documented source extraction; inherited
public document contracts are linked in the [shared evidence](evidence.md#public-foundry-api).
Probe selectors remain in ignored `.local/deity-selector.js`, not this ledger.

| Fixture | Actual selected source | Refreshed MCP read |
| --- | --- | --- |
| Abadar | category deity; can holy/unholy; harm/heal; con/int; society; crossbow; four primary/four alternate domains; three spell claims | 34 records, two description fragments, three resolved spell references |
| Asmodeus | category deity; must unholy; harm; empty attribute array; deception; mace; four primary/three alternate domains; three spell claims | 30 records, two description fragments, three resolved spell references |
| Green Faith | category covenant; can holy; heal; con/wis; nature; sickle/claw; seven primary/five alternate domains; three spell claims | 36 records, one description fragment, three resolved spell references |

The empty Asmodeus attribute array is preserved even though printed p.35
describes an unrestricted attribute choice; source emptiness is not interpreted
as no allowed attribute. Green Faith is a non-deific religion in p.35 prose and
stored category covenant in this runtime; neither is coerced into a creature.

Initial reads before refresh correctly exposed the old pending reader and are
not passing evidence. After the root task restarted the service and refreshed
the development tab, a fresh authenticated SDK client called `read_item` with
`identity/source/description/relationships`, limit100, for each fixture. All
three returned those four sections complete in one page each, with null next
cursor: **three calls, three pages, 100 records, nine resolved immediate spell
references**. Source concepts included sanctification, options, spell claims
and metadata. Resolved targets were actual spell Items; Abadar resolved to
Illusory Object/Creation/Planar Palace, Asmodeus to Charm/Suggestion/Mislead,
Green Faith to Summon Animal/Speak with Animals/Wall of Thorns. Resolution
returned identity only; no target source or recursive spell expansion occurred.

The reusable deity block in `scripts/actor-live-check.py` was then executed
independently through the same fresh-client pattern: **16 calls** (one index
selector probe and five per fixture: source probe, source/prose/effective read,
relationship read, one target identity follow-up and final fingerprint probe).
It passed all three samples and nine links, comparing selected raw paths and
values against public source, exact complete prose hashes, mapping identifiers,
explicit effective-section exclusion, spell target types and unchanged source
fingerprints. This is bounded deterministic live verification, not a fresh-agent
evaluation. Full regression execution remains owned by the root task.

## Remaining limits

This live sample covers two deity definitions and one covenant, optional and
mandatory sanctification, ordinary option arrays, empty attributes, exact
description fragments and nine successful spell links. It does not live-test
pantheon/philosophy categories, null sanctification/skill, missing/denied/bad
spell links, forced pagination/staleness, world or owned/token deity contexts,
or a populated cleric's acquisition state. Deterministic tests must cover those
branches separately. No live v13, other system version, active-benefit,
effective-statistic, spell preparation, font expenditure or automatic rule
application support is established by this audit.

Final regression suites passed:301 Python tests (one skipped),370 JavaScript tests.
The reusable full live check passed, including3 deity samples and9 spell links;
the dedicated GM browser reported zero console errors.
