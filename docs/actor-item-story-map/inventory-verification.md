# Actor inventory evidence

Verified October 22, 2026 against Foundry **14.369 / PF2e 8.6.1**.
This audit supplies rulebook, schema and available-fixture evidence for
[CORE-inventory](stories/CORE-inventory.md). Production reader acceptance is
separate; a source audit alone does not prove the implemented reader works.

## Actual rulebook reads

Read complete canonical pages through the private PDF MCP. Every page returned
`next_offset=null`; extraction reading order and table structure remain
unverified. No numeric table relationships were inferred from adjacency.

| Book | Printed / physical pages | Character counts |
| --- | --- | --- |
| Player Core Remaster | 267 / 268; 268 / 269; 269 / 270 | 5156; 3702; 5489 |
| GM Core Remaster | 219 / 220; 220 / 221 | 5038; 5044 |

Player Core revision:
`9e34130ba88cb6a700f588d8837c9ad0b1e5122bbf5e75f4d19f8bf3b575cd22`.
GM Core revision:
`8d1d540e6e649277342cbb1b09d22f8609302a94d4dea6a2bda65179d4c3276e`.

Player Core distinguishes held, worn and stowed possessions. Wielding requires
holding an item in sufficient hands for use; simply possessing or holding an
item does not establish wielding. Retrieving a stowed item and opening its
container can require separate actions. Starting equipment packages describe
bundles with constituent gear, rather than a second set of possessions to add
to the gear already owned. Currency denominations, item purchase Price and
resale rules are separate facts. Quantity and price basis should remain visible
without an inferred wallet or sale proceeds. Bulk includes rounding, coin
aggregation and special handling, so a simple source-field sum is insufficient.

GM Core distinguishes constant benefits, investment and activation. Wearing or
holding an item alone does not establish all its magical benefits. Investment
has daily and continuing requirements; a stored investment flag does not prove
all prerequisites remain satisfied. Permanent-item activations can appear in
description paragraphs. Preserve exact prose for follow-up `read_item` reads;
absence of structured activation fields is not absence of an activation.

## Pinned schema contracts

The local upstream clone is pinned to PF2e 8.6.1 revision
`28d9d156f252d084371d994dc359509b49eadf18`.

- [Physical source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/physical/data.ts)
  declares `quantity`, nullable `containerId`, stored carrying fields,
  independently optional price denomination leaves and price-per basis.
  Investment is type-dependent and nullable. Optional source members must not
  become invented zero/false values. Derived `stackGroup`, `bulk.per`, effective
  usage and broken threshold are outside this persisted-source join.
- [Weapon source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/weapon/data.ts)
  declares nullable local `selectedAmmoId` and serialized physical `subitems`.
  A selected-ammunition claim needs same-owner identity resolution; carried
  stacks do not establish compatibility, loading, ammunition consumption or
  current Strike options.
- [Shield source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/shield/data.ts)
  declares serialized adjustments/attachments/talismans under `subitems`.
  Integrated-weapon configuration is source data under `traits.integrated`,
  not proof of a separate owned Item or generated attack UUID.
- [Container source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/container/data.ts)
  uses type `backpack` for containers generally; containment joins originate
  from actual child Items' `containerId`, not a prepared contents getter.
- [Book source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/book/data.ts)
  is physical and stores category, capacity and Item-UUID contents. Those
  referenced definitions are distinct from actual owned possessions.
- [Kit source](https://github.com/foundryvtt/pf2e/blob/28d9d156f252d084371d994dc359509b49eadf18/src/module/item/kit/data.ts)
  is a bundle definition with nested named component UUIDs, quantities and
  container flags. It is not an ordinary physical possession. Never import or
  recursively hydrate components to construct the actual Actor inventory.

Use actual selected Actor `items`, document identity and `toObject(true)`;
selected tokens use their actual `actor` without base-Actor substitution.
Existing public Foundry document contracts are recorded in the
[API/source evidence ledger](evidence.md). Source-schema relationships do not
authorize prepared system internals, sheet data or UI scraping.

## Read-only live fixture scope

Inspected public world Actors and scene tokens' actual Actors, deduplicating
actual Actor UUIDs and filtering **character/NPC/familiar before counting**.
There are **172 world NPCs** and **559 additional synthetic NPCs**: 731 supported
instances. No populated character or familiar exists in either scope.

| Physical type | World NPC owned | All distinct supported instances |
| --- | --- | --- |
| weapon | 61 | 449 |
| armor | 21 | 118 |
| equipment | 29 | 198 |
| consumable | 25 | 135 |
| ammo | 11 | 103 |
| treasure | 5 | 14 |
| shield / backpack / book | 0 / 0 / 0 | 0 / 0 / 0 |
| Total | 152 | 1017 |

Across the 1017 actual physical Items, carrying source is held for 274 and worn
for 743. There are 765 explicit `equipped.invested=null` values, 103 non-unit
stored `price.per` values (all ammunition with basis 10) and 234 quantities
above one. None has a nonempty
`containerId`, selected ammunition ID or serialized attachment. No kit Item was
found on these supported instances. Each inspected physical Item's serialized
source compared equal before and after inspection. These are equality checks,
not independently measured cryptographic fingerprints.

These gaps require deterministic same-instance fixtures for nested containers,
orphan and wrong-type parents, rootless cycles, multiple ammunition stacks,
selected-ammunition resolution, serialized attachments, book/kit definitions
and duplicate generated-component references. The excluded loot Actors'
containers cannot establish supported owned-container runtime acceptance; see
[container verification](container-verification.md). No new world, Actor or
Item should be created merely to populate these gaps.

## Production reader acceptance

Consume actual paginated `read_actor(sections=["inventory"])` responses for
supported world and synthetic NPCs, checking each real possession appears once,
child source provenance remains scoped to its actual owner, independent
quantity/price-per/denominations and carrying values match source, and no
unselected definitions are hydrated. Follow returned canonical Items with
`read_item` for exact prose and specialty source. Check unchanged complete
source fingerprints and stale continuation rejection after deterministic
source/relationship changes. Denied/malformed references must remain explicit
without leaking names or claiming an empty collection.

Baseline source inventory does not require an effective Bulk, sale, activation
eligibility or attack engine. Pending optional book/kit interpretation must be
explicit without blocking ordinary physical possession delivery. Neither the
live fixture audit nor the book reading by itself closes CORE-inventory.


Production MCP verification completed with the fresh authenticated SDK client
against the existing service and GM browser. Three selected world/token Actor
contexts cover all six available physical types. All pages were consumed,
canonical possession UUIDs appeared once, same-owner source donors and token
context matched, and quantity/price-per/denomination/carry fields matched exact
stored values. Absent container/ammo claims retained missing/null distinctions.
Canonical Item follow-ups use `read_item` identity without hydration of unrelated
definitions. Complete Actor source SHA-256 fingerprints remained unchanged.
Discovery exposed inventory source/mapped support with effective support false.

Live verification exposed PF2e prepared Item display names that differ from
stored source names. A failing deterministic test reproduced the provenance
mismatch. Inventory now consistently labels references using cached persisted
names, including ammunition/container targets, with Unicode-aware clipping;
strict Python validation remains unchanged. Follow-up Item identity may display
a different prepared name, while its canonical UUID is the same.

Full suites pass:259 Python tests (one skipped),305 JavaScript tests. The
11 helper tests plus three shared-reader tests and eight Python boundary tests
cover acceptance, token contexts, stale continuations, denied data, malformed
source and system boundaries. No imports, rolls, activation or game writes
occurred. Missing live fixtures above remain explicit limitations, not reasons
to infer unsupported effective calculations.
