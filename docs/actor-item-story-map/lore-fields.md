# Lore source field boundary

PF2e-specific `lore` selector baseline: **PF2e 8.6.1 / Foundry 14.369**.
`actorLore.js` consumes detached document source only. It does not call Foundry
or PF2e preparation, skill getters, rolls, enrichment, or mutation APIs.

The authoritative pinned [LoreSystemSource interface](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/lore.ts)
contains the following selected fields. Shared fields come from
[ItemSystemSource](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/system.ts).
The interface is schema evidence; its preparation implementation explains owner
semantics but is **not** called or adopted as an external API.

| Source path | Descriptor concept | Meaning and boundary |
| --- | --- | --- |
| `/system/mod/value` | `npc_lore_authored_modifier` / `stored_lore_modifier` | Finite numeric authored value. Owner context is required; never advertised as an effective total. |
| `/system/proficient/value` | `character_lore_proficiency_rank` / `stored_lore_proficiency_rank` | Original integer 0–4; not a proficiency bonus or check total. Owner context is required. |
| `/system/variants/<key>/label` | `lore_variant_label` | Stored string; exact source key retained using JSON Pointer escaping. |
| `/system/variants/<key>/options` | `lore_variant_options` | Stored options string; not executed or applied. |
| `/system/traits/otherTags/<index>` | `lore_other_tag_code` | Original strings, duplicates and order preserved. No unverified label lookup. |
| `/system/slug` | `source_slug` | Exact string or null; never synthesized from name. |
| `/system/publication/{title,authors,license,remaster}` | `publication_<field>` | Original publication metadata; remaster is boolean. |

Nonempty maps and arrays flatten into typed primitive descriptor leaves. Only
explicitly empty maps/arrays use `{}`/`[]` markers. Missing values remain missing;
optional own `variants: undefined` represents absent serialized source. Null is
accepted only for slug. Malformed selected scalar values are rejected instead
of leaking objects. Unknown extra fields are not selected. No `level`, `ability`,
`traits.value`, `traits.rarity`, rules, flags, private migration, or description
are implicitly included. Descriptions remain the shared reader's explicit view.

## Integration obligations

The reader supplies the actual resolved owner's persisted Actor type to the pure
selector. NPC modifiers use `npc_lore_authored_modifier`; character ranks use
`character_lore_proficiency_rank`. Other contexts use neutral stored concepts.
Rank mapping retains `{rank,label}` with labels Untrained through Legendary.
No mapping calculates an effective modifier, proficiency bonus or ability score.
Item identity includes actual `actor.type` when owned; the Python boundary accepts
its omission from older neutral DTOs without inferring an owner.

Actor `skills` returns actual owned Lore Item references, exact source names,
canonical UUIDs and selected linked/synthetic token context. Duplicate names
remain separate references. Unreadable Items produce a generic denied marker
without names or selectors. This section remains `partial` with
`other_skills_pending`; other Skills and effective totals are not implemented.
Each resolved reference can be followed through `read_item`.

Deterministic coverage in `tests/js/actor-lore.test.js`,
`tests/js/actor-lore-readers.test.js` and `tests/test_actor_lore.py` verifies owner
semantics, escaped variant keys, missing/empty/zero values, duplicate specialties,
permissions, stale membership, bounded descriptions, linked/synthetic follow-up,
actual cross-language DTOs, and the non-PF2e boundary.

## October 20, 2026 verification addendum

Actual rulebook text was read through `list_pdf_documents` and `read_pdf_pages`
from **Pathfinder 2e - Player Core Remaster.pdf**, document
`6e595a7ead90468c99a4f11aa9bac6f8`, immutable revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
The printed labels differ from physical page numbers:

| Printed page | Physical PDF page | Read evidence and relevance |
| --- | --- | --- |
| 84 | 85 | Backgrounds grant trained rank in two skills including a Lore skill; choices are subject to GM approval. |
| 85 | 86 | Adjacent background examples confirm distinct named Lore specialties rather than a single generic Lore skill. |
| 240 | 241 | Lore subcategories each count as their own skill; proficiency increases in one do not increase another. |
| 241 | 242 | Continuation of Lore rules: applicability is decided by the GM; untrained Recall Knowledge and trained Earn Income are distinct. |

All four physical pages returned `next_offset: null` at `offset: 0` with
`max_characters: 8000`; their returned `total_characters` were respectively
4868, 2809, 4131, and 2826. Each requested page was therefore fully read without
continuation. These citations justify specialty identity and rank terminology;
they do not establish a supported runtime effective-check API. Extraction reports
reading order/table structure unverified; no table arithmetic was inferred.

A read-only development audit used the existing GM-connected **14.369 / 8.6.1**
world and `toObject(true)` sources. It found **12 NPC-owned Lore Items**, zero
character-owned, zero familiar-owned, and zero world-level Lore Items. The pure
selector accepted all 12; all 12 omitted variants, and no source had own undefined,
empty, or populated variants. Source JSON fingerprints before and after were
identical. No same-name duplicate Lore specialties occurred within an Actor in
that available set. This records actual fixture coverage without creating game
documents or exposing names, identities or statistics.

Character/familiar owners, standalone world Items, variant source shapes and
duplicate-specialty behavior still require deterministic coverage and suitable
existing fixtures for any corresponding live claim. The final character effective
check interface remains unverified. The selector audit is independent of the
reader's subsequent end-to-end MCP and Actor Skills integration checks.

Actual authenticated MCP discovery and reads subsequently passed on the same
runtime using `./scripts/actor-tools.sh live`. The runner verified NPC-owned Lore
source, owner type, authored modifier, preserved rank, partial Actor Skills and
resolved Item follow-ups. Persisted source fingerprints remained unchanged.
The full offline suites passed: 157 Python tests (one skipped) and 134 JavaScript
tests, zero failures. Character/familiar/world Lore, variants and duplicate
specialties have deterministic coverage only; live coverage is limited to the
available NPC fixtures. These checks do not close effective-statistic gates.
