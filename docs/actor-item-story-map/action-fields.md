# Action Item selected source fields

ITEM-action selected source and immediate relationship reader evidence, October 20, 2026. Delivered through `read_item` on Foundry14.369/PF2e8.6.1.

The selector accepts detached `Item.toObject(true)` data for `type="action"`.
It returns `null` for other types. Every descriptor has `path`, `present`,
`concept`, `limitations`, and `value` only when present. Known activation codes
also have `mapped_value`. Paths are JSON Pointers into the original source.
No source defaults or prepared getters fill missing values.

## Pinned technical evidence

PF2e **8.6.1**, commit `28d9d156f252d084371d994dc359509b49eadf18`, was
confirmed in the local ignored upstream checkout. These definitions were read:

- [Ability source schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts): activation, count, category, deathNote, frequency and self-effect fields.
- [Shared Item source model](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/base/data/model.ts): publication, slug and shared trait tags.
- [Configuration codes](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/scripts/config/index.ts): action/reaction/free/passive discriminators and familiar category.

Implementation/preparation bodies were read only to establish exclusions:
frequency remaining uses can be initialized during preparation; a passive
ability's prepared self-effect can be cleared. The selector retains stored
values and does neither operation. Public Foundry document extraction and
permissions remain owned by [the shared contract](../actor-tools.md), not this
pure selector. No new Foundry API calls are introduced here.

## Allowlist and mappings

All paths below start with `/system/`.

| Source path | Mapped concept and interpretation |
| --- | --- |
| `actionType/value` | `activation_kind`: action → `action_or_activity`, reaction → `reaction`, free → `free_action`, passive → `passive_ability`; unknown code retained with limitation |
| `actions/value` | `action_count`; stored number or null; never determines activation kind |
| `category` | `ability_category_code`; familiar remains an ability category, not an actor/master inference |
| `deathNote` | `death_note_source_flag`; source metadata, not a condition, frequency or current death state |
| `slug` | `source_slug`; original string or null |
| `traits/value/<index>` | `ability_trait_code`; original codes, order and duplicates retained |
| `traits/otherTags/<index>` | `ability_other_tag_code`; no unverified localization lookup |
| `frequency/value` | `recorded_frequency_remaining`; missing is uninitialized/absent source, zero remains zero; no availability calculation |
| `frequency/max` | `frequency_maximum`; source maximum, not proof of current usable actions |
| `frequency/per` | `frequency_interval_code`; original interval code, no resource normalization |
| `selfEffect/uuid` | `self_effect_uuid`; named unverified source reference, never applied, fetched or converted to a fabricated selector |
| `selfEffect/name` | `self_effect_name`; stored label, not a verified target name |
| `publication/title`, `publication/authors`, `publication/license`, `publication/remaster` | Corresponding `publication_*` source metadata; no edition-precedence assumption |

Missing/null frequency and self-effect containers emit one absent/null container
record; objects emit selected primitive leaves only. Explicitly empty trait
arrays emit `[]`; nonempty arrays emit indexed strings, preserving count and
order. Malformed allowlisted objects/scalars fail rather than leak arbitrary
objects. No truncation is performed here; reader pagination/text handling owns
response bounds, and indivisible metadata may return `ResponseTooLarge`.

Descriptions remain exact bounded text requested through `description`.
Triggers, requirements and exceptions are not guessed from the activation
fields. `rules` is never implicit. Trait toggles, derived action cost, suppressed
state, rule-element results and complete actor activities remain excluded.
Self-effect resolution requires the shared relationship reader; this selector
only exposes its stored name/UUID with explicit unverified limitations.

## Rulebook evidence and acceptance

Player Core Remaster source pages were actually reread through PDF MCP on
October 20, 2026, revision
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`:
printed **15, 414, 212–213**, physical **16, 415, 213–214** respectively.
Every page returned `next_offset=null`. Extraction warns that reading order and
table structure are unverified; no table relationships were inferred.

Pages 15/414 distinguish free actions, reactions, single actions and activities.
An activity can use one action, a reaction or a free action, so count alone cannot
classify it completely. Pages 212–213 describe familiar and master abilities;
the familiar category must not imply ordinary combat actions, selected benefits
or master-derived statistics without the owning actor evidence.

Focused deterministic tests verify activation/null-count distinctions,
source-only frequency, named unverified self-effects, familiar category,
unknown/duplicate traits, absent/null/zero/empty distinctions, no source mutation
and malformed-data rejection. Parent/pack/token identity, permissions, bounded
descriptions, MCP discovery and read-only behavior are separately verified in the
reader integration evidence below. No effective-value support is claimed.

## Existing-runtime source and relationship evidence

A read-only fresh authenticated FastMCP client on October 20, 2026 checked the
existing core14.369/PF2e8.6.1 development world without creating or updating
any documents. On supported world Actors it found 557 embedded action Items:

| Activation source code | Count | Null `actions.value` |
| --- | ---: | ---: |
| passive | 320 | 320 |
| action | 197 | 0 |
| reaction | 34 | 34 |
| free | 6 | 6 |

No standalone world action Item was available. Six embedded actions had named
source self-effect references. One was resolved using the public async
[`foundry.utils.fromUuid(uuid, {relative: item})`](https://foundryvtt.com/api/v14/functions/foundry.utils.fromUuid.html),
which returns `Promise<Document | null>`. Its target was an Item of type effect;
target and containing-pack OBSERVER permission checks passed. The originating
Item's serialized source was unchanged before/after resolution. This verifies
read-only lookup, not activation or benefits. A production relationship reader
must also validate canonical target UUID/type and applicable owner permissions,
retain explicit missing/denied/unsupported results, and incorporate selected
relationship dependencies into continuation revisions.

One action was hydrated from the existing familiar-abilities compendium without
importing it. Its source category was `familiar`, activation code `action`, and
count non-null. Its parent was null, compendium accessor matched the selected
pack, and Item OBSERVER permission passed. Source snapshots before/after reads
matched. This is a familiar-ability Item sample, not a populated familiar/master
Actor test. Standalone world action identity remains deterministic coverage.

Own source properties with `undefined` were common: `deathNote` on 540 actions,
`frequency` on 519, and `selfEffect` on 551. The pinned Ability schema explicitly
uses `initial: undefined` for these optional fields and for `frequency.value`.
They must remain absent selected values rather than being replaced by prepared
false, null, or maximum frequency uses. These live shapes complement, rather
than replace, the pinned source contracts. No private document names, IDs, or
UUIDs were retained in this evidence.

## Reader integration acceptance

The exact registry is integrated into source records with `pf2e.action.source.v1` provenance. Complete means all selected source records after pagination, not all possible activities or effective benefits. `effective` and `rules` remain explicitly unsupported. `description` retains exact text and triggers/requirements without interpreting or executing it.

Schema-optional own undefined `deathNote`, `frequency`, `frequency.value` and `selfEffect` are absent selected source. A regression test failed before the narrow correction; no prepared defaults or frequency maxima are substituted.

Explicit `relationships` emits one `self_effect` relationship record, retaining UUID/name source contributors and resolved/missing/denied/unsupported/unverified status. Target UUID is null unless canonical resolution and effect/owner/pack authorization succeed. Resolved synthetic targets also return token_uuid after public Actor.token and token.actor/membership checks. Call `read_item(item_uuid=mapped.value.target_uuid, token_uuid=mapped.value.token_uuid)` when token context is present. No recursive expansion, activation, rolls, chat or writes occur. Source-only reads never resolve the effect.

Live actual MCP checks passed for passive/free/reaction/action, a familiar compendium ability, a placed-token action, and immediate self-effect follow-up. Before/after persisted source fingerprints for the selected action, self-effect-bearing and token samples were equal. The fixed probe uses bounded chunks because the development serializer clips individual strings to 1000 characters; truncated probes are rejected and tested rather than treated as complete evidence.

No standalone world action or live synthetic self-effect-target fixture was present. World/pack/embedded identity and synthetic follow-ups have deterministic public-boundary coverage; this does not close familiar/master derived statistics or other Actor integration gates. Tests: `actor-action.test.js`, `actor-action-readers.test.js`, `test_actor_action.py` and the shared identity/reader suites.
