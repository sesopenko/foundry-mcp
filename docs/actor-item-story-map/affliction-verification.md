# Affliction evidence and runtime boundary

## Approved deferral and actual interface verification — October 25, 2026

The user explicitly deferred dedicated Affliction Items from this delivery until
PF2e maintainers complete upstream functionality. The original schema/rulebook
research below is retained for that follow-up, not offered as a runtime reader.
ITEM-affliction is Deferred and excluded from current delivery progress and
condition/effect dependencies; it is not Complete.

The fresh-client `scripts/affliction-interface-check.py` passed against the
running development server and refreshed GM bridge in four MCP calls. It checked
all **22 published tool input schemas**, including nested enum/const definitions,
for unusable affliction selectors and verified the descriptions' explicit
unsupported boundaries. The registry reports in_scope/source/mapped/effective
false. Both owned-Item and compendium Item affliction filter attempts were
rejected at input validation, using nonexistent placeholders; zero documents
were read, loaded, created or changed. No source, stage or timer fallback exists.
Seven offline checker tests reject misleading schemas/descriptions, false support
flags, accepted filters and backend missing-document errors posing as validation.

## Historical rulebook and runtime research

Verified October 20, 2026 (local date), against Foundry **14.369 / PF2e 8.6.1**.
This records rulebook reads and a read-only fixture audit; it does not establish
effective progression, application, recovery or expiry support.

## Actual rulebook pages

The GM-private PDF MCP returned each complete canonical extracted page below.
Both reads used `max_characters: 8000`, returned `next_offset: null`, and needed
no continuation. Warnings included unverified reading order/table structure and
untrusted source content. No numeric table associations were inferred.

| Book | Printed page | Physical page | Revision | Complete characters |
| --- | --- | --- | --- | --- |
| Player Core Remaster | 430 | 431 | `9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22` | 4510 |
| GM Core Remaster | 86 | 87 | `8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e` | 4663 |

Player Core p. 430 separates an initial saving throw, optional onset, maximum
duration, and stage definitions with individual intervals. Subsequent saves can
raise or lower stages; advancing beyond the highest listed stage repeats that
stage's effects. Ending an affliction does not necessarily end its conditions:
normal condition durations and the affliction's exceptions still matter.
Additional poison exposures have different progression rules from repeat
exposure to an existing curse or disease. Consequently, a stored stage and a
duration unit alone cannot establish active effects, recovery or expiry.

GM Core p. 86 explains that many curses have one effect and a specified duration
or removal requirement. Staged curses are uncommon and use the affliction rules.
A reader must therefore preserve an empty stage list and description rather
than manufacture stage 1 effects for every curse.

## Pinned schema versus prepared state

The immutable [8.6.1 affliction schema](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/affliction/data.ts)
defines persisted `status.onset`, `status.stage`, `status.progress`, optional
`onset`, ordered `stages`, maximum `duration`, `start`, `save`, `fromSpell` and
effect `context`. Stage damage formulas/categories, condition slugs/values/link
flags, effect UUIDs and interval units are distinct fields. Array indexes are
zero-based; the stored status stage is one-based. Progress is described as
recovery progress relevant to virulent afflictions, not a generic percentage.

The same source's `prepareBaseData` clamps prepared `status.stage` to the number
of definitions, treating no definitions as a maximum of one. This implementation
detail explains why observed prepared state can differ from selected persisted
source. It is **not** an adopted public API. Source readers must use
`toObject(true)`, retain the actual stored stage, and label a missing/nonintegral/
out-of-range definition match explicitly rather than reproducing that clamp.
An in-range match identifies a definition, not proof its effects are active.

The [8.6.1 Item constructor](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/affliction/document.ts)
rejects affliction construction in production builds. Installed
`foundry-data/Data/systems/pf2e/pf2e.mjs` independently contains that unconditional
production constructor rejection (line 48922 during this audit). Installed
source inspection explains the runtime limitation; it does not authorize
constructing Items through an alternate class, bypassing the guard, or calling
preparation, advancement, damage, recovery, linked-item or expiry internals.
No constructor or gameplay method was invoked in this audit.

## Read-only live fixture audit

Native `execute_javascript` returned core `14.369` and PF2e `8.6.1`. The audit
found **zero world affliction Items** and **zero affliction Items owned by
supported world Actors** (`character`, `npc`, `familiar`). It searched all **26
Item pack indexes** using `getIndex({fields: ['type']})`, with **zero affliction
candidates and zero failed pack searches**. A separate scan of **565 supported
Scene token Actor contexts** through public `TokenDocument.actor` found zero
affliction Items; repeated linked Actor contexts were not deduplicated. Actor
compendium embedded Items were not exhaustively hydrated or audited.
No names, identifiers, descriptions,
damage, DCs or other campaign content were returned. No documents were imported,
created, changed, advanced, rolled or deleted.

The pack audit's selected-hydration branch was ready to validate each candidate
through public APIs:

```javascript
const index = await pack.getIndex({fields: ['type']});
for (const entry of index.filter(entry => entry.type === 'affliction')) {
    const item = await foundry.utils.fromUuid(pack.getUuid(entry._id));
    if (item?.documentName === 'Item' && item.type === 'affliction') {
        const source = item.toObject(true);
        // Validate source.type before using a bounded affliction selector.
    }
}
```

**That branch did not run:** there were no candidates. This snippet supplies no
claim that an existing pack affliction was hydrated successfully. It is not a
production dependency or permission-check replacement. A selected reader must
still apply the existing document/pack permissions and canonical identity
checks. Type discovery and a schema declaration do not establish constructible
content in this production runtime.

Coverage remains absent for an actual world, owned or compendium affliction;
linked/synthetic token affliction source; populated stage/context/effect links;
and source-versus-prepared stage differences observed on an instantiated Item.
Pure fixtures can verify deterministic source translation and boundary
validation, but cannot close these live gaps. Current timer/application APIs,
legacy migrations, future PF2e releases and Foundry v13 support remain
unverified. No fixture should be manufactured by bypassing the production guard.

## Reader boundary verification

Focused fixtures verify UnsupportedType before source extraction, false runtime
support flags, unaffected owned-Item navigation and unsupported condition-parent
references. The pure schema selector separately verifies five source/stage cases;
it is excluded from runtime reader packaging. Full offline suites passed (193
Python tests, one skipped; 176 JavaScript tests). Actual authenticated MCP
confirmed affliction support flags remain false/live not_run and regression-checked
delivered readers after refresh. No affliction was hydrated or created, so this
is capability-boundary evidence, not a live affliction-reading claim.
