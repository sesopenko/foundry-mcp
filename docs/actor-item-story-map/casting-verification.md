# Actor casting joins: rulebook and runtime verification

Verified 2026-10-22 against Foundry **14.369 / PF2e 8.6.1**. This evidence concerns recorded source and owner-local relationships. It does not establish usable casting resources, spell legality, derived statistics or successful casting.

## Rulebook evidence and schema boundary

Reuse the complete actual-book reads recorded in [spellcasting-entry verification](spellcasting-entry-verification.md): Player Core Remaster printed 297–299 (physical 298–300), revision `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`; GM Core Remaster printed 123 (physical 124), revision `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e`. These were complete canonical text reads with no remaining continuation. No new table interpretation is asserted here.

Individual prepared uses, spontaneous repertoire and shared slot resources, innate per-spell frequency, cantrips and a shared focus pool have different rulebook meanings. Repeated preparations must remain separate. A generic zero slot counter does not erase prepared records. Missing expenditure flags or uses do not prove availability. GM Core's creature-specific focus/slot exception prevents imposing the PC focus resource model universally.

Pinned upstream revision: `28d9d156f252d084371d994dc359509b49eadf18` (PF2e 8.6.1):

- [Character source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/character/data.ts): `CharacterResourcesSource` lines 194–196 declares optional `focus: { value: number; max?: never }`. The later prepared `CharacterResources` interface includes value/max/cap; it is not a persisted-source contract. A source reader must exclude character focus max/cap, including when encountered as unexpected source members.
- [Creature source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/actor/creature/data.ts): optional `resources` and optional `CreatureResourcesSource.focus: ValueAndMaybeMax` allow a stored current value and optional maximum. The later prepared `CreatureResources` adds cap; that cap must not be read as persisted source.
- [Spell source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spell/data.ts): `location.value` is a nullable owner-local casting-entry ID; signature, heightenedLevel, autoHeightenLevel and innate uses are independent optional fields. Base `level.value`, configured heightened rank and slot rank remain distinct. `traits.value` retains cantrip/focus context independently of entry mode.
- [Entry source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/data.ts): a preparation position is distinct from its possibly repeated spell ID. The documented template slot11/interface discrepancy and historical object-to-array migration remain as recorded in the entry verification; reading must not migrate documents.

Join only within the selected actual Actor instance. A spell's claimed entry and a preparation's claimed spell are separate relationships; resolving both does not prove that the preparation's spell claims the same entry. Preserve missing, wrong-type, denied, unassigned and conflicting claims. Never use a same-named spell, unrelated owner, base Actor fallback or fabricated UUID to repair them.

## Existing read-only runtime audit

Authenticated `execute_javascript` inspected public world Actor/Item collections and `toObject(true)`. No document writes, migrations, casting, preparation, expenditure, rolls, chat or enrichment occurred. The ignored reproducible selector `.local/casting-selector.js` dynamically selects Actors for each observed mode, repeated preparation and unassigned spell, and returns canonical identities plus complete source SHA256 fingerprints in bounded 800-character chunks.

| Observation | Result |
| --- | --- |
| Supported world Actors | 172, all NPC; no character/familiar fixtures |
| Owned spells / casting entries | 791 / 85 |
| Entry modes | 14 prepared, 11 spontaneous, 49 innate, 11 focus |
| Actors with multiple distinct modes | 24 |
| Unassigned spells (null/empty/missing location) | 20 |
| Nonempty spell location missing target / wrong target type | 0 / 0 |
| Prepared nonempty spell ID missing target / wrong type | 0 / 0 |
| Resolved prepared spell claiming a different entry | 0 |
| Slot groups with repeated nonempty spell IDs | 9 |
| Persisted NPC focus present / absent | 54 / 118 |
| Present focus record key shape | All 54 contain exactly value and max |
| Innate spells / cantrips within those spells | 325 / 84 |
| Innate per-spell uses present / absent | 9 / 316 |
| Spontaneous spells | 185; all omit signature |
| Spells assigned to focus entries | 17 with focus trait, **5 without** |

Focus mode and a focus trait are therefore distinct source facts. Do not infer universal pool consumption or assign entry identity from traits alone. Recorded focus samples retain value/max 1/1 and 2/2; absence on another Actor means unknown, not exhausted or unlimited.

The prepared and focus selectors select the same existing multi-mode NPC; the spontaneous selector selects another NPC with spontaneous and focus entries. The innate and unassigned selectors select additional existing NPCs. Every selected complete serialized Actor source remained byte-for-byte unchanged during this inspection, with SHA256 computed through standard browser crypto. This establishes read-only audit behavior, not yet the implementation's read-only behavior.

## Acceptance verification still required

Actual authenticated `read_actor` calls must consume all casting pages, compare raw source, mapped meanings, provenance and canonical owner/token identities against selected source, follow returned spell/entry selectors, and verify unchanged complete source fingerprints after reads. Live fixtures cover the four observed entry modes, repeated preparations, shared NPC focus and unassigned spells. Available evidence does not establish live character/familiar focus, explicit signature flags, populated legacy object preparations, missing/wrong-type joins, mismatched location/preparation claims or denied targets; deterministic tests must establish these boundaries without manufacturing world data. Current availability remains unproven when required source flags or frequency data are absent.

## Actual Actor casting source-checkpoint verification

Authenticated MCP consumed every spellcasting page for four selected Actor
contexts, including a selected scene token. The sample covers prepared,
spontaneous, innate and focus entries. Actual entry/spell reference UUID sets
matched the selected owner's Items; follow-up identity reads retained supplied
token context. Every assignment matched source local-ID ownership; repeated
preparations retained separate records. Actor source focus values/maxima and
absence matched persisted source. All complete Actor source fingerprints remained
unchanged after reading, and every record key was unique. The section remained
partial with `availability_not_evaluated`; effective remained unsupported.

Deterministic tests additionally cover character exclusion of derived focus max,
missing/denied/wrong-type/mismatched targets, legacy preparation partial source,
signature/configured rank separation, independent expenditure flags, missing
spell parents, synthetic selectors, stale preparations and non-PF2e rejection.
Python rejects cross-owner/fabricated selectors, wrong provenance, derived
character max and any false complete availability claim. Full suites passed:
242 Python tests (one skipped) and 272 JavaScript tests. An unrelated
effect-name-bound regression caught during validation was restored and its
existing failing test passed before the successful full run.

No spell, Actor or Item was cast, prepared, imported, rolled or written. This
checkpoint does not prove current castability, usable focus/innate resources,
signature rank options or specialized mode execution. CORE-casting stays open;
character/familiar live casting and absent/mismatched assignment cases remain
unavailable in the existing world, with deterministic source-boundary coverage.

## Eligibility-interface audit — October 22, 2026

Read the pinned [entry canCast implementation](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/spellcasting-entry/document.ts#L243-L265).
Its result tests item origin, casting-feature eligibility, tradition or list
membership. It does not inspect remaining preparations, expended flags, slots
or focus resources. Therefore it cannot establish current availability. This
source inspection explains behavior; it does not by itself establish an external
API contract, and production does not adopt this method. Explicit contextual
option presentation remains separate work. Any future claim of complete current
availability retains the original story's mode-specific verification requirement.

## Canonical contextual-rank reads — October 25, 2026

Browser-independent PDF MCP retrieval reread Player Core Remaster and read the
Bard Signature Spells class feature. The ready book's revision was
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
Every row below is an actual complete `read_pdf_pages` response, not a search
snippet; `next_offset` was null on each page.

| Printed label | Physical page | Total canonical characters |
| --- | --- | --- |
| 99 | 100 | 5095 |
| 297 | 298 | 5261 |
| 298 | 299 | 5706 |
| 299 | 300 | 5273 |

Printed 297 distinguishes individual preparations from spontaneous repertoire
and requires knowing a spontaneous spell at its heightened rank. Printed 298
explicitly permits spending a higher spontaneous slot while casting at the
known lower rank, without heightened benefits. It also establishes ordinary
cantrip/focus automatic heightening and one shared focus pool. Printed 299
distinguishes innate granted ranks, ordinary inability to heighten innate spells,
and innate-cantrip exceptions. Granting abilities may change those innate rules.

Printed 99's Bard Signature Spells feature permits heightening designated spells
without separately learning each rank. A signature spell learned above its
minimum also permits lower-rank versions without separate learning. This is
evidence for the class feature's entitlement; a stored
`/system/location/signature` flag records configuration and does not independently
prove acquisition, eligibility, available slots or legal casting. Do not apply
the Bard feature to every Actor, entry mode or arbitrary flagged spell.

All pages retain reading-order/table-structure warnings. No numeric table
relationship was inferred. No private extracted text is committed. The
[proposed contextual-option contract](casting-options-contract.md) distinguishes
these verified rules from configuration-only presentation and deferred rank
evaluation. These reads do not close CORE-casting's live availability gate.
