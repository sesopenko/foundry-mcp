# NPC Actor acceptance

Audited October 28, 2026 for Foundry **14.369 / PF2e 8.6.1**. This closes
[ACT-npc and M-NPC](stories/ACT-npc.md) for their declared supported/partial
views. It does not certify every current creature mechanic or complete
CORE-token/CORE-acceptance.

## Original requirements and evidence

| Requirement | Implementation and authoritative evidence | Result |
| --- | --- | --- |
| Identity/level/traits, source attributes/skills/defenses/HP, senses/languages/movement/IWR and exceptional notes | `actorNpc.js`, explicit notes selector and production readers; `actor-npc.test.js` checks authored modifiers, special-skill predicates, AC/save/HP/movement notes, sense range and compound IWR exceptions. [NPC source contract](npc-fields.md) records runtime source/biography proof. | Verified source checkpoint. Unknown codes and exact notes survive; no elite/weak math or PC construction is imposed. |
| A source-only NPC without spells remains useful with explicit unread sections | `actor-npc-readers.test.js` uses an Actor with no owned Items, paginates authored values, checks `effective` unsupported, private-note exclusion and source fingerprints. | Verified; spell absence does not prevent basic creature reading. |
| Ranged `melee`, multiple damage components, duplicate names and special skills retain context | `actor-melee-readers.test.js` checks range plus independent acid/fire and persistent damage components while carried weapon damage is unrelated; NPC reference tests retain separate duplicate Item UUIDs. Special-skill base/notes/predicates remain selected source. | Verified authored attacks and exceptions. Current conditional variants and final damage remain unevaluated. |
| Preserve source/base versus elite/weak/current values | Current-statistics runtime proof retains source AC 22 versus current 24, source maximum HP 65 versus current 85, on an existing elite NPC; a separate unlinked instance also passes. `actor-integrated-readers.test.js` checks separate source/current witnesses across combined sections. | Verified selected current values; no local adjustment arithmetic or full target-context claim. |
| Current senses, language qualifications and IWR declarations have supported runtime evidence | [Current-statistics verification](current-statistics-verification.md) records world/synthetic NPC supplements: 14/10 selected supplemental records independently compared against public serialization, with unchanged source/current fingerprints. | Verified those selected NPC declarations, not damage application, perception detection or every optional configuration. |
| Current ordinary skills and owner-local Lore joins are distinct from source rank/modifier contributions | `actor-skills-live-check.py` independently compares returned selected witnesses, exact source Lore membership and actual Item-ID joins; strict JS/Python tests cover duplicate Lore, wrong/missing/denied targets, source/current distinctions and stale current-only values. | Representative NPC runtime gap closed below. Conditional skill variants remain explicitly unevaluated. |
| Join authored attacks, abilities, Lore, casting, possessions and supported state | Production `readActor` plus combined `actor-integrated-readers.test.js` checks actual authored melee/action references, current Strike rows, source/current Lore, repeated casting contexts, inventory and condition/effect identities together. | Verified integrated composition, not exhaustive actions or active benefits. |
| Preserve raw/mapped fields, contributing documents, completeness and bounded continuation | `test_actor_integrated.py` validates actual production JS pages through Python, forwards returned cursors, checks byte/count limits, stable revisions, unique keys, owned contributor IDs and source/transformed bases. Combined continuation tests reject current, owned source and permission changes. | Verified at commit `a87a830`. |
| Canonical journal/discovery/world/pack/token identities never substitute for each other | Existing CORE-journal verification follows a real journal NPC to its actual owned Item. Shared document/pack tests and combined world/token reads preserve canonical owner/instance selectors with no base-source substitution. | Verified adapter boundaries; full contextual end-to-end acceptance remains CORE-acceptance's separate gate. |
| Errors and read-only behavior remain explicit | Shared document and reader tests cover non-PF2e, denied/missing/unsupported selectors. Combined fixtures make mutation, preparation and roll entry points throw and fingerprint source/current/owned data. Scoped live runs preserve fingerprints. | Verified; no imports, activation, casting, rolls, chat or reader writes. |

## Current Skills runtime evidence

The existing-world NPC selection census found 172 NPCs with current skill maps;
12 had resolved owned Lore claims. The representative selected NPC passed
**221 current rows across 23 pages, one source Lore reference and one current
owner-local Lore join in 36 MCP calls**. Every returned raw witness and mapped
field was independently checked, including transformed basis and exact source
versus display-name contracts. A canonical Lore follow-up retained the actual
owner. Complete selected fingerprints matched before and after reading.

The later character verification reused the same Skills runner for NPC and
character contexts: 42 total pages, 408 current rows, two source Lore references
and two resolved joins in 64 nested calls. Those are combined counts, not
additional NPC-only totals. No extra NPC fixture was created to repeat passing
evidence. This closes the previously recorded representative NPC current-Skills
gap; it does not evaluate conditional checks or infer all Lore possessions from
one prepared-map contributor.

## Preserved limits and separate gates

The original story permits supported fields alongside explicit partial or
unsupported sections and requires evidence before claiming full current
statistics. Completion therefore covers the selected, verified source/current
boundaries and their integration, not unsupported effective behavior.

Current damage, target eligibility, area/auto-fire current interpretation,
conditional skill variants, complete ability enumeration, IWR application and
full current statistics remain unsupported or unevaluated. Casting contexts do
not establish available/legal casts. State application remains unknown; stored
override claims and effect expiry booleans do not prove effective condition
suppression. Dedicated affliction functionality is Deferred outside current
delivery by the user's explicit decision and remains visibly unsupported.

Full world/compendium/token and journal workflows, the existing same-base
unlinked token-pair requirement, and compatibility beyond Foundry14.369/PF2e8.6.1
retain their separate gates. The original Actor story explicitly assigns
contextual end-to-end acceptance to CORE-acceptance; this scoped closure does not
replace that evidence or count CORE-token complete.
