# Character owned ability navigation

Implemented boundary for explicit `read_actor(sections=['abilities'])` on
characters, Foundry14.369/PF2e8.6.1, pinned revision
`28d9d156f252d084371d994dc359509b49eadf18`. Runtime evidence is recorded below
and this checkpoint alone does not complete ACT-character.

Public Actor.items, Item.parent/uuid/testUserPermission and `toObject(true)`
supply actual owned identities and persisted source. Pinned PF2e
[ability](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/ability/data.ts)
and [feat](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/feat/data.ts)
contracts establish the selected Item types. No preparation, activation, roll,
grant application, sheet data or effective-benefit calculation is used.

## Exact response contract

Every actual readable owned `action` or `feat` Item appears once, including
ordinary feats and feature-category Items. Sort by persisted lowercase name,
then actual UUID; duplicate names remain separate documents. Other Item types
are excluded. Actual parent and collection membership must match the selected
Actor. Check permission before source or identity extraction; denied names and
source are never read.

Each relationship has key `abilities:item:<actual Item UUID>`, section
`abilities`, kind `relationship`, concept `character_ability_item`, unit null,
mapping `pf2e.character.ability-reference.v1` and exactly one limitation:
`owned_item_reference_not_complete_or_active_ability`.

Raw witnesses are exactly `/name` then `/type`, both present with `basis: source`
and the actual owned Item UUID. Contributors match those witnesses exactly.
Mapped value is `{status: resolved,target_uuid,type,name,name_truncated}` with
the selected `token_uuid` additionally present for token contexts. Type is
`action` or `feat`; mapped names use the exact persisted source clipped to 256
Unicode codepoints. Raw names remain exact, with a 6,000 UTF-16-unit bound.
Selected source accessors are rejected without invocation; nonplain containers
with own data properties are allowed. Public display labels are not substituted.

One aggregate denied relationship has key `abilities:items:denied`, the same
mapping/concept/limitation, empty raw/contributors and
`{status: denied,target_uuid: null}`. It exposes no names, IDs or counts.

The section is always partial, including an empty collection. Its reasons
always include `other_abilities_not_enumerated`; denial adds
`ability_items_denied`, and shared pagination may add `pagination`. Snapshot
selection admits at most 12,000 owned Items, yielding at most 12,000 ability
relationships including any denial aggregate. These bounds differ from page
count/UTF-8 byte limits.
Malformed source, membership or bounds fail actionable `ReadFailed`.

## Follow-up and meaning

Use `read_item(item_uuid=target_uuid, token_uuid=token_uuid when returned)` with
source and description selected. Its typed reader supplies activation/category,
requirements, frequency and exact prose. A `feat` Item may be a feat or a class/
ancestry feature; this navigation view does not infer that classification.
Ownership establishes the document, not active benefits or current usability.

Basic actions, generated capabilities and equipment-only prose abilities are
not enumerated. This is not an exhaustive action list. Build/inventory/state
remain separate views with shared contributor identities. Default/source-only
Actor reads do not serialize owned abilities. Selected identities/source and
permission changes participate in revision checks; pass returned continuations
unchanged. NPC/familiar ability contracts retain their existing behavior.

Dedicated affliction Items remain deferred and unreadable; they cannot become
abilities through this view or a readable-type filter.

## Deterministic verification

Pure helper and actual reader tests cover action/feat/feature identities,
duplicates, exact source names and Unicode clipping, permissions, parent/member
forgery, source accessors, world/compendium/token context, pagination, relevant
staleness, bounds and source/default exclusion. Python checks actual paginated
JavaScript DTOs and fresh MCP discovery, rejecting forged owner/token/type,
names, provenance, keys and false completeness.

## Runtime verification — October 25

The existing test world supplied one genuine marked temporary character with
three inert owned Items: an action, an ordinary feat and a class feature. They
shared a name but retained distinct canonical identities. Actual MCP verified
all three ability references, then followed every Item through source and exact
description continuations: **one Actor page, 13 Item pages and 75 source checks
in 24 requested/completed calls**. Source categories retained the ordinary-feat
versus feature distinction without inferring active benefits. Exact description
hashes, UTF-16 boundaries and full source fingerprints matched.

Exact UUID/type/run-marker cleanup passed, with zero pending creations and zero
remaining marked Actors. Eight offline harness tests cover deferred creation,
lost responses, cleanup identity, bounded clients, source normalization and
rejection of incorrect returned prose/values. No existing document was changed,
and no activation, roll or grant was executed.

Two earlier diagnostic runs stopped in the verifier and both cleaned up. The
root cause was an own `undefined` optional source property being mistaken for
persisted presence. An actual `actionFields` regression failed before the fix;
the independent comparison now uses canonical serialized source, matching the
reader's documented optional-field semantics. The successful run confirmed
14 such source absences. The description input was unchanged; HTML normalization
was ruled out, and no production-reader correction was needed for this failure.

World character navigation now has live evidence. Character pack/token contexts,
denial and stale reads have deterministic evidence; those live configurations
remain unverified. Combined Actor-section acceptance remains a separate gate.
